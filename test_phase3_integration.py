"""
Test Phase 3: Integration with Main API

Tests the integration of MicroScalpMonitor with the main API server.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_api_imports():
    """Test 1: Verify API imports work correctly"""
    print("\n" + "="*60)
    print("TEST 1: API Imports")
    print("="*60)
    
    try:
        # Test that main_api can be imported
        from app import main_api
        print("[PASS] main_api imported successfully")
        
        # Test that monitor is accessible
        if hasattr(main_api, 'micro_scalp_monitor'):
            print("[PASS] micro_scalp_monitor accessible in main_api")
        else:
            print("[INFO] micro_scalp_monitor will be initialized on startup")
        
        return True
    except Exception as e:
        print(f"[FAIL] Import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_status_endpoint_exists():
    """Test 2: Verify status endpoint is registered"""
    print("\n" + "="*60)
    print("TEST 2: Status Endpoint")
    print("="*60)
    
    try:
        from app.main_api import app
        
        # Check if endpoint exists
        routes = [route.path for route in app.routes]
        if "/micro-scalp/status" in routes:
            print("[PASS] Status endpoint registered: /micro-scalp/status")
            return True
        else:
            print(f"[FAIL] Status endpoint not found. Available routes: {[r for r in routes if 'micro' in r.lower()]}")
            return False
    except Exception as e:
        print(f"[FAIL] Error checking routes: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_startup_integration():
    """Test 3: Verify startup integration code exists"""
    print("\n" + "="*60)
    print("TEST 3: Startup Integration")
    print("="*60)
    
    try:
        import inspect
        from app.main_api import startup_event
        
        # Get source code
        source = inspect.getsource(startup_event)
        
        checks = [
            ("MicroScalpMonitor" in source, "MicroScalpMonitor initialization"),
            ("micro_scalp_monitor.start()" in source or "micro_scalp_monitor.start()" in source.replace(" ", ""), "Monitor start call"),
            ("micro_scalp_engine" in source, "Engine initialization"),
            ("micro_scalp_execution" in source, "Execution manager initialization"),
        ]
        
        all_passed = True
        for check, description in checks:
            if check:
                print(f"[PASS] {description} found in startup_event")
            else:
                print(f"[FAIL] {description} not found in startup_event")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_shutdown_integration():
    """Test 4: Verify shutdown integration code exists"""
    print("\n" + "="*60)
    print("TEST 4: Shutdown Integration")
    print("="*60)
    
    try:
        import inspect
        from app.main_api import shutdown_event
        
        # Get source code
        source = inspect.getsource(shutdown_event)
        
        if "micro_scalp_monitor" in source and "stop()" in source:
            print("[PASS] Monitor stop call found in shutdown_event")
            return True
        else:
            print("[FAIL] Monitor stop call not found in shutdown_event")
            return False
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_endpoint_response_format():
    """Test 5: Verify endpoint returns correct format"""
    print("\n" + "="*60)
    print("TEST 5: Endpoint Response Format")
    print("="*60)
    
    try:
        import inspect
        from app.main_api import get_micro_scalp_status
        
        # Get source code
        source = inspect.getsource(get_micro_scalp_status)
        
        checks = [
            ("ok" in source, "Response includes 'ok' field"),
            ("status" in source, "Response includes 'status' field"),
            ("timestamp" in source, "Response includes 'timestamp' field"),
        ]
        
        all_passed = True
        for check, description in checks:
            if check:
                print(f"[PASS] {description}")
            else:
                print(f"[FAIL] {description}")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all Phase 3 integration tests"""
    print("\n" + "="*60)
    print("PHASE 3: API INTEGRATION TEST")
    print("="*60)
    
    tests = [
        ("API Imports", test_api_imports),
        ("Status Endpoint", test_status_endpoint_exists),
        ("Startup Integration", test_startup_integration),
        ("Shutdown Integration", test_shutdown_integration),
        ("Endpoint Response Format", test_endpoint_response_format),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"[FAIL] {test_name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All Phase 3 integration tests passed!")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

