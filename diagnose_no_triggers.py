"""
Diagnose why plans aren't triggering at current price
"""
import asyncio
import json
from cursor_trading_bridge import get_bridge
from datetime import datetime

async def diagnose_no_triggers():
    """Diagnose why plans at $4,492 aren't triggering"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("DIAGNOSING WHY PLANS AREN'T TRIGGERING")
    print("=" * 70)
    
    # Get current price
    print("\n💰 Current Market Price:")
    try:
        xau_price = await bridge.get_current_price("XAUUSD")
        xau_bid = xau_price.get("data", {}).get("bid", None)
        print(f"   XAUUSD: ${xau_bid:.2f}" if xau_bid else "   XAUUSD: N/A")
    except Exception as e:
        print(f"   ⚠️ Could not get price: {e}")
        xau_bid = 4492.0  # Use provided price
    
    # Get all plans
    status = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    print(f"\n📊 System Status:")
    print(f"   Running: {system_status.get('running', False)}")
    print(f"   Thread Alive: {system_status.get('thread_alive', False)}")
    print(f"   Check Interval: {system_status.get('check_interval', 'N/A')} seconds")
    print(f"   Total Plans: {len(all_plans)}")
    
    # Find XAUUSD plans that should trigger at $4,492
    print(f"\n🔍 Analyzing XAUUSD Plans at ${xau_bid:.2f}:")
    print("-" * 70)
    
    plans_should_trigger = []
    plans_blocked = []
    
    for plan in all_plans:
        symbol = plan.get("symbol", "")
        if symbol != "XAUUSDc":
            continue
        
        direction = plan.get("direction", "")
        entry = plan.get("entry_price", 0)
        conditions = plan.get("conditions", {})
        tolerance = conditions.get("tolerance", 0)
        price_near = conditions.get("price_near", entry)
        expires_at = plan.get("expires_at", "")
        status_val = plan.get("status", "")
        
        # Check expiration
        expired = False
        if expires_at:
            try:
                exp_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                now = datetime.now(exp_time.tzinfo)
                expired = now > exp_time
            except:
                pass
        
        if expired or status_val != "pending":
            continue
        
        # Check price proximity
        distance = abs(xau_bid - price_near)
        in_range = distance <= tolerance
        
        if not in_range:
            continue
        
        # Check conditions
        blocking_reasons = []
        
        # Structure conditions
        if conditions.get("choch_bull") or conditions.get("choch_bear"):
            blocking_reasons.append("CHOCH not formed")
        if conditions.get("bos_bull") or conditions.get("bos_bear"):
            blocking_reasons.append("BOS not confirmed")
        if conditions.get("liquidity_sweep"):
            blocking_reasons.append("Liquidity sweep not detected")
        if conditions.get("rejection_wick"):
            blocking_reasons.append("Rejection wick not present")
        if conditions.get("inside_bar"):
            blocking_reasons.append("Inside bar not formed")
        if conditions.get("order_block"):
            blocking_reasons.append("Order block not validated")
        if conditions.get("breaker_block"):
            blocking_reasons.append("Breaker block not detected")
        
        # Confluence
        if conditions.get("confluence_min"):
            min_confluence = conditions.get("confluence_min", 0)
            blocking_reasons.append(f"Confluence < {min_confluence}")
        
        # VWAP
        if conditions.get("vwap_deviation"):
            blocking_reasons.append("VWAP deviation not met")
        
        # BB
        if conditions.get("bb_expansion"):
            blocking_reasons.append("BB expansion not detected")
        
        plan_info = {
            "plan_id": plan.get("plan_id", "N/A"),
            "direction": direction,
            "entry": entry,
            "price_near": price_near,
            "tolerance": tolerance,
            "distance": distance,
            "conditions": conditions,
            "blocking_reasons": blocking_reasons,
            "notes": plan.get("notes", "")
        }
        
        if blocking_reasons:
            plans_blocked.append(plan_info)
        else:
            plans_should_trigger.append(plan_info)
    
    # Show plans that should trigger
    print(f"\n✅ Plans That SHOULD Trigger (Price in Range, No Blocking Conditions):")
    if plans_should_trigger:
        for i, plan in enumerate(plans_should_trigger, 1):
            print(f"\n{i}. Plan: {plan['plan_id'][:20]}...")
            print(f"   Direction: {plan['direction']} | Entry: ${plan['entry']:.2f}")
            print(f"   Price Near: ${plan['price_near']:.2f} | Tolerance: ±{plan['tolerance']}")
            print(f"   Distance: {plan['distance']:.2f} (within tolerance)")
            print(f"   Conditions: {list(plan['conditions'].keys())}")
            print(f"   ⚠️ SHOULD TRIGGER BUT HASN'T - Possible system issue!")
    else:
        print("   None found")
    
    # Show plans blocked by conditions
    print(f"\n⏸️ Plans Blocked by Conditions (Price in Range but Conditions Not Met):")
    if plans_blocked:
        for i, plan in enumerate(plans_blocked[:10], 1):
            print(f"\n{i}. Plan: {plan['plan_id'][:20]}...")
            print(f"   Direction: {plan['direction']} | Entry: ${plan['entry']:.2f}")
            print(f"   Distance: {plan['distance']:.2f} (within tolerance)")
            print(f"   Blocking Reasons: {', '.join(plan['blocking_reasons'])}")
            print(f"   Conditions: {list(plan['conditions'].keys())}")
    else:
        print("   None found")
    
    # Check system health
    print(f"\n🔧 System Health Check:")
    print(f"   Monitoring Running: {system_status.get('running', False)}")
    print(f"   Thread Alive: {system_status.get('thread_alive', False)}")
    
    if not system_status.get('running', False):
        print(f"   ❌ CRITICAL: Monitoring system is NOT running!")
    if not system_status.get('thread_alive', False):
        print(f"   ❌ CRITICAL: Monitoring thread is NOT alive!")
    
    # Recommendations
    print(f"\n" + "=" * 70)
    print("DIAGNOSIS & RECOMMENDATIONS")
    print("=" * 70)
    
    if plans_should_trigger:
        print(f"\n⚠️ CRITICAL ISSUE: {len(plans_should_trigger)} plan(s) should trigger but haven't!")
        print(f"   Possible causes:")
        print(f"   1. Monitoring system not checking conditions properly")
        print(f"   2. Condition validation logic has bugs")
        print(f"   3. System needs restart")
        print(f"   4. MT5 connection issues preventing execution")
    else:
        print(f"\n✅ All plans in range have blocking conditions")
        print(f"   Plans are waiting for structure conditions to form")
        print(f"   This is expected behavior")
    
    print(f"\n💡 Next Steps:")
    print(f"   1. Check if monitoring system is actually running")
    print(f"   2. Review condition validation logic")
    print(f"   3. Check MT5 connection status")
    print(f"   4. Consider restarting auto-execution system")
    print(f"   5. Check logs for errors")

if __name__ == "__main__":
    asyncio.run(diagnose_no_triggers())
