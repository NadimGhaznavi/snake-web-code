"""Real Git integration tests; every repository and remote is temporary."""

import fcntl
import socket
import re
from datetime import datetime, timedelta, timezone
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
        self.appdb.get_golden_configurations.return_value = []
        self.appdb.get_event_export_end.return_value = 0
        self.appdb.get_public_events.return_value = []
        self.appdb.get_public_simulations.return_value = []
        self.appdb.get_run_scores.return_value = []
        self.appdb.get_top_runs.return_value = []
        self.activity = PublishStatus(self.appdb, self.publisher)

    def git(self, directory, *args):
        return subprocess.run(['git', '-C', str(directory), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def expected_page(self, status):
        page = self.page.read_text()
        match = re.search(r'<!-- last-updated -->([^<]*)<!-- /last-updated -->', page)
        return render_status(status, socket.gethostname(), match.group(1) if match else '')

    def remote_page(self):
        return self.git(self.remote, 'show', 'main:index.md')

    def test_publish_and_no_duplicate_commit(self):
        self.assertIn('published', self.activity.run())
        self.assertEqual(self.remote_page(), self.expected_page(STATUS).strip())
        head = self.git(self.remote, 'rev-parse', 'main')
        with patch.object(self.publisher, '_git', wraps=self.publisher._git) as git:
            self.assertIn('unchanged', self.activity.run())
            self.assertFalse(any(call.args[0] == 'push' for call in git.call_args_list))
        self.assertEqual(head, self.git(self.remote, 'rev-parse', 'main'))
        self.assertEqual(self.git(self.repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').splitlines(), sorted(self.publisher.OWNED_PATHS))

    def test_top_runs_refresh_and_retry_failed_push(self):
        self.appdb.get_top_runs.return_value = [dict(id=9, high_score=30)]
        hook = self.remote / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        with self.assertRaises(RuntimeError):
            self.activity.run()
        head = self.git(self.repo, 'rev-parse', 'HEAD')
        hook.unlink()
        self.activity.run()
        self.assertEqual(head, self.git(self.remote, 'rev-parse', 'main'))
        self.assertIn('Run #9 - Score: 30', self.git(
            self.remote, 'show', 'main:' + self.publisher.TOP_RUNS_PATH))
        self.appdb.get_top_runs.return_value = [dict(id=12, high_score=40)]
        self.activity.run()
        page = self.git(self.remote, 'show', 'main:' + self.publisher.TOP_RUNS_PATH)
        self.assertIn('Run #12 - Score: 40', page)
        self.assertNotIn('Run #9', page)

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

    def test_histogram_update_and_failed_push_retry(self):
        self.appdb.get_run_scores.return_value = [dict(id=1, high_score=None)]
        self.activity.run()
        self.appdb.get_run_scores.return_value = [dict(id=1, high_score=8), dict(id=2, high_score=0)]
        hook = self.remote / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        with self.assertRaisesRegex(RuntimeError, 'Git push failed'):
            self.activity.run()
        head = self.git(self.repo, 'rev-parse', 'HEAD')
        hook.unlink()
        self.activity.run()
        self.assertEqual(head, self.git(self.remote, 'rev-parse', 'main'))
        self.assertEqual(self.git(self.remote, 'show', 'main:' + self.publisher.SCORES_PATH),
                         'id,high_score\n1,\n1,8\n2,0')
        self.assertIn('reports/score-distribution.html', self.remote_page())
        self.assertIn('data/run-scores.csv', self.git(
            self.remote, 'show', 'main:' + self.publisher.DISTRIBUTION_SCRIPT_PATH))

    def test_golden_history_incremental_retry(self):
        self.appdb.get_golden_configurations.return_value = [dict(
            event_id=10, occurred_at='2026-09-16 12:00:00', process_id='baseline', high_score=0)]
        self.activity.run()
        self.appdb.get_golden_configurations.assert_called_with(0)
        original = (self.repo / self.publisher.GOLDEN_HISTORY_PATH).read_text()
        self.appdb.get_golden_configurations.return_value = [dict(
            event_id=20, occurred_at='2026-09-16 13:00:00', process_id='winner', high_score=8)]
        hook = self.remote / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        with self.assertRaisesRegex(RuntimeError, 'Git push failed'):
            self.activity.run()
        self.appdb.get_golden_configurations.assert_called_with(10)
        head = self.git(self.repo, 'rev-parse', 'HEAD')
        self.appdb.get_golden_configurations.return_value = []
        hook.unlink()
        self.activity.run()
        self.appdb.get_golden_configurations.assert_called_with(20)
        self.assertEqual(head, self.git(self.remote, 'rev-parse', 'main'))
        self.assertEqual((self.repo / self.publisher.GOLDEN_HISTORY_PATH).read_text(),
                         original + '20,2026-09-16 13:00:00,winner,8,,,\n')
        self.assertIn('reports/golden-configurations.html', self.remote_page())

    def test_last_updated_uses_local_time_and_changes_only_with_content(self):
        clock = Mock()
        clock.now.return_value.astimezone.return_value = datetime(
            2026, 9, 16, 15, 4, 5, tzinfo=timezone(timedelta(hours=-4), 'EDT'))
        with patch('snake_web.activity.PublishStatus.datetime', clock):
            self.activity.run()
            self.assertIn('Last Updated: <!-- last-updated -->2026-09-16 15:04:05 EDT (-0400)',
                          self.remote_page())
            clock.now.return_value.astimezone.return_value = datetime(
                2026, 9, 16, 16, 4, 5, tzinfo=timezone(timedelta(hours=-4), 'EDT'))
            self.assertIn('unchanged', self.activity.run())
            self.assertIn('15:04:05 EDT', self.remote_page())
            self.appdb.get_run_scores.return_value = [dict(id=1, high_score=5)]
            self.activity.run()
            self.assertIn('16:04:05 EDT', self.remote_page())

    def test_event_log_failed_push_retries_sanitized_files_and_cursor(self):
        self.appdb.get_event_export_end.return_value = 9
        event = dict(event_id=5, occurred_at='2026-09-16 12:00:00',
                     category='Conversation', name='reply_received', content=
                     '{"choices":[{"message":{"reasoning_content":"public reason","content":"PRIVATE"}}]}')
        self.appdb.get_public_events.side_effect = lambda after, end: [event] if after < 5 else []
        hook = self.remote / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        with self.assertRaisesRegex(RuntimeError, 'Git push failed'):
            self.activity.run()
        head = self.git(self.repo, 'rev-parse', 'HEAD')
        hook.unlink()
        self.appdb.get_public_events.reset_mock()
        self.activity.run()
        self.appdb.get_public_events.assert_not_called()
        self.assertEqual(head, self.git(self.remote, 'rev-parse', 'main'))
        exported = self.git(self.remote, 'show', 'main:' + self.publisher.EVENT_HISTORY_PATH)
        self.assertIn('public reason', exported)
        self.assertNotIn('PRIVATE', exported)
        self.assertIn('"through_event_id": 9', self.git(
            self.remote, 'show', 'main:' + self.publisher.EVENT_CURSOR_PATH))
        self.assertIn('reports/event-log.html', self.remote_page())

    def test_other_metrics_publish_without_a_new_all_time_highscore(self):
        self.activity.run()
        head = self.git(self.remote, 'rev-parse', 'main')
        self.appdb.get_experiment_status.return_value = replace(STATUS, simulations_submitted=191,
                                                               experiment_cycles=27)
        self.assertIn('published', self.activity.run())
        self.assertNotEqual(head, self.git(self.remote, 'rev-parse', 'main'))
        self.assertIn('Simulations Run: 191', self.remote_page())
        self.assertIn('Completed Experiments: 27', self.remote_page())

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
                self.assertEqual(self.page.read_text(), self.expected_page(STATUS))
                self.assertEqual(self.remote_page(), self.expected_page(STATUS).strip())

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
        self.assertEqual(self.remote_page(), self.expected_page(status).strip())
        result = subprocess.run([sys.executable, '-m', 'snake_web.server', '--once'],
                                cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('unchanged', result.stderr)




class ServiceTests(unittest.TestCase):
    def test_next_publish_is_on_the_hour_or_half_hour(self):
        for value, expected in [
            ('2026-09-16T12:07:00', 1380),
            ('2026-09-16T12:30:00', 1800),
            ('2026-09-16T12:00:00', 1800),
            ('2026-09-16T12:29:59.500000', 0.5),
            ('2026-09-16T23:59:00', 60),
        ]:
            with self.subTest(now=value):
                self.assertEqual(server.seconds_until_next_publish(
                    datetime.fromisoformat(value)), expected)

    def test_once_publishes_without_waiting(self):
        with patch.object(sys, 'argv', ['snake-web', '--once']), \
             patch.object(server.signal, 'signal'), \
             patch.object(server.threading, 'Event') as event, \
             patch.object(server, 'publish_once', return_value='published') as publish:
            event.return_value.is_set.return_value = False
            self.assertEqual(server.main(), 0)
            event.return_value.wait.assert_not_called()
            publish.assert_called_once()

    def test_once_failure_returns_nonzero(self):
        with patch.object(sys, 'argv', ['snake-web', '--once']), \
             patch.object(server.signal, 'signal'), \
             patch.object(server, 'publish_once', side_effect=RuntimeError('unavailable')), \
             self.assertLogs(level='ERROR'):
            self.assertEqual(server.main(), 1)

    def test_service_retries_after_failure(self):
        stopped = Mock()
        stopped.is_set.return_value = False
        stopped.wait.side_effect = [False, False, True]
        with patch.object(sys, 'argv', ['snake-web']), \
             patch.object(server, 'datetime') as clock, \
             patch.object(server.signal, 'signal'), \
             patch.object(server.threading, 'Event', return_value=stopped), \
             patch.object(server, 'publish_once', side_effect=[RuntimeError('unavailable'), 'published']) as publish, \
             self.assertLogs(level='INFO'):
            clock.now.side_effect = [datetime(2026, 9, 16, 12, 7),
                                     datetime(2026, 9, 16, 12, 32),
                                     datetime(2026, 9, 16, 13, 1)]
            self.assertEqual(server.main(), 0)
            self.assertEqual(publish.call_count, 2)
            self.assertEqual([call.args for call in stopped.wait.call_args_list],
                             [(1380,), (1680,), (1740,)])

    def test_shutdown_while_waiting_does_not_publish(self):
        stopped = Mock()
        stopped.is_set.return_value = False
        stopped.wait.return_value = True
        with patch.object(sys, 'argv', ['snake-web']), \
             patch.object(server.signal, 'signal'), \
             patch.object(server.threading, 'Event', return_value=stopped), \
             patch.object(server, 'publish_once') as publish:
            self.assertEqual(server.main(), 0)
            stopped.wait.assert_called_once()
            publish.assert_not_called()

    def test_shutdown_signal_stops_loop(self):
        handlers = {}

        def register(signum, callback):
            handlers[signum] = callback

        def publish():
            handlers[server.signal.SIGTERM](server.signal.SIGTERM, None)
            return 'published'

        with patch.object(sys, 'argv', ['snake-web']), \
             patch.object(server.signal, 'signal', side_effect=register), \
             patch.object(server.threading.Event, 'wait', return_value=False), \
             patch.object(server, 'publish_once', side_effect=publish) as run, \
             self.assertLogs(level='INFO'):
            self.assertEqual(server.main(), 0)
            run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
