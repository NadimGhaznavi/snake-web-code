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
4. Renders [the LAN site template](../../systemd/Caddyfile.snake-neuromancer) as
   `/etc/caddy/snake-web.caddy` and imports it from `/etc/caddy/Caddyfile`,
   preserving other sites. The complete candidate configuration is validated first.
5. Reloads running Caddy or starts it, enables it at boot, and checks metadata
   and histogram HTTP responses on the resolved backend address and port.

The script can be rerun; it replaces the application config without duplicating
the import. It requires the default publication root and preserves publisher
environment settings, credentials, databases, artifacts, and the publisher service.
Custom roots require a reviewed configuration and corresponding permissions.
On a reload/start failure, it restores the previous Caddy files and attempts service
recovery. Package installation, ACL changes, and earlier successful steps may remain
applied after failure; inspect the reported backup directory before retrying.

## Network settings

`DSnakeWebCode.CMDB_NETWORK` declares the `http` default as
`192.168.0.106:8080`. Installation creates the non-secret, readable file
`/opt/prod/snakewebcode/conf/snakewebcode.json` from those defaults only when
missing. Reinstall, upgrade, and uninstall preserve existing settings. The Caddy
setup script also creates it if needed. For example:

```json
{
  "network": {
    "http": {"interface": "192.168.0.106", "port": 8080}
  }
}
```

JSON fields override the declaration; omitted roles and fields inherit defaults.
Explicit values stay fixed when later release defaults change. Only `network`,
the declared `http` role, and its `interface` and `port` fields are supported.
The interface must be an IPv4 address; the port must be an integer from 1 to
65535. Invalid or unreadable settings fail before Caddy changes or package work.
A missing file uses the declared defaults. No listener CLI overrides are provided.

After editing JSON, apply it from the installed release's checkout:

```sh
sudo scripts/deploy-neuromancer-caddy.sh --reload-only
```

This validates settings, regenerates the imported site, and reloads running Caddy
or starts it, without installing packages. Each invocation resolves settings once
for both Caddy and HTTP checks. Probes use loopback for a wildcard `0.0.0.0` bind.
Keep wintermute's upstream synchronized if the backend address or port changes;
the script does not update the other host. CMDB reports declared defaults, not
production JSON overrides.

## Routing and verification

By default, the backend serves HTTP on neuromancer's LAN address
`192.168.0.106:8080`. Wintermute owns public HTTPS; keep router ports 80/443 and DNS pointed there.
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
