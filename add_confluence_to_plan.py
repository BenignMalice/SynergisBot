"""
Add min_confluence filter to plan
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def add_confluence():
    """Add min_confluence to the plan"""
    bridge = get_bridge()
    
    plan_id = "chatgpt_22fff50a"
    
    print("=" * 80)
    print("ADDING CONFLUENCE FILTER TO PLAN")
    print("=" * 80)
    
    # Get current plan
    print(f"\n1. Getting Plan Details...")
    print("-" * 80)
    
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    plan = next((p for p in all_plans if p.get("plan_id") == plan_id), None)
    
    if not plan:
        print(f"   ❌ Plan {plan_id} not found")
        return
    
    symbol = plan.get("symbol", "N/A")
    direction = plan.get("direction", "N/A")
    conditions = plan.get("conditions", {})
    
    print(f"   Plan: {plan_id}")
    print(f"   Symbol: {symbol} | Direction: {direction}")
    print(f"   Current conditions: {list(conditions.keys())}")
    
    # Add min_confluence
    print(f"\n2. Adding min_confluence Filter...")
    print("-" * 80)
    
    new_conditions = conditions.copy()
    new_conditions["min_confluence"] = 70
    
    print(f"   Adding: min_confluence=70")
    
    # Update the plan
    try:
        update_result = await bridge.registry.execute("moneybot.update_auto_plan", {
            "plan_id": plan_id,
            "conditions": new_conditions,
            "notes": "Added min_confluence=70 for improved accuracy"
        })
        
        update_data = update_result.get("data", {})
        if update_data.get("success"):
            print(f"   ✅ Successfully updated")
        else:
            print(f"   ❌ Update failed: {update_data.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"   ❌ Error updating plan: {str(e)}")
    
    # Verify
    print(f"\n3. Verifying Update...")
    print("-" * 80)
    
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    plan = next((p for p in all_plans if p.get("plan_id") == plan_id), None)
    if plan:
        conditions = plan.get("conditions", {})
        if conditions.get("min_confluence") == 70:
            print(f"   ✅ min_confluence=70 confirmed")
        else:
            print(f"   ⚠️  min_confluence not found or incorrect value")
    
    print("\n" + "=" * 80)
    print("UPDATE COMPLETE")
    print("=" * 80)
    print(f"\n✅ Plan now requires:")
    print(f"   - Price proximity (price_near + tolerance)")
    print(f"   - Confluence score ≥ 70 (min_confluence)")
    print(f"   - Volume confirmation (volume_confirmation)")
    print(f"   - Structure confirmation (structure_confirmation)")

if __name__ == "__main__":
    asyncio.run(add_confluence())
