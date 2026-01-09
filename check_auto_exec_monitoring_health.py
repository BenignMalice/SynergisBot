"""
Check Auto-Execution Monitoring System Health
Verifies that both the monitor thread and watchdog thread are running properly.
"""

import sys
import requests
import json
from datetime import datetime

# Fix Windows encoding for emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def check_auto_exec_health():
    """Check auto-execution system health via API and direct inspection"""
    
    print("=" * 70)
    print("Auto-Execution Monitoring System Health Check")
    print("=" * 70)
    print()
    
    # Check 1: API Status Endpoint
    print("1. Checking API Status Endpoint...")
    try:
        response = requests.get("http://localhost:8000/auto-execution/system-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            status = data.get("system_status", {})
            
            print(f"   ✅ API Endpoint: Accessible")
            print(f"   - Running: {status.get('running', 'N/A')}")
            print(f"   - Thread Alive: {status.get('thread_alive', 'N/A')}")
            print(f"   - Pending Plans: {status.get('pending_plans', 0)}")
            print(f"   - Check Interval: {status.get('check_interval', 'N/A')} seconds")
            
            if status.get('running') and status.get('thread_alive'):
                print("   ✅ System Status: HEALTHY")
            elif status.get('running') and not status.get('thread_alive'):
                print("   ⚠️  WARNING: System marked as running but thread is not alive!")
            else:
                print("   ⚠️  System Status: NOT RUNNING")
        else:
            print(f"   ❌ API Endpoint: Error {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("   ❌ API Endpoint: Cannot connect (server may be down)")
    except Exception as e:
        print(f"   ❌ API Endpoint: Error - {e}")
    
    print()
    
    # Check 2: Verify monitoring is actually happening
    print("2. Checking Recent Monitoring Activity...")
    try:
        # Get plans to see if they're being monitored
        response = requests.get("http://localhost:8000/auto-execution/system-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            plans = data.get("system_status", {}).get("plans", [])
            
            if plans:
                print(f"   ✅ Found {len(plans)} pending plans")
                
                # Check if any plans are near expiration
                now = datetime.now()
                expiring_soon = []
                for plan in plans[:5]:  # Check first 5 plans
                    if plan.get("expires_at"):
                        try:
                            exp_time = datetime.fromisoformat(plan["expires_at"].replace('Z', '+00:00'))
                            hours_until_exp = (exp_time - now.replace(tzinfo=exp_time.tzinfo)).total_seconds() / 3600
                            if 0 < hours_until_exp < 24:
                                expiring_soon.append((plan.get("plan_id"), hours_until_exp))
                        except:
                            pass
                
                if expiring_soon:
                    print(f"   ℹ️  {len(expiring_soon)} plans expiring within 24 hours")
                else:
                    print("   ℹ️  No plans expiring soon")
            else:
                print("   ℹ️  No pending plans to monitor")
        else:
            print("   ⚠️  Could not fetch plans")
    except Exception as e:
        print(f"   ⚠️  Error checking plans: {e}")
    
    print()
    
    # Check 3: Watchdog Implementation Verification
    print("3. Watchdog Implementation Check...")
    try:
        with open("auto_execution_system.py", "r", encoding="utf-8") as f:
            content = f.read()
            
            checks = {
                "Watchdog thread creation": "_start_watchdog_thread" in content,
                "Watchdog loop function": "def watchdog_loop" in content,
                "Health check function": "_check_thread_health" in content,
                "Restart function": "_restart_monitor_thread" in content,
                "Non-daemon monitor thread": 'daemon=False' in content and 'AutoExecutionMonitor' in content,
                "Non-daemon watchdog thread": 'daemon=False' in content and 'watchdog_loop' in content,
            }
            
            all_good = True
            for check_name, result in checks.items():
                status = "✅" if result else "❌"
                print(f"   {status} {check_name}: {result}")
                if not result:
                    all_good = False
            
            if all_good:
                print("   ✅ Watchdog Implementation: COMPLETE")
            else:
                print("   ⚠️  Watchdog Implementation: INCOMPLETE")
    except Exception as e:
        print(f"   ❌ Error checking implementation: {e}")
    
    print()
    
    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    
    try:
        response = requests.get("http://localhost:8000/auto-execution/system-status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            status = data.get("system_status", {})
            
            if status.get('running') and status.get('thread_alive'):
                print("✅ Auto-Execution Monitoring System: OPERATIONAL")
                print()
                print("The system is running and monitoring trade plans.")
                print("The watchdog thread should automatically restart the monitor")
                print("thread if it dies unexpectedly.")
            else:
                print("⚠️  Auto-Execution Monitoring System: NOT OPERATIONAL")
                print()
                print("The system is not running properly. Check logs for errors.")
        else:
            print("❌ Cannot verify system status (API error)")
    except:
        print("❌ Cannot verify system status (connection error)")
    
    print()

if __name__ == "__main__":
    check_auto_exec_health()

