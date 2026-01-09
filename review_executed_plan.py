"""
Review a specific executed trade plan
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import json
from datetime import datetime

def review_plan(plan_id: str, db_path: str = "data/auto_execution.db"):
    """Review a specific plan by ID"""
    
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get plan
    cursor.execute("""
        SELECT *
        FROM trade_plans
        WHERE plan_id = ?
    """, (plan_id,))
    
    plan = cursor.fetchone()
    conn.close()
    
    if not plan:
        print(f"[ERROR] Plan '{plan_id}' not found in database")
        return
    
    print("=" * 80)
    print(f"TRADE PLAN REVIEW: {plan_id}")
    print("=" * 80)
    print()
    
    # Basic info
    print("[BASIC INFORMATION]")
    print(f"  Plan ID: {plan['plan_id']}")
    print(f"  Symbol: {plan['symbol']}")
    print(f"  Direction: {plan['direction']}")
    print(f"  Status: {plan['status']}")
    print(f"  Created: {plan['created_at']}")
    print(f"  Created By: {plan['created_by']}")
    if plan['expires_at']:
        print(f"  Expires: {plan['expires_at']}")
    print()
    
    # Trade details
    print("[TRADE DETAILS]")
    print(f"  Planned Entry Price: {plan['entry_price']:.2f}")
    
    # Check if user reported different entry (from notes or manual input)
    user_reported_entry = None
    if plan['notes']:
        # Try to extract from notes
        import re
        entry_match = re.search(r'entry[:\s]+(\d+\.?\d*)', plan['notes'], re.IGNORECASE)
        if entry_match:
            try:
                user_reported_entry = float(entry_match.group(1))
            except:
                pass
    
    # Allow manual override via command line
    import sys
    if len(sys.argv) > 2:
        try:
            user_reported_entry = float(sys.argv[2])
        except:
            pass
    
    if user_reported_entry:
        entry_slippage = user_reported_entry - plan['entry_price']
        entry_slippage_pct = (entry_slippage / plan['entry_price']) * 100 if plan['entry_price'] > 0 else 0
        print(f"  Actual Entry Price: {user_reported_entry:.2f} (user reported)")
        if abs(entry_slippage) > 0.01:
            if entry_slippage > 0:
                print(f"  Slippage: +{entry_slippage:.2f} ({entry_slippage_pct:+.2f}%) - worse fill")
            else:
                print(f"  Slippage: {entry_slippage:.2f} ({entry_slippage_pct:+.2f}%) - better fill")
        else:
            print(f"  Slippage: None (exact match)")
        # Use actual entry for distance calculations
        actual_entry = user_reported_entry
    else:
        actual_entry = plan['entry_price']
    
    print(f"  Stop Loss: {plan['stop_loss']:.2f}")
    print(f"  Take Profit: {plan['take_profit']:.2f}")
    print(f"  Volume: {plan['volume']:.2f} lots")
    
    # Calculate distances using actual entry
    sl_distance = abs(actual_entry - plan['stop_loss'])
    tp_distance = abs(plan['take_profit'] - actual_entry)
    if sl_distance > 0:
        rr_ratio = tp_distance / sl_distance
        print(f"  R:R Ratio: {rr_ratio:.2f}:1")
        print(f"  SL Distance: {sl_distance:.2f}")
        print(f"  TP Distance: {tp_distance:.2f}")
    print()
    
    # Execution details
    if plan['status'] in ['executed', 'closed']:
        print("[EXECUTION DETAILS]")
        if plan['executed_at']:
            print(f"  Executed At: {plan['executed_at']}")
        if plan['ticket']:
            print(f"  MT5 Ticket: {plan['ticket']}")
        if plan['exit_price']:
            print(f"  Exit Price: {plan['exit_price']:.2f}")
            # Check if hit SL or TP
            if plan['direction'] == 'BUY':
                if abs(plan['exit_price'] - plan['stop_loss']) < 0.01:
                    print(f"  -> Hit Stop Loss ({plan['stop_loss']:.2f})")
                elif abs(plan['exit_price'] - plan['take_profit']) < 0.01:
                    print(f"  -> Hit Take Profit ({plan['take_profit']:.2f})")
            else:  # SELL
                if abs(plan['exit_price'] - plan['stop_loss']) < 0.01:
                    print(f"  -> Hit Stop Loss ({plan['stop_loss']:.2f})")
                elif abs(plan['exit_price'] - plan['take_profit']) < 0.01:
                    print(f"  -> Hit Take Profit ({plan['take_profit']:.2f})")
        if plan['close_time']:
            print(f"  Close Time: {plan['close_time']}")
        if plan['close_reason']:
            print(f"  Close Reason: {plan['close_reason']}")
        if plan['profit_loss'] is not None:
            pnl = plan['profit_loss']
            pnl_str = f"${pnl:+.2f}" if pnl != 0 else "$0.00"
            print(f"  Profit/Loss: {pnl_str}")
        print()
    
    # Conditions
    if plan['conditions']:
        print("[CONDITIONS]")
        conditions = json.loads(plan['conditions'])
        
        # Group conditions by type
        price_conditions = []
        order_flow_conditions = []
        pattern_conditions = []
        other_conditions = []
        
        for key, value in conditions.items():
            if key.startswith('price_'):
                price_conditions.append(f"{key}: {value}")
            elif any(x in key for x in ['order_block', 'liquidity', 'fvg', 'cvd', 'delta']):
                order_flow_conditions.append(f"{key}: {value}")
            elif key.startswith('pattern_'):
                pattern_conditions.append(f"{key}: {value}")
            else:
                other_conditions.append(f"{key}: {value}")
        
        if price_conditions:
            print("  Price Conditions:")
            for cond in price_conditions:
                print(f"    - {cond}")
        
        if order_flow_conditions:
            print("  Order Flow Conditions:")
            for cond in order_flow_conditions:
                print(f"    - {cond}")
        
        if pattern_conditions:
            print("  Pattern Conditions:")
            for cond in pattern_conditions:
                print(f"    - {cond}")
        
        if other_conditions:
            print("  Other Conditions:")
            for cond in other_conditions:
                print(f"    - {cond}")
        print()
    
    # Notes
    if plan['notes']:
        print("[NOTES]")
        print(f"  {plan['notes']}")
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if plan['status'] in ['executed', 'closed']:
        if plan['profit_loss'] is not None:
            pnl = plan['profit_loss']
            if pnl > 0:
                print(f"[SUCCESS] Trade was profitable: ${pnl:+.2f}")
            elif pnl < 0:
                print(f"[LOSS] Trade resulted in loss: ${pnl:.2f}")
            else:
                print(f"[BREAKEVEN] Trade closed at breakeven")
            
            # Show outcome details
            if plan['exit_price']:
                if plan['direction'] == 'BUY':
                    if abs(plan['exit_price'] - plan['stop_loss']) < 0.01:
                        print(f"[OUTCOME] Stop Loss hit at {plan['exit_price']:.2f}")
                    elif abs(plan['exit_price'] - plan['take_profit']) < 0.01:
                        print(f"[OUTCOME] Take Profit hit at {plan['exit_price']:.2f}")
                    else:
                        print(f"[OUTCOME] Closed at {plan['exit_price']:.2f} (manual/other)")
                else:  # SELL
                    if abs(plan['exit_price'] - plan['stop_loss']) < 0.01:
                        print(f"[OUTCOME] Stop Loss hit at {plan['exit_price']:.2f}")
                    elif abs(plan['exit_price'] - plan['take_profit']) < 0.01:
                        print(f"[OUTCOME] Take Profit hit at {plan['exit_price']:.2f}")
                    else:
                        print(f"[OUTCOME] Closed at {plan['exit_price']:.2f} (manual/other)")
            
            # Calculate actual vs expected
            entry_for_calc = user_reported_entry if user_reported_entry else plan['entry_price']
            if entry_for_calc and plan['exit_price']:
                if plan['direction'] == 'BUY':
                    price_move = plan['exit_price'] - entry_for_calc
                else:  # SELL
                    price_move = entry_for_calc - plan['exit_price']
                print(f"[PRICE MOVE] {price_move:+.2f} points from {'actual' if user_reported_entry else 'planned'} entry")
        else:
            print("[INFO] Trade executed but P/L not yet recorded")
    else:
        print(f"[INFO] Plan status: {plan['status']}")
    
    print()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        plan_id = sys.argv[1]
    else:
        plan_id = input("Enter plan ID: ").strip()
    
    review_plan(plan_id)
