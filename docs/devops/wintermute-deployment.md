# One-time wintermute deployment

This is the former single-host setup, with publisher and Caddy both on wintermute.
For the current publisher on neuromancer behind wintermute's reverse proxy, use
[the neuromancer deployment](neuromancer-deployment.md) instead. Do not run this
script for the two-host setup.

Configure Snake Web's Caddy site on wintermute after installing the static
publisher. The script preserves MyCount's existing Caddy site and uses the
host's current port 80/443 router mappings.

Copy or commit/pull the reviewed script and `systemd/Caddyfile.snake` into the
deployment checkout on wintermute. From that checkout, run:

```sh
sudo scripts/deploy-wintermute-caddy.sh
```

The script requires wintermute, root, the installed static publisher, and running
Caddy and Snake Web services. It does not install a release or provision databases.
It:

1. Saves the home-directory ACL and configuration backups under
   `/var/backups/snake-web-caddy.*`.
2. Creates `/var/lib/snake-web/public`, granting Caddy traversal of the private
   parent without granting it access to the other contents.
3. Validates the combined Caddy configuration, installs `snake-web.caddy`, and
   adds its import alongside MyCount's import. It follows MyCount's direct
   `caddy reload` approach. A failed reload restores the Caddy configuration files.
4. Sets `PUBLISH_DIRECTORY`, restarts Snake Web, and publishes once immediately.
5. Checks that Caddy can read the metadata and histogram.

MyCount's files, services, router mappings, database credentials, and saved
publication data are preserved. If a later step fails, the script exits nonzero and
reports the backup directory; earlier successful steps remain applied.

Check certificate issuance in the Caddy journal and verify:

```sh
curl -I https://snake.osoyalce.com/score-distribution.gif
curl -i -H 'Origin: https://snakeweb.osoyalce.com' https://snake.osoyalce.com/live.json
```

Expect `Cache-Control: no-store` and the website's CORS origin. A missing game GIF
is normal when no qualifying captures exist today. The one-time website update
is a separate GitHub Pages publication; this script does not push repositories.
See [static publishing](static-publishing.md) for the page and artifact contract.
