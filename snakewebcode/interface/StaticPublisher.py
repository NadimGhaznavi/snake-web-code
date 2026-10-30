"""Replace the fixed public GIFs and metadata served by Caddy."""

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile


class StaticPublisher:
    DAILY_PATH = 'live.json'
    DAILY_GIF_PATHS = tuple(f'game-{name}.gif' for name in ('one', 'two', 'three', 'four', 'five'))
    DISTRIBUTION_PATH = 'score-distribution.gif'
    GIF_PATHS = (*DAILY_GIF_PATHS, DISTRIBUTION_PATH)

    def __init__(self, directory):
        self.directory = Path(directory)
        if not self.directory.is_absolute() or self.directory.resolve() != self.directory:
            raise ValueError('Public directory must be an absolute path without symlinks')

    def _path(self, name):
        if name not in (*self.GIF_PATHS, self.DAILY_PATH):
            raise ValueError('Not a managed artifact path')
        path = self.directory / name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise RuntimeError('Artifact paths must be regular files without symlinks')
        return path

    @contextmanager
    def session(self):
        self.directory.mkdir(mode=0o755, exist_ok=True)
        descriptor = os.open(self.directory.parent / f'.{self.directory.name}.lock',
                             os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield

    def read_history(self, name):
        path = self._path(name)
        return path.read_text(encoding='utf-8') if path.exists() else ''

    def read_bytes(self, name):
        path = self._path(name)
        return path.read_bytes() if path.exists() else b''

    def publish(self, state, files, *, updated):
        if not set(files).issubset(self.GIF_PATHS):
            raise ValueError('Not a managed GIF path')
        paths = {name: self._path(name) for name in (*self.GIF_PATHS, self.DAILY_PATH)}
        previous = json.loads(self.read_history(self.DAILY_PATH) or '{}')
        previous.pop('updated', None)
        changed = state != previous or any(self.read_bytes(name) != data for name, data in files.items())
        unused = set(self.GIF_PATHS) - set(files)
        if not changed and not any(paths[name].exists() for name in unused):
            return False
        # Invalidate the saved game list before changing slots. An interrupted pass
        # will regenerate captures rather than reuse a GIF under the wrong game ID.
        paths[self.DAILY_PATH].unlink(missing_ok=True)
        for name, data in files.items():
            if self.read_bytes(name) != data:
                self._replace(paths[name], data)
        for name in unused:
            paths[name].unlink(missing_ok=True)
        metadata = {**state, 'updated': updated}
        self._replace(paths[self.DAILY_PATH], (json.dumps(metadata, indent=2) + '\n').encode())
        return True

    @staticmethod
    def _replace(path, data):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
            temporary.chmod(0o644)
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
