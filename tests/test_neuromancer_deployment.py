"""Exercise the LAN Caddy deployment without installing packages or touching services."""

import sys
import unittest

import test_installation


STUB = '''import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(os.environ['SNAKEWEB_TEST_ROOT'])
name, args = Path(sys.argv[0]).name, sys.argv[1:]
with (root / 'commands.jsonl').open('a') as stream:
    stream.write(json.dumps([name, *args]) + '\\n')
running = root / 'caddy-running'
if name == 'hostname':
    print(os.environ.get('SNAKEWEB_TEST_HOST', 'neuromancer'))
elif name == 'apt-get':
    if os.environ.get('SNAKEWEB_TEST_APT_FAIL'):
        sys.exit(8)
    if args[0] == 'install':
        config = root / 'etc/caddy/Caddyfile'
        config.parent.mkdir(exist_ok=True)
        if not config.exists():
            config.write_text(':80 {\\n root * /usr/share/caddy\\n file_server\\n}\\n')
elif name == 'getfacl':
    print('user::rwx\\ngroup::r-x\\nother::---')
elif name == 'setfacl':
    pass
elif name == 'runuser':
    if os.environ.get('SNAKEWEB_TEST_UNREADABLE'):
        sys.exit(1)
    sys.exit(subprocess.run(args[args.index('--') + 1:]).returncode)
elif name == 'systemctl':
    if args[0] == 'is-active':
        if args[-1] == 'snake-web.service':
            sys.exit(3 if os.environ.get('SNAKEWEB_TEST_STOPPED') else 0)
        sys.exit(0 if running.exists() else 3)
    if args[0] == 'start':
        if os.environ.get('SNAKEWEB_TEST_START_FAIL'):
            sys.exit(9)
        running.touch()
    if args[0] == 'stop':
        running.unlink(missing_ok=True)
elif name == 'caddy':
    if args[0] == 'validate':
        candidate = Path(args[args.index('--config') + 1])
        (root / 'validated.Caddyfile').write_text(candidate.read_text())
    if os.environ.get('SNAKEWEB_TEST_CADDY_FAIL') == args[0]:
        sys.exit(9)
elif name == 'curl':
    if os.environ.get('SNAKEWEB_TEST_HTTP_FAIL'):
        sys.exit(22)
elif name == 'timeout':
    sys.exit(subprocess.run(args[1:]).returncode)
else:
    sys.exit(f'Unexpected command: {name} {args}')
'''


class NeuromancerDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_installation.InstallationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.caddy = f.root / 'etc/caddy'
        self.config = self.caddy / 'Caddyfile'
        self.site = self.caddy / 'snake-web.caddy'
        f.home.mkdir(mode=0o750)
        public = f.home / 'public'
        public.mkdir(mode=0o755)
        (public / 'live.json').write_text('{"games": []}\n')
        (public / 'score-distribution.gif').write_bytes(b'GIF89a existing histogram')
        f.config.mkdir(mode=0o700)
        self.environment = f.config / 'snake-web.env'
        self.environment.write_text('SNAKE_LAB_ENDPOINT=tcp://127.0.0.1:41970\n')
        self.environment.chmod(0o600)
        self.credentials = f.config / 'database.env'
        self.credentials.write_text('private reader credentials\n')
        self.credentials.chmod(0o600)
        publisher = f.deployed / 'snakewebcode/interface/StaticPublisher.py'
        publisher.parent.mkdir(parents=True)
        publisher.write_text('# installed publisher\n')
        self.backups = f.root / 'var/backups'
        self.backups.mkdir()
        script = f.checkout / 'scripts/deploy-neuromancer-caddy.sh'
        script.write_text(script.read_text().replace('/var/backups', str(self.backups)))
        self.template = f.checkout / 'systemd/Caddyfile.snake-neuromancer'
        self.template.write_text(self.template.read_text().replace('/var/lib/snake-web', str(f.home)))
        for name in ('hostname', 'apt-get', 'getfacl', 'setfacl', 'runuser',
                     'systemctl', 'caddy', 'curl', 'timeout'):
            target = f.bin / name
            target.write_text('#!' + sys.executable + '\n' + STUB)
            target.chmod(0o755)
        python = f.bin / 'python3'
        python.unlink()
        python.symlink_to(sys.executable)

    def run_script(self, **env):
        return self.fixture.run_script('deploy-neuromancer-caddy.sh', **env)

    def test_first_install_preserves_publisher_and_installs_readable_lan_site(self):
        saved = {p: (p.read_bytes(), p.stat().st_mode) for p in (
            self.environment, self.credentials, *self.fixture.home.joinpath('public').iterdir())}
        result = self.run_script(umask=0o077)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.site.read_bytes(), self.template.read_bytes())
        self.assertIn(f'import {self.site}\n', self.config.read_text())
        for path in (self.config, self.site):
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)
        for path, state in saved.items():
            self.assertEqual((path.read_bytes(), path.stat().st_mode), state)
        backup = next(self.backups.iterdir())
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
        self.assertIn(':80 {', (backup / 'Caddyfile').read_text())
        self.assertTrue((backup / 'service-home.acl').is_file())
        commands = self.fixture.commands()
        self.assertIn(['apt-get', 'install', '-y', '--no-install-recommends', 'caddy', 'acl', 'curl'], commands)
        self.assertIn(['setfacl', '-m', 'u:caddy:--x', str(self.fixture.home)], commands)
        self.assertIn(['systemctl', 'start', 'caddy.service'], commands)
        self.assertIn(['systemctl', 'enable', 'caddy.service'], commands)
        self.assertEqual(len([c for c in commands if c[0] == 'curl']), 2)
        self.assertFalse(any('snake-web.service' in c and c[1] != 'is-active' for c in commands))
        self.assertFalse(any(c[0] in ('mariadb', 'systemd-run') for c in commands))

    def test_repeated_install_preserves_other_sites_and_reloads_without_duplicate_import(self):
        self.caddy.mkdir()
        other = self.caddy / 'other.caddy'
        other.write_text('http://:9090 {\n respond "other service"\n}\n')
        original = f'import {other}\n'
        self.config.write_text(original)
        (self.fixture.root / 'caddy-running').touch()
        for _ in range(2):
            result = self.run_script()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.config.read_text(), original + f'import {self.site}\n')
        self.assertEqual(other.read_text(), 'http://:9090 {\n respond "other service"\n}\n')
        self.assertIn(original, (self.fixture.root / 'validated.Caddyfile').read_text())
        commands = self.fixture.commands()
        self.assertEqual(len([c for c in commands if c[:2] == ['caddy', 'reload']]), 2)
        self.assertNotIn(['systemctl', 'start', 'caddy.service'], commands)

    def test_validation_failure_preserves_existing_configuration(self):
        self.caddy.mkdir()
        self.config.write_text('# existing main config\n')
        self.site.write_text('# existing Snake site\n')
        result = self.run_script(SNAKEWEB_TEST_CADDY_FAIL='validate')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.config.read_text(), '# existing main config\n')
        self.assertEqual(self.site.read_text(), '# existing Snake site\n')
        self.assertFalse(any(c[:2] in (['caddy', 'reload'], ['systemctl', 'start'])
                             for c in self.fixture.commands()))
        self.assertIn('Deployment incomplete', result.stderr)

    def test_reload_failure_restores_configuration_and_attempts_service_recovery(self):
        self.caddy.mkdir()
        self.config.write_text(f'# existing config\nimport {self.site}\n')
        self.site.write_text('# existing Snake site\n')
        original = self.config.read_bytes()
        (self.fixture.root / 'caddy-running').touch()
        result = self.run_script(SNAKEWEB_TEST_CADDY_FAIL='reload')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(self.site.read_text(), '# existing Snake site\n')
        self.assertEqual(len([c for c in self.fixture.commands() if c[:2] == ['caddy', 'reload']]), 2)

    def test_start_failure_removes_new_site_and_restores_package_configuration(self):
        result = self.run_script(SNAKEWEB_TEST_START_FAIL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.site.exists())
        self.assertNotIn('import ', self.config.read_text())
        self.assertIn(['systemctl', 'stop', 'caddy.service'], self.fixture.commands())

    def test_wrong_host_stopped_publisher_or_custom_root_refused_before_packages(self):
        for env in ({'SNAKEWEB_TEST_HOST': 'wintermute'}, {'SNAKEWEB_TEST_STOPPED': '1'}):
            result = self.run_script(**env)
            self.assertNotEqual(result.returncode, 0)
        self.environment.write_text('PUBLISH_DIRECTORY=/custom/public\n')
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('requires PUBLISH_DIRECTORY=', result.stderr)
        self.assertEqual(list(self.backups.iterdir()), [])
        self.assertFalse(any(c[0] == 'apt-get' for c in self.fixture.commands()))

    def test_symlinked_configuration_refused_before_packages(self):
        self.caddy.mkdir()
        self.config.symlink_to(self.environment)
        original = self.environment.read_bytes()
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.environment.read_bytes(), original)
        self.assertFalse(any(c[0] == 'apt-get' for c in self.fixture.commands()))

    def test_unreadable_artifacts_stop_before_installing_site(self):
        result = self.run_script(SNAKEWEB_TEST_UNREADABLE='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.site.exists())

    def test_package_and_http_failures_report_partial_setup(self):
        result = self.run_script(SNAKEWEB_TEST_APT_FAIL='1')
        self.assertEqual(result.returncode, 8, result.stdout + result.stderr)
        self.assertFalse(self.site.exists())
        self.assertIn('Deployment incomplete', result.stderr)
        result = self.run_script(SNAKEWEB_TEST_HTTP_FAIL='1')
        self.assertEqual(result.returncode, 22, result.stdout + result.stderr)
        self.assertTrue(self.site.exists())
        self.assertIn('Deployment incomplete', result.stderr)
        self.assertNotIn('LAN server configured.', result.stdout)
