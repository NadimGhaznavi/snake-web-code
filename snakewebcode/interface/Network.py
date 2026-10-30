"""Resolve listener defaults and production overrides once per process."""

from functools import cache
from pathlib import Path

from snakewebcode.constants.DSnakeWebCode import DSnakeWebCode
from snakewebcode.interface.Configuration import Configuration


class Network:
    @staticmethod
    def binding(use: str, path: Path | None = None) -> tuple[str, int]:
        return Network._bindings(Configuration.path() if path is None else path,
                                 DSnakeWebCode.CMDB_NETWORK)[use]

    @staticmethod
    def destination(use: str, path: Path | None = None) -> tuple[str, int]:
        interface, port = Network.binding(use, path)
        return ('127.0.0.1' if interface == '0.0.0.0' else interface, port)

    @staticmethod
    @cache
    def _bindings(path: Path, defaults: tuple[tuple[str, str, int], ...]) -> dict[str, tuple[str, int]]:
        return Configuration.read(path, defaults)
