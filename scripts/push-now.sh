#!/usr/bin/env bash
# Publish once using the installed application and production configuration.
set -euo pipefail

usage() {
    cat <<EOF
Usage: sudo $0

Generate and push current website content immediately, using the installed
code in /opt/prod/snake-web and configuration in /etc/snake-web.
Runs as snake-web, displays publishing output, and returns its exit status.
Leaves the scheduled service running. Unchanged content creates no new commit.
If another publication is in progress, wait for it to finish and rerun.
EOF
}

if [[ $# == 1 && ( $1 == --help || $1 == -h ) ]]; then
    usage
    exit 0
fi
[[ $# == 0 ]] || { usage >&2; exit 2; }
if [[ ${EUID} != 0 ]]; then
    printf 'Error: Run this script with sudo to load the service configuration.\n' >&2
    exit 1
fi

# Let systemd read EnvironmentFile syntax and root-only credentials, just as
# it does for the daemon. Do not source configuration files as shell scripts.
exec systemd-run --wait --pipe --collect \
    --description='Snake Web manual publication' \
    --uid=snake-web --gid=snake-web \
    --working-directory=/opt/prod/snake-web \
    --setenv=HOME=/var/lib/snake-web \
    --setenv=PYTHONUNBUFFERED=1 \
    --setenv=PYTHONDONTWRITEBYTECODE=1 \
    --setenv=GIT_TERMINAL_PROMPT=0 \
    --property=EnvironmentFile=/etc/snake-web/snake-web.env \
    --property=EnvironmentFile=/etc/snake-web/database.env \
    --property=NoNewPrivileges=true \
    --property=PrivateTmp=true \
    --property=ProtectHome=true \
    --property=ProtectSystem=strict \
    --property=ReadWritePaths=/var/lib/snake-web \
    /opt/prod/snake-web/venv/bin/python -m snake_web.server --once
