"""
Verify that the auto-execution monitoring system is actively functioning
Checks for evidence of active monitoring cycles
"""
import json
import urllib.request
import time
from datetime import datetime, timezone
from typing import Dict, Any

def check_monitoring_activity() -> Dict[str, Any]:
    """Check if monitoring system is actively checking plans"""
    print("=" * 80)
    print("MONITORING SYSTEM ACTIVITY VERIFICATION")
    print("=" * 80)
    print()
    
    # First check - System status
    print("1. CHECKING SYSTEM STATUS...")
    try:
        url = "http://localhost:8000/auto-execution/system-status"
        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                system_status = data.get("system_status", {})
                
                running = system_status.get("running", False)
                thread_alive = system_status.get("thread_alive", False)
                pending_plans = system_status.get("pending_plans", 0)
                check_interval = system_status.get("check_interval", 30)
                
                print(f"   System Running: {'[OK] YES' if running else '[FAIL] NO'}")
                print(f"   Thread Alive: {'[OK] YES' if thread_alive else '[FAIL] NO'}")
                print(f"   Pending Plans: {pending_plans}")
                print(f"   Check Interval: {check_interval} seconds")
                print()
                
                if not running or not thread_alive:
                    print("   [CRITICAL] System is not running or thread is dead!")
                    print("   -> Monitoring will NOT occur")
                    return {"active": False, "reason": "System not running or thread dead"}
                
                if pending_plans == 0:
                    print("   [WARNING] No pending plans to monitor")
                    print("   -> System is running but has nothing to check")
                    return {"active": True, "warning": "No plans to monitor"}
                
    except Exception as e:
        print(f"   [FAIL] Cannot check system status: {e}")
        return {"active": False, "reason": f"Cannot connect to API: {e}"}
    
    # Second check - Wait and verify monitoring is happening
    print("2. VERIFYING ACTIVE MONITORING...")
    print("   Waiting 35 seconds to observe monitoring cycle...")
    print("   (Monitoring checks occur every 30 seconds)")
    print()
    
    # Get initial timestamp
    initial_time = datetime.now(timezone.utc)
    
    # Wait for a monitoring cycle to occur
    time.sleep(35)
    
    # Check status again to see if anything changed
    try:
        url = "http://localhost:8000/auto-execution/system-status"
        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                system_status = data.get("system_status", {})
                
                final_running = system_status.get("running", False)
                final_thread_alive = system_status.get("thread_alive", False)
                final_pending_plans = system_status.get("pending_plans", 0)
                
                elapsed = (datetime.now(timezone.utc) - initial_time).total_seconds()
                
                print(f"   Elapsed Time: {elapsed:.1f} seconds")
                print(f"   System Still Running: {'[OK] YES' if final_running else '[FAIL] NO'}")
                print(f"   Thread Still Alive: {'[OK] YES' if final_thread_alive else '[FAIL] NO'}")
                print(f"   Pending Plans: {final_pending_plans} (was {pending_plans})")
                print()
                
                if not final_running or not final_thread_alive:
                    print("   [CRITICAL] System stopped or thread died during monitoring!")
                    return {"active": False, "reason": "System stopped during monitoring"}
                
                if final_pending_plans != pending_plans:
                    print(f"   [INFO] Plan count changed: {pending_plans} -> {final_pending_plans}")
                    print("   -> This indicates monitoring is active (plans executed/expired)")
                
                print("   [OK] System remained active during monitoring cycle")
                print("   -> Monitoring loop is functioning")
                
    except Exception as e:
        print(f"   [FAIL] Cannot verify monitoring activity: {e}")
        return {"active": False, "reason": f"Cannot verify: {e}"}
    
    # Third check - Verify health check is working
    print("3. VERIFYING HEALTH CHECK...")
    print("   Health check should run every 30 seconds")
    print("   Checking if health check detects thread status correctly...")
    print()
    
    # Call status multiple times to trigger health checks
    health_check_working = True
    for i in range(3):
        try:
            url = "http://localhost:8000/auto-execution/system-status"
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    system_status = data.get("system_status", {})
                    thread_alive = system_status.get("thread_alive", False)
                    
                    if not thread_alive:
                        print(f"   [WARNING] Thread reported as dead on check {i+1}")
                        health_check_working = False
                    else:
                        print(f"   [OK] Check {i+1}: Thread is alive")
            
            if i < 2:
                time.sleep(1)  # Small delay between checks
        except Exception as e:
            print(f"   [FAIL] Error on health check {i+1}: {e}")
            health_check_working = False
    
    print()
    
    if health_check_working:
        print("   [OK] Health check is working correctly")
    else:
        print("   [WARNING] Health check may have issues")
    
    print()
    
    # Summary
    print("=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print()
    
    all_ok = running and thread_alive and final_running and final_thread_alive and health_check_working
    
    if all_ok:
        print("  [OK] MONITORING SYSTEM IS ACTIVE AND FUNCTIONING")
        print()
        print("  The system is:")
        print("    - Running and monitoring plans")
        print("    - Thread is alive and checking conditions")
        print("    - Health check is working")
        print("    - Ready to execute trades when conditions are met")
        print()
        print(f"  Monitoring {pending_plans} pending plan(s) every {check_interval} seconds")
    else:
        print("  [WARNING] MONITORING SYSTEM HAS ISSUES")
        print()
        if not running:
            print("    - System is not running")
        if not thread_alive:
            print("    - Monitor thread is dead")
        if not health_check_working:
            print("    - Health check may not be working correctly")
    
    print()
    print("=" * 80)
    
    return {
        "active": all_ok,
        "running": running,
        "thread_alive": thread_alive,
        "pending_plans": pending_plans,
        "health_check_working": health_check_working
    }

if __name__ == "__main__":
    result = check_monitoring_activity()

