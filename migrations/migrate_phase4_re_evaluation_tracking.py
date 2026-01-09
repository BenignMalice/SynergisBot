"""
Migration: Phase 4 - Re-evaluation Tracking
Adds re-evaluation tracking fields to trade_plans table.
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def migrate_phase4_re_evaluation_tracking(db_path: str) -> bool:
    """
    Add re-evaluation tracking columns to trade_plans table.
    
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
            
            # Check if columns exist
            cursor.execute("PRAGMA table_info(trade_plans)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Add last_re_evaluation column if it doesn't exist
            if 'last_re_evaluation' not in columns:
                cursor.execute("""
                    ALTER TABLE trade_plans 
                    ADD COLUMN last_re_evaluation TEXT
                """)
                logger.info("Added last_re_evaluation column to trade_plans table")
            else:
                logger.debug("last_re_evaluation column already exists")
            
            # Add re_evaluation_count_today column if it doesn't exist
            if 're_evaluation_count_today' not in columns:
                cursor.execute("""
                    ALTER TABLE trade_plans 
                    ADD COLUMN re_evaluation_count_today INTEGER DEFAULT 0
                """)
                logger.info("Added re_evaluation_count_today column to trade_plans table")
            else:
                logger.debug("re_evaluation_count_today column already exists")
            
            # Add re_evaluation_count_date column if it doesn't exist (to track which day the count is for)
            if 're_evaluation_count_date' not in columns:
                cursor.execute("""
                    ALTER TABLE trade_plans 
                    ADD COLUMN re_evaluation_count_date TEXT
                """)
                logger.info("Added re_evaluation_count_date column to trade_plans table")
            else:
                logger.debug("re_evaluation_count_date column already exists")
            
            conn.commit()
            logger.info("Phase 4 re-evaluation tracking migration completed successfully")
            return True
            
    except Exception as e:
        logger.error(f"Error in Phase 4 re-evaluation tracking migration: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    # Test migration
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/auto_execution_plans.db"
    migrate_phase4_re_evaluation_tracking(db_path)

