"""A SQLite transaction scope that also releases Windows file handles."""
import sqlite3


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect(*args, **kwargs):
    return sqlite3.connect(*args, factory=ClosingConnection, **kwargs)
