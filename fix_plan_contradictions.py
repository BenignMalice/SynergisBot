"""
Fix contradictory conditions in auto-execution plans
"""
import sqlite3
import json
from pathlib import Path

db_path = Path("data/auto_execution.db")

if not db_path.exists():
    print(f"ERROR: Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))

# Plan to fix
plan_id = "chatgpt_c6785eba"

cursor = conn.execute("""
    SELECT plan_id, symbol, direction, entry_price, conditions, notes
    FROM trade_plans 
    WHERE plan_id = ?
""", (plan_id,))

row = cursor.fetchone()
if not row:
    print(f"Plan {plan_id} not found")
    conn.close()
    exit(1)

plan_id_db, symbol, direction, entry_price, conditions_json, notes = row
conditions = json.loads(conditions_json) if conditions_json else {}

print(f"Fixing plan: {plan_id_db}")
print(f"Symbol: {symbol}")
print(f"Direction: {direction}")
print(f"Entry: {entry_price}")
print(f"Before: {json.dumps(conditions, indent=2)}")
print()

# Fix: SELL plan should use price_below, not price_above
if direction.upper() == "SELL" and "price_above" in conditions:
    # Remove price_above and add price_below
    price_above_val = conditions.pop("price_above")
    conditions["price_below"] = entry_price  # Use entry_price for price_below
    conditions["price_near"] = entry_price  # Ensure price_near matches entry
    print(f"Fixed: Removed price_above ({price_above_val}), added price_below ({entry_price})")
    print(f"Fixed: Set price_near to entry_price ({entry_price})")
elif direction.upper() == "BUY" and "price_below" in conditions:
    # Remove price_below and add price_above
    price_below_val = conditions.pop("price_below")
    conditions["price_above"] = entry_price  # Use entry_price for price_above
    conditions["price_near"] = entry_price  # Ensure price_near matches entry
    print(f"Fixed: Removed price_below ({price_below_val}), added price_above ({entry_price})")
    print(f"Fixed: Set price_near to entry_price ({entry_price})")

# Ensure price_near matches entry_price if it exists
if "price_near" in conditions:
    price_near = conditions["price_near"]
    if abs(price_near - entry_price) > 10:  # More than 10 points away
        conditions["price_near"] = entry_price
        print(f"Fixed: Changed price_near from {price_near} to {entry_price} (entry_price)")

# Ensure tolerance exists if price_near exists
if "price_near" in conditions and "tolerance" not in conditions:
    # Set default tolerance based on symbol
    if symbol.upper().startswith("BTC"):
        conditions["tolerance"] = 100.0
    elif symbol.upper().startswith("XAU") or symbol.upper().startswith("GOLD"):
        conditions["tolerance"] = 5.0
    else:
        conditions["tolerance"] = 0.001
    print(f"Fixed: Added tolerance ({conditions['tolerance']})")

print()
print(f"After: {json.dumps(conditions, indent=2)}")
print()

# Update database
conn.execute("""
    UPDATE trade_plans 
    SET conditions = ?
    WHERE plan_id = ?
""", (json.dumps(conditions), plan_id_db))

conn.commit()
conn.close()

print("[OK] Plan updated in database")

