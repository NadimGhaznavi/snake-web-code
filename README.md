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
