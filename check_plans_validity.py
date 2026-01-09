"""
Check validity of two auto-execution plans
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime

def check_plan(plan_id: str):
    """Check a single plan's validity"""
    db_path = Path("data/auto_execution.db")
    
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        return None
    
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute("""
                SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit, 
                       volume, conditions, created_at, created_by, status, expires_at, 
                       executed_at, ticket, notes
                FROM trade_plans 
                WHERE plan_id = ?
            """, (plan_id,))
            
            row = cursor.fetchone()
            
            if not row:
                print(f"[ERROR] Plan {plan_id} not found in database")
                return None
            
            # Parse data
            plan_data = {
                "plan_id": row[0],
                "symbol": row[1],
                "direction": row[2],
                "entry_price": row[3],
                "stop_loss": row[4],
                "take_profit": row[5],
                "volume": row[6],
                "conditions": json.loads(row[7]) if row[7] else {},
                "created_at": row[8],
                "created_by": row[9],
                "status": row[10],
                "expires_at": row[11],
                "executed_at": row[12],
                "ticket": row[13],
                "notes": row[14] or ""
            }
            
            return plan_data
            
    except Exception as e:
        print(f"ERROR reading plan {plan_id}: {e}")
        return None

def analyze_plan(plan_data):
    """Analyze plan validity and conditions"""
    if not plan_data:
        return
    
    print("=" * 80)
    print(f"PLAN: {plan_data['plan_id']}")
    print("=" * 80)
    print(f"Symbol: {plan_data['symbol']}")
    print(f"Direction: {plan_data['direction']}")
    print(f"Status: {plan_data['status']}")
    print(f"Entry: ${plan_data['entry_price']:,.2f}")
    print(f"Stop Loss: ${plan_data['stop_loss']:,.2f}")
    print(f"Take Profit: ${plan_data['take_profit']:,.2f}")
    print(f"Risk/Reward: {abs(plan_data['entry_price'] - plan_data['stop_loss']):,.2f} / {abs(plan_data['take_profit'] - plan_data['entry_price']):,.2f} = {abs(plan_data['take_profit'] - plan_data['entry_price']) / abs(plan_data['entry_price'] - plan_data['stop_loss']):.2f}:1")
    print()
    
    conditions = plan_data['conditions']
    print("CONDITIONS:")
    print(json.dumps(conditions, indent=2))
    print()
    
    # Validation checks
    issues = []
    warnings = []
    validations = []
    
    # Check 1: Price conditions consistency
    entry = plan_data['entry_price']
    direction = plan_data['direction']
    
    price_above = conditions.get("price_above")
    price_below = conditions.get("price_below")
    price_near = conditions.get("price_near")
    tolerance = conditions.get("tolerance", 100)
    
    if price_above is not None:
        if direction == "SELL":
            issues.append(f"[ERROR] BUY plan has price_above={price_above} but direction is {direction}")
        else:
            validations.append(f"[OK] price_above={price_above} matches BUY direction")
            if abs(price_above - entry) > tolerance:
                warnings.append(f"[WARN] price_above ({price_above}) differs from entry ({entry}) by {abs(price_above - entry):.2f}")
    
    if price_below is not None:
        if direction == "BUY":
            issues.append(f"[ERROR] BUY plan has price_below={price_below} but direction is {direction}")
        else:
            validations.append(f"[OK] price_below={price_below} matches SELL direction")
            if abs(price_below - entry) > tolerance:
                warnings.append(f"[WARN] price_below ({price_below}) differs from entry ({entry}) by {abs(price_below - entry):.2f}")
    
    if price_near is not None:
        if abs(price_near - entry) > tolerance:
            warnings.append(f"[WARN] price_near ({price_near}) differs from entry ({entry}) by {abs(price_near - entry):.2f}")
        else:
            validations.append(f"[OK] price_near={price_near} matches entry price")
    
    # Check 2: BB Expansion condition
    if conditions.get("bb_expansion"):
        timeframe = conditions.get("timeframe", "M15")
        validations.append(f"[OK] bb_expansion=true with timeframe={timeframe}")
        
        # Check if price_above is set for BUY
        if direction == "BUY" and price_above is None:
            issues.append("[ERROR] bb_expansion BUY plan missing price_above condition")
        elif direction == "BUY" and price_above is not None:
            validations.append(f"[OK] BUY with bb_expansion has price_above={price_above}")
    
    # Check 3: Range Scalp conditions
    if conditions.get("range_scalp_confluence") is not None:
        min_confluence = conditions.get("range_scalp_confluence")
        validations.append(f"[OK] range_scalp_confluence={min_confluence}")
        
        if min_confluence < 80:
            warnings.append(f"[WARN] range_scalp_confluence={min_confluence} is below recommended 80")
        
        if not conditions.get("structure_confirmation"):
            warnings.append("[WARN] range_scalp plan missing structure_confirmation=true")
        else:
            validations.append("[OK] structure_confirmation=true")
    
    # Check 4: Strategy type consistency
    strategy_type = conditions.get("strategy_type")
    if strategy_type:
        validations.append(f"[OK] strategy_type={strategy_type}")
        
        # Check if conditions match strategy
        if "breakout" in strategy_type.lower() or "volatility" in strategy_type.lower():
            if not conditions.get("bb_expansion") and not conditions.get("bb_squeeze"):
                warnings.append(f"[WARN] Strategy {strategy_type} suggests BB conditions but none found")
    
    # Check 5: Timeframe
    timeframe = conditions.get("timeframe")
    if timeframe:
        validations.append(f"[OK] timeframe={timeframe}")
    else:
        warnings.append("[WARN] No timeframe specified in conditions")
    
    # Check 6: Plan type
    plan_type = conditions.get("plan_type")
    if plan_type:
        validations.append(f"[OK] plan_type={plan_type}")
    
    # Print results
    print("VALIDATION RESULTS:")
    print("-" * 80)
    
    if validations:
        print("\n[OK] VALID:")
        for v in validations:
            print(f"  {v}")
    
    if warnings:
        print("\n[WARN] WARNINGS:")
        for w in warnings:
            print(f"  {w}")
    
    if issues:
        print("\n[ERROR] ISSUES:")
        for i in issues:
            print(f"  {i}")
    
    # Overall verdict
    print()
    print("-" * 80)
    if issues:
        print("[ERROR] PLAN HAS ISSUES - May not execute correctly")
    elif warnings:
        print("[WARN] PLAN HAS WARNINGS - Should work but may need adjustments")
    else:
        print("[OK] PLAN LOOKS VALID")
    print()
    
    return {
        "valid": len(issues) == 0,
        "warnings": len(warnings),
        "issues": len(issues)
    }

# Main
if __name__ == "__main__":
    plan_ids = ["chatgpt_8071ed17", "chatgpt_f5fb620f"]
    
    print("\n" + "=" * 80)
    print("AUTO-EXECUTION PLAN VALIDATION")
    print("=" * 80)
    print()
    
    results = []
    for plan_id in plan_ids:
        plan_data = check_plan(plan_id)
        if plan_data:
            result = analyze_plan(plan_data)
            results.append((plan_id, result))
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for plan_id, result in results:
        if result:
            status = "[OK] VALID" if result['valid'] else "[ERROR] HAS ISSUES"
            print(f"{plan_id}: {status} ({result['warnings']} warnings, {result['issues']} issues)")

