"""
Tick Metrics Cache Schema Migration
Version: 1.0
Date: January 2026
Location: data/unified_tick_pipeline/tick_metrics_cache.db

Creates the tick_metrics_cache table and indexes for storing computed tick metrics.
"""
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATABASE_PATH = Path("data/unified_tick_pipeline/tick_metrics_cache.db")


def migrate():
    """
    Creates the tick_metrics_cache table if it doesn't exist.
    """
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        # Enable WAL mode for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA cache_size=-100000")  # 100MB cache
        cursor.execute("PRAGMA busy_timeout=5000")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tick_metrics_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timestamp)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tick_metrics_symbol 
            ON tick_metrics_cache(symbol)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tick_metrics_expires 
            ON tick_metrics_cache(expires_at)
        """)
        
        conn.commit()
        logger.info("Tick metrics cache schema created successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate()

