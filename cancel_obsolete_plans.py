"""
Cancel obsolete auto-execution plans identified in viability review
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def cancel_obsolete_plans():
    """Cancel obsolete plans from viability review"""
    bridge = get_bridge()
    
    print("=" * 80)
    print("CANCELLING OBSOLETE AUTO-EXECUTION PLANS")
    print("=" * 80)
    
    # Current obsolete plans (updated based on latest review)
    obsolete_plan_ids = [
        # XAUUSD obsolete plans (7) - SELL plans far from current price
        "chatgpt_ae88beb4",  # SELL - Target: $4492.00, Diff: $17.44
        "chatgpt_206eb10b",  # SELL - Target: $4488.00, Diff: $13.44
        "chatgpt_6dd2c794",  # SELL - Target: $4488.00, Diff: $13.44
        "chatgpt_e1e32ad7",  # SELL - Target: $4492.00, Diff: $17.44
        "chatgpt_8afeafa3",  # SELL - Target: $4485.00, Diff: $10.44
        "chatgpt_eca9feda",  # SELL - Target: $4492.00, Diff: $17.44
        "chatgpt_ace396c9",  # SELL - Target: $4492.00, Diff: $17.44
    ]
    
    print(f"\n1. Plans to Cancel: {len(obsolete_plan_ids)}")
    print("-" * 80)
    
    print(f"\n   XAUUSD Plans: {len(obsolete_plan_ids)}")
    for plan_id in obsolete_plan_ids:
        print(f"      - {plan_id}")
    
    print(f"\n2. Cancelling Plans...")
    print("-" * 80)
    
    # Cancel the plans
    cancel_result = await bridge.registry.execute(
        "moneybot.cancel_multiple_auto_plans",
        {"plan_ids": obsolete_plan_ids}
    )
    
    cancel_data = cancel_result.get("data", {})
    cancelled = cancel_data.get("cancelled", [])
    failed = cancel_data.get("failed", [])
    
    print(f"\n   Cancelled: {len(cancelled)} plan(s)")
    if cancelled:
        for plan_id in cancelled:
            print(f"      ✅ {plan_id}")
    
    if failed:
        print(f"\n   Failed to cancel: {len(failed)} plan(s)")
        for plan_id in failed:
            print(f"      ❌ {plan_id}")
    
    # Verify cancellation
    print(f"\n3. Verifying Cancellation...")
    print("-" * 80)
    
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    remaining = [p for p in all_plans if p.get("plan_id") in obsolete_plan_ids]
    
    if remaining:
        print(f"   ⚠️  WARNING: {len(remaining)} plan(s) still active:")
        for plan in remaining:
            print(f"      - {plan.get('plan_id')} (status: {plan.get('status')})")
    else:
        print(f"   ✅ All obsolete plans successfully cancelled")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print(f"\nPlans Cancelled: {len(cancelled)}/{len(obsolete_plan_ids)}")
    print(f"   XAUUSD: {len(cancelled)}/{len(obsolete_plan_ids)}")
    
    if len(cancelled) == len(obsolete_plan_ids):
        print(f"\n✅ All obsolete plans have been cancelled successfully.")
        print(f"   Remaining active plans: {len(all_plans) - len(cancelled)}")
    else:
        print(f"\n⚠️  Some plans could not be cancelled. Please review manually.")

if __name__ == "__main__":
    asyncio.run(cancel_obsolete_plans())
