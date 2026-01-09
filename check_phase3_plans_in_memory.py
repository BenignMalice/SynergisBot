"""
Check if Phase III test plans are loaded in auto-execution system memory
"""

import sys
import codecs

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

print("="*70)
print("Checking Phase III Test Plans in Auto-Execution System Memory")
print("="*70)

test_plan_ids = ["chatgpt_1d801fab", "chatgpt_be4af5f0"]

try:
    from auto_execution_system import AutoExecutionSystem
    
    auto_exec = AutoExecutionSystem()
    
    print(f"\n✅ Auto-Execution System initialized")
    # Check if monitoring is running by checking the running flag and thread
    is_running = hasattr(auto_exec, 'running') and auto_exec.running
    has_thread = hasattr(auto_exec, 'monitor_thread') and auto_exec.monitor_thread and auto_exec.monitor_thread.is_alive()
    monitoring_status = "RUNNING" if (is_running and has_thread) else "STOPPED"
    print(f"   Monitoring Status: {monitoring_status}")
    if is_running:
        print(f"   Running Flag: {auto_exec.running}")
    if has_thread:
        print(f"   Monitor Thread: {auto_exec.monitor_thread.name} (alive: {auto_exec.monitor_thread.is_alive()})")
    
    # Check if plans are loaded in memory
    with auto_exec.plans_lock:
        total_plans = len(auto_exec.plans)
        print(f"\n📊 Plans in Memory: {total_plans}")
        
        # Check for our test plans
        found_plans = []
        for plan_id in test_plan_ids:
            if plan_id in auto_exec.plans:
                plan = auto_exec.plans[plan_id]
                found_plans.append(plan_id)
                print(f"\n✅ Plan {plan_id} FOUND in memory:")
                print(f"   Status: {plan.status}")
                print(f"   Symbol: {plan.symbol}")
                print(f"   Direction: {plan.direction}")
                print(f"   Entry: {plan.entry_price}")
                print(f"   Conditions: {list(plan.conditions.keys())[:10]}...")
                
                # Check if it's identified as order flow plan
                order_flow_conditions = [
                    "delta_positive", "delta_negative",
                    "cvd_rising", "cvd_falling",
                    "cvd_div_bear", "cvd_div_bull",
                    "delta_divergence_bull", "delta_divergence_bear",
                    "absorption_zone_detected"
                ]
                has_of = any(plan.conditions.get(cond) for cond in order_flow_conditions)
                print(f"   Order Flow Plan: {'YES' if has_of else 'NO'}")
                
                # Check Phase III conditions
                phase3_conditions = [
                    "choch_bull_m5", "choch_bull_m15", "choch_bear_m5", "choch_bear_m15",
                    "consecutive_inside_bars", "volatility_fractal_expansion",
                    "bb_expansion", "min_confluence"
                ]
                has_phase3 = any(plan.conditions.get(cond) for cond in phase3_conditions)
                print(f"   Phase III Plan: {'YES' if has_phase3 else 'NO'}")
            else:
                print(f"\n❌ Plan {plan_id} NOT FOUND in memory")
        
        if len(found_plans) < len(test_plan_ids):
            print(f"\n⚠️  Only {len(found_plans)}/{len(test_plan_ids)} test plans found in memory")
            print(f"   Plans may need to be reloaded from database")
            print(f"   Next reload happens every {auto_exec.plan_reload_interval} seconds")
        
        # Check order flow plans
        order_flow_plans = auto_exec._get_order_flow_plans()
        print(f"\n📊 Order Flow Plans: {len(order_flow_plans)}")
        print(f"   Checked every: 5 seconds")
        
        # Check regular plans (non-order-flow)
        pending_plans = [p for p in auto_exec.plans.values() if p.status == "pending"]
        regular_plans = [p for p in pending_plans if p not in order_flow_plans]
        print(f"📊 Regular Plans (including Phase III): {len(regular_plans)}")
        print(f"   Checked every: {auto_exec.check_interval} seconds")
        
        # Show if our test plans are in regular plans
        test_regular_plans = [p for p in regular_plans if p.plan_id in test_plan_ids]
        if test_regular_plans:
            print(f"   ✅ Test Phase III plans are in regular plans list")
            print(f"   They will be checked every {auto_exec.check_interval} seconds")
        else:
            print(f"   ⚠️  Test Phase III plans NOT in regular plans list")
            print(f"   This may indicate they're not being checked")
    
except Exception as e:
    print(f"\n❌ Error checking plans: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("Check Complete")
print("="*70)

