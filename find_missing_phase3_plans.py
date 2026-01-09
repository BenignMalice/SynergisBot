"""Find the 2 missing Phase III plans (Plan 1 and Plan 4)"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from chatgpt_auto_execution_tools import tool_get_auto_plan_status

# Plan 1: Rejection Wick - SELL @ 4493, SL 4498, TP 4478
# Plan 4: Absorption Scalp - BUY @ 4482.5, SL 4480, TP 4487.5

async def find_plans():
    result = await tool_get_auto_plan_status({})
    data = result.get('data', {})
    plans = data.get('plans', [])
    
    print("Searching for Plan 1 (Rejection Wick - SELL @ 4493)...")
    plan1_candidates = [
        p for p in plans 
        if p.get('symbol', '').upper() == 'XAUUSDC'
        and p.get('direction', '').upper() == 'SELL'
        and abs(float(p.get('entry_price', 0)) - 4493.0) < 1.0
    ]
    if plan1_candidates:
        for p in plan1_candidates:
            print(f"  FOUND: {p.get('plan_id')} - Entry: {p.get('entry_price')}, SL: {p.get('stop_loss')}, TP: {p.get('take_profit')}, Status: {p.get('status')}")
    else:
        print("  NOT FOUND")
    
    print("\nSearching for Plan 4 (Absorption Scalp - BUY @ 4482.5)...")
    plan4_candidates = [
        p for p in plans 
        if p.get('symbol', '').upper() == 'XAUUSDC'
        and p.get('direction', '').upper() == 'BUY'
        and abs(float(p.get('entry_price', 0)) - 4482.5) < 1.0
    ]
    if plan4_candidates:
        for p in plan4_candidates:
            print(f"  FOUND: {p.get('plan_id')} - Entry: {p.get('entry_price')}, SL: {p.get('stop_loss')}, TP: {p.get('take_profit')}, Status: {p.get('status')}")
    else:
        print("  NOT FOUND")
    
    print(f"\nTotal XAUUSDc plans: {len([p for p in plans if p.get('symbol', '').upper() == 'XAUUSDC'])}")

if __name__ == "__main__":
    asyncio.run(find_plans())

