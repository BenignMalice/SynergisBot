"""
Quick test of monitoring system resilience
Fast tests with timeouts to prevent hanging
"""
import json
import urllib.request
import time
from datetime import datetime, timezone

def get_status(timeout=3):
    """Get system status with timeout"""
    try:
        url = "http://localhost:8000/auto-execution/system-status"
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data.get("system_status", {})
    except Exception as e:
        return {"error": str(e)}
    return {}

def test_quick():
    """Run quick tests"""
    print("=" * 80)
    print("QUICK MONITORING SYSTEM RESILIENCE TEST")
    print("=" * 80)
    print()
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Initial Status
    print("TEST 1: Initial Status Check")
    tests_total += 1
    status = get_status()
    running = status.get("running", False)
    thread_alive = status.get("thread_alive", False)
    if running and thread_alive:
        print("  [PASS] System running and thread alive")
        tests_passed += 1
    else:
        print(f"  [FAIL] Running={running}, ThreadAlive={thread_alive}")
    print()
    
    # Test 2: Health Check Active
    print("TEST 2: Health Check Mechanism")
    tests_total += 1
    status1 = get_status()
    time.sleep(1)
    status2 = get_status()
    has_thread_status = "thread_alive" in status1 and "thread_alive" in status2
    if has_thread_status:
        print("  [PASS] Health check reporting thread status")
        tests_passed += 1
    else:
        print("  [FAIL] Health check not reporting thread status")
    print()
    
    # Test 3: Thread Persistence (short)
    print("TEST 3: Thread Persistence (15 seconds)")
    tests_total += 1
    initial = get_status()
    initial_alive = initial.get("thread_alive", False)
    if not initial_alive:
        print("  [FAIL] Thread not alive initially")
    else:
        time.sleep(5)
        check1 = get_status()
        time.sleep(5)
        check2 = get_status()
        time.sleep(5)
        check3 = get_status()
        
        all_alive = all([
            check1.get("thread_alive", False),
            check2.get("thread_alive", False),
            check3.get("thread_alive", False)
        ])
        if all_alive:
            print("  [PASS] Thread remained alive over 15 seconds")
            tests_passed += 1
        else:
            print("  [FAIL] Thread died during test")
    print()
    
    # Test 4: Status Consistency
    print("TEST 4: Status Consistency")
    tests_total += 1
    statuses = []
    for i in range(5):
        statuses.append(get_status())
        time.sleep(0.5)
    
    running_values = [s.get("running", False) for s in statuses]
    thread_values = [s.get("thread_alive", False) for s in statuses]
    
    consistent = len(set(running_values)) == 1 and len(set(thread_values)) == 1
    if consistent:
        print("  [PASS] Status reporting is consistent")
        tests_passed += 1
    else:
        print(f"  [FAIL] Status inconsistent: Running={running_values}, Thread={thread_values}")
    print()
    
    # Test 5: Plan Monitoring
    print("TEST 5: Plan Monitoring")
    tests_total += 1
    status = get_status()
    pending = status.get("pending_plans", 0)
    if pending > 0:
        print(f"  [PASS] Monitoring {pending} plans")
        tests_passed += 1
    else:
        print("  [FAIL] No plans being monitored")
    print()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"  Passed: {tests_passed}/{tests_total}")
    print()
    
    if tests_passed == tests_total:
        print("  [OK] ALL TESTS PASSED")
        print("  System is resilient and health check is working")
    else:
        print(f"  [WARNING] {tests_total - tests_passed} test(s) failed")
    
    print()
    print("=" * 80)
    
    return tests_passed == tests_total

if __name__ == "__main__":
    test_quick()

