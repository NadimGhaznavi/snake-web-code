"""Publish only the status page from a dedicated, serialized Git checkout."""

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import subprocess
import tempfile


class GitPublisher:
    STATUS_PATH = "pages/status/index.md"

    def __init__(self, checkout, branch="main"):
        self.checkout = Path(checkout).resolve()
        self.branch = branch
        self._git("check-ref-format", f"refs/heads/{branch}")

    def _git(self, *args, check=True):
        result = subprocess.run(
            ["git", "-C", str(self.checkout), *args],
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            capture_output=True, text=True, timeout=60,
        )
        if check and result.returncode:
            raise RuntimeError(f"Git {args[0]} failed: {result.stderr.strip()}")
        return result

    def _ancestor(self, first, second):
        result = self._git("merge-base", "--is-ancestor", first, second, check=False)
        if result.returncode not in (0, 1):
            raise RuntimeError("Cannot compare publishing branch history")
        return result.returncode == 0

    @contextmanager
    def session(self):
        top = Path(self._git("rev-parse", "--show-toplevel").stdout.strip()).resolve()
        if top != self.checkout:
            raise RuntimeError("Publishing checkout must be the repository root")
        git_dir = Path(self._git("rev-parse", "--absolute-git-dir").stdout.strip())
        with (git_dir / "snake-web-publish.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self._git("branch", "--show-current").stdout.strip() != self.branch:
                raise RuntimeError(f"Publishing checkout must be on {self.branch}")
            if self._git("status", "--porcelain", "--untracked-files=all").stdout:
                raise RuntimeError("Publishing checkout must be clean; inspect it before retrying")
            self._git("fetch", "--no-tags", "origin", f"refs/heads/{self.branch}")
            if self._ancestor("HEAD", "FETCH_HEAD"):
                self._git("merge", "--ff-only", "FETCH_HEAD")
            elif not self._ancestor("FETCH_HEAD", "HEAD"):
                raise RuntimeError("Publishing branch diverged; reconcile it before retrying")
            # Only retry unpublished commits whose changes are confined to status.
            commits = self._git("rev-list", "FETCH_HEAD..HEAD").stdout.splitlines()
            for commit in commits:
                parents = self._git("rev-list", "--parents", "-n", "1", commit).stdout.split()
                paths = self._git("diff-tree", "--no-commit-id", "--name-only", "-r", commit).stdout.splitlines()
                if len(parents) != 2 or paths != [self.STATUS_PATH]:
                    raise RuntimeError("Unpublished commits must change only the status page")
            yield

    def _status_file(self):
        path = self.checkout / self.STATUS_PATH
        if path.resolve() != path or not path.is_file():
            raise RuntimeError("Status page must be an existing file without symlinks")
        self._git("ls-files", "--error-unmatch", "--", self.STATUS_PATH)
        return path

    def read_status(self):
        return self._status_file().read_bytes().decode("utf-8")

    def publish(self, content):
        path = self._status_file()
        if path.read_bytes() != content.encode("utf-8"):
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(content.encode("utf-8"))
                temporary.chmod(path.stat().st_mode & 0o777)
                temporary.replace(path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            self._git("add", "--", self.STATUS_PATH)
            self._git("commit", "-m", "Update simulation high score", "--", self.STATUS_PATH)
        pending = self._git("rev-list", "--count", "FETCH_HEAD..HEAD").stdout.strip() != "0"
        if pending:
            self._git("push", "origin", f"HEAD:refs/heads/{self.branch}")
        return pending
