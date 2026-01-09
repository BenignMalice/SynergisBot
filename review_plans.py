"""
Review trade plans and verify system is working correctly
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

def review_plans():
    """Review all active plans"""
    db_paths = [
        Path("data/trade_plans.sqlite"),
        Path("data/auto_execution.db"),
    ]
    
    db_path = None
    for path in db_paths:
        if path.exists():
            db_path = path
            break
    
    if not db_path:
        print("[ERROR] Database not found")
        return
    
    print(f"\n{'='*80}")
    print("TRADE PLAN REVIEW")
    print(f"{'='*80}")
    print(f"Database: {db_path}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    plan_ids = [
        "chatgpt_e71be723",  # Delta Absorption
        "chatgpt_8da1d1e5",  # CVD Acceleration
        "chatgpt_631f9739",  # Delta Divergence
        "chatgpt_56d943d9",  # Absorption Reversal Scalp
        "chatgpt_72043641",  # Liquidity Imbalance Rebalance
        "chatgpt_9ad9c84f",  # Breaker + Delta Continuation
        "micro_scalp_a6ec41c2",  # VWAP Reversion Micro-Scalp
    ]
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("""
        SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit,
               volume, conditions, status, created_at, expires_at, notes
        FROM trade_plans
        WHERE plan_id IN ({})
        ORDER BY created_at DESC
    """.format(','.join(['?' for _ in plan_ids])), plan_ids)
    
    plans = cursor.fetchall()
    
    if not plans:
        print("[WARN] No plans found in database")
        # Try to find any plans
        cursor = conn.execute("""
            SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit,
                   volume, conditions, status, created_at, expires_at, notes
            FROM trade_plans
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT 20
        """)
        plans = cursor.fetchall()
        print(f"[INFO] Found {len(plans)} pending plans in database")
    
    order_flow_conditions = [
        "delta_positive", "delta_negative",
        "cvd_rising", "cvd_falling",
        "cvd_div_bear", "cvd_div_bull",
        "delta_divergence_bull", "delta_divergence_bear",
        "avoid_absorption_zones", "absorption_zone_detected"
    ]
    
    for plan in plans:
        plan_id, symbol, direction, entry, sl, tp, volume, conditions_json, status, created_at, expires_at, notes = plan
        
        print(f"\n{'-'*80}")
        print(f"Plan ID: {plan_id}")
        print(f"Symbol: {symbol}")
        print(f"Direction: {direction}")
        print(f"Entry: {entry}")
        print(f"SL: {sl}")
        print(f"TP: {tp}")
        print(f"Volume: {volume}")
        print(f"Status: {status}")
        print(f"Created: {created_at}")
        if expires_at:
            print(f"Expires: {expires_at}")
        if notes:
            print(f"Notes: {notes}")
        
        # Parse conditions
        conditions = {}
        if conditions_json:
            try:
                conditions = json.loads(conditions_json)
                print(f"\nConditions:")
                for key, value in conditions.items():
                    print(f"  {key}: {value}")
                
                # Check for order flow conditions
                has_of = any(conditions.get(cond) for cond in order_flow_conditions)
                if has_of:
                    print(f"\n[ORDER FLOW PLAN]")
                    of_conds = [k for k in conditions.keys() if k in order_flow_conditions]
                    print(f"  Order flow conditions: {of_conds}")
            except json.JSONDecodeError:
                print(f"\n[ERROR] Failed to parse conditions JSON")
        
        # Validate SL/TP for direction
        if direction == "BUY":
            if sl >= entry:
                print(f"\n[ERROR] BUY plan: SL ({sl}) must be < Entry ({entry})")
            if tp <= entry:
                print(f"\n[ERROR] BUY plan: TP ({tp}) must be > Entry ({entry})")
        elif direction == "SELL":
            if sl <= entry:
                print(f"\n[ERROR] SELL plan: SL ({sl}) must be > Entry ({entry})")
            if tp >= entry:
                print(f"\n[ERROR] SELL plan: TP ({tp}) must be < Entry ({entry})")
        
        # Calculate distances
        sl_distance = abs(entry - sl)
        tp_distance = abs(tp - entry)
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
        
        print(f"\nDistances:")
        print(f"  SL distance: ${sl_distance:.2f}")
        print(f"  TP distance: ${tp_distance:.2f}")
        print(f"  R:R ratio: {rr_ratio:.2f}:1")
        
        # Check micro-scalp rules
        if "micro_scalp" in plan_id or conditions.get("plan_type") == "micro_scalp":
            print(f"\n[MICRO-SCALP PLAN]")
            if "BTC" in symbol.upper():
                if sl_distance > 10:
                    print(f"  [ERROR] BTC micro-scalp SL distance ({sl_distance:.2f}) exceeds $10 limit")
                elif sl_distance < 5:
                    print(f"  [WARN] BTC micro-scalp SL distance ({sl_distance:.2f}) is below $5 minimum")
            elif "XAU" in symbol.upper():
                if sl_distance > 1.20:
                    print(f"  [ERROR] XAU micro-scalp SL distance ({sl_distance:.2f}) exceeds $1.20 limit")
                elif sl_distance < 0.50:
                    print(f"  [WARN] XAU micro-scalp SL distance ({sl_distance:.2f}) is below $0.50 minimum")
    
    conn.close()
    
    print(f"\n{'-'*80}")
    print("REVIEW COMPLETE")
    print(f"{'='*80}")

if __name__ == "__main__":
    review_plans()

