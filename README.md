# Snake Web code

Python service that reads Snake Lab scores and publishes updates to the
[Snake Web website](https://github.com/NadimGhaznavi/snake-web).
Application code, deployment scripts, and tests live here; website pages and
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

See the [installation guide](https://github.com/NadimGhaznavi/snake-web/blob/main/pages/devops/install.md)
and [upgrade guide](https://github.com/NadimGhaznavi/snake-web/blob/main/pages/devops/upgrade.md)
for configuration and deployment details.
