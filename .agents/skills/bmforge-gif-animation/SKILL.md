---
name: bmforge-gif-animation
description: Encode application-owned Pillow image frames into looping or nonlooping GIFs with controlled timing, palettes and bytes/file output. Use for animated dashboards, demonstrations, simulation playback or time-lapse exports.
---

# GIF animation component

Read `references/specification.md` and `references/engineering-contract.md` first. Copy `assets/GIFAnimation.py` into the consuming application's `interface/` package. It is a **technical encoder**; keep chart drawing, screenshot capture, image processing, photo acquisition, overlays, scheduling and publication in application-owned activities/interfaces. The app never imports BMForge or the frozen Snake Web reference at runtime.

Use **Pillow 12.3.0** (`PIL.Image`) plus only `io` and `pathlib` for the encoder. For application-originated in-memory images or files, supply `PIL.Image.Image` frames and an integer `duration_ms`; require a fixed frame size and make a snapshot on addition. The library supports `to_bytes()` for HTTP or atomic storage layers and `save(path)` for straightforward file output; the parent directory must exist.

Preserve pre-indexed opaque `P` palettes for a stable chart palette. Other frames are composited onto the configured RGB background, then encoded. Use full-frame disposal method 2, optional infinite looping, and cumulative rounding to GIF's 10 ms ticks (75 ms frames encode as 80/70/80 ms). Do not independently round every frame, secretly resize the image, invent interpolation, or treat GIF as a video format.

The pinned Snake Web example at `references/source/snake-web-code/snakewebcode/activity/SimulationAnimation.py` shows a real animation with indexed colour rendering and cumulative time correction; **do not copy its Snake simulation business logic**. Keep the literal `BMFORGE_COMPONENT` marker `bmforge.gif-animation` spec `0.1.0` in the owning module. Run the specification's round-trip and negative acceptance checks in the destination application. This component needs no daemon, health endpoint or BMForge runtime dependency.
