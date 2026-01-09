"""Verify that all conditions in plans are checked by the auto-execution system"""
import asyncio
import sys
import json
import codecs
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

from chatgpt_auto_execution_tools import tool_get_auto_plan_status

# All conditions that ARE checked by the system (from auto_execution_system.py _check_conditions method)
CHECKED_CONDITIONS = {
    # Price conditions
    "price_near": True,
    "price_above": True,
    "price_below": True,
    "tolerance": True,
    
    # Structure conditions
    "choch_bull": True,
    "choch_bear": True,
    "bos_bull": True,
    "bos_bear": True,
    "structure_confirmation": True,
    "structure_timeframe": True,
    "structure_tf": True,
    "timeframe": True,
    "tf": True,
    
    # Order block conditions
    "order_block": True,
    "order_block_type": True,
    "min_validation_score": True,
    
    # Breaker block conditions
    "breaker_block": True,
    
    # FVG conditions
    "fvg_bull": True,
    "fvg_bear": True,
    "fvg_filled_pct": True,
    
    # MSS conditions
    "mss_bull": True,
    "mss_bear": True,
    "pullback_to_mss": True,
    
    # Mitigation block conditions
    "mitigation_block_bull": True,
    "mitigation_block_bear": True,
    "structure_broken": True,
    
    # Liquidity conditions
    "liquidity_sweep": True,
    "liquidity_grab_bull": True,
    "liquidity_grab_bear": True,
    "rejection_detected": True,
    "rejection_wick": True,
    "min_wick_ratio": True,
    
    # Order flow conditions (BTC)
    "delta_positive": True,
    "delta_negative": True,
    "cvd_rising": True,
    "cvd_falling": True,
    "cvd_div_bear": True,
    "cvd_div_bull": True,
    "cvd_divergence_bear": True,
    "cvd_divergence_bull": True,
    "cvd_divergence_bearish": True,
    "cvd_divergence_bullish": True,
    "delta_divergence_bull": True,
    "delta_divergence_bear": True,
    "delta_divergence_bullish": True,
    "delta_divergence_bearish": True,
    "avoid_absorption_zones": True,
    "absorption_zone_detected": True,
    
    # VWAP conditions
    "vwap_deviation": True,
    "vwap_deviation_threshold": True,
    "vwap_deviation_direction": True,
    
    # EMA conditions
    "ema_slope": True,
    "ema_period": True,
    "ema_timeframe": True,
    "ema_slope_direction": True,
    "min_ema_slope_pct": True,
    
    # Bollinger Bands conditions
    "bb_squeeze": True,
    "bb_squeeze_threshold": True,
    "bb_expansion": True,
    "bb_expansion_threshold": True,
    "bb_expansion_check_both": True,
    
    # Pattern conditions
    "inside_bar": True,
    "equal_highs": True,
    "equal_lows": True,
    "equal_tolerance_pct": True,
    
    # RSI conditions
    "rsi_div_bull": True,
    "rsi_div_bear": True,
    
    # Volatility conditions
    "volatility_state": True,
    "atr_5m_threshold": True,
    "vix_threshold": True,
    "bb_width_threshold": True,
    "volatility_trigger_rule": True,
    "min_volatility": True,
    "max_volatility": True,
    "atr_based_stops": True,
    
    # Session conditions
    "require_active_session": True,
    "session": True,
    "london_session_active": True,
    "sweep_detected": True,
    "reversal_structure": True,
    "asian_session_high": True,
    "asian_session_low": True,
    "kill_zone_active": True,
    "volatility_spike": True,
    
    # Time conditions
    "time_after": True,
    "time_before": True,
    
    # Confluence conditions
    "range_scalp_confluence": True,
    "min_confluence": True,
    
    # Plan type conditions
    "plan_type": True,
    "strategy_type": True,
    "strategy": True,
    
    # Premium/Discount conditions
    "price_in_discount": True,
    "price_in_premium": True,
    
    # Special execution flags
    "execute_immediately": True,
    
    # Risk/R:R conditions
    "min_rr_ratio": True,
    
    # Confidence conditions
    "min_confidence": True,
}

async def verify_coverage():
    print("=" * 80)
    print("CONDITION COVERAGE VERIFICATION")
    print("=" * 80)
    
    # Get all plans
    print("\n[1] RETRIEVING ALL PLANS...")
    plans_result = await tool_get_auto_plan_status({})
    plans_data = plans_result.get('data', {})
    all_plans = plans_data.get('plans', [])
    
    print(f"  Total plans: {len(all_plans)}")
    
    # Collect all unique conditions from all plans
    all_conditions_found = set()
    plans_by_condition = {}
    
    for plan in all_plans:
        plan_id = plan.get('plan_id', 'unknown')
        symbol = plan.get('symbol', 'unknown')
        conditions = plan.get('conditions', {})
        
        if not conditions:
            continue
        
        # Parse conditions (may be string or dict)
        if isinstance(conditions, str):
            try:
                conditions = json.loads(conditions)
            except:
                continue
        
        # Track all conditions found
        for cond_key in conditions.keys():
            all_conditions_found.add(cond_key)
            if cond_key not in plans_by_condition:
                plans_by_condition[cond_key] = []
            plans_by_condition[cond_key].append({
                'plan_id': plan_id,
                'symbol': symbol
            })
    
    print(f"  Unique conditions found: {len(all_conditions_found)}")
    
    # Check which conditions are checked vs not checked
    print("\n[2] ANALYZING CONDITION COVERAGE...")
    print("=" * 80)
    
    checked_conditions = []
    unchecked_conditions = []
    metadata_conditions = []  # Conditions that are metadata, not actual checks
    
    for cond in sorted(all_conditions_found):
        if cond in CHECKED_CONDITIONS:
            checked_conditions.append(cond)
        elif cond.startswith('_') or cond in ['notes', 'created_at', 'expires_at']:
            metadata_conditions.append(cond)
        else:
            unchecked_conditions.append(cond)
    
    print(f"\n[CHECKED] CONDITIONS ({len(checked_conditions)}):")
    for cond in checked_conditions:
        plan_count = len(plans_by_condition.get(cond, []))
        print(f"  - {cond} (used in {plan_count} plan(s))")
    
    if metadata_conditions:
        print(f"\n[METADATA] CONDITIONS ({len(metadata_conditions)}):")
        for cond in metadata_conditions:
            print(f"  - {cond} (not a condition, just metadata)")
    
    if unchecked_conditions:
        print(f"\n[WARNING] UNCHECKED CONDITIONS ({len(unchecked_conditions)}):")
        for cond in unchecked_conditions:
            plan_count = len(plans_by_condition.get(cond, []))
            plan_list = plans_by_condition.get(cond, [])[:3]  # Show first 3
            plan_str = ", ".join([f"{p['symbol']} ({p['plan_id'][:8]}...)" for p in plan_list])
            if plan_count > 3:
                plan_str += f" ... and {plan_count - 3} more"
            print(f"  - {cond} (used in {plan_count} plan(s): {plan_str})")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total unique conditions found: {len(all_conditions_found)}")
    print(f"[CHECKED] Checked by system: {len(checked_conditions)} ({len(checked_conditions)/len(all_conditions_found)*100:.1f}%)")
    print(f"[METADATA] Metadata (not conditions): {len(metadata_conditions)}")
    print(f"[WARNING] Not checked: {len(unchecked_conditions)}")
    
    if unchecked_conditions:
        print("\n[WARNING] Some conditions are set in plans but NOT checked by the system!")
        print("   These conditions will be IGNORED during execution.")
        print("   Plans with these conditions may execute even if the condition is not met.")
    else:
        print("\n[SUCCESS] All conditions found in plans are checked by the system!")
        print("   The system will properly evaluate all conditions before executing trades.")
    
    # Show example plans with unchecked conditions
    if unchecked_conditions:
        print("\n[3] EXAMPLE PLANS WITH UNCHECKED CONDITIONS:")
        print("=" * 80)
        for cond in unchecked_conditions[:5]:  # Show first 5
            plans = plans_by_condition.get(cond, [])[:2]  # Show first 2 plans
            print(f"\n  Condition: {cond}")
            for plan in plans:
                print(f"    - Plan: {plan['plan_id']} ({plan['symbol']})")
                # Get full plan details
                full_plan = next((p for p in all_plans if p.get('plan_id') == plan['plan_id']), None)
                if full_plan:
                    conditions = full_plan.get('conditions', {})
                    if isinstance(conditions, str):
                        try:
                            conditions = json.loads(conditions)
                        except:
                            conditions = {}
                    cond_value = conditions.get(cond, 'N/A')
                    print(f"      Value: {cond_value}")

if __name__ == "__main__":
    asyncio.run(verify_coverage())

