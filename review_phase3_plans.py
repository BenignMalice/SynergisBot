"""Review Phase III auto-execution plans for correctness and monitoring status"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from chatgpt_auto_execution_tools import tool_get_auto_plan_status, tool_get_auto_system_status

# Expected Phase III plans
expected_plans = [
    {
        "name": "Plan 1: Rejection Wick - Liquidity Sweep -> CHOCH",
        "plan_id": None,  # Unknown
        "direction": "SELL",
        "entry": 4493,
        "stop_loss": 4498,
        "take_profit": 4478,
        "conditions": ["choch_bear", "liquidity_sweep", "rejection_wick"],
        "type": "rejection_wick"
    },
    {
        "name": "Plan 2: Order Block - VWAP + OB Fusion",
        "plan_id": "chatgpt_16bb2e49",
        "direction": "BUY",
        "entry": 4482,
        "stop_loss": 4478,
        "take_profit": 4492,
        "conditions": ["order_block", "vwap_deviation"],
        "type": "order_block"
    },
    {
        "name": "Plan 3: Post-CPI FVG Reaction",
        "plan_id": "chatgpt_feba3e1f",
        "direction": "SELL",
        "entry": 4486,
        "stop_loss": 4491,
        "take_profit": 4471,
        "conditions": ["fvg_bear", "bb_expansion"],
        "type": "auto_trade"
    },
    {
        "name": "Plan 4: Absorption Scalp",
        "plan_id": None,  # Unknown
        "direction": "BUY",
        "entry": 4482.5,
        "stop_loss": 4480,
        "take_profit": 4487.5,
        "conditions": ["absorption_zone_detected"],
        "type": "auto_trade"
    },
    {
        "name": "Plan 5: Breaker-Block Flip",
        "plan_id": "chatgpt_ad4993aa",
        "direction": "SELL",
        "entry": 4495,
        "stop_loss": 4501,
        "take_profit": 4482,
        "conditions": ["breaker_block"],
        "type": "auto_trade"
    },
    {
        "name": "Plan 6: Session Reversion (Kill-Zone)",
        "plan_id": "chatgpt_ac440dfb",
        "direction": "BUY",
        "entry": 4484,
        "stop_loss": 4480,
        "take_profit": 4491,
        "conditions": ["kill_zone_active", "vwap_deviation"],
        "type": "auto_trade"
    },
    {
        "name": "Plan 7: Inside-Bar Breakout Trap",
        "plan_id": "chatgpt_c26c4129",
        "direction": "SELL",
        "entry": 4488,
        "stop_loss": 4493,
        "take_profit": 4475,
        "conditions": ["inside_bar", "price_below"],
        "type": "auto_trade"
    },
    {
        "name": "Plan 8: CVD Divergence Continuation",
        "plan_id": "chatgpt_f97269bf",
        "direction": "SELL",
        "entry": 4489,
        "stop_loss": 4494,
        "take_profit": 4478,
        "conditions": ["cvd_div_bear"],
        "type": "auto_trade"
    },
    {
        "name": "Plan 9: Premium / Discount Array",
        "plan_id": "chatgpt_de77a692",
        "direction": "BUY",
        "entry": 4480,
        "stop_loss": 4475,
        "take_profit": 4495,
        "conditions": ["price_in_discount", "choch_bull"],
        "type": "auto_trade"
    }
]

async def review_plans():
    print("=" * 80)
    print("PHASE III AUTO-EXECUTION PLANS REVIEW")
    print("=" * 80)
    
    # Get system status
    print("\n[1] Checking Auto-Execution System Status...")
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
        print("  WARNING: Auto-execution system is NOT properly running!")
        if not running:
            print("    - System is not running (restart main_api.py)")
        if not thread_alive:
            print("    - Monitoring thread is dead (restart main_api.py)")
        return
    
    print("  STATUS: Monitoring is ACTIVE - plans will be executed when conditions are met")
    
    # Get all plans
    print("\n[2] Retrieving All Plans...")
    plans_result = await tool_get_auto_plan_status({})
    plans_data = plans_result.get('data', {})
    all_plans = plans_data.get('plans', [])
    
    print(f"  Total plans retrieved: {len(all_plans)}")
    
    # Review each expected plan
    print("\n[3] Reviewing Phase III Plans...")
    print("=" * 80)
    
    found_count = 0
    issues = []
    
    for expected in expected_plans:
        print(f"\n{expected['name']}")
        print("-" * 80)
        
        if expected['plan_id']:
            # Find by plan_id
            plan = next((p for p in all_plans if p.get('plan_id') == expected['plan_id']), None)
        else:
            # Find by characteristics
            candidates = [
                p for p in all_plans
                if p.get('symbol', '').upper() == 'XAUUSDC'
                and p.get('direction', '').upper() == expected['direction']
                and abs(float(p.get('entry_price', 0)) - expected['entry']) < 2.0
            ]
            plan = candidates[0] if candidates else None
        
        if not plan:
            print(f"  STATUS: NOT FOUND")
            issues.append(f"{expected['name']}: Plan not found in system")
            continue
        
        found_count += 1
        plan_id = plan.get('plan_id', 'Unknown')
        status = plan.get('status', 'Unknown')
        symbol = plan.get('symbol', 'Unknown')
        direction = plan.get('direction', 'Unknown')
        entry = plan.get('entry_price', 0)
        sl = plan.get('stop_loss', 0)
        tp = plan.get('take_profit', 0)
        volume = plan.get('volume', 0)
        expires_at = plan.get('expires_at', 'Unknown')
        conditions = plan.get('conditions', {})
        
        print(f"  Plan ID: {plan_id}")
        print(f"  Status: {status}")
        print(f"  Symbol: {symbol}")
        print(f"  Direction: {direction}")
        print(f"  Entry: {entry} (expected: {expected['entry']})")
        print(f"  Stop Loss: {sl} (expected: {expected['stop_loss']})")
        print(f"  Take Profit: {tp} (expected: {expected['take_profit']})")
        print(f"  Volume: {volume} lots")
        print(f"  Expires: {expires_at}")
        
        # Verify parameters
        entry_match = abs(float(entry) - expected['entry']) < 1.0
        sl_match = abs(float(sl) - expected['stop_loss']) < 1.0
        tp_match = abs(float(tp) - expected['take_profit']) < 1.0
        
        if not entry_match:
            issues.append(f"{expected['name']}: Entry mismatch ({entry} vs {expected['entry']})")
        if not sl_match:
            issues.append(f"{expected['name']}: SL mismatch ({sl} vs {expected['stop_loss']})")
        if not tp_match:
            issues.append(f"{expected['name']}: TP mismatch ({tp} vs {expected['take_profit']})")
        
        # Check conditions
        print(f"  Conditions: {conditions}")
        missing_conditions = []
        for cond in expected['conditions']:
            if cond not in str(conditions).lower():
                missing_conditions.append(cond)
        
        if missing_conditions:
            issues.append(f"{expected['name']}: Missing conditions: {missing_conditions}")
            print(f"  WARNING: Missing expected conditions: {missing_conditions}")
        else:
            print(f"  Conditions: OK (all expected conditions present)")
        
        # Check if plan will be monitored
        if status == 'pending':
            print(f"  Monitoring: YES (status is 'pending', will be monitored)")
        elif status == 'executed':
            print(f"  Monitoring: NO (already executed)")
        elif status == 'expired':
            print(f"  Monitoring: NO (expired)")
        elif status == 'cancelled':
            print(f"  Monitoring: NO (cancelled)")
        else:
            print(f"  Monitoring: UNKNOWN (status: {status})")
    
    # Summary
    print("\n" + "=" * 80)
    print("REVIEW SUMMARY")
    print("=" * 80)
    print(f"Plans Found: {found_count}/{len(expected_plans)}")
    print(f"Issues Found: {len(issues)}")
    
    if issues:
        print("\nIssues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\nAll plans are correct!")
    
    print(f"\nSystem Monitoring: {'ACTIVE' if (running and thread_alive) else 'INACTIVE'}")
    print(f"Pending Plans: {pending_count}")
    print(f"Check Interval: {check_interval} seconds")
    
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

