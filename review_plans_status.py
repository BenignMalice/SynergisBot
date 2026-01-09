"""
Review and verify plan status and system functionality
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

def find_database():
    """Find the trade plans database"""
    possible_paths = [
        "data/trade_plans.sqlite",
        "data/trade_plans.db",
        "trade_plans.sqlite",
        "trade_plans.db"
    ]
    
    for path in possible_paths:
        if Path(path).exists():
            return path
    return None

def get_plan_details(db_path: str, plan_id: str) -> Optional[Dict]:
    """Get plan details from database"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit,
                   volume, conditions, status, created_at, expires_at, executed_at,
                   ticket, notes, zone_entry_tracked, zone_entry_time
            FROM trade_plans
            WHERE plan_id = ?
        """, (plan_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            conditions = json.loads(row['conditions']) if row['conditions'] else {}
            return {
                'plan_id': row['plan_id'],
                'symbol': row['symbol'],
                'direction': row['direction'],
                'entry_price': row['entry_price'],
                'stop_loss': row['stop_loss'],
                'take_profit': row['take_profit'],
                'volume': row['volume'],
                'conditions': conditions,
                'status': row['status'],
                'created_at': row['created_at'],
                'expires_at': row['expires_at'],
                'executed_at': row['executed_at'],
                'ticket': row['ticket'],
                'notes': row['notes'],
                'zone_entry_tracked': row['zone_entry_tracked'],
                'zone_entry_time': row['zone_entry_time']
            }
    except Exception as e:
        print(f"Error getting plan {plan_id}: {e}")
    return None

def analyze_plan(plan: Dict) -> Dict:
    """Analyze a plan for issues"""
    issues = []
    warnings = []
    info = []
    
    # Check SL/TP relationship
    if plan['direction'] == 'BUY':
        if plan['stop_loss'] >= plan['entry_price']:
            issues.append(f"Invalid SL: {plan['stop_loss']} >= Entry: {plan['entry_price']}")
        if plan['take_profit'] <= plan['entry_price']:
            issues.append(f"Invalid TP: {plan['take_profit']} <= Entry: {plan['entry_price']}")
        sl_distance = plan['entry_price'] - plan['stop_loss']
        tp_distance = plan['take_profit'] - plan['entry_price']
    else:  # SELL
        if plan['stop_loss'] <= plan['entry_price']:
            issues.append(f"Invalid SL: {plan['stop_loss']} <= Entry: {plan['entry_price']}")
        if plan['take_profit'] >= plan['entry_price']:
            issues.append(f"Invalid TP: {plan['take_profit']} >= Entry: {plan['entry_price']}")
        sl_distance = plan['stop_loss'] - plan['entry_price']
        tp_distance = plan['entry_price'] - plan['take_profit']
    
    # Check R:R ratio
    if sl_distance > 0:
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
        info.append(f"R:R Ratio: {rr_ratio:.2f}")
        if rr_ratio < 1.0:
            warnings.append(f"Poor R:R ratio: {rr_ratio:.2f} < 1.0")
    
    # Check order flow conditions
    conditions = plan['conditions']
    order_flow_conditions = [
        "delta_positive", "delta_negative",
        "cvd_rising", "cvd_falling",
        "cvd_div_bear", "cvd_div_bull",
        "delta_divergence_bull", "delta_divergence_bear",
        "avoid_absorption_zones", "absorption_zone_detected"
    ]
    
    has_order_flow = any(conditions.get(cond) for cond in order_flow_conditions)
    if has_order_flow:
        of_conds = [k for k in conditions.keys() if k in order_flow_conditions]
        info.append(f"Order Flow Conditions: {', '.join(of_conds)}")
    
    # Check price_near condition
    if 'price_near' in conditions:
        tolerance = conditions.get('tolerance', 50)
        info.append(f"Price Near: {conditions['price_near']} +/- {tolerance}")
    
    # Check expiry
    if plan['expires_at']:
        try:
            expires = datetime.fromisoformat(plan['expires_at'].replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            if expires < now:
                issues.append(f"Plan expired: {expires}")
            else:
                hours_left = (expires - now).total_seconds() / 3600
                info.append(f"Expires in: {hours_left:.1f} hours")
        except:
            pass
    
    # Check status
    if plan['status'] != 'pending':
        info.append(f"Status: {plan['status']}")
        if plan['status'] == 'executed' and plan['ticket']:
            info.append(f"Executed with ticket: {plan['ticket']}")
    
    return {
        'issues': issues,
        'warnings': warnings,
        'info': info
    }

def check_order_flow_service():
    """Check if order flow service is accessible"""
    try:
        from desktop_agent import registry
        
        if hasattr(registry, 'order_flow_service'):
            service = registry.order_flow_service
            if service:
                if hasattr(service, 'running') and service.running:
                    symbols = getattr(service, 'symbols', 'unknown')
                    return {
                        'available': True,
                        'running': True,
                        'symbols': symbols,
                        'status': 'OK'
                    }
                else:
                    return {
                        'available': True,
                        'running': False,
                        'status': 'Service found but not running'
                    }
            else:
                return {
                    'available': False,
                    'status': 'Service is None'
                }
        else:
            return {
                'available': False,
                'status': 'Service not in registry'
            }
    except ImportError:
        return {
            'available': False,
            'status': 'Cannot import desktop_agent.registry'
        }
    except Exception as e:
        return {
            'available': False,
            'status': f'Error: {e}'
        }

def main():
    """Main review function"""
    print("\n" + "="*70)
    print("PLAN REVIEW AND SYSTEM STATUS CHECK")
    print("="*70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Find database
    db_path = find_database()
    if not db_path:
        print("[ERROR] Could not find trade plans database")
        return
    
    print(f"[INFO] Using database: {db_path}\n")
    
    # Plans to review
    plan_ids = [
        "chatgpt_e71be723",  # Delta Absorption
        "chatgpt_8da1d1e5",  # CVD Acceleration
        "chatgpt_631f9739",  # Delta Divergence
        "chatgpt_56d943d9",  # Absorption Reversal Scalp
        "chatgpt_72043641",  # Liquidity Imbalance Rebalance
        "chatgpt_9ad9c84f",  # Breaker + Delta Continuation
        "micro_scalp_a6ec41c2"  # VWAP Reversion Micro-Scalp
    ]
    
    # Check order flow service
    print("="*70)
    print("ORDER FLOW SERVICE STATUS")
    print("="*70)
    of_service = check_order_flow_service()
    if of_service['available'] and of_service.get('running'):
        print(f"[PASS] Order Flow Service: RUNNING")
        print(f"       Symbols: {of_service.get('symbols', 'unknown')}")
    else:
        print(f"[FAIL] Order Flow Service: {of_service['status']}")
        print("       Order flow plans will NOT execute without service")
    print()
    
    # Review each plan
    print("="*70)
    print("PLAN REVIEW")
    print("="*70)
    
    for plan_id in plan_ids:
        print(f"\n--- {plan_id} ---")
        plan = get_plan_details(db_path, plan_id)
        
        if not plan:
            print(f"[ERROR] Plan not found in database")
            continue
        
        print(f"Symbol: {plan['symbol']}")
        print(f"Direction: {plan['direction']}")
        print(f"Entry: {plan['entry_price']}")
        print(f"SL: {plan['stop_loss']}")
        print(f"TP: {plan['take_profit']}")
        print(f"Status: {plan['status']}")
        
        analysis = analyze_plan(plan)
        
        if analysis['issues']:
            print("\n[ISSUES]:")
            for issue in analysis['issues']:
                print(f"  - {issue}")
        
        if analysis['warnings']:
            print("\n[WARNINGS]:")
            for warning in analysis['warnings']:
                print(f"  - {warning}")
        
        if analysis['info']:
            print("\n[INFO]:")
            for info in analysis['info']:
                print(f"  - {info}")
        
        # Check if order flow conditions exist but service unavailable
        conditions = plan['conditions']
        order_flow_conditions = [
            "delta_positive", "delta_negative",
            "cvd_rising", "cvd_falling",
            "cvd_div_bear", "cvd_div_bull",
            "delta_divergence_bull", "delta_divergence_bear",
            "avoid_absorption_zones", "absorption_zone_detected"
        ]
        has_order_flow = any(conditions.get(cond) for cond in order_flow_conditions)
        
        if has_order_flow and not (of_service['available'] and of_service.get('running')):
            print("\n[CRITICAL]:")
            print("  - Plan has order flow conditions but service is not running")
            print("  - Plan will NOT execute until service is available")
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("\nNext steps:")
    print("1. Verify order flow service is running (check logs)")
    print("2. Fix any plan issues identified above")
    print("3. Monitor logs for condition checks")
    print("="*70)

if __name__ == "__main__":
    main()

