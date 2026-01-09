"""
Check main_api.py logs for Discord Alert Dispatcher activity.
"""

import sys
from pathlib import Path
from datetime import datetime

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

project_root = Path(__file__).parent

print("=" * 80)
print("MAIN_API LOGS CHECK - DISCORD ALERT DISPATCHER")
print("=" * 80)
print()

# Check all log files
log_dir = project_root / "data" / "logs"
if log_dir.exists():
    log_files = sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    print(f"Found {len(log_files)} log files")
    print()
    
    for log_file in log_files[:3]:  # Check 3 most recent
        print(f"[{log_file.name}]")
        print("-" * 80)
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Look for dispatcher-related entries
            dispatcher_keywords = [
                'Discord Alert Dispatcher',
                'alert_dispatcher',
                'detection cycle',
                'Alert sent',
                'run_detection_cycle',
                'main_api',
                'startup'
            ]
            
            dispatcher_lines = []
            for line in lines[-10000:]:  # Last 10k lines
                if any(kw in line for kw in dispatcher_keywords):
                    dispatcher_lines.append(line.strip())
            
            if dispatcher_lines:
                print(f"Found {len(dispatcher_lines)} dispatcher-related entries")
                print("\nMost recent (last 15):")
                for line in dispatcher_lines[-15:]:
                    print(f"  {line[:200]}")
            else:
                print("No dispatcher-related entries found")
                
            # Check for startup messages
            startup_lines = [l for l in lines if 'started' in l.lower() and ('dispatcher' in l.lower() or 'main_api' in l.lower())]
            if startup_lines:
                print(f"\nStartup messages found ({len(startup_lines)}):")
                for line in startup_lines[-5:]:
                    print(f"  {line.strip()[:200]}")
                    
        except Exception as e:
            print(f"Error reading {log_file.name}: {e}")
        
        print()
        
else:
    print(f"Log directory not found: {log_dir}")

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print("\nThe Discord Alert Dispatcher runs in main_api.py (not chatgpt_bot.py).")
print("If no dispatcher logs are found, it may not be running or logging to a different location.")
print("\nTo check if dispatcher is running:")
print("1. Check if main_api.py process is running")
print("2. Check console output where main_api.py was started")
print("3. Look for 'Discord Alert Dispatcher started' message")

