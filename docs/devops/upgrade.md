# Upgrade Snake Web

Cut a release in the `snake-web-code` development checkout, then switch to root and pull the
release into a separate `snake-web-code` deployment checkout on the host. From that checkout
on `main`, run:

```sh
git pull --ff-only origin main
scripts/upgrade.sh
systemctl status snake-web.service
```

`upgrade.sh` applies the files from its own checkout using the installer:
it deploys code, updates the systemd unit, reloads systemd, and enables and
restarts the service. It also supports the first deployment. It does not fetch
or select a release itself; to deploy a specific version, check out its `vX.Y.Z`
tag before running the script. Keep this deployment checkout separate from
both `/opt/prod/snakewebcode` (installed code) and `/var/lib/snake-web/public`
(the public artifacts). This workflow also works on the development host.
Upgrades preserve `/etc/snake-web/snake-web.env`, `/etc/snake-web/database.env`, the service account's home, credentials,
public artifacts, and any legacy publishing clone. They also install the release's Python dependencies into
the deployed virtual environment and provision or repair the dedicated database
reader using its saved password. Local MariaDB root socket access is required. Configure the database and publisher as
described in [Install Snake Web](install.md) before the
first publishing run.

For the one-time switch from Git publication to Caddy, follow
[static publishing](static-publishing.md#upgrade-from-git-publication) before
upgrading. No history rewrite or source reset is part of the switch.

The upgrade removes retired report exporters, templates, and the Git publisher
from the installed application. It narrows the dedicated reader to SELECT on
`snakelab.simulation_runs`, preserving its saved password. Public artifacts, old
website checkouts, and source experiment data are not removed.
