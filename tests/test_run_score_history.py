"""Mutable scores retain export history without double-counting runs."""
import unittest
from unittest.mock import Mock

from snake_web.activity.AppDb import AppDb
from snake_web.activity.RunScoreHistory import append_scores, read_scores


class RunScoreTests(unittest.TestCase):
    def test_appends_only_new_or_changed_observations(self):
        first = append_scores('', [dict(id=1, high_score=None), dict(id=2, high_score=0)])
        second = append_scores(first, [dict(id=1, high_score=5), dict(id=2, high_score=0),
                                       dict(id=3, high_score=None, secret='private')])
        self.assertEqual(second, first + '1,5\n3,\n')
        self.assertEqual(read_scores(second), {1: 5, 2: 0, 3: None})
        self.assertEqual(append_scores(second, [dict(id=1, high_score=5)]), second)
        self.assertNotIn('private', second)

    def test_empty_and_invalid_data(self):
        self.assertEqual(read_scores(append_scores('', [])), {})
        for text in ('bad\n', 'id,high_score\n1,-1\n', 'id,high_score\n0,5\n',
                     'id,high_score\n1,2,3\n'):
            with self.assertRaises(ValueError):
                read_scores(text)
        for row in (dict(id=True, high_score=3), dict(id=1, high_score=-1)):
            with self.assertRaises(ValueError):
                append_scores('', [row])

    def test_query_includes_earlier_mutable_runs_and_unscored_runs(self):
        db = Mock()
        AppDb(db).get_run_scores()
        db.query.assert_called_once_with('SELECT id, high_score FROM simulation_runs ORDER BY id')
