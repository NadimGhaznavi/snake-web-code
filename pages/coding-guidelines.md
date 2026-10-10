---
title: Coding Guidelines
author_profile: true
layout: single
---

[Project overview](../README.md) · [DevOps documentation](../docs/devops/index.md)

These are Snake Web's development standards. MUST identifies a requirement;
SHOULD identifies a default whose exceptions need a concrete reason.

## Ownership and scope

The project owner is the architect and release manager. The AI assistant is
responsible for implementation, verification, and documentation.

Changes MUST follow the owner's architecture and requested scope. Preserve
existing behavior unless the task requires changing it. Do not expand a task
into an unrelated refactor.

Snake Web publishes Snake Lab scores, Ax3l experiment status, sanitized reports,
and captured daily games to a static website. This repository owns the Python
publisher, its templates and report assets, deployment scripts, and tests.
The separate `snake-web` repository owns website pages and Jekyll configuration.
Snake Lab and Ax3l own simulation execution, optimization, and source schemas.

ANY edits to files outside this repository MUST be approved by the user.
Use authorization already given in the session; do not ask for it again.
The owner handles production rollout unless they delegate it explicitly.
Git operations and release scripts may be used within the authorized workflow.

## Ecosystem consistency

Snake Web, Snake Lab, and Ax3l share infrastructure and interfaces. Preserve
established schema, protocol, and data contracts.

When an inconsistency between projects appears, stop the affected work and
alert the owner before implementing a workaround. Explain the mismatch and its
impact so the owner can choose a shared-contract fix or authorize a temporary
solution. Document approved workarounds and the upstream standard to revisit.

Preserve running experiments and their data. Do not wipe, reset, or migrate
source databases to resolve an inconsistency without explicit authorization.

## Architecture and project structure

Each component MUST have a clear responsibility and resource owner. Keep
transport, application rules, persistence, publication, and presentation separate.
Dependencies SHOULD use narrow interfaces or injected callables. Construct and
connect resources at explicit application entry points. Introduce abstractions
and services only for demonstrated requirements.

| Location | Responsibility |
| --- | --- |
| `README.md` | Project overview and development entry point |
| `pages/` | Canonical development guidelines |
| `docs/devops/` | Installation, publication, and maintenance guides |
| `snake_web/server.py` | Application wiring, scheduling, and lifecycle |
| `snake_web/entity/` | Data entities |
| `snake_web/activity/` | Application queries, exports, rendering, and publishing operations |
| `snake_web/activity/reports/` | Static report templates and browser scripts |
| `snake_web/interface/` | Database, Snake Lab, filesystem, and Git boundaries |
| `snake_web/constants/` | Version and shared definitions |
| `scripts/` | Installation, maintenance, and release tooling |
| `systemd/` | Service unit and environment template |
| `tests/` | Rendering, query, publication, and provisioning verification |
| `CHANGELOG.md` | User-visible changes |

The data abstraction layer MUST follow this call flow:

**App → activity/AppDb → interface/DbMgr → database**

`AppDb` owns SQL, query rules, and interpretation of source records. `DbMgr`
owns connections, parameterized execution, transactions, and cleanup, returning
rows without interpreting application concepts. Application operations MUST
request data through `AppDb`. Rendering and Git publication remain outside the DAL.

## Configuration and external interfaces

- Database access from the publisher MUST remain read-only. Provision only the
  dedicated reader's required grants; do not initialize source application tables.
- Snake Lab capture retrieval MUST follow its versioned ZMQ contract and validate
  external responses before rendering. Keep Ax3l-compatible capture and animation behavior.
- Validate configuration, source records, export cursors, and publishing paths
  at their boundaries. Internal callers MUST trust validated objects and contracts.
- Keep public export fields explicit. Preserve the event allowlist and sanitization
  rules; do not expose credentials, private responses, or unapproved source payloads.
- Network and subprocess operations MUST have explicit timeouts.
- Credentials and secrets MUST NOT appear in logs, public artifacts, or command arguments.

Expected external failures MUST produce a clear result. A failed `--once` pass
MUST return a failing exit status; scheduled publication MUST log failures and
retry on a later pass. Programming errors MUST surface rather than being hidden
by broad exception handlers. Document any deliberate stale-cache behavior.

## Saved state and publication

Publication MUST serialize access to its dedicated Git checkout and release
locks reliably. Require the configured branch and a clean worktree; incorporate
remote updates without discarding unrelated work. Refuse diverged histories and
unrelated pending commits. Never force-push as part of routine publication.

Publish only managed paths. Related homepage, report, data, cursor, and GIF
updates MUST share a commit. Replace saved files atomically. Retry unpublished
commits without duplicating records or falsely reporting a successful push.

Incremental exports MUST preserve source ordering, nullable and zero scores,
and cursor semantics. Source-history replacement requires the owner's deliberate
reset workflow; do not silently backfill or reset cursors to hide discrepancies.
Daily rankings use a JSON flat file and cached GIFs; legacy SVG-only results MUST
remain excluded from the daily viewer. See the [project overview](../README.md)
for the daily selection and cache contract.

## Installation and production

Installation deploys code to `/opt/prod/snake-web` and runs `snake-web.service`
as the `snake-web` account. Configuration lives in `/etc/snake-web`; persistent
state, SSH credentials, and the default publishing checkout live under
`/var/lib/snake-web`. Keep development, deployment, and publishing checkouts separate.

Installation MUST deploy every required module, template, browser asset, and
Python dependency. Upgrades and uninstallation MUST preserve configuration,
credentials, the publishing checkout, and saved publication data. Configuration
and credential files MUST have restrictive permissions. Maintenance requires
root; the running publisher uses its dedicated account and read-only DB access.

Confirm the intended host and configured source before production work. An
installer can copy code before provisioning fails; report partial installation
accurately. Do not bypass missing source schemas or restart a service the owner
has deliberately stopped without authorization. Follow the
[installation](../docs/devops/install.md), [upgrade](../docs/devops/upgrade.md),
and [immediate publication](../docs/devops/push-now.md) guides.

## Documentation

Documentation MUST be short, direct, and task-focused. Include what readers need
to install, use, or develop the software. Omit implementation narration, repeated
explanations, development history, and speculative features. Put detailed
contracts in one reference and link to it.

- Keep `README.md` as the project entry point and link operational guides through
  `docs/devops/index.md`. Link canonical guidelines instead of maintaining duplicate rules.
- Give each document one purpose. Preserve existing Markdown conventions;
  pages under `pages/` use YAML front matter with a `title` key.
- Use relative Markdown links in this code repository. In the separate Jekyll
  website, follow its established `site.baseurl` and `link` conventions.
- Use fenced examples and tables where useful, and document verified commands.
- Credentials and secrets MUST NOT appear in public documentation.

Let the shared theme own website presentation where applicable and use GitHub
Pages for website builds. Do not add a Gemfile, require local Jekyll builds,
or commit generated site output to this code repository. Managed publication
artifacts belong in the dedicated website checkout.

## Verification and review

Run checks appropriate to the change. Use temporary directories, disposable Git
repositories and local remotes, isolated databases, and simulated control interfaces.
Routine verification MUST NOT modify production experiments or publish to the
live website without the owner's authorization.

Query and export changes MUST cover ordering, ties, null and zero scores,
source boundaries, sanitization, cursor advancement, and repeated exports as
applicable. Publication changes MUST cover unchanged content, failed-push retries,
concurrency, remote advances, and refusal of dirty or diverged checkouts.

Daily-game changes MUST cover missing captures, exclusion of legacy SVG-only
results, GIF reuse and replacement, day rollover, capture-service failures,
and navigation with zero, one, two, and three games. Inspect rendered output at
desktop and mobile widths when presentation changes.

Installer changes MUST verify deployed files, permissions, upgrades, preservation
of state and credentials, and reader provisioning without source-schema mutation.
Release changes MUST use disposable repositories and a local remote to check
version, changelog, branch, and tag updates.

Review architectural changes with `$review-architecture` when available. Reviews
MUST identify concrete evidence, consequences, and bounded corrections. Trace a
normal operation and a relevant failure path. Distinguish defects from preferences;
passing tests alone does not establish architectural correctness.

Check documentation front matter, link targets, and navigation. Report checks
that could not be run, including optional database or browser verification.

## Changelog and releases

Record meaningful changes under `## [Unreleased]` in `CHANGELOG.md`, focusing on
user-visible outcomes.

`DSnakeWeb.VERSION` MUST remain a single-line literal string in
`snake_web/constants/DSnakeWeb.py` for the current release script.
`scripts/new-release.sh` takes a version, a release message, and an optional next
feature branch. It runs from a clean, committed `feat/*` branch, merges through
`dev` and `main`, updates the version and changelog timestamp, and publishes those
branches and the annotated version tag to `origin`.

The current script pushes without an interactive confirmation. Verify repository,
release details, and owner authorization before invoking it. Do not introduce
codename or CMDB requirements that the project's release tooling does not implement.
