"""Real Git integration tests; every repository and remote is temporary."""

import fcntl
import socket
from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pymysql
from unittest.mock import Mock, patch

from snake_web.activity.AppDb import AppDb
from snake_web.activity.PublishStatus import PublishStatus, render_status
from snake_web.interface.DbMgr import DbMgr
from snake_web.interface.GitPublisher import GitPublisher
from snake_web.entity.ExperimentStatus import ExperimentStatus
from snake_web import server


ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / 'tests/fixtures/status.md').read_text()
STATUS = ExperimentStatus(51, 39, 190, 26)


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='snake-web-git-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / 'remote.git'
        self.repo = self.root / 'site'
        self.git(self.root, 'init', '--bare', '--initial-branch=main', str(self.remote))
        self.git(self.root, 'clone', str(self.remote), str(self.repo))
        self.git(self.repo, 'config', 'user.name', 'DEV Test')
        self.git(self.repo, 'config', 'user.email', 'dev-test@example.invalid')
        self.page = self.repo / 'index.md'
        self.page.write_text(PAGE)
        self.git(self.repo, 'add', '.')
        self.git(self.repo, 'commit', '-m', 'Fixture')
        self.git(self.repo, 'push', 'origin', 'main')
        self.publisher = GitPublisher(self.repo)
        self.appdb = Mock()
        self.appdb.get_experiment_status.return_value = STATUS
        self.appdb.get_highscore_history.return_value = []
        self.activity = PublishStatus(self.appdb, self.publisher)

    def git(self, directory, *args):
        return subprocess.run(['git', '-C', str(directory), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def remote_page(self):
        return self.git(self.remote, 'show', 'main:index.md')

    def test_publish_and_no_duplicate_commit(self):
        self.assertIn('published', self.activity.run())
        self.assertEqual(self.remote_page(), render_status(STATUS, socket.gethostname()).strip())
        head = self.git(self.remote, 'rev-parse', 'main')
        with patch.object(self.publisher, '_git', wraps=self.publisher._git) as git:
            self.assertIn('unchanged', self.activity.run())
            self.assertFalse(any(call.args[0] == 'push' for call in git.call_args_list))
        self.assertEqual(head, self.git(self.remote, 'rev-parse', 'main'))
        self.assertEqual(self.git(self.repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').splitlines(), sorted(self.publisher.OWNED_PATHS))

    def test_history_appends_and_preserves_lower_seed_baselines(self):
        self.appdb.get_highscore_history.return_value = [
            dict(event_id=10, simulations=2, score=51, seed=7)]
        self.activity.run()
        first = (self.repo / self.publisher.HISTORY_PATH).read_text()
        self.appdb.get_highscore_history.assert_called_with(0)
        self.appdb.get_highscore_history.return_value = [
            dict(event_id=20, simulations=5, score=12, seed=8)]
        self.activity.run()
        self.appdb.get_highscore_history.assert_called_with(10)
        data = self.git(self.remote, 'show', 'main:' + self.publisher.HISTORY_PATH)
        self.assertEqual(data, first + '20,5,12,8')
        self.appdb.get_highscore_history.return_value = []
        self.assertIn('unchanged', self.activity.run())
        self.appdb.get_highscore_history.assert_called_with(20)

    def test_report_paths_refuse_symlinks_before_homepage_changes(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.repo / 'reports').symlink_to(outside, target_is_directory=True)
        self.git(self.repo, 'add', 'reports')
        self.git(self.repo, 'commit', '-m', 'Symlink report directory')
        self.git(self.repo, 'push', 'origin', 'main')
        with self.assertRaisesRegex(RuntimeError, 'without symlinks'):
            self.activity.run()
        self.assertEqual(self.page.read_text(), PAGE)
        self.assertEqual(list(outside.iterdir()), [])

    def test_other_metrics_publish_without_a_new_all_time_highscore(self):
        self.activity.run()
        head = self.git(self.remote, 'rev-parse', 'main')
        self.appdb.get_experiment_status.return_value = replace(STATUS, simulations_submitted=191,
                                                               experiment_cycles=27)
        self.assertIn('published', self.activity.run())
        self.assertNotEqual(head, self.git(self.remote, 'rev-parse', 'main'))
        self.assertIn('Simulations Submitted: 191', self.remote_page())
        self.assertIn('Experiment Cycles: 27', self.remote_page())

    def test_existing_contents_are_replaced(self):
        for content in (b'', b'# Custom homepage\n',
                        b'- Current highscore: 1\n- Current highscore: 2\n',
                        b'\xff\xfe'):
            with self.subTest(content=content):
                self.page.write_bytes(content)
                self.git(self.repo, 'add', 'index.md')
                self.git(self.repo, 'commit', '-m', 'Replace homepage')
                self.git(self.repo, 'push', 'origin', 'main')
                self.activity.run()
                self.assertEqual(self.page.read_text(), render_status(STATUS, socket.gethostname()))
                self.assertEqual(self.remote_page(), render_status(STATUS, socket.gethostname()).strip())

    def test_missing_homepage_is_not_created(self):
        self.git(self.repo, 'rm', 'index.md')
        self.git(self.repo, 'commit', '-m', 'Remove homepage')
        self.git(self.repo, 'push', 'origin', 'main')
        head = self.git(self.remote, 'rev-parse', 'main')
        with self.assertRaisesRegex(RuntimeError, 'must be an existing file'):
            self.activity.run()
        self.assertFalse(self.page.exists())
        self.assertEqual(self.git(self.remote, 'rev-parse', 'main'), head)

    def test_zero_is_a_score(self):
        self.appdb.get_experiment_status.return_value = replace(STATUS, all_time_highscore=0, current_highscore=0)
        self.activity.run()
        self.assertIn('Current Highscore: 0', self.remote_page())

    def test_no_score_preserves_page_without_git(self):
        self.appdb.get_experiment_status.return_value = replace(STATUS, all_time_highscore=None)
        with patch.object(self.publisher, 'session') as session:
            self.assertIn('No recorded score', self.activity.run())
            session.assert_not_called()
        self.assertEqual(self.page.read_text(), PAGE)

    def test_database_failure_preserves_page(self):
        self.appdb.get_experiment_status.side_effect = RuntimeError('DB unavailable')
        with self.assertRaisesRegex(RuntimeError, 'DB unavailable'):
            self.activity.run()
        self.assertEqual(self.page.read_text(), PAGE)

    def test_dirty_checkout_refused(self):
        (self.repo / 'unrelated.txt').write_text('developer work')
        with self.assertRaisesRegex(RuntimeError, 'must be clean'):
            self.activity.run()
        self.assertEqual(self.page.read_text(), PAGE)

    def test_unrelated_pending_commit_refused(self):
        (self.repo / 'unrelated.txt').write_text('developer work')
        self.git(self.repo, 'add', '.')
        self.git(self.repo, 'commit', '-m', 'Unrelated')
        with self.assertRaisesRegex(RuntimeError, 'only the homepage'):
            self.activity.run()
        self.assertEqual(self.remote_page(), PAGE.strip())

    def test_failed_push_retried_without_duplicate_commit(self):
        hook = self.remote / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        with self.assertRaisesRegex(RuntimeError, 'Git push failed'):
            self.activity.run()
        head = self.git(self.repo, 'rev-parse', 'HEAD')
        hook.unlink()
        self.assertIn('published', self.activity.run())
        self.assertEqual(head, self.git(self.remote, 'rev-parse', 'main'))

    def test_remote_advance_preserved(self):
        other = self.root / 'other'
        self.git(self.root, 'clone', str(self.remote), str(other))
        (other / 'release.txt').write_text('release content')
        self.git(other, 'add', '.')
        self.git(other, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'Release')
        self.git(other, 'push', 'origin', 'main')
        self.activity.run()
        self.assertEqual((self.repo / 'release.txt').read_text(), 'release content')
        self.assertIn('51', self.remote_page())

    def test_diverged_branch_refused(self):
        hook = self.remote / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        with self.assertRaises(RuntimeError):
            self.activity.run()
        hook.unlink()
        other = self.root / 'other'
        self.git(self.root, 'clone', str(self.remote), str(other))
        (other / 'release.txt').write_text('release')
        self.git(other, 'add', '.')
        self.git(other, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'Release')
        self.git(other, 'push', 'origin', 'main')
        with self.assertRaisesRegex(RuntimeError, 'diverged'):
            self.activity.run()
        self.assertEqual(self.remote_page(), PAGE.strip())

    def test_concurrent_publisher_refused(self):
        with (self.repo / '.git/snake-web-publish.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                self.activity.run()

    def test_wrong_branch_refused(self):
        self.git(self.repo, 'switch', '-c', 'dev')
        with self.assertRaisesRegex(RuntimeError, 'must be on main'):
            self.activity.run()

    @unittest.skipUnless(os.environ.get('SNAKE_WEB_TEST_DB_SOCKET'), 'requires restored DEV MariaDB')
    def test_backup_to_remote_via_cli(self):
        env = {**os.environ, 'DB_SOCKET': os.environ['SNAKE_WEB_TEST_DB_SOCKET'],
               'DB_USER': 'root', 'DB_PASSWORD': '', 'DB_NAME': 'snakelab',
               'PUBLISH_CHECKOUT': str(self.repo), 'PUBLISH_BRANCH': 'main'}
        with patch.dict(os.environ, env):
            with DbMgr() as db:
                status = AppDb(db).get_experiment_status()
                score = status.all_time_highscore
                with self.assertRaises(pymysql.err.OperationalError) as rejected:
                    db.query('UPDATE simulation_runs SET high_score = 0 WHERE id = 1')
                self.assertEqual(rejected.exception.args[0], 1792)
        self.assertEqual(score, int(os.environ.get("SNAKE_WEB_TEST_EXPECTED_SCORE", "49")))
        result = subprocess.run([sys.executable, '-m', 'snake_web.server', '--once'],
                                cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.remote_page(), render_status(status, socket.gethostname()).strip())
        result = subprocess.run([sys.executable, '-m', 'snake_web.server', '--once'],
                                cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('unchanged', result.stderr)




class ServiceTests(unittest.TestCase):
    def test_once_failure_returns_nonzero(self):
        with patch.object(sys, 'argv', ['snake-web', '--once']), \
             patch.object(server.signal, 'signal'), \
             patch.object(server, 'publish_once', side_effect=RuntimeError('unavailable')), \
             self.assertLogs(level='ERROR'):
            self.assertEqual(server.main(), 1)

    def test_service_retries_after_failure(self):
        stopped = Mock()
        stopped.is_set.return_value = False
        stopped.wait.side_effect = [False, True]
        with patch.object(sys, 'argv', ['snake-web']), \
             patch.object(server.DSnakeWeb, 'POLL_INTERVAL', 37), \
             patch.object(server.signal, 'signal'), \
             patch.object(server.threading, 'Event', return_value=stopped), \
             patch.object(server, 'publish_once', side_effect=[RuntimeError('unavailable'), 'published']) as publish, \
             self.assertLogs(level='INFO'):
            self.assertEqual(server.main(), 0)
            self.assertEqual(publish.call_count, 2)
            self.assertEqual([call.args for call in stopped.wait.call_args_list], [(37,), (37,)])

    def test_shutdown_signal_stops_loop(self):
        handlers = {}

        def register(signum, callback):
            handlers[signum] = callback

        def publish():
            handlers[server.signal.SIGTERM](server.signal.SIGTERM, None)
            return 'published'

        with patch.object(sys, 'argv', ['snake-web']), \
             patch.object(server.signal, 'signal', side_effect=register), \
             patch.object(server, 'publish_once', side_effect=publish) as run, \
             self.assertLogs(level='INFO'):
            self.assertEqual(server.main(), 0)
            run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
