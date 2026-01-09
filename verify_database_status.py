"""Verify database status after fix"""
import sqlite3
from pathlib import Path

db_path = Path("data/auto_execution.db")
conn = sqlite3.connect(str(db_path))

# Get status counts
cursor = conn.execute("""
    SELECT status, COUNT(*) as count
    FROM trade_plans
    GROUP BY status
    ORDER BY count DESC
""")
rows = cursor.fetchall()

print("=" * 80)
print("DATABASE STATUS VERIFICATION")
print("=" * 80)
print()
print("Status Breakdown:")
for status, count in rows:
    print(f"  {status}: {count}")

# Get pending plans
cursor = conn.execute("""
    SELECT plan_id, symbol, direction, entry_price, expires_at
    FROM trade_plans
    WHERE status = 'pending'
    ORDER BY created_at DESC
""")
pending_plans = cursor.fetchall()

print()
print(f"Pending Plans ({len(pending_plans)}):")
for plan_id, symbol, direction, entry_price, expires_at in pending_plans:
    print(f"  - {plan_id}: {symbol} {direction} @ {entry_price} (expires: {expires_at})")

conn.close()

print()
print("=" * 80)

