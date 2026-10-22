"""Windows handle release and transaction semantics are part of correctness."""
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bind-zero-x' / 'code'))
from sqlite_scope import connect
from research_loop_store import SQLiteResearchLoops


class ConnectionLifecycle(unittest.TestCase):
    def test_transactions_commit_rollback_and_release(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'scoped.db'
            with connect(path) as db:
                db.execute('CREATE TABLE demo (value INTEGER)')
                db.execute('INSERT INTO demo VALUES (1)')
            with self.assertRaises(sqlite3.ProgrammingError):
                db.execute('SELECT 1')
            with self.assertRaisesRegex(ValueError, 'rollback'):
                with connect(path) as db:
                    db.execute('INSERT INTO demo VALUES (2)')
                    raise ValueError('rollback')
            with connect(path) as db:
                self.assertEqual(db.execute('SELECT value FROM demo').fetchall(), [(1,)])
            path.rename(Path(temp) / 'released.db')

    def test_store_does_not_hold_handles_after_initialization(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'loops.db'
            SQLiteResearchLoops(path)
            path.rename(Path(temp) / 'closed.db')


if __name__ == '__main__':
    unittest.main()
