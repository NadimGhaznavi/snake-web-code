"""The reader uses Snake Lab's UTC clock and a read-only transaction."""

import os
import unittest
from unittest.mock import MagicMock, patch

from snakewebcode.interface.DbMgr import DbMgr


class DbMgrTests(unittest.TestCase):
    def test_utc_session_and_read_only_transaction(self):
        connection = MagicMock()
        with patch.dict(os.environ, DB_USER='reader', DB_PASSWORD='test-only'), \
             patch('snakewebcode.interface.DbMgr.pymysql.connect', return_value=connection) as connect:
            with DbMgr() as db:
                db.query('SELECT CURRENT_TIMESTAMP AS observed_at')
            self.assertEqual(connect.call_args.kwargs['init_command'], "SET time_zone = '+00:00'")
            self.assertFalse(connect.call_args.kwargs['autocommit'])
            self.assertEqual(connection.cursor.return_value.__enter__.return_value.execute.call_args_list[0].args,
                             ('START TRANSACTION READ ONLY',))
            connection.close.assert_called_once_with()
