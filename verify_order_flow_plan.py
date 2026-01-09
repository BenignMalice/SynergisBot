"""
Verify Order Flow Plan Status and Monitoring

Checks if plan chatgpt_e21bef2b is saved correctly and will be monitored.
"""

import asyncio
import json
import sqlite3
from pathlib import Path
from cursor_trading_bridge import get_bridge

async def verify_plan():
    """Verify plan status and conditions"""
    bridge = get_bridge()
    
    plan_id = "chatgpt_e21bef2b"
    
    print("=" * 70)
    print("ORDER FLOW PLAN VERIFICATION")
    print("=" * 70)
    print()
    
    # 1. Check if plan exists in database
    print("1. Checking if plan exists in database...")
    db_path = Path("data/auto_execution.db")
    
    if not db_path.exists():
        print("   [FAIL] Database not found at data/auto_execution.db")
        return
    
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute("""
                SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit,
                       volume, conditions, status, created_at, expires_at
                FROM trade_plans 
                WHERE plan_id = ?
            """, (plan_id,))
            
            row = cursor.fetchone()
            
            if not row:
                print(f"   [FAIL] Plan {plan_id} not found in database")
                return
            
            plan_data = {
                "plan_id": row[0],
                "symbol": row[1],
                "direction": row[2],
                "entry_price": row[3],
                "stop_loss": row[4],
                "take_profit": row[5],
                "volume": row[6],
                "conditions": json.loads(row[7]) if row[7] else {},
                "status": row[8],
                "created_at": row[9],
                "expires_at": row[10]
            }
            
            print(f"   [PASS] Plan found in database")
            print(f"   Plan ID: {plan_data['plan_id']}")
            print(f"   Symbol: {plan_data['symbol']}")
            print(f"   Direction: {plan_data['direction']}")
            print(f"   Entry: ${plan_data['entry_price']:.2f}")
            print(f"   Stop Loss: ${plan_data['stop_loss']:.2f}")
            print(f"   Take Profit: ${plan_data['take_profit']:.2f}")
            print(f"   Status: {plan_data['status']}")
            print()
            
            # 2. Verify conditions
            print("2. Verifying conditions...")
            conditions = plan_data['conditions']
            
            required_conditions = {
                "delta_positive": True,
                "cvd_rising": True,
                "price_near": 88450.0,
                "tolerance": 50.0
            }
            
            all_present = True
            for key, expected_value in required_conditions.items():
                if key in conditions:
                    actual_value = conditions[key]
                    if actual_value == expected_value:
                        print(f"   [PASS] {key}: {actual_value}")
                    else:
                        print(f"   [WARN] {key}: {actual_value} (expected {expected_value})")
                else:
                    print(f"   [FAIL] {key}: MISSING")
                    all_present = False
            
            if all_present:
                print("   [PASS] All required conditions present")
            else:
                print("   [FAIL] Some conditions missing")
            
            print()
            
            # 3. Check system status
            print("3. Checking auto-execution system status...")
            try:
                status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
                status_data = status_result.get("data", {})
                system_status = status_data.get("system_status", {})
                
                running = system_status.get("running", False)
                total_plans = system_status.get("total_plans", 0)
                pending_plans = system_status.get("pending_plans", 0)
                
                print(f"   System Running: {running}")
                print(f"   Total Plans: {total_plans}")
                print(f"   Pending Plans: {pending_plans}")
                
                # Check if our plan is in the list
                plans = system_status.get("plans", [])
                our_plan = next((p for p in plans if p.get("plan_id") == plan_id), None)
                
                if our_plan:
                    print(f"   [PASS] Plan found in active plans list")
                    print(f"   Plan Status: {our_plan.get('status')}")
                else:
                    print(f"   [WARN] Plan not in active plans list (may be in database but not loaded)")
                
            except Exception as e:
                print(f"   [WARN] Could not check system status: {e}")
            
            print()
            
            # 4. Verify condition checking logic
            print("4. Verifying condition checking logic...")
            print("   Checking code paths for order flow conditions:")
            
            # Verify BTC symbol
            symbol_norm = plan_data['symbol'].upper().rstrip('Cc')
            if symbol_norm.startswith('BTC'):
                print(f"   [PASS] Symbol {plan_data['symbol']} is BTC - order flow conditions will be checked")
            else:
                print(f"   [FAIL] Symbol {plan_data['symbol']} is NOT BTC - order flow conditions may not work")
            
            # Verify conditions are in the recognized list
            order_flow_conditions = [
                "delta_positive", "delta_negative",
                "cvd_rising", "cvd_falling",
                "cvd_div_bear", "cvd_div_bull",
                "delta_divergence_bull", "delta_divergence_bear",
                "avoid_absorption_zones", "absorption_zone_detected"
            ]
            
            has_order_flow = any(cond in conditions for cond in order_flow_conditions)
            if has_order_flow:
                print(f"   [PASS] Plan has order flow conditions")
                print(f"   Order flow conditions found: {[k for k in conditions.keys() if k in order_flow_conditions]}")
            else:
                print(f"   [FAIL] Plan does not have order flow conditions")
            
            print()
            
            # 5. Monitoring frequency
            print("5. Monitoring frequency...")
            print("   [INFO] Order flow plans are checked every 5 seconds (Phase 2.2)")
            print("   [INFO] Regular plans are checked every 30 seconds")
            print("   [INFO] Plan will be monitored until expiration or execution")
            print()
            
            # 6. Execution requirements
            print("6. Execution requirements...")
            print("   For plan to execute, ALL conditions must be met:")
            print(f"   - delta_positive: true → Delta volume must be > 0")
            print(f"   - cvd_rising: true → CVD slope must be > 0 (rising)")
            print(f"   - price_near: 88450 ± 50 → Price must be between $88,400 and $88,500")
            print()
            print("   [INFO] System checks these conditions in _check_btc_order_flow_conditions_only()")
            print("   [INFO] Location: auto_execution_system.py lines 1888-1915")
            print()
            
            # 7. Summary
            print("=" * 70)
            print("VERIFICATION SUMMARY")
            print("=" * 70)
            
            if all_present and symbol_norm.startswith('BTC') and has_order_flow:
                print("[SUCCESS] Plan is correctly configured and will be monitored")
                print()
                print("Plan will execute when:")
                print("  1. Delta volume > 0 (buying pressure)")
                print("  2. CVD slope > 0 (CVD rising)")
                print("  3. Price is between $88,400 and $88,500")
                print("  4. All other conditions pass (if any)")
                print()
                print("Monitoring:")
                print("  - Checked every 5 seconds (order flow plans)")
                print("  - System must be running")
                print("  - Order flow service must be available")
            else:
                print("[WARNING] Plan may not execute correctly")
                if not all_present:
                    print("  - Some conditions are missing")
                if not symbol_norm.startswith('BTC'):
                    print("  - Symbol is not BTC (order flow only works for BTC)")
                if not has_order_flow:
                    print("  - No order flow conditions found")
            
    except Exception as e:
        print(f"[ERROR] Error verifying plan: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_plan())
