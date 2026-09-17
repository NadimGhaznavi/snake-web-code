import sqlite3
import json
import unittest

from snake_web.activity.AppDb import AppDb
from snake_web.activity.TopRuns import render_top_runs
from test_experiment_status import SNAPSHOT


class TopRunsTests(unittest.TestCase):
    def test_ranking_limit_ties_null_and_zero(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.row_factory = sqlite3.Row
        db.execute('CREATE TABLE simulation_runs (id INTEGER, run_id TEXT, high_score INTEGER, high_score_snapshot TEXT)')
        db.executescript("""
            ATTACH DATABASE ':memory:' AS ax3l;
            CREATE TABLE ax3l.events (event_id INTEGER, category TEXT, name TEXT, process_id TEXT);
            CREATE TABLE ax3l.event_messages (event_id INTEGER, content TEXT);
        """)
        db.create_function('JSON_UNQUOTE', 1, lambda value: value)
        db.executemany('INSERT INTO simulation_runs (id, high_score) VALUES (?, ?)',
                       [(1, None), (2, 0), (3, 12), (4, 12), (5, 20)])

        class Database:
            def query(self, sql, params=()):
                return [dict(row) for row in db.execute(sql.replace('%s', '?'), params)]

        app = AppDb(Database())
        self.assertEqual([row['id'] for row in app.get_top_runs()], [5, 3, 4, 2])
        db.executemany('INSERT INTO simulation_runs (id, high_score) VALUES (?, ?)',
                       [(i, i) for i in range(6, 120)])
        rows = app.get_top_runs()
        self.assertEqual(len(rows), 100)
        self.assertEqual(rows[0]['id'], 119)

    def test_boards_navigation_wrap_and_missing_snapshot(self):
        page = render_top_runs([
            dict(id=42, high_score=90, high_score_snapshot=SNAPSHOT),
            dict(id=7, high_score=80, high_score_snapshot=None),
            dict(id=81, high_score=0, high_score_snapshot='invalid'),
        ])
        first = page.split('id="rank-1"', 1)[1].split('</section>', 1)[0]
        self.assertLess(first.index('<svg'), first.index('<nav'))
        self.assertIn('data-rank="3"', first)
        self.assertIn('data-rank="2"', first)
        self.assertIn('Run #42 - Score: 90', first)
        last = page.split('id="rank-3"', 1)[1].split('</section>', 1)[0]
        self.assertIn('data-rank="1"', last)
        self.assertEqual(page.count('No saved board is available'), 2)

    def test_empty_single_and_invalid_values(self):
        self.assertIn('No scored simulations', render_top_runs([]))
        page = render_top_runs([dict(id=5, high_score=0)])
        self.assertEqual(page.count('data-rank="1"'), 2)
        with self.assertRaises(ValueError):
            render_top_runs([dict(id='<script>', high_score=10)])

    def test_thinking_uses_only_reasoning_and_keeps_matching_navigation(self):
        response = json.dumps({'choices': [{'message': {
            'reasoning_content': 'The User asked me to...\n<script>literal</script> {{ liquid }}',
            'content': 'private content', 'tool_calls': ['private tool'],
        }}, {'message': {'reasoning_content': 'private second choice'}}], 'secret': 'private envelope'})
        rows = [dict(id=42, high_score=90, response=response), dict(id=7, high_score=80)]
        page = render_top_runs(rows, thinking=True)
        self.assertIn("<title>Ax3l's Thinking</title>", page)
        self.assertIn('The User asked me to...\n&lt;script&gt;literal&lt;/script&gt;', page)
        self.assertNotIn('private', page)
        self.assertNotIn('{{', page)
        self.assertIn('No saved reasoning is available', page)
        for fragment in ('Run #42 - Score: 90', 'Run #7 - Score: 80', 'data-rank="2"', 'data-rank="1"'):
            self.assertIn(fragment, page)
            self.assertIn(fragment, render_top_runs(rows))
