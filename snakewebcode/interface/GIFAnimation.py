"""Encode application-rendered Pillow frames as an animated GIF."""

from io import BytesIO
from pathlib import Path

from PIL import Image


BMFORGE_COMPONENT = {"id": "bmforge.gif-animation", "spec_version": "0.1.0"}


class GIFAnimation:
    """Own frame timing and GIF encoding, not application-specific rendering."""

    def __init__(self, width: int, height: int, *, loop: bool = True,
                 background: tuple[int, int, int] = (255, 255, 255)):
        if type(width) is not int or width <= 0 or type(height) is not int or height <= 0:
            raise ValueError("GIF dimensions must be positive integers")
        if type(loop) is not bool:
            raise ValueError("loop must be a boolean")
        if (not isinstance(background, tuple) or len(background) != 3
                or any(type(channel) is not int or not 0 <= channel <= 255
                       for channel in background)):
            raise ValueError("background must be an RGB tuple of integers from 0 to 255")
        self.width = width
        self.height = height
        self.loop = loop
        self.background = background
        self._frames: list[Image.Image] = []
        self._durations: list[int] = []

    def add_frame(self, frame: Image.Image, *, duration_ms: int) -> None:
        """Snapshot a full-size frame and its requested playback duration."""
        if not isinstance(frame, Image.Image):
            raise TypeError("frame must be a Pillow image")
        if frame.size != (self.width, self.height):
            raise ValueError(f"frame must be {self.width}x{self.height}, got {frame.size}")
        if (type(duration_ms) is not int or duration_ms < 10
                or duration_ms > 600000):
            raise ValueError("duration_ms must be an integer from 10 to 600000")
        if frame.mode == "P" and "transparency" not in frame.info:
            prepared = frame.copy()  # Preserve caller-provided, stable indexed palettes.
        else:
            rgba = frame.convert("RGBA")
            canvas = Image.new("RGBA", frame.size, (*self.background, 255))
            canvas.alpha_composite(rgba)
            prepared = canvas.convert("RGB")
        self._frames.append(prepared)
        self._durations.append(duration_ms)

    def to_bytes(self) -> bytes:
        """Return an encoded GIF, rounding cumulative playback time to 10 ms ticks."""
        if not self._frames:
            raise ValueError("Cannot encode a GIF without frames")
        elapsed_ms = encoded_ms = 0
        durations = []
        for duration in self._durations:
            elapsed_ms += duration
            next_ms = ((elapsed_ms + 5) // 10) * 10
            durations.append(next_ms - encoded_ms)
            encoded_ms = next_ms
        options = {
            "format": "GIF", "save_all": True,
            "append_images": self._frames[1:],
            "duration": durations, "disposal": 2, "optimize": False,
        }
        if self.loop:
            options["loop"] = 0
        with BytesIO() as output:
            self._frames[0].save(output, **options)
            return output.getvalue()

    def save(self, path: str | Path) -> Path:
        """Write the encoded GIF to an existing directory; return its path."""
        destination = Path(path)
        destination.write_bytes(self.to_bytes())
        return destination
