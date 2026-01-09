"""
Migration: Phase III - Plan Execution State Table
Creates plan_execution_state table for tracking dynamic plan conversion state
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def migrate_execution_state(db_path: str = "data/auto_execution.db") -> bool:
    """
    Create plan_execution_state table for Phase III execution state tracking.
    
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
                WHERE type='table' AND name='plan_execution_state'
            """)
            if cursor.fetchone():
                logger.info("plan_execution_state table already exists")
                return True
            
            # Create plan_execution_state table
            logger.info("Creating plan_execution_state table")
            cursor.execute("""
                CREATE TABLE plan_execution_state (
                    plan_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    trailing_mode_enabled INTEGER DEFAULT 0,
                    trailing_activation_rr REAL DEFAULT 0.0,
                    current_rr REAL DEFAULT 0.0,
                    state_data TEXT,
                    updated_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES trade_plans(plan_id) ON DELETE CASCADE
                )
            """)
            
            # Create indexes
            logger.info("Creating indexes for plan_execution_state")
            cursor.execute("""
                CREATE INDEX idx_exec_state_symbol ON plan_execution_state(symbol)
            """)
            cursor.execute("""
                CREATE INDEX idx_exec_state_updated ON plan_execution_state(updated_at)
            """)
            cursor.execute("""
                CREATE INDEX idx_exec_state_trailing ON plan_execution_state(trailing_mode_enabled)
            """)
            
            conn.commit()
            logger.info("Phase III plan_execution_state migration completed successfully")
            return True
            
    except sqlite3.OperationalError as e:
        if "already exists" in str(e).lower():
            logger.warning(f"Table or index already exists (non-fatal): {e}")
            return True  # Not a fatal error
        else:
            logger.error(f"Database operational error during migration: {e}")
            return False
    except sqlite3.IntegrityError as e:
        # Foreign key constraint might fail if trade_plans doesn't exist
        # This is OK - foreign key will be enforced when trade_plans exists
        logger.warning(f"Foreign key constraint issue (non-fatal, will be enforced later): {e}")
        return True
    except Exception as e:
        logger.error(f"Error during execution_state migration: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    success = migrate_execution_state()
    sys.exit(0 if success else 1)

