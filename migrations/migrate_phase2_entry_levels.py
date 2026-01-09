"""
Migration: Phase 2 - Entry Levels Column
Adds entry_levels JSON column to trade_plans table for multi-level entry support
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def migrate_entry_levels(db_path: str = "data/auto_execution.db") -> bool:
    """
    Add entry_levels column to trade_plans table.
    
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
            
            # Check if column already exists
            cursor.execute("PRAGMA table_info(trade_plans)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Add entry_levels column if it doesn't exist
            if "entry_levels" not in columns:
                logger.info("Adding entry_levels column to trade_plans table")
                cursor.execute("""
                    ALTER TABLE trade_plans 
                    ADD COLUMN entry_levels TEXT
                """)
            else:
                logger.debug("entry_levels column already exists")
            
            conn.commit()
            logger.info("Phase 2 entry levels migration completed successfully")
            return True
            
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            logger.warning(f"Column already exists (non-fatal): {e}")
            return True  # Not a fatal error
        else:
            logger.error(f"Database operational error during migration: {e}")
            return False
    except Exception as e:
        logger.error(f"Error during entry levels migration: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    success = migrate_entry_levels()
    sys.exit(0 if success else 1)

