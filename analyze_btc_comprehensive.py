"""Comprehensive BTCUSDc analysis with current price and plan viability"""
import sqlite3
import json
import httpx
from datetime import datetime, timezone
from collections import defaultdict

# Get current BTC price
print("=" * 80)
print("BTCUSDc MARKET ANALYSIS & AUTO-EXECUTION PLAN REVIEW")
print("=" * 80)
print()

current_price = None
price_data = None

try:
    with httpx.Client(timeout=5.0) as client:
        response = client.get("http://localhost:8000/api/v1/price/BTCUSDc")
        if response.status_code == 200:
            price_data = response.json()
            current_price = price_data.get('mid') or price_data.get('bid')
            print(f"Current BTC Price: ${current_price:,.2f}")
            print(f"Bid: ${price_data.get('bid', 0):,.2f} | Ask: ${price_data.get('ask', 0):,.2f} | Spread: ${price_data.get('spread', 0):.2f}")
        else:
            print("[WARNING] Could not fetch current price from API")
except Exception as e:
    print(f"[WARNING] Could not fetch current price: {e}")

print()

# Database analysis
db_path = "data/auto_execution.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get ALL BTC plans
cursor.execute("""
    SELECT plan_id, symbol, direction, conditions, status, created_at, expires_at,
           entry_levels, cancellation_reason, last_re_evaluation
    FROM trade_plans
    WHERE symbol LIKE '%BTC%'
    ORDER BY created_at DESC
""")

all_plans = cursor.fetchall()

print("=" * 80)
print("DATABASE SUMMARY")
print("=" * 80)
print(f"\nTotal BTC Plans: {len(all_plans)}\n")

# Group by status
by_status = defaultdict(list)
for plan in all_plans:
    status = plan['status']
    by_status[status].append(plan)

print("Plans by Status:")
for status, plans in sorted(by_status.items()):
    print(f"  {status.upper()}: {len(plans)}")

# Analyze pending plans
pending_plans = [p for p in all_plans if p['status'] == 'pending']
print(f"\n{'=' * 80}")
print(f"PENDING PLANS ANALYSIS ({len(pending_plans)} plans)")
print(f"{'=' * 80}\n")

order_flow_keys = ['delta_positive', 'cvd_rising', 'cvd_div_bear', 'cvd_div_bull',
                  'delta_divergence_bull', 'delta_divergence_bear', 'absorption_zone_detected']
structure_keys = ['liquidity_sweep', 'choch_bull', 'choch_bear', 'bos_bull', 'bos_bear',
                 'order_block', 'inside_bar', 'fair_value_gap']

# Group by direction
buy_plans = [p for p in pending_plans if p['direction'] == 'BUY']
sell_plans = [p for p in pending_plans if p['direction'] == 'SELL']

print(f"BUY Plans: {len(buy_plans)}")
print(f"SELL Plans: {len(sell_plans)}\n")

# Analyze price proximity
if current_price:
    print(f"{'=' * 80}")
    print("PRICE PROXIMITY ANALYSIS")
    print(f"{'=' * 80}\n")
    
    price_near_plans = []
    price_far_plans = []
    
    for plan in pending_plans:
        try:
            conditions = json.loads(plan['conditions']) if plan['conditions'] else {}
            price_near = conditions.get('price_near')
            tolerance = conditions.get('tolerance', 100)
            
            if price_near:
                distance = abs(current_price - price_near)
                pct_distance = (distance / current_price) * 100
                
                if distance <= tolerance:
                    price_near_plans.append((plan, distance, pct_distance, 'IN RANGE'))
                else:
                    price_far_plans.append((plan, distance, pct_distance, 'OUT OF RANGE'))
        except:
            pass
    
    print(f"Plans IN PRICE RANGE: {len(price_near_plans)}")
    print(f"Plans OUT OF PRICE RANGE: {len(price_far_plans)}\n")
    
    if price_near_plans:
        print("Plans Near Entry Price:")
        for plan, dist, pct, status in sorted(price_near_plans, key=lambda x: x[1])[:10]:
            print(f"  {plan['plan_id'][:20]:20} | {plan['direction']:4} | Distance: ${dist:.2f} ({pct:.2f}%) | {status}")
    
    print()

# Detailed plan breakdown
print(f"{'=' * 80}")
print("PLAN TYPE BREAKDOWN")
print(f"{'=' * 80}\n")

plan_types = defaultdict(int)
for plan in pending_plans:
    try:
        conditions = json.loads(plan['conditions']) if plan['conditions'] else {}
        plan_type = conditions.get('plan_type', 'chatgpt')
        plan_types[plan_type] += 1
    except:
        plan_types['unknown'] += 1

for ptype, count in sorted(plan_types.items(), key=lambda x: x[1], reverse=True):
    print(f"  {ptype}: {count}")

print()

# Structure conditions breakdown
print(f"{'=' * 80}")
print("CONDITION TYPE BREAKDOWN")
print(f"{'=' * 80}\n")

condition_counts = defaultdict(int)
for plan in pending_plans:
    try:
        conditions = json.loads(plan['conditions']) if plan['conditions'] else {}
        for key in structure_keys:
            if key in conditions and conditions[key]:
                condition_counts[key] += 1
    except:
        pass

for cond, count in sorted(condition_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  {cond}: {count}")

print()

# Recent plans
print(f"{'=' * 80}")
print("RECENT PLANS (Last 10 by creation date)")
print(f"{'=' * 80}\n")

recent_plans = sorted(pending_plans, key=lambda x: x['created_at'] or '', reverse=True)[:10]

for i, plan in enumerate(recent_plans, 1):
    status_icon = "[PENDING]"
    print(f"{status_icon} {plan['plan_id'][:25]:25} | {plan['direction']:4} | Created: {plan['created_at']}")

conn.close()

print()
print("=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)

