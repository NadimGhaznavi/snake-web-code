# Install Snake Web

Snake Web reads Snake Lab simulations and Ax3l experiment events, generates
`index.md` at the root of the dedicated publishing clone, and
commits and pushes the page when its content changes. It runs immediately on
startup and then waits `DSnakeWeb.POLL_INTERVAL` seconds between checks
(currently 300 seconds). It pushes when the generated page changes or a previous homepage
commit still needs to be pushed. It opens no listening ports.

The host needs Python 3.10 or newer with `venv` support, Git, and systemd.
On Debian, install `python3-venv`, `git`, and `mariadb-client` first. MariaDB
must already be running locally with the Snake Lab schema (including
`simulation_runs.high_score_snapshot`) and the `ax3l.events` and
`ax3l.event_messages` tables installed, and root
must be able to administer it through its Unix socket without a password. The installer creates a
virtual environment under `/opt/prod/snake-web/venv` and installs the PyMySQL
dependency from `requirements.txt`; this requires package download access.

Application code, scripts, and tests live in the
[snake-web-code repository](https://github.com/NadimGhaznavi/snake-web-code).
Run the installer from the root of that checkout:

```sh
sudo scripts/install.sh
systemctl status snake-web.service
journalctl -u snake-web.service
```

It creates the `snake-web` system account with a `/bin/bash` shell, prepares its
home with mode `0750`, and creates the root-owned daemon code directory. On
reinstall, it checks the existing account's home, shell, and primary group and
preserves account data. Existing accounts using `/usr/sbin/nologin` are migrated
to `/bin/bash`. It copies daemon code and installs, enables, and starts
`snake-web.service`, restarting it on reinstall. It provisions the dedicated
Snake Web database reader; GitHub credential setup remains separate.

The service starts at boot.

## Production configuration

Install and upgrade automatically create Snake Web's own MariaDB account,
`snake_web_reader@localhost`, with a generated password and only `SELECT` on
`snakelab.simulation_runs`, `ax3l.events`, and `ax3l.event_messages`. They discover the local MariaDB socket using the
`mariadb` client and perform provisioning with local root access. They never
reuse or modify the Snake Lab or Ax3l application accounts and never create or
migrate the source database schema.

Credentials are stored at **`/etc/snake-web/database.env`**, owned by `root:root`
with mode `0600` in `/etc/snake-web/` (created with mode `0700`). The file contains `DB_HOST`, `DB_SOCKET`, `DB_NAME`, `DB_USER`, and
`DB_PASSWORD`; systemd loads it for the service, so the service account does not
need direct read access. The DAL also uses a read-only transaction.

For existing installations, install and upgrade copy a validated Snake Web-managed
`/etc/snake-lab/database.env` into the new location when the new file is absent,
preserving the password. The old file is left in place; the service uses the new
file. Unrelated or invalid legacy files are rejected without modification.

Upgrades preserve the generated password and reapply the dedicated account's
SELECT-only privileges. A missing account can be recreated from its saved
credentials. If the environment file belongs to another application, or the
reader account exists without a Snake Web-managed credential file, provisioning
stops without taking it over. Keep this file when moving or restoring the
service. A socket-path mismatch also stops provisioning for inspection.

The installer creates `/etc/snake-web/snake-web.env`, owned by `root:root` with
mode `0600`, using the following defaults. Edit it as root for your publishing
setup. Reinstall and upgrade preserve the existing file. If only the former
`/etc/snake-web.env` exists, its settings are copied to the new location and the
old file is left in place.


```ini
PUBLISH_CHECKOUT=/var/lib/snake-web/site
PUBLISH_BRANCH=main
GIT_SSH_COMMAND="ssh -i /var/lib/snake-web/.ssh/id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/var/lib/snake-web/.ssh/known_hosts"
```

Remove any old `DB_*` entries from `/etc/snake-web/snake-web.env`; the managed database
file is loaded afterward and supplies the database configuration. Both files
are preserved during upgrades and uninstallation. Uninstallation also preserves
the reader account and grants.

Set up the dedicated clone and SSH credentials as described in
[Git Access](git-access.md). The configured branch must
already contain `index.md` at its root (normally `/var/lib/snake-web/site/index.md`)
as a tracked file. Its existing contents may be empty or arbitrary: the daemon
replaces the complete page with generated Jekyll front matter and a responsive
Current Experiment panel. The panel shows the daemon host name, all-time high
score, current golden configuration score, simulation count, completed experiment
cycles, three report names as plain text, and the current golden configuration’s
saved board as an inline SVG. No extra website assets are required.

All-time high score and simulation count cover every `simulation_runs` row.
The current score and snapshot come from the run referenced by the latest
`golden_config_created` event, matching the report server. Cycles count completed
ordered round-robin passes from Ax3l checkpoints and comparisons, ignoring
duplicate comparisons and incomplete passes. Missing current scores display
`—`; missing or invalid boards display an explanatory message. The page is
published when any displayed content changes, even if the all-time score does
not. Upgrading adds the two event-table SELECT grants to the existing reader.

After configuring the service, run `sudo systemctl restart snake-web.service`
and inspect `journalctl -u snake-web.service`. Missing configuration or publishing
failures are logged and retried on the next interval.

## DEV validation on Sally

Production is a separate host running the live Ax3l and Snake Lab systems.
Use restored backups and temporary Git repositories for DEV validation.
Run the following commands from the `snake-web-code` checkout.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

The Git tests create temporary repositories and local bare remotes. To also
exercise the real DAL and one-shot command, restore the supplied Snake Lab dump
into an isolated MariaDB instance, including the Snake Lab snapshot column
and Ax3l event tables, then run:

```sh
SNAKE_WEB_TEST_DB_SOCKET=/tmp/snake-web-slice-db.sock \
  SNAKE_WEB_TEST_EXPECTED_SCORE=49 \
  .venv/bin/python -m unittest discover -s tests -v
```

This optional test expects the isolated instance to allow local `root` access
without a password. It verifies that a write is rejected by the read-only
transaction, then queries the backup and publishes only to a temporary local
remote. The September 14, 2026 Snake Lab backup contains 110 runs and a high
score of 49. Adjust the expected score when testing another backup.

For a configured foreground run, use `.venv/bin/python -m snake_web.server --once`.
It requires the `DB_*` values from the managed database file and the Git
settings in its environment, performs an actual status commit and
push, and exits nonzero on failure. Omitting `--once` runs the periodic service.
A missing score preserves the existing page; zero is a valid score.

To test provisioning itself, add
`SNAKE_WEB_PROVISION_TEST_SOCKET=/tmp/snake-web-slice-db.sock` to the test command.
Use only the isolated test instance: these tests create and remove the
`snake_web_reader` account there and verify that its access is restricted. They
write credential files only in temporary directories. They refuse to start if
that instance already contains a `snake_web_reader` account.
