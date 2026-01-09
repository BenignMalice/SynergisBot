"""
Check all auto-execution plans for contradictory conditions
"""
import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any

db_path = Path("data/auto_execution.db")

if not db_path.exists():
    print(f"ERROR: Database not found at {db_path}")
    exit(1)

def check_plan_contradictions(plan_id: str, symbol: str, direction: str, entry_price: float, conditions: Dict[str, Any]) -> List[str]:
    """Check a plan for contradictory conditions"""
    issues = []
    
    # Check 1: Both price_above AND price_below (contradictory)
    has_price_above = "price_above" in conditions and conditions["price_above"] is not None
    has_price_below = "price_below" in conditions and conditions["price_below"] is not None
    
    if has_price_above and has_price_below:
        issues.append(f"CONTRADICTION: Has both price_above ({conditions['price_above']}) AND price_below ({conditions['price_below']})")
    
    # Check 2: price_near doesn't match entry_price (or is way off)
    if "price_near" in conditions:
        price_near = conditions["price_near"]
        tolerance = conditions.get("tolerance", 0)
        
        # Calculate distance between price_near and entry_price
        distance = abs(price_near - entry_price)
        
        # For BTCUSD, tolerance is typically 100, so distance should be within reasonable range
        # For other symbols, adjust accordingly
        if symbol.upper().startswith("BTC"):
            max_reasonable_distance = 500  # 500 points for BTC
        elif symbol.upper().startswith("XAU") or symbol.upper().startswith("GOLD"):
            max_reasonable_distance = 20  # 20 dollars for gold
        else:
            max_reasonable_distance = 0.01  # 0.01 for forex
        
        if distance > max_reasonable_distance:
            issues.append(f"WARNING: price_near ({price_near}) is {distance:.2f} away from entry_price ({entry_price}) - should match entry_price")
        
        # Check if price_near conflicts with price_above/price_below
        if has_price_above:
            price_above_val = conditions["price_above"]
            if price_near < price_above_val - tolerance:
                issues.append(f"CONTRADICTION: price_near ({price_near}) is below price_above ({price_above_val}) - price cannot be both above {price_above_val} AND near {price_near}")
        
        if has_price_below:
            price_below_val = conditions["price_below"]
            if price_near > price_below_val + tolerance:
                issues.append(f"CONTRADICTION: price_near ({price_near}) is above price_below ({price_below_val}) - price cannot be both below {price_below_val} AND near {price_near}")
    
    # Check 3: price_above but direction is SELL (should be BUY)
    if has_price_above and direction.upper() == "SELL":
        issues.append(f"WARNING: Has price_above but direction is SELL - typically SELL plans use price_below")
    
    # Check 4: price_below but direction is BUY (should be SELL)
    if has_price_below and direction.upper() == "BUY":
        issues.append(f"WARNING: Has price_below but direction is BUY - typically BUY plans use price_above")
    
    # Check 5: price_above value doesn't match entry_price (for BUY plans)
    if has_price_above and direction.upper() == "BUY":
        price_above_val = conditions["price_above"]
        if abs(price_above_val - entry_price) > 100:  # Allow some tolerance
            issues.append(f"WARNING: price_above ({price_above_val}) doesn't match entry_price ({entry_price}) for BUY plan")
    
    # Check 6: price_below value doesn't match entry_price (for SELL plans)
    if has_price_below and direction.upper() == "SELL":
        price_below_val = conditions["price_below"]
        if abs(price_below_val - entry_price) > 100:  # Allow some tolerance
            issues.append(f"WARNING: price_below ({price_below_val}) doesn't match entry_price ({entry_price}) for SELL plan")
    
    return issues

conn = sqlite3.connect(str(db_path))
cursor = conn.execute("""
    SELECT plan_id, symbol, direction, entry_price, conditions, status, created_at, notes
    FROM trade_plans 
    WHERE status = 'pending'
    ORDER BY created_at DESC
""")

plans = cursor.fetchall()

print("=" * 80)
print("AUTO-EXECUTION PLANS - CONTRADICTION CHECK")
print("=" * 80)
print()

total_plans = len(plans)
plans_with_issues = 0
total_issues = 0

for row in plans:
    plan_id, symbol, direction, entry_price, conditions_json, status, created_at, notes = row
    
    if not conditions_json:
        continue
    
    try:
        conditions = json.loads(conditions_json) if conditions_json else {}
    except:
        print(f"ERROR: Could not parse conditions for plan {plan_id}")
        continue
    
    issues = check_plan_contradictions(plan_id, symbol, direction, entry_price, conditions)
    
    if issues:
        plans_with_issues += 1
        total_issues += len(issues)
        
        print(f"Plan ID: {plan_id}")
        print(f"Symbol: {symbol} | Direction: {direction} | Entry: {entry_price}")
        print(f"Status: {status} | Created: {created_at[:19]}")
        print(f"Notes: {notes[:100] if notes else 'None'}")
        print()
        print("Conditions:")
        print(json.dumps(conditions, indent=2))
        print()
        print("ISSUES FOUND:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print()
        print("-" * 80)
        print()

if plans_with_issues == 0:
    print(f"[OK] No contradictions found in {total_plans} pending plans!")
else:
    print(f"[WARNING] Found {total_issues} issue(s) in {plans_with_issues} plan(s) out of {total_plans} total pending plans")
    print()
    print("RECOMMENDATION: Fix these plans to ensure they can execute properly.")

conn.close()

