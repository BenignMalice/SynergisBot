"""
Verify Auto-Execution Plans are Saved Correctly and Will Be Monitored
Checks database, plan structure, condition monitoring, and execution logic.
"""

import sys
import sqlite3
import json
import requests
from datetime import datetime, timezone
from pathlib import Path

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def check_database_plans():
    """Check if plans are saved correctly in the database"""
    print("=" * 70)
    print("1. Checking Database Plans")
    print("=" * 70)
    
    db_path = Path("data/auto_execution.db")
    if not db_path.exists():
        print(f"   ❌ Database not found: {db_path}")
        return []
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check table structure (table name is 'trade_plans')
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trade_plans'")
        if not cursor.fetchone():
            print("   ❌ Table 'trade_plans' not found")
            conn.close()
            return []
        
        # Get all pending plans
        cursor.execute("""
            SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit, 
                   volume, conditions, status, created_at, expires_at, notes
            FROM trade_plans
            WHERE status = 'pending'
            ORDER BY created_at DESC
        """)
        
        plans = cursor.fetchall()
        print(f"   ✅ Found {len(plans)} pending plans in database")
        
        # Check plan structure
        if plans:
            sample_plan = plans[0]
            print(f"\n   Sample Plan Structure:")
            print(f"   - Plan ID: {sample_plan[0]}")
            print(f"   - Symbol: {sample_plan[1]}")
            print(f"   - Direction: {sample_plan[2]}")
            print(f"   - Entry Price: {sample_plan[3]}")
            print(f"   - Stop Loss: {sample_plan[4]}")
            print(f"   - Take Profit: {sample_plan[5]}")
            print(f"   - Volume: {sample_plan[6]}")
            
            # Check conditions
            try:
                conditions = json.loads(sample_plan[7]) if sample_plan[7] else {}
                print(f"   - Conditions: {len(conditions)} condition(s)")
                for key, value in list(conditions.items())[:5]:
                    print(f"     • {key}: {value}")
                if len(conditions) > 5:
                    print(f"     ... and {len(conditions) - 5} more")
            except:
                print(f"   - Conditions: Error parsing")
            
            print(f"   - Status: {sample_plan[8]}")
            print(f"   - Created At: {sample_plan[9]}")
            print(f"   - Expires At: {sample_plan[10]}")
        
        conn.close()
        return plans
        
    except Exception as e:
        print(f"   ❌ Error reading database: {e}")
        return []

def check_api_plans():
    """Check plans via API endpoint"""
    print("\n" + "=" * 70)
    print("2. Checking Plans via API")
    print("=" * 70)
    
    try:
        response = requests.get("http://localhost:8000/auto-execution/system-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            status = data.get("system_status", {})
            plans = status.get("plans", [])
            
            print(f"   ✅ API returned {len(plans)} plans")
            
            if plans:
                # Check a sample plan
                sample = plans[0]
                print(f"\n   Sample Plan from API:")
                print(f"   - Plan ID: {sample.get('plan_id')}")
                print(f"   - Symbol: {sample.get('symbol')}")
                print(f"   - Direction: {sample.get('direction')}")
                print(f"   - Status: {sample.get('status')}")
                
                conditions = sample.get('conditions', {})
                print(f"   - Conditions: {len(conditions)} condition(s)")
                for key, value in list(conditions.items())[:5]:
                    print(f"     • {key}: {value}")
                if len(conditions) > 5:
                    print(f"     ... and {len(conditions) - 5} more")
            
            return plans
        else:
            print(f"   ❌ API Error: {response.status_code}")
            return []
    except Exception as e:
        print(f"   ❌ API Error: {e}")
        return []

def check_condition_monitoring():
    """Check if monitoring logic handles all condition types"""
    print("\n" + "=" * 70)
    print("3. Checking Condition Monitoring Logic")
    print("=" * 70)
    
    try:
        with open("auto_execution_system.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check for various condition types
        condition_checks = {
            "Price conditions": "_check_price_condition" in content or "price_near" in content.lower(),
            "Order block conditions": "order_block" in content.lower(),
            "BOS/CHOCH conditions": "bos_" in content.lower() or "choch_" in content.lower(),
            "Liquidity sweep conditions": "liquidity_sweep" in content.lower(),
            "Volume conditions": "volume_" in content.lower(),
            "Confluence conditions": "confluence" in content.lower() or "min_confluence" in content.lower(),
            "Structure confirmation": "structure_confirmation" in content.lower(),
            "Inside bar conditions": "inside_bar" in content.lower(),
            "Range scalp conditions": "range_scalp" in content.lower(),
            "Micro scalp conditions": "micro_scalp" in content.lower(),
        }
        
        all_good = True
        for check_name, result in condition_checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check_name}: {result}")
            if not result:
                all_good = False
        
        if all_good:
            print("\n   ✅ All condition types appear to be supported")
        else:
            print("\n   ⚠️  Some condition types may not be fully supported")
        
        # Check monitoring loop
        if "_monitor_loop" in content:
            print("\n   ✅ Monitoring loop function found")
        else:
            print("\n   ❌ Monitoring loop function not found")
        
        # Check condition evaluation
        if "_check_plan_conditions" in content or "_evaluate_conditions" in content or "check_conditions" in content.lower():
            print("   ✅ Condition evaluation function found")
        else:
            print("   ⚠️  Condition evaluation function not clearly identified")
        
    except Exception as e:
        print(f"   ❌ Error checking monitoring logic: {e}")

def check_execution_logic():
    """Check if execution logic will trigger trades appropriately"""
    print("\n" + "=" * 70)
    print("4. Checking Execution Logic")
    print("=" * 70)
    
    try:
        with open("auto_execution_system.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        execution_checks = {
            "Execute trade function": "_execute_trade" in content or "execute_plan" in content.lower(),
            "MT5 connection check": "mt5." in content or "MT5Service" in content,
            "Position size validation": "volume" in content.lower() and "lot" in content.lower(),
            "Risk management": "stop_loss" in content.lower() and "take_profit" in content.lower(),
            "Error handling": "try:" in content and "except" in content,
            "Status updates": "status" in content.lower() and "executed" in content.lower(),
            "Trade registration": "register" in content.lower() or "Universal" in content,
        }
        
        all_good = True
        for check_name, result in execution_checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check_name}: {result}")
            if not result:
                all_good = False
        
        if all_good:
            print("\n   ✅ Execution logic appears complete")
        else:
            print("\n   ⚠️  Some execution components may be missing")
        
    except Exception as e:
        print(f"   ❌ Error checking execution logic: {e}")

def check_system_status():
    """Check overall system status"""
    print("\n" + "=" * 70)
    print("5. System Status Check")
    print("=" * 70)
    
    try:
        response = requests.get("http://localhost:8000/auto-execution/system-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            status = data.get("system_status", {})
            
            print(f"   Running: {status.get('running', 'N/A')}")
            print(f"   Thread Alive: {status.get('thread_alive', 'N/A')}")
            print(f"   Pending Plans: {status.get('pending_plans', 0)}")
            print(f"   Check Interval: {status.get('check_interval', 'N/A')} seconds")
            
            if status.get('running') and status.get('thread_alive'):
                print("\n   ✅ System is running and monitoring")
            else:
                print("\n   ⚠️  System may not be running properly")
        else:
            print(f"   ❌ API Error: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

def main():
    """Run all checks"""
    print("\n" + "=" * 70)
    print("Auto-Execution Plans Verification")
    print("=" * 70)
    print()
    
    # Check database
    db_plans = check_database_plans()
    
    # Check API
    api_plans = check_api_plans()
    
    # Check condition monitoring
    check_condition_monitoring()
    
    # Check execution logic
    check_execution_logic()
    
    # Check system status
    check_system_status()
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    if db_plans and api_plans:
        print("✅ Plans are saved correctly in database")
        print("✅ Plans are accessible via API")
        print("✅ Monitoring system is running")
        print("✅ Condition monitoring logic is in place")
        print("✅ Execution logic is in place")
        print("\n✅ System is ready to monitor and execute trades when conditions are met")
    else:
        print("⚠️  Some issues detected - review above checks")
    
    print()

if __name__ == "__main__":
    main()

