"""
Cancel price-only BTC plans
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def cancel_price_only_plans():
    """Cancel price-only BTC plans"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("CANCELLING PRICE-ONLY BTC PLANS")
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
    
    # Identify price-only plans (minimal structure - effectively price-only)
    price_only_plan_ids = []
    
    for plan in btc_plans:
        plan_id = plan.get("plan_id", "N/A")
        conditions = plan.get("conditions", {})
        
        # Check if price-only (minimal structure)
        has_price_near = conditions.get("price_near") is not None
        has_tolerance = conditions.get("tolerance") is not None
        
        # Check for structure indicators
        structure_keys = [
            "liquidity_sweep", "rejection_wick", "choch_bull", "choch_bear",
            "bos_bull", "bos_bear", "order_block", "m1_choch", "m1_bos"
        ]
        has_structure_indicators = any(conditions.get(key) for key in structure_keys)
        
        structure_conditions = conditions.get("structure_conditions", {})
        has_structure = structure_conditions and any(structure_conditions.values())
        
        has_timeframe = conditions.get("timeframe") is not None
        
        # Count structure indicators
        structure_count = sum(1 for key in structure_keys if conditions.get(key))
        if structure_conditions:
            structure_count += sum(1 for v in structure_conditions.values() if v)
        
        # Price-only: has price_near and tolerance, but minimal/no structure
        # This matches the "minimal structure" plans we found earlier
        is_price_only = (
            has_price_near and
            has_tolerance and
            structure_count == 0 and  # No structure indicators
            not has_timeframe
        )
        
        if is_price_only:
            price_only_plan_ids.append(plan_id)
            direction = plan.get("direction", "N/A")
            price_near = conditions.get("price_near", 0)
            tolerance = conditions.get("tolerance", 0)
            confluence_min = conditions.get("confluence_min")
            print(f"\n   Found: {plan_id} ({direction})")
            print(f"      Price Near: ${price_near:.2f}, Tolerance: {tolerance} points")
            if confluence_min:
                print(f"      Confluence Min: {confluence_min}")
    
    if not price_only_plan_ids:
        print("\n   No price-only BTC plans found to cancel")
        return
    
    print(f"\n2. Cancelling {len(price_only_plan_ids)} Price-Only Plan(s)...")
    print("-" * 70)
    
    # Cancel the plans
    cancel_result = await bridge.registry.execute(
        "moneybot.cancel_multiple_auto_plans",
        {"plan_ids": price_only_plan_ids}
    )
    
    cancel_data = cancel_result.get("data", {})
    cancelled = cancel_data.get("cancelled", [])
    failed = cancel_data.get("failed", [])
    
    print(f"\n   Cancelled: {len(cancelled)} plan(s)")
    for plan_id in cancelled:
        print(f"      - {plan_id}")
    
    if failed:
        print(f"\n   Failed to cancel: {len(failed)} plan(s)")
        for plan_id in failed:
            print(f"      - {plan_id}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    print(f"\nPrice-Only Plans Cancelled: {len(cancelled)}")
    print(f"Remaining BTC Plans: {len(btc_plans) - len(cancelled)}")
    
    if cancelled:
        print(f"\nAll price-only BTC plans have been cancelled successfully.")

if __name__ == "__main__":
    asyncio.run(cancel_price_only_plans())
