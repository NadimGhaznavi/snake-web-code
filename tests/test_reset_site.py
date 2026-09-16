"""Reset only generated publication data, using disposable repositories."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

import test_publishing

spec = importlib.util.spec_from_file_location('reset_site', Path(__file__).resolve().parents[1] / 'scripts/reset-site.py')
reset = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset)


class ResetSiteTests(unittest.TestCase):
    git = test_publishing.PublishingTests.git

    def setUp(self):
        test_publishing.PublishingTests.setUp(self)
        (self.repo / '_config.yml').write_text('title: Keep this theme\n')
        (self.repo / 'CNAME').write_text('example.invalid\n')
        (self.repo / 'pages').mkdir()
        (self.repo / 'pages/about.md').write_text('Keep this page\n')
        self.git(self.repo, 'add', '.')
        self.git(self.repo, 'commit', '-m', 'Site configuration')
        self.git(self.repo, 'push', 'origin', 'main')
        self.activity.run()

    def run_script(self, *args):
        return subprocess.run([sys.executable, reset.__file__, str(self.repo), *args],
                              capture_output=True, text=True)

    def test_preview_apply_push_and_restart(self):
        original = self.git(self.repo, 'rev-parse', 'HEAD')
        preview = self.run_script()
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn('Preview only', preview.stdout)
        self.assertEqual(original, self.git(self.repo, 'rev-parse', 'HEAD'))
        result = self.run_script('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(original, self.git(self.remote, 'rev-parse', 'main'))
        self.assertEqual(self.page.read_text(), reset.EMPTY_HOME)
        for name in self.publisher.OWNED_PATHS:
            if name != 'index.md':
                self.assertFalse((self.repo / name).exists(), name)
        self.assertEqual((self.repo / 'CNAME').read_text(), 'example.invalid\n')
        self.assertEqual((self.repo / 'pages/about.md').read_text(), 'Keep this page\n')
        self.assertEqual((self.repo / '_config.yml').read_text(), 'title: Keep this theme\n')
        reset_head = self.git(self.repo, 'rev-parse', 'HEAD')
        result = self.run_script('--apply', '--push')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(reset_head, self.git(self.remote, 'rev-parse', 'main'))
        self.assertEqual(self.git(self.repo, 'status', '--porcelain'), '')
        self.activity.run()
        self.appdb.get_golden_configurations.assert_called_with(0)
        self.appdb.get_highscore_history.assert_called_with(0)
        self.assertTrue((self.repo / self.publisher.EVENT_HISTORY_PATH).exists())

    def test_dirty_or_non_site_checkout_refused(self):
        self.page.write_text('Uncommitted work')
        result = self.run_script('--apply')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.page.read_text(), 'Uncommitted work')
        self.git(self.repo, 'add', 'index.md')
        self.git(self.repo, 'commit', '-m', 'User edit')
        self.git(self.repo, 'rm', '_config.yml')
        self.git(self.repo, 'commit', '-m', 'Not a site')
        result = self.run_script('--apply')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Jekyll', result.stderr)

    def test_symlink_refused_without_removing_target(self):
        target = self.root / 'outside'
        target.write_text('Keep me')
        report = self.repo / self.publisher.EVENT_HISTORY_PATH
        report.unlink()
        report.symlink_to(target)
        self.git(self.repo, 'add', '.')
        self.git(self.repo, 'commit', '-m', 'Symlink')
        result = self.run_script('--apply')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_text(), 'Keep me')

    def test_failed_reset_push_can_be_retried(self):
        hook = self.remote / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        result = self.run_script('--apply', '--push')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Git push failed', result.stderr)
        head = self.git(self.repo, 'rev-parse', 'HEAD')
        hook.unlink()
        result = self.run_script('--apply', '--push')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(head, self.git(self.remote, 'rev-parse', 'main'))

    def test_push_requires_explicit_apply(self):
        result = self.run_script('--push')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--push requires --apply', result.stderr)
