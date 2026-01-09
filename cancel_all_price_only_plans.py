"""
Cancel all price-only plans (plans with only price_near + tolerance, no structure conditions)
"""
import asyncio
import json
from cursor_trading_bridge import get_bridge

async def cancel_price_only_plans():
    """Cancel all price-only plans"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("CANCELLING ALL PRICE-ONLY PLANS")
    print("=" * 70)
    
    # Get system status to find all plans
    status = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    print(f"\n📊 Total Plans: {len(all_plans)}")
    
    # Identify price-only plans
    price_only_plans = []
    
    for plan in all_plans:
        plan_id = plan.get("plan_id", "")
        status_val = plan.get("status", "")
        symbol = plan.get("symbol", "")
        conditions = plan.get("conditions", {})
        
        # Skip if already executed/cancelled/expired
        if status_val not in ["pending", "executing"]:
            continue
        
        # Check if it's a price-only plan
        # Price-only = has price_near + tolerance, but NO structure/M1 conditions
        has_price_near = "price_near" in conditions
        has_tolerance = "tolerance" in conditions
        
        # Check for structure conditions
        has_structure = any([
            conditions.get("liquidity_sweep"),
            conditions.get("rejection_wick"),
            conditions.get("choch_bull"),
            conditions.get("choch_bear"),
            conditions.get("bos_bull"),
            conditions.get("bos_bear"),
            conditions.get("order_block"),
            conditions.get("inside_bar"),
            conditions.get("m1_choch"),
            conditions.get("m1_bos"),
            conditions.get("m1_choch_bos_combo"),
            conditions.get("m1_volatility_contracting"),
            conditions.get("m1_volatility_expanding"),
            conditions.get("m1_squeeze_duration"),
            conditions.get("m1_momentum_quality"),
            conditions.get("m1_structure_type"),
            conditions.get("m1_trend_alignment"),
        ])
        
        # Check for other conditions that indicate it's not price-only
        has_other_conditions = any([
            conditions.get("confluence_min"),
            conditions.get("timeframe"),
            conditions.get("range_low"),
            conditions.get("range_high"),
            conditions.get("strategy_type"),
        ])
        
        # Price-only = has price_near + tolerance, but NO structure/M1/other conditions
        # However, we'll allow confluence_min as it's minimal and was added to optimized plans
        # So price-only = price_near + tolerance, but NO structure/M1 conditions
        # (confluence_min is OK, it's a filter, not a structure condition)
        
        is_price_only = (
            has_price_near and 
            has_tolerance and 
            not has_structure and
            not conditions.get("timeframe")  # timeframe indicates structure-based
        )
        
        if is_price_only:
            entry = plan.get("entry_price", 0)
            sl = plan.get("stop_loss", 0)
            sl_distance = abs(entry - sl) if entry and sl else 0
            notes = plan.get("notes", "")
            
            price_only_plans.append({
                "plan_id": plan_id,
                "symbol": symbol,
                "direction": plan.get("direction", "N/A"),
                "entry": entry,
                "sl": sl,
                "sl_distance": sl_distance,
                "notes": notes[:60] if notes else "",
                "confluence": conditions.get("confluence_min", "N/A")
            })
    
    if not price_only_plans:
        print("\n✅ No price-only plans found")
        print("   All plans either:")
        print("   • Have structure conditions")
        print("   • Are already executed/cancelled")
        return
    
    print(f"\n⚠️ Found {len(price_only_plans)} price-only plans")
    
    # Group by symbol
    by_symbol = {}
    for plan in price_only_plans:
        symbol = plan["symbol"]
        if symbol not in by_symbol:
            by_symbol[symbol] = []
        by_symbol[symbol].append(plan)
    
    # Show plans to be cancelled
    print("\n📋 Price-Only Plans to Cancel:")
    print("-" * 70)
    
    for symbol, symbol_plans in sorted(by_symbol.items()):
        print(f"\n📊 {symbol}: {len(symbol_plans)} plans")
        
        for i, plan_info in enumerate(symbol_plans, 1):
            print(f"   {i}. {plan_info['plan_id'][:30]}...")
            print(f"      {plan_info['direction']} @ ${plan_info['entry']:.2f}")
            print(f"      SL Distance: {plan_info['sl_distance']:.2f} points")
            if plan_info['confluence'] != "N/A":
                print(f"      Confluence: {plan_info['confluence']}%")
            if plan_info['notes']:
                print(f"      Notes: {plan_info['notes']}...")
    
    print(f"\n📊 Summary by Symbol:")
    for symbol, symbol_plans in sorted(by_symbol.items()):
        print(f"   {symbol}: {len(symbol_plans)} plans")
    
    total_plans = len(price_only_plans)
    print(f"\n   Total: {total_plans} price-only plans")
    
    # Confirm cancellation
    print(f"\n🚨 Ready to cancel {total_plans} price-only plans")
    print(f"   These plans have only price_near + tolerance conditions")
    print(f"   No structure/M1 conditions")
    
    # Cancel plans
    plan_ids_to_cancel = [p["plan_id"] for p in price_only_plans]
    
    print(f"\n🔄 Cancelling plans...")
    
    cancel_result = await bridge.registry.execute(
        "moneybot.cancel_multiple_auto_plans",
        {"plan_ids": plan_ids_to_cancel}
    )
    
    cancel_data = cancel_result.get("data", {})
    successful = cancel_data.get("successful", 0)
    failed = cancel_data.get("failed", 0)
    
    print(f"\n✅ Cancellation Results:")
    print(f"   Successfully Cancelled: {successful}")
    print(f"   Failed: {failed}")
    
    if cancel_data.get("results"):
        print(f"\n📋 Cancellation Details:")
        cancelled_count = 0
        failed_count = 0
        
        for result in cancel_data["results"]:
            plan_id = result.get("plan_id", "N/A")
            status = result.get("status", "N/A")
            message = result.get("message", "")
            
            if status == "cancelled":
                cancelled_count += 1
                if cancelled_count <= 10:  # Show first 10
                    print(f"   ✅ {plan_id[:30]}... - Cancelled")
            else:
                failed_count += 1
                print(f"   ❌ {plan_id[:30]}... - {status}: {message}")
        
        if cancelled_count > 10:
            print(f"   ... and {cancelled_count - 10} more cancelled")
    
    # Summary
    print("\n" + "=" * 70)
    print("CANCELLATION SUMMARY")
    print("=" * 70)
    
    print(f"\n✅ Actions Completed:")
    print(f"   • Identified {total_plans} price-only plans")
    print(f"   • Cancelled {successful} plans")
    print(f"   • {failed} cancellations failed")
    
    print(f"\n📊 Breakdown by Symbol:")
    for symbol, symbol_plans in sorted(by_symbol.items()):
        print(f"   {symbol}: {len(symbol_plans)} plans cancelled")
    
    print(f"\n💡 Next Steps:")
    print(f"   • Monitor remaining structure-based plans")
    print(f"   • Create new plans with proper structure conditions if needed")
    print(f"   • Review performance of structure-based vs price-only")

if __name__ == "__main__":
    asyncio.run(cancel_price_only_plans())
