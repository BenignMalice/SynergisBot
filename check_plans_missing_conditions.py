"""
Check for missing recommended conditions in auto-execution plans
"""
import sqlite3
import json
from pathlib import Path

db_path = Path("data/auto_execution.db")

if not db_path.exists():
    print(f"ERROR: Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.execute("""
    SELECT plan_id, symbol, direction, entry_price, conditions, status, notes
    FROM trade_plans 
    WHERE status = 'pending'
    ORDER BY created_at DESC
""")

plans = cursor.fetchall()

print("=" * 80)
print("AUTO-EXECUTION PLANS - MISSING CONDITIONS CHECK")
print("=" * 80)
print()

total_plans = len(plans)
plans_with_warnings = 0
total_warnings = 0

for row in plans:
    plan_id, symbol, direction, entry_price, conditions_json, status, notes = row
    
    if not conditions_json:
        continue
    
    try:
        conditions = json.loads(conditions_json) if conditions_json else {}
    except:
        continue
    
    warnings = []
    
    # Check 1: Has price_above or price_below but missing price_near
    has_price_above = "price_above" in conditions
    has_price_below = "price_below" in conditions
    
    if (has_price_above or has_price_below) and "price_near" not in conditions:
        warnings.append("Has price_above/price_below but missing price_near - recommended for tighter execution control")
    
    # Check 2: Has price_near but missing tolerance
    if "price_near" in conditions and "tolerance" not in conditions:
        warnings.append("Has price_near but missing tolerance - system will use default, but explicit is better")
    
    # Check 3: Has choch_bull/bear but missing price_near
    has_choch = conditions.get("choch_bull") or conditions.get("choch_bear")
    if has_choch and "price_near" not in conditions:
        warnings.append("Has CHOCH condition but missing price_near - plan may execute at ANY price when CHOCH confirms")
    
    # Check 4: Has order_block but missing price_near
    if conditions.get("order_block") and "price_near" not in conditions:
        warnings.append("Has order_block but missing price_near - recommended for tighter execution control")
    
    # Check 5: Has rejection_wick but missing price_near
    if conditions.get("rejection_wick") and "price_near" not in conditions:
        warnings.append("Has rejection_wick but missing price_near - recommended for tighter execution control")
    
    if warnings:
        plans_with_warnings += 1
        total_warnings += len(warnings)
        
        print(f"Plan ID: {plan_id}")
        print(f"Symbol: {symbol} | Direction: {direction} | Entry: {entry_price}")
        print(f"Notes: {notes[:80] if notes else 'None'}")
        print()
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. [WARNING] {warning}")
        print()
        print("-" * 80)
        print()

if plans_with_warnings == 0:
    print(f"[OK] All {total_plans} pending plans have recommended conditions!")
else:
    print(f"[INFO] Found {total_warnings} warning(s) in {plans_with_warnings} plan(s) out of {total_plans} total pending plans")
    print()
    print("NOTE: These are recommendations for better execution control, not critical errors.")

conn.close()

