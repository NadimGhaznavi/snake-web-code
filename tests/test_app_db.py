"""Check the remaining data queries independently of removed reports."""

from datetime import date, datetime
import sqlite3
import unittest
from unittest.mock import Mock

from snakewebcode.activity.AppDb import AppDb


class AppDbTests(unittest.TestCase):
    def test_daily_selection_uses_source_date(self):
        db = Mock()
        db.query.return_value = [{'day': date(2026, 10, 30)}]
        self.assertEqual(AppDb(db).get_daily_game_day(), date(2026, 10, 30))
        db.query.assert_called_once_with('SELECT CURRENT_DATE AS day')

    def test_histogram_projection_keeps_null_zero_and_submission_order(self):
        connection = sqlite3.connect(':memory:')
        self.addCleanup(connection.close)
        connection.row_factory = sqlite3.Row
        connection.execute('CREATE TABLE simulation_runs (id INTEGER, high_score INTEGER)')
        connection.executemany('INSERT INTO simulation_runs VALUES (?, ?)', [(3, 8), (1, None), (2, 0)])
        db = Mock()
        db.query.side_effect = lambda sql: [dict(row) for row in connection.execute(sql)]
        self.assertEqual(AppDb(db).get_run_scores(), [
            dict(id=1, high_score=None), dict(id=2, high_score=0), dict(id=3, high_score=8)])

    def test_daily_observation_uses_source_clock(self):
        db = Mock()
        now = datetime(2026, 10, 30, 12, 30)
        db.query.return_value = [{'observed_at': now}]
        self.assertEqual(AppDb(db).get_daily_progress_time(), now)
        db.query.assert_called_once_with('SELECT CURRENT_TIMESTAMP AS observed_at')

    def test_daily_chart_boundaries_observation_time_ties_zero_null_and_limit(self):
        connection = sqlite3.connect(':memory:')
        self.addCleanup(connection.close)
        connection.row_factory = sqlite3.Row
        connection.execute('CREATE TABLE simulation_runs '
                           '(id INT, high_score INT, status TEXT, completed_at TEXT)')
        rows = [(1, 90, 'completed', '2026-10-29 23:59:59'),
                (2, 0, 'completed', '2026-10-30 00:00:00'),
                (3, 9, 'completed', '2026-10-30 12:30:00'),
                (4, 9, 'completed', '2026-10-30 10:00:00'),
                (5, 99, 'completed', '2026-10-30 12:30:01'),
                (6, 99, 'completed', '2026-10-31 00:00:00'),
                (7, None, 'completed', '2026-10-30 11:00:00'),
                (8, 99, 'running', '2026-10-30 11:00:00')]
        connection.executemany('INSERT INTO simulation_runs VALUES (?, ?, ?, ?)', rows)
        db = Mock()
        db.query.side_effect = lambda sql, params: [dict(row) for row in connection.execute(
            sql.replace('%s', '?'), tuple(str(p) for p in params))]
        app = AppDb(db)
        self.assertEqual(app.get_daily_configurations(date(2026, 10, 30), datetime(2026, 10, 30, 12, 30)),
                         [dict(id=3, high_score=9), dict(id=4, high_score=9), dict(id=2, high_score=0)])
        self.assertEqual([row['id'] for row in app.get_daily_configurations(
            date(2026, 10, 30), datetime(2026, 10, 31))], [5, 3, 4, 2])
        connection.executemany('INSERT INTO simulation_runs VALUES (?, ?, ?, ?)',
                               [(i, 10, 'completed', '2026-10-30 09:00:00') for i in range(10, 22)])
        self.assertEqual([row['id'] for row in app.get_daily_configurations(
            date(2026, 10, 30), datetime(2026, 10, 30, 12, 30))], list(range(10, 20)))
