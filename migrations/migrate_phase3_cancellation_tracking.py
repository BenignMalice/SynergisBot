"""
Migration: Phase 3 - Conditional Cancellation Tracking
Adds cancellation_reason and last_cancellation_check fields to trade_plans table.
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def migrate_phase3_cancellation_tracking(db_path: str) -> bool:
    """
    Add cancellation_reason and last_cancellation_check columns to trade_plans table.
    
    Args:
        db_path: Path to the database file
        
    Returns:
        True if migration successful, False otherwise
    """
    try:
        db_file = Path(db_path)
        if not db_file.exists():
            logger.warning(f"Database file not found: {db_path}")
            return False
        
        with sqlite3.connect(db_path, timeout=10.0) as conn:
            cursor = conn.cursor()
            
            # Check if cancellation_reason column exists
            cursor.execute("PRAGMA table_info(trade_plans)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Add cancellation_reason column if it doesn't exist
            if 'cancellation_reason' not in columns:
                cursor.execute("""
                    ALTER TABLE trade_plans 
                    ADD COLUMN cancellation_reason TEXT
                """)
                logger.info("Added cancellation_reason column to trade_plans table")
            else:
                logger.debug("cancellation_reason column already exists")
            
            # Add last_cancellation_check column if it doesn't exist
            if 'last_cancellation_check' not in columns:
                cursor.execute("""
                    ALTER TABLE trade_plans 
                    ADD COLUMN last_cancellation_check TEXT
                """)
                logger.info("Added last_cancellation_check column to trade_plans table")
            else:
                logger.debug("last_cancellation_check column already exists")
            
            conn.commit()
            logger.info("Phase 3 cancellation tracking migration completed successfully")
            return True
            
    except Exception as e:
        logger.error(f"Error in Phase 3 cancellation tracking migration: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    # Test migration
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/auto_execution_plans.db"
    migrate_phase3_cancellation_tracking(db_path)

