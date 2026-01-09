"""
Cancel old XAUUSD plans with stop losses > 5 points
"""
import asyncio
import json
from cursor_trading_bridge import get_bridge

async def cancel_old_plans():
    """Cancel old XAUUSD plans with wide stop losses"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("CANCELLING OLD XAUUSD PLANS WITH WIDE STOP LOSSES")
    print("=" * 70)
    
    # Get system status to find all XAUUSD plans
    status = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    # Filter XAUUSD plans
    xau_plans = [p for p in all_plans if p.get("symbol") == "XAUUSDc"]
    
    print(f"\n📊 Total XAUUSD Plans: {len(xau_plans)}")
    
    # Find plans with SL > 5 points
    plans_to_cancel = []
    
    for plan in xau_plans:
        plan_id = plan.get("plan_id", "")
        status_val = plan.get("status", "")
        entry = plan.get("entry_price", 0)
        sl = plan.get("stop_loss", 0)
        
        # Skip if already executed/cancelled/expired
        if status_val not in ["pending", "executing"]:
            continue
        
        # Calculate SL distance
        if entry and sl:
            sl_distance = abs(entry - sl)
            
            # Check if SL > 5 points
            if sl_distance > 5.0:
                # Check if it's an optimized plan (shouldn't cancel those)
                notes = plan.get("notes", "")
                is_optimized = "OPTIMIZED" in notes.upper()
                
                if not is_optimized:
                    plans_to_cancel.append({
                        "plan_id": plan_id,
                        "entry": entry,
                        "sl": sl,
                        "sl_distance": sl_distance,
                        "direction": plan.get("direction", "N/A"),
                        "notes": notes[:60] if notes else ""
                    })
    
    if not plans_to_cancel:
        print("\n✅ No old plans found with SL > 5 points")
        print("   All plans either:")
        print("   • Have SL <= 5 points")
        print("   • Are already optimized")
        print("   • Are already executed/cancelled")
        return
    
    print(f"\n⚠️ Found {len(plans_to_cancel)} plans with SL > 5 points")
    
    # Show plans to be cancelled
    print("\n📋 Plans to Cancel:")
    print("-" * 70)
    
    total_sl_distance = 0
    by_direction = {"BUY": 0, "SELL": 0}
    
    for i, plan_info in enumerate(plans_to_cancel, 1):
        print(f"\n{i}. Plan: {plan_info['plan_id'][:30]}...")
        print(f"   Direction: {plan_info['direction']}")
        print(f"   Entry: ${plan_info['entry']:.2f} | SL: ${plan_info['sl']:.2f}")
        print(f"   SL Distance: {plan_info['sl_distance']:.2f} points ⚠️")
        if plan_info['notes']:
            print(f"   Notes: {plan_info['notes']}...")
        
        total_sl_distance += plan_info['sl_distance']
        by_direction[plan_info['direction']] += 1
    
    print(f"\n📊 Summary:")
    print(f"   Total Plans: {len(plans_to_cancel)}")
    print(f"   BUY: {by_direction['BUY']}")
    print(f"   SELL: {by_direction['SELL']}")
    print(f"   Average SL Distance: {total_sl_distance/len(plans_to_cancel):.2f} points")
    
    # Confirm cancellation
    print(f"\n🚨 Ready to cancel {len(plans_to_cancel)} plans")
    print(f"   These plans have stop losses > 5 points")
    print(f"   They will be replaced by optimized plans (3.5 point SL)")
    
    # Cancel plans
    plan_ids_to_cancel = [p["plan_id"] for p in plans_to_cancel]
    
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
        for result in cancel_data["results"]:
            plan_id = result.get("plan_id", "N/A")
            status = result.get("status", "N/A")
            message = result.get("message", "")
            
            if status == "cancelled":
                print(f"   ✅ {plan_id[:30]}... - Cancelled")
            else:
                print(f"   ❌ {plan_id[:30]}... - {status}: {message}")
    
    # Summary
    print("\n" + "=" * 70)
    print("CANCELLATION SUMMARY")
    print("=" * 70)
    
    print(f"\n✅ Actions Completed:")
    print(f"   • Identified {len(plans_to_cancel)} plans with SL > 5 points")
    print(f"   • Cancelled {successful} plans")
    print(f"   • {failed} cancellations failed")
    
    print(f"\n💡 Next Steps:")
    print(f"   • Monitor optimized plans (3.5 point SL)")
    print(f"   • Compare performance vs old plans")
    print(f"   • Adjust further if needed")
    
    # Show remaining XAUUSD plans
    print(f"\n📊 Remaining XAUUSD Plans:")
    remaining = [p for p in xau_plans if p.get("status") in ["pending", "executing"]]
    remaining_optimized = [p for p in remaining if "OPTIMIZED" in p.get("notes", "").upper()]
    
    print(f"   Total Pending: {len(remaining)}")
    print(f"   Optimized Plans: {len(remaining_optimized)}")
    print(f"   Other Plans: {len(remaining) - len(remaining_optimized)}")

if __name__ == "__main__":
    asyncio.run(cancel_old_plans())
