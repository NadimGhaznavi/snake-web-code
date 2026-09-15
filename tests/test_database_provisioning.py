"""Provisioning tests use only an explicitly selected isolated DEV database."""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pymysql


spec = importlib.util.spec_from_file_location(
    'provision_database', Path(__file__).resolve().parents[1] / 'scripts/provision-database.py')
provisioner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provisioner)


class CredentialTests(unittest.TestCase):
    def test_unrelated_file_is_rejected_and_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'database.env'
            original = 'DB_USER=snake_lab\nDB_PASSWORD=existing\n'
            path.write_text(original)
            path.chmod(0o600)
            with self.assertRaisesRegex(RuntimeError, 'not managed by Snake Web'):
                provisioner.load_credentials(path)
            self.assertEqual(path.read_text(), original)

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'other.env'
            target.write_text('existing')
            path = Path(directory) / 'database.env'
            path.symlink_to(target)
            with self.assertRaisesRegex(RuntimeError, 'regular file'):
                provisioner.load_credentials(path)



class MigrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.legacy = Path(temp.name) / 'old/database.env'
        self.destination = Path(temp.name) / 'new/database.env'
        self.legacy.parent.mkdir()
        self.original = (provisioner.MARKER + '\nDB_HOST=localhost\n'
                         'DB_SOCKET=/tmp/snake-web-test.sock\nDB_NAME=snakelab\n'
                         'DB_USER=snake_web_reader\nDB_PASSWORD=' + 'a' * 64 + '\n')
        self.legacy.write_text(self.original)
        self.legacy.chmod(0o600)
        self.admin = MagicMock()
        self.admin.cursor.return_value.__enter__.return_value.fetchone.return_value = (1,)

    def provision(self):
        with patch.object(provisioner.pymysql, 'connect', return_value=MagicMock()):
            provisioner.provision(self.admin, '/tmp/snake-web-test.sock',
                                  self.destination, self.legacy)

    def test_migration_and_rerun_preserve_password_and_permissions(self):
        self.provision()
        self.assertEqual(self.destination.read_text(), self.original)
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.destination.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.legacy.read_text(), self.original)
        self.legacy.write_text('unrelated legacy file')
        self.provision()
        self.assertEqual(self.destination.read_text(), self.original)
        self.assertEqual(self.legacy.read_text(), 'unrelated legacy file')

    def test_foreign_legacy_credentials_are_left_untouched(self):
        self.legacy.write_text('DB_USER=snake_lab\n')
        with self.assertRaisesRegex(RuntimeError, 'not managed by Snake Web'):
            self.provision()
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.legacy.read_text(), 'DB_USER=snake_lab\n')
        self.assertEqual(self.admin.cursor.return_value.__enter__.return_value.execute.call_count, 2)

    def test_socket_mismatch_does_not_copy_or_change_account(self):
        self.legacy.write_text(self.original.replace('snake-web-test.sock', 'other.sock'))
        with self.assertRaisesRegex(RuntimeError, 'Saved socket differs'):
            self.provision()
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.admin.cursor.return_value.__enter__.return_value.execute.call_count, 2)


@unittest.skipUnless(os.environ.get('SNAKE_WEB_PROVISION_TEST_SOCKET'), 'requires isolated provisioning DB')
class ProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.socket = os.environ['SNAKE_WEB_PROVISION_TEST_SOCKET']
        if not self.socket.startswith('/tmp/snake-web-'):
            self.fail('Provisioning tests require a dedicated /tmp/snake-web-* socket')
        self.admin = pymysql.connect(unix_socket=self.socket, user='root', autocommit=True)
        self.addCleanup(self.admin.close)
        with self.admin.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM mysql.user WHERE User='snake_web_reader'")
            self.assertEqual(cursor.fetchone()[0], 0, 'Use an isolated DB without an existing reader account')
        self.addCleanup(self.drop_reader)
        self.temp = tempfile.TemporaryDirectory(prefix='snake-web-db-config-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'config/database.env'

    def drop_reader(self):
        with self.admin.cursor() as cursor:
            cursor.execute("DROP USER IF EXISTS 'snake_web_reader'@'localhost'")

    def reader(self):
        credentials = provisioner.load_credentials(self.path)
        return pymysql.connect(unix_socket=self.socket, user=credentials['DB_USER'],
                               password=credentials['DB_PASSWORD'], database=credentials['DB_NAME'])

    def assert_reader_privileges(self):
        with self.reader() as reader:
            with reader.cursor() as cursor:
                cursor.execute('SELECT MAX(high_score) FROM simulation_runs')
                self.assertEqual(cursor.fetchone()[0], 49)
                # Neither statement changes source data even if permissions regress.
                for sql in ('UPDATE simulation_runs SET high_score=0 WHERE id=-1',
                            'SELECT * FROM configurations LIMIT 0',
                            'SELECT * FROM mysql.user LIMIT 0'):
                    with self.assertRaises(pymysql.err.OperationalError) as denied:
                        cursor.execute(sql)
                    self.assertIn(denied.exception.args[0], (1142, 1143))

    def test_install_and_upgrade_preserve_password_and_enforce_select_only(self):
        provisioner.provision(self.admin, self.socket, self.path)
        original = self.path.read_bytes()
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assert_reader_privileges()
        with self.admin.cursor() as cursor:
            cursor.execute("GRANT INSERT ON snakelab.simulation_runs TO 'snake_web_reader'@'localhost'")
        provisioner.provision(self.admin, self.socket, self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assert_reader_privileges()
        with self.reader() as reader:
            with reader.cursor() as cursor:
                cursor.execute('SHOW GRANTS')
                grants = [row[0] for row in cursor.fetchall()]
                self.assertEqual(len(grants), 2)
                self.assertTrue(any('GRANT SELECT ON `snakelab`.`simulation_runs`' in row for row in grants))
                self.assertFalse(any('INSERT' in row for row in grants))

    def test_foreign_file_does_not_create_account(self):
        self.path.parent.mkdir()
        self.path.write_text('DB_USER=snake_lab\nDB_PASSWORD=existing\n')
        self.path.chmod(0o600)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'not managed by Snake Web'):
            provisioner.provision(self.admin, self.socket, self.path)
        self.assertEqual(self.path.read_bytes(), before)
        with self.admin.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM mysql.user WHERE User='snake_web_reader'")
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_existing_account_without_file_is_not_taken_over(self):
        with self.admin.cursor() as cursor:
            cursor.execute("CREATE USER 'snake_web_reader'@'localhost' IDENTIFIED BY 'existing-dev-only'")
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            provisioner.provision(self.admin, self.socket, self.path)
        self.assertFalse(self.path.exists())
        with pymysql.connect(unix_socket=self.socket, user='snake_web_reader', password='existing-dev-only'):
            pass

    def test_saved_password_recovers_missing_account(self):
        provisioner.provision(self.admin, self.socket, self.path)
        original = self.path.read_bytes()
        self.drop_reader()
        provisioner.provision(self.admin, self.socket, self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assert_reader_privileges()


if __name__ == '__main__':
    unittest.main()
