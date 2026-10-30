"""Check Ax3l-compatible cumulative GIF frames, timing, labels, and shared scales."""
from io import BytesIO
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from snakewebcode.activity.ScoreDistribution import distribution_frames, render_distribution, PLOT


class ScoreDistributionTests(unittest.TestCase):
    def test_2054_simulations_have_four_cumulative_checkpoints_and_all_runs(self):
        scores = {number: number % 20 for number in range(1, 2055)}
        frames = distribution_frames(scores)
        self.assertEqual(len(frames), 6)
        self.assertEqual(frames[0], ('Before simulation #1', []))
        self.assertEqual(frames[1][0], 'Simulations #1–500')
        self.assertEqual(frames[2][0], 'Simulations #1–1000')
        self.assertEqual(frames[-2][0], 'Simulations #1–2000')
        self.assertEqual(frames[-1][0], 'All simulations #1–2054')
        self.assertEqual([len(values) for _, values in frames[1:-1]], [500, 1000, 1500, 2000])
        for index, (_, values) in enumerate(frames[1:-1], 1):
            self.assertEqual(values, [scores[number] for number in range(1, index * 500 + 1)])
        self.assertEqual(len(frames[-1][1]), 2054)
        gif = Image.open(BytesIO(render_distribution(scores)))
        self.assertEqual(gif.n_frames, 6)
        self.assertEqual(gif.info['loop'], 0)
        self.assertEqual(gif.size, (800, 480))
        for index in range(6):
            gif.seek(index)
            self.assertEqual(gif.info['duration'], 5000 if index == 5 else 2000)
            self.assertEqual(gif.disposal_method, 2)

    def test_fixed_axes_bar_positions_and_embedded_labels(self):
        # Cumulative bars grow while both axes stay fixed through the final frame.
        scores = {number: 0 if number % 2 else 10 for number in range(1, 1001)}
        labels = []
        font_sizes = {}
        original = ImageDraw.ImageDraw.text
        def record(draw, xy, text, *args, **kwargs):
            labels.append(text)
            font_sizes[text] = kwargs['font'].size
            return original(draw, xy, text, *args, **kwargs)
        with patch.object(ImageDraw.ImageDraw, 'text', record):
            data = render_distribution(scores)
        self.assertIn('Simulations #1–1000', labels)
        self.assertIn('1,000 submitted · 1,000 scored', labels)
        self.assertIn('Number of runs', labels)
        self.assertIn('Run high score', labels)
        self.assertEqual(font_sizes['Number of runs'], 15)
        self.assertEqual(font_sizes['Score Distribution'], 17)
        self.assertEqual(font_sizes['Simulations #1–1000'], 14)
        self.assertEqual(font_sizes['Run high score'], 14)
        self.assertEqual(font_sizes['1,000 submitted · 1,000 scored'], 12)
        self.assertEqual(font_sizes['200'], 11)
        self.assertIn('500', labels)
        gif = Image.open(BytesIO(data))
        images = []
        for index in range(gif.n_frames):
            gif.seek(index)
            images.append(gif.convert('RGB'))
        for image in images[1:]:
            self.assertEqual(image.crop((90, 351, 775, 430)).tobytes(),
                             images[0].crop((90, 351, 775, 430)).tobytes())
        for image in images[1:]:
            self.assertEqual(image.crop((0, 110, 90, 351)).tobytes(),
                             images[0].crop((0, 110, 90, 351)).tobytes())
        x = int(PLOT[0] + .5 * (PLOT[2] - PLOT[0]) / 11)
        blue = (76, 155, 232)
        self.assertNotEqual(images[0].getpixel((x, 300)), blue)
        self.assertEqual(images[1].getpixel((x, 300)), blue)
        self.assertNotEqual(images[1].getpixel((x, 150)), blue)
        self.assertEqual(images[-1].getpixel((x, 150)), blue)
        self.assertEqual(data, render_distribution(scores))

    def test_null_zero_and_missing_ids_preserve_reached_checkpoints(self):
        scores = {1: 9, 2: 0}
        self.assertEqual(distribution_frames(scores)[-1][1], [9, 0])
        missing = {number: None for number in range(1, 1001) if number != 50}
        frames = distribution_frames(missing)
        self.assertEqual(len(frames), 4)
        self.assertEqual(frames[1][0], 'Simulations #1–500')
        self.assertEqual(len(frames[1][1]), 499)
        self.assertEqual(frames[2][0], 'Simulations #1–1000')
        self.assertEqual(len(frames[2][1]), 999)
        for scores in ({}, {1: None}, {1: 0}, missing):
            gif = Image.open(BytesIO(render_distribution(scores)))
            self.assertEqual(gif.n_frames, len(distribution_frames(scores)))
            gif.seek(gif.n_frames - 1)
            self.assertEqual(gif.info['duration'], 5000)

    def test_second_encoded_frame_shows_first_500_range_despite_missing_id(self):
        scores = {number: 0 for number in range(2, 1055)}
        gif = Image.open(BytesIO(render_distribution(scores)))
        self.assertEqual(gif.n_frames, 4)
        palette = gif.copy()
        gif.seek(1)
        self.assertEqual(gif.info['duration'], 2000)
        # Compare the decoded frame's range label to independently drawn text.
        expected = Image.new('RGB', gif.size, '#101720')
        from PIL import ImageFont
        from snakewebcode.activity.ScoreDistribution import FONT
        ImageDraw.Draw(expected).text((24, 56), 'Simulations #1–500',
                                      font=ImageFont.truetype(str(FONT), 14), fill='#d5dfeb')
        expected = expected.quantize(palette=palette, dither=Image.Dither.NONE).convert('RGB')
        self.assertEqual(gif.convert('RGB').crop((24, 56, 250, 80)).tobytes(),
                         expected.crop((24, 56, 250, 80)).tobytes())
        self.assertEqual(distribution_frames({1001: 0})[1:3],
                         [('Simulations #1–500', []), ('Simulations #1–1000', [])])

    def test_final_y_scale_includes_partial_block_and_is_used_throughout(self):
        scores = {number: number % 50 for number in range(1, 501)}
        scores.update({number: number % 25 for number in range(501, 1001)})
        scores.update({number: 0 for number in range(1001, 1100)})
        ticks = []
        original = ImageDraw.ImageDraw.text
        def record(draw, xy, text, *args, **kwargs):
            if text == 'Score Distribution':
                ticks.append([])
            if xy[0] == PLOT[0] - 10:
                ticks[-1].append(text)
            return original(draw, xy, text, *args, **kwargs)
        with patch.object(ImageDraw.ImageDraw, 'text', record):
            render_distribution(scores)
        self.assertEqual(ticks, [['0', '26', '52', '78', '104', '130']] * 4)

    def test_rare_scores_remain_visible_with_large_all_run_counts(self):
        scores = {number: 0 for number in range(1, 1001)}
        scores[1001] = 100
        gif = Image.open(BytesIO(render_distribution(scores)))
        gif.seek(gif.n_frames - 1)
        image = gif.convert('RGB')
        x = int(PLOT[0] + 100.5 * (PLOT[2] - PLOT[0]) / 101)
        self.assertEqual(image.getpixel((x, PLOT[3] - 1)), (76, 155, 232))

