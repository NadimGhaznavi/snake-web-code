"""Observed daily rankings, GIF timing, and source-day boundaries."""

from datetime import date, datetime, timedelta
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

from snake_web.activity.AppDb import AppDb
from snake_web.activity.DailyProgress import export_daily_progress, read_progress, render_progress
from snake_web.interface.GitPublisher import GitPublisher


class DailyProgressTests(unittest.TestCase):
    def setUp(self):
        self.files = {}
        self.publisher = Mock()
        for name in ('PROGRESS_PATH', 'PROGRESS_GIF_PATH'):
            setattr(self.publisher, name, getattr(GitPublisher, name))
        self.publisher.read_history.side_effect = lambda name: self.files.get(name, '')
        self.publisher.read_bytes.side_effect = lambda name: self.files.get(name, b'')
        self.app = Mock()
        self.app.get_daily_configurations.return_value = []

    def export(self, timestamp, rows=()):
        self.app.get_daily_progress_time.return_value = datetime.fromisoformat(timestamp)
        self.app.get_daily_configurations.return_value = list(rows)
        html, files = export_daily_progress(self.app, self.publisher)
        self.files.update(files)
        return html, read_progress(files[GitPublisher.PROGRESS_PATH])

    def test_start_without_backfill_and_freeze_retries(self):
        html, state = self.export('2026-10-11T12:30:04', [dict(id=2, high_score=40)])
        self.assertEqual([frame['slot'] for frame in state['frames']], [24])
        self.assertIn('?v=', html)
        data = self.files[GitPublisher.PROGRESS_GIF_PATH]
        self.app.get_daily_configurations.reset_mock()
        with patch('snake_web.activity.DailyProgress.render_progress', wraps=render_progress) as render:
            repeated, state = self.export('2026-10-11T12:45:00', [dict(id=3, high_score=41)])
            render.assert_not_called()
        self.app.get_daily_configurations.assert_not_called()
        self.assertEqual(repeated, html)
        self.assertEqual(self.files[GitPublisher.PROGRESS_GIF_PATH], data)
        _, state = self.export('2026-10-11T14:00:00', [dict(id=3, high_score=41), dict(id=2, high_score=40)])
        self.assertEqual([frame['slot'] for frame in state['frames']], [24, 27])
        self.assertEqual(state['frames'][0]['configurations'], [dict(id=2, high_score=40)])

    def test_manual_publication_renders_saved_observations_without_collection(self):
        self.assertEqual(export_daily_progress(self.app, self.publisher, collect=False), ('', {}))
        html, state = self.export('2026-10-11T12:30:00', [dict(id=1, high_score=40)])
        self.app.reset_mock()
        del self.files[GitPublisher.PROGRESS_GIF_PATH]
        repeated, files = export_daily_progress(self.app, self.publisher, collect=False)
        self.assertEqual(repeated, html)
        self.assertEqual(read_progress(files[GitPublisher.PROGRESS_PATH]), state)
        self.assertTrue(files[GitPublisher.PROGRESS_GIF_PATH].startswith(b'GIF89a'))
        self.app.get_daily_progress_time.assert_not_called()
        self.app.get_daily_configurations.assert_not_called()

    def test_utc_observation_includes_completed_score_50_and_preserves_legacy_frames(self):
        connection = sqlite3.connect(':memory:')
        self.addCleanup(connection.close)
        connection.row_factory = sqlite3.Row
        connection.execute('CREATE TABLE simulation_runs (id INT, high_score INT, status TEXT, completed_at TEXT)')
        connection.executemany('INSERT INTO simulation_runs VALUES (?, ?, ?, ?)', [
            (2019, 44, 'completed', '2026-10-11 06:00:00'),
            (2030, 50, 'completed', '2026-10-11 11:05:40.726437'),
            (2032, 55, 'completed', '2026-10-11 13:30:12')])
        legacy = dict(version=1, renderer=3, day='2026-10-11', frames=[dict(
            slot=17, observed_at='2026-10-11T09:00:11',
            configurations=[dict(id=2019, high_score=44)])])
        self.files[GitPublisher.PROGRESS_PATH] = json.dumps(legacy)
        db = Mock()
        db.query.side_effect = lambda sql, params: [dict(row) for row in connection.execute(
            sql.replace('%s', '?'), tuple(str(value) for value in params))]
        self.app.get_daily_configurations.side_effect = AppDb(db).get_daily_configurations
        _, state = self.export('2026-10-11T13:30:11')
        # A result completed after this observation remains excluded.
        self.assertEqual(state['frames'][0], legacy['frames'][0])
        self.assertEqual(state['frames'][-1]['observed_at'], '2026-10-11T13:30:11+00:00')
        self.assertEqual(state['frames'][-1]['configurations'],
                         [dict(id=2030, high_score=50), dict(id=2019, high_score=44)])
        with Image.open(BytesIO(self.files[GitPublisher.PROGRESS_GIF_PATH])) as gif:
            gif.seek(gif.n_frames - 1)
            self.assertEqual(gif.convert('RGB').getpixel((741, 60)), (121, 184, 243))

    def test_footer_uses_toronto_time_and_keeps_legacy_local_labels(self):
        original = ImageDraw.ImageDraw.text
        for observed_at, expected in [
            ('2026-10-11T13:30:00+00:00', '11 Oct 2026 - 09:30'),
            ('2026-01-11T13:30:00+00:00', '11 Jan 2026 - 08:30'),
            ('2026-10-11T00:30:00+00:00', '10 Oct 2026 - 20:30'),
            ('2026-10-11T09:00:11', '11 Oct 2026 - 09:00')]:
            with self.subTest(observed_at=observed_at), \
                 patch.object(ImageDraw.ImageDraw, 'text', autospec=True, side_effect=original) as draw:
                render_progress(dict(frames=[dict(observed_at=observed_at, configurations=[])]))
                self.assertEqual(draw.call_args.args[2], expected)

    def test_complete_day_has_48_frames_and_99_second_loop(self):
        start = datetime(2026, 10, 11)
        # Exercise all slots without rendering every intermediate GIF again.
        with patch('snake_web.activity.DailyProgress.render_progress', return_value=b'GIF89a'):
            for number in range(1, 48):
                self.export((start + timedelta(minutes=30 * number)).isoformat(),
                            [dict(id=number, high_score=number)])
        self.export((start + timedelta(days=1)).isoformat(), [dict(id=48, high_score=48)])
        state = read_progress(self.files[GitPublisher.PROGRESS_PATH])
        self.assertEqual(state['day'], '2026-10-11')
        self.assertEqual([frame['slot'] for frame in state['frames']], list(range(48)))
        with Image.open(BytesIO(self.files[GitPublisher.PROGRESS_GIF_PATH])) as gif:
            self.assertEqual(gif.n_frames, 48)
            self.assertEqual(gif.info['loop'], 0)
            durations = []
            for index in range(48):
                gif.seek(index)
                durations.append(gif.info['duration'])
            self.assertEqual(durations, [2000] * 47 + [5000])
            self.assertEqual(sum(durations), 99000)

    def test_rollover_discards_yesterday_and_empty_is_not_zero(self):
        self.export('2026-10-11T23:30:00', [dict(id=1, high_score=42)])
        _, state = self.export('2026-10-12T00:00:00', [dict(id=2, high_score=43), dict(id=1, high_score=42)])
        self.assertEqual(state['day'], '2026-10-11')
        self.assertEqual(state['frames'][-1]['slot'], 47)
        self.app.get_daily_configurations.assert_called_with(date(2026, 10, 11), datetime(2026, 10, 12))
        _, state = self.export('2026-10-12T00:30:00')
        self.assertEqual(state['day'], '2026-10-12')
        self.assertEqual(len(state['frames']), 1)
        self.assertEqual(state['frames'][0]['configurations'], [])
        _, state = self.export('2026-10-12T01:00:00', [dict(id=3, high_score=0)])
        self.assertEqual(state['frames'][-1]['configurations'], [dict(id=3, high_score=0)])

    def test_ascending_bars_fixed_scale_and_ten_slots(self):
        rows = [dict(id=number, high_score=number * 4) for number in range(10, 0, -1)]
        self.export('2026-10-11T00:30:00', rows)
        self.export('2026-10-11T01:00:00', [dict(id=11, high_score=45)] + rows[:9])
        with Image.open(BytesIO(self.files[GitPublisher.PROGRESS_GIF_PATH])) as gif:
            for frame, scores in enumerate((list(range(4, 41, 4)), list(range(8, 41, 4)) + [45])):
                gif.seek(frame)
                image = gif.convert('RGB')
                for index, score in enumerate(scores):
                    x = 111 + index * 70
                    y = 328 - 270 * score / 50
                    self.assertEqual(image.getpixel((x, int(y) + 2)), (121, 184, 243))
                    self.assertEqual(image.getpixel((x, int(y) - 2)), (16, 23, 32))

    def test_invalid_state_and_source_rows_fail(self):
        _, state = self.export('2026-10-11T12:30:00')
        invalid = {**state, 'frames': [state['frames'][0], state['frames'][0]]}
        with self.assertRaises(ValueError):
            read_progress(json.dumps(invalid))
        for rows in ([dict(id=1, high_score=None)], [dict(id=1, high_score=-1)],
                     [dict(id=1, high_score=40), dict(id=1, high_score=40)],
                     [dict(id=1, high_score=30), dict(id=2, high_score=40)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.export('2026-10-11T13:00:00', rows)
        with self.assertRaisesRegex(ValueError, 'backwards'):
            self.export('2026-10-11T12:00:00')

    def test_renderer_upgrade_and_missing_gif_use_observations(self):
        self.export('2026-10-11T12:30:00', [dict(id=1, high_score=40)])
        state = json.loads(self.files[GitPublisher.PROGRESS_PATH])
        state['renderer'] = 0
        self.files[GitPublisher.PROGRESS_PATH] = json.dumps(state)
        self.app.get_daily_configurations.reset_mock()
        with patch('snake_web.activity.DailyProgress.render_progress', wraps=render_progress) as render:
            self.export('2026-10-11T12:35:00')
            render.assert_called_once()
        self.app.get_daily_configurations.assert_not_called()
        del self.files[GitPublisher.PROGRESS_GIF_PATH]
        self.export('2026-10-11T12:40:00')
        self.assertTrue(self.files[GitPublisher.PROGRESS_GIF_PATH].startswith(b'GIF89a'))

    def test_source_query_boundaries_order_ties_null_zero_and_limit(self):
        connection = sqlite3.connect(':memory:')
        self.addCleanup(connection.close)
        connection.row_factory = sqlite3.Row
        connection.execute('CREATE TABLE simulation_runs (id INT, high_score INT, status TEXT, completed_at TEXT)')
        connection.executemany('INSERT INTO simulation_runs VALUES (?, ?, ?, ?)', [
            (1, 99, 'completed', '2026-10-10 23:59:59'),
            (2, 41, 'completed', '2026-10-11 00:00:00'),
            (3, 41, 'completed', '2026-10-11 12:30:00'),
            (4, 99, 'completed', '2026-10-11 12:30:01'),
            (5, 0, 'completed', '2026-10-11 12:00:00'),
            (6, None, 'completed', '2026-10-11 12:00:00'),
            (7, 99, 'running', '2026-10-11 12:00:00'),
            (8, 99, 'completed', '2026-10-12 00:00:00')])
        db = Mock()
        db.query.side_effect = lambda sql, params: [dict(row) for row in connection.execute(
            sql.replace('%s', '?'), tuple(str(value) for value in params))]
        app = AppDb(db)
        self.assertEqual(app.get_daily_configurations(date(2026, 10, 11), datetime(2026, 10, 11, 12, 30)),
                         [dict(id=2, high_score=41), dict(id=3, high_score=41), dict(id=5, high_score=0)])
        connection.executemany('INSERT INTO simulation_runs VALUES (?, ?, ?, ?)',
                               [(number, 40, 'completed', '2026-10-11 12:00:00') for number in range(9, 25)])
        leaders = app.get_daily_configurations(date(2026, 10, 11), datetime(2026, 10, 11, 12, 30))
        self.assertEqual([row['id'] for row in leaders], [2, 3] + list(range(9, 17)))


class PackagingTests(unittest.TestCase):
    def test_installer_includes_renderer(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn('snake_web/activity/DailyProgress.py', (root / 'scripts/install.sh').read_text())
