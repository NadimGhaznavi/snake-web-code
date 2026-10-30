"""Behavior and contract checks for BMForge's application-owned GIF template."""

import ast
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image, ImageSequence

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "snakewebcode/interface/GIFAnimation.py"

from snakewebcode.interface.GIFAnimation import GIFAnimation


class GifAnimationTests(unittest.TestCase):
    @staticmethod
    def frame(color):
        return Image.new("RGB", (8, 6), color)

    def test_bytes_loop_timing_and_full_frames(self):
        animation = GIFAnimation(8, 6)
        for color in ("red", "lime", "blue"):
            animation.add_frame(self.frame(color), duration_ms=75)
        with Image.open(BytesIO(animation.to_bytes())) as image:
            self.assertEqual(image.size, (8, 6))
            self.assertEqual(image.n_frames, 3)
            self.assertEqual(image.info["loop"], 0)
            self.assertEqual([frame.info["duration"] for frame in ImageSequence.Iterator(image)],
                             [80, 70, 80])
            self.assertEqual([frame.convert("RGB").getpixel((4, 3))
                              for frame in ImageSequence.Iterator(image)],
                             [(255, 0, 0), (0, 255, 0), (0, 0, 255)])
            self.assertEqual([frame.disposal_method for frame in ImageSequence.Iterator(image)],
                             [2, 2, 2])

    def test_many_75ms_frames_do_not_accumulate_rounding_drift(self):
        animation = GIFAnimation(8, 6)
        for index in range(20):
            animation.add_frame(self.frame("red" if index % 2 else "blue"), duration_ms=75)
        with Image.open(BytesIO(animation.to_bytes())) as image:
            durations = [frame.info["duration"] for frame in ImageSequence.Iterator(image)]
            self.assertEqual(durations, [80, 70] * 10)
            self.assertEqual(sum(durations), 1500)

    def test_explicit_durations_with_final_pause(self):
        animation = GIFAnimation(8, 6, loop=False)
        animation.add_frame(self.frame("red"), duration_ms=50)
        animation.add_frame(self.frame("blue"), duration_ms=1000)
        with Image.open(BytesIO(animation.to_bytes())) as image:
            self.assertNotIn("loop", image.info)
            self.assertEqual([frame.info["duration"] for frame in ImageSequence.Iterator(image)],
                             [50, 1000])

    def test_add_frame_copies_source_and_preserves_indexed_palette(self):
        frame = Image.new("P", (8, 6), 0)
        frame.putpalette([12, 34, 56, 200, 180, 160] + [0] * 762)
        animation = GIFAnimation(8, 6)
        animation.add_frame(frame, duration_ms=100)
        frame.paste(1, (0, 0, 8, 6))
        with Image.open(BytesIO(animation.to_bytes())) as image:
            self.assertEqual(image.convert("RGB").getpixel((4, 3)), (12, 34, 56))

    def test_alpha_composited_onto_explicit_background(self):
        frame = Image.new("RGBA", (8, 6), (0, 0, 0, 0))
        frame.putpixel((0, 0), (255, 0, 0, 255))
        animation = GIFAnimation(8, 6, background=(20, 40, 60))
        animation.add_frame(frame, duration_ms=100)
        with Image.open(BytesIO(animation.to_bytes())) as image:
            rgb = image.convert("RGB")
            self.assertEqual(rgb.getpixel((0, 0)), (255, 0, 0))
            self.assertEqual(rgb.getpixel((4, 3)), (20, 40, 60))

    def test_single_frame_and_filesystem_output(self):
        animation = GIFAnimation(8, 6)
        animation.add_frame(self.frame("orange"), duration_ms=123)
        with TemporaryDirectory() as folder:
            output = Path(folder) / "animation.gif"
            self.assertEqual(animation.save(output), output)
            with Image.open(output) as image:
                self.assertEqual(image.n_frames, 1)
                self.assertEqual(image.info["duration"], 120)

    def test_reject_invalid_configuration_and_frames(self):
        for size in ((0, 2), (8, -1), (True, 6), (8, 1.5)):
            with self.subTest(size=size), self.assertRaises(ValueError):
                GIFAnimation(*size)
        for options in ({"loop": 0}, {"background": "white"},
                        {"background": (0, 0, 256)}, {"background": (False, 3, 4)}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                GIFAnimation(8, 6, **options)
        animation = GIFAnimation(8, 6)
        with self.assertRaises(ValueError):
            animation.to_bytes()
        with self.assertRaises(TypeError):
            animation.add_frame("not an image", duration_ms=100)
        with self.assertRaises(ValueError):
            animation.add_frame(Image.new("RGB", (7, 6)), duration_ms=100)
        for duration in (0, 9, -1, 600001, 100.0, True):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                animation.add_frame(self.frame("red"), duration_ms=duration)
        self.assertEqual(animation._frames, [])

    def test_template_dependencies_and_provenance(self):
        content = TEMPLATE.read_text()
        self.assertIn('BMFORGE_COMPONENT = {"id": "bmforge.gif-animation", "spec_version": "0.1.0"}',
                      content)
        self.assertNotIn("from bmforge", content)
        imports = set()
        for node in ast.walk(ast.parse(content)):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                imports.add(node.module)
        self.assertEqual(imports, {"io", "pathlib", "PIL"})


if __name__ == "__main__":
    unittest.main()
