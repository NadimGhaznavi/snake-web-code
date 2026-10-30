"""Run deployment scripts against temporary paths and simulated OS services."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
OS_STUB = '''import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(os.environ["SNAKEWEB_TEST_ROOT"])
name, args = Path(sys.argv[0]).name, sys.argv[1:]
with (root / "commands.jsonl").open("a") as stream:
    stream.write(json.dumps([name, *args]) + "\\n")
if name == "getent":
    print(f"snake-web:x:123:123::{root}/var/lib/snake-web:/bin/bash")
elif name == "id":
    print("snake-web")
elif name == "install":
    filtered = []
    iterator = iter(args)
    for arg in iterator:
        if arg in ("-o", "-g"):
            next(iterator)
        else:
            filtered.append(arg)
    sys.exit(subprocess.run(["/usr/bin/install", *filtered]).returncode)
elif name == "python3" and args[:2] == ["-m", "venv"]:
    target = Path(args[2]) / "bin/python"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(__file__, target)
elif name == "python" and args[0].endswith("provision-database.py"):
    if os.environ.get("SNAKEWEB_TEST_PROVISION_FAIL"):
        sys.exit(7)
    credentials = root / "etc/snake-web/database.env"
    if not credentials.exists():
        credentials.write_text("saved reader credentials\\n")
        credentials.chmod(0o600)
elif name == "python" and args[:2] == ["-m", "pip"]:
    pass
elif name in ("systemctl", "systemd-run"):
    pass
else:
    sys.exit(f"Unexpected OS command: {name} {args}")
'''


class InstallationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="snakewebcode-install-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.checkout = self.root / "checkout with spaces"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        stub = "#!" + sys.executable + "\n" + OS_STUB
        for name in ("getent", "id", "install", "python3", "systemctl", "systemd-run",
                     "groupadd", "useradd", "usermod", "git", "mariadb"):
            command = self.bin / name
            command.write_text(stub)
            command.chmod(0o755)
        for directory in ("scripts", "systemd", "snakewebcode"):
            shutil.copytree(ROOT / directory, self.checkout / directory,
                            ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(ROOT / "requirements.txt", self.checkout / "requirements.txt")
        for script in (self.checkout / "scripts").glob("*.sh"):
            # Redirect only the fixture copies; no production paths are written.
            source = script.read_text().replace("${EUID}", "0")
            source = source.replace("/usr/bin/python3", str(self.bin / "python3"))
            source = re.sub(r"/(?:etc|opt|var/lib|run/systemd/system)\b",
                            lambda match: str(self.root) + match[0], source)
            script.write_text(source)
        (self.root / "run/systemd/system").mkdir(parents=True)
        (self.root / "etc/systemd/system").mkdir(parents=True)
        (self.root / "var/lib").mkdir(parents=True)
        self.home = self.root / "var/lib/snake-web"
        self.config = self.root / "etc/snake-web"
        self.deployed = self.root / "opt/prod/snakewebcode"
        self.unit = self.root / "etc/systemd/system/snake-web.service"
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        SNAKEWEB_TEST_ROOT=str(self.root))

    def run_script(self, name, **env):
        return subprocess.run(["/bin/bash", str(self.checkout / "scripts" / name)],
                              cwd=self.root, env=dict(self.env, **env),
                              capture_output=True, text=True, timeout=20)

    def commands(self):
        return [json.loads(line) for line in (self.root / "commands.jsonl").read_text().splitlines()]

    def test_install_upgrade_and_uninstall_preserve_configuration_and_state(self):
        result = self.run_script("install.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        source = self.checkout / "snakewebcode"
        for path in source.rglob("*"):
            if path.is_file():
                deployed = self.deployed / "snakewebcode" / path.relative_to(source)
                self.assertEqual(deployed.read_bytes(), path.read_bytes())
                self.assertEqual(deployed.stat().st_mode & 0o777, 0o644)
        constants = self.deployed / "snakewebcode/constants/DSnakeWebCode.py"
        for path in (self.deployed, constants.parent.parent, constants.parent):
            self.assertEqual(path.stat().st_mode & 0o777, 0o755)
        self.assertIn("-m snakewebcode.server", self.unit.read_text())
        self.assertIn("WorkingDirectory=/opt/prod/snakewebcode", self.unit.read_text())
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.home.stat().st_mode & 0o777, 0o750)
        environment = self.config / "snake-web.env"
        environment.write_text("PUBLISH_CHECKOUT=/custom/publishing/path\n")
        credentials = self.config / "database.env"
        key = self.home / ".ssh/id_ed25519"
        key.parent.mkdir(mode=0o700)
        key.write_text("private test key\n")
        key.chmod(0o600)
        cursor = self.home / "site/reports/data/event-export.json"
        cursor.parent.mkdir(parents=True)
        cursor.write_text('{"last_event_id":123}\n')
        public = self.home / 'public/game-one.gif'
        public.parent.mkdir()
        public.write_bytes(b'GIF89a saved public artifact')
        legacy = self.root / "opt/prod/snake-web/old-code"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("previous installation\n")
        saved = {path: (path.read_bytes(), path.stat().st_mode) for path in
                 (environment, credentials, key, cursor, public, legacy)}
        retired = [self.deployed / 'snakewebcode' / name for name in (
            'interface/GitPublisher.py', 'activity/PublishStatus.py',
            'activity/reports/event-log.html', 'entity/ExperimentStatus.py')]
        for path in retired:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('retired application code\n')
        constants.write_text('VERSION = "old"\n')
        result = self.run_script("upgrade.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(constants.read_bytes(), (ROOT / "snakewebcode/constants/DSnakeWebCode.py").read_bytes())
        self.assertTrue(all(not path.exists() for path in retired))
        for path, (content, mode) in saved.items():
            self.assertEqual((path.read_bytes(), path.stat().st_mode), (content, mode))
        installs = [command for command in self.commands() if command[0] == "install"]
        self.assertTrue(all("-o" in command and "-g" in command for command in installs))
        service_commands = [command[1:] for command in self.commands() if command[0] == "systemctl"]
        self.assertEqual(service_commands, [
            ["daemon-reload"], ["enable", "snake-web.service"],
            ["restart", "snake-web.service"], ["is-active", "--quiet", "snake-web.service"],
        ] * 2)
        result = self.run_script("uninstall.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.deployed.exists())
        self.assertFalse(self.unit.exists())
        for path, (content, mode) in saved.items():
            self.assertEqual((path.read_bytes(), path.stat().st_mode), (content, mode))

    def test_provisioning_failure_leaves_existing_service_unit_untouched(self):
        self.unit.write_text("previous service unit\n")
        retired = self.deployed / 'snakewebcode/activity/reports/event-log.html'
        retired.parent.mkdir(parents=True)
        retired.write_text('previous report asset\n')
        result = self.run_script("upgrade.sh", SNAKEWEB_TEST_PROVISION_FAIL="1")
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertTrue((self.deployed / "snakewebcode/constants/DSnakeWebCode.py").is_file())
        self.assertEqual(self.unit.read_text(), "previous service unit\n")
        self.assertEqual(retired.read_text(), 'previous report asset\n')
        self.assertFalse(any(command[0] == "systemctl" for command in self.commands()))

    def test_manual_publication_uses_new_code_with_existing_identity_and_configuration(self):
        result = self.run_script("push-now.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        command = self.commands()[-1]
        self.assertEqual(command[0], "systemd-run")
        self.assertIn("--uid=snake-web", command)
        self.assertIn("--working-directory=" + str(self.deployed), command)
        self.assertIn("--property=EnvironmentFile=" + str(self.config / "database.env"), command)
        self.assertEqual(command[-4:], [str(self.deployed / "venv/bin/python"),
                                       "-m", "snakewebcode.server", "--once"])
