# Git Access

The publisher needs Git installed, write access to its checkout (including
`.git`), a Git commit identity, and unattended SSH authentication to GitHub.
The `snake-web` service account uses `/bin/bash` for interactive administration.

Use a dedicated production clone owned by the service account. Keep the
development checkout at `/opt/dev/snake-web` separate so publishing cannot
accidentally commit development work or change a developer's active branch.
The examples below assume an account and group named `snake-web`, a home at
`/var/lib/snake-web`, and a production clone at `/var/lib/snake-web/site`.
The daemon code lives separately in `/opt/prod/snake-web`, owned by `root:root`
with mode `0755`, so the service account can read and execute it.

GitHub credential setup is separate from installation. Run Git and key
generation as `snake-web`, even though installation runs as root, so the account
owns the resulting files. Complete credential setup and check access before
enabling automated publishing.

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

Set `GIT_SSH_COMMAND` and `PUBLISH_CHECKOUT` in `/etc/snake-web/snake-web.env` as shown in
[Install Snake Web](install.md). The installed unit
sets the service account, home, and `GIT_TERMINAL_PROMPT=0`, and reads that file.
Its working directory is `/opt/prod/snake-web`; the publisher runs Git in the
configured publishing clone.

`StateDirectory=snake-web` makes `/var/lib/snake-web` writable within the service's
filesystem protections. Keep the clone there, owned by `snake-web`. A clone at
another location also needs an appropriate systemd `ReadWritePaths` override.
Outbound networking must allow SSH to GitHub. Restart the service after editing
its environment file.

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

## Publisher behavior and recovery

The publisher locks its clone, requires a clean worktree on `PUBLISH_BRANCH`,
fetches that branch from `origin`, and fast-forwards to remote changes before
generating the homepage and reports. It stages only `index.md`,
`reports/experiment-highscores.html`, `reports/experiment-highscores.js`, and
`reports/data/experiment-highscores.csv`, `reports/score-distribution.html`,
`reports/score-distribution.js`, `reports/data/run-scores.csv`,
`reports/golden-configurations.html`, `reports/golden-configurations.js`, and
`reports/data/golden-configurations.csv`, `reports/event-log.html`,
`reports/event-detail.html`, `reports/event-log.js`, `reports/report-csv.js`,
`reports/data/events.csv`, `reports/data/event-simulations.csv`, and
`reports/data/event-export.json`, committing
all changed files together. It never
force-pushes.

If a push fails, the status commit remains locally and is retried on the next
pass, even when the score is unchanged. Pending commits are accepted only when
each changes only these managed files. A dirty checkout, unrelated pending commit,
or diverged history stops that pass and logs an error. Stop the service, inspect
and reconcile the publishing clone, then restart it. A commit failure can leave
the generated page staged and likewise requires inspection.

The project owner handles code check-ins and releases. Automated commits belong
only to the dedicated status publishing clone; DEV tests use temporary local
remotes. Fetch and incorporate production status commits into the release
branches before cutting subsequent releases so the release push can succeed.
