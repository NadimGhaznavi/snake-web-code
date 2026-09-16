# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
