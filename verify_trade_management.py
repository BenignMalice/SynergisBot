"""
Verify that trades are properly managed by Universal Manager
Checks: Registration, Break-even, Trailing Stops

Usage:
    # Activate venv first (Windows PowerShell):
    .venv\Scripts\Activate.ps1
    
    # Then run:
    python verify_trade_management.py
    
    # Or directly with venv Python (Windows):
    .venv\Scripts\python.exe verify_trade_management.py
"""
import asyncio
import sqlite3
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Check if running in venv
if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    venv_python = os.path.join(os.path.dirname(__file__), '.venv', 'Scripts', 'python.exe')
    if os.path.exists(venv_python):
        print(f"[INFO] Not running in venv. Use: {venv_python} {__file__}")
        print(f"[INFO] Or activate venv with: .venv\\Scripts\\activate (Windows)")

from cursor_trading_bridge import get_bridge

async def verify_trade_management():
    """Verify trade management for open positions"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("TRADE MANAGEMENT VERIFICATION")
    print("=" * 70)
    
    # Get open positions
    positions_result = await bridge.registry.execute("moneybot.getPositions", {})
    positions_data = positions_result.get("data", {})
    positions = positions_data.get("positions", [])
    
    if not positions:
        print("\n⚠️ No open positions found")
        return
    
    print(f"\n📊 Open Positions: {len(positions)}")
    
    # Check Universal Manager database
    db_paths = [
        "data/universal_sl_tp_trades.db",
        "data/universal_sl_tp_manager.db",
        "universal_sl_tp_trades.db",
    ]
    
    found_db = None
    for db_path in db_paths:
        if os.path.exists(db_path):
            found_db = db_path
            break
    
    for pos in positions:
        ticket = pos.get("ticket")
        symbol = pos.get("symbol", "")
        entry = pos.get("price_open", 0)
        sl = pos.get("sl", 0)
        tp = pos.get("tp", 0)
        profit = pos.get("profit", 0)
        direction = pos.get("type", 0)  # 0=BUY, 1=SELL
        
        print(f"\n📊 Ticket {ticket} ({symbol}):")
        print(f"   Entry: ${entry:.2f} | SL: ${sl:.2f} | TP: ${tp:.2f}")
        print(f"   Current P&L: ${profit:.2f}")
        
        # Check registration
        if found_db:
            try:
                conn = sqlite3.connect(found_db)
                cursor = conn.cursor()
                
                # Try to find trade state
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                registered = False
                trade_state = None
                
                for table in tables:
                    if 'trade' in table.lower() or 'state' in table.lower():
                        try:
                            cursor.execute(f"SELECT * FROM {table} WHERE ticket = ?", (ticket,))
                            row = cursor.fetchone()
                            if row:
                                registered = True
                                # Get column names
                                cursor.execute(f"PRAGMA table_info({table})")
                                columns = [col[1] for col in cursor.fetchall()]
                                trade_state = dict(zip(columns, row))
                                break
                        except:
                            pass
                
                if registered:
                    print(f"   ✅ Registered with Universal Manager")
                    
                    # Check break-even status
                    if trade_state:
                        be_triggered = trade_state.get("breakeven_triggered", 0)
                        strategy = trade_state.get("strategy_type", "N/A")
                        print(f"   Strategy: {strategy}")
                        print(f"   Break-even Triggered: {'✅ YES' if be_triggered else '⏸️ NO'}")
                else:
                    print(f"   ⚠️ NOT registered with Universal Manager")
                    print(f"   💡 Trade may not get trailing stops")
                
                conn.close()
            except Exception as e:
                print(f"   ⚠️ Could not check registration: {e}")
        else:
            print(f"   ⚠️ Could not find Universal Manager database")
            print(f"   Checked: {db_paths}")
        
        # Check break-even status
        if entry and sl:
            distance_from_entry = abs(entry - sl)
            be_threshold = entry * 0.001  # 0.1% of entry
            
            if distance_from_entry < be_threshold:
                print(f"   ✅ Break-even set (SL within 0.1% of entry)")
                print(f"      Distance: {distance_from_entry:.2f} points")
            else:
                print(f"   ⏸️ Break-even not set (SL is {distance_from_entry:.2f} from entry)")
                
                # Calculate when break-even should trigger
                if direction == 0:  # BUY
                    risk = entry - sl
                    reward = tp - entry
                    if reward > 0:
                        be_trigger_price = entry + (risk * 0.3)  # 0.3R
                        print(f"      Break-even triggers at: ${be_trigger_price:.2f} (0.3R)")
        
        # Check if trailing should be active
        if profit > 0 and entry and sl:
            distance_from_entry = abs(entry - sl)
            if distance_from_entry < entry * 0.001:  # Within 0.1%
                print(f"   💡 Trailing stops should be active")
                print(f"      • Break-even triggered ✅")
                print(f"      • Trade in profit ✅")
                print(f"      • Universal Manager should be trailing SL")
                print(f"      • Check logs for 'ATR-based SL calculation' messages")
    
    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    print(f"\n💡 What to Monitor:")
    print(f"   1. Check logs for 'ATR-based SL calculation failed' warnings")
    print(f"   2. Verify SL is moving as price moves in your favor")
    print(f"   3. If ATR fails, trailing stops won't work")
    print(f"   4. Consider manual trailing if ATR continues to fail")

if __name__ == "__main__":
    asyncio.run(verify_trade_management())
