#!/usr/bin/env bash
# Install the LAN artifact server behind wintermute's HTTPS reverse proxy.
set -euo pipefail

usage() {
    printf 'Usage: sudo scripts/deploy-neuromancer-caddy.sh [--reload-only]\nInstall Caddy and the Snake Web LAN site on neuromancer. Requires published artifacts.\nUse --reload-only to apply network settings without installing packages.\n'
}
if [[ $# == 1 && ( $1 == --help || $1 == -h ) ]]; then
    usage
    exit 0
fi
reload_only=false
if [[ $# == 1 && $1 == --reload-only ]]; then
    reload_only=true
    shift
fi
[[ $# == 0 && ${EUID} == 0 ]] || { usage >&2; exit 1; }
[[ $(hostname -s) == neuromancer ]] || { printf 'Run this script on neuromancer.\n' >&2; exit 1; }
umask 022
commands=(python3 runuser systemctl timeout)
if ${reload_only}; then
    commands+=(caddy getfacl setfacl curl)
else
    commands+=(apt-get)
fi
for command in "${commands[@]}"; do
    command -v "${command}" >/dev/null || { printf 'Missing command: %s\n' "${command}" >&2; exit 1; }
done
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ -f ${source_dir}/systemd/Caddyfile.snake-neuromancer &&
   -f /opt/prod/snakewebcode/snakewebcode/interface/StaticPublisher.py ]] || {
    printf 'Use the release checkout after installing Snake Web.\n' >&2; exit 1;
}
systemctl is-active --quiet snake-web.service || {
    printf 'snake-web.service must already be running.\n' >&2; exit 1;
}

network_config=/opt/prod/snakewebcode/conf/snakewebcode.json
# Validate configuration and resolve one binding for both the site and HTTP checks.
network_settings=$(python3 -B - "${source_dir}" "${network_config}" <<'PY'
from pathlib import Path
import shlex
import sys

sys.path.insert(0, sys.argv[1])
from snakewebcode.interface.Configuration import Configuration
from snakewebcode.interface.Network import Network

for name in ('/etc/caddy', '/var/lib/snake-web', '/var/lib/snake-web/public'):
    path = Path(name)
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise RuntimeError(f'Refusing non-directory or symlink: {path}')
for name in ('/etc/caddy/Caddyfile', '/etc/caddy/snake-web.caddy',
             '/etc/snake-web/snake-web.env'):
    path = Path(name)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise RuntimeError(f'Refusing non-regular configuration: {path}')
for line in Path('/etc/snake-web/snake-web.env').read_text().splitlines():
    key, separator, value = line.partition('=')
    if separator and key.strip() == 'PUBLISH_DIRECTORY':
        if shlex.split(value, comments=True) != ['/var/lib/snake-web/public']:
            raise RuntimeError('This deployment requires PUBLISH_DIRECTORY=/var/lib/snake-web/public.')
for name in ('live.json', 'score-distribution.gif'):
    path = Path('/var/lib/snake-web/public') / name
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f'Publish artifacts before configuring Caddy: {path}')
settings = Path(sys.argv[2])
Configuration.install(settings)
interface, port = Network.binding('http', settings)
destination, _ = Network.destination('http', settings)
print(interface, port, destination)
PY
)
read -r bind_interface bind_port probe_interface <<< "${network_settings}"

backup_dir=$(mktemp -d /var/backups/snake-web-caddy.XXXXXX)
printf 'Configuration backup: %s\n' "${backup_dir}"
trap 'printf "Deployment incomplete; inspect the error and backups in %s. Packages and ACL changes may remain applied.\n" "${backup_dir}" >&2' ERR
if ! ${reload_only}; then
    timeout 300 apt-get update
    timeout 600 env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends caddy acl curl
fi
getfacl -p /var/lib/snake-web > "${backup_dir}/service-home.acl"
setfacl -m u:caddy:--x /var/lib/snake-web
runuser -u caddy -- test -r /var/lib/snake-web/public/live.json
runuser -u caddy -- test -r /var/lib/snake-web/public/score-distribution.gif

python3 - "${source_dir}" "${backup_dir}" "${bind_interface}" "${bind_port}" <<'PY'
from pathlib import Path
import os
import shutil
import subprocess
import sys
from tempfile import NamedTemporaryFile

source, backup = map(Path, sys.argv[1:3])
interface, port = sys.argv[3:5]
config = Path('/etc/caddy/Caddyfile')
site = Path('/etc/caddy/snake-web.caddy')
original = config.read_bytes()
previous_site = site.read_bytes() if site.exists() else None
shutil.copy2(config, backup / 'Caddyfile')
if previous_site is not None:
    shutil.copy2(site, backup / 'snake-web.caddy')
rendered = (source / 'systemd/Caddyfile.snake-neuromancer').read_text()
rendered = rendered.replace('__HTTP_INTERFACE__', interface).replace('__HTTP_PORT__', port)
directive = f'import {site}'
base = '\n'.join(line for line in original.decode().splitlines() if line.strip() != directive)
with NamedTemporaryFile(mode='w', prefix='.snake-web-', suffix='.Caddyfile', dir=config.parent) as candidate:
    candidate.write(base + '\n' + rendered)
    candidate.flush()
    subprocess.run(['caddy', 'validate', '--config', candidate.name, '--adapter', 'caddyfile'],
                   check=True, timeout=60)


def replace(path, content):
    with NamedTemporaryFile(prefix='.snake-web-', dir=path.parent, delete=False) as staged:
        temporary = Path(staged.name)
        try:
            staged.write(content)
            staged.flush()
            os.fchmod(staged.fileno(), 0o644)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


was_active = subprocess.run(['systemctl', 'is-active', '--quiet', 'caddy.service'],
                            timeout=30).returncode == 0
try:
    replace(site, rendered.encode())
    replace(config, (base + '\n' + directive + '\n').encode())
    if was_active:
        subprocess.run(['caddy', 'reload', '--config', str(config), '--adapter', 'caddyfile'],
                       check=True, timeout=60)
    else:
        subprocess.run(['systemctl', 'start', 'caddy.service'], check=True, timeout=60)
except (OSError, subprocess.SubprocessError):
    replace(config, original)
    if previous_site is None:
        site.unlink(missing_ok=True)
    else:
        replace(site, previous_site)
    if was_active:
        recovery = ['caddy', 'reload', '--config', str(config), '--adapter', 'caddyfile']
    else:
        recovery = ['systemctl', 'stop', 'caddy.service']
    try:
        subprocess.run(recovery, check=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'Configuration files restored; service recovery failed: {exc}', file=sys.stderr)
    raise
PY

timeout 60 systemctl enable caddy.service
systemctl is-active --quiet caddy.service
for artifact in live.json score-distribution.gif; do
    curl --fail --silent --show-error --head --connect-timeout 5 --max-time 15 \
        "http://${probe_interface}:${bind_port}/${artifact}"
done
printf 'Snake Web LAN server configured. Backup: %s\n' "${backup_dir}"
printf "Backend binding: %s:%s; keep wintermute's upstream in sync.\n" "${bind_interface}" "${bind_port}"
printf 'Then verify HTTPS: curl -I --max-time 15 https://snake.osoyalce.com/score-distribution.gif\n'
