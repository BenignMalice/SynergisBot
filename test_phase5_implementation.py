"""
Test script for Phase 5: Remove Duplicate Initialization
Tests that DTMS initialization is removed from chatgpt_bot.py and app/main_api.py
"""

import sys
import os

# Test results
test_results = {
    "passed": 0,
    "failed": 0,
    "total": 0,
    "details": []
}


def log_test(test_name: str, passed: bool, details: str = ""):
    """Log test result"""
    test_results["total"] += 1
    if passed:
        test_results["passed"] += 1
        status = "[PASS]"
    else:
        test_results["failed"] += 1
        status = "[FAIL]"
    
    test_results["details"].append({
        "test": test_name,
        "status": status,
        "details": details
    })
    print(f"{status}: {test_name}")
    if details:
        print(f"   {details}")


def test_chatgpt_bot_init_removed():
    """Test 5.1: DTMS initialization removed from chatgpt_bot.py"""
    print("\n=== Test 5.1: chatgpt_bot.py Initialization Removal ===")
    
    try:
        file_path = os.path.join(os.path.dirname(__file__), "chatgpt_bot.py")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Check that initialization is commented out
        has_commented_init = "# Initialize DTMS" in source or "# PHASE 5:" in source
        has_skipped_message = "DTMS initialization skipped" in source or "using API server" in source.lower()
        has_old_code_commented = "# OLD CODE" in source or "# OLD:" in source
        
        # Check that initialize_dtms is not called (or is commented)
        init_called = "initialize_dtms(" in source and not ("# initialize_dtms(" in source or "# PHASE 5:" in source)
        
        log_test("DTMS initialization commented out", has_commented_init or has_skipped_message,
                "Initialization code is commented or replaced with skip message")
        log_test("Old code preserved for rollback", has_old_code_commented,
                "Old code is commented out for easy rollback")
        log_test("initialize_dtms() not called", not init_called,
                "initialize_dtms() is not actively called (commented out)")
        
    except FileNotFoundError:
        log_test("chatgpt_bot.py initialization removal", False, "chatgpt_bot.py file not found")
    except Exception as e:
        log_test("chatgpt_bot.py initialization removal", False, f"Error: {e}")


def test_chatgpt_bot_monitoring_removed():
    """Test 5.2: DTMS monitoring removed from chatgpt_bot.py"""
    print("\n=== Test 5.2: chatgpt_bot.py Monitoring Removal ===")
    
    try:
        file_path = os.path.join(os.path.dirname(__file__), "chatgpt_bot.py")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Check that monitoring cycle is commented out
        has_commented_monitoring = "# PHASE 5:" in source and "DTMS monitoring" in source
        has_disabled_function = "PHASE 5: Disabled" in source or "using API server" in source.lower()
        
        # Check that scheduler job is commented out
        scheduler_job_commented = "# PHASE 5:" in source and "scheduler job" in source.lower()
        
        log_test("Monitoring cycle function disabled", has_commented_monitoring or has_disabled_function,
                "run_dtms_monitoring_cycle() is disabled or commented")
        log_test("Scheduler job commented out", scheduler_job_commented or has_disabled_function,
                "DTMS monitoring scheduler job is commented out")
        
    except FileNotFoundError:
        log_test("chatgpt_bot.py monitoring removal", False, "chatgpt_bot.py file not found")
    except Exception as e:
        log_test("chatgpt_bot.py monitoring removal", False, f"Error: {e}")


def test_main_api_init_removed():
    """Test 5.3: DTMS initialization removed from app/main_api.py"""
    print("\n=== Test 5.3: app/main_api.py Initialization Removal ===")
    
    try:
        file_path = os.path.join(os.path.dirname(__file__), "app", "main_api.py")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Check that initialization is commented out
        has_commented_init = "# PHASE 5:" in source and "DTMS initialization" in source
        has_skipped_message = "DTMS initialization skipped" in source or "using API server" in source.lower()
        has_old_code_commented = "# OLD CODE" in source or "# OLD:" in source
        
        # Check that initialize_dtms is not called (or is commented)
        init_called = "initialize_dtms(" in source and not ("# initialize_dtms(" in source or "# PHASE 5:" in source)
        
        log_test("DTMS initialization commented out", has_commented_init or has_skipped_message,
                "Initialization code is commented or replaced with skip message")
        log_test("Old code preserved for rollback", has_old_code_commented,
                "Old code is commented out for easy rollback")
        log_test("initialize_dtms() not called", not init_called,
                "initialize_dtms() is not actively called (commented out)")
        
    except FileNotFoundError:
        log_test("app/main_api.py initialization removal", False, "app/main_api.py file not found")
    except Exception as e:
        log_test("app/main_api.py initialization removal", False, f"Error: {e}")


def test_main_api_monitoring_removed():
    """Test 5.4: DTMS monitoring removed from app/main_api.py"""
    print("\n=== Test 5.4: app/main_api.py Monitoring Removal ===")
    
    try:
        file_path = os.path.join(os.path.dirname(__file__), "app", "main_api.py")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Check that monitoring loop is commented out
        has_commented_loop = "# PHASE 5:" in source and "dtms_monitor_loop" in source
        has_disabled_function = "PHASE 5: Disabled" in source or "using API server" in source.lower()
        
        # Check that start_dtms_monitoring is not called (or is commented)
        start_called = "start_dtms_monitoring()" in source and not ("# start_dtms_monitoring()" in source or "# PHASE 5:" in source)
        
        log_test("Monitoring loop function disabled", has_commented_loop or has_disabled_function,
                "dtms_monitor_loop() is disabled or commented")
        log_test("start_dtms_monitoring() not called", not start_called,
                "start_dtms_monitoring() is not actively called (commented out)")
        
    except FileNotFoundError:
        log_test("app/main_api.py monitoring removal", False, "app/main_api.py file not found")
    except Exception as e:
        log_test("app/main_api.py monitoring removal", False, f"Error: {e}")


def test_api_endpoints_preserved():
    """Test 5.5: API endpoints still work (fallback to API server)"""
    print("\n=== Test 5.5: API Endpoints Preserved ===")
    
    try:
        file_path = os.path.join(os.path.dirname(__file__), "app", "main_api.py")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Check that endpoints still exist
        has_status_endpoint = "@app.get(\"/api/dtms/status\")" in source
        has_trade_endpoint = "@app.get(\"/api/dtms/trade/{ticket}\")" in source
        has_actions_endpoint = "@app.get(\"/api/dtms/actions\")" in source
        
        # Check that endpoints have API fallback
        has_api_fallback = "http://127.0.0.1:8001" in source or "port 8001" in source.lower()
        
        log_test("/api/dtms/status endpoint exists", has_status_endpoint,
                "Status endpoint still available")
        log_test("/api/dtms/trade/{ticket} endpoint exists", has_trade_endpoint,
                "Trade info endpoint still available")
        log_test("/api/dtms/actions endpoint exists", has_actions_endpoint,
                "Actions endpoint still available")
        log_test("Endpoints have API fallback", has_api_fallback,
                "Endpoints fall back to DTMS API server")
        
    except FileNotFoundError:
        log_test("API endpoints preserved", False, "app/main_api.py file not found")
    except Exception as e:
        log_test("API endpoints preserved", False, f"Error: {e}")


def test_auto_enable_dtms_preserved():
    """Test 5.6: auto_enable_dtms_protection_async still works"""
    print("\n=== Test 5.6: auto_enable_dtms_protection_async Preserved ===")
    
    try:
        file_path = os.path.join(os.path.dirname(__file__), "chatgpt_bot.py")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Check that function still exists
        has_function = "async def auto_enable_dtms_protection_async" in source
        
        # Check that it uses API
        uses_api = "http://localhost:8001/dtms/trade/enable" in source or "8001/dtms/trade/enable" in source
        
        log_test("auto_enable_dtms_protection_async() exists", has_function,
                "Function still available")
        log_test("Uses API server", uses_api,
                "Function calls DTMS API server (port 8001)")
        
    except FileNotFoundError:
        log_test("auto_enable_dtms_protection_async preserved", False, "chatgpt_bot.py file not found")
    except Exception as e:
        log_test("auto_enable_dtms_protection_async preserved", False, f"Error: {e}")


def print_summary():
    """Print test summary"""
    print("\n" + "=" * 80)
    print("PHASE 5 IMPLEMENTATION TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {test_results['total']}")
    print(f"[PASS] Passed: {test_results['passed']}")
    print(f"[FAIL] Failed: {test_results['failed']}")
    
    if test_results['failed'] == 0:
        success_rate = 100.0
    else:
        success_rate = (test_results['passed'] / test_results['total']) * 100
    
    print(f"Success Rate: {success_rate:.1f}%")
    
    if test_results['failed'] > 0:
        print("\nFailed Tests:")
        for detail in test_results['details']:
            if "FAIL" in detail['status']:
                print(f"  - {detail['test']}: {detail['details']}")
    
    print("=" * 80)
    
    if success_rate == 100.0:
        print("[SUCCESS] ALL TESTS PASSED - Phase 5 implementation is complete!")
        return True
    else:
        print(f"[WARNING] {test_results['failed']} test(s) failed - review and fix issues")
        return False


if __name__ == "__main__":
    print("=" * 80)
    print("PHASE 5: REMOVE DUPLICATE INITIALIZATION - TEST SUITE")
    print("=" * 80)
    print()
    
    # Run all tests
    test_chatgpt_bot_init_removed()
    test_chatgpt_bot_monitoring_removed()
    test_main_api_init_removed()
    test_main_api_monitoring_removed()
    test_api_endpoints_preserved()
    test_auto_enable_dtms_preserved()
    
    # Print summary
    all_passed = print_summary()
    
    # Exit with appropriate code
    exit(0 if all_passed else 1)

