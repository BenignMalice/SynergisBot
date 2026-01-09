"""
Check alert system status and recent activity.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
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
print("ALERT SYSTEM STATUS CHECK")
print("=" * 80)
print()

# ============================================================================
# 1. Check Alert Monitor Initialization
# ============================================================================
print("[1/4] Checking Alert Monitor Initialization...")
print("-" * 80)

try:
    from infra.alert_monitor import AlertMonitor
    from infra.custom_alerts import CustomAlertManager
    
    print("  [OK] AlertMonitor and CustomAlertManager modules available")
    
    # Try to check if alert monitor is initialized
    try:
        # Check if there's a way to get the global instance
        import chatgpt_bot
        if hasattr(chatgpt_bot, 'alert_monitor') and chatgpt_bot.alert_monitor:
            print("  [OK] Alert monitor is initialized in chatgpt_bot")
        else:
            print("  [WARN] Alert monitor not initialized in chatgpt_bot")
    except Exception as e:
        print(f"  [INFO] Could not check chatgpt_bot instance: {e}")
        
except ImportError as e:
    print(f"  [ERROR] Could not import alert monitor: {e}")

print()

# ============================================================================
# 2. Check Custom Alerts Database
# ============================================================================
print("[2/4] Checking Custom Alerts Database...")
print("-" * 80)

alerts_file = project_root / "data" / "custom_alerts.json"

if alerts_file.exists():
    print(f"  [OK] Alerts file exists: {alerts_file}")
    print(f"  Size: {alerts_file.stat().st_size} bytes")
    
    try:
        with open(alerts_file, 'r', encoding='utf-8') as f:
            alerts_data = json.load(f)
        
        alerts = alerts_data.get('alerts', [])
        print(f"  Total alerts configured: {len(alerts)}")
        
        if alerts:
            print(f"\n  Active alerts:")
            for alert in alerts[:10]:  # Show first 10
                alert_id = alert.get('id', 'Unknown')
                symbol = alert.get('symbol', 'Unknown')
                condition = alert.get('condition', 'Unknown')
                target = alert.get('target_value', 'Unknown')
                enabled = alert.get('enabled', True)
                status = "✅ Enabled" if enabled else "❌ Disabled"
                print(f"    - {alert_id}: {symbol} {condition} {target} ({status})")
        else:
            print(f"  [INFO] No alerts configured")
            
    except Exception as e:
        print(f"  [ERROR] Error reading alerts file: {e}")
else:
    print(f"  [WARN] Alerts file not found: {alerts_file}")

print()

# ============================================================================
# 3. Check Recent Logs for Alert Activity
# ============================================================================
print("[3/4] Checking Recent Logs for Alert Activity...")
print("-" * 80)

log_path = project_root / "data" / "logs" / "chatgpt_bot.log"

if log_path.exists():
    print(f"  [OK] Log file exists: {log_path}")
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Search for alert-related log entries
        alert_keywords = [
            'alert', 'Alert', 'ALERT',
            'check_all_alerts', 'check_custom_alerts',
            'Alert sent', 'Alert triggered', 'condition alert'
        ]
        
        recent_alert_lines = []
        for line in lines[-5000:]:  # Check last 5000 lines
            if any(keyword in line for keyword in alert_keywords):
                recent_alert_lines.append(line.strip())
        
        if recent_alert_lines:
            print(f"  Found {len(recent_alert_lines)} alert-related log entries")
            print(f"\n  Most recent alert entries (last 10):")
            for line in recent_alert_lines[-10:]:
                # Extract timestamp and message
                parts = line.split(' - ', 2)
                if len(parts) >= 3:
                    timestamp = parts[0]
                    module = parts[1]
                    message = parts[2].strip()
                    print(f"    [{timestamp}] {module}: {message[:100]}")
        else:
            print(f"  [WARN] No alert-related log entries found in recent logs")
            
        # Check for errors
        error_lines = [l for l in lines[-1000:] if 'ERROR' in l and 'alert' in l.lower()]
        if error_lines:
            print(f"\n  [WARN] Found {len(error_lines)} alert-related errors:")
            for line in error_lines[-5:]:
                parts = line.split(' - ', 2)
                if len(parts) >= 3:
                    timestamp = parts[0]
                    message = parts[2].strip()
                    print(f"    [{timestamp}] {message[:150]}")
                    
    except Exception as e:
        print(f"  [ERROR] Error reading logs: {e}")
else:
    print(f"  [WARN] Log file not found: {log_path}")

print()

# ============================================================================
# 4. Check Scheduler Status
# ============================================================================
print("[4/4] Checking Scheduler Status...")
print("-" * 80)

try:
    # Check if scheduler is running by looking for scheduler logs
    if log_path.exists():
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Look for scheduler activity
        scheduler_lines = [l for l in lines[-500:] if 'scheduler' in l.lower() or 'apscheduler' in l.lower()]
        
        if scheduler_lines:
            print(f"  [OK] Scheduler activity found in logs")
            print(f"  Recent scheduler entries (last 5):")
            for line in scheduler_lines[-5:]:
                parts = line.split(' - ', 2)
                if len(parts) >= 3:
                    timestamp = parts[0]
                    message = parts[2].strip()
                    print(f"    [{timestamp}] {message[:100]}")
        else:
            print(f"  [WARN] No scheduler activity found in recent logs")
            
        # Check for check_custom_alerts function calls
        check_alerts_lines = [l for l in lines[-1000:] if 'check_custom_alerts' in l or 'check_all_alerts' in l]
        if check_alerts_lines:
            print(f"\n  [OK] Found {len(check_alerts_lines)} alert check calls in recent logs")
            print(f"  Most recent (last 3):")
            for line in check_alerts_lines[-3:]:
                parts = line.split(' - ', 2)
                if len(parts) >= 3:
                    timestamp = parts[0]
                    print(f"    [{timestamp}] Alert check executed")
        else:
            print(f"\n  [WARN] No alert check calls found in recent logs")
            print(f"  This suggests the scheduler may not be running check_custom_alerts")
            
except Exception as e:
    print(f"  [ERROR] Error checking scheduler: {e}")

print()

# ============================================================================
# SUMMARY
# ============================================================================
print("=" * 80)
print("SUMMARY")
print("=" * 80)

# Calculate time since last alert (11:53)
try:
    # Parse 11:53 (assuming today, need to check timezone)
    current_time = datetime.now()
    last_alert_time_str = "11:53"
    
    # Try to parse (assuming 24-hour format)
    hour, minute = map(int, last_alert_time_str.split(':'))
    last_alert_time = current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # If last alert time is in the future, assume it was yesterday
    if last_alert_time > current_time:
        last_alert_time = last_alert_time - timedelta(days=1)
    
    time_since_alert = current_time - last_alert_time
    hours_since = time_since_alert.total_seconds() / 3600
    
    print(f"  Time since last alert (11:53): {hours_since:.1f} hours")
    
    if hours_since > 1:
        print(f"\n  ⚠️ WARNING: No alerts for {hours_since:.1f} hours")
        print(f"  Possible issues:")
        print(f"    1. Alert monitor not running")
        print(f"    2. Scheduler not calling check_custom_alerts")
        print(f"    3. No market conditions matching alert criteria")
        print(f"    4. Alert system errors preventing detection")
    else:
        print(f"\n  ✅ Alerts received recently (within last hour)")
        
except Exception as e:
    print(f"  [INFO] Could not calculate time since last alert: {e}")

print()
print("=" * 80)

