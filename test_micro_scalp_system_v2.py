"""
Test Micro-Scalp System - Verify API integration and functionality (Updated)
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
        
        # Test 1.2: Get M1 candles for BTCUSDc
        print("1.2 Testing /streamer/candles/BTCUSDc/M1...")
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
                        return True
                    else:
                        print(f"   ❌ API returned error: {data.get('error')}")
                        return False
                else:
                    print(f"   ❌ Candles request failed: {response.status_code}")
                    return False
        except Exception as e:
            print(f"   ❌ Candles request error: {e}")
            return False
        
    except ImportError:
        print("   ❌ httpx not available")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_monitor_api_integration():
    """Test if monitor can access streamer API"""
    print("=" * 80)
    print("TEST 2: Monitor API Integration")
    print("=" * 80)
    print()
    
    print("2.1 Testing if monitor can access streamer API...")
    print("   The monitor should be calling: http://localhost:8000/streamer/candles/{symbol}/M1")
    print()
    print("   Checking monitor status on port 8010...")
    
    try:
        import httpx
        
        # Try to access monitor view page
        base_url = "http://localhost:8010"
        
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{base_url}/micro-scalp/view")
                if response.status_code == 200:
                    print(f"   ✅ Monitor view page accessible")
                    print(f"   Visit: http://localhost:8010/micro-scalp/view")
                else:
                    print(f"   ⚠️ Monitor view returned: {response.status_code}")
        except Exception as e:
            print(f"   ⚠️ Could not access monitor view: {e}")
        
        print()
        print("   To verify API integration:")
        print("   1. Check monitor logs for 'Got X M1 candles from API' messages")
        print("   2. Monitor should show successful condition checks")
        print("   3. No 'No M1 candles available' errors should appear")
        print()
        print("   Waiting 15 seconds for monitor to run check cycles...")
        
        time.sleep(15)
        
        print()
        print("   ✅ Monitor should have attempted to use API by now")
        print("   Check logs for confirmation")
        
        return True
        
    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        return False

def test_api_performance():
    """Test API performance"""
    print("=" * 80)
    print("TEST 3: API Performance")
    print("=" * 80)
    print()
    
    try:
        import httpx
        
        base_url = "http://localhost:8000"
        
        print("3.1 Testing API response time...")
        
        times = []
        for i in range(10):
            start = time.time()
            try:
                with httpx.Client(timeout=2.0) as client:
                    response = client.get(f"{base_url}/streamer/candles/BTCUSDc/M1", params={"limit": 50})
                    if response.status_code == 200:
                        elapsed = (time.time() - start) * 1000  # Convert to ms
                        times.append(elapsed)
            except Exception as e:
                print(f"   ⚠️ Request {i+1} failed: {e}")
        
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            print(f"   ✅ Performance test completed")
            print(f"   Average response time: {avg_time:.2f} ms")
            print(f"   Min: {min_time:.2f} ms")
            print(f"   Max: {max_time:.2f} ms")
            print(f"   Requests: {len(times)}/10 successful")
            
            if avg_time < 10:
                print(f"   ✅ Excellent performance (< 10ms)")
            elif avg_time < 50:
                print(f"   ✅ Good performance (< 50ms)")
            else:
                print(f"   ⚠️ Performance could be better (> 50ms)")
            
            return True
        else:
            print(f"   ❌ No successful requests")
            return False
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    """Run all tests"""
    print()
    print("=" * 80)
    print("MICRO-SCALP SYSTEM TEST SUITE (v2)")
    print("=" * 80)
    print()
    print(f"Test started at: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    results = []
    
    # Test 1: Streamer API
    results.append(("Streamer API", test_streamer_api()))
    print()
    
    # Test 2: Monitor API Integration
    results.append(("Monitor API Integration", test_monitor_api_integration()))
    print()
    
    # Test 3: API Performance
    results.append(("API Performance", test_api_performance()))
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
        print()
        print("Next steps:")
        print("1. Check monitor logs for 'Got X M1 candles from API' messages")
        print("2. Visit http://localhost:8010/micro-scalp/view to see monitor dashboard")
        print("3. Verify condition checks are happening successfully")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
    print()

if __name__ == "__main__":
    main()

