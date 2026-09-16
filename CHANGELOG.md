# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
