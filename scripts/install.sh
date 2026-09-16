#!/usr/bin/env bash
# Install and start the status publishing service.
set -euo pipefail

service_user=snake-web
service_home=/var/lib/snake-web
install_dir=/opt/prod/snake-web
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
unit_path=/etc/systemd/system/snake-web.service
config_dir=/etc/snake-web
environment_file=${config_dir}/snake-web.env
legacy_environment_file=/etc/snake-web.env

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<EOF
Usage: sudo $0

Create the snake-web system account with home /var/lib/snake-web and
install Python daemon code in /opt/prod/snake-web, owned by root, and
enable and start snake-web.service (restart it on reinstall).
Safe to rerun with an existing compatible account and directories.
Provisions a dedicated local MariaDB reader and /etc/snake-web/database.env.
Creates /etc/snake-web/snake-web.env; preserves existing settings on reinstall.
Requires local MariaDB root socket access and the existing Snake Lab schema.
Does not configure GitHub credentials. Requires Python 3 with venv support, Git, systemd, and package download access.
EOF
}

if [[ $# == 1 && ( $1 == --help || $1 == -h ) ]]; then
    usage
    exit 0
fi
[[ $# == 0 ]] || { usage >&2; exit 2; }
[[ ${EUID} == 0 ]] || fail 'Run this installer as root.'

for command in getent groupadd useradd usermod install id systemctl git mariadb; do
    command -v "${command}" >/dev/null || fail "Required command not found: ${command}"
done
[[ -x /bin/bash ]] || fail 'Missing /bin/bash.'
[[ -x /usr/bin/python3 ]] || fail 'Missing /usr/bin/python3.'
[[ -d /run/systemd/system ]] || fail 'This installer requires a running systemd system.'
code_files=(
    snake_web/__init__.py
    snake_web/server.py
    snake_web/constants/DSnakeWeb.py
    snake_web/activity/AppDb.py
    snake_web/activity/PublishStatus.py
    snake_web/activity/SimulationBoard.py
    snake_web/activity/homepage.html
    snake_web/entity/ExperimentStatus.py
    snake_web/interface/DbMgr.py
    snake_web/interface/GitPublisher.py
)
for source_file in "${code_files[@]}" requirements.txt scripts/provision-database.py systemd/snake-web.service systemd/snake-web.env; do
    [[ -f ${source_dir}/${source_file} ]] || fail "Missing source file: ${source_file}"
done

for directory in /etc "${config_dir}" /var/lib "${service_home}" /opt /opt/prod "${install_dir}" "${install_dir}/snake_web" "${install_dir}/snake_web/constants" "${install_dir}/snake_web/activity" "${install_dir}/snake_web/entity" "${install_dir}/snake_web/interface" "${install_dir}/venv"; do
    [[ ! -L ${directory} ]] || fail "Refusing symlink: ${directory}"
    [[ ! -e ${directory} || -d ${directory} ]] || fail "Not a directory: ${directory}"
done
for relative in "${code_files[@]}" requirements.txt; do
    destination="${install_dir}/${relative}"
    [[ ! -L ${destination} ]] || fail "Refusing symlink: ${destination}"
    [[ ! -e ${destination} || -f ${destination} ]] || fail "Not a regular file: ${destination}"
done
[[ ! -L ${unit_path} ]] || fail "Refusing symlink: ${unit_path}"
[[ ! -e ${unit_path} || -f ${unit_path} ]] || fail "Not a regular file: ${unit_path}"

[[ ! -L ${environment_file} ]] || fail "Refusing symlink: ${environment_file}"
[[ ! -e ${environment_file} || -f ${environment_file} ]] || fail "Not a regular file: ${environment_file}"
if [[ ! -e ${environment_file} ]]; then
    [[ ! -L ${legacy_environment_file} ]] || fail "Refusing symlink: ${legacy_environment_file}"
    [[ ! -e ${legacy_environment_file} || -f ${legacy_environment_file} ]] || fail "Not a regular file: ${legacy_environment_file}"
fi

if account=$(getent passwd "${service_user}"); then
    IFS=: read -r name password uid gid comment account_home account_shell <<< "${account}"
    [[ ${uid} != 0 ]] || fail 'The service account must not be root.'
    [[ ${account_home} == "${service_home}" ]] || fail "Existing account home must be ${service_home}."
    [[ ${account_shell} == /bin/bash || ${account_shell} == /usr/sbin/nologin ]] || fail 'Existing account must use /bin/bash or /usr/sbin/nologin.'
    [[ $(id -gn "${service_user}") == "${service_user}" ]] || fail "Existing account primary group must be ${service_user}."
    if [[ ${account_shell} == /usr/sbin/nologin ]]; then
        usermod --shell /bin/bash "${service_user}"
    fi
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
for relative in "${code_files[@]}" requirements.txt; do
    install -D -m 0644 -o root -g root "${source_dir}/${relative}" "${install_dir}/${relative}"
done
install -d -m 0700 -o root -g root "${config_dir}"
if [[ ! -e ${environment_file} ]]; then
    if [[ -f ${legacy_environment_file} ]]; then
        install -m 0600 -o root -g root "${legacy_environment_file}" "${environment_file}"
    else
        install -m 0600 -o root -g root "${source_dir}/systemd/snake-web.env" "${environment_file}"
    fi
fi
/usr/bin/python3 -m venv "${install_dir}/venv"
"${install_dir}/venv/bin/python" -m pip install -r "${install_dir}/requirements.txt"
"${install_dir}/venv/bin/python" "${source_dir}/scripts/provision-database.py"
install -m 0644 -o root -g root "${source_dir}/systemd/snake-web.service" "${unit_path}"
systemctl daemon-reload
systemctl enable snake-web.service
systemctl restart snake-web.service
systemctl is-active --quiet snake-web.service

printf 'Service account ready: %s (home: %s)\n' "${service_user}" "${service_home}"
printf 'Daemon code directory ready: %s (root:root, 0755)\n' "${install_dir}"
printf 'Publishing configuration ready: %s (review Git settings and complete SSH setup)\n' "${environment_file}"
printf 'snake-web.service enabled and started.\n'
