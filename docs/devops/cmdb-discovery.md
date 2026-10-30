# CMDB discovery

Install or [upgrade](upgrade.md) Snake Web, then use CMDB's **Add Application**
with the exact name `SnakeWebCode`. The standard scanner reads:

```text
/opt/prod/snakewebcode/snakewebcode/constants/DSnakeWebCode.py
```

CMDB parses literal declarations without importing or running the application.
The required `DSnakeWebCode.VERSION` identifies the installed release. Development
checkouts and the separate `snake-web` website repository are not discovery targets.

| Declaration | Value |
| --- | --- |
| `CMDB_TYPE` | `Application` |
| `CMDB_SUBTYPE` | `Website Publisher` |
| `CMDB_SUPPLIER` | `Nadim-Daniel` |
| `CMDB_CODENAME` | Release message, maintained by the release script |
| `CMDB_COMPONENTS` | `Public Artifacts` at `/var/lib/snake-web/public` |
| `CMDB_DATABASES` | `Snake Lab` → `snakelab`; `Ax3l` → `ax3l` |
| `CMDB_NETWORK` | Empty tuple; the publisher opens no listeners |

The filesystem component contains the public GIFs and live metadata. Its literal
path must agree with `PUBLISH_DIRECTORY`; discovery does not read environment
overrides or check that the directory exists. Adjust the declaration before
deployment if choosing a custom root.

Directory backups run as `cmdbagent`, which needs read access to the declared
directory and traversal access through its parents. The default service home is
mode `0750`, so declaring the component alone does not enable backups. Configure
access for the public directory if using CMDB backups; keep SSH keys and
credential files restricted. The declaration excludes the service's `.ssh` directory
and `/etc/snake-web` configuration.

Database references match exact catalog names on the application's host through
the default local MariaDB socket. They do not create databases or alter Snake Web's
read-only grants. The Snake Lab ZMQ endpoint and MariaDB connection
are outbound dependencies and are not network listeners.

Use **Re-Scan Applications** on the inventoried host. Verify the version,
classification, codename, public directory, and both database references.
Expect no listener rows for SnakeWebCode. A missing file, unreadable file, or invalid
version prevents detection; check the installation path and agent access first.
