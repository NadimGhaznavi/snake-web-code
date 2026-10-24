"""Exercise release confirmation and publication using a local bare remote."""

import ast
import os
from pathlib import Path
import pty
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONSTANTS = "snakewebcode/constants/DSnakeWebCode.py"


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="snakewebcode-release-")
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name) / "repo"
        self.repo.mkdir()
        self.remote = Path(temporary.name) / "remote.git"
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0",
                        GIT_AUTHOR_NAME="Release Test", GIT_AUTHOR_EMAIL="test@example.invalid",
                        GIT_COMMITTER_NAME="Release Test", GIT_COMMITTER_EMAIL="test@example.invalid")
        self.git("init", "-b", "main")
        self.git("init", "--bare", str(self.remote))
        self.git("remote", "add", "origin", str(self.remote))
        for name in ("scripts/new-release.sh", CONSTANTS):
            destination = self.repo / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)
        (self.repo / CONSTANTS).write_text(
            'from typing import Final\n\nclass DSnakeWebCode:\n'
            '    VERSION: Final[str] = "0.0.1"  # keep version comment\n'
            '    CMDB_CODENAME: Final[str] = "Original"  # keep codename comment\n')
        (self.repo / "CHANGELOG.md").write_text(
            '# Changelog\n\n## [Unreleased]\n\n### Added\n\nFirst feature.\n')
        self.git("add", ".")
        self.git("commit", "-m", "Initial project")
        self.git("branch", "dev")
        self.git("push", "origin", "main", "dev")
        self.git("switch", "-c", "feat/maint-0.1.0")
        (self.repo / "feature.txt").write_text("Feature content\n")
        self.git("add", ".")
        self.git("commit", "-m", "Add feature")

    def command(self, *args, **kwargs):
        return subprocess.run(args, cwd=self.repo, env=self.env, text=True,
                              capture_output=True, timeout=20, **kwargs)

    def git(self, *args):
        return self.command("git", *args, check=True).stdout.strip()

    def release(self, *args, answer="y"):
        if answer is None:
            return self.command("bash", "scripts/new-release.sh", *args, input="y\n")
        master, slave = pty.openpty()
        try:
            os.write(master, (answer + "\n").encode())
            return self.command("bash", "scripts/new-release.sh", *args, stdin=slave)
        finally:
            os.close(master)
            os.close(slave)

    def assert_rejected(self, args, error):
        before = self.git("show-ref")
        branch = self.git("branch", "--show-current")
        result = self.release(*args)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(error, result.stderr)
        self.assertEqual(self.git("show-ref"), before)
        self.assertEqual(self.git("branch", "--show-current"), branch)

    def test_release_publishes_version_codename_branches_and_annotated_tag(self):
        codename = 'kēkā "quoted" \\ $(literal) `literal`'
        result = self.release("0.1.0", codename)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git("branch", "--show-current"), "feat/maint-0.1.1")
        head = self.git("rev-parse", "HEAD")
        for ref in ("main", "dev", "origin/main", "origin/dev", "v0.1.0^{commit}"):
            self.assertEqual(self.git("rev-parse", ref), head)
        self.assertEqual(self.git("cat-file", "-t", "v0.1.0"), "tag")
        self.assertEqual(self.git("log", "-1", "--format=%s"), "Release 0.1.0: " + codename)
        constants = (self.repo / CONSTANTS).read_text()
        values = {node.target.id: ast.literal_eval(node.value)
                  for node in ast.walk(ast.parse(constants)) if isinstance(node, ast.AnnAssign)}
        self.assertEqual(values, {"VERSION": "0.1.0", "CMDB_CODENAME": codename})
        self.assertIn('# keep version comment', constants)
        self.assertIn('# keep codename comment', constants)
        changelog = (self.repo / "CHANGELOG.md").read_text()
        self.assertIn("## [0.1.0] - ", changelog)
        self.assertEqual(changelog.count("## [Unreleased]"), 1)
        self.assertTrue(changelog.endswith("### Added\n\nFirst feature.\n"))
        self.assertEqual(self.git("status", "--porcelain"), "")
        remote = self.git("ls-remote", "origin")
        self.assertIn("refs/tags/v0.1.0", remote)
        self.assertNotIn("refs/heads/feat/", remote)

    def test_prerelease_and_explicit_next_branch(self):
        result = self.release("0.1.0-rc.1+build.01", "Candidate", "feat/next")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git("branch", "--show-current"), "feat/next")
        self.assertIn('"0.1.0-rc.1+build.01"', (self.repo / CONSTANTS).read_text())

    def test_cancel_and_noninteractive_execution_do_not_create_a_release(self):
        before = self.git("show-ref")
        constants = (self.repo / CONSTANTS).read_bytes()
        changelog = (self.repo / "CHANGELOG.md").read_bytes()
        for answer in ("n", "", None):
            with self.subTest(answer=answer):
                result = self.release("0.1.0", "Candidate", answer=answer)
                if answer is None:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("interactive terminal", result.stderr)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("Release cancelled", result.stdout)
                self.assertEqual(self.git("show-ref"), before)
                self.assertEqual((self.repo / CONSTANTS).read_bytes(), constants)
                self.assertEqual((self.repo / "CHANGELOG.md").read_bytes(), changelog)

    def test_invalid_arguments_leave_refs_unchanged(self):
        for version in ("v0.1.0", "01.2.3", "0.1.0-01", "0.1.0-rc.01", "0.1.0/evil"):
            with self.subTest(version=version):
                self.assert_rejected((version, "Release"), "Use a version")
        self.assert_rejected(("0.1.0", "  "), "A release message is required")
        self.assert_rejected(("0.1.0", "Release", "dev"), "Next feature branch already exists")

    def test_dirty_tree_and_main_branch_are_rejected(self):
        (self.repo / "uncommitted.txt").write_text("Pending work")
        self.assert_rejected(("0.1.0", "Release"), "Commit or stash")
        self.git("switch", "main")
        self.assert_rejected(("0.1.0", "Release"), "Run from a feature branch")

    def test_invalid_constants_are_rejected_before_branch_changes(self):
        path = self.repo / CONSTANTS
        original = path.read_text()
        for declaration in ('    VERSION = "duplicate"\n', '    CMDB_CODENAME = "duplicate"\n'):
            path.write_text(original + declaration)
            self.git("add", ".")
            self.git("commit", "-m", "Invalid release constants")
            self.assert_rejected(("0.1.0", "Release"), "Cannot read SnakeWebCode release constants")

    def test_rejected_push_does_not_publish_any_release_refs(self):
        hook = self.remote / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        remote_before = self.git("ls-remote", "origin")
        result = self.release("0.1.0", "Candidate")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Stopped during Push release refs atomically", result.stderr)
        self.assertEqual(self.git("ls-remote", "origin"), remote_before)
        self.assertEqual(self.git("branch", "--show-current"), "dev")
        self.assertEqual(self.git("cat-file", "-t", "v0.1.0"), "tag")
        self.assertNotEqual(self.command("git", "show-ref", "--verify",
                                        "refs/heads/feat/maint-0.1.1").returncode, 0)

    def test_help_uses_current_version_without_a_versioned_branch(self):
        self.git("switch", "-c", "feat/setup")
        result = self.release("--help", answer=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Likely next version: 0.0.2", result.stdout)
        self.assertEqual(self.git("status", "--porcelain"), "")
