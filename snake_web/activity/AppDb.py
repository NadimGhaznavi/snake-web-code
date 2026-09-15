"""Application queries for Snake Lab data."""

from snake_web.interface.DbMgr import DbMgr


class AppDb:
    def __init__(self, db: DbMgr):
        self._db = db

    def get_current_highscore(self) -> int | None:
        """Highest recorded score across all runs; None before any score exists."""
        return self._db.query(
            "SELECT MAX(high_score) AS high_score FROM simulation_runs"
        )[0]["high_score"]
