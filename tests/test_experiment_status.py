"""Homepage rendering and report queries, using isolated in-memory tables."""

from dataclasses import replace
from html.parser import HTMLParser
import json
import os

import pymysql
import sqlite3
import unittest
from xml.etree import ElementTree

from snake_web.activity.AppDb import AppDb, completed_cycles
from snake_web.activity.PublishStatus import render_status
from snake_web.activity.SimulationBoard import board_svg
from snake_web.entity.ExperimentStatus import ExperimentStatus


SNAPSHOT = {'board': {'grid_size': [4, 3], 'snake_head': [2, 1],
                      'snake_body': [[1, 1], [0, 1]], 'food': [3, 2]}}


class PageParser(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.tags = []
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)


class RenderingTests(unittest.TestCase):
    def setUp(self):
        self.status = ExperimentStatus(49, 39, 190, 26, SNAPSHOT,
                                       games_played=1234, moves_made=567890)

    def test_metrics_plain_reports_and_real_snapshot(self):
        page = render_status(self.status, 'wintermute')
        for text in ('Running on: wintermute', 'All-Time Highscore: 49',
                     'Current Highscore: 39', 'Simulations Run: 190',
                     'Completed Experiments: 26', 'Score Distribution',
                     'Games Played: 1,234', 'Moves Made: 567,890',
                     'Experiment Highscores', 'Golden Configurations', 'Event Log'):
            self.assertIn(text, page)
        self.assertIn('reports/experiment-highscores.html', page)
        self.assertIn('svg', PageParser(page).tags)
        self.assertTrue(page.startswith('---\n'))
        self.assertIn('layout: single', page)
        self.assertEqual(page, render_status(self.status, 'wintermute'))

    def test_missing_current_golden_is_not_all_time_score(self):
        page = render_status(replace(self.status, current_highscore=None, snapshot=None), 'host')
        self.assertIn('Current Highscore: —', page)
        self.assertIn('All-Time Highscore: 49', page)
        self.assertIn('No saved board is available', page)
        self.assertNotIn('svg', PageParser(page).tags)

    def test_hostnames_are_escaped_for_html_and_liquid(self):
        page = render_status(self.status, '<script>{{ variable }}{% include secret %}</script>')
        self.assertNotIn('script', PageParser(page).tags)
        self.assertNotIn('{{', page)
        self.assertNotIn('{%', page)
        self.assertIn('&lt;script&gt;', page)

    def test_invalid_metrics_fail_and_zero_is_valid(self):
        for field in ('all_time_highscore', 'current_highscore', 'simulations_submitted',
                      'experiment_cycles', 'games_played', 'moves_made'):
            for value in (-1, True, '51', 1.5):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    render_status(replace(self.status, **{field: value}), 'host')
        self.assertIn('Current Highscore: 0', render_status(replace(self.status, current_highscore=0), 'host'))
        page = render_status(replace(self.status, games_played=0, moves_made=0), 'host')
        self.assertIn('Games Played: 0', page)
        self.assertIn('Moves Made: 0', page)

    def test_svg_geometry_and_json_input(self):
        svg = board_svg(json.dumps(SNAPSHOT))
        self.assertEqual(svg, board_svg(SNAPSHOT))
        root = ElementTree.fromstring(svg)
        self.assertEqual(root.attrib['viewBox'], '0 0 128 96')
        self.assertEqual(root.attrib['role'], 'img')
        ns = {'s': 'http://www.w3.org/2000/svg'}
        food = root.find('s:circle', ns)
        self.assertEqual((food.attrib['cx'], food.attrib['cy']), ('112.0', '80.0'))
        self.assertEqual(len(root.findall('s:rect', ns)), 4)

    def test_unavailable_or_malformed_snapshots(self):
        for snapshot in (None, '', 'invalid json', {}, [],
                         {'board': {**SNAPSHOT['board'], 'grid_size': [1000000, 3]}},
                         {'board': {**SNAPSHOT['board'], 'snake_head': [4, 1]}},
                         {'board': {**SNAPSHOT['board'], 'snake_body': '<script>'}},
                         {'board': {**SNAPSHOT['board'], 'food': [True, 1]}}):
            with self.subTest(snapshot=snapshot):
                self.assertIsNone(board_svg(snapshot))


class ExperimentQueryTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            ATTACH DATABASE ':memory:' AS ax3l;
            CREATE TABLE simulation_runs (run_id TEXT, high_score INTEGER, high_score_snapshot TEXT);
            CREATE TABLE simulation_episodes (run_id TEXT, steps INTEGER);
            CREATE TABLE ax3l.events (event_id INTEGER PRIMARY KEY, occurred_at TEXT,
                category TEXT, name TEXT, process_id TEXT);
            CREATE TABLE ax3l.event_messages (event_id INTEGER PRIMARY KEY, content TEXT);
        ''')
        self.app = AppDb(self)

    def query(self, sql, params=None):
        return [dict(row) for row in self.db.execute(sql.replace('%s', '?'), params or ())]

    def event(self, name, process_id=None, content='{}', category='Configuration'):
        cursor = self.db.execute('INSERT INTO ax3l.events (occurred_at, category, name, process_id) '
                                 "VALUES ('2026-09-16', ?, ?, ?)", (category, name, process_id))
        self.db.execute('INSERT INTO ax3l.event_messages VALUES (?, ?)', (cursor.lastrowid, content))

    def test_golden_score_and_snapshot_are_distinct_from_all_time_and_latest_run(self):
        snapshot = json.dumps(SNAPSHOT)
        self.db.executemany('INSERT INTO simulation_runs VALUES (?, ?, ?)',
                           [('record', 49, None), ('golden', 39, snapshot), ('latest', 12, None),
                            ('pending', None, None)])
        self.event('golden_config_created', 'record')
        self.event('golden_config_created', 'golden')
        self.assertEqual(self.app.get_experiment_status(), ExperimentStatus(49, 39, 4, 0, snapshot))

    def test_empty_tables_and_missing_golden(self):
        self.assertEqual(self.app.get_experiment_status(), ExperimentStatus(None, None, 0, 0))
        self.db.execute("INSERT INTO simulation_runs VALUES ('run', 0, NULL)")
        self.event('golden_config_created', 'missing-run')
        self.assertEqual(self.app.get_experiment_status(), ExperimentStatus(0, None, 1, 0))

    def test_episode_totals_include_every_run_and_zero_step_games(self):
        self.db.executemany('INSERT INTO simulation_episodes VALUES (?, ?)',
                           [('old', 1200), ('old', 0), ('current', 3456)])
        status = self.app.get_experiment_status()
        self.assertEqual(status.games_played, 3)
        self.assertEqual(status.moves_made, 4656)

    def test_cycles_count_completed_ordered_comparisons_only(self):
        # A gap, one full round, a duplicate, and an unfinished next round.
        for index, process_id in [(1, 'gap'), (0, 'a'), (1, 'b'), (2, 'c'), (0, 'd')]:
            self.event('round_robin_checkpoint', content=json.dumps({
                'parameter_order': ['one', 'two', 'three'], 'index': index}))
            self.event('proposal_accepted', process_id)
            if process_id != 'd':
                self.event('configuration_compared', process_id)
                self.event('configuration_compared', process_id)
        self.assertEqual(self.app.get_experiment_status().experiment_cycles, 1)

    def test_cycles_do_not_reset_at_new_golden(self):
        for index in range(3):
            self.event('round_robin_checkpoint', content=json.dumps({
                'parameter_order': ['one', 'two', 'three'], 'index': index}))
            self.event('proposal_accepted', str(index))
            self.event('configuration_compared', str(index))
            self.event('golden_config_created', str(index))
        self.assertEqual(self.app.get_experiment_status().experiment_cycles, 1)

    def test_malformed_checkpoint_or_changed_order_is_rejected(self):
        for checkpoint in ({'parameter_order': [], 'index': 0},
                           {'parameter_order': ['one'], 'index': True},
                           {'parameter_order': ['one'], 'index': 2}):
            with self.assertRaises(ValueError):
                completed_cycles([{'process_id': 'a', 'content': json.dumps(checkpoint)}])
        with self.assertRaisesRegex(ValueError, 'order changed'):
            completed_cycles([
                {'process_id': 'a', 'content': json.dumps({'parameter_order': ['one'], 'index': 0})},
                {'process_id': 'b', 'content': json.dumps({'parameter_order': ['two'], 'index': 0})},
            ])


@unittest.skipUnless(os.environ.get('SNAKE_WEB_TEST_DB_SOCKET'), 'requires isolated DEV MariaDB')
class CollationTests(unittest.TestCase):
    def test_golden_lookup_across_different_schema_collations(self):
        socket = os.environ['SNAKE_WEB_TEST_DB_SOCKET']
        self.assertTrue(socket.startswith('/tmp/snake-web-'), 'Use an isolated test database')
        connection = pymysql.connect(unix_socket=socket, user='root', database='snakelab',
                                     cursorclass=pymysql.cursors.DictCursor, autocommit=True)
        self.addCleanup(connection.close)
        # Temporary tables shadow the fixture tables only on this connection.
        with connection.cursor() as cursor:
            cursor.execute('CREATE TEMPORARY TABLE simulation_episodes (steps INT)')
            cursor.execute("""CREATE TEMPORARY TABLE simulation_runs (
                run_id CHAR(36), high_score INT, high_score_snapshot JSON
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci""")
            cursor.execute("""CREATE TEMPORARY TABLE ax3l.events (
                event_id INT PRIMARY KEY, occurred_at DATETIME, category VARCHAR(50),
                name VARCHAR(100), process_id CHAR(36)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_uca1400_ai_ci""")
            cursor.execute("""CREATE TEMPORARY TABLE ax3l.event_messages (
                event_id INT PRIMARY KEY, content TEXT
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_uca1400_ai_ci""")
            cursor.execute("INSERT INTO simulation_runs VALUES ('record', 49, NULL), ('golden', 39, %s)",
                           (json.dumps(SNAPSHOT),))
            cursor.execute("""INSERT INTO ax3l.events VALUES
                (1, '2026-09-16', 'Configuration', 'golden_config_created', 'golden')""")
            cursor.execute("INSERT INTO ax3l.event_messages VALUES (1, '{}')")
            # Reproduce the deployment failure to ensure this fixture covers it.
            with self.assertRaises(pymysql.err.OperationalError) as error:
                cursor.execute("""SELECT r.high_score FROM simulation_runs r
                    WHERE r.run_id = (SELECT process_id FROM ax3l.events LIMIT 1)""")
            self.assertEqual(error.exception.args[0], 1267)

        class Database:
            def query(self, sql, params=None):
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    return list(cursor.fetchall())

        result = AppDb(Database()).get_experiment_status()
        self.assertEqual(result.all_time_highscore, 49)
        self.assertEqual(result.current_highscore, 39)
        self.assertEqual(json.loads(result.snapshot), SNAPSHOT)
