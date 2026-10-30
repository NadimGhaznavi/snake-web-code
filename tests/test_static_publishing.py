"""Check the Caddy publisher with captured games and disposable files only."""

from datetime import date
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from uuid import UUID

from PIL import Image
import zmq

from snakewebcode.activity.PublishLive import PublishLive
from snakewebcode.interface.StaticPublisher import StaticPublisher


def run(number, score=None):
    return dict(id=number, run_id=str(UUID(int=number)), high_score=number if score is None else score)


def frames(score):
    board = dict(grid_size=[4, 3], snake_head=[1, 0], snake_body=[[0, 0]],
                 food=[3, 2], direction=[1, 0], score=score)
    return [dict(version=1, episode=1, step=step,
                 board={**board, 'snake_head': [step + 1, 0]}) for step in range(2)]


class StaticPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='snakeweb-static-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.public = self.root / 'public'
        self.publisher = StaticPublisher(self.public)
        self.app = Mock()
        self.app.get_daily_game_day.return_value = date(2026, 10, 29)
        self.app.get_daily_runs.return_value = [run(i) for i in range(8, 0, -1)]
        self.app.get_run_scores.return_value = [dict(id=i, high_score=i) for i in range(1, 9)]
        self.snake = self.enterContext(patch('snakewebcode.activity.DailyGames.SnakeLab')).return_value
        self.snake.get_highscore_frames.side_effect = lambda uuid: frames(int(UUID(uuid)))

    def publish(self):
        return PublishLive(self.app, self.publisher).run()

    def metadata(self):
        return json.loads((self.public / 'live.json').read_text())

    def test_five_daily_slots_histogram_and_metadata_without_git(self):
        with patch('subprocess.run', side_effect=AssertionError('Publication must not invoke Git')):
            self.assertIn('published', self.publish())
        self.assertEqual({path.name for path in self.public.iterdir()},
                         set(self.publisher.GIF_PATHS) | {'live.json'})
        self.assertEqual([row['id'] for row in self.metadata()['games']], [8, 7, 6, 5, 4])
        self.assertEqual(self.snake.get_highscore_frames.call_count, 5)
        self.assertRegex(self.metadata()['updated'], r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$')
        for name in self.publisher.GIF_PATHS:
            path = self.public / name
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)
            with Image.open(path) as image:
                self.assertEqual(image.info['loop'], 0)
                self.assertGreater(image.n_frames, 1)

    def test_unchanged_and_restart_reuse_bytes_mtimes_and_timestamp(self):
        self.publish()
        saved = {path.name: (path.read_bytes(), path.stat().st_mtime_ns)
                 for path in self.public.iterdir()}
        self.publisher = StaticPublisher(self.public)
        self.snake.get_highscore_frames.reset_mock()
        self.assertIn('unchanged', self.publish())
        self.snake.get_highscore_frames.assert_not_called()
        self.assertEqual(saved, {path.name: (path.read_bytes(), path.stat().st_mtime_ns)
                                 for path in self.public.iterdir()})

    def test_new_leader_moves_cached_slots_and_unused_slots_are_removed(self):
        self.publish()
        leader = (self.public / 'game-one.gif').read_bytes()
        self.app.get_daily_runs.return_value.insert(0, run(9))
        self.snake.get_highscore_frames.reset_mock()
        self.publish()
        self.snake.get_highscore_frames.assert_called_once_with(run(9)['run_id'])
        self.assertEqual((self.public / 'game-two.gif').read_bytes(), leader)
        self.app.get_daily_runs.return_value = [run(9)]
        self.publish()
        self.assertEqual({p.name for p in self.public.glob('game-*.gif')}, {'game-one.gif'})

    def test_rollover_discards_yesterdays_games_even_during_outage(self):
        self.publish()
        self.app.get_daily_game_day.return_value = date(2026, 10, 30)
        self.app.get_daily_runs.return_value = [run(10)]
        self.snake.get_highscore_frames.side_effect = zmq.Again()
        with self.assertLogs(level='ERROR'):
            self.publish()
        self.assertEqual(self.metadata()['games'], [])
        self.assertEqual(self.metadata()['day'], '2026-10-30')
        self.assertEqual(list(self.public.glob('game-*.gif')), [])

    def test_outage_preserves_current_day_cached_leaders(self):
        self.publish()
        self.app.get_daily_runs.return_value.insert(0, run(9))
        self.snake.get_highscore_frames.side_effect = zmq.Again()
        with self.assertLogs(level='ERROR'):
            self.publish()
        self.assertEqual([row['id'] for row in self.metadata()['games']], [8, 7, 6, 5, 4])

    def test_skip_legacy_captures_and_include_zero_score(self):
        self.app.get_daily_runs.return_value = [run(2), run(1), run(3, 0)]
        self.snake.get_highscore_frames.side_effect = [None, frames(1), frames(0)]
        self.publish()
        self.assertEqual([row['id'] for row in self.metadata()['games']], [1, 3])

    def test_renderer_upgrade_regenerates_games(self):
        self.publish()
        self.snake.get_highscore_frames.reset_mock()
        with patch('snakewebcode.activity.DailyGames.SimulationAnimation.VERSION', 9):
            self.publish()
        self.assertEqual(self.snake.get_highscore_frames.call_count, 5)

    def test_changed_scores_and_missing_histogram_regenerate_distribution(self):
        self.publish()
        from snakewebcode.activity.ScoreDistribution import render_distribution
        with patch('snakewebcode.activity.PublishLive.render_distribution', wraps=render_distribution) as render:
            self.app.get_run_scores.return_value[0]['high_score'] = 0
            self.publish()
            render.assert_called_once()
            render.reset_mock()
            (self.public / 'score-distribution.gif').unlink()
            self.publish()
            render.assert_called_once()

    def test_interrupted_rank_change_does_not_reuse_new_image_for_old_game(self):
        self.publish()
        original_leader = (self.public / 'game-one.gif').read_bytes()
        self.app.get_daily_runs.return_value.insert(0, run(9))
        replace = self.publisher._replace

        def fail_second(path, data):
            if path.name == 'game-two.gif':
                raise OSError('disk full')
            replace(path, data)

        with patch.object(self.publisher, '_replace', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'disk full'):
                self.publish()
        self.assertFalse((self.public / 'live.json').exists())
        self.assertNotEqual((self.public / 'game-one.gif').read_bytes(), original_leader)
        self.publisher = StaticPublisher(self.public)
        self.snake.get_highscore_frames.reset_mock()
        self.publish()
        self.assertEqual((self.public / 'game-two.gif').read_bytes(), original_leader)
        self.assertEqual(self.metadata()['games'][0]['id'], 9)
        self.assertEqual(self.snake.get_highscore_frames.call_count, 5)
        self.snake.get_highscore_frames.reset_mock()
        self.assertIn('unchanged', self.publish())
        self.snake.get_highscore_frames.assert_not_called()

    def test_bad_capture_leaves_publication_untouched(self):
        self.publish()
        saved = {p.name: p.read_bytes() for p in self.public.iterdir()}
        self.app.get_daily_runs.return_value.insert(0, run(9))
        self.snake.get_highscore_frames.side_effect = lambda uuid: frames(999)
        with self.assertRaisesRegex(ValueError, 'score differs'):
            self.publish()
        self.assertEqual(saved, {p.name: p.read_bytes() for p in self.public.iterdir()})

    def test_lock_refuses_overlap_and_releases_after_failure(self):
        with self.publisher.session():
            with self.assertRaises(BlockingIOError):
                with StaticPublisher(self.public).session():
                    self.fail('Concurrent session entered')
        with self.assertRaises(RuntimeError):
            with self.publisher.session():
                raise RuntimeError('failed pass')
        self.publish()

    def test_symlinks_and_unmanaged_paths_are_refused(self):
        self.public.mkdir()
        secret = self.root / 'private'
        secret.write_bytes(b'private data')
        (self.public / 'game-one.gif').symlink_to(secret)
        with self.assertRaisesRegex(RuntimeError, 'symlinks'):
            self.publish()
        self.assertEqual(secret.read_bytes(), b'private data')
        with self.assertRaises(ValueError):
            self.publisher.publish({}, {'../private': b'GIF89a'}, updated='2026-10-29 12:00')
        linked = self.root / 'linked'
        linked.symlink_to(self.public)
        with self.assertRaises(ValueError):
            StaticPublisher(linked)

    def test_service_wires_static_publication(self):
        from snakewebcode import server
        with patch.dict(os.environ, PUBLISH_DIRECTORY=str(self.public)), \
                patch.object(server, 'DbMgr') as db, patch.object(server, 'PublishLive') as activity:
            server.publish_once()
        db.assert_called_once_with()
        self.assertIsInstance(activity.call_args.args[1], StaticPublisher)
        self.assertEqual(activity.call_args.args[1].directory, self.public)
        activity.return_value.run.assert_called_once_with()
