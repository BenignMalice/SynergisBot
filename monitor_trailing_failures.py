"""
Monitor trailing stop failures and ATR calculation issues

Usage:
    # Activate venv first (Windows PowerShell):
    .venv\Scripts\Activate.ps1
    
    # Then run:
    python monitor_trailing_failures.py
    
    # Or directly with venv Python (Windows):
    .venv\Scripts\python.exe monitor_trailing_failures.py
"""
import asyncio
import re
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Check if running in venv
if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    venv_python = os.path.join(os.path.dirname(__file__), '.venv', 'Scripts', 'python.exe')
    if os.path.exists(venv_python):
        print(f"[INFO] Not running in venv. Use: {venv_python} {__file__}")
        print(f"[INFO] Or activate venv with: .venv\\Scripts\\activate (Windows)")

from cursor_trading_bridge import get_bridge

async def monitor_trailing_failures():
    """Monitor trailing stop failures"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("TRAILING STOP FAILURE MONITORING")
    print("=" * 70)
    
    # Check log files for ATR failures
    print("\n1. Checking Log Files for ATR Failures:")
    print("-" * 70)
    
    log_paths = [
        "data/logs",
        "logs",
        ".",
    ]
    
    log_files = []
    for log_path in log_paths:
        if Path(log_path).exists():
            for file in Path(log_path).glob("*.log"):
                log_files.append(str(file))
    
    if log_files:
        print(f"\n   Found {len(log_files)} log file(s)")
        
        # Search for ATR failures in last hour
        cutoff_time = datetime.now() - timedelta(hours=1)
        atr_failures = []
        
        for log_file in log_files[:3]:  # Check first 3 logs
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    
                    for i, line in enumerate(lines[-1000:], 1):  # Last 1000 lines
                        if "ATR" in line.upper() and ("FAILED" in line.upper() or "WARNING" in line.upper()):
                            # Try to extract timestamp
                            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                            if timestamp_match:
                                try:
                                    log_time = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
                                    if log_time >= cutoff_time:
                                        atr_failures.append({
                                            "file": log_file,
                                            "line": i,
                                            "time": log_time,
                                            "message": line.strip()[:150]
                                        })
                                except:
                                    pass
            except:
                pass
        
        if atr_failures:
            print(f"\n   Found {len(atr_failures)} ATR failure(s) in last hour:")
            for failure in atr_failures[:10]:  # Show first 10
                print(f"      {failure['time']}: {failure['message']}")
        else:
            print(f"\n   OK: No ATR failures found in last hour")
    else:
        print(f"\n   WARNING: Could not find log files")
    
    # Check current positions
    print("\n2. Checking Current Positions:")
    print("-" * 70)
    
    try:
        positions_result = await bridge.registry.execute("moneybot.getPositions", {})
        positions_data = positions_result.get("data", {})
        positions = positions_data.get("positions", [])
        
        if positions:
            print(f"\n   Found {len(positions)} open position(s)")
            
            for pos in positions:
                ticket = pos.get("ticket")
                symbol = pos.get("symbol", "")
                entry = pos.get("price_open", 0)
                sl = pos.get("sl", 0)
                profit = pos.get("profit", 0)
                
                print(f"\n   Position {ticket} ({symbol}):")
                print(f"      Entry: ${entry:.2f} | SL: ${sl:.2f} | P&L: ${profit:.2f}")
                
                # Check if break-even set
                if entry and sl:
                    distance = abs(entry - sl)
                    if distance < entry * 0.001:  # Within 0.1%
                        print(f"      OK: Break-even set")
                        if profit > 0:
                            print(f"      INFO: Trade in profit - trailing should be active")
                            print(f"      Monitor logs for 'ATR calculation failed' warnings")
                    else:
                        print(f"      INFO: Break-even not set yet")
        else:
            print(f"\n   No open positions")
    except Exception as e:
        print(f"\n   ERROR: Could not check positions: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("MONITORING SUMMARY")
    print("=" * 70)
    
    print(f"\nRecommendations:")
    print(f"   1. Monitor logs for 'ATR calculation failed' warnings")
    print(f"   2. If ATR fails, fallback methods should activate automatically")
    print(f"   3. Check Discord for ATR failure alerts")
    print(f"   4. Run test_atr_calculation.py to verify ATR is working")
    print(f"   5. Run verify_trade_management.py to check trade registration")

if __name__ == "__main__":
    asyncio.run(monitor_trailing_failures())
