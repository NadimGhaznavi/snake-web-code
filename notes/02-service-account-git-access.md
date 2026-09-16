# Service account Git access

The publisher needs Git installed, write access to its checkout (including
`.git`), a Git commit identity, and unattended SSH authentication to GitHub.
The `snake-web` service account uses `/bin/bash` for interactive administration.

Use a dedicated production clone owned by the service account. Keep the
development checkout at `/opt/dev/snake-web` separate so publishing cannot
accidentally commit development work or change a developer's active branch.
The examples below assume an account and group named `snake-web`, a home at
`/var/lib/snake-web`, and a production clone at `/var/lib/snake-web/site`.
The daemon code lives separately in `/opt/prod/snake-web`, owned by `root:root`
with mode `0755`, so the service account can read and execute it. The current
`snake_web.server` service only waits for shutdown; publishing is not yet
implemented.

## Root-run installation

Run the installer from the project root:

```sh
sudo scripts/install.sh
```

It creates the `snake-web` system account with a `/bin/bash` shell, prepares its
home with mode `0750`, and creates the root-owned daemon code directory. On
reinstall, it checks the existing account's home, shell, and primary group and
preserves account data. Existing accounts using `/usr/sbin/nologin` are migrated
to `/bin/bash`. It copies daemon code and installs, enables, and starts
`snake-web.service`, restarting it on reinstall. Python 3 and a running systemd
system are required. It does not configure GitHub credentials.

For later releases, pull the desired release into the root-managed deployment
checkout and run `scripts/upgrade.sh` as root. The upgrade script uses this same
installation path to update code and the unit and restart the service, while
preserving the service account's home, credentials, and publishing clone.

Run Git and key
generation as `snake-web`, even though installation runs as root, so the account
owns the resulting files. Complete GitHub credential setup and check access
before enabling automated publishing.

## Uninstallation

Run from the project root:

```sh
sudo scripts/uninstall.sh
```

This stops and disables the service, removes its systemd unit, and removes
`/opt/prod/snake-web` and its contents. It preserves the `snake-web`
account and group, its home at `/var/lib/snake-web`, SSH credentials, the
publishing clone, and the development checkout. It can be rerun after removal.

## SSH credentials

After creating the service account and its home, run as an administrator:

```sh
sudo install -d -m 0700 -o snake-web -g snake-web /var/lib/snake-web/.ssh
sudo -u snake-web ssh-keygen -t ed25519 -N '' \
  -C snake-web-publisher -f /var/lib/snake-web/.ssh/id_ed25519
```

Generate the key once; do not overwrite an existing key. Add the `.pub` file to
the `NadimGhaznavi/snake-web` repository under **Settings → Deploy keys**, with
**Allow write access** enabled. GitHub documents this in
[Managing deploy keys](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys).
Keep the private key outside the checkout, readable only by the service account.

Populate `/var/lib/snake-web/.ssh/known_hosts` with GitHub's verified SSH host
keys, using [GitHub's published fingerprints](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints)
to verify them. Ensure the service account can read the file.

Use this SSH command for setup and as `GIT_SSH_COMMAND` in the service:

```sh
export GIT_SSH_COMMAND='ssh -i /var/lib/snake-web/.ssh/id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/var/lib/snake-web/.ssh/known_hosts'
sudo -u snake-web env GIT_SSH_COMMAND="$GIT_SSH_COMMAND" \
  git clone --branch main git@github.com:NadimGhaznavi/snake-web.git /var/lib/snake-web/site
sudo -u snake-web git -C /var/lib/snake-web/site config user.name 'Snake Web Publisher'
sudo -u snake-web git -C /var/lib/snake-web/site config user.email 'snake-web@localhost'
```

The email is an example commit identity; replace it with the intended publisher
identity. Branch rules must permit that credential to push to the publishing
branch. Configure GitHub Pages to deploy from that branch or its associated
workflow.

## systemd settings

When publishing is implemented, add the Git environment settings below to the
service. Keep its working directory at `/opt/prod/snake-web` so Python can find
the installed module, and use `git -C /var/lib/snake-web/site` for Git commands.
The installed unit already sets the account, home, and filesystem protections;
`StateDirectory=snake-web` makes `/var/lib/snake-web` writable by the service.

```ini
[Service]
User=snake-web
Group=snake-web
WorkingDirectory=/opt/prod/snake-web
Environment=HOME=/var/lib/snake-web
Environment=GIT_TERMINAL_PROMPT=0
Environment="GIT_SSH_COMMAND=ssh -i /var/lib/snake-web/.ssh/id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/var/lib/snake-web/.ssh/known_hosts"
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/snake-web/site
```

`ReadWritePaths` allows writes through systemd's filesystem protection; normal
filesystem ownership and permissions must also allow them. Outbound networking
must allow SSH to GitHub. Reload systemd and restart the service after updating
its unit.

If the service must share an existing checkout owned by another account, grant
write access to both its worktree and Git directory through a shared group or
ACLs, including inherited access for new files. Also add that exact checkout
path to the service account's global `safe.directory` configuration. This Git
trust setting does not grant filesystem permissions. A service-owned clone
does not need this exception.

## Verify publishing

Using the same `GIT_SSH_COMMAND` as above:

```sh
sudo -u snake-web env GIT_SSH_COMMAND="$GIT_SSH_COMMAND" GIT_TERMINAL_PROMPT=0 \
  git -C /var/lib/snake-web/site push --dry-run origin HEAD:main
```

The dry run checks the connection and proposed push without publishing. An
actual status commit and push are still needed to verify branch rules, the
service's sandbox, and the Pages deployment end to end.

Serialize updates to the publishing clone. Stage only the intended generated
status files, commit when they change, and push explicitly to the publishing
branch. Handle remote updates before retrying a rejected push; do not force-push.
