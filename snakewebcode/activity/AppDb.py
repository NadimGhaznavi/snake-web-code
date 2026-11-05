"""Read Snake Lab games and Ax3l's reporting status without changing source data."""

from datetime import timedelta

from snakewebcode.interface.DbMgr import DbMgr


class AppDb:
    def __init__(self, db: DbMgr):
        self._db = db

    def get_status(self) -> dict:
        """Use the display server's summaries and latest golden configuration."""
        rows = self._db.query('''
            SELECT s.all_time_high_score, r.high_score AS current_high_score,
                   s.experiment_cycles AS completed_experiments,
                   s.simulations_submitted, s.games_played, s.moves_made
            FROM ax3l.report_state s
            LEFT JOIN simulation_runs r ON r.run_id = (
                SELECT e.process_id COLLATE utf8mb4_unicode_ci
                FROM ax3l.events e JOIN ax3l.event_messages m USING (event_id)
                WHERE e.category = %s AND e.name = %s
                ORDER BY e.occurred_at DESC, e.event_id DESC LIMIT 1
            )
            WHERE s.singleton = 1 AND s.refreshed_at IS NOT NULL
        ''', ('Configuration', 'golden_config_created'))
        if not rows:
            raise RuntimeError('Ax3l reporting summaries are not ready; refresh them with Ax3l first')
        row = rows[0]
        status = {}
        for field in ('all_time_high_score', 'current_high_score', 'completed_experiments',
                      'simulations_submitted', 'games_played', 'moves_made'):
            value = row[field]
            if value is None and field in ('all_time_high_score', 'current_high_score'):
                status[field] = None
            elif type(value) is int and value >= 0:
                status[field] = value
            else:
                raise ValueError(f'Invalid Ax3l status field: {field}')
        return status

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
