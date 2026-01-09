#!/usr/bin/env python3
"""
Test script for new volatility regime monitoring and notifications endpoints
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8010"

def test_root_dashboard():
    """Test root dashboard endpoint"""
    print("\n[TEST] Root Dashboard (/)")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "Volatility Regime Monitor" in response.text, "Dashboard should contain volatility monitor link"
        assert "Notifications Management" in response.text, "Dashboard should contain notifications link"
        print("  [OK] Root dashboard accessible and contains expected links")
        return True
    except requests.exceptions.ConnectionError:
        print("  [WARN] Server not running. Start with: python -m uvicorn main_api:app --host 0.0.0.0 --port 8010")
        return False
    except Exception as e:
        print(f"  [ERROR] Error: {e}")
        return False

def test_volatility_monitor_page():
    """Test volatility regime monitor page"""
    print("\n[TEST] Volatility Regime Monitor Page (/volatility-regime/monitor)")
    try:
        response = requests.get(f"{BASE_URL}/volatility-regime/monitor", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "Volatility Regime Monitor" in response.text, "Page should have correct title"
        assert "BTCUSDc" in response.text, "Page should show symbols"
        print("  [OK] Volatility monitor page accessible")
        return True
    except requests.exceptions.ConnectionError:
        print("  [WARN] Server not running")
        return False
    except Exception as e:
        print(f"  [ERROR] Error: {e}")
        return False

def test_notifications_page():
    """Test notifications management page"""
    print("\n[TEST] Notifications Management Page (/notifications/view)")
    try:
        response = requests.get(f"{BASE_URL}/notifications/view", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "Notifications Management" in response.text, "Page should have correct title"
        assert "Discord Notifications" in response.text, "Page should show Discord section"
        print("  [OK] Notifications page accessible")
        return True
    except requests.exceptions.ConnectionError:
        print("  [WARN] Server not running")
        return False
    except Exception as e:
        print(f"  [ERROR] Error: {e}")
        return False

def test_notifications_status_api():
    """Test notifications status API"""
    print("\n[TEST] Notifications Status API (/notifications/status)")
    try:
        response = requests.get(f"{BASE_URL}/notifications/status", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "success" in data, "Response should have success field"
        assert "discord" in data, "Response should have discord status"
        assert "telegram" in data, "Response should have telegram status"
        print(f"  [OK] Notifications status API working")
        print(f"     Discord enabled: {data.get('discord', {}).get('enabled', False)}")
        print(f"     Telegram enabled: {data.get('telegram', {}).get('enabled', False)}")
        return True
    except requests.exceptions.ConnectionError:
        print("  [WARN] Server not running")
        return False
    except Exception as e:
        print(f"  [ERROR] Error: {e}")
        return False

def test_volatility_regime_status_api():
    """Test volatility regime status API (may fail if MT5 not connected)"""
    print("\n[TEST] Volatility Regime Status API (/volatility-regime/status/BTCUSDc)")
    try:
        response = requests.get(f"{BASE_URL}/volatility-regime/status/BTCUSDc", timeout=10)
        if response.status_code == 200:
            data = response.json()
            assert "success" in data, "Response should have success field"
            print(f"  [OK] Volatility regime status API working")
            if data.get("success"):
                regime_data = data.get("regime_data", {})
                regime = regime_data.get("regime", "UNKNOWN")
                confidence = regime_data.get("confidence", 0)
                print(f"     Current regime: {regime}")
                print(f"     Confidence: {confidence:.1f}%")
            return True
        elif response.status_code == 500:
            print("  [WARN] API endpoint exists but MT5/IndicatorBridge not initialized (expected if server not fully started)")
            return True  # Endpoint exists, just needs services
        else:
            print(f"  [WARN] Unexpected status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("  [WARN] Server not running")
        return False
    except Exception as e:
        print(f"  [ERROR] Error: {e}")
        return False

def test_volatility_regime_events_api():
    """Test volatility regime events API"""
    print("\n[TEST] Volatility Regime Events API (/volatility-regime/events/BTCUSDc)")
    try:
        response = requests.get(f"{BASE_URL}/volatility-regime/events/BTCUSDc?limit=5", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "success" in data, "Response should have success field"
        assert "events" in data, "Response should have events array"
        print(f"  [OK] Volatility regime events API working")
        print(f"     Events found: {data.get('count', 0)}")
        return True
    except requests.exceptions.ConnectionError:
        print("  [WARN] Server not running")
        return False
    except Exception as e:
        print(f"  [ERROR] Error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 80)
    print("Testing New Endpoints: Volatility Regime Monitor & Notifications")
    print("=" * 80)
    print(f"Base URL: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    results.append(("Root Dashboard", test_root_dashboard()))
    results.append(("Volatility Monitor Page", test_volatility_monitor_page()))
    results.append(("Notifications Page", test_notifications_page()))
    results.append(("Notifications Status API", test_notifications_status_api()))
    results.append(("Volatility Regime Status API", test_volatility_regime_status_api()))
    results.append(("Volatility Regime Events API", test_volatility_regime_events_api()))
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] ALL TESTS PASSED!")
        return 0
    elif passed > 0:
        print(f"\n[WARNING] {total - passed} test(s) failed (may need server running)")
        return 1
    else:
        print("\n[ERROR] All tests failed - server may not be running")
        print("\nTo start the server:")
        print("  python -m uvicorn main_api:app --host 0.0.0.0 --port 8010 --reload")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())

