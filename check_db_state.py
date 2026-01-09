"""Check production database state before migration"""
import sqlite3
import sys
import codecs
from pathlib import Path

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

db_path = "data/auto_execution.db"
db_path_obj = Path(db_path)

if not db_path_obj.exists():
    print(f"❌ Database not found: {db_path}")
    sys.exit(1)

print(f"Checking database: {db_path}")
print("=" * 60)

with sqlite3.connect(db_path) as conn:
    # Check existing tables
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Existing tables: {tables}")
    
    # Check if trade_plans exists
    if 'trade_plans' in tables:
        cursor = conn.execute("PRAGMA table_info(trade_plans)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"\ntrade_plans columns: {columns}")
        
        # Check for Phase III columns
        phase3_cols = ['cancellation_reason', 'last_cancellation_check']
        for col in phase3_cols:
            if col in columns:
                print(f"  ✅ {col} already exists")
            else:
                print(f"  ⚠️  {col} missing (will be added)")
    else:
        print("\n⚠️  trade_plans table not found")
    
    # Check for Phase III tables
    phase3_tables = ['pattern_history', 'plan_execution_state']
    for table in phase3_tables:
        if table in tables:
            print(f"\n✅ {table} table already exists")
            cursor = conn.execute(f"PRAGMA table_info({table})")
            cols = [row[1] for row in cursor.fetchall()]
            print(f"   Columns: {cols}")
        else:
            print(f"\n⚠️  {table} table missing (will be created)")

print("\n" + "=" * 60)
print("Database ready for migration")

