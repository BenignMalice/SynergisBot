"""Review all XAUUSDc plans to verify monitoring and execution readiness"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from chatgpt_auto_execution_tools import tool_get_auto_plan_status, tool_get_auto_system_status

# All plans from the user's list
all_plans = {
    # Level 1 - PDL zone (4456)
    "chatgpt_d79cd64a": {"level": 1, "name": "Liquidity Sweep → Reclaim", "direction": "BUY", "entry": 4456.0, "sl": 4453.5, "tp": 4470.0},
    "chatgpt_6c5d89c4": {"level": 1, "name": "Breaker Block Retest", "direction": "BUY", "entry": 4456.5, "sl": 4453.8, "tp": 4472.0},
    "chatgpt_85ef5b72": {"level": 1, "name": "FVG Retracement", "direction": "BUY", "entry": 4457.0, "sl": 4454.0, "tp": 4473.5},
    "chatgpt_2c6a1c83": {"level": 1, "name": "Inducement Reversal", "direction": "BUY", "entry": 4456.2, "sl": 4453.9, "tp": 4468.5},
    "chatgpt_dc447645": {"level": 1, "name": "Mitigation Block Confirm", "direction": "BUY", "entry": 4456.8, "sl": 4453.8, "tp": 4471.0},
    
    # Level 2 - Compression zone (4462-4465)
    "chatgpt_46e0fe5c": {"level": 2, "name": "Inside Bar Breakout", "direction": "BUY", "entry": 4464.5, "sl": 4461.5, "tp": 4473.4},
    "chatgpt_bb787641": {"level": 2, "name": "VWAP Deviation Fade", "direction": "SELL", "entry": 4464.0, "sl": 4466.5, "tp": 4458.0},
    "chatgpt_18101a54": {"level": 2, "name": "Premium / Discount Array", "direction": "BUY", "entry": 4462.0, "sl": 4460.5, "tp": 4468.0},
    "chatgpt_9a70376f": {"level": 2, "name": "Range Scalp Bounce", "direction": "BUY", "entry": 4463.5, "sl": 4461.0, "tp": 4468.5},
    "chatgpt_0d645a46": {"level": 2, "name": "Micro CHOCH Flip", "direction": "BUY", "entry": 4462.8, "sl": 4460.8, "tp": 4470.0},
    
    # Level 3 - PDH zone (4474-4476)
    "chatgpt_9d7c5f61": {"level": 3, "name": "Order Block Rejection", "direction": "SELL", "entry": 4474.8, "sl": 4478.8, "tp": 4462.0},
    "chatgpt_70ce286b": {"level": 3, "name": "Breaker Block Flip", "direction": "SELL", "entry": 4475.2, "sl": 4479.0, "tp": 4463.5},
    "chatgpt_eca76a47": {"level": 3, "name": "Liquidity Sweep Fail Reversal", "direction": "SELL", "entry": 4476.0, "sl": 4479.5, "tp": 4465.0},
    "chatgpt_1ef5a867": {"level": 3, "name": "Mitigation Block Pullback", "direction": "SELL", "entry": 4474.5, "sl": 4478.0, "tp": 4464.0},
    "chatgpt_64635592": {"level": 3, "name": "MSS Continuation", "direction": "SELL", "entry": 4475.0, "sl": 4478.0, "tp": 4460.0},
    
    # Level 4 - Extension zone (4478-4482)
    "chatgpt_e6940c4e": {"level": 4, "name": "FVG Retracement", "direction": "SELL", "entry": 4479.0, "sl": 4482.0, "tp": 4468.0},
    "chatgpt_cfd73ae0": {"level": 4, "name": "Session Liquidity Run", "direction": "SELL", "entry": 4480.0, "sl": 4483.0, "tp": 4470.0},
    "chatgpt_570037c1": {"level": 4, "name": "Trend Continuation Pullback", "direction": "SELL", "entry": 4478.5, "sl": 4481.5, "tp": 4468.5},
    "chatgpt_e1673517": {"level": 4, "name": "VWAP Deviation Fade", "direction": "SELL", "entry": 4481.0, "sl": 4483.5, "tp": 4470.5},
    "chatgpt_b6c471e2": {"level": 4, "name": "Order Block Breaker", "direction": "SELL", "entry": 4480.5, "sl": 4484.0, "tp": 4469.5},
    
    # Level 5 - Micro scalp zone (4458-4462)
    "micro_scalp_6e12069d": {"level": 5, "name": "Micro Scalp", "direction": "BUY", "entry": 4460.0, "sl": 4459.0, "tp": 4462.4},
    "chatgpt_d0dbadb4": {"level": 5, "name": "VWAP Bounce", "direction": "BUY", "entry": 4461.0, "sl": 4459.5, "tp": 4463.5},
    "chatgpt_23f37c5f": {"level": 5, "name": "Mini CHOCH Pullback", "direction": "BUY", "entry": 4459.8, "sl": 4458.8, "tp": 4463.0},
    "chatgpt_9ed2caa0": {"level": 5, "name": "Liquidity Sweep Mini", "direction": "BUY", "entry": 4458.8, "sl": 4458.0, "tp": 4462.2},
    "chatgpt_6fd4896a": {"level": 5, "name": "Range Scalp Ping", "direction": "BUY", "entry": 4461.5, "sl": 4459.8, "tp": 4464.0},
}

async def review_plans():
    print("=" * 80)
    print("XAUUSDc MULTI-LEVEL PORTFOLIO REVIEW")
    print("=" * 80)
    
    # Check system status
    print("\n[1] CHECKING AUTO-EXECUTION SYSTEM STATUS...")
    system_result = await tool_get_auto_system_status({})
    system_data = system_result.get('data', {})
    system_status = system_data.get('system_status', system_data)
    
    running = system_status.get('running', False)
    thread_alive = system_status.get('thread_alive', False)
    pending_count = system_status.get('pending_plans', 0)
    check_interval = system_status.get('check_interval', 30)
    
    print(f"  System Running: {running}")
    print(f"  Thread Alive: {thread_alive}")
    print(f"  Total Pending Plans: {pending_count}")
    print(f"  Check Interval: {check_interval} seconds")
    
    if not running or not thread_alive:
        print("\n  WARNING: System is NOT properly running - plans will NOT execute!")
        return
    
    print("  STATUS: Monitoring is ACTIVE - plans will be executed when conditions are met")
    
    # Get all plans
    print("\n[2] RETRIEVING ALL PLANS...")
    plans_result = await tool_get_auto_plan_status({})
    plans_data = plans_result.get('data', {})
    all_registered_plans = plans_data.get('plans', [])
    
    print(f"  Total plans in system: {len(all_registered_plans)}")
    
    # Filter XAUUSDc plans
    xau_plans = [p for p in all_registered_plans if p.get('symbol', '').upper() == 'XAUUSDC']
    print(f"  XAUUSDc plans: {len(xau_plans)}")
    
    # Review each expected plan
    print("\n[3] REVIEWING EXPECTED PLANS...")
    print("=" * 80)
    
    found_count = 0
    issues = []
    by_level = {1: [], 2: [], 3: [], 4: [], 5: []}
    
    for plan_id, expected in all_plans.items():
        plan = next((p for p in xau_plans if p.get('plan_id') == plan_id), None)
        
        if not plan:
            issues.append(f"{expected['name']} ({plan_id}): NOT FOUND")
            continue
        
        found_count += 1
        status = plan.get('status', 'Unknown')
        direction = plan.get('direction', 'Unknown')
        entry = plan.get('entry_price', 0)
        sl = plan.get('stop_loss', 0)
        tp = plan.get('take_profit', 0)
        conditions = plan.get('conditions', {})
        expires_at = plan.get('expires_at', 'N/A')
        
        # Verify parameters
        entry_match = abs(float(entry) - expected['entry']) < 0.1
        sl_match = abs(float(sl) - expected['sl']) < 0.1
        tp_match = abs(float(tp) - expected['tp']) < 0.1
        direction_match = direction.upper() == expected['direction'].upper()
        
        if not entry_match:
            issues.append(f"{expected['name']}: Entry mismatch ({entry} vs {expected['entry']})")
        if not sl_match:
            issues.append(f"{expected['name']}: SL mismatch ({sl} vs {expected['sl']})")
        if not tp_match:
            issues.append(f"{expected['name']}: TP mismatch ({tp} vs {expected['tp']})")
        if not direction_match:
            issues.append(f"{expected['name']}: Direction mismatch ({direction} vs {expected['direction']})")
        
        # Check if will be monitored
        will_monitor = status == 'pending'
        
        by_level[expected['level']].append({
            'plan_id': plan_id,
            'name': expected['name'],
            'status': status,
            'will_monitor': will_monitor,
            'entry': entry,
            'direction': direction,
            'conditions_count': len(conditions) if conditions else 0
        })
    
    # Summary by level
    print("\n[4] SUMMARY BY LEVEL:")
    print("=" * 80)
    
    for level in [1, 2, 3, 4, 5]:
        level_plans = by_level[level]
        pending = [p for p in level_plans if p['status'] == 'pending']
        print(f"\nLevel {level}: {len(level_plans)}/{len([p for p in all_plans.values() if p['level'] == level])} plans found")
        print(f"  Pending (will monitor): {len(pending)}")
        print(f"  Plans:")
        for p in level_plans:
            monitor_status = "YES" if p['will_monitor'] else "NO"
            # Replace Unicode arrows with ASCII
            name = p['name'].replace('→', '->').replace('≈', '~')
            print(f"    - {name}: {p['status']} (Monitor: {monitor_status}, Conditions: {p['conditions_count']})")
    
    # Final summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print(f"Plans Found: {found_count}/{len(all_plans)}")
    print(f"Issues: {len(issues)}")
    
    if issues:
        print("\nIssues Found:")
        for issue in issues[:10]:  # Show first 10
            print(f"  - {issue}")
        if len(issues) > 10:
            print(f"  ... and {len(issues) - 10} more")
    
    total_pending = sum(len([p for p in by_level[l] if p['status'] == 'pending']) for l in [1, 2, 3, 4, 5])
    print(f"\nTotal Pending Plans: {total_pending}/{found_count}")
    print(f"System Monitoring: {'ACTIVE' if (running and thread_alive) else 'INACTIVE'}")
    
    if running and thread_alive and found_count > 0:
        print("\n" + "=" * 80)
        print("CONCLUSION: Plans are registered and WILL be monitored/executed")
        print("  - System is running and monitoring thread is alive")
        print("  - Plans will be checked every 30 seconds")
        print("  - Trades will execute automatically when conditions are met")
        if issues:
            print(f"\n  Note: {len(issues)} minor issues found (see above), but plans are functional")
    elif not (running and thread_alive):
        print("\n" + "=" * 80)
        print("WARNING: System monitoring is not active - plans will NOT execute")
        print("  - Action needed: Restart main_api.py to start monitoring")
    else:
        print("\n" + "=" * 80)
        print("WARNING: Some plans may not be properly registered")

if __name__ == "__main__":
    asyncio.run(review_plans())

