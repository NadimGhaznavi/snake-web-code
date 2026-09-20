# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed

- Wording on the *score distribution page*.

## [2.3.0] - 2026-09-20 @ 16:58

### Changed

- Match Ax3l’s cumulative score distribution groups: all runs, oldest two-thirds, and oldest third, with shared bins, matching colors, and counts in hover and keyboard details.

## [2.2.0] - 2026-09-19 @ 15:24

### Added

- Link to the About page from the generated homepage.

## [2.1.5] - 2026-09-17 @ 05:49

### Changed

- Update the Score Distribution introduction to “This chart shows how many times a score was achieved by the Ax3l AI.”
- Combine simulation counts and color descriptions into one bullet list, with colors after counts, and rename “First-half simulations run” to “Oldest half simulations run”.

## [2.1.4] - 2026-09-17 @ 05:38

### Changed

- Simplify the Score Distribution explanation to “This chart shows the score distribution.” with “All simulations: Blue” and “Oldest half: Orange” bullets.

## [2.1.3] - 2026-09-17 @ 05:28

### Changed

- Move Score Distribution totals below the chart explanation as separate “All simulations run” and “First-half simulations run” bullets.
- Mark seed changes with purple points on Experiment Highscores, with a color explanation and seed-change hover details.
- Explain Experiment Highscores as the score the Ax3l AI is trying to beat, with italicized wording describing random seed changes and lucky highscores.

## [2.1.0] - 2026-09-16 @ 21:14

### Changed

- Restyle Golden Configurations as a column of matching report boxes. Replace Configuration run with Config and JSON links; replace expandable reasons with Thoughts links. Both open detail pages with a Back link, and configuration exports include golden baselines.

## [2.0.1] - 2026-09-16 @ 20:51

### Changed

- Place Back on the left and Download CSV on the right of the same footer row on Score Distribution and Experiment Highscores.

## [2.0.0] - 2026-09-16 @ 20:45

### Added

- Add Ax3l's Thinking beneath Experiment Highscores, displaying saved LLM reasoning for the same ranked simulations as Top 100, with matching navigation and publication timing.

## [1.6.2] - 2026-09-16 @ 20:36

### Changed

- Use matching stacked boxes for the Score Distribution and Experiment Highscores pages, with Download CSV and Back links below the chart. Shorten the histogram title to Score Distribution.
- Give Top 100 a boxed Back link and styled previous/next buttons below the board, preserving wrapping navigation.

## [1.6.0] - 2026-09-16 @ 20:20

### Added

- Add Top 100 as the first report link, with saved simulation boards ranked by high score and wrapping previous/next navigation below each board.

### Changed

- Remove the Reports heading and extra spacing between homepage report links.

## [1.5.2] - 2026-09-16 @ 20:04

### Changed

- Match the reports and publication footer to the snake snapshot box, using the same centered responsive width, border, background, and padding.

## [1.5.1] - 2026-09-16 @ 19:59

### Added

- Add `scripts/push-now.sh` to publish immediately with the installed application and service credentials, showing output and returning the publication's exit status without changing the schedule.

## [1.5.0] - 2026-09-16 @ 19:54

### Changed

- Render the Score Distribution Histogram with responsive Plotly bars, preserving shared bins and the all-runs/oldest-half comparison, with hover counts and keyboard navigation.
- Start the homepage with a responsive snake snapshot and stacked highscore, completed-experiment, and simulation metrics. Remove the Status and Current Experiment boxes, preserve reports, and move the hostname above Last Updated in the footer.
- Use Plotly spline smoothing for Experiment Highscores, retaining recorded score markers, hover details, and keyboard navigation.
- Schedule publishing on the hour and half hour in the server's local timezone, waiting until the next boundary after startup and retrying failures at the next scheduled time. Remove five-minute database polling; keep immediate manual publishing with `--once`.

## [1.4.0] - 2026-09-16 @ 06:25

### Added

- Add a preview-first site reset script that clears generated reports, CSV histories, and export cursors for a new production source while preserving site configuration and Git history; supports committing and retrying the reset push.


### Starting fresh on a different production machine

Run from the `snake-web-code` checkout. These commands use the default publishing
checkout; substitute your `PUBLISH_CHECKOUT` if different and add `--branch BRANCH`
if the publishing branch is not `main`.

```bash
# Stop the old machine's daemon before resetting the published experiment.
sudo systemctl stop snake-web.service

# Preview the files that will be reset.
sudo -u snake-web python3 scripts/reset-site.py /var/lib/snake-web/site

# Reset generated content, commit, and push to the website repository.
sudo -u snake-web python3 scripts/reset-site.py /var/lib/snake-web/site --apply --push
```

The reset removes generated reports, CSV histories, and export cursors, and
replaces the homepage with a waiting-for-publication placeholder. It preserves
site configuration, `CNAME`, other pages, Git history, and source databases.
Omit `--push` to inspect the reset commit locally first; rerun with
`--apply --push` to publish it or retry a failed push.

Keep the old daemon stopped. If that machine will remain in service, prevent
publication from restarting after a reboot:

```bash
sudo systemctl disable snake-web.service
```

On the new machine, clone or synchronize the publishing checkout to include the
pushed reset commit before installing/starting the daemon. The installer starts
the service automatically. Configure it for the new source database, and do not
restore the old CSVs or cursors. Only one machine should publish to this branch.

See [Reset published experiment](docs/devops/reset-site.md) for full instructions.

## [1.3.2] - 2026-09-16 @ 06:08

### Changed

- Shorten conversation links in the Event Log to Current Golden, Prompt, or Response, preserving full detail content and text search.

## [1.3.1] - 2026-09-16 @ 05:57

### Fixed

- Convert MariaDB's Decimal event-cursor aggregate to an integer before JSON export, preventing status publication failures while preserving exact event IDs.

## [1.3.0] - 2026-09-16 @ 05:49

### Added

- Publish the complete sanitized Event Log with the five agreed event types, search, filters, pagination, and a homepage link.
- Add static prompt, reasoning, simulation-run, and submitted-configuration details with Home and Event Log navigation; pretty-print prompt JSON and exclude full response/choices payloads before export.
- Track event export progress separately from retained rows and refresh mutable simulation details, publishing data and cursor together for safe push retries.
- Install event report assets and provision read-only access to Snake Lab configurations.

### Changed

- Label the homepage navigation link “Home” on all three report pages.

## [1.2.0] - 2026-09-16 @ 05:32

### Added

- Show Last Updated in the daemon’s local timezone at the bottom of the homepage; preserve the timestamp on unchanged polling passes and push retries.

### Removed

- Remove GoatCounter tracking and the visitor count from the homepage.

### Added

- Publish Golden Configurations from incremental CSV with timestamps, run IDs, scores, parameter changes, and expandable LLM reasoning.
- Sanitize golden history before export: retain only displayed fields and first-choice reasoning, excluding full response and tool payloads.
- Install and publish golden report assets with the other reports and link the table from the homepage.

## [1.1.1] - 2026-09-16 @ 05:23

### Added

- Display a GoatCounter visitor count at the bottom of the homepage after the analytics script loads.

## [1.1.0] - 2026-09-16 @ 05:20

### Added

- Publish the Score Distribution Histogram from static CSV, comparing all runs with the oldest half using shared bins, with hover and keyboard details.
- Append observations for new runs and changed scores; histogram counts use the latest score per run, retaining unscored submissions for the cohort split.
- Include histogram assets in installation and the existing atomic publication commit.

## [1.0.0] - 2026-09-16 @ 05:13

### Added

- Publish an Experiment Highscores plot backed by an incremental static CSV of accepted scores, with hover and keyboard details and a homepage link.
- Publish report assets and homepage together and retry failed pushes without duplicate history records.
- Provision read-only access to Ax3l's experiment highscore history and install the report assets.

## [0.2.9] - 2026-09-16 @ 04:32

### Fixed

- Look up the golden run using a parameterized ID instead of comparing text columns across the Snake Lab and Ax3l schemas, avoiding their current collation mismatch without altering either schema.

## [0.2.8] - 2026-09-16 @ 03:57

### Added

- Generate a responsive Current Experiment panel with hostname, all-time and current golden scores, simulation and cycle counts, plain-text report names, and an inline SVG of the current golden run’s saved board.
- Read Ax3l golden-configuration and round-robin events; install and upgrade grant the existing reader SELECT on `ax3l.events` and `ax3l.event_messages`.

## [0.2.7] - 2026-09-16 @ 03:38

### Changed

- Regenerate the complete homepage from the current high score; require an existing `index.md` but do not validate or preserve its contents.

## [0.2.6] - 2026-09-16 @ 03:28

### Fixed

- Resolve the homepage as `index.md` relative to `PUBLISH_CHECKOUT`, avoiding an extra `site/` directory in the publishing path.

## [0.2.5] - 2026-09-16 @ 03:05

### Changed

- Publish high-score updates to the homepage at `site/index.md`.

## [0.2.4] - 2026-09-15 @ 19:52

### Changed

- Install publishing defaults at `/etc/snake-web/snake-web.env`, preserving existing settings and copying the former `/etc/snake-web.env` when needed; systemd reads the new path.

- Store managed database credentials in `/etc/snake-web/database.env`; install and upgrade preserve credentials from the former Snake Web-managed path when needed.

- Move the DevOps guides from `snake-web` into `docs/devops` and use repository-relative documentation links.

## [0.2.3] - 2026-09-15 @ 19:35

- Move the application, deployment scripts, dependencies, and tests into the separate `snake-web-code` repository.
- Use a local status-page fixture so code tests run independently of the website checkout.

## [0.2.2] - 2026-09-14 @ 06:20

### Added

- Install and upgrade now provision Snake Web's own `snake_web_reader@localhost` account with only SELECT access to `snakelab.simulation_runs`, using local MariaDB root socket access.
- Store generated credentials in root-owned `/etc/snake-lab/database.env` (0600), preserving the password across upgrades and leaving unrelated application credentials untouched.
- Added isolated MariaDB tests for credential preservation, restricted grants, account recovery, and refusal to take over unrelated files or accounts.

### Changed

- The systemd service loads its managed database environment separately from Git settings in `/etc/snake-web.env`.

## [0.2.0] - 2026-09-14 @ 05:32

### Added

- Added the AppDb → DbMgr DAL for reading the highest recorded Snake Lab simulation score without modifying source databases.
- Added one-shot and periodic status publishing through a dedicated Git clone, with status-only commits, serialized updates, and retries for pending pushes.
- Added DEV tests using temporary Git repositories and optional restored MariaDB data.
- Documented coding conventions and split the DevOps guide into dedicated pages.

### Changed

- The daemon now uses `DSnakeWeb.POLL_INTERVAL` between high-score checks, pushing only changed status or a pending status commit from a failed push.
- Installation now deploys the DAL and publisher with a Python virtual environment and reads production configuration from `/etc/snake-web.env`, preserving it during upgrades.

## [0.1.0] - 2026-09-13 @ 22:30

### Added

- Added `scripts/upgrade.sh` for root-run deployment of a pulled release, reusing the installer to update code and systemd while preserving service account data.
- Added an idle Python service with clean SIGTERM/SIGINT shutdown and journal logging.
- Adapted the Ax3l systemd template to run as `snake-web` with filesystem protections and automatic restart on failure.

### Changed

- Installation now deploys daemon code and enables and starts the systemd service; reinstallation restarts it.
- Uninstallation now stops and removes the service while preserving the account and its data.

## [0.0.1] - 2026-09-13 @ 21:52

### Added

- Created basic project structure.
- Added a `new-release.sh` script.
- Added `scripts/install.sh` to create the `snake-web` service account, its home at `/var/lib/snake-web`, and the root-owned daemon code directory at `/opt/prod/snake-web`.
- Added `scripts/uninstall.sh` to remove the daemon code directory while preserving the service account, group, home, SSH credentials, and publishing clone.
- Documented installation, uninstallation, and service account Git access for publishing experiment status to GitHub Pages.
