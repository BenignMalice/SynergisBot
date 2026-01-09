"""
Check if latest plans are price-only or have conditions
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def check_latest_plans():
    """Check conditions of recently created plans"""
    bridge = get_bridge()
    
    print("=" * 80)
    print("LATEST PLANS CONDITIONS CHECK")
    print("=" * 80)
    
    # Latest plan IDs we created
    latest_plan_ids = [
        # BTC plans
        "chatgpt_92a3aa65",  # order_block BUY
        "chatgpt_ae2c5ce7",  # order_block SELL
        "chatgpt_45b1c505",  # auto_trade BUY
        "chatgpt_095a448e",  # auto_trade SELL
        # XAUUSD plan
        "chatgpt_bd18a876",  # bearish breakout SELL
    ]
    
    print(f"\n1. Getting Plan Details...")
    print("-" * 80)
    
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    # Find our plans
    found_plans = []
    for plan_id in latest_plan_ids:
        plan = next((p for p in all_plans if p.get("plan_id") == plan_id), None)
        if plan:
            found_plans.append(plan)
        else:
            print(f"   ⚠️  {plan_id}: NOT FOUND")
    
    print(f"\n2. Analyzing Plan Conditions:")
    print("-" * 80)
    
    price_only_count = 0
    structure_based_count = 0
    
    for plan in found_plans:
        plan_id = plan.get("plan_id", "N/A")
        symbol = plan.get("symbol", "N/A")
        direction = plan.get("direction", "N/A")
        status = plan.get("status", "N/A")
        conditions = plan.get("conditions", {})
        
        print(f"\n   Plan: {plan_id}")
        print(f"   Symbol: {symbol} | Direction: {direction} | Status: {status}")
        
        # Check for price-only vs structure-based
        has_price_near = conditions.get("price_near") is not None
        has_tolerance = conditions.get("tolerance") is not None
        
        # Check for structure conditions
        structure_keys = [
            "liquidity_sweep", "rejection_wick", "choch_bull", "choch_bear",
            "bos_bull", "bos_bear", "order_block", "m1_choch", "m1_bos",
            "fvg_bull", "fvg_bear", "breaker_block", "mss_bull", "mss_bear"
        ]
        has_structure_indicators = any(conditions.get(key) for key in structure_keys)
        
        structure_conditions = conditions.get("structure_conditions", {})
        has_structure_conditions = structure_conditions and any(structure_conditions.values())
        
        has_timeframe = conditions.get("timeframe") is not None
        has_strategy_type = conditions.get("strategy_type") is not None
        
        # Determine plan type
        if has_price_near and has_tolerance and not has_structure_indicators and not has_structure_conditions and not has_timeframe:
            plan_type = "PRICE-ONLY"
            price_only_count += 1
        else:
            plan_type = "STRUCTURE-BASED"
            structure_based_count += 1
        
        print(f"   Type: {plan_type}")
        
        # Show conditions
        print(f"   Conditions:")
        if has_price_near:
            print(f"      - price_near: ${conditions.get('price_near', 0):,.2f}")
        if has_tolerance:
            print(f"      - tolerance: {conditions.get('tolerance', 0)}")
        if has_strategy_type:
            print(f"      - strategy_type: {conditions.get('strategy_type', 'N/A')}")
        if has_timeframe:
            print(f"      - timeframe: {conditions.get('timeframe', 'N/A')}")
        
        # Show structure indicators
        structure_found = []
        for key in structure_keys:
            if conditions.get(key):
                structure_found.append(key)
        
        if structure_conditions:
            for key, value in structure_conditions.items():
                if value:
                    structure_found.append(f"structure_conditions.{key}")
        
        if structure_found:
            print(f"      - Structure Indicators: {', '.join(structure_found)}")
        elif plan_type == "STRUCTURE-BASED":
            print(f"      - Structure: Plan type indicates structure-based (order_block/rejection_wick)")
        
        # Check plan type from plan itself
        plan_type_field = plan.get("plan_type", "N/A")
        if plan_type_field != "N/A":
            print(f"   Plan Type Field: {plan_type_field}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print(f"\nTotal Plans Checked: {len(found_plans)}")
    print(f"   Price-Only Plans: {price_only_count}")
    print(f"   Structure-Based Plans: {structure_based_count}")
    
    if price_only_count > 0:
        print(f"\n⚠️  WARNING: {price_only_count} plan(s) are price-only")
        print(f"   These plans will execute based solely on price proximity")
        print(f"   Consider adding structure conditions for better confluence")
    
    if structure_based_count > 0:
        print(f"\n✅ {structure_based_count} plan(s) have structure conditions")
        print(f"   These plans require both price AND structure confirmation")

if __name__ == "__main__":
    asyncio.run(check_latest_plans())
