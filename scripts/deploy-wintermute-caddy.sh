#!/usr/bin/env bash
# One-time Caddy/environment setup for the already-installed Snake Web 5 publisher.
set -euo pipefail

usage() {
    printf 'Usage: sudo scripts/deploy-wintermute-caddy.sh\nConfigure static Snake Web publication on wintermute. Requires Snake Web 5 already installed.\n'
}
if [[ $# == 1 && ( $1 == --help || $1 == -h ) ]]; then
    usage
    exit 0
fi
[[ $# == 0 && ${EUID} == 0 ]] || { usage >&2; exit 1; }
[[ $(hostname -s) == wintermute ]] || { printf 'Run this script on wintermute.\n' >&2; exit 1; }
for command in caddy python3 setfacl getfacl runuser systemctl timeout; do
    command -v "${command}" >/dev/null || { printf 'Missing command: %s\n' "${command}" >&2; exit 1; }
done
[[ -f /opt/prod/snakewebcode/snakewebcode/interface/StaticPublisher.py ]] || {
    printf 'Install Snake Web 5 before configuring Caddy.\n' >&2; exit 1;
}
for service in caddy.service snake-web.service; do
    systemctl is-active --quiet "${service}" || {
        printf 'Required service is not running: %s\n' "${service}" >&2; exit 1;
    }
done
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ -f ${source_dir}/systemd/Caddyfile.snake && -f ${source_dir}/scripts/push-now.sh ]] || {
    printf 'Run the script from the reviewed Snake Web checkout.\n' >&2; exit 1;
}
backup_dir=$(mktemp -d /var/backups/snake-web-caddy.XXXXXX)
printf 'Configuration backup: %s\n' "${backup_dir}"
trap 'printf "Deployment incomplete; inspect the error and backups in %s.\n" "${backup_dir}" >&2' ERR

getfacl -p /var/lib/snake-web > "${backup_dir}/service-home.acl"
install -d -m 0755 -o snake-web -g snake-web /var/lib/snake-web/public
setfacl -m u:caddy:--x /var/lib/snake-web
runuser -u caddy -- test -x /var/lib/snake-web/public

python3 - "${source_dir}" "${backup_dir}" <<'PY'
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import NamedTemporaryFile

source, backup = map(Path, sys.argv[1:])
config = Path('/etc/caddy/Caddyfile')
site = Path('/etc/caddy/snake-web.caddy')
environment = Path('/etc/snake-web/snake-web.env')
for path in (config, site, environment):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise RuntimeError(f'Refusing non-regular configuration: {path}')
original = config.read_text()
settings = environment.read_text()
previous_site = site.read_bytes() if site.exists() else None
rendered = (source / 'systemd/Caddyfile.snake').read_text()
directive = f'import {site}'
base = '\n'.join(line for line in original.splitlines() if line.strip() != directive)

# Follow MyCount: validate a combined candidate in the real config directory,
# preserving the base configuration and its other imports.
with NamedTemporaryFile(mode='w', prefix='.snake-web-', suffix='.Caddyfile', dir=config.parent) as candidate:
    candidate.write(base + '\n' + rendered)
    candidate.flush()
    subprocess.run(['caddy', 'validate', '--config', candidate.name, '--adapter', 'caddyfile'],
                   check=True, timeout=60)

shutil.copy2(config, backup / 'Caddyfile')
shutil.copy2(environment, backup / 'snake-web.env')
if previous_site is not None:
    shutil.copy2(site, backup / 'snake-web.caddy')
site.write_text(rendered)
site.chmod(0o644)
config.write_text(base + '\n' + directive + '\n')
try:
    # Match MyCount's direct reload; do not restart the shared Caddy service or
    # wait on systemd's reload notification.
    subprocess.run(['caddy', 'reload', '--config', str(config), '--adapter', 'caddyfile'],
                   check=True, timeout=60)
except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
    config.write_text(original)
    if previous_site is None:
        site.unlink(missing_ok=True)
    else:
        site.write_bytes(previous_site)
    raise

lines = [line for line in settings.splitlines()
         if not line.strip().startswith('PUBLISH_DIRECTORY=')]
environment.write_text('\n'.join(lines) + '\nPUBLISH_DIRECTORY=/var/lib/snake-web/public\n')
environment.chmod(0o600)
PY

systemctl restart snake-web.service
systemctl is-active --quiet snake-web.service
timeout 300 bash "${source_dir}/scripts/push-now.sh"
runuser -u caddy -- test -r /var/lib/snake-web/public/live.json
runuser -u caddy -- test -r /var/lib/snake-web/public/score-distribution.gif
printf 'Static publication configured. Backup: %s\n' "${backup_dir}"
printf 'Verify HTTPS/certificate issuance and no-store headers: curl -I https://snake.osoyalce.com/score-distribution.gif\n'
printf 'Deploy the separate snake-web homepage through its normal GitHub Pages workflow.\n'
