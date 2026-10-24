# Uninstall Snake Web

Run from the project root:

```sh
sudo scripts/uninstall.sh
```

This stops and disables the service, removes its systemd unit, and removes
`/opt/prod/snakewebcode` and its contents. It preserves the `snake-web`
account and group, its home at `/var/lib/snake-web`, SSH credentials, the
publishing clone, `/etc/snake-web/snake-web.env`, `/etc/snake-web/database.env`, the
dedicated database reader account and grants, and the development checkout. It can be rerun after removal.

An old `/opt/prod/snake-web` directory retained from the
[installation-path migration](upgrade.md#upgrading-from-optprodsnake-web) is left
untouched; remove it separately when it is no longer needed.
