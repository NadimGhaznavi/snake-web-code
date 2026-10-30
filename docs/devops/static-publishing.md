# Publish static GIFs with Caddy

The publisher writes six GIFs at most and `live.json` to
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
Subsequent experiment updates modify only the Caddy-served files.

## Caddy

Keep the dynamic DNS mapping and inbound ports 80/443 pointed at the production
host. Merge [the supplied site block](../../systemd/Caddyfile.snake) into the
existing Caddy configuration, adapting its root if necessary. Do not replace
unrelated site blocks. The block serves only the six known GIF paths and
`live.json`; other paths return 404. It sets `Cache-Control: no-store` and permits
metadata requests from `https://snakeweb.osoyalce.com` through CORS.

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
sudo systemctl reload caddy
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
curl -I https://snake.osoyalce.com/score-distribution.gif
curl -i -H 'Origin: https://snakeweb.osoyalce.com' https://snake.osoyalce.com/live.json
```

Expect `Cache-Control: no-store`, GIF content types, and the configured CORS origin.
`game-one.gif` returns 404 when no qualifying capture exists today. Verify the
homepage's update time, game navigation, and histogram on desktop and mobile.

## Recovery

The directory's `live.json` stores the UTC ranking day, renderer version, game
identities, and update time. Keep it with the GIFs when backing up or restoring.
The lock file lives alongside the public directory, outside Caddy's root.

Files are replaced individually. The saved game list is removed before changes
and written last, so an interrupted pass regenerates games on the next attempt.
A request during publication can briefly receive a missing metadata response;
reload after the pass completes. Stop the publisher before restoring data. Do not reset source databases as a recovery measure.
