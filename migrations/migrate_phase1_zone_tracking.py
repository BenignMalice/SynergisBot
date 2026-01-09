"""
Migration: Phase 1 - Zone Tracking Columns
Adds zone_entry_tracked, zone_entry_time, zone_exit_time columns to trade_plans table
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def migrate_zone_tracking(db_path: str = "data/auto_execution.db") -> bool:
    """
    Add zone tracking columns to trade_plans table.
    
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
            
            # Check if columns already exist
            cursor.execute("PRAGMA table_info(trade_plans)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Add zone_entry_tracked column if it doesn't exist
            if "zone_entry_tracked" not in columns:
                logger.info("Adding zone_entry_tracked column to trade_plans table")
                cursor.execute("""
                    ALTER TABLE trade_plans 
                    ADD COLUMN zone_entry_tracked INTEGER DEFAULT 0
                """)
            else:
                logger.debug("zone_entry_tracked column already exists")
            
            # Add zone_entry_time column if it doesn't exist
            if "zone_entry_time" not in columns:
                logger.info("Adding zone_entry_time column to trade_plans table")
                cursor.execute("""
                    ALTER TABLE trade_plans 
                    ADD COLUMN zone_entry_time TEXT
                """)
            else:
                logger.debug("zone_entry_time column already exists")
            
            # Add zone_exit_time column if it doesn't exist
            if "zone_exit_time" not in columns:
                logger.info("Adding zone_exit_time column to trade_plans table")
                cursor.execute("""
                    ALTER TABLE trade_plans 
                    ADD COLUMN zone_exit_time TEXT
                """)
            else:
                logger.debug("zone_exit_time column already exists")
            
            conn.commit()
            logger.info("Phase 1 zone tracking migration completed successfully")
            return True
            
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            logger.warning(f"Column already exists (non-fatal): {e}")
            return True  # Not a fatal error
        else:
            logger.error(f"Database operational error during migration: {e}")
            return False
    except Exception as e:
        logger.error(f"Error during zone tracking migration: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    success = migrate_zone_tracking()
    sys.exit(0 if success else 1)

