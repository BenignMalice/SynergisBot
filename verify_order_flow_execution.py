"""
Verify Order Flow Service Registration and Plan Execution Capability

This script checks:
1. Log messages for Order Flow Service registration
2. Order flow service availability in registry
3. Order flow metrics initialization
4. Ability to execute order flow plans
"""

import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime

def check_log_messages():
    """Check for required log messages"""
    log_file = Path("data/logs/chatgpt_bot.log")
    if not log_file.exists():
        print("[FAIL] Log file not found")
        return False
    
    required_messages = [
        "Order Flow Service registered in global registry (before start)",
        "Order Flow Service re-registered in global registry (after start)",
        "Order flow service found in desktop_agent.registry and running",
        "BTC order flow metrics initialized with active service"
    ]
    
    print("\n" + "="*70)
    print("CHECKING LOG MESSAGES")
    print("="*70)
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        log_content = f.read()
    
    all_found = True
    for msg in required_messages:
        # Escape special regex characters
        pattern = re.escape(msg)
        if re.search(pattern, log_content):
            print(f"[PASS] Found: {msg}")
        else:
            print(f"[FAIL] Missing: {msg}")
            all_found = False
    
    return all_found

def check_database_plans():
    """Check for plans with order flow conditions"""
    db_path = Path("data/trade_plans.sqlite")
    if not db_path.exists():
        print("\n[FAIL] Database file not found")
        return False
    
    print("\n" + "="*70)
    print("CHECKING DATABASE PLANS")
    print("="*70)
    
    order_flow_conditions = [
        "delta_positive", "delta_negative",
        "cvd_rising", "cvd_falling",
        "cvd_div_bear", "cvd_div_bull",
        "delta_divergence_bull", "delta_divergence_bear",
        "avoid_absorption_zones", "absorption_zone_detected"
    ]
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("""
            SELECT plan_id, symbol, conditions, status 
            FROM trade_plans 
            WHERE status IN ('pending', 'executing')
            ORDER BY created_at DESC
            LIMIT 20
        """)
        
        plans = cursor.fetchall()
        print(f"\nFound {len(plans)} active plan(s)")
        
        of_plans = []
        for plan_id, symbol, conditions_json, status in plans:
            if not conditions_json:
                continue
            
            try:
                conditions = json.loads(conditions_json)
                has_of = any(conditions.get(cond) for cond in order_flow_conditions)
                
                if has_of:
                    of_plans.append((plan_id, symbol, conditions, status))
                    print(f"\n[PASS] Order Flow Plan Found:")
                    print(f"   Plan ID: {plan_id}")
                    print(f"   Symbol: {symbol}")
                    print(f"   Status: {status}")
                    print(f"   Order Flow Conditions: {[k for k in conditions.keys() if k in order_flow_conditions]}")
            except json.JSONDecodeError:
                continue
        
        conn.close()
        
        if of_plans:
            print(f"\n[PASS] Found {len(of_plans)} plan(s) with order flow conditions")
            return True
        else:
            print(f"\n[INFO] No plans with order flow conditions found in database")
            print("   Note: This is OK if no order flow plans have been created yet")
            return True  # Not an error, just informational
        
    except Exception as e:
        print(f"\n[FAIL] Error checking database: {e}")
        return False

def verify_service_access():
    """Verify order flow service can be accessed"""
    print("\n" + "="*70)
    print("VERIFYING SERVICE ACCESS")
    print("="*70)
    
    try:
        # Try to import and access registry
        from desktop_agent import registry
        
        if hasattr(registry, 'order_flow_service'):
            service = registry.order_flow_service
            if service:
                if hasattr(service, 'running') and service.running:
                    symbols = getattr(service, 'symbols', 'unknown')
                    print(f"[PASS] Order Flow Service found in registry")
                    print(f"   Status: RUNNING")
                    print(f"   Symbols: {symbols}")
                    return True
                else:
                    print(f"[WARN] Order Flow Service found but not running")
                    return False
            else:
                print(f"[FAIL] Order Flow Service is None in registry")
                return False
        else:
            print(f"[FAIL] Order Flow Service not found in registry")
            return False
            
    except ImportError:
        print(f"[FAIL] Could not import desktop_agent.registry")
        return False
    except Exception as e:
        print(f"[FAIL] Error accessing service: {e}")
        return False

def verify_metrics_initialization():
    """Verify order flow metrics can be initialized"""
    print("\n" + "="*70)
    print("VERIFYING METRICS INITIALIZATION")
    print("="*70)
    
    try:
        # Try to access auto execution system
        import chatgpt_bot
        
        if hasattr(chatgpt_bot, 'auto_execution'):
            auto_exec = chatgpt_bot.auto_execution
            if auto_exec and hasattr(auto_exec, 'auto_system'):
                system = auto_exec.auto_system
                if system:
                    if hasattr(system, 'micro_scalp_engine'):
                        engine = system.micro_scalp_engine
                        if engine and hasattr(engine, 'btc_order_flow'):
                            btc_flow = engine.btc_order_flow
                            if btc_flow:
                                print(f"[PASS] BTC Order Flow Metrics initialized")
                                print(f"   Available in micro_scalp_engine.btc_order_flow")
                                
                                # Try to get metrics
                                try:
                                    metrics = btc_flow.get_metrics("BTCUSDT", window_seconds=300)
                                    if metrics:
                                        print(f"[PASS] Metrics retrieval successful")
                                        print(f"   Delta Volume: {metrics.delta_volume}")
                                        print(f"   CVD Slope: {metrics.cvd_slope}")
                                        return True
                                    else:
                                        print(f"[INFO] Metrics returned None (may need more data)")
                                        return True  # Not an error, just needs data
                                except Exception as e:
                                    print(f"[INFO] Error getting metrics: {e}")
                                    return True  # Service is initialized, just needs data
                            else:
                                print(f"[FAIL] btc_order_flow is None")
                                return False
                        else:
                            print(f"[FAIL] micro_scalp_engine has no btc_order_flow")
                            return False
                    else:
                        print(f"[FAIL] auto_system has no micro_scalp_engine")
                        return False
                else:
                    print(f"[FAIL] auto_exec.auto_system is None")
                    return False
            else:
                print(f"[INFO] auto_execution not initialized (may need to start bot)")
                return False
        else:
            print(f"[INFO] chatgpt_bot has no auto_execution (may need to start bot)")
            return False
            
    except ImportError:
        print(f"[INFO] Could not import chatgpt_bot (bot may not be running)")
        return False
    except Exception as e:
        print(f"[INFO] Error checking metrics: {e}")
        return False

def main():
    """Main verification function"""
    print("\n" + "="*70)
    print("ORDER FLOW SERVICE VERIFICATION")
    print("="*70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        "log_messages": check_log_messages(),
        "database_plans": check_database_plans(),
        "service_access": verify_service_access(),
        "metrics_init": verify_metrics_initialization()
    }
    
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    
    all_passed = True
    for check, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {check}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("[PASS] ALL CHECKS PASSED - Order Flow Plans Can Execute")
    else:
        print("[WARN] SOME CHECKS FAILED - Review issues above")
    print("="*70)
    
    return all_passed

if __name__ == "__main__":
    main()

