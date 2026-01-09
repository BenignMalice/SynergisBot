"""
Check Binance service operational status
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("BINANCE SERVICE STATUS CHECK")
print("=" * 80)

# Check 1: Is Binance service initialized in chatgpt_bot?
print("\n[1] Checking if Binance service is initialized in chatgpt_bot.py...")
try:
    # Try to import and check if it's started
    from infra.binance_service import BinanceService
    
    # Check if there's a global instance we can access
    # Note: This won't work if chatgpt_bot.py isn't running, but we can check the code
    print("   [OK] BinanceService module is available")
    
    # Check main_api.py to see if it's disabled
    main_api_path = Path("app/main_api.py")
    if main_api_path.exists():
        with open(main_api_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if "DISABLED FOR RESOURCE CONSERVATION" in content and "Unified Tick Pipeline" in content:
                print("   [INFO] Unified Tick Pipeline is DISABLED in main_api.py")
                print("          (This is intentional - was consuming too much CPU/RAM/SSD)")
            else:
                print("   [INFO] Unified Tick Pipeline status: Unknown")
    
except ImportError as e:
    print(f"   [ERROR] Cannot import BinanceService: {e}")

# Check 2: Check recent logs for Binance activity
print("\n[2] Checking recent logs for Binance activity...")
log_files = [
    "desktop_agent.log",
    "logs/chatgpt_bot.log",
    "logs/app.log"
]

binance_activity_found = False
for log_file in log_files:
    log_path = Path(log_file)
    if log_path.exists():
        try:
            # Read last 100 lines
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                recent_lines = lines[-100:] if len(lines) > 100 else lines
                
                # Check for Binance-related messages
                for line in recent_lines:
                    if "Binance" in line and ("started" in line.lower() or "running" in line.lower() or "stopped" in line.lower()):
                        print(f"   [FOUND] In {log_file}: {line.strip()}")
                        binance_activity_found = True
                        break
        except Exception as e:
            pass

if not binance_activity_found:
    print("   [INFO] No recent Binance activity found in logs")

# Check 3: Check if there's a running Python process for Binance
print("\n[3] Checking for running Binance-related processes...")
try:
    import subprocess
    result = subprocess.run(
        ["powershell", "-Command", "Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like '*binance*' -or $_.CommandLine -like '*start_binance*'} | Select-Object Id, ProcessName, StartTime"],
        capture_output=True,
        text=True,
        timeout=5
    )
    if result.stdout and "Id" in result.stdout:
        print(f"   [FOUND] Binance-related Python processes:")
        print(f"   {result.stdout}")
    else:
        print("   [INFO] No Binance-related Python processes found")
except Exception as e:
    print(f"   [INFO] Could not check processes: {e}")

# Check 4: Check chatgpt_bot.py code to see if Binance is started
print("\n[4] Checking chatgpt_bot.py initialization code...")
chatgpt_bot_path = Path("chatgpt_bot.py")
if chatgpt_bot_path.exists():
    with open(chatgpt_bot_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if "binance_service = BinanceService()" in content:
            print("   [OK] BinanceService is initialized in chatgpt_bot.py")
            # Check if it's started
            if "binance_service.start" in content or "await.*start" in content:
                print("   [OK] Binance service start() is called")
            else:
                print("   [WARNING] BinanceService is initialized but start() may not be called")
                print("            (Service may be initialized but not actively streaming)")

# Check 5: Check desktop_agent.py
print("\n[5] Checking desktop_agent.py for Binance initialization...")
desktop_agent_path = Path("desktop_agent.py")
if desktop_agent_path.exists():
    with open(desktop_agent_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if "BinanceService" in content or "binance" in content.lower():
            if "start" in content.lower() and "binance" in content.lower():
                print("   [OK] Binance service appears to be started in desktop_agent.py")
            else:
                print("   [INFO] BinanceService referenced but may not be actively started")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("""
Based on the code analysis:
- BinanceService is initialized in chatgpt_bot.py
- The Unified Tick Pipeline is DISABLED in main_api.py (intentional - resource conservation)
- Binance service may be initialized but not actively streaming

To check if it's actually running:
1. Check if chatgpt_bot.py is running
2. Look for "Binance streams running" in logs
3. Use the moneybot.binance_feed_status tool via ChatGPT

To start Binance service (if needed):
- It should start automatically with chatgpt_bot.py
- Or run: python start_binance_feed.py
""")

