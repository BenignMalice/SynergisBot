"""
Fix existing bracket trade plans with contradictory price_above/price_below conditions
"""
import sqlite3
import json
from pathlib import Path

db_path = Path("data/auto_execution.db")

if not db_path.exists():
    print(f"ERROR: Database not found at {db_path}")
    exit(1)

# Plan IDs to fix
plan_ids = ["chatgpt_6102a854", "chatgpt_102a8852"]

conn = sqlite3.connect(str(db_path))

for plan_id in plan_ids:
    cursor = conn.execute("""
        SELECT plan_id, symbol, direction, conditions, notes
        FROM trade_plans 
        WHERE plan_id = ?
    """, (plan_id,))
    
    row = cursor.fetchone()
    if not row:
        print(f"Plan {plan_id} not found")
        continue
    
    plan_id_db, symbol, direction, conditions_json, notes = row
    conditions = json.loads(conditions_json) if conditions_json else {}
    
    print(f"\nFixing plan: {plan_id_db}")
    print(f"  Symbol: {symbol}")
    print(f"  Direction: {direction}")
    print(f"  Before: price_above={conditions.get('price_above')}, price_below={conditions.get('price_below')}")
    
    # Fix based on direction
    if direction == "BUY":
        # BUY should only have price_above
        if "price_below" in conditions:
            del conditions["price_below"]
            print(f"  Removed price_below from BUY plan")
    elif direction == "SELL":
        # SELL should only have price_below
        if "price_above" in conditions:
            del conditions["price_above"]
            print(f"  Removed price_above from SELL plan")
    
    print(f"  After: price_above={conditions.get('price_above')}, price_below={conditions.get('price_below')}")
    
    # Fix price_near - should match entry price, not midpoint
    cursor_entry = conn.execute("SELECT entry_price FROM trade_plans WHERE plan_id = ?", (plan_id_db,))
    entry_price_row = cursor_entry.fetchone()
    if entry_price_row:
        entry_price = entry_price_row[0]
        old_price_near = conditions.get('price_near')
        conditions["price_near"] = entry_price
        print(f"  Fixed price_near: {old_price_near} -> {entry_price} (entry price)")
    
    # Update database
    conn.execute("""
        UPDATE trade_plans 
        SET conditions = ?
        WHERE plan_id = ?
    """, (json.dumps(conditions), plan_id_db))
    
    print(f"  [OK] Updated in database")

conn.commit()
conn.close()

print("\n[OK] All bracket trade plans fixed!")

