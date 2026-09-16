# Start a fresh published experiment

Use `scripts/reset-site.py` from the snake-web-code checkout to clear the
**snake-web website repository's generated experiment data** before moving to a
new source database. The script uses standard Python only.

It replaces `index.md` with a waiting-for-publication placeholder and removes
all daemon-managed report HTML/JavaScript, CSV histories, and export cursors.
It preserves `.git`, `_config.yml`, `CNAME`, other pages, credentials, and source
databases. Old published data remains in Git history; this is not a history purge.

Stop the old machine's publishing daemon first:

```sh
sudo systemctl stop snake-web.service
```

Keep it stopped throughout the migration. Disable it if the old machine will
remain in service so a reboot does not restart publication:

```sh
sudo systemctl disable snake-web.service
```

Run the reset as the publishing checkout's owner. The following examples use
the production defaults; substitute the actual `PUBLISH_CHECKOUT` and pass
`--branch BRANCH` if it is not `main`.

Preview without changing files, fetching, committing, or pushing:

```sh
sudo -u snake-web python3 scripts/reset-site.py /var/lib/snake-web/site
```

Apply, commit, and publish the reset:

```sh
sudo -u snake-web python3 scripts/reset-site.py /var/lib/snake-web/site --apply --push
```

Omit `--push` to inspect the local reset commit first. Rerun with `--apply --push`
to publish it; this also retries a failed push without creating a duplicate
reset commit. The script takes the daemon's checkout lock, requires a clean
website repository, synchronizes the publishing branch, and never force-pushes.
Unrelated pending commits or diverged history must be reconciled first.

On the new production machine, prepare the publishing checkout with the pushed
reset commit (a fresh clone will do), then follow the normal installation
instructions with the new source MariaDB. The installer starts the daemon, so
the reset checkout must be ready before installation. Do not copy the old CSVs
or cursors back into that checkout. Only one machine should publish to this branch. The daemon will rebuild all reports from
the new database; until a score exists, the placeholder remains visible.

If you reset a development clone instead, use its owner and path in the commands.
Do not point this script at the snake-web-code repository.
