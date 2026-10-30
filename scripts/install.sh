#!/usr/bin/env bash
# Install and start the static artifact publishing service.
set -euo pipefail

service_user=snake-web
service_home=/var/lib/snake-web
install_dir=/opt/prod/snakewebcode
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
unit_path=/etc/systemd/system/snake-web.service
config_dir=/etc/snake-web
environment_file=${config_dir}/snake-web.env

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<EOF
Usage: sudo $0

Create the snake-web system account with home /var/lib/snake-web and
install Python daemon code in /opt/prod/snakewebcode, owned by root, and
enable and start snake-web.service (restart it on reinstall).
Safe to rerun with an existing compatible account and directories.
Provisions a dedicated local MariaDB reader and /etc/snake-web/database.env.
Creates /etc/snake-web/snake-web.env; preserves existing settings on reinstall.
Creates conf/snakewebcode.json from listener defaults; preserves existing overrides.
Requires local MariaDB root socket access and the existing Snake Lab schema.
Requires Python 3 with venv support, systemd, and package download access.
Caddy setup is separate; see docs/devops/static-publishing.md.
EOF
}

if [[ $# == 1 && ( $1 == --help || $1 == -h ) ]]; then
    usage
    exit 0
fi
[[ $# == 0 ]] || { usage >&2; exit 2; }
[[ ${EUID} == 0 ]] || fail 'Run this installer as root.'
# The service account must be able to read the virtual environment and dependencies.
umask 022

for command in getent groupadd useradd install id systemctl mariadb; do
    command -v "${command}" >/dev/null || fail "Required command not found: ${command}"
done
[[ -x /bin/bash ]] || fail 'Missing /bin/bash.'
[[ -x /usr/bin/python3 ]] || fail 'Missing /usr/bin/python3.'
[[ -d /run/systemd/system ]] || fail 'This installer requires a running systemd system.'
code_files=(
    snakewebcode/__init__.py
    snakewebcode/server.py
    snakewebcode/constants/DSnakeWebCode.py
    snakewebcode/constants/DSnakeLab.py
    snakewebcode/activity/AppDb.py
    snakewebcode/activity/PublishLive.py
    snakewebcode/activity/DailyGames.py
    snakewebcode/activity/ScoreDistribution.py
    snakewebcode/activity/SimulationAnimation.py
    snakewebcode/activity/fonts/DejaVuSansMono.ttf
    snakewebcode/activity/fonts/LICENSE.txt
    snakewebcode/interface/DbMgr.py
    snakewebcode/interface/SnakeLab.py
    snakewebcode/interface/StaticPublisher.py
    snakewebcode/interface/GIFAnimation.py
    snakewebcode/interface/Configuration.py
    snakewebcode/interface/Network.py
)
for source_file in "${code_files[@]}" requirements.txt scripts/provision-database.py systemd/snake-web.service systemd/snake-web.env; do
    [[ -f ${source_dir}/${source_file} ]] || fail "Missing source file: ${source_file}"
done

for directory in /etc "${config_dir}" /var/lib "${service_home}" /opt /opt/prod "${install_dir}" "${install_dir}/conf" "${install_dir}/snakewebcode" "${install_dir}/venv"; do
    [[ ! -L ${directory} ]] || fail "Refusing symlink: ${directory}"
    [[ ! -e ${directory} || -d ${directory} ]] || fail "Not a directory: ${directory}"
done
requirements_file="${install_dir}/requirements.txt"
[[ ! -L ${requirements_file} ]] || fail "Refusing symlink: ${requirements_file}"
[[ ! -e ${requirements_file} || -f ${requirements_file} ]] || fail "Not a regular file: ${requirements_file}"
[[ ! -L ${unit_path} ]] || fail "Refusing symlink: ${unit_path}"
[[ ! -e ${unit_path} || -f ${unit_path} ]] || fail "Not a regular file: ${unit_path}"

[[ ! -L ${environment_file} ]] || fail "Refusing symlink: ${environment_file}"
[[ ! -e ${environment_file} || -f ${environment_file} ]] || fail "Not a regular file: ${environment_file}"

# Validate incoming network settings before provisioning, replacing code, or restarting services.
network_config=${install_dir}/conf/snakewebcode.json
[[ ! -L ${network_config} ]] || fail "Refusing symlink: ${network_config}"
/usr/bin/python3 -B - "${source_dir}" "${network_config}" <<'PY'
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])
from snakewebcode.constants.DSnakeWebCode import DSnakeWebCode
from snakewebcode.interface.Configuration import Configuration

Configuration.read(Path(sys.argv[2]), DSnakeWebCode.CMDB_NETWORK)
PY

if account=$(getent passwd "${service_user}"); then
    IFS=: read -r name password uid gid comment account_home account_shell <<< "${account}"
    [[ ${uid} != 0 ]] || fail 'The service account must not be root.'
    [[ ${account_home} == "${service_home}" ]] || fail "Existing account home must be ${service_home}."
    [[ ${account_shell} == /bin/bash ]] || fail 'Existing account must use /bin/bash.'
    [[ $(id -gn "${service_user}") == "${service_user}" ]] || fail "Existing account primary group must be ${service_user}."
else
    if ! getent group "${service_user}" >/dev/null; then
        groupadd --system "${service_user}"
    fi
    useradd --system --gid "${service_user}" --home-dir "${service_home}" \
        --no-create-home --shell /bin/bash "${service_user}"
fi

install -d -m 0750 -o "${service_user}" -g "${service_user}" "${service_home}"
if [[ ! -d /opt/prod ]]; then
    install -d -m 0755 -o root -g root /opt/prod
fi
install -d -m 0755 -o root -g root "${install_dir}"
install -m 0644 -o root -g root "${source_dir}/requirements.txt" "${requirements_file}"
install -d -m 0700 -o root -g root "${config_dir}"
if [[ ! -e ${environment_file} ]]; then
    install -m 0600 -o root -g root "${source_dir}/systemd/snake-web.env" "${environment_file}"
fi
/usr/bin/python3 -m venv "${install_dir}/venv"
"${install_dir}/venv/bin/python" -m pip install -r "${requirements_file}"
"${install_dir}/venv/bin/python" "${source_dir}/scripts/provision-database.py"
# Replace application code completely; configuration and publication data live elsewhere.
rm -rf --one-file-system -- "${install_dir}/snakewebcode"
for relative in "${code_files[@]}"; do
    install -D -m 0644 -o root -g root "${source_dir}/${relative}" "${install_dir}/${relative}"
done
/usr/bin/python3 -B - "${source_dir}" "${network_config}" <<'PY'
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])
from snakewebcode.interface.Configuration import Configuration

Configuration.install(Path(sys.argv[2]))
PY
install -m 0644 -o root -g root "${source_dir}/systemd/snake-web.service" "${unit_path}"
systemctl daemon-reload
systemctl enable snake-web.service
systemctl restart snake-web.service
systemctl is-active --quiet snake-web.service

printf 'Service account ready: %s (home: %s)\n' "${service_user}" "${service_home}"
printf 'Daemon code directory ready: %s (root:root, 0755)\n' "${install_dir}"
printf 'Publishing configuration ready: %s (review the public directory and Caddy setup)\n' "${environment_file}"
printf 'snake-web.service enabled and started.\n'
