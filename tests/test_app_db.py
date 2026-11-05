"""Check game queries and the display server's reporting-status contract."""

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


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')
        self.addCleanup(self.connection.close)
        self.connection.row_factory = sqlite3.Row
        self.connection.create_collation('utf8mb4_unicode_ci', lambda a, b:
                                         (a.casefold() > b.casefold()) - (a.casefold() < b.casefold()))
        self.connection.execute("ATTACH DATABASE ':memory:' AS ax3l")
        self.connection.execute('''CREATE TABLE ax3l.report_state (
            singleton INT, all_time_high_score INT, experiment_cycles INT,
            simulations_submitted INT, games_played INT, moves_made INT, refreshed_at TEXT)''')
        self.connection.execute('''INSERT INTO ax3l.report_state VALUES
            (1, 58, 503, 3588, 5368500, 835101262, '2026-11-05 12:00:00')''')
        self.connection.execute('CREATE TABLE simulation_runs '
                                '(id INT, run_id TEXT COLLATE utf8mb4_unicode_ci, high_score INT)')
        self.connection.executemany('INSERT INTO simulation_runs VALUES (?, ?, ?)',
                                    [(1, 'first', 58), (2, 'second', 49), (3, 'zero', 0),
                                     (4, 'unscored', None), (5, 'other', 99)])
        self.connection.execute('CREATE TABLE ax3l.events '
                                '(event_id INT, occurred_at TEXT, category TEXT, name TEXT, process_id TEXT)')
        self.connection.execute('CREATE TABLE ax3l.event_messages (event_id INT, content TEXT)')
        db = Mock()
        db.query.side_effect = lambda sql, params: [dict(row) for row in self.connection.execute(
            sql.replace('%s', '?'), params)]
        self.app = AppDb(db)
        self.expected = dict(all_time_high_score=58, current_high_score=None,
                             completed_experiments=503, simulations_submitted=3588,
                             games_played=5368500, moves_made=835101262)

    def golden(self, event_id, when, run_id, *, category='Configuration',
               name='golden_config_created', message=True):
        self.connection.execute('INSERT INTO ax3l.events VALUES (?, ?, ?, ?, ?)',
                                (event_id, when, category, name, run_id))
        if message:
            self.connection.execute('INSERT INTO ax3l.event_messages VALUES (?, ?)',
                                    (event_id, 'private decision text'))

    def test_summary_counters_and_latest_golden_match_display_server(self):
        self.golden(100, '2026-11-04 12:00:00', 'first')
        self.golden(1, '2026-11-05 12:00:00', 'first')
        self.golden(2, '2026-11-05 12:00:00', 'SECOND')
        self.golden(3, '2026-11-05 13:00:00', 'other', category='Other')
        self.golden(4, '2026-11-05 13:00:00', 'other', name='proposal_accepted')
        self.golden(5, '2026-11-05 13:00:00', 'other', message=False)
        self.assertEqual(self.app.get_status(), {**self.expected, 'current_high_score': 49})

    def test_missing_golden_and_empty_scores_are_null_and_zero_is_preserved(self):
        self.assertEqual(self.app.get_status(), self.expected)
        for event_id, run_id, score in [(1, 'first', 58), (2, 'zero', 0),
                                         (3, 'unscored', None), (4, 'missing', None)]:
            with self.subTest(run_id=run_id):
                self.golden(event_id, '2026-11-05 12:00:00', run_id)
                self.assertEqual(self.app.get_status(), {**self.expected, 'current_high_score': score})
        for score in (None, 0):
            self.connection.execute('UPDATE ax3l.report_state SET all_time_high_score = ?, '
                                    'experiment_cycles = 0, simulations_submitted = 0, '
                                    'games_played = 0, moves_made = 0', (score,))
            self.assertEqual(self.app.get_status(), dict(all_time_high_score=score,
                current_high_score=None, completed_experiments=0, simulations_submitted=0,
                games_played=0, moves_made=0))

    def test_uninitialized_reporting_summary_is_not_published_as_zero(self):
        self.connection.execute('UPDATE ax3l.report_state SET refreshed_at = NULL')
        with self.assertRaisesRegex(RuntimeError, 'refresh them with Ax3l first'):
            self.app.get_status()
        self.connection.execute('DELETE FROM ax3l.report_state')
        with self.assertRaisesRegex(RuntimeError, 'not ready'):
            self.app.get_status()

    def test_invalid_source_counters_are_rejected_and_private_fields_are_excluded(self):
        db = Mock()
        db.query.return_value = [{**self.expected, 'private': 'not public'}]
        app = AppDb(db)
        self.assertEqual(app.get_status(), self.expected)
        for field, value in [('games_played', -1), ('moves_made', 1.5),
                             ('completed_experiments', None), ('all_time_high_score', True),
                             ('current_high_score', '49')]:
            with self.subTest(field=field, value=value):
                db.query.return_value = [{**self.expected, field: value}]
                with self.assertRaisesRegex(ValueError, field):
                    app.get_status()
