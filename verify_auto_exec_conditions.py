"""
Verify auto-execution plan conditions match strategy requirements
"""
import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

def verify_plan_conditions(plan_id: str, conditions: Dict[str, Any], strategy_type: Optional[str], plan_type: Optional[str] = None) -> Dict[str, Any]:
    """Verify plan has required conditions, return dict with missing/warnings"""
    result = {
        "plan_id": plan_id,
        "strategy_type": strategy_type,
        "missing_critical": [],
        "missing_recommended": [],
        "warnings": [],
        "can_execute": True
    }
    
    # Special handling for micro_scalp and range_scalp
    if plan_type == "micro_scalp":
        # Micro-scalp uses 4-layer validation - conditions are optional
        result["warnings"].append("Micro-scalp plan - uses 4-layer validation system (conditions are optional)")
        return result
    
    if plan_type == "range_scalp":
        # Range scalp should have range_scalp_confluence (usually auto-added)
        if "range_scalp_confluence" not in conditions:
            result["missing_recommended"].append("range_scalp_confluence (usually auto-added by create_range_scalp_plan)")
    
    # Price conditions: Recommended but not always required
    has_price_condition = any([
        "price_near" in conditions,
        "price_above" in conditions,
        "price_below" in conditions
    ])
    
    if not has_price_condition:
        result["missing_recommended"].append("price_near, price_above, or price_below (recommended for execution control)")
    elif "price_near" in conditions and "tolerance" not in conditions:
        result["warnings"].append("price_near specified but tolerance missing (will use auto-calculated tolerance)")
    
    # Strategy-specific requirements (CRITICAL - blocks execution if missing)
    if strategy_type == "breaker_block":
        if "breaker_block" not in conditions or not conditions.get("breaker_block"):
            result["missing_critical"].append("breaker_block: true (CRITICAL - plan won't check breaker blocks without this)")
            result["can_execute"] = False
        
        # Warn if incorrect detection flags are present (these should NOT be in conditions)
        if "ob_broken" in conditions:
            result["warnings"].append("ob_broken in conditions (should NOT be included - checked dynamically by system)")
        if "price_retesting_breaker" in conditions:
            result["warnings"].append("price_retesting_breaker in conditions (should NOT be included - checked dynamically by system)")
    
    elif strategy_type == "order_block_rejection":
        if "order_block" not in conditions or not conditions.get("order_block"):
            result["missing_critical"].append("order_block: true (CRITICAL - plan won't check order blocks without this)")
            result["can_execute"] = False
        if "order_block_type" not in conditions:
            result["missing_recommended"].append("order_block_type (will default to 'auto' if missing)")
    
    elif strategy_type == "liquidity_sweep_reversal":
        if "liquidity_sweep" not in conditions or not conditions.get("liquidity_sweep"):
            result["missing_critical"].append("liquidity_sweep: true (CRITICAL - plan won't detect sweeps without this)")
            result["can_execute"] = False
        if "price_below" not in conditions and "price_above" not in conditions:
            result["missing_critical"].append("price_below or price_above (required for liquidity sweep detection)")
            result["can_execute"] = False
        if "timeframe" not in conditions and "structure_tf" not in conditions:
            result["missing_critical"].append("timeframe or structure_tf (required for liquidity sweep detection)")
            result["can_execute"] = False
    
    # Structure conditions require timeframe
    structure_conditions = ["choch_bull", "choch_bear", "rejection_wick", "liquidity_sweep"]
    has_structure = any(conditions.get(c) for c in structure_conditions)
    if has_structure:
        if "timeframe" not in conditions and "structure_tf" not in conditions:
            result["missing_critical"].append("timeframe or structure_tf (required for structure-based conditions)")
            result["can_execute"] = False
    
    return result

def verify_all_plans(include_all_statuses: bool = False):
    """Verify all plans in database (pending by default, or all if specified)"""
    db_path = Path("data/auto_execution.db")
    if not db_path.exists():
        print("Database not found")
        return
    
    status_filter = "" if include_all_statuses else "WHERE status = 'pending'"
    
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.execute(f"""
            SELECT plan_id, conditions, status 
            FROM trade_plans 
            {status_filter}
            ORDER BY created_at DESC
        """)
        
        plans = cursor.fetchall()
        critical_issues = []
        warnings = []
        
        for plan_id, conditions_json, status in plans:
            try:
                conditions = json.loads(conditions_json) if conditions_json else {}
                strategy_type = conditions.get("strategy_type")
                plan_type = conditions.get("plan_type")
                
                result = verify_plan_conditions(plan_id, conditions, strategy_type, plan_type)
                
                if result["missing_critical"]:
                    critical_issues.append(result)
                elif result["missing_recommended"] or result["warnings"]:
                    warnings.append(result)
            except Exception as e:
                print(f"Error processing plan {plan_id}: {e}")
        
        # Report results
        if critical_issues:
            print(f"\n❌ Found {len(critical_issues)} plans with CRITICAL missing conditions:\n")
            for issue in critical_issues:
                print(f"Plan: {issue['plan_id']}")
                print(f"  Strategy: {issue['strategy_type']}")
                print(f"  Status: {status}")
                print(f"  ❌ Missing Critical: {', '.join(issue['missing_critical'])}")
                if issue['missing_recommended']:
                    print(f"  ⚠️ Missing Recommended: {', '.join(issue['missing_recommended'])}")
                if issue['warnings']:
                    print(f"  ⚠️ Warnings: {', '.join(issue['warnings'])}")
                print(f"  ⚠️ Will NOT execute correctly without critical conditions")
                print()
        
        if warnings:
            print(f"\n⚠️ Found {len(warnings)} plans with warnings/recommendations:\n")
            for warning in warnings:
                print(f"Plan: {warning['plan_id']}")
                print(f"  Strategy: {warning['strategy_type']}")
                if warning['missing_recommended']:
                    print(f"  ⚠️ Missing Recommended: {', '.join(warning['missing_recommended'])}")
                if warning['warnings']:
                    print(f"  ⚠️ Warnings: {', '.join(warning['warnings'])}")
                print()
        
        if not critical_issues and not warnings:
            print("✅ All plans have required conditions")
        elif critical_issues:
            print(f"\n💡 Recommendation: Fix critical issues first - these plans will not execute correctly")

if __name__ == "__main__":
    import sys
    include_all = "--all" in sys.argv
    verify_all_plans(include_all_statuses=include_all)
