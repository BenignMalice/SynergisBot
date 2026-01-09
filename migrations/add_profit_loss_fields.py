"""
Migration script to add profit/loss fields to trade_plans table.

Run this script before implementing Phase 2 database storage features.
The TradePlan dataclass must be updated first (already done in auto_execution_system.py).
"""

import sqlite3
from pathlib import Path
from typing import Optional

def migrate(db_path: Optional[str] = None):
    """
    Add profit/loss fields to trade_plans table.
    
    Args:
        db_path: Path to database file. If None, tries to get from AutoExecutionSystem.
    """
    if db_path is None:
        # Try to get from AutoExecutionSystem if available
        try:
            from chatgpt_auto_execution_integration import get_chatgpt_auto_execution
            auto_execution = get_chatgpt_auto_execution()
            db_path = str(auto_execution.auto_system.db_path)
        except Exception:
            # Fallback to default path
            db_path = "data/auto_execution.db"
    
    db_path = Path(db_path)
    
    # Ensure database directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Use context manager for connection
    with sqlite3.connect(str(db_path), timeout=10.0) as conn:
        c = conn.cursor()
        
        try:
            # Check if columns already exist
            c.execute("PRAGMA table_info(trade_plans)")
            columns = [row[1] for row in c.fetchall()]
            
            if 'profit_loss' not in columns:
                c.execute("ALTER TABLE trade_plans ADD COLUMN profit_loss REAL")
                print("✅ Added profit_loss column")
            else:
                print("ℹ️  profit_loss column already exists")
            
            if 'exit_price' not in columns:
                c.execute("ALTER TABLE trade_plans ADD COLUMN exit_price REAL")
                print("✅ Added exit_price column")
            else:
                print("ℹ️  exit_price column already exists")
            
            if 'close_time' not in columns:
                c.execute("ALTER TABLE trade_plans ADD COLUMN close_time TEXT")
                print("✅ Added close_time column")
            else:
                print("ℹ️  close_time column already exists")
            
            if 'close_reason' not in columns:
                c.execute("ALTER TABLE trade_plans ADD COLUMN close_reason TEXT")
                print("✅ Added close_reason column")
            else:
                print("ℹ️  close_reason column already exists")
            
            conn.commit()
            print("✅ Migration completed successfully")
        except Exception as e:
            # SQLite doesn't support rollback for DDL operations (ALTER TABLE)
            # But ALTER TABLE is atomic, so if it fails, nothing is changed
            print(f"❌ Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate()

