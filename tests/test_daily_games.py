"""Daily selection, durable caching, source boundaries, and capture validation."""

from datetime import date
from io import BytesIO
import json
import sqlite3
import unittest
from unittest.mock import Mock, patch
from uuid import UUID

from PIL import Image
import zmq

from snake_web.activity.AppDb import AppDb
from snake_web.activity.DailyGames import export_daily_games, render_daily_games
from snake_web.interface.GitPublisher import GitPublisher
from snake_web.interface.SnakeLab import SnakeLab, SnakeLabQueryError


def run(number, score):
    return dict(id=number, run_id=str(UUID(int=number)), high_score=score)


def frames(score):
    board = dict(grid_size=[4, 3], snake_head=[1, 0], snake_body=[[0, 0]],
                 food=[3, 2], direction=[1, 0], score=score)
    return [dict(version=1, episode=1, step=step,
                 board={**board, 'snake_head': [step + 1, 0]}) for step in range(2)]


class DailyGamesTests(unittest.TestCase):
    def setUp(self):
        self.files = {}
        self.publisher = Mock()
        for name in ('DAILY_PATH', 'DAILY_GIF_PATHS'):
            setattr(self.publisher, name, getattr(GitPublisher, name))
        self.publisher.read_history.side_effect = lambda name: self.files.get(name, '')
        self.publisher.read_bytes.side_effect = lambda name: self.files.get(name, b'')
        self.app = Mock()
        self.app.get_daily_game_day.return_value = date(2026, 10, 10)
        self.snake = Mock()
        self.snake.get_highscore_frames.side_effect = lambda uuid: frames(int(UUID(uuid)))

    def export(self, rows):
        self.app.get_daily_runs.return_value = rows
        games, files = export_daily_games(self.app, self.publisher, self.snake)
        self.files.update(files)
        return games, files

    def test_skip_legacy_and_continue_beyond_first_three(self):
        self.snake.get_highscore_frames.side_effect = lambda uuid: (
            None if int(UUID(uuid)) <= 3 else frames(int(UUID(uuid))))
        games, files = self.export([run(1, 100), run(2, 90), run(3, 80),
                                   run(6, 6), run(5, 5), run(4, 4), run(7, 0)])
        self.assertEqual([game['id'] for game in games], [6, 5, 4])
        self.assertEqual(self.snake.get_highscore_frames.call_count, 6)
        for path in GitPublisher.DAILY_GIF_PATHS:
            with Image.open(BytesIO(files[path])) as gif:
                self.assertEqual(gif.info['loop'], 0)
                self.assertGreater(gif.n_frames, 1)
                self.assertGreater(gif.width, 128)
                self.assertGreater(gif.height, 96)

    def test_restart_reuses_gifs_and_new_winner_moves_cached_slots(self):
        self.export([run(3, 3), run(2, 2), run(1, 1)])
        old_bytes = self.files[GitPublisher.DAILY_GIF_PATHS[0]]
        self.snake.get_highscore_frames.reset_mock()
        games, files = self.export([run(4, 4), run(3, 3), run(2, 2), run(1, 1)])
        self.snake.get_highscore_frames.assert_called_once_with(run(4, 4)['run_id'])
        self.assertEqual([g['id'] for g in games], [4, 3, 2])
        self.assertEqual(files[GitPublisher.DAILY_GIF_PATHS[1]], old_bytes)
        self.snake.get_highscore_frames.reset_mock()
        self.export([run(4, 4), run(3, 3), run(2, 2)])
        self.snake.get_highscore_frames.assert_not_called()

    def test_day_rollover_is_blank_and_never_uses_yesterdays_games(self):
        self.export([run(1, 1)])
        self.app.get_daily_game_day.return_value = date(2026, 10, 11)
        games, files = self.export([])
        self.assertEqual(games, [])
        self.assertEqual(json.loads(files[GitPublisher.DAILY_PATH])['games'], [])
        self.assertEqual(render_daily_games(games), '')

    def test_renderer_change_regenerates_capture(self):
        self.export([run(1, 1)])
        state = json.loads(self.files[GitPublisher.DAILY_PATH])
        state['renderer'] -= 1
        self.files[GitPublisher.DAILY_PATH] = json.dumps(state)
        self.snake.get_highscore_frames.reset_mock()
        self.export([run(1, 1)])
        self.snake.get_highscore_frames.assert_called_once()

    def test_outage_retains_current_day_cached_games(self):
        self.export([run(2, 2), run(1, 1)])
        self.snake.get_highscore_frames.side_effect = zmq.Again()
        with self.assertLogs(level='ERROR'):
            games, _ = self.export([run(5, 5), run(4, 4), run(2, 2), run(1, 1)])
        self.assertEqual([g['id'] for g in games], [2, 1])

    def test_zero_qualifies_and_caption_has_simulation_id(self):
        self.snake.get_highscore_frames.return_value = frames(0)
        self.snake.get_highscore_frames.side_effect = None
        games, _ = self.export([run(41, 0)])
        html = render_daily_games(games)
        self.assertIn('Simulation #41 - Highscore 0', html)
        self.assertIn('.gif?', html)
        self.assertNotIn('svg', html)
        self.assertNotIn(' hidden', html)

    def test_score_mismatch_fails_before_any_files_are_written(self):
        with self.assertRaisesRegex(ValueError, 'score differs'):
            self.export([run(1, 999)])
        self.assertEqual(self.files, {})

    def test_query_day_boundaries_ties_null_and_incomplete(self):
        connection = sqlite3.connect(':memory:')
        self.addCleanup(connection.close)
        connection.row_factory = sqlite3.Row
        connection.execute('CREATE TABLE simulation_runs (id INT, run_id TEXT, high_score INT, '
                           'status TEXT, completed_at TEXT)')
        connection.executemany('INSERT INTO simulation_runs VALUES (?, ?, ?, ?, ?)', [
            (1, 'a', 99, 'completed', '2026-10-09 23:59:59'),
            (2, 'b', 5, 'completed', '2026-10-10 00:00:00'),
            (3, 'c', 5, 'completed', '2026-10-10 23:59:59'),
            (4, 'd', 99, 'completed', '2026-10-11 00:00:00'),
            (5, 'e', 0, 'completed', '2026-10-10 12:00:00'),
            (6, 'f', None, 'completed', '2026-10-10 12:00:00'),
            (7, 'g', 99, 'running', '2026-10-10 12:00:00')])
        db = Mock()
        db.query.side_effect = lambda sql, params: [dict(r) for r in connection.execute(
            sql.replace('%s', '?'), tuple(str(p) for p in params))]
        self.assertEqual([r['id'] for r in AppDb(db).get_daily_runs(date(2026, 10, 10))], [2, 3, 5])


class CaptureContractTests(unittest.TestCase):
    def test_unavailable_capture_and_validated_metadata(self):
        snake = SnakeLab()
        run_id = run(1, 1)['run_id']
        with patch.object(snake, '_request', side_effect=SnakeLabQueryError(
                {'code': 'frames_unavailable'})):
            self.assertIsNone(snake.get_highscore_frames(run_id))
        with patch.object(snake, '_request', return_value={'run_id': run_id, 'frames': frames(1)}) as request:
            self.assertEqual(snake.get_highscore_frames(run_id), frames(1))
            request.assert_called_once_with('simulation.highscore_frames', {'run_id': run_id})
        for payload in ({'run_id': run_id, 'frames': []},
                        {'run_id': run(2, 2)['run_id'], 'frames': frames(1)},
                        {'run_id': run_id, 'frames': [{**frames(1)[0], 'step': 4}]}):
            with patch.object(snake, '_request', return_value=payload), self.assertRaises(ValueError):
                snake.get_highscore_frames(run_id)

    def test_zmq_request_uses_versioned_envelope_and_checks_response(self):
        with patch('snake_web.interface.SnakeLab.zmq.Context') as context:
            socket = context.return_value.__enter__.return_value.socket.return_value.__enter__.return_value
            socket.recv_json.side_effect = lambda: dict(
                protocol_version=1, request_id=socket.send_json.call_args.args[0]['request_id'],
                status='ok', payload={'frames': []})
            snake = SnakeLab('tcp://127.0.0.1:12345')
            self.assertEqual(snake._request('simulation.highscore_frames', {'run_id': 'test'}), {'frames': []})
            request = socket.send_json.call_args.args[0]
            self.assertEqual(request['protocol_version'], 1)
            self.assertEqual(request['method'], 'simulation.highscore_frames')
            socket.connect.assert_called_with('tcp://127.0.0.1:12345')
            socket.recv_json.return_value = {'protocol_version': 1, 'request_id': 'wrong'}
            socket.recv_json.side_effect = None
            with self.assertRaisesRegex(ValueError, 'request_id'):
                snake._request('simulation.highscore_frames', {})
