"""
Review Auto Execution Plans

Checks all auto-execution plans in the system:
1. Gets all plans from database
2. Shows plan details (symbol, direction, conditions, status)
3. Checks if plans are being monitored
4. Shows recent activity/checks
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import codecs
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

import sqlite3
from datetime import datetime
import json

print("=" * 70)
print("AUTO EXECUTION PLANS REVIEW")
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

# Get all plans - check what columns exist first
cursor.execute("PRAGMA table_info(trade_plans)")
columns_info = cursor.fetchall()
column_names = [col[1] for col in columns_info]

# Build SELECT query with available columns
available_cols = ['plan_id', 'symbol', 'direction', 'stop_loss', 'take_profit',
                 'volume', 'status', 'conditions', 'created_at', 'expires_at']
select_cols = [col for col in available_cols if col in column_names]

# Add optional columns if they exist
optional_cols = ['entry_levels', 'last_check', 'cancellation_reason', 'last_re_evaluation']
for col in optional_cols:
    if col in column_names:
        select_cols.append(col)

select_query = f"""
    SELECT {', '.join(select_cols)}
    FROM trade_plans
    ORDER BY created_at DESC
"""
cursor.execute(select_query)

plans = cursor.fetchall()

if not plans:
    print("[INFO] No auto-execution plans found in database")
    sys.exit(0)

print(f"[1/4] ALL PLANS IN DATABASE")
print("-" * 70)
print(f"[OK] Found {len(plans)} plan(s) in database")
print()

# Group plans by status
plans_by_status = {}
for plan in plans:
    status = plan['status']
    if status not in plans_by_status:
        plans_by_status[status] = []
    plans_by_status[status].append(plan)

print(f"Plans by status:")
for status, status_plans in plans_by_status.items():
    print(f"  {status}: {len(status_plans)} plan(s)")
print()

# Show all plans
for idx, plan in enumerate(plans, 1):
    print(f"[{idx}/{len(plans)}] Plan: {plan['plan_id']}")
    print(f"   Symbol: {plan['symbol']}")
    print(f"   Direction: {plan['direction']}")
    
    # Helper function to safely get row value
    def get_row_value(row, key, default=None):
        try:
            return row[key] if key in row.keys() else default
        except:
            return default
    
    # Parse entry levels or entry_price
    entry_levels_val = get_row_value(plan, 'entry_levels')
    entry_price_val = get_row_value(plan, 'entry_price')
    
    if entry_levels_val:
        try:
            entry_levels = json.loads(entry_levels_val)
            if isinstance(entry_levels, dict):
                entry_str = f"{entry_levels.get('primary', 'N/A')}"
                if entry_levels.get('secondary'):
                    entry_str += f" / {entry_levels.get('secondary')}"
            else:
                entry_str = str(entry_levels)
        except:
            entry_str = str(entry_levels_val)
    elif entry_price_val:
        entry_str = f"{entry_price_val:.2f}"
    else:
        entry_str = "N/A"
    
    print(f"   Entry: {entry_str}")
    print(f"   Stop Loss: {plan['stop_loss'] if plan['stop_loss'] else 'None'}")
    print(f"   Take Profit: {plan['take_profit'] if plan['take_profit'] else 'None'}")
    print(f"   Volume: {plan['volume']}")
    print(f"   Status: {plan['status']}")
    
    # Parse conditions
    conditions = None
    if plan['conditions']:
        try:
            conditions = json.loads(plan['conditions'])
        except:
            conditions = plan['conditions']
    
    if conditions:
        print(f"   Conditions:")
        if isinstance(conditions, dict):
            for key, value in conditions.items():
                print(f"      {key}: {value}")
        else:
            print(f"      {conditions}")
    
    print(f"   Created: {plan['created_at']}")
    expires_val = get_row_value(plan, 'expires_at')
    print(f"   Expires: {expires_val if expires_val else 'Never'}")
    
    last_check_val = get_row_value(plan, 'last_check')
    if last_check_val:
        print(f"   Last Check: {last_check_val}")
    
    last_re_eval_val = get_row_value(plan, 'last_re_evaluation')
    if last_re_eval_val:
        print(f"   Last Re-evaluation: {last_re_eval_val}")
    
    cancellation_reason = get_row_value(plan, 'cancellation_reason')
    if cancellation_reason:
        print(f"   Cancellation Reason: {cancellation_reason}")
    
    print()

# Check monitoring status
print(f"[2/4] MONITORING STATUS")
print("-" * 70)
try:
    from auto_execution_system import AutoExecutionSystem
    
    auto_exec = AutoExecutionSystem()
    
    # Check if monitoring is running
    monitoring_running = auto_exec.is_monitoring()
    print(f"   Monitoring Running: {'[YES]' if monitoring_running else '[NO]'}")
    
    # Get pending plans
    pending_plans = [p for p in plans if p['status'] == 'PENDING']
    print(f"   Pending Plans: {len(pending_plans)}")
    
    # Get active plans (executed but not closed)
    active_plans = [p for p in plans if p['status'] == 'ACTIVE']
    print(f"   Active Plans: {len(active_plans)}")
    
    # Get executed plans
    executed_plans = [p for p in plans if p['status'] == 'EXECUTED']
    print(f"   Executed Plans: {len(executed_plans)}")
    
    # Get cancelled plans
    cancelled_plans = [p for p in plans if p['status'] == 'CANCELLED']
    print(f"   Cancelled Plans: {len(cancelled_plans)}")
    
except Exception as e:
    print(f"   [WARN] Could not check monitoring status: {e}")
    print()

# Check recent activity
print(f"[3/4] RECENT PLAN ACTIVITY")
print("-" * 70)
try:
    import re
    
    log_file = "data/logs/chatgpt_bot.log"
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Get last 1000 lines
        recent_lines = lines[-1000:] if len(lines) > 1000 else lines
        
        # Search for plan activity
        plan_ids = [p['plan_id'] for p in plans]
        activity = []
        
        for line in recent_lines:
            for plan_id in plan_ids:
                if plan_id in line and ('checking' in line.lower() or 'executed' in line.lower() or 'triggered' in line.lower() or 'condition' in line.lower()):
                    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if timestamp_match:
                        activity.append((timestamp_match.group(1), plan_id, line.strip()))
        
        if activity:
            print(f"   [OK] Found {len(activity)} recent activity log(s):")
            # Group by plan
            activity_by_plan = {}
            for timestamp, plan_id, log_line in activity[-30:]:  # Last 30
                if plan_id not in activity_by_plan:
                    activity_by_plan[plan_id] = []
                activity_by_plan[plan_id].append((timestamp, log_line))
            
            for plan_id, plan_activity in list(activity_by_plan.items())[:10]:  # Top 10 plans
                print(f"      Plan {plan_id}: {len(plan_activity)} activity log(s)")
                for timestamp, log_line in plan_activity[-3:]:  # Last 3 per plan
                    print(f"         {timestamp}: {log_line[:80]}...")
        else:
            print(f"   [INFO] No recent plan activity found in logs")
    else:
        print(f"   [WARN] Log file not found: {log_file}")
except Exception as e:
    print(f"   [WARN] Could not check recent activity: {e}")

print()

# Check order flow plans
print(f"[4/4] ORDER FLOW PLANS")
print("-" * 70)
order_flow_plans = []
for plan in plans:
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
        
        if has_order_flow:
            order_flow_plans.append(plan)

if order_flow_plans:
    print(f"   [OK] Found {len(order_flow_plans)} plan(s) with order flow conditions:")
    for plan in order_flow_plans:
        conditions = json.loads(plan['conditions']) if plan['conditions'] else {}
        order_flow_conds = {k: v for k, v in conditions.items() if k in ['delta_positive', 'cvd_rising', 'cvd_div_bear', 'cvd_div_bull',
                          'delta_divergence_bull', 'delta_divergence_bear', 'absorption_zone_detected']}
        print(f"      {plan['plan_id']} ({plan['symbol']} {plan['direction']}): {order_flow_conds}")
else:
    print(f"   [INFO] No plans with order flow conditions found")

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print()

print(f"Total Plans: {len(plans)}")
print(f"  Pending: {len(plans_by_status.get('PENDING', []))}")
print(f"  Active: {len(plans_by_status.get('ACTIVE', []))}")
print(f"  Executed: {len(plans_by_status.get('EXECUTED', []))}")
print(f"  Cancelled: {len(plans_by_status.get('CANCELLED', []))}")
print(f"  Expired: {len(plans_by_status.get('EXPIRED', []))}")
print(f"  Order Flow Plans: {len(order_flow_plans)}")

print()
print("=" * 70)

conn.close()
