---
title: GIF Animation Component
lang: en
locale: en-US
language_name: English
component_id: "bmforge.gif-animation"
spec_version: "0.1.0"
spec_status: "draft"
translation_key: bmforge-component-gif-animation
---

**Component ID:** `{{ page.component_id }}` · **Specification:** `{{ page.spec_version }}` ({{ page.spec_status }})

This optional component encodes a sequence of **already-rendered Pillow images** into an animated GIF. The consuming application owns the frame content and cadence, whether those frames are charts, screenshots, Snake simulations, or photographs. The encoder owns frame snapshots, dimensions, timing quantization, palette handling, loop metadata and GIF encoding. It does **not** render domain data, take screenshots, manage a camera, schedule a job, publish files, run an HTTP service, or cache generated media.

Copy [the standalone GIFAnimation template]({{ '/components/templates/gif-animation/interface/GIFAnimation.py' | relative_url }}) into the consuming application's `interface/` package. There are no BMForge runtime imports. See the [engineering contract]({{ site.baseurl }}{% link pages/engineering-contract.md %}), [class classification]({{ site.baseurl }}{% link pages/classification.md %}), and [specification traceability]({{ site.baseurl }}{% link pages/specification-lifecycle.md %}). This is separate from [browser display visualization]({{ site.baseurl }}{% link pages/component-visualization.md %}): Plotly.js does not encode GIFs.

## Approved runtime modules

| Origin | Module | Purpose |
| --- | --- | --- |
| Python stdlib | `io` | In-memory GIF output via `BytesIO` |
| Python stdlib | `pathlib` | Save to an application-supplied path |
| Third-party | `PIL.Image` (**Pillow 12.3.0**) | Image snapshots, alpha composition and GIF encoding |

This is the complete implementation inventory for the GIF encoder. The consuming application's **frame-generation activity** can have its own separately approved dependencies. Do not introduce ImageMagick, FFmpeg, moviepy, browser capture packages or another encoder without owner approval and a new version of this specification. Do not modify Pillow's backend or silently change its required version. If these modules cannot meet a requirement, stop and ask the user.

## Contract

1. `GIFAnimation(width, height, loop=True, background=(255, 255, 255))` owns one independent animation. Dimensions must be positive integers; `loop` is a boolean; `background` is an RGB tuple of byte values.
2. `add_frame(image, duration_ms=...)` snapshots a Pillow `Image.Image` of **exactly** the declared dimensions. It never resizes, crops or mutates the caller's frame. A requested duration must be an integer from **10 through 600000 milliseconds**.
3. Durations are rounded to the GIF format's **10 ms** ticks by rounding **cumulative elapsed time** rather than every frame separately. For three 75 ms frames the encoded delays are 80, 70 and 80 ms. Tiny per-frame drift does not accumulate. Identical consecutive images may be merged by Pillow, preserving their combined delay.
4. Full-frame playback uses disposal method **2** (restore background before the following frame); `loop=True` writes GIF infinite-loop metadata (`loop=0`), and `loop=False` omits it.
5. Already-indexed `P` frames **without transparency** keep their palettes; this supports a fixed, application-selected chart palette. Other modes, including RGBA and transparent indexed images, are composited over `background` and encoded as opaque RGB. GIF does not preserve partial alpha. For palette-sensitive charts, create frames using a shared `P` palette; photographs can use Pillow's GIF quantization.
6. `to_bytes()` returns a complete encoded GIF suitable for an application response or for its own atomic storage layer. `save(path)` writes the complete encoding to an existing parent directory and returns `Path`. An empty animation or invalid frame raises an actionable exception; no blank GIF or fabricated output.
7. Frame storage is in memory. This contract targets bounded sequences such as short demonstrations and selected time-lapse exports, not live video or unbounded capture. The application handles retention, file ownership, atomic publication, requests and monitoring if it needs them.

## Example

```python
from PIL import Image
from yourapp.interface.GIFAnimation import GIFAnimation

animation = GIFAnimation(800, 450, loop=True, background=(16, 23, 32))
for frame_path in frame_paths:                  # Ordered by the application
    with Image.open(frame_path) as frame:
        animation.add_frame(frame, duration_ms=75)

gif_data = animation.to_bytes()                 # HTTP/storage integration owns delivery
animation.save("output.gif")                   # Or write a GIF to an existing directory
```

Frames can also be produced entirely in memory and passed directly. Use an application's activity to arrange frames, draw overlays and choose timing; do not move such domain logic into `GIFAnimation`.

## Source, provenance, and delivery

- **Application-owned template:** `components/templates/gif-animation/interface/GIFAnimation.py`. This is the canonical copy-and-adapt implementation.
- **Frozen reference:** `components/reference/snake-web-code/snakewebcode/activity/SimulationAnimation.py`, from `NadimGhaznavi/snake-web-code` commit `b4a6837169950cd3940ba53231298ce6033b75a5` (24 October 2026). Its domain rendering, manually indexed colours, 75 ms timing and GIF-byte response demonstrate real requirements. It is **not** the generic implementation and must never be imported or transplanted into another application's domain.
- **Verification:** `tests/test_gif_animation.py` checks encoding round trips, timing, loop policy, palette preservation, alpha composition, source immutability and invalid requests.
- **Optional Codex skill:** `bmforge-gif-animation`, installed using the existing pinned, opt-in component bootstrap. It packages this specification, template and local frozen example; installation creates no GIF-producing application.

## Acceptance checks

1. Encode two or more distinct full-size frames; reopen the GIF and verify order, pixel colours, dimensions, loop policy and restoration/disposal behavior.
2. Reopen non-10 ms source delays (e.g. 75 ms) and verify cumulative rounding without long-term drift, plus an explicit final-frame pause.
3. Verify `P` palette colour values are retained and later modification of the caller's source image does not change the output.
4. Verify transparent source imagery is composited onto the configured background, rather than relying on undefined GIF alpha semantics.
5. Reject empty sequences, malformed dimensions/backgrounds, wrong-sized images and invalid durations without writing a success artifact.
6. Verify both a GIF byte result and a filesystem result; ensure the destination application owns publishing and storage policy.
7. Confirm only the approved runtime modules are imported; the implementation carries `BMFORGE_COMPONENT` with ID `bmforge.gif-animation` and version `0.1.0` and imports no BMForge or Snake Web runtime module.
8. Bootstrap only the selected `bmforge-gif-animation` skill into a temporary project, including its local specification, template and reference snapshot; updates remain opt-in and notification-only.

---

[Component Blueprints]({{ site.baseurl }}{% link pages/component-blueprints.md %}) · [Back to BMForge]({{ site.baseurl }}{% link index.md %})
