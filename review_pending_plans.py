"""
Review Pending Auto Execution Plans

Quick review of pending plans with focus on:
1. Pending plans count and details
2. Order flow plans
3. Monitoring status
4. Recent activity
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import codecs
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

import sqlite3
import json

print("=" * 70)
print("PENDING AUTO EXECUTION PLANS REVIEW")
print("=" * 70)
print()

# Connect to database
db_path = "data/auto_execution.db"
if not os.path.exists(db_path):
    print(f"[ERROR] Database not found: {db_path}")
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

pending_plans = cursor.fetchall()

print(f"[1/4] PENDING PLANS SUMMARY")
print("-" * 70)
print(f"[OK] Found {len(pending_plans)} pending plan(s)")
print()

if not pending_plans:
    print("[INFO] No pending plans found")
    sys.exit(0)

# Group by symbol
plans_by_symbol = {}
for plan in pending_plans:
    symbol = plan['symbol']
    if symbol not in plans_by_symbol:
        plans_by_symbol[symbol] = []
    plans_by_symbol[symbol].append(plan)

print("Plans by symbol:")
for symbol, symbol_plans in plans_by_symbol.items():
    print(f"  {symbol}: {len(symbol_plans)} plan(s)")
print()

# Show pending plans (limit to 20 most recent)
print(f"[2/4] PENDING PLANS DETAILS (showing first 20)")
print("-" * 70)
for idx, plan in enumerate(pending_plans[:20], 1):
    print(f"[{idx}/{len(pending_plans)}] {plan['plan_id'][:30]}...")
    print(f"   Symbol: {plan['symbol']}")
    print(f"   Direction: {plan['direction']}")
    entry_str = f"{plan['entry_price']:.2f}" if plan['entry_price'] else "N/A"
    print(f"   Entry: {entry_str}")
    sl_str = f"{plan['stop_loss']:.2f}" if plan['stop_loss'] else "None"
    print(f"   SL: {sl_str}")
    tp_str = f"{plan['take_profit']:.2f}" if plan['take_profit'] else "None"
    print(f"   TP: {tp_str}")
    print(f"   Volume: {plan['volume']}")
    
    # Parse conditions
    conditions = None
    if plan['conditions']:
        try:
            conditions = json.loads(plan['conditions'])
        except:
            pass
    
    if conditions and isinstance(conditions, dict):
        # Show key conditions
        key_conditions = []
        for key in ['price_near', 'price_above', 'price_below', 'delta_positive', 'cvd_rising',
                   'cvd_div_bear', 'cvd_div_bull', 'delta_divergence_bull', 'delta_divergence_bear',
                   'absorption_zone_detected', 'liquidity_sweep', 'choch_bull', 'choch_bear',
                   'bos_bull', 'bos_bear', 'order_block']:
            if key in conditions:
                key_conditions.append(f"{key}={conditions[key]}")
        
        if key_conditions:
            print(f"   Key Conditions: {', '.join(key_conditions[:5])}")
    
    print(f"   Created: {plan['created_at'][:19]}")
    print(f"   Expires: {plan['expires_at'][:19] if plan['expires_at'] else 'Never'}")
    print()

# Check order flow plans
print(f"[3/4] ORDER FLOW PLANS")
print("-" * 70)
order_flow_plans = []
order_flow_conditions = ['delta_positive', 'cvd_rising', 'cvd_div_bear', 'cvd_div_bull',
                         'delta_divergence_bull', 'delta_divergence_bear', 'absorption_zone_detected']

for plan in pending_plans:
    conditions = None
    if plan['conditions']:
        try:
            conditions = json.loads(plan['conditions'])
        except:
            pass
    
    if conditions and isinstance(conditions, dict):
        has_order_flow = any(key in conditions for key in order_flow_conditions)
        if has_order_flow:
            order_flow_plans.append(plan)

if order_flow_plans:
    print(f"[OK] Found {len(order_flow_plans)} pending plan(s) with order flow conditions:")
    for plan in order_flow_plans:
        conditions = json.loads(plan['conditions']) if plan['conditions'] else {}
        of_conds = {k: v for k, v in conditions.items() if k in order_flow_conditions}
        print(f"   {plan['plan_id'][:30]}... ({plan['symbol']} {plan['direction']}): {of_conds}")
else:
    print(f"[INFO] No pending plans with order flow conditions found")

print()

# Check monitoring
print(f"[4/4] MONITORING STATUS")
print("-" * 70)
try:
    from auto_execution_system import AutoExecutionSystem
    
    auto_exec = AutoExecutionSystem()
    monitoring_running = auto_exec.is_monitoring()
    
    print(f"   Monitoring Running: {'[YES]' if monitoring_running else '[NO]'}")
    
    if monitoring_running:
        # Get order flow plans count
        order_flow_plans_list = auto_exec._get_order_flow_plans()
        print(f"   Order Flow Plans: {len(order_flow_plans_list)} (checked every 5s)")
        
        # Get regular plans count
        all_plans = auto_exec._load_all_plans()
        regular_plans = [p for p in all_plans if p.status == 'PENDING' and p not in order_flow_plans_list]
        print(f"   Regular Plans: {len(regular_plans)} (checked every 30s)")
    else:
        print(f"   [WARN] Monitoring is not running - plans will not execute")
        
except Exception as e:
    print(f"   [WARN] Could not check monitoring: {e}")

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print()

print(f"Total Pending Plans: {len(pending_plans)}")
print(f"  Order Flow Plans: {len(order_flow_plans)}")
print(f"  Regular Plans: {len(pending_plans) - len(order_flow_plans)}")
print()

# Symbols breakdown
print("By Symbol:")
for symbol, symbol_plans in plans_by_symbol.items():
    of_count = sum(1 for p in symbol_plans if p in order_flow_plans)
    print(f"  {symbol}: {len(symbol_plans)} total ({of_count} order flow, {len(symbol_plans) - of_count} regular)")

print()
print("=" * 70)

conn.close()
