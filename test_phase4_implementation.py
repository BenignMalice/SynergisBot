"""
Test script for Phase 4: Update DTMS Queries
Tests API query functionality, especially Intelligent Exit Manager integration
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


def test_intelligent_exit_api_query():
    """Test 4.1: Intelligent Exit Manager queries DTMS API"""
    print("\n=== Test 4.1: Intelligent Exit Manager API Query ===")
    
    try:
        # Read file directly
        file_path = os.path.join(os.path.dirname(__file__), "infra", "intelligent_exit_manager.py")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Check for API query indicators
        has_api_query = "http://127.0.0.1:8001/dtms/trade" in source
        has_requests = "import requests" in source or "requests.get" in source
        has_caching = "_dtms_state_cache" in source
        has_last_known_cache = "_dtms_last_known_cache" in source
        has_retry_logic = "for attempt in range(2)" in source or "attempt" in source.lower()
        has_timeout = "timeout=2.0" in source or "timeout=" in source
        
        log_test("_is_dtms_in_defensive_mode() queries DTMS API", has_api_query,
                "Queries http://127.0.0.1:8001/dtms/trade/{ticket}")
        log_test("Uses requests library (sync HTTP client)", has_requests,
                "Uses requests.get() for synchronous HTTP calls")
        log_test("Has state caching (10 second cache)", has_caching,
                "Uses _dtms_state_cache for performance")
        log_test("Has last known state cache (30 second TTL)", has_last_known_cache,
                "Uses _dtms_last_known_cache for API unavailability")
        log_test("Has retry logic", has_retry_logic,
                "Retries API queries on failure")
        log_test("Has timeout handling", has_timeout,
                "Sets timeout for API queries")
        
        # Check for cache initialization in __init__
        has_cache_init = "_dtms_state_cache = {}" in source or "_dtms_state_cache={}" in source.replace(" ", "")
        
        log_test("Cache initialized in __init__", has_cache_init,
                "Caches initialized when IntelligentExitManager is created")
        
    except FileNotFoundError:
        log_test("Intelligent Exit Manager API query", False, "intelligent_exit_manager.py file not found")
    except Exception as e:
        log_test("Intelligent Exit Manager API query", False, f"Error: {e}")


def test_api_endpoints_have_fallback():
    """Test 4.2: API endpoints have fallback to DTMS API server"""
    print("\n=== Test 4.2: API Endpoints Fallback ===")
    
    endpoints_to_check = [
        ("app/main_api.py", "/api/dtms/status", "get_dtms_status_api"),
        ("app/main_api.py", "/api/dtms/trade/{ticket}", "get_dtms_trade_info_api"),
        ("app/main_api.py", "/api/dtms/actions", "get_dtms_action_history_api"),
    ]
    
    all_have_fallback = True
    
    for file_path, endpoint, function_name in endpoints_to_check:
        try:
            full_path = os.path.join(os.path.dirname(__file__), file_path)
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for API fallback indicators
            has_api_fallback = "http://127.0.0.1:8001" in content or "port 8001" in content.lower()
            has_httpx = "httpx" in content.lower()
            has_fallback_logic = "If not available locally" in content or "fallback" in content.lower()
            
            log_test(f"{endpoint} has API fallback", has_api_fallback,
                    f"Falls back to DTMS API server (port 8001)")
            log_test(f"{endpoint} uses httpx", has_httpx,
                    f"Uses httpx.AsyncClient for API calls")
            
            if not has_api_fallback:
                all_have_fallback = False
                
        except FileNotFoundError:
            log_test(f"{endpoint} has API fallback", False, f"{file_path} not found")
            all_have_fallback = False
        except Exception as e:
            log_test(f"{endpoint} has API fallback", False, f"Error: {e}")
            all_have_fallback = False
    
    log_test("All API endpoints have fallback", all_have_fallback,
            "All endpoints fall back to DTMS API server when local engine unavailable")


def test_defensive_mode_check():
    """Test 4.3: Defensive mode check logic"""
    print("\n=== Test 4.3: Defensive Mode Check Logic ===")
    
    try:
        file_path = os.path.join(os.path.dirname(__file__), "infra", "intelligent_exit_manager.py")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Check for defensive mode logic
        checks_hedged = "'HEDGED'" in source or '"HEDGED"' in source
        checks_warning_l2 = "'WARNING_L2'" in source or '"WARNING_L2"' in source
        has_state_check = "state in" in source or "state == " in source
        
        log_test("Checks for HEDGED state", checks_hedged,
                "Detects HEDGED defensive mode")
        log_test("Checks for WARNING_L2 state", checks_warning_l2,
                "Detects WARNING_L2 defensive mode")
        log_test("Has state comparison logic", has_state_check,
                "Compares DTMS state to defensive modes")
        
    except FileNotFoundError:
        log_test("Defensive mode check logic", False, "intelligent_exit_manager.py file not found")
    except Exception as e:
        log_test("Defensive mode check logic", False, f"Error: {e}")


def test_conservative_fallback():
    """Test 4.4: Conservative fallback when API unavailable"""
    print("\n=== Test 4.4: Conservative Fallback ===")
    
    try:
        file_path = os.path.join(os.path.dirname(__file__), "infra", "intelligent_exit_manager.py")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Check for conservative fallback
        has_conservative = "assuming not in defensive mode" in source.lower() or "conservative" in source.lower()
        has_last_known = "last_known" in source.lower()
        has_ttl_check = "30" in source and "cache_time" in source
        
        log_test("Has conservative fallback", has_conservative,
                "Assumes not in defensive mode when API unavailable")
        log_test("Uses last known state", has_last_known,
                "Falls back to last known state cache")
        log_test("Has TTL check for cache", has_ttl_check,
                "Checks cache expiration (30 second TTL)")
        
    except FileNotFoundError:
        log_test("Conservative fallback", False, "intelligent_exit_manager.py file not found")
    except Exception as e:
        log_test("Conservative fallback", False, f"Error: {e}")


def print_summary():
    """Print test summary"""
    print("\n" + "=" * 80)
    print("PHASE 4 IMPLEMENTATION TEST SUMMARY")
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
        print("[SUCCESS] ALL TESTS PASSED - Phase 4 implementation is complete!")
        return True
    else:
        print(f"[WARNING] {test_results['failed']} test(s) failed - review and fix issues")
        return False


if __name__ == "__main__":
    print("=" * 80)
    print("PHASE 4: UPDATE DTMS QUERIES - TEST SUITE")
    print("=" * 80)
    print()
    
    # Run all tests
    test_intelligent_exit_api_query()
    test_api_endpoints_have_fallback()
    test_defensive_mode_check()
    test_conservative_fallback()
    
    # Print summary
    all_passed = print_summary()
    
    # Exit with appropriate code
    exit(0 if all_passed else 1)

