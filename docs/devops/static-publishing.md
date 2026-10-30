# Publish static GIFs with Caddy

The publisher writes seven GIFs at most and `live.json` to
`/var/lib/snake-web/public`. Set `PUBLISH_DIRECTORY` in
`/etc/snake-web/snake-web.env` to override it. The service creates the public
directory on its first pass; its parent must already exist and be writable by
`snake-web`. Custom locations also need a systemd `ReadWritePaths` override for
the service and manual publication. Keep the directory separate from Git checkouts,
credentials, and old experiment exports.

## Website

Publish `index.md` and `assets/js/ax3l-live.js` from the separate
`snake-web` checkout using its normal GitHub Pages workflow. The homepage embeds
images from `https://snake.osoyalce.com`, reads `live.json` for available games and
the update time, and cycles through today's top five with wrapping arrow buttons.
The daily score chart appears between the game controls and the cumulative score
distribution after its first scheduled observation. `live.json` exposes the
boolean `daily_progress` flag so the page can hide an unavailable daily chart.
Subsequent experiment updates modify static files and local daily observations.

## Caddy

Public HTTPS terminates on wintermute, where DNS and router ports 80/443 point.
Its Snake site reverse-proxies to Caddy on neuromancer at `192.168.0.106:8080`.
Use [the neuromancer setup script](neuromancer-deployment.md) to install the
[LAN site block](../../systemd/Caddyfile.snake-neuromancer) as a separate imported
configuration, preserving unrelated sites. The block serves only the seven known
GIF paths and `live.json`; other paths return 404. It sets `Cache-Control: no-store` and permits
metadata requests from `https://snakeweb.osoyalce.com` through CORS.

When upgrading to daily scores, apply the updated Caddy allowlist with
`sudo scripts/deploy-neuromancer-caddy.sh --reload-only` on neuromancer.
Publish the updated homepage and navigation script through GitHub Pages.

The default service home has mode `0750`. Grant the Caddy account traversal of
that parent without making the service's private state readable. For installations
where Caddy runs as `caddy`, and with the `acl` utilities installed:

```sh
sudo setfacl -m u:caddy:--x /var/lib/snake-web
```

The public directory is `0755` and its files are `0644`. Check any additional
parent directories when choosing a custom root. Keep credentials and SSH keys
restricted. The Caddy service must be allowed to read the root by its own sandbox.

Validate the complete merged configuration before reloading it:

```sh
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

`no-store` instructs browsers and intermediary caches not to store responses.
The page also fetches metadata with `cache: 'no-store'` and gives image requests
fresh query parameters, bypassing older cached URLs. See the
[Caddy header reference](https://caddyserver.com/docs/caddyfile/directives/header)
and [HTTP cache controls](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control).

## Verification

After deployment, [publish once](push-now.md) and verify:

```sh
curl -I https://snake.osoyalce.com/game-one.gif
curl -I https://snake.osoyalce.com/daily-progress.gif
curl -I https://snake.osoyalce.com/score-distribution.gif
curl -i -H 'Origin: https://snakeweb.osoyalce.com' https://snake.osoyalce.com/live.json
```

Expect `Cache-Control: no-store`, GIF content types, and the configured CORS origin.
`game-one.gif` returns 404 when no qualifying capture exists today;
`daily-progress.gif` returns 404 before the first scheduled observation. Verify
the homepage's update time, game navigation, daily scores, and cumulative
histogram on desktop and mobile.

## Recovery

The directory's `live.json` stores the UTC ranking day, renderer version, game
identities, and update time. Keep it with the GIFs when backing up or restoring.
The lock file lives alongside the public directory, outside Caddy's root.
Daily observations live in `.public-progress.json` beside the default public
directory, with mode `0600`; a custom directory uses `.<directory-name>-progress.json`.
Keep that file with the GIFs to preserve the current day's observed animation.
It retains at most 48 observations and is replaced at the next day's first
observation. Public-write failures leave earlier observations available for retry.

Files are replaced individually. The saved game list is removed before changes
and written last, so an interrupted pass regenerates games on the next attempt.
A request during publication can briefly receive a missing metadata response;
reload after the pass completes. Stop the publisher before restoring data. Do not reset source databases as a recovery measure.
