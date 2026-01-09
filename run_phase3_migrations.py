"""
Run Phase III Database Migrations
Runs all Phase III migrations on test or production database
"""

import sqlite3
import sys
import codecs
import shutil
from pathlib import Path
from datetime import datetime, timezone

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

def backup_database(db_path: Path) -> Path:
    """Create backup of database"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"
    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    print(f"✅ Backup created: {backup_path}")
    return backup_path

def verify_table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Verify table exists"""
    cursor = conn.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None

def verify_column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    """Verify column exists in table"""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def run_migrations(db_path: str, test_mode: bool = True):
    """Run all Phase III migrations"""
    print("=" * 70)
    print("Phase III Database Migrations")
    print("=" * 70)
    print(f"Database: {db_path}")
    print(f"Mode: {'TEST' if test_mode else 'PRODUCTION'}")
    print("=" * 70)
    
    db_path_obj = Path(db_path)
    
    # Check if database exists
    if not db_path_obj.exists():
        print(f"❌ Database not found: {db_path}")
        print("   Creating new database...")
        db_path_obj.parent.mkdir(parents=True, exist_ok=True)
        # Create minimal trade_plans table if it doesn't exist
        with sqlite3.connect(str(db_path_obj)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_plans (
                    plan_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    volume REAL NOT NULL,
                    conditions TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    expires_at TEXT,
                    executed_at TEXT,
                    ticket INTEGER,
                    notes TEXT
                )
            """)
            conn.commit()
        print("✅ Created new database with trade_plans table")
    
    # Backup production database (not test)
    if not test_mode:
        try:
            backup_path = backup_database(db_path_obj)
        except Exception as e:
            print(f"⚠️  Warning: Could not create backup: {e}")
            response = input("Continue without backup? (yes/no): ")
            if response.lower() != 'yes':
                print("Migration cancelled")
                return False
    
    results = {}
    
    # Migration 1: Pattern History
    print("\n" + "=" * 70)
    print("Migration 1: pattern_history table")
    print("=" * 70)
    try:
        from migrations.migrate_phase3_pattern_history import migrate_pattern_history
        success = migrate_pattern_history(db_path)
        results['pattern_history'] = success
        
        if success:
            # Verify
            with sqlite3.connect(db_path, timeout=30.0) as conn:
                if verify_table_exists(conn, 'pattern_history'):
                    cursor = conn.execute("PRAGMA table_info(pattern_history)")
                    columns = [row[1] for row in cursor.fetchall()]
                    print(f"✅ pattern_history table created with columns: {columns}")
                else:
                    print("❌ pattern_history table not found after migration")
                    results['pattern_history'] = False
        else:
            print("❌ pattern_history migration failed")
    except Exception as e:
        print(f"❌ Error running pattern_history migration: {e}")
        import traceback
        traceback.print_exc()
        results['pattern_history'] = False
    
    # Migration 2: Execution State
    print("\n" + "=" * 70)
    print("Migration 2: plan_execution_state table")
    print("=" * 70)
    try:
        from migrations.migrate_phase3_execution_state import migrate_execution_state
        success = migrate_execution_state(db_path)
        results['execution_state'] = success
        
        if success:
            # Verify
            with sqlite3.connect(db_path, timeout=30.0) as conn:
                if verify_table_exists(conn, 'plan_execution_state'):
                    cursor = conn.execute("PRAGMA table_info(plan_execution_state)")
                    columns = [row[1] for row in cursor.fetchall()]
                    print(f"✅ plan_execution_state table created with columns: {columns}")
                else:
                    print("❌ plan_execution_state table not found after migration")
                    results['execution_state'] = False
        else:
            print("❌ plan_execution_state migration failed")
    except Exception as e:
        print(f"❌ Error running execution_state migration: {e}")
        import traceback
        traceback.print_exc()
        results['execution_state'] = False
    
    # Migration 3: Cancellation Tracking
    print("\n" + "=" * 70)
    print("Migration 3: cancellation_tracking columns (trade_plans)")
    print("=" * 70)
    try:
        from migrations.migrate_phase3_cancellation_tracking import migrate_phase3_cancellation_tracking
        success = migrate_phase3_cancellation_tracking(db_path)
        results['cancellation_tracking'] = success
        
        if success:
            # Verify
            with sqlite3.connect(db_path, timeout=30.0) as conn:
                if verify_column_exists(conn, 'trade_plans', 'cancellation_reason'):
                    print("✅ cancellation_reason column added")
                else:
                    print("❌ cancellation_reason column not found")
                    results['cancellation_tracking'] = False
                
                if verify_column_exists(conn, 'trade_plans', 'last_cancellation_check'):
                    print("✅ last_cancellation_check column added")
                else:
                    print("❌ last_cancellation_check column not found")
                    results['cancellation_tracking'] = False
        else:
            print("❌ cancellation_tracking migration failed")
    except Exception as e:
        print(f"❌ Error running cancellation_tracking migration: {e}")
        import traceback
        traceback.print_exc()
        results['cancellation_tracking'] = False
    
    # Summary
    print("\n" + "=" * 70)
    print("Migration Summary")
    print("=" * 70)
    all_success = all(results.values())
    
    for migration, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{migration:30s} {status}")
    
    if all_success:
        print("\n✅ All migrations completed successfully!")
        return True
    else:
        print("\n❌ Some migrations failed. Review errors above.")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run Phase III database migrations')
    parser.add_argument('--db', type=str, default='data/auto_execution.db',
                       help='Database path (default: data/auto_execution.db)')
    parser.add_argument('--test', action='store_true',
                       help='Run in test mode (no backup)')
    parser.add_argument('--production', action='store_true',
                       help='Run in production mode (creates backup)')
    
    args = parser.parse_args()
    
    # Determine mode
    test_mode = not args.production
    
    # Run migrations
    success = run_migrations(args.db, test_mode=test_mode)
    sys.exit(0 if success else 1)

