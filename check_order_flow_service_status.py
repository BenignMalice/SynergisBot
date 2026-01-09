"""
Check Order Flow Service Status and Plan Monitoring

1. Check if Order Flow Service is running
2. Check if BTCOrderFlowMetrics is initialized
3. Check if plans are being monitored
4. Check recent log activity
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("ORDER FLOW SERVICE STATUS CHECK")
print("=" * 80)
print()

# Check 1: Order Flow Service from registry
print("[1/5] CHECKING ORDER FLOW SERVICE")
print("-" * 80)

try:
    from desktop_agent import registry
    
    if hasattr(registry, 'order_flow_service') and registry.order_flow_service:
        of_service = registry.order_flow_service
        print(f"   [OK] Order Flow Service found in registry")
        
        if hasattr(of_service, 'running'):
            print(f"   Service Running: {of_service.running}")
        else:
            print(f"   [WARN] Service object has no 'running' attribute")
        
        if hasattr(of_service, 'symbols'):
            print(f"   Symbols: {of_service.symbols}")
        else:
            print(f"   [INFO] Service object has no 'symbols' attribute")
    else:
        print(f"   [WARN] Order Flow Service not found in registry")
        print(f"   [INFO] Service may be initialized in main_api.py instead")
except Exception as e:
    print(f"   [ERROR] Could not check registry: {e}")

print()

# Check 2: BTCOrderFlowMetrics initialization
print("[2/5] CHECKING BTC ORDER FLOW METRICS")
print("-" * 80)

try:
    from infra.btc_order_flow_metrics import BTCOrderFlowMetrics
    
    # Try to create instance
    try:
        from desktop_agent import registry
        of_service = getattr(registry, 'order_flow_service', None)
        
        if of_service:
            btc_metrics = BTCOrderFlowMetrics(order_flow_service=of_service)
            print(f"   [OK] BTCOrderFlowMetrics can be initialized")
            print(f"   Order Flow Service: {'Available' if of_service else 'None'}")
        else:
            btc_metrics = BTCOrderFlowMetrics()
            print(f"   [WARN] BTCOrderFlowMetrics initialized without service")
            print(f"   [INFO] Will show warnings but won't crash")
    except Exception as e:
        print(f"   [ERROR] Could not initialize BTCOrderFlowMetrics: {e}")
except Exception as e:
    print(f"   [ERROR] Could not import BTCOrderFlowMetrics: {e}")

print()

# Check 3: AutoExecutionSystem status
print("[3/5] CHECKING AUTO EXECUTION SYSTEM")
print("-" * 80)

try:
    from auto_execution_system import AutoExecutionSystem
    
    auto_exec = AutoExecutionSystem()
    
    # Check if monitoring is running
    if hasattr(auto_exec, 'is_monitoring'):
        is_monitoring = auto_exec.is_monitoring()
        print(f"   Monitoring Running: {is_monitoring}")
    else:
        print(f"   [WARN] AutoExecutionSystem has no 'is_monitoring' method")
    
    # Check if BTCOrderFlowMetrics is initialized
    if hasattr(auto_exec, 'btc_order_flow'):
        if auto_exec.btc_order_flow:
            print(f"   [OK] BTCOrderFlowMetrics is initialized in AutoExecutionSystem")
            if hasattr(auto_exec.btc_order_flow, 'order_flow_service'):
                of_service = auto_exec.btc_order_flow.order_flow_service
                if of_service:
                    print(f"   Order Flow Service: Available")
                    if hasattr(of_service, 'running'):
                        print(f"   Service Running: {of_service.running}")
                else:
                    print(f"   Order Flow Service: None (initialized without service)")
        else:
            print(f"   [WARN] BTCOrderFlowMetrics is None in AutoExecutionSystem")
    else:
        print(f"   [WARN] AutoExecutionSystem has no 'btc_order_flow' attribute")
    
    # Check plans
    if hasattr(auto_exec, 'plans'):
        with auto_exec.plans_lock:
            plan_count = len(auto_exec.plans)
            print(f"   Loaded Plans: {plan_count}")
            
            # Check for order flow plans
            order_flow_conditions = [
                "delta_positive", "delta_negative",
                "cvd_rising", "cvd_falling",
                "cvd_div_bear", "cvd_div_bull",
                "delta_divergence_bull", "delta_divergence_bear",
                "absorption_zone_detected"
            ]
            
            of_plans = []
            for plan in auto_exec.plans.values():
                if plan.status == "pending":
                    if any(plan.conditions.get(cond) for cond in order_flow_conditions):
                        of_plans.append(plan.plan_id)
            
            print(f"   Order Flow Plans: {len(of_plans)}")
            if of_plans:
                print(f"   Order Flow Plan IDs:")
                for plan_id in of_plans[:10]:  # Show first 10
                    print(f"      - {plan_id}")
    else:
        print(f"   [WARN] AutoExecutionSystem has no 'plans' attribute")
        
except Exception as e:
    print(f"   [ERROR] Could not check AutoExecutionSystem: {e}")
    import traceback
    print(f"   Traceback: {traceback.format_exc()}")

print()

# Check 4: Recent log activity
print("[4/5] CHECKING RECENT LOG ACTIVITY")
print("-" * 80)

log_file = "data/logs/chatgpt_bot.log"
if os.path.exists(log_file):
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Get last 500 lines
        recent_lines = lines[-500:] if len(lines) > 500 else lines
        
        # Search for order flow related messages
        of_activity = []
        monitoring_activity = []
        
        for line in recent_lines:
            if any(keyword in line.lower() for keyword in ['order flow', 'orderflow', 'btc order flow', 'order flow metrics']):
                of_activity.append(line.strip())
            if any(keyword in line.lower() for keyword in ['monitoring loop', 're-evaluation', 'checking plan']):
                monitoring_activity.append(line.strip())
        
        if of_activity:
            print(f"   [OK] Found {len(of_activity)} order flow related log entries:")
            for line in of_activity[-5:]:  # Last 5
                print(f"      {line[:100]}...")
        else:
            print(f"   [WARN] No order flow related log entries found")
        
        if monitoring_activity:
            print(f"\n   [OK] Found {len(monitoring_activity)} monitoring related log entries:")
            for line in monitoring_activity[-5:]:  # Last 5
                print(f"      {line[:100]}...")
        else:
            print(f"\n   [WARN] No monitoring related log entries found")
            
    except Exception as e:
        print(f"   [ERROR] Could not read log file: {e}")
else:
    print(f"   [WARN] Log file not found: {log_file}")

print()

# Check 5: Specific plan IDs
print("[5/5] CHECKING SPECIFIC PLAN IDs")
print("-" * 80)

plan_ids = [
    "chatgpt_c3f96a39",
    "chatgpt_f3ef7217",
    "chatgpt_debdbd31",
    "chatgpt_45a4cb39",
    "chatgpt_1b33fc7e"
]

try:
    from auto_execution_system import AutoExecutionSystem
    auto_exec = AutoExecutionSystem()
    
    if hasattr(auto_exec, 'plans'):
        with auto_exec.plans_lock:
            found_plans = []
            for plan_id in plan_ids:
                if plan_id in auto_exec.plans:
                    plan = auto_exec.plans[plan_id]
                    found_plans.append((plan_id, plan.status, plan.conditions))
                    print(f"   [OK] {plan_id}: Status={plan.status}")
                    
                    # Check if it has order flow conditions
                    order_flow_conditions = [
                        "delta_positive", "delta_negative",
                        "cvd_rising", "cvd_falling",
                        "cvd_div_bear", "cvd_div_bull",
                        "delta_divergence_bull", "delta_divergence_bear",
                        "absorption_zone_detected"
                    ]
                    has_of = any(plan.conditions.get(cond) for cond in order_flow_conditions)
                    print(f"      Order Flow Conditions: {'YES' if has_of else 'NO'}")
                else:
                    print(f"   [WARN] {plan_id}: NOT FOUND in loaded plans")
            
            if len(found_plans) < len(plan_ids):
                print(f"\n   [WARN] Only {len(found_plans)}/{len(plan_ids)} plans found in memory")
                print(f"   [INFO] Plans may need to be loaded from database")
except Exception as e:
    print(f"   [ERROR] Could not check plans: {e}")

print()
print("=" * 80)
print("STATUS CHECK COMPLETE")
print("=" * 80)
