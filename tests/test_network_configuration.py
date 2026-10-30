"""Verify listener defaults, deployment overrides, and configuration lifecycle."""

import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from snakewebcode.constants.DSnakeWebCode import DSnakeWebCode
from snakewebcode.interface.Configuration import Configuration
from snakewebcode.interface.Network import Network


class NetworkConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='snakeweb-network-')
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'conf/snakewebcode.json'
        self.addCleanup(Network._bindings.cache_clear)

    def write(self, values):
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(values))

    def test_cmdb_listener_is_literal_and_matches_default_resolution(self):
        source = Path(__file__).resolve().parents[1] / 'snakewebcode/constants/DSnakeWebCode.py'
        application = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.ClassDef))
        declaration = next(n.value for n in application.body if isinstance(n, ast.AnnAssign)
                           and n.target.id == 'CMDB_NETWORK')
        self.assertEqual(ast.literal_eval(declaration), (('http', '192.168.0.106', 8080),))
        self.assertEqual(Network.binding('http', self.path), ('192.168.0.106', 8080))
        self.assertEqual(Configuration.path(), Path('/opt/prod/snakewebcode/conf/snakewebcode.json'))

    def test_partial_overrides_inherit_release_defaults(self):
        self.write({'network': {'http': {'port': 18080}}})
        with patch.object(DSnakeWebCode, 'CMDB_NETWORK', (('http', '192.0.2.20', 18000),)):
            self.assertEqual(Network.binding('http', self.path), ('192.0.2.20', 18080))

    def test_explicit_values_survive_changed_defaults(self):
        self.write({'network': {'http': {'interface': '192.168.0.106', 'port': 8080}}})
        with patch.object(DSnakeWebCode, 'CMDB_NETWORK', (('http', '192.0.2.20', 18000),)):
            self.assertEqual(Network.binding('http', self.path), ('192.168.0.106', 8080))

    def test_empty_and_missing_groups_use_defaults(self):
        for values in ({}, {'network': {}}, {'network': {'http': {}}}):
            with self.subTest(values=values):
                self.write(values)
                self.assertEqual(Configuration.read(self.path, DSnakeWebCode.CMDB_NETWORK),
                                 {'http': ('192.168.0.106', 8080)})

    def test_destination_uses_loopback_only_for_wildcard_binding(self):
        for interface, expected in (('0.0.0.0', '127.0.0.1'), ('192.0.2.20', '192.0.2.20')):
            with self.subTest(interface=interface):
                self.write({'network': {'http': {'interface': interface}}})
                Network._bindings.cache_clear()
                self.assertEqual(Network.destination('http', self.path), (expected, 8080))

    def test_invalid_settings_report_path_and_setting(self):
        cases = [([], 'object'), ({'unknown': {}}, 'network'),
                 ({'network': []}, 'network'),
                 ({'network': {'unknown': {}}}, 'unknown network use'),
                 ({'network': {'http': {'host': '127.0.0.1'}}}, 'network.http'),
                 ({'network': {'http': []}}, 'network.http')]
        for interface in ('neuromancer', '::1', '999.0.0.1', None, 42):
            cases.append(({'network': {'http': {'interface': interface}}}, 'network.http.interface'))
        for port in (True, False, 0, 65536, '8080', 1.5, None):
            cases.append(({'network': {'http': {'port': port}}}, 'network.http.port'))
        for values, message in cases:
            with self.subTest(values=values):
                self.write(values)
                with self.assertRaises(ValueError) as error:
                    Configuration.read(self.path, DSnakeWebCode.CMDB_NETWORK)
                self.assertIn(str(self.path), str(error.exception))
                self.assertIn(message, str(error.exception))

    def test_malformed_and_unreadable_files_do_not_fall_back(self):
        self.path.parent.mkdir()
        self.path.write_text('{broken')
        with self.assertRaisesRegex(ValueError, 'invalid JSON'):
            Network.binding('http', self.path)
        with patch.object(Path, 'read_text', side_effect=PermissionError('unreadable')):
            with self.assertRaises(PermissionError):
                Network.binding('http', self.path)

    def test_install_creates_readable_defaults_and_preserves_existing_overrides(self):
        Configuration.install(self.path)
        self.assertEqual(json.loads(self.path.read_text()), {'network': {
            'http': {'interface': '192.168.0.106', 'port': 8080}}})
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o644)
        self.write({'network': {'http': {'port': 18080}}})
        before = self.path.read_bytes(), self.path.stat().st_mode
        Configuration.install(self.path)
        self.assertEqual((self.path.read_bytes(), self.path.stat().st_mode), before)

    def test_install_rejects_symlinks_without_changing_target(self):
        target = self.path.parent.parent / 'saved.json'
        target.write_text('{}')
        self.path.parent.mkdir()
        self.path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            Configuration.install(self.path)
        self.assertEqual(target.read_text(), '{}')

    def test_resolution_is_cached_until_next_process_or_explicit_reset(self):
        self.write({'network': {'http': {'port': 18080}}})
        self.assertEqual(Network.binding('http', self.path)[1], 18080)
        self.write({'network': {'http': {'port': 18081}}})
        self.assertEqual(Network.binding('http', self.path)[1], 18080)
        Network._bindings.cache_clear()
        self.assertEqual(Network.binding('http', self.path)[1], 18081)
