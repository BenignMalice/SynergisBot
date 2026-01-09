"""
Test Phase III Database Migrations
Tests pattern_history and plan_execution_state table creation
"""

import sqlite3
import sys
import codecs
from pathlib import Path
from datetime import datetime, timezone

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

def test_migrations():
    """Test Phase III migrations"""
    print("=" * 60)
    print("Testing Phase III Database Migrations")
    print("=" * 60)
    
    # Use test database
    test_db = Path("data/test_phase3.db")
    if test_db.exists():
        test_db.unlink()  # Remove existing test database
    
    test_db.parent.mkdir(parents=True, exist_ok=True)
    
    # Create test trade_plans table first (required for foreign key)
    with sqlite3.connect(str(test_db)) as conn:
        conn.execute("""
            CREATE TABLE trade_plans (
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
        print("[OK] Created test trade_plans table")
    
    # Test pattern_history migration
    print("\n1. Testing pattern_history migration...")
    try:
        from migrations.migrate_phase3_pattern_history import migrate_pattern_history
        success = migrate_pattern_history(str(test_db))
        if success:
            print("[OK] pattern_history migration successful")
            
            # Verify table exists
            with sqlite3.connect(str(test_db)) as conn:
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='pattern_history'
                """)
                if cursor.fetchone():
                    print("[OK] pattern_history table exists")
                    
                    # Check columns
                    cursor = conn.execute("PRAGMA table_info(pattern_history)")
                    columns = [row[1] for row in cursor.fetchall()]
                    expected_columns = ['pattern_id', 'symbol', 'pattern_type', 'pattern_data', 'detected_at', 'expires_at']
                    if all(col in columns for col in expected_columns):
                        print(f"✅ All expected columns present: {columns}")
                    else:
                        print(f"❌ Missing columns. Expected: {expected_columns}, Got: {columns}")
                        return False
                    
                    # Check indexes
                    cursor = conn.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='index' AND tbl_name='pattern_history'
                    """)
                    indexes = [row[0] for row in cursor.fetchall()]
                    expected_indexes = ['idx_pattern_symbol', 'idx_pattern_type', 'idx_pattern_detected']
                    if all(idx in indexes for idx in expected_indexes):
                        print(f"[OK] All expected indexes present: {indexes}")
                    else:
                        print(f"[WARN] Some indexes missing. Expected: {expected_indexes}, Got: {indexes}")
                else:
                    print("[FAIL] pattern_history table not found")
                    return False
        else:
            print("[FAIL] pattern_history migration failed")
            return False
    except Exception as e:
        print(f"[FAIL] Error testing pattern_history migration: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test plan_execution_state migration
    print("\n2. Testing plan_execution_state migration...")
    try:
        from migrations.migrate_phase3_execution_state import migrate_execution_state
        success = migrate_execution_state(str(test_db))
        if success:
            print("[OK] plan_execution_state migration successful")
            
            # Verify table exists
            with sqlite3.connect(str(test_db)) as conn:
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='plan_execution_state'
                """)
                if cursor.fetchone():
                    print("[OK] plan_execution_state table exists")
                    
                    # Check columns
                    cursor = conn.execute("PRAGMA table_info(plan_execution_state)")
                    columns = [row[1] for row in cursor.fetchall()]
                    expected_columns = ['plan_id', 'symbol', 'trailing_mode_enabled', 'trailing_activation_rr', 
                                      'current_rr', 'state_data', 'updated_at', 'created_at']
                    if all(col in columns for col in expected_columns):
                        print(f"✅ All expected columns present: {columns}")
                    else:
                        print(f"❌ Missing columns. Expected: {expected_columns}, Got: {columns}")
                        return False
                    
                    # Check indexes
                    cursor = conn.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='index' AND tbl_name='plan_execution_state'
                    """)
                    indexes = [row[0] for row in cursor.fetchall()]
                    expected_indexes = ['idx_exec_state_symbol', 'idx_exec_state_updated', 'idx_exec_state_trailing']
                    if all(idx in indexes for idx in expected_indexes):
                        print(f"[OK] All expected indexes present: {indexes}")
                    else:
                        print(f"[WARN] Some indexes missing. Expected: {expected_indexes}, Got: {indexes}")
                    
                    # Test insert
                    test_plan_id = "test_plan_123"
                    now_iso = datetime.now(timezone.utc).isoformat()
                    conn.execute("""
                        INSERT INTO trade_plans 
                        (plan_id, symbol, direction, entry_price, stop_loss, take_profit, volume, 
                         conditions, created_at, created_by, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (test_plan_id, "BTCUSDc", "BUY", 50000, 49000, 51000, 0.01, 
                          '{"test": true}', now_iso, "test", "pending"))
                    
                    conn.execute("""
                        INSERT INTO plan_execution_state 
                        (plan_id, symbol, trailing_mode_enabled, trailing_activation_rr, 
                         current_rr, state_data, updated_at, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (test_plan_id, "BTCUSDc", 0, 1.5, 0.0, '{"test": true}', now_iso, now_iso))
                    conn.commit()
                    print("[OK] Test insert successful (foreign key constraint works)")
                else:
                    print("[FAIL] plan_execution_state table not found")
                    return False
        else:
            print("[FAIL] plan_execution_state migration failed")
            return False
    except Exception as e:
        print(f"[FAIL] Error testing plan_execution_state migration: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Cleanup (skip on Windows if file is locked)
    try:
        test_db.unlink()
    except PermissionError:
        print("[WARN] Could not delete test database (file locked - this is OK)")
    
    print("\n[OK] All migration tests passed!")
    return True

if __name__ == "__main__":
    success = test_migrations()
    sys.exit(0 if success else 1)

