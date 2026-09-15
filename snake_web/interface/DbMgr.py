"""Read-only MariaDB access. Never initializes or modifies source tables."""

import os

import pymysql
from pymysql.cursors import DictCursor


class DbMgr:
    def __init__(self):
        self._connection = pymysql.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", "3306")),
            unix_socket=os.environ.get("DB_SOCKET") or None,
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ.get("DB_NAME", "snakelab"),
            charset="utf8mb4", cursorclass=DictCursor,
            autocommit=False, connect_timeout=10, read_timeout=30, write_timeout=30,
        )
        try:
            with self._connection.cursor() as cursor:
                cursor.execute("START TRANSACTION READ ONLY")
        except Exception:
            self.close()
            raise

    def query(self, sql, params=None) -> list[dict]:
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())

    def close(self) -> None:
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
