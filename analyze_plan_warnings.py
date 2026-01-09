"""
Analyze Auto-Execution Plan Warnings

This script analyzes pending plans and identifies:
1. Stale entry prices (price moved >2x tolerance from entry)
2. Low R:R ratios (<1.5:1 minimum)
3. Plans that should be reviewed or expired
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import json
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional

# Import tolerance helper
from infra.tolerance_helper import get_price_tolerance

# Try to get current prices from MT5
try:
    from infra.mt5_service import MT5Service
    mt5_service = MT5Service()
    mt5_available = True
except Exception:
    mt5_available = False
    mt5_service = None


def get_current_price(symbol: str) -> Optional[float]:
    """Get current market price for symbol"""
    if not mt5_available or not mt5_service:
        return None
    
    try:
        quote = mt5_service.get_quote(symbol)
        if quote and hasattr(quote, 'bid') and hasattr(quote, 'ask'):
            return (quote.bid + quote.ask) / 2  # Mid price
    except Exception:
        pass
    
    return None


def calculate_rr_ratio(entry_price: float, stop_loss: float, take_profit: float) -> Optional[float]:
    """Calculate risk:reward ratio"""
    sl_distance = abs(entry_price - stop_loss)
    if sl_distance == 0:
        return None
    tp_distance = abs(take_profit - entry_price)
    return tp_distance / sl_distance


def analyze_plans(db_path: str = "data/auto_execution.db") -> Dict[str, any]:
    """Analyze all pending plans for warnings"""
    
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found: {db_path}")
        return {}
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all pending plans
    cursor.execute("""
        SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit,
               volume, status, conditions, created_at, expires_at, notes
        FROM trade_plans
        WHERE status = 'pending'
        ORDER BY created_at DESC
    """)
    
    plans = cursor.fetchall()
    conn.close()
    
    if not plans:
        print("[INFO] No pending plans found")
        return {}
    
    print("=" * 80)
    print("AUTO-EXECUTION PLAN WARNINGS ANALYSIS")
    print("=" * 80)
    print(f"\n[INFO] Analyzing {len(plans)} pending plan(s)...\n")
    
    # Results
    stale_plans = []
    low_rr_plans = []
    invalid_rr_plans = []
    healthy_plans = []
    
    # Group by symbol for price fetching
    symbols = list(set(plan['symbol'] for plan in plans))
    current_prices = {}
    
    if mt5_available:
        print("[INFO] Fetching current market prices...")
        for symbol in symbols:
            price = get_current_price(symbol)
            if price:
                current_prices[symbol] = price
                print(f"  {symbol}: {price:.2f}")
        print()
    else:
        print("[WARNING] MT5 service not available - cannot check stale prices")
        print("          Stale price analysis will be skipped\n")
    
    # Analyze each plan
    for plan in plans:
        plan_id = plan['plan_id']
        symbol = plan['symbol']
        entry_price = plan['entry_price']
        stop_loss = plan['stop_loss']
        take_profit = plan['take_profit']
        conditions = json.loads(plan['conditions']) if plan['conditions'] else {}
        
        issues = []
        
        # 1. Check R:R ratio
        rr_ratio = calculate_rr_ratio(entry_price, stop_loss, take_profit)
        if rr_ratio is not None:
            min_rr = conditions.get("min_rr_ratio", 1.5)
            
            if rr_ratio < 1.0:
                issues.append(f"INVALID R:R: {rr_ratio:.2f}:1 (TP < SL)")
                invalid_rr_plans.append({
                    'plan_id': plan_id,
                    'symbol': symbol,
                    'rr_ratio': rr_ratio,
                    'entry': entry_price,
                    'sl': stop_loss,
                    'tp': take_profit,
                    'issues': issues.copy()
                })
            elif rr_ratio < min_rr:
                issues.append(f"LOW R:R: {rr_ratio:.2f}:1 < {min_rr:.1f}:1 minimum")
                low_rr_plans.append({
                    'plan_id': plan_id,
                    'symbol': symbol,
                    'rr_ratio': rr_ratio,
                    'min_rr': min_rr,
                    'entry': entry_price,
                    'sl': stop_loss,
                    'tp': take_profit,
                    'issues': issues.copy()
                })
        
        # 2. Check stale entry price
        if symbol in current_prices:
            current_price = current_prices[symbol]
            price_distance = abs(current_price - entry_price)
            
            # Get tolerance
            tolerance = conditions.get("tolerance")
            if tolerance is None:
                tolerance = get_price_tolerance(symbol)
            
            max_stale_distance = tolerance * 2
            
            if price_distance > max_stale_distance:
                price_distance_pct = (price_distance / entry_price) * 100 if entry_price > 0 else 0
                issues.append(
                    f"STALE ENTRY: Price {price_distance:.2f} away "
                    f"({price_distance_pct:.2f}%, >{max_stale_distance:.2f} tolerance)"
                )
                stale_plans.append({
                    'plan_id': plan_id,
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'price_distance': price_distance,
                    'price_distance_pct': price_distance_pct,
                    'tolerance': tolerance,
                    'max_stale_distance': max_stale_distance,
                    'issues': issues.copy()
                })
        
        # If no issues, mark as healthy
        if not issues:
            healthy_plans.append(plan_id)
    
    # Print results
    print("=" * 80)
    print("ANALYSIS RESULTS")
    print("=" * 80)
    print()
    
    print(f"[SUMMARY]")
    print(f"  Total pending plans: {len(plans)}")
    print(f"  Healthy plans: {len(healthy_plans)}")
    print(f"  Stale entry prices: {len(stale_plans)}")
    print(f"  Low R:R ratios: {len(low_rr_plans)}")
    print(f"  Invalid R:R ratios: {len(invalid_rr_plans)}")
    print()
    
    # Detailed reports
    if stale_plans:
        print("=" * 80)
        print("STALE ENTRY PRICE WARNINGS")
        print("=" * 80)
        print()
        for plan in stale_plans:
            print(f"Plan: {plan['plan_id']}")
            print(f"  Symbol: {plan['symbol']}")
            print(f"  Entry: {plan['entry_price']:.2f}")
            print(f"  Current: {plan['current_price']:.2f}")
            print(f"  Distance: {plan['price_distance']:.2f} ({plan['price_distance_pct']:.2f}%)")
            print(f"  Tolerance: {plan['tolerance']:.2f} (max stale: {plan['max_stale_distance']:.2f})")
            print(f"  Issue: {plan['issues'][0]}")
            print()
    
    if low_rr_plans:
        print("=" * 80)
        print("LOW R:R RATIO WARNINGS")
        print("=" * 80)
        print()
        for plan in low_rr_plans:
            sl_dist = abs(plan['entry'] - plan['sl'])
            tp_dist = abs(plan['tp'] - plan['entry'])
            print(f"Plan: {plan['plan_id']}")
            print(f"  Symbol: {plan['symbol']}")
            print(f"  R:R Ratio: {plan['rr_ratio']:.2f}:1 (minimum: {plan['min_rr']:.1f}:1)")
            print(f"  Entry: {plan['entry']:.2f}")
            print(f"  Stop Loss: {plan['sl']:.2f} (distance: {sl_dist:.2f})")
            print(f"  Take Profit: {plan['tp']:.2f} (distance: {tp_dist:.2f})")
            print(f"  Issue: {plan['issues'][0]}")
            print()
    
    if invalid_rr_plans:
        print("=" * 80)
        print("INVALID R:R RATIO ERRORS")
        print("=" * 80)
        print()
        for plan in invalid_rr_plans:
            sl_dist = abs(plan['entry'] - plan['sl'])
            tp_dist = abs(plan['tp'] - plan['entry'])
            print(f"Plan: {plan['plan_id']}")
            print(f"  Symbol: {plan['symbol']}")
            print(f"  R:R Ratio: {plan['rr_ratio']:.2f}:1 (INVALID - TP < SL)")
            print(f"  Entry: {plan['entry']:.2f}")
            print(f"  Stop Loss: {plan['sl']:.2f} (distance: {sl_dist:.2f})")
            print(f"  Take Profit: {plan['tp']:.2f} (distance: {tp_dist:.2f})")
            print(f"  Issue: {plan['issues'][0]}")
            print()
    
    if healthy_plans:
        print("=" * 80)
        print("HEALTHY PLANS (No Issues)")
        print("=" * 80)
        print(f"  {len(healthy_plans)} plan(s) have no warnings")
        if len(healthy_plans) <= 10:
            for plan_id in healthy_plans:
                print(f"    - {plan_id}")
        print()
    
    # Recommendations
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    if stale_plans:
        print(f"[ACTION] {len(stale_plans)} plan(s) have stale entry prices:")
        print("  - These plans are unlikely to execute (price_near condition will fail)")
        print("  - Consider updating entry prices or cancelling these plans")
        print("  - Plans with price >2x tolerance from entry are considered stale")
        print()
    
    if low_rr_plans:
        print(f"[ACTION] {len(low_rr_plans)} plan(s) have low R:R ratios:")
        print("  - These plans are blocked from execution (R:R < minimum threshold)")
        print("  - Consider adjusting TP/SL to improve R:R ratio")
        print("  - Or cancel these plans if R:R cannot be improved")
        print()
    
    if invalid_rr_plans:
        print(f"[CRITICAL] {len(invalid_rr_plans)} plan(s) have invalid R:R ratios:")
        print("  - These plans have TP distance < SL distance (backwards R:R)")
        print("  - These should be cancelled immediately")
        print()
    
    return {
        'total': len(plans),
        'healthy': len(healthy_plans),
        'stale': len(stale_plans),
        'low_rr': len(low_rr_plans),
        'invalid_rr': len(invalid_rr_plans),
        'stale_plans': stale_plans,
        'low_rr_plans': low_rr_plans,
        'invalid_rr_plans': invalid_rr_plans
    }


if __name__ == "__main__":
    analyze_plans()

