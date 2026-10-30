"""Exercise the one-time deployment against copied files and simulated services."""

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
if name == 'hostname':
    print(os.environ.get('SNAKEWEB_TEST_HOST', 'wintermute'))
elif name == 'getfacl':
    print('user::rwx\\ngroup::r-x\\nother::---')
elif name == 'caddy':
    if args[0] == 'validate':
        candidate = Path(args[args.index('--config') + 1])
        (root / 'validated.Caddyfile').write_text(candidate.read_text())
    if os.environ.get('SNAKEWEB_TEST_CADDY_FAIL') == args[0]:
        sys.exit(9)
elif name == 'systemctl':
    if args[0] == 'is-active' and os.environ.get('SNAKEWEB_TEST_STOPPED') == args[-1]:
        sys.exit(3)
elif name == 'systemd-run':
    if os.environ.get('SNAKEWEB_TEST_PUBLICATION_FAIL'):
        sys.exit(7)
elif name == 'timeout':
    sys.exit(subprocess.run(args[1:]).returncode)
elif name in ('setfacl', 'runuser'):
    pass
else:
    sys.exit(f'Unexpected command: {name} {args}')
'''


class WintermuteDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_installation.InstallationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.root = f.root
        self.caddy = f.root / 'etc/caddy'
        self.caddy.mkdir()
        self.config = self.caddy / 'Caddyfile'
        self.mycount = self.caddy / 'mycount.caddy'
        self.mycount.write_text('https://count.osoyalce.com {\n reverse_proxy 127.0.0.1:36666\n}\n')
        self.original = f':80 {{\n root * /usr/share/caddy\n file_server\n}}\nimport {self.mycount}\n'
        self.config.write_text(self.original)
        f.home.mkdir()
        f.config.mkdir(parents=True)
        self.environment = f.config / 'snake-web.env'
        self.settings = 'SNAKE_LAB_ENDPOINT=tcp://127.0.0.1:41970\n'
        self.environment.write_text(self.settings)
        self.environment.chmod(0o600)
        publisher = f.deployed / 'snakewebcode/interface/StaticPublisher.py'
        publisher.parent.mkdir(parents=True)
        publisher.write_text('# installed static publisher\n')
        self.backups = f.root / 'var/backups'
        self.backups.mkdir()
        script = f.checkout / 'scripts/deploy-wintermute-caddy.sh'
        script.write_text(script.read_text().replace('/var/backups', str(self.backups)))
        for name in ('hostname', 'caddy', 'getfacl', 'setfacl', 'runuser',
                     'systemctl', 'systemd-run', 'timeout'):
            target = f.bin / name
            target.write_text('#!' + sys.executable + '\n' + STUB)
            target.chmod(0o755)
        # The deployment's inline Python is real; only external OS services are stubbed.
        python = f.bin / 'python3'
        python.unlink()
        python.symlink_to(sys.executable)

    def run_script(self, **env):
        return self.fixture.run_script('deploy-wintermute-caddy.sh', **env)

    def test_adds_separate_site_preserves_mycount_and_runs_publication(self):
        before = self.mycount.read_bytes()
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.mycount.read_bytes(), before)
        site = self.caddy / 'snake-web.caddy'
        self.assertIn('Cache-Control "no-store"', site.read_text())
        self.assertEqual(self.config.read_text(), self.original + f'import {site}\n')
        self.assertIn(self.settings, self.environment.read_text())
        self.assertEqual(self.environment.stat().st_mode & 0o777, 0o600)
        self.assertIn('PUBLISH_DIRECTORY=' + str(self.fixture.home / 'public'), self.environment.read_text())
        self.assertEqual((self.fixture.home / 'public').stat().st_mode & 0o777, 0o755)
        backup = next(self.backups.iterdir())
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
        self.assertEqual((backup / 'Caddyfile').read_text(), self.original)
        self.assertEqual((backup / 'snake-web.env').read_text(), self.settings)
        commands = self.fixture.commands()
        self.assertIn(['setfacl', '-m', 'u:caddy:--x', str(self.fixture.home)], commands)
        self.assertIn(['systemctl', 'restart', 'snake-web.service'], commands)
        self.assertTrue(any(c[:2] == ['caddy', 'reload'] for c in commands))
        self.assertTrue(any(c[0] == 'systemd-run' for c in commands))
        self.assertFalse(any(c[:2] in (['systemctl', 'reload'], ['systemctl', 'start']) for c in commands))
        self.assertIn(f'import {self.mycount}', (self.root / 'validated.Caddyfile').read_text())

    def test_repeat_does_not_duplicate_import_or_directory_setting(self):
        for _ in range(2):
            result = self.run_script()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.config.read_text().count('import ' + str(self.caddy / 'snake-web.caddy')), 1)
        self.assertEqual(self.environment.read_text().count('PUBLISH_DIRECTORY='), 1)

    def test_validation_failure_leaves_configuration_and_services_untouched(self):
        result = self.run_script(SNAKEWEB_TEST_CADDY_FAIL='validate')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.config.read_text(), self.original)
        self.assertEqual(self.environment.read_text(), self.settings)
        self.assertFalse((self.caddy / 'snake-web.caddy').exists())
        self.assertFalse(any(c[:2] == ['systemctl', 'restart'] for c in self.fixture.commands()))

    def test_reload_failure_restores_existing_caddy_site(self):
        site = self.caddy / 'snake-web.caddy'
        site.write_text('# previous Snake site\n')
        result = self.run_script(SNAKEWEB_TEST_CADDY_FAIL='reload')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.config.read_text(), self.original)
        self.assertEqual(site.read_text(), '# previous Snake site\n')
        self.assertEqual(self.environment.read_text(), self.settings)

    def test_publication_failure_reports_partial_deployment(self):
        result = self.run_script(SNAKEWEB_TEST_PUBLICATION_FAIL='1')
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertIn('Deployment incomplete', result.stderr)
        self.assertNotIn('Static publication configured.', result.stdout)
        self.assertTrue((self.caddy / 'snake-web.caddy').is_file())
        self.assertIn('PUBLISH_DIRECTORY=', self.environment.read_text())

    def test_wrong_host_or_stopped_service_refused_before_changes(self):
        for env in ({'SNAKEWEB_TEST_HOST': 'elsewhere'}, {'SNAKEWEB_TEST_STOPPED': 'snake-web.service'}):
            result = self.run_script(**env)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(self.backups.iterdir()), [])
            self.assertFalse((self.fixture.home / 'public').exists())
