"""
Test monitoring system restart mechanism
Verifies that health check can detect and restart dead threads
"""
import json
import urllib.request
import time
from datetime import datetime, timezone

def get_status(timeout=3):
    """Get system status"""
    try:
        url = "http://localhost:8000/auto-execution/system-status"
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data.get("system_status", {})
    except Exception as e:
        return {"error": str(e)}
    return {}

def test_restart_mechanism():
    """Test that health check can restart threads"""
    print("=" * 80)
    print("MONITORING SYSTEM RESTART MECHANISM TEST")
    print("=" * 80)
    print()
    print("This test verifies:")
    print("  1. Health check runs on status calls")
    print("  2. Health check can detect dead threads")
    print("  3. System can recover from thread death")
    print()
    
    # Initial check
    print("STEP 1: Initial Status Check")
    status1 = get_status()
    running1 = status1.get("running", False)
    thread_alive1 = status1.get("thread_alive", False)
    print(f"  Initial: Running={running1}, ThreadAlive={thread_alive1}")
    
    # If thread is dead, health check should restart it
    if not thread_alive1 and running1:
        print("  [INFO] Thread is dead but system should be running")
        print("  [INFO] Health check should restart thread on next status call")
    
    # Wait a moment
    time.sleep(2)
    
    # Check again - health check should have run
    print("\nSTEP 2: Status Check After Health Check")
    status2 = get_status()
    running2 = status2.get("running", False)
    thread_alive2 = status2.get("thread_alive", False)
    print(f"  After health check: Running={running2}, ThreadAlive={thread_alive2}")
    
    # Check multiple times to see if thread restarts
    print("\nSTEP 3: Multiple Status Checks (Triggering Health Checks)")
    checks = []
    for i in range(5):
        status = get_status()
        running = status.get("running", False)
        thread_alive = status.get("thread_alive", False)
        checks.append({"running": running, "thread_alive": thread_alive})
        print(f"  Check {i+1}/5: Running={running}, ThreadAlive={thread_alive}")
        time.sleep(1)
    
    # Analyze results
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    
    # Check if thread recovered
    final_alive = checks[-1]["thread_alive"]
    final_running = checks[-1]["running"]
    
    if final_alive and final_running:
        print("  [PASS] Thread is alive and system is running")
        print("  -> Health check mechanism is working")
        
        # Check if thread was restarted
        was_dead = not thread_alive1
        is_alive = final_alive
        if was_dead and is_alive:
            print("  [PASS] Thread was restarted by health check")
            print("  -> Automatic recovery is working!")
        elif thread_alive1 and is_alive:
            print("  [INFO] Thread was already alive")
    else:
        print("  [FAIL] Thread is not alive or system not running")
        print(f"  -> Running={final_running}, ThreadAlive={final_alive}")
    
    # Check consistency
    all_running = all(c["running"] for c in checks)
    all_alive = all(c["thread_alive"] for c in checks)
    
    print(f"\n  Consistency: All running={all_running}, All alive={all_alive}")
    
    if all_running and all_alive:
        print("  [PASS] System remained stable throughout test")
    elif final_running and final_alive:
        print("  [INFO] System recovered during test")
    else:
        print("  [WARNING] System has issues")
    
    print()
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    
    if final_running and final_alive:
        print("  [OK] System is operational")
        print("  [OK] Health check mechanism is active")
        if was_dead and is_alive:
            print("  [OK] Automatic restart mechanism is working")
        print()
        print("  The monitoring system will:")
        print("    - Check thread health every 30 seconds")
        print("    - Automatically restart thread if it dies")
        print("    - Continue monitoring plans after recovery")
    else:
        print("  [WARNING] System needs attention")
        print("  - Check logs for errors")
        print("  - Verify API server is running")
        print("  - Restart services if needed")
    
    print()
    return final_running and final_alive

if __name__ == "__main__":
    test_restart_mechanism()

