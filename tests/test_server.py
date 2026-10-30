"""Half-hour scheduling, one-shot publication, failure handling, and shutdown."""

from datetime import datetime
import sys
import unittest
from unittest.mock import Mock, patch

from snakewebcode import server


class ServiceTests(unittest.TestCase):
    def test_two_consecutive_half_hours_both_publish(self):
        stopped = Mock()
        stopped.is_set.return_value = False
        stopped.wait.side_effect = [False, False, True]
        with patch.object(sys, 'argv', ['snake-web']), \
             patch.object(server, 'datetime') as clock, \
             patch.object(server.signal, 'signal'), \
             patch.object(server.threading, 'Event', return_value=stopped), \
             patch.object(server, 'publish_once', return_value='unchanged') as publish:
            clock.now.side_effect = [datetime(2026, 10, 30, 12, 0),
                                     datetime(2026, 10, 30, 12, 30),
                                     datetime(2026, 10, 30, 13, 0)]
            self.assertEqual(server.main(), 0)
        self.assertEqual(publish.call_count, 2)
        self.assertEqual([call.args for call in stopped.wait.call_args_list], [(1800,)] * 3)

    def test_unexpected_programming_error_is_not_swallowed(self):
        with patch.object(sys, 'argv', ['snake-web', '--once']), \
             patch.object(server.signal, 'signal'), \
             patch.object(server, 'publish_once', side_effect=KeyError('programming defect')):
            with self.assertRaises(KeyError):
                server.main()

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
            publish.assert_called_once_with()

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
