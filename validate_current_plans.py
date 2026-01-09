"""
Validate current auto-execution plans to ensure they will be monitored and triggered correctly
"""
import asyncio
from cursor_trading_bridge import get_bridge
from datetime import datetime, timezone
from infra.session_helpers import SessionHelpers

async def validate_plans():
    """Validate all current auto-execution plans"""
    bridge = get_bridge()
    
    print("=" * 80)
    print("VALIDATING CURRENT AUTO-EXECUTION PLANS")
    print("=" * 80)
    print()
    
    # Get all plans
    try:
        result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
        data = result.get("data", {})
        system_status = data.get("system_status", {})
        plans = system_status.get("plans", [])
        
        print(f"Found {len(plans)} plan(s) in system")
        print()
        
        if not plans:
            print("No plans found in system.")
            return
        
        # Get current session
        current_session = SessionHelpers.get_current_session()
        print(f"Current Session: {current_session}")
        print()
        
        # Strategies allowed in Asian session
        asian_allowed_strategies = [
            "range_scalp", "range_fade", "mean_reversion",
            "fvg_retracement", "premium_discount_array",
            "order_block_rejection"
        ]
        
        valid_plans = []
        invalid_plans = []
        
        for i, plan in enumerate(plans, 1):
            plan_id = plan.get("plan_id", "unknown")
            symbol = plan.get("symbol", "unknown")
            direction = plan.get("direction", "unknown")
            status = plan.get("status", "unknown")
            # Try to get strategy_type from multiple sources (check both strategy_type and plan_type for compatibility)
            conditions = plan.get("conditions", {})
            strategy_type = (
                plan.get("strategy_type") or 
                conditions.get("strategy_type") or 
                conditions.get("plan_type") or 
                "unknown"
            )
            
            # Debug: Print full plan structure for first plan
            if i == 1:
                print(f"   [DEBUG] Full plan keys: {list(plan.keys())}")
                print(f"   [DEBUG] Conditions keys: {list(conditions.keys()) if conditions else 'None'}")
            
            print(f"[{i}/{len(plans)}] Plan {plan_id}")
            print(f"   Symbol: {symbol}")
            print(f"   Direction: {direction}")
            print(f"   Status: {status}")
            print(f"   Strategy: {strategy_type}")
            
            issues = []
            warnings = []
            
            # Check 1: Status
            if status != "pending":
                warnings.append(f"Status is '{status}' (not pending)")
            
            # Check 2: Session blocking (if require_active_session is True)
            require_active_session = conditions.get("require_active_session")
            if require_active_session is None:
                # Default True for XAU
                if "XAU" in symbol.upper():
                    require_active_session = True
                    warnings.append("require_active_session defaults to True for XAU")
            
            if require_active_session:
                if current_session == "ASIAN":
                    strategy_type_lower = str(strategy_type).lower() if strategy_type else ""
                    is_asian_appropriate = any(
                        allowed in strategy_type_lower 
                        for allowed in asian_allowed_strategies
                    )
                    
                    # If strategy_type is unknown/not set, check if we can infer from conditions
                    if strategy_type == "unknown" or not strategy_type:
                        # Check for range/mean reversion indicators in conditions
                        has_range_indicators = any([
                            "range_scalp" in str(conditions).lower(),
                            "range_fade" in str(conditions).lower(),
                            "mean_reversion" in str(conditions).lower(),
                            "fvg" in str(conditions).lower(),
                            conditions.get("range_scalp"),
                            conditions.get("range_fade"),
                            conditions.get("mean_reversion")
                        ])
                        
                        if has_range_indicators:
                            warnings.append(
                                "Strategy type unknown but has range/mean reversion indicators - "
                                "may be allowed if conditions match Asian-appropriate strategy"
                            )
                        else:
                            issues.append(
                                f"BLOCKED: Plan in Asian session but strategy type is unknown/not set. "
                                f"Allowed strategies: {', '.join(asian_allowed_strategies)}. "
                                f"To allow: Set strategy_type to one of the allowed strategies or set require_active_session: false"
                            )
                    elif not is_asian_appropriate:
                        issues.append(
                            f"BLOCKED: Plan in Asian session but strategy '{strategy_type}' is not appropriate. "
                            f"Allowed strategies: {', '.join(asian_allowed_strategies)}"
                        )
                    else:
                        print(f"   [OK] Strategy '{strategy_type}' is allowed in Asian session")
            
            # Check 3: R:R Ratio
            entry = plan.get("entry_price")
            stop_loss = plan.get("stop_loss")
            take_profit = plan.get("take_profit")
            
            if entry and stop_loss and take_profit:
                sl_distance = abs(entry - stop_loss)
                tp_distance = abs(take_profit - entry)
                
                if sl_distance > 0:
                    rr_ratio = tp_distance / sl_distance
                    min_rr = conditions.get("min_rr_ratio", 1.5)
                    
                    if rr_ratio < min_rr:
                        issues.append(
                            f"INVALID R:R: {rr_ratio:.2f}:1 (minimum required: {min_rr:.1f}:1)"
                        )
                    elif tp_distance < sl_distance:
                        issues.append(
                            f"BACKWARDS R:R: TP distance ({tp_distance:.2f}) < SL distance ({sl_distance:.2f}) - REJECTED"
                        )
                    else:
                        print(f"   [OK] R:R = {rr_ratio:.2f}:1 (meets minimum {min_rr:.1f}:1)")
                else:
                    warnings.append("SL distance is 0 - cannot calculate R:R")
            else:
                warnings.append("Missing entry/SL/TP prices")
            
            # Check 4: Order flow conditions (for BTC)
            if "BTC" in symbol.upper():
                has_order_flow = any([
                    conditions.get("delta_positive"),
                    conditions.get("delta_negative"),
                    conditions.get("cvd_rising"),
                    conditions.get("cvd_falling"),
                    conditions.get("avoid_absorption_zones")
                ])
                
                if has_order_flow:
                    print(f"   [INFO] Plan has order flow conditions (will be checked by auto-execution system)")
                    # Note: We can't verify if service is running from here, but auto-execution system will check
            
            # Check 5: Required conditions
            if not conditions:
                warnings.append("No conditions specified")
            else:
                # Check for price condition
                has_price_condition = any([
                    "price_near" in conditions,
                    "price_above" in conditions,
                    "price_below" in conditions
                ])
                
                if not has_price_condition:
                    warnings.append("No price condition specified (price_near, price_above, or price_below)")
            
            # Check 6: Strategy type consistency
            if strategy_type:
                # Check if strategy-specific conditions match
                if strategy_type == "order_block_rejection":
                    if not conditions.get("order_block"):
                        warnings.append("Strategy type is 'order_block_rejection' but 'order_block' condition not set")
            
            # Summary
            if issues:
                print(f"   [ISSUES]:")
                for issue in issues:
                    print(f"      ❌ {issue}")
                invalid_plans.append({
                    "plan_id": plan_id,
                    "symbol": symbol,
                    "issues": issues,
                    "warnings": warnings
                })
            else:
                if warnings:
                    print(f"   [WARNINGS]:")
                    for warning in warnings:
                        print(f"      ⚠️ {warning}")
                else:
                    print(f"   [OK] Plan appears valid")
                valid_plans.append({
                    "plan_id": plan_id,
                    "symbol": symbol,
                    "warnings": warnings
                })
            
            print()
        
        # Summary
        print("=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        print()
        print(f"Total Plans: {len(plans)}")
        print(f"Valid Plans: {len(valid_plans)}")
        print(f"Invalid Plans: {len(invalid_plans)}")
        print()
        
        if valid_plans:
            print("✅ Valid Plans:")
            for plan in valid_plans:
                print(f"   - {plan['plan_id']} ({plan['symbol']})")
                if plan.get('warnings'):
                    for warning in plan['warnings']:
                        print(f"     ⚠️ {warning}")
        
        if invalid_plans:
            print()
            print("❌ Invalid Plans (will NOT execute):")
            for plan in invalid_plans:
                print(f"   - {plan['plan_id']} ({plan['symbol']})")
                for issue in plan['issues']:
                    print(f"     ❌ {issue}")
        
        print()
        print("=" * 80)
        print("NOTES")
        print("=" * 80)
        print()
        print("1. Order flow conditions will be checked by auto-execution system (runs in main process)")
        print("2. Session blocking is strategy-aware (range/mean reversion allowed in Asian session)")
        print("3. R:R validation is automatic (minimum 1.5:1, backwards R:R rejected)")
        print("4. Plans with issues will be blocked from execution")
        print("5. Plans with warnings may still execute but should be reviewed")
        print()
        
    except Exception as e:
        print(f"Error validating plans: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(validate_plans())
