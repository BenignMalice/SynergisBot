"""
Cancel specific BTC price-only plans
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def cancel_specific_plans():
    """Cancel the 4 identified price-only BTC plans"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("CANCELLING SPECIFIC BTC PRICE-ONLY PLANS")
    print("=" * 70)
    
    # The 4 price-only plans identified earlier
    plan_ids_to_cancel = [
        "chatgpt_bef35d0a",  # BUY - Price Near: $87650.00, Tolerance: 120
        "chatgpt_8cbe5fa5",  # SELL - Price Near: $87850.00, Tolerance: 120
        "chatgpt_f7a2a8d6",  # BUY - Price Near: $87620.00, Tolerance: 80
        "chatgpt_22640c20",  # BUY - Price Near: $87200.00, Tolerance: 400
    ]
    
    print(f"\n1. Plans to Cancel: {len(plan_ids_to_cancel)}")
    for plan_id in plan_ids_to_cancel:
        print(f"   - {plan_id}")
    
    print(f"\n2. Cancelling Plans...")
    print("-" * 70)
    
    # Cancel the plans
    cancel_result = await bridge.registry.execute(
        "moneybot.cancel_multiple_auto_plans",
        {"plan_ids": plan_ids_to_cancel}
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
    
    # Verify cancellation
    print(f"\n3. Verifying Cancellation...")
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    remaining = [p for p in all_plans if p.get("plan_id") in plan_ids_to_cancel]
    
    if remaining:
        print(f"   WARNING: {len(remaining)} plan(s) still active:")
        for plan in remaining:
            print(f"      - {plan.get('plan_id')} (status: {plan.get('status')})")
    else:
        print(f"   OK: All plans successfully cancelled")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    print(f"\nPlans Cancelled: {len(cancelled)}/{len(plan_ids_to_cancel)}")
    
    if len(cancelled) == len(plan_ids_to_cancel):
        print(f"\nAll price-only BTC plans have been cancelled successfully.")

if __name__ == "__main__":
    asyncio.run(cancel_specific_plans())
