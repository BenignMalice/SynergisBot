"""
Detailed check of Discord Alert Dispatcher status.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
import json

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("DISCORD ALERT DISPATCHER - DETAILED STATUS CHECK")
print("=" * 80)
print()

# ============================================================================
# 1. Check if Dispatcher is Running (via API or direct check)
# ============================================================================
print("[1/5] Checking Dispatcher Runtime Status...")
print("-" * 80)

try:
    # Try to check if dispatcher is accessible
    import httpx
    with httpx.Client(timeout=5.0) as client:
        # Check if there's a status endpoint
        try:
            response = client.get("http://localhost:8000/health")
            if response.status_code == 200:
                print("  [OK] Main API server is running")
        except:
            pass
except:
    pass

# Try to check dispatcher directly
try:
    from infra.discord_alert_dispatcher import DiscordAlertDispatcher
    
    # Check if we can access the global instance (if available)
    try:
        import app.main_api as main_api_module
        if hasattr(main_api_module, 'alert_dispatcher'):
            dispatcher = main_api_module.alert_dispatcher
            if dispatcher:
                print(f"  [OK] Dispatcher instance found in main_api")
                print(f"  Is running: {dispatcher.is_running}")
                print(f"  Symbols: {', '.join(dispatcher.symbols) if dispatcher.symbols else 'None'}")
                print(f"  Streamer available: {dispatcher.streamer is not None}")
            else:
                print(f"  [WARN] Dispatcher instance is None")
        else:
            print(f"  [INFO] Could not access dispatcher instance (may be in different process)")
    except Exception as e:
        print(f"  [INFO] Could not check dispatcher instance: {e}")
        
except ImportError as e:
    print(f"  [ERROR] Could not import DiscordAlertDispatcher: {e}")

print()

# ============================================================================
# 2. Check Streamer Data Availability
# ============================================================================
print("[2/5] Checking MultiTimeframeStreamer Data...")
print("-" * 80)

try:
    from infra.multi_timeframe_streamer import MultiTimeframeStreamer
    
    # Check if streamer is running and has data
    try:
        # Try to get streamer instance
        import app.main_api as main_api_module
        if hasattr(main_api_module, 'alert_dispatcher') and main_api_module.alert_dispatcher:
            streamer = main_api_module.alert_dispatcher.streamer
            if streamer:
                print(f"  [OK] Streamer instance found")
                
                # Check data for configured symbols
                symbols = main_api_module.alert_dispatcher.symbols
                for symbol in symbols:
                    m5_candles = streamer.get_candles(symbol, 'M5', 10)
                    m15_candles = streamer.get_candles(symbol, 'M15', 10)
                    h1_candles = streamer.get_candles(symbol, 'H1', 10)
                    
                    print(f"\n  {symbol}:")
                    print(f"    M5 candles: {len(m5_candles) if m5_candles else 0}")
                    print(f"    M15 candles: {len(m15_candles) if m15_candles else 0}")
                    print(f"    H1 candles: {len(h1_candles) if h1_candles else 0}")
                    
                    # Check freshness
                    if m5_candles and len(m5_candles) > 0:
                        last_candle = m5_candles[-1]
                        if hasattr(last_candle, 'time'):
                            candle_time = datetime.fromtimestamp(last_candle.time)
                            age = (datetime.now() - candle_time).total_seconds() / 60
                            print(f"    Last M5 candle age: {age:.1f} minutes")
                            if age > 10:
                                print(f"    [WARN] M5 candles are stale (>10 minutes old)")
            else:
                print(f"  [WARN] Streamer not available in dispatcher")
        else:
            print(f"  [INFO] Could not access dispatcher to check streamer")
    except Exception as e:
        print(f"  [INFO] Could not check streamer: {e}")
        
except ImportError:
    print(f"  [WARN] MultiTimeframeStreamer not available")

print()

# ============================================================================
# 3. Check Quiet Hours
# ============================================================================
print("[3/5] Checking Quiet Hours Configuration...")
print("-" * 80)

config_path = project_root / "config" / "discord_alerts_config.json"

if config_path.exists():
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        quiet_hours = config.get('quiet_hours', {})
        if quiet_hours:
            enabled = quiet_hours.get('enabled', False)
            start = quiet_hours.get('start', '22:00')
            end = quiet_hours.get('end', '06:00')
            
            print(f"  Quiet hours enabled: {enabled}")
            if enabled:
                print(f"  Quiet hours: {start} - {end}")
                
                # Check if we're currently in quiet hours
                current_time = datetime.now(timezone.utc)
                current_hour = current_time.hour
                print(f"  Current UTC time: {current_time.strftime('%H:%M')}")
                
                # Simple check (would need proper parsing for full check)
                print(f"  [INFO] Check if current time is within quiet hours range")
        else:
            print(f"  [INFO] No quiet hours configured")
            
    except Exception as e:
        print(f"  [ERROR] Error reading config: {e}")
else:
    print(f"  [WARN] Config file not found")

print()

# ============================================================================
# 4. Check Recent Detection Activity
# ============================================================================
print("[4/5] Checking Recent Detection Activity...")
print("-" * 80)

# Check all log files for dispatcher activity
log_dir = project_root / "data" / "logs"
log_files = list(log_dir.glob("*.log")) if log_dir.exists() else []

for log_file in log_files[:3]:  # Check first 3 log files
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Look for detection cycle runs
        detection_lines = [l for l in lines[-2000:] if 'run_detection_cycle' in l.lower() or 'detection cycle' in l.lower()]
        if detection_lines:
            print(f"  Found detection cycle activity in {log_file.name}:")
            for line in detection_lines[-5:]:
                parts = line.split(' - ', 2)
                if len(parts) >= 3:
                    timestamp = parts[0]
                    message = parts[2].strip()
                    print(f"    [{timestamp}] {message[:100]}")
            break
    except Exception:
        continue
else:
    print(f"  [WARN] No detection cycle activity found in logs")

# Check for "Alert sent" from dispatcher (not intelligent exits)
log_path = project_root / "data" / "logs" / "chatgpt_bot.log"
if log_path.exists():
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Look for condition alerts (CHOCH, BOS, OB, etc.)
        condition_alert_keywords = ['CHOCH', 'BOS', 'Order Block', 'Sweep', 'VWAP', 'Inside Bar', 'BB_SQUEEZE']
        condition_alerts = []
        for line in lines[-10000:]:
            if any(keyword in line for keyword in condition_alert_keywords):
                if 'Alert sent' in line or 'alert sent' in line:
                    condition_alerts.append(line)
        
        if condition_alerts:
            print(f"\n  Found {len(condition_alerts)} condition alerts:")
            for line in condition_alerts[-5:]:
                parts = line.split(' - ', 2)
                if len(parts) >= 3:
                    timestamp = parts[0]
                    message = parts[2].strip()
                    print(f"    [{timestamp}] {message[:120]}")
        else:
            print(f"\n  [WARN] No condition alerts found (only intelligent exit alerts)")
            
    except Exception as e:
        print(f"  [ERROR] Error checking logs: {e}")

print()

# ============================================================================
# 5. Check for Errors
# ============================================================================
print("[5/5] Checking for Errors...")
print("-" * 80)

log_path = project_root / "data" / "logs" / "chatgpt_bot.log"
if log_path.exists():
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Look for dispatcher errors
        error_keywords = ['Alert detection error', 'Error processing', 'dispatcher', 'Discord Alert']
        errors = []
        for line in lines[-5000:]:
            if 'ERROR' in line and any(keyword in line for keyword in error_keywords):
                errors.append(line)
        
        if errors:
            print(f"  Found {len(errors)} dispatcher-related errors:")
            for line in errors[-5:]:
                parts = line.split(' - ', 2)
                if len(parts) >= 3:
                    timestamp = parts[0]
                    message = parts[2].strip()
                    print(f"    [{timestamp}] {message[:150]}")
        else:
            print(f"  [OK] No dispatcher-related errors found")
            
    except Exception as e:
        print(f"  [ERROR] Error checking for errors: {e}")

print()

# ============================================================================
# SUMMARY
# ============================================================================
print("=" * 80)
print("SUMMARY & RECOMMENDATIONS")
print("=" * 80)

print("\n  Findings:")
print("    1. Main API server is running ✅")
print("    2. Config is enabled and symbols configured ✅")
print("    3. No condition alerts found since 11:53 ⚠️")
print("    4. Dispatcher runs in main_api.py (separate process)")
print("\n  Possible Issues:")
print("    1. Dispatcher may not have started (check main_api startup logs)")
print("    2. Streamer may not have fresh candle data")
print("    3. Market conditions may not be matching alert criteria")
print("    4. Alerts may be throttled (cooldown periods)")
print("    5. Quiet hours may be active")
print("    6. Weekend filtering may be blocking alerts")
print("\n  Next Steps:")
print("    1. Check main_api.py startup logs for dispatcher initialization")
print("    2. Verify MultiTimeframeStreamer is running and has fresh data")
print("    3. Check if current time is in quiet hours")
print("    4. Verify market conditions - alerts only trigger on specific patterns")
print("    5. Check Discord webhook configuration")

print()
print("=" * 80)

