# Set up Caddy on neuromancer

Run this manual release step on neuromancer after installing Snake Web and
publishing artifacts to `/var/lib/snake-web/public`. From the release checkout:

```sh
sudo scripts/deploy-neuromancer-caddy.sh
```

The script requires root, the `neuromancer` hostname, a running publisher,
its existing metadata and histogram, and Debian package download access. It:

1. Installs `caddy`, `acl`, and `curl` using APT.
2. Saves the current Caddy files and service-home ACL under
   `/var/backups/snake-web-caddy.*`.
3. Grants `caddy` traversal of `/var/lib/snake-web` and verifies that it can read
   the artifacts without opening the service's private state.
4. Installs [the LAN site](../../systemd/Caddyfile.snake-neuromancer) as
   `/etc/caddy/snake-web.caddy` and imports it from `/etc/caddy/Caddyfile`,
   preserving other sites. The complete candidate configuration is validated first.
5. Reloads running Caddy or starts it, enables it at boot, and checks metadata
   and histogram HTTP responses on `192.168.0.106:8080`.

The script can be rerun; it replaces the application config without duplicating
the import. It requires the default publication root and leaves publisher
configuration, credentials, databases, artifacts, and the publisher service untouched.
Custom roots require a reviewed configuration and corresponding permissions.
On a reload/start failure, it restores the previous Caddy files and attempts service
recovery. Package installation, ACL changes, and earlier successful steps may remain
applied after failure; inspect the reported backup directory before retrying.

## Routing and verification

The backend serves HTTP bound to neuromancer's LAN address `192.168.0.106`, port
8080. Wintermute owns public HTTPS; keep router ports 80/443 and DNS pointed there.
Its `/etc/caddy/snake-web.caddy` should contain:

```caddyfile
snake.osoyalce.com {
    reverse_proxy 192.168.0.106:8080
}
```

From wintermute, verify the backend and public route:

```sh
curl -i --max-time 15 http://192.168.0.106:8080/live.json
curl -I --max-time 15 https://snake.osoyalce.com/score-distribution.gif
curl -i --max-time 15 -H 'Origin: https://snakeweb.osoyalce.com' https://snake.osoyalce.com/live.json
```

Expect HTTP 200, `Cache-Control: no-store`, and
`Access-Control-Allow-Origin: https://snakeweb.osoyalce.com`.
If a host firewall filters the LAN connection, allow wintermute to reach port
8080; the script does not modify firewall rules or wintermute.
The [GitHub Pages homepage](static-publishing.md#website) is published separately.
