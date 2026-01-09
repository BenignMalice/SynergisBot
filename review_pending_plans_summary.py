"""
Quick Summary of Pending Auto Execution Plans
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import codecs
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

import sqlite3
import json

db_path = "data/auto_execution.db"
if not os.path.exists(db_path):
    print("[ERROR] Database not found")
    sys.exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get pending plans
cursor.execute("""
    SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit,
           volume, status, conditions, created_at, expires_at
    FROM trade_plans
    WHERE status = 'pending'
    ORDER BY created_at DESC
""")

plans = cursor.fetchall()

print("=" * 70)
print("PENDING AUTO EXECUTION PLANS SUMMARY")
print("=" * 70)
print()

if not plans:
    print("[INFO] No pending plans found")
    sys.exit(0)

print(f"[OK] Found {len(plans)} pending plan(s)")
print()

# Group by symbol
plans_by_symbol = {}
for plan in plans:
    symbol = plan['symbol']
    if symbol not in plans_by_symbol:
        plans_by_symbol[symbol] = []
    plans_by_symbol[symbol].append(plan)

print("Plans by Symbol:")
for symbol, symbol_plans in sorted(plans_by_symbol.items()):
    print(f"  {symbol}: {len(symbol_plans)} plan(s)")
print()

# Show pending plans
for idx, plan in enumerate(plans, 1):
    print(f"[{idx}/{len(plans)}] {plan['plan_id']}")
    print(f"   Symbol: {plan['symbol']}")
    print(f"   Direction: {plan['direction']}")
    
    entry_price = plan.get('entry_price')
    if entry_price:
        print(f"   Entry: {entry_price:.2f}")
    else:
        print(f"   Entry: N/A")
    
    print(f"   SL: {plan['stop_loss']:.2f if plan['stop_loss'] else 'None'}")
    print(f"   TP: {plan['take_profit']:.2f if plan['take_profit'] else 'None'}")
    print(f"   Volume: {plan['volume']}")
    
    # Parse conditions
    conditions = None
    if plan['conditions']:
        try:
            conditions = json.loads(plan['conditions'])
        except:
            pass
    
    if conditions and isinstance(conditions, dict):
        # Check for order flow conditions
        order_flow_keys = ['delta_positive', 'cvd_rising', 'cvd_div_bear', 'cvd_div_bull',
                          'delta_divergence_bull', 'delta_divergence_bear', 'absorption_zone_detected']
        has_order_flow = any(key in conditions for key in order_flow_keys)
        
        # Show key conditions
        key_conditions = []
        if 'price_near' in conditions:
            key_conditions.append(f"price_near: {conditions['price_near']}")
        if 'tolerance' in conditions:
            key_conditions.append(f"tolerance: {conditions['tolerance']}")
        if has_order_flow:
            of_conds = {k: v for k, v in conditions.items() if k in order_flow_keys}
            key_conditions.append(f"order_flow: {of_conds}")
        
        if key_conditions:
            print(f"   Key Conditions: {', '.join(key_conditions)}")
    
    print(f"   Created: {plan['created_at'][:19] if plan['created_at'] else 'N/A'}")
    print(f"   Expires: {plan['expires_at'][:19] if plan['expires_at'] else 'Never'}")
    print()

# Check for order flow plans
order_flow_plans = []
for plan in plans:
    conditions = None
    if plan['conditions']:
        try:
            conditions = json.loads(plan['conditions'])
        except:
            pass
    
    if conditions and isinstance(conditions, dict):
        order_flow_keys = ['delta_positive', 'cvd_rising', 'cvd_div_bear', 'cvd_div_bull',
                          'delta_divergence_bull', 'delta_divergence_bear', 'absorption_zone_detected']
        if any(key in conditions for key in order_flow_keys):
            order_flow_plans.append(plan)

print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total Pending Plans: {len(plans)}")
print(f"Order Flow Plans: {len(order_flow_plans)}")
print(f"Regular Plans: {len(plans) - len(order_flow_plans)}")
print("=" * 70)

conn.close()
