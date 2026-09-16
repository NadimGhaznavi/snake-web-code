# Snake Web code

Python service that publishes Snake Lab scores, Ax3l experiment status, and a
saved high-score board to the
[Snake Web website](https://github.com/NadimGhaznavi/snake-web).
Application code, deployment scripts, DevOps documentation, and tests live here; website pages and
Jekyll configuration live in `snake-web`.

## Development

Run from the `snake-web-code` checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

## Deployment

Run `sudo scripts/install.sh` or `sudo scripts/upgrade.sh` from this checkout.
The installed service remains at `/opt/prod/snake-web` and publishes to a
separate `snake-web` checkout configured with `PUBLISH_CHECKOUT`.

See the [installation guide](docs/devops/install.md)
and [upgrade guide](docs/devops/upgrade.md)
for configuration and deployment details.

See [DevOps documentation](docs/devops/index.md) for all operational guides and coding guidelines.

## Static report slice

The homepage links to Experiment Highscores. Each publishing pass reads the
published CSV after synchronizing the site checkout, queries accepted scores
with a newer event ID, and appends them. The first pass exports the full accepted
score history. The browser fetches the static CSV and draws a plot with hover
and keyboard details, preserving lower scores after seed changes.

Only event ID, simulation count, score, and seed are exported. Event-log payloads
and their sanitization are outside this slice. Export, report assets, and homepage
share one publication commit; failed pushes retry without duplicating records.
The existing polling/publication triggers remain in place.

Upgrade provisioning adds SELECT access to `ax3l.experiment_highscores`.
The CSV assumes one continuous Ax3l database history with immutable accepted-score
records; replacing/resetting that database requires deliberately starting a new
export. Do not reuse an old CSV with reset event IDs.
