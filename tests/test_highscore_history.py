"""Public history contract and incremental database boundary."""
import unittest
from unittest.mock import Mock

from snake_web.activity.AppDb import AppDb
from snake_web.activity.HighscoreHistory import append_history, read_history


class HistoryTests(unittest.TestCase):
    def test_empty_and_nullable_seed(self):
        content = append_history('', [])
        self.assertEqual(read_history(content), [])
        content = append_history(content, [dict(event_id=5, simulations=2, score=0, seed=None,
                                                private_payload='never publish')])
        self.assertEqual(read_history(content), [dict(event_id=5, simulations=2, score=0, seed=None)])
        self.assertNotIn('private', content)
        self.assertEqual(append_history(content, []), content)

    def test_duplicate_and_corrupt_history_rejected(self):
        row = dict(event_id=5, simulations=2, score=4, seed=1)
        content = append_history('', [row])
        with self.assertRaises(ValueError):
            append_history(content, [row])
        for corrupt in ('wrong,header\n', 'event_id,simulations,score,seed\n5,-1,4,1\n'):
            with self.assertRaises(ValueError):
                read_history(corrupt)

    def test_query_uses_saved_event_id_and_no_message_payload(self):
        db = Mock()
        db.query.return_value = [dict(event_id=8, simulations=4, score=2, seed=9)]
        self.assertEqual(AppDb(db).get_highscore_history(7), db.query.return_value)
        sql, parameters = db.query.call_args.args
        self.assertIn('WHERE event_id > %s ORDER BY event_id', sql)
        self.assertNotIn('event_messages', sql)
        self.assertEqual(parameters, (7,))
