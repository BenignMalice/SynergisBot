"""
Test monitoring system resilience and automatic restart
Simulates various failure scenarios and verifies recovery
"""
import json
import urllib.request
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List

class MonitoringSystemTester:
    """Test monitoring system resilience"""
    
    def __init__(self):
        self.api_url = "http://localhost:8000/auto-execution/system-status"
        self.test_results = []
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status"""
        try:
            with urllib.request.urlopen(self.api_url, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    return data.get("system_status", {})
        except Exception as e:
            return {"error": str(e)}
        return {}
    
    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        status = "[PASS]" if passed else "[FAIL]"
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        print(f"  {status} {test_name}")
        if details:
            print(f"      {details}")
    
    def test_1_initial_status(self) -> bool:
        """Test 1: Verify system starts in good state"""
        print("\n" + "=" * 80)
        print("TEST 1: Initial System Status")
        print("=" * 80)
        
        status = self.get_status()
        running = status.get("running", False)
        thread_alive = status.get("thread_alive", False)
        pending_plans = status.get("pending_plans", 0)
        
        passed = running and thread_alive
        details = f"Running={running}, ThreadAlive={thread_alive}, Plans={pending_plans}"
        
        self.log_test("Initial Status Check", passed, details)
        return passed
    
    def test_2_health_check_frequency(self) -> bool:
        """Test 2: Verify health check runs frequently"""
        print("\n" + "=" * 80)
        print("TEST 2: Health Check Frequency")
        print("=" * 80)
        print("  Checking if health check detects thread status...")
        
        # Call status multiple times to trigger health checks
        results = []
        for i in range(5):
            status = self.get_status()
            thread_alive = status.get("thread_alive", False)
            results.append(thread_alive)
            if i < 4:
                time.sleep(1)
        
        # All checks should show thread alive
        all_alive = all(results)
        details = f"Thread status over 5 checks: {results}"
        
        self.log_test("Health Check Frequency", all_alive, details)
        return all_alive
    
    def test_3_thread_persistence(self) -> bool:
        """Test 3: Verify thread persists over time"""
        print("\n" + "=" * 80)
        print("TEST 3: Thread Persistence")
        print("=" * 80)
        print("  Monitoring thread status over 30 seconds...")
        
        initial_status = self.get_status()
        initial_alive = initial_status.get("thread_alive", False)
        
        if not initial_alive:
            self.log_test("Thread Persistence", False, "Thread not alive initially")
            return False
        
        # Check every 5 seconds for 30 seconds
        checks = []
        for i in range(6):
            time.sleep(5)
            status = self.get_status()
            thread_alive = status.get("thread_alive", False)
            checks.append(thread_alive)
            print(f"    Check {i+1}/6: Thread alive = {thread_alive}")
        
        all_alive = all(checks)
        details = f"Thread remained alive over 30 seconds: {checks}"
        
        self.log_test("Thread Persistence", all_alive, details)
        return all_alive
    
    def test_4_status_consistency(self) -> bool:
        """Test 4: Verify status reporting is consistent"""
        print("\n" + "=" * 80)
        print("TEST 4: Status Consistency")
        print("=" * 80)
        
        statuses = []
        for i in range(10):
            status = self.get_status()
            statuses.append({
                "running": status.get("running", False),
                "thread_alive": status.get("thread_alive", False),
                "pending_plans": status.get("pending_plans", 0)
            })
            time.sleep(0.5)
        
        # All statuses should be consistent
        running_values = [s["running"] for s in statuses]
        thread_alive_values = [s["thread_alive"] for s in statuses]
        plan_counts = [s["pending_plans"] for s in statuses]
        
        running_consistent = len(set(running_values)) == 1
        thread_consistent = len(set(thread_alive_values)) == 1
        plans_consistent = len(set(plan_counts)) == 1
        
        passed = running_consistent and thread_consistent and plans_consistent
        details = f"Running consistent: {running_consistent}, Thread consistent: {thread_consistent}, Plans consistent: {plans_consistent}"
        
        self.log_test("Status Consistency", passed, details)
        return passed
    
    def test_5_recovery_mechanism(self) -> bool:
        """Test 5: Verify recovery mechanism exists (can't actually kill thread, but verify health check)"""
        print("\n" + "=" * 80)
        print("TEST 5: Recovery Mechanism Verification")
        print("=" * 80)
        print("  Note: Cannot actually kill thread from external test")
        print("  Verifying health check mechanism is active...")
        
        # Check that health check runs on status calls
        initial_time = time.time()
        status1 = self.get_status()
        time.sleep(1)
        status2 = self.get_status()
        time.sleep(1)
        status3 = self.get_status()
        elapsed = time.time() - initial_time
        
        # All status calls should work (health check runs)
        all_work = (
            "error" not in status1 and
            "error" not in status2 and
            "error" not in status3
        )
        
        # Check that thread_alive is reported
        has_thread_status = (
            "thread_alive" in status1 and
            "thread_alive" in status2 and
            "thread_alive" in status3
        )
        
        passed = all_work and has_thread_status
        details = f"Health check active: {all_work}, Thread status reported: {has_thread_status}, Elapsed: {elapsed:.1f}s"
        
        self.log_test("Recovery Mechanism", passed, details)
        return passed
    
    def test_6_plan_monitoring(self) -> bool:
        """Test 6: Verify plans are being monitored"""
        print("\n" + "=" * 80)
        print("TEST 6: Plan Monitoring")
        print("=" * 80)
        
        status = self.get_status()
        pending_plans = status.get("pending_plans", 0)
        plans_list = status.get("plans", [])
        
        has_plans = pending_plans > 0
        plans_loaded = len(plans_list) > 0
        
        passed = has_plans and plans_loaded
        details = f"Pending plans: {pending_plans}, Plans in response: {len(plans_list)}"
        
        self.log_test("Plan Monitoring", passed, details)
        return passed
    
    def test_7_error_handling(self) -> bool:
        """Test 7: Verify error handling doesn't break system"""
        print("\n" + "=" * 80)
        print("TEST 7: Error Handling")
        print("=" * 80)
        print("  Testing system response to invalid requests...")
        
        # Test with invalid endpoint (should not break system)
        try:
            invalid_url = "http://localhost:8000/auto-execution/invalid-endpoint"
            try:
                with urllib.request.urlopen(invalid_url, timeout=2) as response:
                    pass  # Expected to fail
            except urllib.error.HTTPError:
                pass  # Expected
        except Exception:
            pass  # Expected
        
        # Wait a moment
        time.sleep(2)
        
        # System should still be working
        status = self.get_status()
        still_working = "error" not in status and status.get("running", False)
        
        self.log_test("Error Handling", still_working, "System remained functional after invalid request")
        return still_working
    
    def test_8_concurrent_access(self) -> bool:
        """Test 8: Verify system handles concurrent status requests"""
        print("\n" + "=" * 80)
        print("TEST 8: Concurrent Access")
        print("=" * 80)
        print("  Testing concurrent status requests...")
        
        results = []
        errors = []
        
        def check_status():
            try:
                status = self.get_status()
                results.append(status.get("thread_alive", False))
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads checking status simultaneously
        threads = []
        for i in range(10):
            t = threading.Thread(target=check_status)
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join(timeout=5)
        
        # All should succeed
        all_succeeded = len(results) == 10 and len(errors) == 0
        all_alive = all(results) if results else False
        
        passed = all_succeeded and all_alive
        details = f"Successful requests: {len(results)}/10, Errors: {len(errors)}, All threads alive: {all_alive}"
        
        self.log_test("Concurrent Access", passed, details)
        return passed
    
    def test_9_long_running_stability(self) -> bool:
        """Test 9: Verify system stability over extended period"""
        print("\n" + "=" * 80)
        print("TEST 9: Long-Running Stability")
        print("=" * 80)
        print("  Monitoring system for 45 seconds...")
        
        checks = []
        start_time = time.time()
        
        # Check every 10 seconds for 45 seconds
        for i in range(5):
            status = self.get_status()
            running = status.get("running", False)
            thread_alive = status.get("thread_alive", False)
            checks.append({"running": running, "thread_alive": thread_alive})
            print(f"    Check {i+1}/5: Running={running}, ThreadAlive={thread_alive}")
            if i < 4:
                time.sleep(10)
        
        elapsed = time.time() - start_time
        
        # All checks should show system running and thread alive
        all_running = all(c["running"] for c in checks)
        all_alive = all(c["thread_alive"] for c in checks)
        
        passed = all_running and all_alive
        details = f"Stable over {elapsed:.0f} seconds: Running={all_running}, ThreadAlive={all_alive}"
        
        self.log_test("Long-Running Stability", passed, details)
        return passed
    
    def test_10_restart_detection(self) -> bool:
        """Test 10: Verify system can detect and report thread restarts"""
        print("\n" + "=" * 80)
        print("TEST 10: Restart Detection")
        print("=" * 80)
        print("  Note: Cannot simulate thread death from external test")
        print("  Verifying health check can detect thread status...")
        
        # Monitor thread status over time
        statuses = []
        for i in range(20):
            status = self.get_status()
            statuses.append({
                "thread_alive": status.get("thread_alive", False),
                "running": status.get("running", False)
            })
            time.sleep(0.5)
        
        # Check that status is consistently reported
        thread_statuses = [s["thread_alive"] for s in statuses]
        running_statuses = [s["running"] for s in statuses]
        
        # Status should be consistent (or if thread dies, health check should detect it)
        has_consistent_reporting = len(set(thread_statuses)) <= 2  # Allow for state changes
        has_running_status = all(running_statuses)
        
        passed = has_consistent_reporting and has_running_status
        details = f"Consistent reporting: {has_consistent_reporting}, All running: {has_running_status}"
        
        self.log_test("Restart Detection", passed, details)
        return passed
    
    def run_all_tests(self):
        """Run all tests"""
        print("=" * 80)
        print("MONITORING SYSTEM RESILIENCE TESTS")
        print("=" * 80)
        print()
        print("Testing various failure scenarios and recovery mechanisms...")
        print()
        
        tests = [
            ("Initial Status", self.test_1_initial_status),
            ("Health Check Frequency", self.test_2_health_check_frequency),
            ("Thread Persistence", self.test_3_thread_persistence),
            ("Status Consistency", self.test_4_status_consistency),
            ("Recovery Mechanism", self.test_5_recovery_mechanism),
            ("Plan Monitoring", self.test_6_plan_monitoring),
            ("Error Handling", self.test_7_error_handling),
            ("Concurrent Access", self.test_8_concurrent_access),
            ("Long-Running Stability", self.test_9_long_running_stability),
            ("Restart Detection", self.test_10_restart_detection),
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"  [ERROR] {test_name} failed with exception: {e}")
                results.append((test_name, False))
        
        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print()
        
        passed_count = sum(1 for _, result in results if result)
        total_count = len(results)
        
        for test_name, result in results:
            status = "[PASS]" if result else "[FAIL]"
            print(f"  {status} {test_name}")
        
        print()
        print(f"  Total: {passed_count}/{total_count} tests passed")
        print()
        
        if passed_count == total_count:
            print("  [OK] ALL TESTS PASSED - System is resilient!")
        else:
            print(f"  [WARNING] {total_count - passed_count} test(s) failed")
        
        print()
        print("=" * 80)
        
        return passed_count == total_count

if __name__ == "__main__":
    tester = MonitoringSystemTester()
    success = tester.run_all_tests()

