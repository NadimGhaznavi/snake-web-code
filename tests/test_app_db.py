"""Check the remaining data queries independently of removed reports."""

from datetime import date
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
