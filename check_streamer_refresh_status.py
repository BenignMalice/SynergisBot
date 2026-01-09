"""Check MultiTimeframeStreamer refresh intervals and monitor for errors"""
import urllib.request
import json
from datetime import datetime, timezone
from pathlib import Path

API_BASE = "http://localhost:8000"

print("\n" + "="*80)
print("MULTI-TIMEFRAME STREAMER REFRESH STATUS CHECK")
print("="*80 + "\n")

# 1. Check streamer status and refresh intervals
print("1. STREAMER STATUS & REFRESH INTERVALS:")
print("-" * 80)

try:
    req = urllib.request.Request(f"{API_BASE}/api/v1/streamer/status")
    req.add_header('User-Agent', 'StreamerCheck')
    with urllib.request.urlopen(req, timeout=5) as response:
        if response.status == 200:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get("status") == "running":
                print("[OK] Streamer is RUNNING")
                
                # Show refresh intervals
                refresh_intervals = data.get("refresh_intervals", {})
                if refresh_intervals:
                    print("\n   Refresh Intervals:")
                    for tf, interval_sec in refresh_intervals.items():
                        interval_min = interval_sec / 60
                        print(f"     {tf}: {interval_sec}s ({interval_min:.1f} minutes)")
                    
                    # Check M5 specifically
                    m5_interval = refresh_intervals.get("M5", 0)
                    if m5_interval:
                        m5_min = m5_interval / 60
                        print(f"\n   [VERIFY] M5 refresh interval: {m5_interval}s ({m5_min:.1f} minutes)")
                        if 240 <= m5_interval <= 300:
                            print(f"   [OK] M5 interval is within expected range (4-5 minutes)")
                        else:
                            print(f"   [WARNING] M5 interval is outside expected range (should be 240-300s)")
                else:
                    print("   [WARNING] No refresh intervals found in status")
                
                # Show metrics
                metrics = data.get("metrics", {})
                errors = metrics.get("errors", 0)
                if errors > 0:
                    print(f"\n   [ERROR] Streamer has {errors} errors recorded")
                    print("   Check server logs for: 'Error in M5 stream for BTCUSDc'")
                else:
                    print(f"\n   [OK] No errors recorded in streamer metrics")
                
                # Show buffer status
                buffer_status = data.get("buffer_status", {})
                if buffer_status:
                    print("\n   Buffer Status:")
                    for symbol, tfs in buffer_status.items():
                        for tf, status in tfs.items():
                            count = status.get("count", 0)
                            has_data = status.get("has_data", False)
                            if tf == "M5":
                                print(f"     {symbol} {tf}: {count} candles {'[OK]' if has_data else '[EMPTY]'}")
            else:
                print(f"[ERROR] Streamer status: {data.get('status', 'unknown')}")
        else:
            print(f"[ERROR] Status endpoint returned {response.status}")
except Exception as e:
    print(f"[ERROR] Cannot check streamer status: {e}")
    print("         Is the API server running?")

# 2. Check latest M5 candle age for BTCUSDc
print("\n2. LATEST M5 CANDLE AGE (BTCUSDc):")
print("-" * 80)

try:
    req = urllib.request.Request(f"{API_BASE}/streamer/candles/BTCUSDc/M5?limit=1")
    req.add_header('User-Agent', 'StreamerCheck')
    with urllib.request.urlopen(req, timeout=5) as response:
        if response.status == 200:
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get("success") and data.get("candles"):
                candles = data.get("candles", [])
                if candles:
                    latest = candles[0]
                    candle_time = latest.get("time")
                    
                    if isinstance(candle_time, (int, float)):
                        # Unix timestamp
                        candle_dt = datetime.fromtimestamp(candle_time, tz=timezone.utc)
                    else:
                        # ISO string
                        candle_dt = datetime.fromisoformat(candle_time.replace('Z', '+00:00'))
                    
                    now = datetime.now(timezone.utc)
                    age_seconds = (now - candle_dt).total_seconds()
                    age_minutes = age_seconds / 60
                    
                    print(f"[OK] Latest M5 candle found")
                    print(f"     Candle time: {candle_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                    print(f"     Current time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                    print(f"     Age: {age_minutes:.2f} minutes ({age_seconds:.0f} seconds)")
                    
                    # Check if stale
                    threshold = 5.5  # Same threshold used in range_scalping_risk_filters
                    if age_minutes > threshold:
                        print(f"\n     [WARNING] Candle is STALE (> {threshold} min threshold)")
                        print(f"     This will trigger MT5 fallback in range scalping filters")
                    else:
                        print(f"\n     [OK] Candle is FRESH (< {threshold} min threshold)")
                else:
                    print("[WARNING] No candles returned")
            else:
                print(f"[WARNING] No candles available: {data.get('error', 'unknown')}")
        else:
            print(f"[ERROR] Candles endpoint returned {response.status}")
except Exception as e:
    print(f"[ERROR] Cannot check candle age: {e}")

# 3. Check for errors in server logs (suggested)
print("\n3. ERROR MONITORING:")
print("-" * 80)
print("   To check for refresh errors, look in server logs for:")
print("   - 'Error in M5 stream for BTCUSDc'")
print("   - 'Error in M5 stream for XAUUSDc'")
print("   - '[WARNING] BTCUSDc M5: No new candles for X fetches'")
print("\n   If errors are found:")
print("   - The refresh task waits 60 seconds before retry")
print("   - This can cause data to become stale")
print("   - Check MT5 connection and market hours")

# 4. Summary
print("\n" + "="*80)
print("SUMMARY & RECOMMENDATIONS")
print("="*80)

print("\nExpected M5 Refresh Behavior:")
print("  - Refresh interval: 240-300 seconds (4-5 minutes)")
print("  - Streamer waits full interval before fetching new candles")
print("  - If initial data is old, it can take 4-5 min to refresh")
print("  - Stale data (>5.5 min) triggers MT5 fallback (expected behavior)")

print("\nIf data is consistently stale:")
print("  1. Check streamer is running: /api/v1/streamer/status")
print("  2. Check for errors in logs: 'Error in M5 stream'")
print("  3. Verify MT5 connection is active")
print("  4. Check market hours (data won't refresh if market is closed)")
print("  5. Verify refresh intervals match expected values (240-300s for M5)")

print("\n" + "="*80 + "\n")

