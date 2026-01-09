"""Check why test plans were cancelled"""
import sqlite3
import sys
import codecs

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

db_path = "data/auto_execution.db"
test_plan_ids = ["chatgpt_d05d9985", "chatgpt_0a116fe0"]

with sqlite3.connect(db_path) as conn:
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    for plan_id in test_plan_ids:
        cursor.execute("""
            SELECT plan_id, status, cancellation_reason, created_at, expires_at
            FROM trade_plans
            WHERE plan_id = ?
        """, (plan_id,))
        
        row = cursor.fetchone()
        if row:
            print(f"\nPlan {plan_id}:")
            print(f"  Status: {row['status']}")
            print(f"  Cancellation Reason: {row['cancellation_reason'] or 'None'}")
            print(f"  Created: {row['created_at']}")
            print(f"  Expires: {row['expires_at']}")

