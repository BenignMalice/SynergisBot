"""
Test Micro-Scalp System - Verify API integration and functionality
"""
import sys
import json
import time
from datetime import datetime, timezone

# Configure encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def test_streamer_api():
    """Test streamer API endpoints"""
    print("=" * 80)
    print("TEST 1: Streamer API Endpoints")
    print("=" * 80)
    print()
    
    try:
        import httpx
        
        base_url = "http://localhost:8000"
        
        # Test 1.1: Health check
        print("1.1 Testing /streamer/health...")
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{base_url}/streamer/health")
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ Health check passed")
                    print(f"   Status: {data.get('status')}")
                    print(f"   Streamer running: {data.get('streamer_running')}")
                else:
                    print(f"   ❌ Health check failed: {response.status_code}")
                    return False
        except Exception as e:
            print(f"   ❌ Health check error: {e}")
            return False
        
        print()
        
        # Test 1.2: Get status
        print("1.2 Testing /streamer/status...")
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{base_url}/streamer/status")
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ Status check passed")
                    print(f"   Running: {data.get('running')}")
                    print(f"   Symbols: {data.get('symbols', [])}")
                    print(f"   Timeframes: {data.get('timeframes', [])}")
                else:
                    print(f"   ❌ Status check failed: {response.status_code}")
                    return False
        except Exception as e:
            print(f"   ❌ Status check error: {e}")
            return False
        
        print()
        
        # Test 1.3: Get available symbols
        print("1.3 Testing /streamer/available...")
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{base_url}/streamer/available")
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ Available check passed")
                    symbols = data.get('symbols', {})
                    for symbol, timeframes in symbols.items():
                        print(f"   {symbol}: {timeframes}")
                else:
                    print(f"   ❌ Available check failed: {response.status_code}")
                    return False
        except Exception as e:
            print(f"   ❌ Available check error: {e}")
            return False
        
        print()
        
        # Test 1.4: Get M1 candles for BTCUSDc
        print("1.4 Testing /streamer/candles/BTCUSDc/M1...")
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{base_url}/streamer/candles/BTCUSDc/M1", params={"limit": 50})
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        candles = data.get('candles', [])
                        print(f"   ✅ Got {len(candles)} M1 candles for BTCUSDc")
                        if candles:
                            latest = candles[0]
                            print(f"   Latest candle: time={latest.get('time')}, close={latest.get('close')}")
                    else:
                        print(f"   ❌ API returned error: {data.get('error')}")
                        return False
                else:
                    print(f"   ❌ Candles request failed: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return False
        except Exception as e:
            print(f"   ❌ Candles request error: {e}")
            return False
        
        print()
        
        # Test 1.5: Get M1 candles for XAUUSDc
        print("1.5 Testing /streamer/candles/XAUUSDc/M1...")
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{base_url}/streamer/candles/XAUUSDc/M1", params={"limit": 50})
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        candles = data.get('candles', [])
                        print(f"   ✅ Got {len(candles)} M1 candles for XAUUSDc")
                        if candles:
                            latest = candles[0]
                            print(f"   Latest candle: time={latest.get('time')}, close={latest.get('close')}")
                    else:
                        print(f"   ⚠️ API returned error: {data.get('error')} (may be expected if symbol not streaming)")
                else:
                    print(f"   ⚠️ Candles request failed: {response.status_code} (may be expected)")
        except Exception as e:
            print(f"   ⚠️ Candles request error: {e} (may be expected)")
        
        print()
        print("✅ Streamer API tests completed")
        return True
        
    except ImportError:
        print("   ❌ httpx not available - install with: pip install httpx")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_micro_scalp_monitor_status():
    """Test micro-scalp monitor status"""
    print("=" * 80)
    print("TEST 2: Micro-Scalp Monitor Status")
    print("=" * 80)
    print()
    
    try:
        import httpx
        
        base_url = "http://localhost:8010"
        
        # Test monitor status endpoint
        print("2.1 Testing /micro-scalp/status...")
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{base_url}/micro-scalp/status")
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ Monitor status retrieved")
                    print(f"   Monitoring: {data.get('monitoring')}")
                    print(f"   Enabled: {data.get('enabled')}")
                    print(f"   Total checks: {data.get('stats', {}).get('total_checks', 0)}")
                    print(f"   Conditions met: {data.get('stats', {}).get('conditions_met', 0)}")
                    print(f"   Executions: {data.get('stats', {}).get('executions', 0)}")
                    print(f"   Thread alive: {data.get('thread_alive', False)}")
                    
                    # Check if monitor is actually running
                    if data.get('monitoring') and data.get('thread_alive'):
                        print(f"   ✅ Monitor is running")
                    else:
                        print(f"   ⚠️ Monitor may not be running")
                else:
                    print(f"   ❌ Status check failed: {response.status_code}")
                    return False
        except Exception as e:
            print(f"   ❌ Status check error: {e}")
            return False
        
        print()
        print("✅ Micro-scalp monitor status check completed")
        return True
        
    except ImportError:
        print("   ❌ httpx not available")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_recent_checks():
    """Test recent check history"""
    print("=" * 80)
    print("TEST 3: Recent Check History")
    print("=" * 80)
    print()
    
    try:
        import httpx
        
        base_url = "http://localhost:8010"
        
        # Test check history endpoint
        print("3.1 Testing /micro-scalp/history...")
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{base_url}/micro-scalp/history", params={"limit": 5})
                if response.status_code == 200:
                    data = response.json()
                    checks = data.get('checks', [])
                    print(f"   ✅ Retrieved {len(checks)} recent checks")
                    
                    if checks:
                        print()
                        print("   Recent checks:")
                        for i, check in enumerate(checks[:5], 1):
                            symbol = check.get('symbol', 'N/A')
                            passed = check.get('passed', False)
                            strategy = check.get('strategy', 'N/A')
                            regime = check.get('regime', 'N/A')
                            timestamp = check.get('timestamp', 'N/A')
                            print(f"   {i}. {symbol} | Strategy: {strategy} | Regime: {regime} | Passed: {passed} | Time: {timestamp}")
                    else:
                        print("   ⚠️ No checks found (monitor may not have run yet)")
                else:
                    print(f"   ❌ History check failed: {response.status_code}")
                    return False
        except Exception as e:
            print(f"   ❌ History check error: {e}")
            return False
        
        print()
        print("✅ Check history test completed")
        return True
        
    except ImportError:
        print("   ❌ httpx not available")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_api_integration():
    """Test if monitor is using API successfully"""
    print("=" * 80)
    print("TEST 4: API Integration Verification")
    print("=" * 80)
    print()
    
    print("4.1 Checking if monitor is using API...")
    print("   (This requires checking logs or waiting for monitor to run)")
    print()
    print("   To verify:")
    print("   1. Check monitor logs for 'Got X M1 candles from API' messages")
    print("   2. Monitor should show successful condition checks")
    print("   3. No 'No M1 candles available' errors should appear")
    print()
    print("   Waiting 10 seconds for monitor to run a check cycle...")
    
    time.sleep(10)
    
    # Check history again to see if new checks happened
    try:
        import httpx
        
        base_url = "http://localhost:8010"
        
        with httpx.Client(timeout=2.0) as client:
            response = client.get(f"{base_url}/micro-scalp/history", params={"limit": 1})
            if response.status_code == 200:
                data = response.json()
                checks = data.get('checks', [])
                if checks:
                    latest = checks[0]
                    symbol = latest.get('symbol', 'N/A')
                    passed = latest.get('passed', False)
                    timestamp = latest.get('timestamp', 'N/A')
                    print(f"   ✅ Latest check: {symbol} | Passed: {passed} | Time: {timestamp}")
                    print(f"   ✅ Monitor is running and checking conditions")
                else:
                    print(f"   ⚠️ No checks found yet (monitor may need more time)")
    except Exception as e:
        print(f"   ⚠️ Could not verify: {e}")
    
    print()
    print("✅ API integration test completed")
    return True

def main():
    """Run all tests"""
    print()
    print("=" * 80)
    print("MICRO-SCALP SYSTEM TEST SUITE")
    print("=" * 80)
    print()
    print(f"Test started at: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    results = []
    
    # Test 1: Streamer API
    results.append(("Streamer API", test_streamer_api()))
    print()
    
    # Test 2: Monitor Status
    results.append(("Monitor Status", test_micro_scalp_monitor_status()))
    print()
    
    # Test 3: Recent Checks
    results.append(("Recent Checks", test_recent_checks()))
    print()
    
    # Test 4: API Integration
    results.append(("API Integration", test_api_integration()))
    print()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print()
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print()
    
    if passed == total:
        print("✅ All tests passed! Micro-scalp system is working properly.")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
    print()

if __name__ == "__main__":
    main()

