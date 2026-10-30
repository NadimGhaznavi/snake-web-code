# Publish immediately

From the `snake-web-code` checkout:

```sh
sudo scripts/push-now.sh
```

The script runs the installed code as `snake-web`, using configuration from
`/etc/snake-web`, and returns its exit status. It refreshes today's top five games,
the whole-experiment score distribution, and `live.json` in the public directory.
It reuses saved daily score observations without adding a new sample, regenerating
the daily GIF if needed. The daily chart first appears after a scheduled pass.
It does not commit or push anything. Unchanged artifacts retain their saved bytes
and update time. Scheduled publication remains running; if another pass holds the
lock, rerun after it finishes.

[Upgrade first](upgrade.md) to publish using changes from this checkout. See
[static publishing](static-publishing.md) for Caddy setup and verification.
