"""
Verify that a plan has all recommended enhancements
"""
import sqlite3
import json
from pathlib import Path

plan_id = "chatgpt_14f79556"
db_path = Path("data/auto_execution.db")

if not db_path.exists():
    print(f"Database not found: {db_path}")
    exit(1)

with sqlite3.connect(db_path) as conn:
    cursor = conn.execute("""
        SELECT plan_id, symbol, direction, conditions, notes
        FROM trade_plans 
        WHERE plan_id = ?
    """, (plan_id,))
    
    row = cursor.fetchone()
    
    if not row:
        print(f"Plan {plan_id} not found")
        exit(1)
    
    print("=" * 60)
    print(f"VERIFICATION: Plan {plan_id}")
    print("=" * 60)
    print(f"\nPlan ID: {row[0]}")
    print(f"Symbol: {row[1]}")
    print(f"Direction: {row[2]}")
    
    conditions = json.loads(row[3])
    print("\nConditions:")
    print(json.dumps(conditions, indent=2))
    
    print("\n" + "=" * 60)
    print("ENHANCEMENT CHECK:")
    print("=" * 60)
    
    has_m1 = conditions.get("m1_choch_bos_combo", False)
    has_min_vol = conditions.get("min_volatility") is not None
    has_bb = conditions.get("bb_width_threshold") is not None
    has_timeframe = conditions.get("timeframe") is not None
    has_choch = conditions.get("choch_bull") or conditions.get("choch_bear")
    
    print(f"  [*] M1 Validation (m1_choch_bos_combo): {has_m1} {'[OK]' if has_m1 else '[MISSING]'}")
    print(f"  [*] Min Volatility: {conditions.get('min_volatility', 'NOT SET')} {'[OK]' if has_min_vol else '[MISSING]'}")
    print(f"  [*] BB Width Threshold: {conditions.get('bb_width_threshold', 'NOT SET')} {'[OK]' if has_bb else '[MISSING]'}")
    print(f"  [*] Timeframe: {conditions.get('timeframe', 'NOT SET')} {'[OK]' if has_timeframe else '[MISSING]'}")
    print(f"  [*] CHOCH Condition: {has_choch} {'[OK]' if has_choch else '[MISSING]'}")
    
    print("\n" + "=" * 60)
    if all([has_m1, has_min_vol, has_bb, has_timeframe, has_choch]):
        print("STATUS: ALL ENHANCEMENTS PRESENT! [SUCCESS]")
    else:
        missing = []
        if not has_m1: missing.append("M1 Validation")
        if not has_min_vol: missing.append("Min Volatility")
        if not has_bb: missing.append("BB Width Threshold")
        if not has_timeframe: missing.append("Timeframe")
        if not has_choch: missing.append("CHOCH Condition")
        print(f"STATUS: MISSING: {', '.join(missing)}")
    print("=" * 60)

