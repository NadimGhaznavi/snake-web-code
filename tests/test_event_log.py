"""Public event boundary, bounded queries, and mutable simulation details."""
import json
from decimal import Decimal
import sqlite3
import unittest
from unittest.mock import Mock

from snake_web.activity.AppDb import AppDb
from snake_web.activity.EventLogExport import (
    EVENT_FIELDS, SIMULATION_FIELDS, read_csv, export_event_log, sanitize_event, prompt_parts,
)
from snake_web.constants.PublicEvents import CONFIGURATION_FIELDS
from snake_web.interface.GitPublisher import GitPublisher


class EventLogTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            ATTACH DATABASE ':memory:' AS ax3l;
            CREATE TABLE ax3l.events (event_id INTEGER PRIMARY KEY, occurred_at TEXT,
                category TEXT, name TEXT, log_level TEXT, process_id TEXT, source_name TEXT,
                parameter TEXT, parent_event_id INTEGER, ax3l_version TEXT);
            CREATE TABLE ax3l.event_messages (event_id INTEGER, content TEXT);
            CREATE TABLE simulation_runs (id INTEGER, run_id TEXT, project_version TEXT,
                high_score INTEGER, completed_at TEXT, high_score_snapshot TEXT);
        ''')
        columns = ', '.join(column + ' REAL' for column, _, _ in CONFIGURATION_FIELDS)
        self.db.execute('CREATE TABLE configurations (run_id TEXT, ' + columns + ')')
        self.db.execute("INSERT INTO simulation_runs VALUES (1, 'run-1', '1.0', NULL, NULL, NULL)")
        values = ', '.join('?' for _ in CONFIGURATION_FIELDS)
        self.db.execute('INSERT INTO configurations VALUES (?, ' + values + ')',
                        ('run-1', *(1 for _ in CONFIGURATION_FIELDS)))
        self.queries = []
        def query(sql, params=()):
            self.queries.append((sql, params))
            return [dict(row) for row in self.db.execute(sql.replace('%s', '?'), params)]
        self.appdb = AppDb(Mock(query=query))
        self.files = {}
        self.publisher = Mock(spec=GitPublisher)
        for key in ('EVENT_HISTORY_PATH', 'EVENT_SIMULATIONS_PATH', 'EVENT_CURSOR_PATH'):
            setattr(self.publisher, key, getattr(GitPublisher, key))
        self.publisher.read_history.side_effect = lambda name: self.files.get(name, '')

    def event(self, id, category, name, content='', process='run-1'):
        self.db.execute('INSERT INTO ax3l.events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        (id, '2026-09-16 12:00:00', category, name, 'INFO', process,
                         'source', 'learning_rate', None, '1.0'))
        self.db.execute('INSERT INTO ax3l.event_messages VALUES (?, ?)', (id, content))

    def export(self):
        output = export_event_log(self.appdb, self.publisher)
        self.files.update(output)
        return output

    def test_five_types_sanitized_and_cursor_skips_excluded_events(self):
        self.event(1, 'SnakeLab', 'simulation_completed', 'Done')
        self.event(2, 'Configuration', 'golden_config_retained', 'Keep golden')
        self.event(3, 'Conversation', 'prompt_sent', json.dumps({'role': 'user', 'content': '{"seed": 1}'}))
        self.event(4, 'Conversation', 'reply_received', json.dumps({
            'id': 'PRIVATE_ENVELOPE', 'choices': [{'message': {
                'reasoning_content': 'Reason "one",\n<script>literal text</script>',
                'content': 'PRIVATE_MESSAGE', 'tool_calls': ['PRIVATE_TOOL']}}],
            'usage': {'prompt_tokens': 12, 'prompt_tokens_details': {'cached_tokens': 3},
                      'private': 'PRIVATE_USAGE'}, 'timings': {'predicted_ms': 2.5}}))
        self.event(5, 'SnakeLab', 'simulation_submitted', 'Submitted')
        self.event(6, 'Tool', 'tool_execution_completed', 'PRIVATE_EXCLUDED')
        self.event(7, 'Other', 'simulation_completed', 'PRIVATE_WRONG_CATEGORY')
        self.export()
        csv = self.files[GitPublisher.EVENT_HISTORY_PATH]
        self.assertNotIn('PRIVATE_', csv)
        rows = read_csv(csv, EVENT_FIELDS)
        self.assertEqual([r['event_id'] for r in rows], ['1', '2', '3', '4', '5'])
        detail = json.loads(rows[3]['detail'])
        self.assertEqual(set(detail), {'reasoning', 'usage', 'timings'})
        self.assertEqual(detail['usage']['prompt_tokens_details.cached_tokens'], 3)
        self.assertIn('\n<script>', detail['reasoning'])
        self.assertEqual(json.loads(self.files[GitPublisher.EVENT_CURSOR_PATH])['through_event_id'], 7)
        first = self.files.copy()
        self.queries.clear()
        self.export()
        self.assertEqual(self.files, first)
        self.assertFalse(any('LIMIT 250' in sql for sql, _ in self.queries))
        self.event(8, 'Conversation', 'reply_received', '{}')
        self.export()
        self.assertTrue(self.files[GitPublisher.EVENT_HISTORY_PATH].startswith(csv))
        self.assertEqual([r['event_id'] for r in read_csv(self.files[GitPublisher.EVENT_HISTORY_PATH], EVENT_FIELDS)],
                         ['1', '2', '3', '4', '5', '8'])

    def test_exports_all_history_across_batches(self):
        for id in range(1, 602):
            self.event(id, 'Configuration', 'golden_config_retained', 'Keep')
        self.export()
        self.assertEqual(len(read_csv(self.files[GitPublisher.EVENT_HISTORY_PATH], EVENT_FIELDS)), 601)
        self.assertEqual(sum('LIMIT 250' in sql for sql, _ in self.queries), 3)

    def test_run_details_refresh_without_new_events(self):
        self.event(1, 'SnakeLab', 'simulation_submitted')
        self.export()
        old = self.files[GitPublisher.EVENT_SIMULATIONS_PATH]
        self.db.execute("UPDATE simulation_runs SET high_score=9, completed_at='2026-09-16 13:00:00'")
        self.export()
        new = self.files[GitPublisher.EVENT_SIMULATIONS_PATH]
        self.assertTrue(new.startswith(old))
        rows = read_csv(new, SIMULATION_FIELDS)
        self.assertEqual(len(rows), 2)
        detail = json.loads(rows[-1]['detail'])
        self.assertEqual(detail['high_score'], 9)
        self.assertEqual(detail['configuration']['training']['learning_rate'], 1)
        self.assertEqual(set(detail), {'run_id', 'project_version', 'high_score', 'completed_at', 'board', 'configuration'})

    def test_malformed_prompt_and_reset_fail_without_advancing(self):
        self.event(1, 'Conversation', 'prompt_sent', 'bad JSON')
        with self.assertRaisesRegex(ValueError, 'Invalid stored prompt'):
            self.export()
        self.assertEqual(self.files, {})
        self.db.execute("UPDATE ax3l.event_messages SET content='{}'")
        self.db.execute("UPDATE ax3l.events SET name='reply_received'")
        self.export()
        previous = self.files.copy()
        self.db.execute('DELETE FROM ax3l.events')
        with self.assertRaisesRegex(ValueError, 'reset'):
            self.export()
        self.assertEqual(self.files, previous)

    def test_decimal_database_cursor_exports_as_integer_and_resumes(self):
        original_query = self.appdb._db.query
        def decimal_aggregate(sql, params=()):
            rows = original_query(sql, params)
            if 'COALESCE(MAX(event_id)' in sql:
                rows[0]['event_id'] = Decimal(rows[0]['event_id'])
            return rows
        self.appdb = AppDb(Mock(query=decimal_aggregate))
        self.assertIs(type(self.appdb.get_event_export_end()), int)
        self.export()
        self.assertEqual(json.loads(self.files[GitPublisher.EVENT_CURSOR_PATH]),
                         {'version': 1, 'through_event_id': 0})
        # Preserve large unsigned IDs without converting through float.
        event_id = 9007199254740993
        self.event(event_id, 'Configuration', 'golden_config_retained', 'Keep')
        self.export()
        cursor = json.loads(self.files[GitPublisher.EVENT_CURSOR_PATH])
        self.assertIs(type(cursor['through_event_id']), int)
        self.assertEqual(cursor['through_event_id'], event_id)
        previous = self.files.copy()
        self.export()
        self.assertEqual(self.files, previous)

    def test_prompt_images_allow_only_embedded_png(self):
        image = {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,YQ=='}}
        self.assertEqual(prompt_parts(json.dumps({'content': [image]}))[0]['type'], 'image')
        image['image_url']['url'] = 'https://private-host/image.png'
        with self.assertRaises(ValueError):
            prompt_parts(json.dumps({'content': [image]}))
        with self.assertRaises(ValueError):
            sanitize_event({'category': 'Tool', 'name': 'tool_execution_completed'})
