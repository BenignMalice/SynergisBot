"""
Check if Binance system is currently operational
"""
import sys
import os
import asyncio
import httpx
from pathlib import Path

print("=" * 80)
print("BINANCE SYSTEM OPERATIONAL STATUS CHECK")
print("=" * 80)

# Method 1: Check via API endpoint (if desktop_agent is running)
print("\n[1] Checking Binance status via API...")
try:
    async def check_via_api():
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Try to check via the desktop agent's binance_feed_status tool
                # This requires the agent to be running and connected
                response = await client.get("http://localhost:8000/health")
                if response.status_code == 200:
                    print("   [OK] Main API server is running")
                    print("   [INFO] Use ChatGPT tool 'moneybot.binance_feed_status' to check actual status")
                else:
                    print(f"   [WARNING] API server returned: {response.status_code}")
        except httpx.ConnectError:
            print("   [INFO] Cannot connect to API server (desktop_agent may not be running)")
        except Exception as e:
            print(f"   [INFO] API check failed: {e}")
    
    asyncio.run(check_via_api())
except Exception as e:
    print(f"   [INFO] Could not check via API: {e}")

# Method 2: Check logs for recent Binance activity
print("\n[2] Checking recent logs for Binance activity...")
log_file = Path("desktop_agent.log")
if log_file.exists():
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            # Get last 500 lines
            recent_lines = lines[-500:] if len(lines) > 500 else lines
            
            # Look for Binance start/stop messages
            binance_started = None
            binance_stopped = None
            
            for i, line in enumerate(reversed(recent_lines)):
                if "Binance Service initialized and started" in line:
                    # Extract timestamp
                    parts = line.split(" - ")
                    if len(parts) > 0:
                        binance_started = parts[0].strip()
                    break
                elif "Binance.*stopped" in line or "Stopping Binance" in line:
                    parts = line.split(" - ")
                    if len(parts) > 0:
                        binance_stopped = parts[0].strip()
                    break
            
            if binance_started:
                print(f"   [FOUND] Binance Service was started at: {binance_started}")
                if binance_stopped:
                    print(f"   [FOUND] Binance Service was stopped at: {binance_stopped}")
                    print("   [STATUS] Binance service is NOT currently running")
                else:
                    print("   [STATUS] Binance service appears to be RUNNING")
                    print("           (No stop message found after start)")
            else:
                print("   [INFO] No recent Binance start message found in logs")
                print("          Service may not have been started in this session")
    except Exception as e:
        print(f"   [ERROR] Could not read log file: {e}")

# Method 3: Check code to see if it's enabled
print("\n[3] Checking code configuration...")
main_api_path = Path("app/main_api.py")
if main_api_path.exists():
    with open(main_api_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if "DISABLED FOR RESOURCE CONSERVATION" in content:
            print("   [INFO] Unified Tick Pipeline is DISABLED in main_api.py")
            print("          This was intentionally disabled due to high CPU/RAM/SSD usage")
            print("          The system uses lightweight Multi-Timeframe Streamer instead")

desktop_agent_path = Path("desktop_agent.py")
if desktop_agent_path.exists():
    with open(desktop_agent_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if "await registry.binance_service.start" in content:
            print("   [OK] desktop_agent.py has code to start Binance service")
            print("          It will start automatically when desktop_agent.py runs")
        else:
            print("   [WARNING] desktop_agent.py may not start Binance service")

print("\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)
print("""
To check if Binance is currently running:
1. Use ChatGPT tool: "Check Binance feed status" or "moneybot.binance_feed_status"
2. Check if desktop_agent.py is running (it starts Binance automatically)
3. Look for "Binance Service initialized and started" in desktop_agent.log

Current Status:
- Binance service IS started in desktop_agent.py (code shows it starts automatically)
- Unified Tick Pipeline is DISABLED in main_api.py (intentional - resource conservation)
- Binance streams only BTCUSD (btcusdt) - other symbols not supported by Binance

If you want to disable Binance to save resources:
- Comment out the Binance start code in desktop_agent.py around line 10552
- Or set registry.binance_service = None after initialization

If you want to re-enable it:
- The code is already there, just ensure desktop_agent.py is running
- It will start automatically on agent startup
""")

