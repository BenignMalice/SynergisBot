"""
Check for price-only BTC plans in the system
"""
import asyncio
import json
from cursor_trading_bridge import get_bridge

async def check_price_only_plans():
    """Check for price-only BTC plans"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("BTC PRICE-ONLY PLANS CHECK")
    print("=" * 70)
    
    # Get all active plans
    print("\n1. Getting Active Plans...")
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    # Filter for BTC plans
    btc_plans = [
        p for p in all_plans 
        if p.get("symbol", "").startswith("BTCUSD") or p.get("symbol", "").startswith("BTC")
    ]
    
    print(f"   Found {len(btc_plans)} active BTC plan(s)")
    
    # Identify price-only plans
    print("\n2. Analyzing Plans...")
    print("-" * 70)
    
    price_only_plans = []
    structure_plans = []
    
    for plan in btc_plans:
        plan_id = plan.get("plan_id", "N/A")
        symbol = plan.get("symbol", "N/A")
        direction = plan.get("direction", "N/A")
        status = plan.get("status", "N/A")
        conditions = plan.get("conditions", {})
        
        # Check if price-only
        has_price_near = conditions.get("price_near") is not None
        has_tolerance = conditions.get("tolerance") is not None
        
        # Check for structure conditions
        has_structure = False
        structure_conditions = conditions.get("structure_conditions", {})
        if structure_conditions:
            has_structure = any(structure_conditions.values())
        
        # Check for other structure indicators
        structure_keys = [
            "liquidity_sweep", "rejection_wick", "choch_bull", "choch_bear",
            "bos_bull", "bos_bear", "order_block", "m1_choch", "m1_bos",
            "fvg_bull", "fvg_bear", "breaker_block", "mss_bull", "mss_bear"
        ]
        
        has_structure_indicators = any(conditions.get(key) for key in structure_keys)
        
        # Check for timeframe requirement (indicates structure-based)
        has_timeframe = conditions.get("timeframe") is not None
        
        # Price-only definition: has price_near and tolerance, but no structure conditions
        is_price_only = (
            has_price_near and
            has_tolerance and
            not has_structure and
            not has_structure_indicators and
            not has_timeframe
        )
        
        if is_price_only:
            price_only_plans.append(plan)
        else:
            structure_plans.append(plan)
    
    # Display price-only plans
    print(f"\n3. PRICE-ONLY PLANS: {len(price_only_plans)}")
    print("=" * 70)
    
    if price_only_plans:
        for i, plan in enumerate(price_only_plans, 1):
            plan_id = plan.get("plan_id", "N/A")
            symbol = plan.get("symbol", "N/A")
            direction = plan.get("direction", "N/A")
            status = plan.get("status", "N/A")
            conditions = plan.get("conditions", {})
            
            price_near = conditions.get("price_near", 0)
            tolerance = conditions.get("tolerance", 0)
            confluence_min = conditions.get("confluence_min")
            
            print(f"\n{i}. Plan ID: {plan_id}")
            print(f"   Symbol: {symbol} | Direction: {direction} | Status: {status}")
            print(f"   Price Near: ${price_near:.2f}")
            print(f"   Tolerance: {tolerance} points")
            if confluence_min:
                print(f"   Confluence Min: {confluence_min}")
            else:
                print(f"   Confluence Min: Not specified")
            
            # Check if it has any other conditions
            other_conditions = []
            for key in conditions.keys():
                if key not in ["price_near", "tolerance", "confluence_min"]:
                    if conditions.get(key):
                        other_conditions.append(key)
            
            if other_conditions:
                print(f"   Other Conditions: {', '.join(other_conditions)}")
            else:
                print(f"   Other Conditions: None (pure price-only)")
    else:
        print("\n   No price-only BTC plans found")
    
    # Display structure-based plans for comparison
    print(f"\n4. STRUCTURE-BASED PLANS: {len(structure_plans)}")
    print("=" * 70)
    
    if structure_plans:
        # Separate into minimal structure vs full structure
        minimal_structure = []
        full_structure = []
        
        for plan in structure_plans:
            conditions = plan.get("conditions", {})
            
            # Count structure indicators
            structure_count = sum(1 for key in [
                "liquidity_sweep", "rejection_wick", "choch_bull", "choch_bear",
                "bos_bull", "bos_bear", "order_block", "m1_choch", "m1_bos"
            ] if conditions.get(key))
            
            structure_conditions = conditions.get("structure_conditions", {})
            if structure_conditions:
                structure_count += sum(1 for v in structure_conditions.values() if v)
            
            if structure_count == 0 and conditions.get("price_near") and conditions.get("tolerance"):
                # Has price_near and tolerance but no explicit structure - might be effectively price-only
                minimal_structure.append(plan)
            else:
                full_structure.append(plan)
        
        if minimal_structure:
            print(f"\n   MINIMAL STRUCTURE PLANS (effectively price-only): {len(minimal_structure)}")
            for i, plan in enumerate(minimal_structure, 1):
                plan_id = plan.get("plan_id", "N/A")
                direction = plan.get("direction", "N/A")
                status = plan.get("status", "N/A")
                conditions = plan.get("conditions", {})
                
                price_near = conditions.get("price_near", 0)
                tolerance = conditions.get("tolerance", 0)
                confluence_min = conditions.get("confluence_min")
                
                print(f"   {i}. {plan_id}: {direction} ({status})")
                print(f"      Price Near: ${price_near:.2f}, Tolerance: {tolerance} points")
                if confluence_min:
                    print(f"      Confluence Min: {confluence_min}")
        
        if full_structure:
            print(f"\n   FULL STRUCTURE PLANS: {len(full_structure)}")
            for i, plan in enumerate(full_structure[:10], 1):  # Show first 10
                plan_id = plan.get("plan_id", "N/A")
                direction = plan.get("direction", "N/A")
                status = plan.get("status", "N/A")
                conditions = plan.get("conditions", {})
                
                # Identify structure type
                structure_types = []
                if conditions.get("liquidity_sweep"):
                    structure_types.append("Liquidity Sweep")
                if conditions.get("rejection_wick"):
                    structure_types.append("Rejection Wick")
                if conditions.get("choch_bull") or conditions.get("choch_bear"):
                    structure_types.append("CHOCH")
                if conditions.get("bos_bull") or conditions.get("bos_bear"):
                    structure_types.append("BOS")
                if conditions.get("order_block"):
                    structure_types.append("Order Block")
                if conditions.get("m1_choch") or conditions.get("m1_bos"):
                    structure_types.append("M1 Microstructure")
                
                structure_str = ", ".join(structure_types) if structure_types else "Price-based with structure"
                
                print(f"   {i}. {plan_id}: {direction} ({status}) - {structure_str}")
    else:
        print("\n   No structure-based BTC plans found")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    print(f"\nTotal BTC Plans: {len(btc_plans)}")
    print(f"Price-Only Plans: {len(price_only_plans)}")
    print(f"Structure-Based Plans: {len(structure_plans)}")
    
    if price_only_plans:
        print(f"\nPrice-Only Plan IDs:")
        for plan in price_only_plans:
            print(f"   - {plan.get('plan_id')} ({plan.get('direction')}, {plan.get('status')})")
        
        print(f"\nRecommendation:")
        print(f"   Consider cancelling these price-only plans if you want to focus on")
        print(f"   structure-based strategies with higher confluence requirements.")

if __name__ == "__main__":
    asyncio.run(check_price_only_plans())
