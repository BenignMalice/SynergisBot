"""
Check auto-execution plans for missing conditions based on strategy type
"""
import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any

# Strategy to condition mapping
STRATEGY_CONDITIONS = {
    "Breakout Volatility Trap": {
        "required": ["price_above", "price_below"],  # At least one
        "optional": ["volatility_check", "bb_width_expanding"],
        "description": "Breakout strategies need price_above or price_below to trigger on breakout"
    },
    "Trend Continuation Pullback": {
        "required": ["choch_bull", "choch_bear", "price_above", "price_below"],  # At least one
        "optional": ["bos_bull", "bos_bear"],
        "description": "Trend continuation needs structure confirmation (CHOCH/BOS) or price breakout"
    },
    "Liquidity Sweep Reversal": {
        "required": ["liquidity_sweep", "rejection_wick"],  # Both recommended
        "optional": ["price_near"],
        "description": "Liquidity sweep reversals need both liquidity_sweep and rejection_wick conditions"
    },
    "Order Block Rejection": {
        "required": ["order_block"],  # Must have
        "optional": ["order_block_type", "min_validation_score", "price_near"],
        "description": "Order Block strategies MUST include order_block: true condition"
    },
    "Mean Reversion Range Scalp": {
        "required": ["price_near"],  # Must have
        "optional": ["range_high", "range_low", "vwap_deviation"],
        "description": "Mean reversion needs price_near to entry, optionally with range boundaries"
    }
}

def check_plan_conditions(plan_id: str, symbol: str, strategy: str, conditions: Dict[str, Any]) -> Dict[str, Any]:
    """Check if plan has required conditions for its strategy"""
    result = {
        "plan_id": plan_id,
        "symbol": symbol,
        "strategy": strategy,
        "has_required": False,
        "missing": [],
        "warnings": [],
        "recommendations": []
    }
    
    # Get strategy requirements
    strategy_req = STRATEGY_CONDITIONS.get(strategy, {})
    if not strategy_req:
        result["warnings"].append(f"Unknown strategy type: {strategy}")
        return result
    
    required = strategy_req.get("required", [])
    optional = strategy_req.get("optional", [])
    description = strategy_req.get("description", "")
    
    # Check for required conditions
    has_any_required = False
    missing_all_required = []
    
    for req_cond in required:
        if req_cond in conditions:
            has_any_required = True
            break
        else:
            missing_all_required.append(req_cond)
    
    # Special handling for strategies that need multiple conditions
    if strategy == "Liquidity Sweep Reversal":
        has_liquidity = "liquidity_sweep" in conditions
        has_rejection = "rejection_wick" in conditions
        if not has_liquidity:
            result["missing"].append("liquidity_sweep")
        if not has_rejection:
            result["missing"].append("rejection_wick")
        result["has_required"] = has_liquidity and has_rejection
    elif strategy == "Order Block Rejection":
        has_order_block = conditions.get("order_block", False)
        if not has_order_block:
            result["missing"].append("order_block")
        result["has_required"] = has_order_block
    elif strategy == "Mean Reversion Range Scalp":
        has_price_near = "price_near" in conditions
        if not has_price_near:
            result["missing"].append("price_near")
        result["has_required"] = has_price_near
    else:
        # For breakout and trend continuation, need at least one required condition
        result["has_required"] = has_any_required
        if not has_any_required:
            result["missing"] = missing_all_required
    
    # Check for price_near (should always be present for proper execution)
    if "price_near" not in conditions:
        result["warnings"].append("Missing price_near - plan may execute at wrong price")
    
    # Check for tolerance (should be present with price_near)
    if "price_near" in conditions and "tolerance" not in conditions:
        result["warnings"].append("Missing tolerance with price_near - using default tolerance")
    
    # Check optional conditions
    has_optional = any(opt in conditions for opt in optional)
    if optional and not has_optional:
        result["recommendations"].append(f"Consider adding optional conditions: {', '.join(optional)}")
    
    # Generate recommendations
    if result["missing"]:
        result["recommendations"].append(f"Add missing conditions: {', '.join(result['missing'])}")
        result["recommendations"].append(description)
    
    return result

def check_all_plans():
    """Check all plans in the database"""
    db_path = Path("data/auto_execution.db")
    
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        return
    
    # Plan IDs to check
    plan_ids = [
        "chatgpt_7e41f030",  # Breakout Volatility Trap BUY
        "chatgpt_8b5eeb0f",   # Breakout Volatility Trap SELL
        "chatgpt_31e4333f",   # Trend Continuation Pullback BUY
        "chatgpt_ef4ba8c9",   # Trend Continuation Pullback SELL
        "chatgpt_6ffeabe0",   # Liquidity Sweep Reversal BUY
        "chatgpt_6b7eda7a",   # Liquidity Sweep Reversal SELL
        "chatgpt_7fb0e63a",   # Order Block Rejection BUY
        "chatgpt_6862f01a",   # Order Block Rejection SELL
        "chatgpt_1c1066a2",   # Mean Reversion Range Scalp BUY
        "chatgpt_1e17c45f"    # Mean Reversion Range Scalp SELL
    ]
    
    # Strategy mapping
    strategy_map = {
        "chatgpt_7e41f030": "Breakout Volatility Trap",
        "chatgpt_8b5eeb0f": "Breakout Volatility Trap",
        "chatgpt_31e4333f": "Trend Continuation Pullback",
        "chatgpt_ef4ba8c9": "Trend Continuation Pullback",
        "chatgpt_6ffeabe0": "Liquidity Sweep Reversal",
        "chatgpt_6b7eda7a": "Liquidity Sweep Reversal",
        "chatgpt_7fb0e63a": "Order Block Rejection",
        "chatgpt_6862f01a": "Order Block Rejection",
        "chatgpt_1c1066a2": "Mean Reversion Range Scalp",
        "chatgpt_1e17c45f": "Mean Reversion Range Scalp"
    }
    
    results = []
    
    try:
        with sqlite3.connect(str(db_path)) as conn:
            for plan_id in plan_ids:
                cursor = conn.execute("""
                    SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit, 
                           volume, conditions, created_at, created_by, status, expires_at, 
                           executed_at, ticket, notes
                    FROM trade_plans 
                    WHERE plan_id = ?
                """, (plan_id,))
                
                row = cursor.fetchone()
                
                if not row:
                    print(f"⚠️  Plan {plan_id} not found in database")
                    continue
                
                # Parse conditions
                conditions = json.loads(row[7]) if row[7] else {}
                strategy = strategy_map.get(plan_id, "Unknown")
                
                # Check conditions
                result = check_plan_conditions(plan_id, row[1], strategy, conditions)
                results.append({
                    "result": result,
                    "entry": row[3],
                    "direction": row[2],
                    "conditions": conditions,
                    "notes": row[14] or ""
                })
        
        # Print results
        print("=" * 80)
        print("AUTO EXECUTION PLANS - CONDITIONS CHECK")
        print("=" * 80)
        print()
        
        for i, data in enumerate(results, 1):
            result = data["result"]
            print(f"{i}. {result['strategy']} - {data['direction']} - {result['symbol']}")
            print(f"   Plan ID: {result['plan_id']}")
            print(f"   Entry: {data['entry']}")
            print()
            
            print(f"   Current Conditions: {json.dumps(data['conditions'], indent=6)}")
            print()
            
            if result["has_required"]:
                print("   [OK] Has required conditions")
            else:
                print("   [ERROR] MISSING REQUIRED CONDITIONS!")
                print(f"      Missing: {', '.join(result['missing'])}")
            
            if result["warnings"]:
                for warning in result["warnings"]:
                    print(f"   [WARNING] {warning}")
            
            if result["recommendations"]:
                for rec in result["recommendations"]:
                    print(f"   [REC] {rec}")
            
            print()
            print("-" * 80)
            print()
        
        # Summary
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print()
        
        missing_count = sum(1 for r in results if not r["result"]["has_required"])
        total_count = len(results)
        
        print(f"Total plans checked: {total_count}")
        print(f"Plans with missing conditions: {missing_count}")
        print(f"Plans with all conditions: {total_count - missing_count}")
        print()
        
        if missing_count > 0:
            print("[WARNING] PLANS WITH MISSING CONDITIONS:")
            for data in results:
                if not data["result"]["has_required"]:
                    result = data["result"]
                    print(f"   - {result['plan_id']}: {result['strategy']} - Missing: {', '.join(result['missing'])}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_all_plans()

