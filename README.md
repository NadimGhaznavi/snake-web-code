# SnakeWebCode

Python service that writes today's top five captured Snake games, animated daily
scores, and a cumulative score distribution to static files served by Caddy at
`https://snake.osoyalce.com`.
The [Snake Web website](https://github.com/NadimGhaznavi/snake-web) contains the
maintained page and navigation script; routine experiment updates never use Git.

## Development

Read the [Coding Guidelines](pages/coding-guidelines.md) before making changes.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

## Publication

The service publishes on the hour and half hour, starting at the next boundary
after startup. `--once` publishes immediately using the same selection and renderer.
Set `PUBLISH_DIRECTORY` (default `/var/lib/snake-web/public`) to the Caddy document
root. See [static publishing](docs/devops/static-publishing.md) for the one-time
website and Caddy setup, permissions, and cache controls.

Games are named `game-one.gif` through `game-five.gif`. Only simulations completed
on the source database's current UTC day qualify, ordered by high score descending
and numeric simulation ID ascending for ties. Unscored, incomplete, and legacy
SVG-only games are excluded; zero scores qualify. If fewer than five captures
exist, only those files are published. Midnight UTC starts a new ranking on the
next publication pass; there is no backfill from earlier days.

Game drawing follows Ax3l, using the BMForge GIF encoder with Pillow 12.3.0,
including its labels and digestion effect,
75 ms moves, and one-second final pause. Capture retrieval uses Snake Lab's
version-1 `simulation.highscore_frames` ZMQ contract. Configure `SNAKE_LAB_ENDPOINT`
if it differs from `tcp://127.0.0.1:41970`.

Unchanged games reuse their saved GIFs, including after restarts and rank changes.
During capture-service outages, available cached leaders for the current day remain
published; missing captures are retried on the next pass. Renderer upgrades
regenerate captures. The publisher removes unused game slots, locks concurrent
publication, and replaces each file atomically. It invalidates `live.json` before changing
slots and writes it last, so an
interrupted write triggers fresh rendering on the next pass.
A failed pass returns nonzero with `--once` or logs an error and retries later.
Unchanged publications retain the existing files and update time.

`daily-progress.gif` shows the day's top ten completed simulation scores as
ascending bars, including zero scores and runs without saved game captures.
Scheduled passes collect one observation per UTC half-hour, without backfilling
missed observations. Frames last two seconds, with a five-second final pause;
axes stay fixed and frame timestamps display Toronto time. Midnight UTC closes
the preceding day; 00:30 UTC starts the new chart. Only the current chart's
observations are retained, up to 48, in `.public-progress.json` alongside the
default public directory. Manual `--once` passes reuse those observations and
can regenerate a missing GIF; before the first scheduled observation, the daily
chart is absent.

`score-distribution.gif` uses Ax3l's Pillow renderer: an empty plot, cumulative
checkpoints every 500 simulation IDs for two seconds each, then all simulations
for five seconds. The final distribution fixes both axes for every frame. Missing
IDs retain their checkpoint boundaries; null scores count as submitted but have
no bars, and zero is scored. The histogram includes the whole experiment, including
current scores for runs still in progress. Each pass renders the current
distribution; identical bytes are left untouched.

The minimal website displays **Ax3l Live**, **LLM configured Snake AI**, the latest
publication time in Toronto (`YYYY-MM-DD HH:MM`), one game with wrapping arrows,
the daily score chart, and the cumulative histogram, in that order. Reload to
refresh. The page fetches `live.json` without caching;
GIF responses use `Cache-Control: no-store`. Zero games leave an empty viewer;
one game disables both arrows. Images retain their natural size and shrink on
narrow screens. No database, Python server, or Git push serves browser requests.

## Deployment

Run `sudo scripts/install.sh` or `sudo scripts/upgrade.sh` from a deployment
checkout. The installed service lives at `/opt/prod/snakewebcode`.

See [DevOps documentation](docs/devops/index.md) for installation, upgrade,
publication, and CMDB discovery. The project owner handles production rollout.
Upgrades replace the installed Python package and preserve configuration,
credentials, and publication data. The dedicated database reader has SELECT
access only to `snakelab.simulation_runs`.
