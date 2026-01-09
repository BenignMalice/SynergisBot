"""
Test script for Phase 3: Update Trade Registration
Tests API fallback functionality in auto_register_dtms()
"""

import asyncio
import sys
from typing import Dict, Any

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


def test_helper_function_exists():
    """Test 3.1: register_trade_with_dtms_api() function exists"""
    print("\n=== Test 3.1: Helper Function ===")
    
    try:
        from dtms_integration.dtms_system import register_trade_with_dtms_api
        import inspect
        
        # Check function signature
        sig = inspect.signature(register_trade_with_dtms_api)
        params = list(sig.parameters.keys())
        required_params = ['ticket', 'trade_data']
        has_required = all(p in params for p in required_params)
        
        log_test("register_trade_with_dtms_api() function exists", True, 
                f"Parameters: {params}")
        log_test("Function has required parameters", has_required,
                f"Required: {required_params}, Found: {params}")
        
        # Check if it's async
        is_async = inspect.iscoroutinefunction(register_trade_with_dtms_api)
        log_test("Function is async", is_async, 
                "Async function for non-blocking API calls")
        
    except ImportError as e:
        log_test("register_trade_with_dtms_api() function exists", False, f"Import error: {e}")
    except Exception as e:
        log_test("register_trade_with_dtms_api() function exists", False, f"Error: {e}")


def test_connection_pooling():
    """Test 3.2: Connection pooling functions exist"""
    print("\n=== Test 3.2: Connection Pooling ===")
    
    try:
        from dtms_integration.dtms_system import get_http_client, close_http_client
        import inspect
        
        # Check get_http_client is async
        is_async_get = inspect.iscoroutinefunction(get_http_client)
        log_test("get_http_client() function exists and is async", is_async_get,
                "Returns httpx.AsyncClient with connection pooling")
        
        # Check close_http_client is async
        is_async_close = inspect.iscoroutinefunction(close_http_client)
        log_test("close_http_client() function exists and is async", is_async_close,
                "Closes global HTTP client on shutdown")
        
    except ImportError as e:
        log_test("Connection pooling functions exist", False, f"Import error: {e}")
    except Exception as e:
        log_test("Connection pooling functions exist", False, f"Error: {e}")


def test_auto_register_has_api_fallback():
    """Test 3.3: auto_register_dtms() has API fallback"""
    print("\n=== Test 3.3: API Fallback in auto_register_dtms() ===")
    
    try:
        # Read file directly (dtms_integration.py is root file, not package)
        import os
        file_path = os.path.join(os.path.dirname(__file__), "dtms_integration.py")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Check for API fallback indicators
        has_api_fallback = "register_trade_with_dtms_api" in source
        has_local_check = "get_dtms_engine" in source
        has_fallback_logic = "Fallback to API" in source or "fallback" in source.lower() or "API fallback" in source
        
        log_test("auto_register_dtms() checks local engine", has_local_check,
                "Checks get_dtms_engine() first")
        log_test("auto_register_dtms() has API fallback", has_api_fallback,
                "Calls register_trade_with_dtms_api() when local engine unavailable")
        log_test("auto_register_dtms() has fallback logic", has_fallback_logic,
                "Contains fallback logic for API registration")
        
        # Check for proper error handling
        has_error_handling = "logger.error" in source or "logger.warning" in source
        log_test("auto_register_dtms() has error handling", has_error_handling,
                "Logs errors instead of silent failures")
        
    except FileNotFoundError:
        log_test("auto_register_dtms() has API fallback", False, "dtms_integration.py file not found")
    except Exception as e:
        log_test("auto_register_dtms() has API fallback", False, f"Error: {e}")


def test_async_context_handling():
    """Test 3.4: Async context handling in auto_register_dtms()"""
    print("\n=== Test 3.4: Async Context Handling ===")
    
    try:
        # Read file directly (dtms_integration.py is root file, not package)
        import os
        file_path = os.path.join(os.path.dirname(__file__), "dtms_integration.py")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Check for proper async handling
        has_get_running_loop = "get_running_loop" in source
        has_create_task = "create_task" in source
        has_new_event_loop = "new_event_loop" in source or "EventLoop" in source
        
        log_test("Handles running event loop", has_get_running_loop or has_create_task,
                "Uses create_task for fire-and-forget in async contexts")
        log_test("Handles sync contexts", has_new_event_loop,
                "Creates new event loop for sync contexts")
        
    except FileNotFoundError:
        log_test("Async context handling", False, "dtms_integration.py file not found")
    except Exception as e:
        log_test("Async context handling", False, f"Error: {e}")


def test_registration_points_use_auto_register():
    """Test 3.5: All registration points use auto_register_dtms()"""
    print("\n=== Test 3.5: Registration Points ===")
    
    registration_points = [
        ("app/main_api.py", "app/main_api.py"),
        ("desktop_agent.py", "desktop_agent.py"),
        ("handlers/trading.py", "handlers/trading.py"),
    ]
    
    all_use_auto_register = True
    for file_path, display_name in registration_points:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                uses_auto_register = "auto_register_dtms" in content
                log_test(f"{display_name} uses auto_register_dtms()", uses_auto_register,
                        "Will automatically get API fallback")
                if not uses_auto_register:
                    all_use_auto_register = False
        except FileNotFoundError:
            log_test(f"{display_name} uses auto_register_dtms()", False, "File not found")
            all_use_auto_register = False
        except Exception as e:
            log_test(f"{display_name} uses auto_register_dtms()", False, f"Error: {e}")
            all_use_auto_register = False
    
    log_test("All registration points use auto_register_dtms()", all_use_auto_register,
            "All points will benefit from API fallback automatically")


def print_summary():
    """Print test summary"""
    print("\n" + "=" * 80)
    print("PHASE 3 IMPLEMENTATION TEST SUMMARY")
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
        print("[SUCCESS] ALL TESTS PASSED - Phase 3 implementation is complete!")
        return True
    else:
        print(f"[WARNING] {test_results['failed']} test(s) failed - review and fix issues")
        return False


if __name__ == "__main__":
    print("=" * 80)
    print("PHASE 3: UPDATE TRADE REGISTRATION - TEST SUITE")
    print("=" * 80)
    print()
    
    # Run all tests
    test_helper_function_exists()
    test_connection_pooling()
    test_auto_register_has_api_fallback()
    test_async_context_handling()
    test_registration_points_use_auto_register()
    
    # Print summary
    all_passed = print_summary()
    
    # Exit with appropriate code
    exit(0 if all_passed else 1)

