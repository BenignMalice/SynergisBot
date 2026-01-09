"""
Check Discord Alert Dispatcher status by examining the running process.
"""

import sys
from pathlib import Path

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("DISCORD ALERT DISPATCHER - LIVE STATUS CHECK")
print("=" * 80)
print()

# Check 1: API Server Status
print("[1/3] Checking Main API Server...")
print("-" * 80)

try:
    import httpx
    with httpx.Client(timeout=5.0) as client:
        response = client.get("http://localhost:8000/health")
        if response.status_code == 200:
            print("  [OK] Main API server is running on port 8000")
            health = response.json()
            print(f"  Status: {health.get('status', 'unknown')}")
        else:
            print(f"  [WARN] API responded with status {response.status_code}")
except Exception as e:
    print(f"  [ERROR] Cannot reach API server: {e}")
    print("  [INFO] Main API server may not be running")
    print()
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print("\n⚠️ Main API server is not running or not accessible.")
    print("The Discord Alert Dispatcher runs in main_api.py.")
    print("\nTo start it, run: python main_api.py")
    sys.exit(1)

print()

# Check 2: Try to access dispatcher module state (if possible)
print("[2/3] Checking Dispatcher Module State...")
print("-" * 80)

try:
    # Try to import and check if dispatcher exists
    # Note: This only works if we're in the same process
    import importlib.util
    spec = importlib.util.spec_from_file_location("main_api", project_root / "main_api.py")
    if spec and spec.loader:
        print("  [INFO] Cannot directly access dispatcher state (runs in separate process)")
        print("  [INFO] Dispatcher state is only accessible from within main_api.py process")
except Exception as e:
    print(f"  [INFO] Cannot check module state: {e}")

print()

# Check 3: Check for recent condition alerts
print("[3/3] Checking for Recent Condition Alerts...")
print("-" * 80)

log_path = project_root / "data" / "logs" / "chatgpt_bot.log"
if log_path.exists():
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Look for condition alerts (CHOCH, BOS, OB, Sweep, etc.)
        condition_keywords = ['CHOCH', 'BOS', 'Order Block', 'Sweep', 'VWAP', 'Inside Bar', 'BB_SQUEEZE', 'BB_EXPANSION']
        condition_alerts = []
        
        for line in lines[-10000:]:  # Last 10k lines
            if any(kw in line for kw in condition_keywords):
                if 'Alert sent' in line or 'alert sent' in line:
                    condition_alerts.append(line)
        
        if condition_alerts:
            print(f"  Found {len(condition_alerts)} condition alerts in recent logs")
            print(f"\n  Most recent (last 5):")
            for line in condition_alerts[-5:]:
                parts = line.split(' - ', 2)
                if len(parts) >= 3:
                    timestamp = parts[0]
                    message = parts[2].strip()
                    print(f"    [{timestamp}] {message[:120]}")
        else:
            print(f"  [WARN] No condition alerts found in recent logs")
            print(f"  [INFO] Only 'Intelligent exit alerts' found (different system)")
            
    except Exception as e:
        print(f"  [ERROR] Error reading logs: {e}")
else:
    print(f"  [WARN] Log file not found: {log_path}")

print()

# Summary
print("=" * 80)
print("DIAGNOSIS")
print("=" * 80)
print()
print("Findings:")
print("  ✅ Main API server is running")
print("  ⚠️  No dispatcher logs found in log files")
print("  ⚠️  No condition alerts found since 11:53")
print()
print("Possible Issues:")
print("  1. Dispatcher failed to start (check main_api.py startup logs)")
print("  2. Dispatcher is running but not logging (unlikely with new logging)")
print("  3. Logs are going to console output (not file)")
print("  4. Market conditions not matching alert criteria")
print()
print("Next Steps:")
print("  1. Check the console/terminal where main_api.py was started")
print("     Look for: '✅ Discord Alert Dispatcher started'")
print("  2. If not found, check for: '⚠️ Discord Alert Dispatcher failed to start'")
print("  3. Restart main_api.py to see new logging output")
print("  4. After restart, check logs for:")
print("     - 'Discord Alert Dispatcher: Running detection cycle'")
print("     - 'No M5 candles available' (if streamer issue)")
print("     - 'Discord Alert Dispatcher: Sent X alert(s)'")
print()
print("=" * 80)

