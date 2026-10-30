"""Read the source data needed by the daily games and score charts."""

from datetime import timedelta

from snakewebcode.interface.DbMgr import DbMgr


class AppDb:
    def __init__(self, db: DbMgr):
        self._db = db

    def get_run_scores(self) -> list[dict]:
        """Include current nullable scores in simulation submission order."""
        return self._db.query('SELECT id, high_score FROM simulation_runs ORDER BY id')

    def get_daily_game_day(self):
        """The database session uses UTC, matching Snake Lab completion timestamps."""
        return self._db.query('SELECT CURRENT_DATE AS day')[0]['day']

    def get_daily_progress_time(self):
        """Sample the UTC source clock used for simulation completions."""
        return self._db.query('SELECT CURRENT_TIMESTAMP AS observed_at')[0]['observed_at']

    def get_daily_configurations(self, day, observed_at) -> list[dict]:
        """Top ten completed scores, including runs without captured games."""
        return self._db.query('''
            SELECT id, high_score FROM simulation_runs
            WHERE status = 'completed' AND high_score IS NOT NULL
              AND completed_at >= %s AND completed_at < %s
              AND completed_at <= %s
            ORDER BY high_score DESC, id ASC LIMIT 10
        ''', (day, day + timedelta(days=1), observed_at))

    def get_daily_runs(self, day) -> list[dict]:
        """Rank today's completed scored runs; capture availability is checked over ZMQ."""
        return self._db.query('''
            SELECT id, run_id, high_score FROM simulation_runs
            WHERE status = 'completed' AND high_score IS NOT NULL
              AND completed_at >= %s AND completed_at < %s
            ORDER BY high_score DESC, id ASC
        ''', (day, day + timedelta(days=1)))
