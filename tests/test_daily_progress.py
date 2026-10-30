"""Verify observed daily score animation, retention, rollover, and saved-state validation."""

from datetime import date, datetime
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

from snakewebcode.activity.DailyProgress import export_daily_progress, read_progress, render_progress
from snakewebcode.interface.StaticPublisher import StaticPublisher


class DailyProgressTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='snakeweb-progress-')
        self.addCleanup(temporary.cleanup)
        self.publisher = StaticPublisher(Path(temporary.name) / 'public')
        self.publisher.directory.mkdir()
        self.app = Mock()
        self.app.get_daily_progress_time.return_value = datetime(2026, 10, 30, 12, 30)
        self.app.get_daily_configurations.return_value = [dict(id=12, high_score=20), dict(id=11, high_score=0)]

    def collect(self, *, collect=True):
        content, files = export_daily_progress(self.app, self.publisher, collect=collect)
        for name, data in files.items():
            (self.publisher.directory / name).write_bytes(data)
        self.publisher.save_progress(content)
        return read_progress(content), files

    def test_collect_only_observed_slots_without_backfilling_or_duplicate_samples(self):
        first, files = self.collect()
        self.assertEqual([frame['slot'] for frame in first['frames']], [24])
        self.app.get_daily_configurations.assert_called_once_with(
            date(2026, 10, 30), datetime(2026, 10, 30, 12, 30))
        again, repeated = self.collect()
        self.assertEqual(again, first)
        self.assertEqual(repeated, files)
        self.app.get_daily_configurations.assert_called_once()
        self.app.get_daily_progress_time.return_value = datetime(2026, 10, 30, 14)
        later, _ = self.collect()
        self.assertEqual([frame['slot'] for frame in later['frames']], [24, 27])
        self.assertEqual(later['frames'][0], first['frames'][0])

    def test_manual_refresh_never_collects_and_recovers_missing_gif(self):
        self.assertEqual(export_daily_progress(self.app, self.publisher, collect=False), ('', {}))
        self.app.get_daily_progress_time.assert_not_called()
        first, files = self.collect()
        (self.publisher.directory / 'daily-progress.gif').unlink()
        self.app.reset_mock()
        again, regenerated = self.collect(collect=False)
        self.assertEqual(first, again)
        self.assertEqual(files, regenerated)
        self.app.get_daily_progress_time.assert_not_called()
        self.app.get_daily_configurations.assert_not_called()

    def test_midnight_closes_previous_utc_day_then_rollover_starts_empty_day(self):
        self.app.get_daily_progress_time.return_value = datetime(2026, 10, 31)
        closed, _ = self.collect()
        self.assertEqual(closed['day'], '2026-10-30')
        self.assertEqual(closed['frames'][0]['slot'], 47)
        self.app.get_daily_configurations.assert_called_with(date(2026, 10, 30), datetime(2026, 10, 31))
        self.app.get_daily_progress_time.return_value = datetime(2026, 10, 31, 0, 30)
        self.app.get_daily_configurations.return_value = []
        fresh, files = self.collect()
        self.assertEqual(fresh['day'], '2026-10-31')
        self.assertEqual(len(fresh['frames']), 1)
        self.assertEqual(fresh['frames'][0]['slot'], 0)
        self.assertEqual(fresh['frames'][0]['configurations'], [])
        self.assertTrue(files['daily-progress.gif'].startswith(b'GIF89a'))

    def test_retention_is_at_most_one_day_and_48_observations(self):
        # Stub rendering so this exercises 49 collections without repeatedly encoding 48-frame GIFs.
        with patch('snakewebcode.activity.DailyProgress.render_progress', return_value=b'GIF89a fixture'):
            for slot in range(48):
                self.app.get_daily_progress_time.return_value = (
                    datetime(2026, 10, 31) if slot == 47
                    else datetime(2026, 10, 30, (slot + 1) // 2, (slot + 1) % 2 * 30))
                state, _ = self.collect()
            self.assertEqual(len(state['frames']), 48)
            self.app.get_daily_progress_time.return_value = datetime(2026, 10, 31, 0, 30)
            state, _ = self.collect()
            self.assertEqual(len(state['frames']), 1)

    def test_backwards_clock_and_invalid_saved_observations_fail(self):
        state, _ = self.collect()
        self.app.get_daily_progress_time.return_value = datetime(2026, 10, 30, 12)
        with self.assertRaisesRegex(ValueError, 'clock moved backwards'):
            self.collect()
        for change in (
            {'day': None},
            {'frames': []},
            {'frames': [state['frames'][0]] * 2},
            {'day': '2026-10-29'},
            {'frames': [{**state['frames'][0], 'observed_at': '2026-10-30T12:30:00-04:00'}]},
            {'frames': [{**state['frames'][0], 'observed_at': None}]},
            {'frames': [{**state['frames'][0], 'configurations': [None]}]},
            {'frames': [{**state['frames'][0], 'configurations': [dict(id=1, high_score=-1)]}]},
            {'frames': [{**state['frames'][0], 'configurations': [dict(id=1, high_score=0)] * 2}]},
            {'frames': [{**state['frames'][0], 'configurations': list(reversed(state['frames'][0]['configurations']))}]},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                read_progress(json.dumps({**state, **change}))

    def test_renderer_upgrade_rebuilds_without_collecting(self):
        self.collect()
        from snakewebcode.activity.DailyProgress import render_progress
        with patch('snakewebcode.activity.DailyProgress.RENDERER_VERSION', 2), \
                patch('snakewebcode.activity.DailyProgress.render_progress', wraps=render_progress) as renderer:
            state, _ = self.collect(collect=False)
        self.assertEqual(state['renderer'], 2)
        renderer.assert_called_once()

    def test_gif_fixed_scale_ascending_bars_zero_timestamps_and_timing(self):
        self.collect()
        self.app.get_daily_progress_time.return_value = datetime(2026, 10, 30, 13)
        self.app.get_daily_configurations.return_value = [dict(id=13, high_score=100), dict(id=11, high_score=0)]
        state, _ = self.collect()
        labels = []
        original = ImageDraw.ImageDraw.text

        def record(draw, xy, text, *args, **kwargs):
            labels.append(text)
            return original(draw, xy, text, *args, **kwargs)

        with patch.object(ImageDraw.ImageDraw, 'text', record):
            data = render_progress(state)
        self.assertIn('30 Oct 2026 - 08:30', labels)
        self.assertIn('30 Oct 2026 - 09:00', labels)
        self.assertIn('Configuration (simulation ID)', labels)
        self.assertIn('0', labels)
        self.assertEqual(data, render_progress(state))
        with Image.open(BytesIO(data)) as gif:
            self.assertEqual(gif.size, (800, 438))
            self.assertEqual(gif.n_frames, 2)
            self.assertEqual(gif.info['loop'], 0)
            first = gif.convert('RGB')
            self.assertEqual(gif.info['duration'], 2000)
            self.assertEqual(gif.disposal_method, 2)
            gif.seek(1)
            final = gif.convert('RGB')
            self.assertEqual(gif.info['duration'], 5000)
            self.assertEqual(gif.disposal_method, 2)
        self.assertEqual(first.crop((0, 58, 77, 329)).tobytes(), final.crop((0, 58, 77, 329)).tobytes())
        self.assertNotEqual(first.getpixel((741, 100)), (121, 184, 243))
        self.assertEqual(final.getpixel((741, 100)), (121, 184, 243))
        self.assertNotEqual(final.getpixel((671, 327)), (121, 184, 243))
