"""Quick verification script to check Phase III plans status"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from chatgpt_auto_execution_tools import tool_get_auto_system_status

async def check_status():
    result = await tool_get_auto_system_status({})
    print(result.get('summary', ''))
    data = result.get('data', {})
    
    # The API returns status nested under 'system_status'
    system_status = data.get('system_status', {})
    if not system_status and 'success' in data:
        # Try direct access if structure is different
        system_status = data
    
    print(f"Pending plans: {system_status.get('pending_plans', 0)}")
    print(f"Active plans: {system_status.get('active_plans', 0)}")
    print(f"Total plans: {system_status.get('total_plans', 0)}")
    print(f"Running: {system_status.get('running', False)}")
    
    # Also try to get all plans
    from chatgpt_auto_execution_tools import tool_get_auto_plan_status
    plans_result = await tool_get_auto_plan_status({})
    plans_data = plans_result.get('data', {})
    plans_list = plans_data.get('plans', [])
    print(f"\nAll plans count: {len(plans_list)}")
    if plans_list:
        print("Plan IDs:")
        for plan in plans_list[:10]:  # Show first 10
            plan_id = plan.get('plan_id', 'Unknown')
            symbol = plan.get('symbol', 'Unknown')
            direction = plan.get('direction', 'Unknown')
            status = plan.get('status', 'Unknown')
            print(f"  - {plan_id}: {symbol} {direction} ({status})")

if __name__ == "__main__":
    asyncio.run(check_status())

