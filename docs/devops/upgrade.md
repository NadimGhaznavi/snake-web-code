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

Upgrades install the release's Python dependencies and provision or repair the
dedicated database reader using its saved password. Local MariaDB root socket
access is required. Once provisioning succeeds, the installer replaces the
installed Python package with the release's files, removing unused application
files. It preserves `/etc/snake-web`, the service account's home, credentials,
and public artifacts. The reader has SELECT access only to
`snakelab.simulation_runs`.

Configure the database and publisher as described in [Install Snake Web](install.md)
and prepare [Caddy access](static-publishing.md) before the first publishing run.
