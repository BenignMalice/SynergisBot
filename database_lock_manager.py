
import sqlite3
import os
import time
import threading
from contextlib import contextmanager

class DatabaseLockManager:
    """Manages database access to prevent locking issues."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._configure_database()
    
    def _configure_database(self):
        """Configure database for optimal concurrency."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=60.0)
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=60000")
            cursor.execute("PRAGMA wal_autocheckpoint=1000")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error configuring database: {e}")
    
    @contextmanager
    def get_connection(self):
        """Get a database connection with proper locking."""
        conn = None
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path, timeout=60.0, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA busy_timeout=60000")
            yield conn
        except Exception as e:
            if conn:
                conn.close()
            raise
        finally:
            if conn:
                conn.close()
