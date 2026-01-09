"""
Verify status of specific plans
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def verify_plans():
    """Check if plans exist and their status"""
    bridge = get_bridge()
    
    plan_ids = [
        "chatgpt_ae88beb4",
        "chatgpt_206eb10b",
        "chatgpt_6dd2c794",
        "chatgpt_e1e32ad7",
        "chatgpt_8afeafa3",
        "chatgpt_eca9feda",
        "chatgpt_ace396c9",
    ]
    
    print("Checking plan status...")
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    print(f"\nTotal plans in system: {len(all_plans)}")
    print(f"\nChecking specific plans:")
    
    for plan_id in plan_ids:
        plan = next((p for p in all_plans if p.get("plan_id") == plan_id), None)
        if plan:
            print(f"   ✅ {plan_id}: {plan.get('status')} - {plan.get('symbol')} {plan.get('direction')}")
        else:
            print(f"   ❌ {plan_id}: NOT FOUND (already cancelled or doesn't exist)")

if __name__ == "__main__":
    asyncio.run(verify_plans())
