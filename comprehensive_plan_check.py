"""
Comprehensive check:
1. Check if new price-only plans triggered
2. Create more price-only plans at different levels
3. Investigate structure condition detection
"""
import asyncio
import json
from cursor_trading_bridge import get_bridge
from datetime import datetime

async def comprehensive_check():
    """Comprehensive plan check and investigation"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("COMPREHENSIVE PLAN ANALYSIS")
    print("=" * 70)
    
    # Get current price
    print("\n💰 Current Market Price:")
    try:
        xau_price = await bridge.get_current_price("XAUUSD")
        xau_bid = xau_price.get("data", {}).get("bid", None)
        print(f"   XAUUSD: ${xau_bid:.2f}" if xau_bid else "   XAUUSD: N/A")
    except Exception as e:
        print(f"   ⚠️ Could not get price: {e}")
        xau_bid = 4492.0
    
    # Get all plans
    status = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    # 1. Check if new price-only plans triggered
    print("\n" + "=" * 70)
    print("1. CHECKING NEW PRICE-ONLY PLANS")
    print("=" * 70)
    
    new_plan_ids = ["chatgpt_5c98c4e4", "chatgpt_69d75b03"]
    new_plans_found = []
    
    for plan in all_plans:
        plan_id = plan.get("plan_id", "")
        if plan_id in new_plan_ids:
            new_plans_found.append(plan)
            status_val = plan.get("status", "")
            executed_at = plan.get("executed_at")
            ticket = plan.get("ticket")
            entry = plan.get("entry_price", 0)
            direction = plan.get("direction", "")
            
            print(f"\n   Plan: {plan_id}")
            print(f"   Status: {status_val}")
            print(f"   Direction: {direction} | Entry: ${entry:.2f}")
            
            if status_val == "executed":
                print(f"   ✅ TRIGGERED! Executed at: {executed_at}")
                print(f"   Ticket: {ticket}")
            elif status_val == "pending":
                # Check if in range
                conditions = plan.get("conditions", {})
                tolerance = conditions.get("tolerance", 0)
                price_near = conditions.get("price_near", entry)
                distance = abs(xau_bid - price_near) if xau_bid else 999
                in_range = distance <= tolerance
                
                print(f"   ⏸️ Still Pending")
                print(f"   Price Near: ${price_near:.2f} | Tolerance: ±{tolerance}")
                print(f"   Current: ${xau_bid:.2f} | Distance: {distance:.2f}")
                print(f"   In Range: {'✅ YES' if in_range else '❌ NO'}")
                if in_range:
                    print(f"   ⚠️ Should trigger but hasn't - possible system issue!")
    
    if not new_plans_found:
        print("   ⚠️ New plans not found in system")
    
    # 2. Create more price-only plans at different levels
    print("\n" + "=" * 70)
    print("2. CREATING MORE PRICE-ONLY PLANS")
    print("=" * 70)
    
    # Create plans at multiple levels around current price
    price_levels = [
        {"entry": 4492.0, "direction": "SELL", "sl": 4496.0, "tp": 4485.0, "tolerance": 5.0},
        {"entry": 4490.0, "direction": "SELL", "sl": 4494.0, "tp": 4483.0, "tolerance": 5.0},
        {"entry": 4488.0, "direction": "SELL", "sl": 4492.0, "tp": 4481.0, "tolerance": 5.0},
        {"entry": 4495.0, "direction": "SELL", "sl": 4499.0, "tp": 4488.0, "tolerance": 5.0},
        {"entry": 4485.0, "direction": "BUY", "sl": 4481.0, "tp": 4492.0, "tolerance": 5.0},
        {"entry": 4487.0, "direction": "BUY", "sl": 4483.0, "tp": 4494.0, "tolerance": 5.0},
        {"entry": 4483.0, "direction": "BUY", "sl": 4479.0, "tp": 4490.0, "tolerance": 5.0},
    ]
    
    new_plans = []
    for level in price_levels:
        new_plans.append({
            "plan_type": "auto_trade",
            "symbol": "XAUUSDc",
            "direction": level["direction"],
            "entry": level["entry"],
            "stop_loss": level["sl"],
            "take_profit": level["tp"],
            "volume": 0.01,
            "conditions": {
                "price_near": level["entry"],
                "tolerance": level["tolerance"]
            },
            "expires_hours": 24,
            "notes": f"Price-only {level['direction']} at {level['entry']} - immediate trigger test"
        })
    
    print(f"\n   Creating {len(new_plans)} price-only plans at different levels...")
    create_result = await bridge.registry.execute(
        "moneybot.create_multiple_auto_plans",
        {"plans": new_plans}
    )
    
    create_data = create_result.get("data", {})
    successful = create_data.get("successful", 0)
    failed = create_data.get("failed", 0)
    
    print(f"   ✅ Created: {successful}")
    print(f"   ❌ Failed: {failed}")
    
    if create_data.get("results"):
        print(f"\n   Created Plan IDs:")
        for result in create_data["results"][:5]:
            if result.get("status") == "created":
                plan_id = result.get("plan_id", "N/A")
                print(f"      {plan_id}")
    
    # 3. Investigate structure condition detection
    print("\n" + "=" * 70)
    print("3. INVESTIGATING STRUCTURE CONDITION DETECTION")
    print("=" * 70)
    
    # Get a sample plan with structure conditions
    structure_plans = []
    for plan in all_plans:
        if plan.get("symbol") == "XAUUSDc":
            conditions = plan.get("conditions", {})
            if any([
                conditions.get("liquidity_sweep"),
                conditions.get("rejection_wick"),
                conditions.get("choch_bull"),
                conditions.get("choch_bear"),
                conditions.get("bos_bull"),
                conditions.get("bos_bear"),
                conditions.get("order_block")
            ]):
                structure_plans.append(plan)
    
    print(f"\n   Found {len(structure_plans)} plans with structure conditions")
    
    if structure_plans:
        sample_plan = structure_plans[0]
        plan_id = sample_plan.get("plan_id", "N/A")
        conditions = sample_plan.get("conditions", {})
        
        print(f"\n   Sample Plan: {plan_id[:20]}...")
        print(f"   Conditions: {list(conditions.keys())}")
        
        # Check what structure conditions are set
        print(f"\n   Structure Conditions Set:")
        if conditions.get("liquidity_sweep"):
            print(f"      ✅ liquidity_sweep: {conditions.get('liquidity_sweep')}")
            print(f"         Timeframe: {conditions.get('timeframe', 'N/A')}")
        if conditions.get("rejection_wick"):
            print(f"      ✅ rejection_wick: {conditions.get('rejection_wick')}")
            print(f"         Timeframe: {conditions.get('timeframe', 'N/A')}")
        if conditions.get("choch_bull") or conditions.get("choch_bear"):
            print(f"      ✅ CHOCH: {conditions.get('choch_bull', False) or conditions.get('choch_bear', False)}")
            print(f"         Timeframe: {conditions.get('timeframe', 'N/A')}")
        if conditions.get("bos_bull") or conditions.get("bos_bear"):
            print(f"      ✅ BOS: {conditions.get('bos_bull', False) or conditions.get('bos_bear', False)}")
            print(f"         Timeframe: {conditions.get('timeframe', 'N/A')}")
        if conditions.get("order_block"):
            print(f"      ✅ order_block: {conditions.get('order_block')}")
            print(f"         Type: {conditions.get('order_block_type', 'N/A')}")
        
        print(f"\n   🔍 Investigation Notes:")
        print(f"      • Structure conditions require real-time market analysis")
        print(f"      • Liquidity sweep: Needs M1/M5 candle analysis to detect sweep")
        print(f"      • Rejection wick: Needs wick ratio > 2.0 (wick > 2x body)")
        print(f"      • CHOCH/BOS: Needs structure break confirmation on M15/M30")
        print(f"      • Order block: Needs validation score ≥ 60")
        print(f"      • These conditions may not be forming in current market")
        print(f"      • Or detection logic may not be working correctly")
        
        # Try to get current market structure
        print(f"\n   📊 Checking Current Market Structure...")
        try:
            analysis = await bridge.analyze_symbol("XAUUSD")
            structure = analysis.get("data", {}).get("structure_summary", {})
            if structure:
                print(f"      Structure available in analysis")
                print(f"      Check analysis data for CHOCH/BOS/Order Blocks")
            else:
                print(f"      ⚠️ Structure data not available in analysis")
        except Exception as e:
            print(f"      ⚠️ Could not analyze structure: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n✅ Checked {len(new_plan_ids)} new price-only plans")
    print(f"✅ Created {successful} additional price-only plans at different levels")
    print(f"✅ Investigated {len(structure_plans)} plans with structure conditions")
    print(f"\n💡 Next Steps:")
    print(f"   1. Monitor new price-only plans - they should trigger if price is in range")
    print(f"   2. If price-only plans don't trigger, there's a system issue")
    print(f"   3. Structure conditions require market events to form")
    print(f"   4. Consider using price-only plans for faster execution")

if __name__ == "__main__":
    asyncio.run(comprehensive_check())
