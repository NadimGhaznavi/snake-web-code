#!/usr/bin/env bash
# Apply the release from this checkout using the shared installation path.
set -euo pipefail

usage() {
    cat <<EOF
Usage: $0

Run as root after pulling the desired release into this checkout.
Deploy the Python code to /opt/prod/snake-web, update the systemd unit,
reload systemd, and enable and restart snake-web.service.

Also supports the first deployment. Preserves /var/lib/snake-web,
including SSH credentials and the publishing clone.
Preserves /etc/snake-web/snake-web.env and /etc/snake-web/database.env and reapplies the dedicated reader privileges.
Uses the files in this checkout; does not fetch or switch Git releases.
EOF
}

if [[ $# == 1 && ( $1 == --help || $1 == -h ) ]]; then
    usage
    exit 0
fi
[[ $# == 0 ]] || { usage >&2; exit 2; }
if [[ ${EUID} != 0 ]]; then
    printf 'Error: Run this upgrade script as root.\n' >&2
    exit 1
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec bash "${script_dir}/install.sh"
