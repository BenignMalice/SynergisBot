"""
Migration: Phase III - Pattern History Table
Creates pattern_history table for tracking institutional signature patterns
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def migrate_pattern_history(db_path: str = "data/auto_execution.db") -> bool:
    """
    Create pattern_history table for Phase III institutional signature detection.
    
    Args:
        db_path: Path to database file
    
    Returns:
        True if migration successful, False otherwise
    """
    try:
        db_path_obj = Path(db_path)
        if not db_path_obj.exists():
            logger.warning(f"Database {db_path} does not exist - migration skipped")
            return True  # Not an error if DB doesn't exist yet
        
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            cursor = conn.cursor()
            
            # Check if table already exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='pattern_history'
            """)
            if cursor.fetchone():
                logger.info("pattern_history table already exists")
                return True
            
            # Create pattern_history table
            logger.info("Creating pattern_history table")
            cursor.execute("""
                CREATE TABLE pattern_history (
                    pattern_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    pattern_type TEXT NOT NULL,
                    pattern_data TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)
            
            # Create indexes
            logger.info("Creating indexes for pattern_history")
            cursor.execute("""
                CREATE INDEX idx_pattern_symbol ON pattern_history(symbol)
            """)
            cursor.execute("""
                CREATE INDEX idx_pattern_type ON pattern_history(pattern_type)
            """)
            cursor.execute("""
                CREATE INDEX idx_pattern_detected ON pattern_history(detected_at)
            """)
            
            conn.commit()
            logger.info("Phase III pattern_history migration completed successfully")
            return True
            
    except sqlite3.OperationalError as e:
        if "already exists" in str(e).lower():
            logger.warning(f"Table or index already exists (non-fatal): {e}")
            return True  # Not a fatal error
        else:
            logger.error(f"Database operational error during migration: {e}")
            return False
    except Exception as e:
        logger.error(f"Error during pattern_history migration: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    success = migrate_pattern_history()
    sys.exit(0 if success else 1)

