"""
Check all pending plans for recommended enhancements
"""
import sqlite3
import json
from pathlib import Path

db_path = Path("data/auto_execution.db")

if not db_path.exists():
    print(f"Database not found: {db_path}")
    exit(1)

with sqlite3.connect(db_path) as conn:
    cursor = conn.execute("""
        SELECT plan_id, symbol, direction, conditions, notes, created_at
        FROM trade_plans
        WHERE status = 'pending'
        ORDER BY created_at DESC
    """)
    
    plans = cursor.fetchall()
    
    print("=" * 80)
    print("PENDING PLANS - ENHANCEMENT CHECK")
    print("=" * 80)
    print()
    
    choch_plans = 0
    plans_with_m1 = 0
    plans_with_vol = 0
    plans_with_bb = 0
    
    for plan_id, symbol, direction, conditions_json, notes, created_at in plans:
        conditions = json.loads(conditions_json) if conditions_json else {}
        
        print(f"Plan ID: {plan_id}")
        print(f"Symbol: {symbol} | Direction: {direction}")
        print(f"Created: {created_at}")
        
        # Check for CHOCH plans
        is_choch = conditions.get("choch_bull") or conditions.get("choch_bear")
        if is_choch:
            choch_plans += 1
        
        # Check enhancements
        has_m1 = conditions.get("m1_choch_bos_combo", False)
        has_min_vol = conditions.get("min_volatility") is not None
        has_bb = conditions.get("bb_width_threshold") is not None
        
        if has_m1:
            plans_with_m1 += 1
        if has_min_vol:
            plans_with_vol += 1
        if has_bb:
            plans_with_bb += 1
        
        print(f"  CHOCH Plan: {is_choch}")
        print(f"  [*] M1 Validation: {has_m1} {'[OK]' if has_m1 or not is_choch else '[MISSING]'}")
        print(f"  [*] Min Volatility: {has_min_vol} {'[OK]' if has_min_vol else '[MISSING]'}")
        print(f"  [*] BB Width Threshold: {has_bb} {'[OK]' if has_bb else '[MISSING]'}")
        
        if notes:
            print(f"  Notes: {notes[:80]}...")
        
        print()
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total pending plans: {len(plans)}")
    print(f"CHOCH plans: {choch_plans}")
    print(f"Plans with M1 validation: {plans_with_m1}")
    print(f"Plans with min_volatility: {plans_with_vol}")
    print(f"Plans with bb_width_threshold: {plans_with_bb}")
    print("=" * 80)

