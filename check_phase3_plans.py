"""Check if Phase III plans are in the system"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from chatgpt_auto_execution_tools import tool_get_auto_plan_status

# Plan IDs from our creation
phase3_plan_ids = [
    "chatgpt_16bb2e49",  # Plan 2: Order Block
    "chatgpt_feba3e1f",  # Plan 3: Post-CPI FVG
    "chatgpt_ad4993aa",  # Plan 5: Breaker-Block
    "chatgpt_ac440dfb",  # Plan 6: Session Reversion
    "chatgpt_c26c4129",  # Plan 7: Inside-Bar
    "chatgpt_f97269bf",  # Plan 8: CVD Divergence
    "chatgpt_de77a692",  # Plan 9: Premium/Discount
]

async def check_plans():
    # Get all plans
    result = await tool_get_auto_plan_status({})
    data = result.get('data', {})
    plans = data.get('plans', [])
    
    print(f"Total plans in system: {len(plans)}")
    print("\nChecking for Phase III plan IDs...")
    
    found = []
    for plan_id in phase3_plan_ids:
        plan = next((p for p in plans if p.get('plan_id') == plan_id), None)
        if plan:
            found.append(plan_id)
            symbol = plan.get('symbol', 'Unknown')
            direction = plan.get('direction', 'Unknown')
            status = plan.get('status', 'Unknown')
            entry = plan.get('entry_price', 'N/A')
            print(f"  [FOUND] {plan_id}: {symbol} {direction} @ {entry} ({status})")
        else:
            print(f"  [NOT FOUND] {plan_id}")
    
    # Also check for XAUUSDc plans created recently
    print(f"\nXAUUSDc plans (showing first 15):")
    xau_plans = [p for p in plans if p.get('symbol', '').upper() == 'XAUUSDC']
    for i, plan in enumerate(xau_plans[:15], 1):
        plan_id = plan.get('plan_id', 'Unknown')
        direction = plan.get('direction', 'Unknown')
        entry = plan.get('entry_price', 'N/A')
        status = plan.get('status', 'Unknown')
        print(f"  {i}. {plan_id}: {direction} @ {entry} ({status})")
    
    print(f"\nPhase III Plans Found: {len(found)}/{len(phase3_plan_ids)}")
    if len(found) == len(phase3_plan_ids):
        print("SUCCESS: All Phase III plans are registered!")
    else:
        print(f"WARNING: Only {len(found)}/{len(phase3_plan_ids)} Phase III plans found")

if __name__ == "__main__":
    asyncio.run(check_plans())

