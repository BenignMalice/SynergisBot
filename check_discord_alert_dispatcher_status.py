"""
Check Discord Alert Dispatcher status and recent activity.
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
print("DISCORD ALERT DISPATCHER STATUS CHECK")
print("=" * 80)
print()

# ============================================================================
# 1. Check if main_api.py is running
# ============================================================================
print("[1/4] Checking Main API Server Status...")
print("-" * 80)

try:
    import httpx
    with httpx.Client(timeout=5.0) as client:
        try:
            response = client.get("http://localhost:8000/health")
            if response.status_code == 200:
                print("  [OK] Main API server is running on port 8000")
                health_data = response.json()
                if 'status' in health_data:
                    print(f"  Status: {health_data.get('status')}")
            else:
                print(f"  [WARN] Main API server responded with status {response.status_code}")
        except httpx.ConnectError:
            print("  [ERROR] Main API server not reachable on port 8000")
            print("  [INFO] Discord Alert Dispatcher runs in main_api.py - server must be running")
        except Exception as e:
            print(f"  [WARN] Error checking main API: {e}")
except ImportError:
    print("  [WARN] httpx not available, cannot check API server")
except Exception as e:
    print(f"  [ERROR] Error checking API server: {e}")

print()

# ============================================================================
# 2. Check Discord Alert Dispatcher Logs
# ============================================================================
print("[2/4] Checking Discord Alert Dispatcher Logs...")
print("-" * 80)

# Check main_api.log if it exists
log_paths = [
    project_root / "data" / "logs" / "main_api.log",
    project_root / "data" / "logs" / "chatgpt_bot.log"
]

for log_path in log_paths:
    if log_path.exists():
        print(f"  [OK] Log file exists: {log_path}")
        
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Search for Discord Alert Dispatcher entries
            dispatcher_keywords = [
                'Discord Alert Dispatcher',
                'alert_dispatcher',
                'run_detection_cycle',
                'Alert sent',
                'detection cycle'
            ]
            
            dispatcher_lines = []
            for line in lines[-5000:]:  # Check last 5000 lines
                if any(keyword in line for keyword in dispatcher_keywords):
                    dispatcher_lines.append(line.strip())
            
            if dispatcher_lines:
                print(f"  Found {len(dispatcher_lines)} dispatcher-related log entries")
                print(f"\n  Most recent entries (last 10):")
                for line in dispatcher_lines[-10:]:
                    parts = line.split(' - ', 2)
                    if len(parts) >= 3:
                        timestamp = parts[0]
                        module = parts[1]
                        message = parts[2].strip()
                        print(f"    [{timestamp}] {module}: {message[:120]}")
            else:
                print(f"  [WARN] No dispatcher-related log entries found")
                
            # Check for startup message
            startup_lines = [l for l in lines if 'Discord Alert Dispatcher started' in l or 'Alert Dispatcher initialized' in l]
            if startup_lines:
                print(f"\n  [OK] Dispatcher startup found:")
                for line in startup_lines[-3:]:
                    parts = line.split(' - ', 2)
                    if len(parts) >= 3:
                        timestamp = parts[0]
                        message = parts[2].strip()
                        print(f"    [{timestamp}] {message}")
            else:
                print(f"\n  [WARN] No dispatcher startup message found")
                
            # Check for errors
            error_lines = [l for l in lines[-2000:] if 'ERROR' in l and ('alert' in l.lower() or 'dispatcher' in l.lower())]
            if error_lines:
                print(f"\n  [WARN] Found {len(error_lines)} dispatcher-related errors:")
                for line in error_lines[-5:]:
                    parts = line.split(' - ', 2)
                    if len(parts) >= 3:
                        timestamp = parts[0]
                        message = parts[2].strip()
                        print(f"    [{timestamp}] {message[:150]}")
                        
        except Exception as e:
            print(f"  [ERROR] Error reading log: {e}")
        break
else:
    print(f"  [WARN] No log files found to check")

print()

# ============================================================================
# 3. Check Discord Alerts Config
# ============================================================================
print("[3/4] Checking Discord Alerts Configuration...")
print("-" * 80)

config_path = project_root / "config" / "discord_alerts_config.json"

if config_path.exists():
    print(f"  [OK] Config file exists: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        enabled = config.get('enabled', True)
        symbols = config.get('symbols', [])
        alerts_config = config.get('alerts', {})
        
        print(f"  Enabled: {enabled}")
        print(f"  Symbols: {', '.join(symbols) if symbols else 'None'}")
        
        if alerts_config:
            print(f"\n  Alert types configured:")
            for alert_type, alert_config in alerts_config.items():
                alert_enabled = alert_config.get('enabled', True)
                status = "✅ Enabled" if alert_enabled else "❌ Disabled"
                print(f"    - {alert_type}: {status}")
        else:
            print(f"  [WARN] No alert types configured")
            
    except Exception as e:
        print(f"  [ERROR] Error reading config: {e}")
else:
    print(f"  [WARN] Config file not found: {config_path}")

print()

# ============================================================================
# 4. Check Recent Alert Activity
# ============================================================================
print("[4/4] Checking Recent Alert Activity...")
print("-" * 80)

# Check for "Alert sent" messages in logs
for log_path in log_paths:
    if log_path.exists():
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Look for "Alert sent" messages
            alert_sent_lines = [l for l in lines[-10000:] if 'Alert sent' in l or 'alert sent' in l]
            
            if alert_sent_lines:
                print(f"  Found {len(alert_sent_lines)} 'Alert sent' messages")
                print(f"\n  Most recent alerts (last 10):")
                for line in alert_sent_lines[-10:]:
                    parts = line.split(' - ', 2)
                    if len(parts) >= 3:
                        timestamp = parts[0]
                        module = parts[1]
                        message = parts[2].strip()
                        print(f"    [{timestamp}] {module}: {message[:120]}")
                
                # Get most recent alert time
                if alert_sent_lines:
                    last_line = alert_sent_lines[-1]
                    parts = last_line.split(' - ', 1)
                    if parts:
                        last_alert_time_str = parts[0].strip()
                        print(f"\n  Last alert time: {last_alert_time_str}")
            else:
                print(f"  [WARN] No 'Alert sent' messages found in recent logs")
                print(f"  This suggests alerts are not being detected or sent")
                
        except Exception as e:
            print(f"  [ERROR] Error checking alert activity: {e}")
        break

print()

# ============================================================================
# SUMMARY
# ============================================================================
print("=" * 80)
print("SUMMARY")
print("=" * 80)

print("\n  Key Findings:")
print("    1. Discord Alert Dispatcher runs in main_api.py (port 8000)")
print("    2. Detection cycle runs every 60 seconds")
print("    3. Monitors: BTCUSDc, XAUUSDc, GBPUSDc, EURUSDc")
print("    4. Alert types: CHOCH, BOS, Sweeps, OB, VWAP, BB, Inside Bar")
print("\n  Recommendations:")
print("    1. Verify main_api.py is running (check port 8000)")
print("    2. Check if MultiTimeframeStreamer has fresh candle data")
print("    3. Verify Discord webhook is configured correctly")
print("    4. Check if alerts are being throttled (cooldown periods)")
print("    5. Verify market conditions - alerts only trigger when conditions are met")

print()
print("=" * 80)

