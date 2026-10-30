# Install Snake Web

Snake Web reads Snake Lab results and captured games and writes static artifacts
for Caddy. The project owner handles production rollout.

## Prerequisites

Use Python 3 with venv support, systemd, the MariaDB client, and package download
access. Install and configure Snake Lab and Ax3l first. The existing reader
provisioner verifies the Snake Lab simulation, episode, and configuration tables
and Ax3l event, message, and high-score tables; it never creates source tables.
The new publication path reads only `snakelab.simulation_runs` and the Snake Lab
capture service. Database access remains read-only.

Confirm the intended production host and source before installation. Use restored,
isolated data for development; do not point verification at live experiments.

## Install

From a separate deployment checkout of `snake-web-code`, run as root:

```sh
scripts/install.sh
systemctl status snake-web.service
journalctl -u snake-web.service
```

The installer creates the `snake-web` account with home `/var/lib/snake-web` and
shell `/bin/bash`, installs code and dependencies at `/opt/prod/snakewebcode`,
provisions a dedicated local MariaDB reader, and enables and starts the service.
Reinstallation restarts it. Code is owned by root; the service runs as `snake-web`.
Upgrades preserve configuration, credentials, and publication data.

Root-only configuration lives under `/etc/snake-web` (directory mode `0700`):

- `database.env`: managed reader credentials, mode `0600`. Provisioning reuses the
  saved password and repairs only the dedicated reader's SELECT grants.
- `snake-web.env`: publication settings, mode `0600`, preserved on upgrade.

The existing provisioner grants SELECT on `snakelab.simulation_runs`,
`snakelab.simulation_episodes`, `snakelab.configurations`, `ax3l.events`,
`ax3l.event_messages`, and `ax3l.experiment_highscores`. It does not alter source
schemas or application accounts. If provisioning fails, code may already have
been copied; inspect the failure before retrying.

## Configure publication

```ini
PUBLISH_DIRECTORY=/var/lib/snake-web/public
SNAKE_LAB_ENDPOINT=tcp://127.0.0.1:41970
```

The ZMQ endpoint is optional when using the default. Prepare the one-time website
change, Caddy site block, and filesystem permissions using
[static publishing](static-publishing.md). Caddy configuration and production
reloads are separate from installation. No Git checkout or GitHub credentials
are required by the publisher.

The systemd service can write under `/var/lib/snake-web`. Custom locations need
a `ReadWritePaths` override and a corresponding adjustment to manual publication.
After configuration changes, restart the service and inspect its log. Scheduled
publication runs at the next hour or half hour. Use
[Publish immediately](push-now.md) for an immediate pass.

## Development verification

From the development checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Tests use temporary files, disposable Git repositories for retained legacy
helpers, and simulated system services. Optional database tests require an
isolated MariaDB instance under a `/tmp/snake-web-*` socket; set
`SNAKE_WEB_TEST_DB_SOCKET` to enable them. Reader-provisioning tests additionally
require `SNAKE_WEB_PROVISION_TEST_SOCKET`. Never use production databases for these
tests. A foreground `python -m snakewebcode.server --once` uses the configured
source and writes real artifacts, so use a temporary `PUBLISH_DIRECTORY` in DEV.
