"""Golden history query matching and sanitization."""
import json
import sqlite3
import unittest

from snake_web.activity.AppDb import AppDb
from snake_web.activity.GoldenConfigurations import parameter_change
from snake_web.activity.GoldenHistory import reasoning_content, append_golden_history, read_golden_history

class GoldenHistoryTests(unittest.TestCase):
    def test_baselines_retries_and_unrelated_conversations(self):
        connection = sqlite3.connect(':memory:')
        self.addCleanup(connection.close)
        connection.row_factory = sqlite3.Row
        connection.create_function('JSON_UNQUOTE', 1, lambda value: value)
        connection.executescript('''
            CREATE TABLE events (event_id INTEGER PRIMARY KEY, occurred_at TEXT,
                                 category TEXT, name TEXT, process_id TEXT, parameter TEXT);
            CREATE TABLE event_messages (event_id INTEGER, content TEXT);
            CREATE TABLE experiment_highscores (event_id INTEGER PRIMARY KEY, score INTEGER);
        ''')

        def event(id, category, name, process, content=None, parameter=None):
            connection.execute('INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)',
                               (id, '2026-09-15 12:00:00', category, name, process, parameter))
            if content is not None:
                connection.execute('INSERT INTO event_messages VALUES (?, ?)', (id, content))

        event(1, 'Configuration', 'golden_config_created', 'baseline')
        event(2, 'Conversation', 'prompt_sent', 'conversation', parameter='learning_rate')
        event(3, 'Conversation', 'reply_received', 'conversation', 'rejected response')
        event(4, 'Tool', 'tool_execution_completed', 'conversation', '{"status":"rejected"}')
        event(5, 'Conversation', 'prompt_sent', 'conversation', parameter='learning_rate')
        response = json.dumps({'choices': [{'message': {'reasoning_content': 'winning reason'}}]})
        event(6, 'Conversation', 'reply_received', 'conversation', response)
        event(7, 'Conversation', 'reply_received', 'unrelated', 'wrong response')
        event(8, 'Tool', 'tool_execution_completed', 'conversation', '{"status":"ok","run_id":"winner"}')
        event(9, 'Configuration', 'golden_config_created', 'winner', 'High score: 55 > 0; network.size: 4 -> 6.')
        event(10, 'Configuration', 'golden_config_retained', 'winner')
        event(11, 'Configuration', 'golden_config_created', 'seed-baseline')
        event(12, 'Tool', 'tool_execution_completed', 'unrelated', 'invalid JSON')
        event(13, 'Other', 'golden_config_created', 'wrong-category')
        connection.executemany('INSERT INTO experiment_highscores VALUES (?, ?)', [(1, 0), (9, 55)])

        class Db:
            def query(self, sql, params):
                return [dict(row) for row in connection.execute(sql.replace('ax3l.', '').replace('%s', '?'), params)]

        rows = AppDb(Db()).get_golden_configurations(0)
        self.assertEqual([r['event_id'] for r in AppDb(Db()).get_golden_configurations(9)], [11])
        self.assertEqual([r['process_id'] for r in rows], ['baseline', 'winner', 'seed-baseline'])
        self.assertEqual([r['high_score'] for r in rows], [0, 55, None])
        self.assertEqual(parameter_change(rows[1]['decision']), '4 > 6')
        self.assertEqual(parameter_change(rows[2]['decision']), '')
        self.assertEqual(rows[1]['reply_id'], 6)
        self.assertEqual(rows[1]['parameter'], 'learning_rate')
        self.assertEqual(reasoning_content(rows[1]['response']), 'winning reason')
        for row in (rows[0], rows[2]):
            self.assertIsNone(row['reply_id'])
            self.assertIsNone(row['parameter'])

    def test_missing_reasoning(self):
        for content in (None, '', 'invalid', 'null', '{}', '{"choices":[]}',
                        '{"choices":[{"message":{"content":"not reasoning"}}]}'):
            self.assertEqual(reasoning_content(content), '')

    def test_recorded_value_changes(self):
        for decision, expected in (
            (None, ''),
            ('Initial defaults', ''),
            ('Fresh baseline after seed rotation. Score to beat: 55.', ''),
            ('High score: 55 > 0; network.size: 4 -> 6.', '4 > 6'),
            ('High score: 55 > 0; learning_rate: 1e-05 -> 0.001.', '1e-05 > 0.001'),
            ('High score: 55 > 0; rewards.food: 0 -> 6; rewards.death: -4 -> -2.',
             'rewards.food: 0 > 6; rewards.death: -4 > -2'),
        ):
            with self.subTest(decision=decision):
                self.assertEqual(parameter_change(decision), expected)



class GoldenExportTests(unittest.TestCase):
    def test_only_public_fields_survive_and_multiline_roundtrips(self):
        reason = 'Choose "this", then\n<script>text</script> {{ liquid }}'
        record = dict(event_id=3, occurred_at='2026-09-16 12:00:00', process_id='run-1',
                      high_score=0, parameter='learning_rate', decision='training.learning_rate: 0.1 -> 0.2.',
                      response=json.dumps({'secret': 'private response', 'choices': [
                          {'message': {'reasoning_content': reason, 'content': 'private content',
                                       'tool_calls': ['private tool']}}]}))
        csv = append_golden_history('', [record])
        self.assertNotIn('private', csv)
        row = read_golden_history(csv)[0]
        self.assertEqual(row['reasoning'], reason)
        self.assertEqual(row['change'], '0.1 > 0.2')
        self.assertEqual(row['parameter'], 'Learning Rate')
        self.assertEqual(row['high_score'], '0')
        self.assertEqual(append_golden_history(csv, []), csv)
        with self.assertRaises(ValueError):
            append_golden_history(csv, [record])

    def test_pair_order_and_missing_reasoning(self):
        self.assertEqual(parameter_change('epsilon.decay: 0.9 -> 0.8; epsilon.initial: 1 -> 0.5.',
                                          'epsilon_pair'), '1 > 0.5, 0.9 > 0.8')
        for response in ('[]', 'null', '{}', '{"choices":[{"message":{"reasoning_content":7}}]}'):
            self.assertEqual(reasoning_content(response), '')
