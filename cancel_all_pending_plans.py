"""
Cancel all pending auto-execution plans
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def cancel_all_pending_plans():
    """Cancel all pending auto-execution plans"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("CANCELLING ALL PENDING AUTO-EXECUTION PLANS")
    print("=" * 70)
    
    # Get all plans
    print("\n1. Fetching all plans...")
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    # Filter for pending plans only
    pending_plans = [p for p in all_plans if p.get("status") == "pending"]
    
    if not pending_plans:
        print("\n   No pending plans found. Nothing to cancel.")
        return
    
    print(f"\n   Found {len(pending_plans)} pending plan(s)")
    
    # Display plans
    print("\n2. Pending Plans to Cancel:")
    print("-" * 70)
    for i, plan in enumerate(pending_plans, 1):
        plan_id = plan.get("plan_id", "unknown")
        symbol = plan.get("symbol", "unknown")
        direction = plan.get("direction", "unknown")
        entry = plan.get("entry_price", 0)
        print(f"   {i}. {plan_id}")
        print(f"      {symbol} {direction} @ ${entry:.2f}")
    
    # Get plan IDs
    plan_ids_to_cancel = [p.get("plan_id") for p in pending_plans]
    
    # Confirm cancellation
    print(f"\n3. Ready to cancel {len(plan_ids_to_cancel)} pending plan(s)")
    print("-" * 70)
    
    # Cancel plans
    print(f"\n4. Cancelling plans...")
    print("-" * 70)
    
    cancel_result = await bridge.registry.execute(
        "moneybot.cancel_multiple_auto_plans",
        {"plan_ids": plan_ids_to_cancel}
    )
    
    cancel_data = cancel_result.get("data", {})
    successful = cancel_data.get("successful", 0)
    failed = cancel_data.get("failed", 0)
    cancelled = cancel_data.get("cancelled", [])
    failed_list = cancel_data.get("failed_plans", [])
    
    print(f"\n   Successfully Cancelled: {successful}")
    if cancelled:
        for plan_id in cancelled:
            print(f"      - {plan_id}")
    
    if failed > 0:
        print(f"\n   Failed to Cancel: {failed}")
        if failed_list:
            for plan_id in failed_list:
                print(f"      - {plan_id}")
    
    # Verify cancellation
    print(f"\n5. Verifying Cancellation...")
    print("-" * 70)
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans_after = system_status.get("plans", [])
    
    remaining_pending = [p for p in all_plans_after if p.get("status") == "pending"]
    
    if remaining_pending:
        print(f"   WARNING: {len(remaining_pending)} plan(s) still pending:")
        for plan in remaining_pending:
            print(f"      - {plan.get('plan_id')}")
    else:
        print(f"   [OK] All pending plans cancelled successfully")
    
    print("\n" + "=" * 70)
    print("CANCELLATION COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(cancel_all_pending_plans())
