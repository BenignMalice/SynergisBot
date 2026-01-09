"""
Comprehensive investigation:
1. Check Universal Manager logs for trailing stop attempts
2. Investigate why break-even SL wasn't set to entry price
3. Create verification script for future trades
"""
import asyncio
import json
import sqlite3
import os
from datetime import datetime, timedelta
from cursor_trading_bridge import get_bridge
from pathlib import Path

async def investigate():
    """Comprehensive investigation"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("COMPREHENSIVE INVESTIGATION: TRAILING STOPS & BREAK-EVEN")
    print("=" * 70)
    
    target_tickets = [177182974, 177182977]
    
    # 1. Check Universal Manager Database
    print("\n" + "=" * 70)
    print("1. CHECKING UNIVERSAL MANAGER DATABASE")
    print("=" * 70)
    
    db_paths = [
        "data/universal_sl_tp_manager.db",
        "universal_sl_tp_manager.db",
        "data/trading.db",
    ]
    
    found_db = None
    for db_path in db_paths:
        if os.path.exists(db_path):
            found_db = db_path
            break
    
    if found_db:
        print(f"\n✅ Found database: {found_db}")
        
        try:
            conn = sqlite3.connect(found_db)
            cursor = conn.cursor()
            
            # Get table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"   Tables: {', '.join(tables)}")
            
            # Check for trade states
            for ticket in target_tickets:
                print(f"\n   📊 Ticket {ticket}:")
                
                # Try different table names
                for table in tables:
                    if 'trade' in table.lower() or 'state' in table.lower():
                        try:
                            cursor.execute(f"SELECT * FROM {table} WHERE ticket = ?", (ticket,))
                            rows = cursor.fetchall()
                            
                            if rows:
                                print(f"      Found in {table}:")
                                # Get column names
                                cursor.execute(f"PRAGMA table_info({table})")
                                columns = [col[1] for col in cursor.fetchall()]
                                
                                for row in rows:
                                    for col, val in zip(columns, row):
                                        if val is not None:
                                            print(f"         {col}: {val}")
                        except:
                            pass
        except Exception as e:
            print(f"   ⚠️ Error accessing database: {e}")
    else:
        print(f"\n⚠️ Could not find Universal Manager database")
        print(f"   Checked paths: {db_paths}")
    
    # 2. Check Log Files
    print("\n" + "=" * 70)
    print("2. CHECKING LOG FILES")
    print("=" * 70)
    
    log_paths = [
        "logs",
        "data/logs",
        ".",
    ]
    
    log_files = []
    for log_path in log_paths:
        if os.path.exists(log_path):
            for file in Path(log_path).glob("*.log"):
                log_files.append(str(file))
    
    if log_files:
        print(f"\n✅ Found {len(log_files)} log file(s)")
        
        # Search for relevant log entries
        for ticket in target_tickets:
            print(f"\n   🔍 Searching for ticket {ticket} in logs...")
            
            for log_file in log_files[:5]:  # Check first 5 logs
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines[-500:], 1):  # Last 500 lines
                            if str(ticket) in line:
                                # Check for trailing stop or break-even messages
                                if any(keyword in line.lower() for keyword in [
                                    'trailing', 'breakeven', 'break-even', 'sl', 
                                    'stop loss', 'universal manager', 'intelligent exit'
                                ]):
                                    print(f"      {log_file}:{i}")
                                    print(f"         {line.strip()[:100]}...")
                except:
                    pass
    else:
        print(f"\n⚠️ Could not find log files")
    
    # 3. Investigate Break-Even Calculation
    print("\n" + "=" * 70)
    print("3. BREAK-EVEN CALCULATION INVESTIGATION")
    print("=" * 70)
    
    # Get closed trades
    trades_result = await bridge.get_recent_trades(days_back=1)
    trades_data = trades_result.get("data", {})
    trades = trades_data.get("trades", [])
    
    xau_trades = [
        t for t in trades 
        if t.get("ticket") in target_tickets and t.get("symbol") == "XAUUSDc"
    ]
    
    for trade in xau_trades:
        ticket = trade.get("ticket")
        entry = trade.get("entry_price", 0)
        direction = trade.get("direction", "N/A")
        
        # Based on alerts:
        if ticket == 177182974:
            alert_breakeven_sl = 4478.58693
            alert_old_sl = 4474.80
        elif ticket == 177182977:
            alert_breakeven_sl = 4478.60391
            alert_old_sl = 4474.50
        else:
            continue
        
        print(f"\n   📊 Ticket {ticket} ({direction}):")
        print(f"      Entry: ${entry:.2f}")
        print(f"      Alert Break-even SL: ${alert_breakeven_sl:.2f}")
        print(f"      Difference: ${entry - alert_breakeven_sl:.2f} ({((entry - alert_breakeven_sl) / entry * 100):.3f}%)")
        
        # Calculate what break-even should be
        # Code uses: entry_price - spread - tiny_buffer (0.1% of entry)
        spread_estimate = 0.15  # Typical XAUUSD spread
        tiny_buffer = entry * 0.001  # 0.1% of entry
        
        if direction == "BUY":
            calculated_be = entry - spread_estimate - tiny_buffer
            print(f"      Calculated BE (entry - spread - 0.1%): ${calculated_be:.2f}")
            print(f"      Alert BE: ${alert_breakeven_sl:.2f}")
            
            if abs(calculated_be - alert_breakeven_sl) < 1.0:
                print(f"      ✅ Break-even calculation matches expected formula")
            else:
                print(f"      ⚠️ Break-even calculation doesn't match expected")
                print(f"      💡 May be using different spread/buffer values")
        
        # Check if break-even is too far from entry
        distance_from_entry = abs(entry - alert_breakeven_sl)
        if distance_from_entry > entry * 0.001:  # More than 0.1%
            print(f"      ⚠️ Break-even SL is {distance_from_entry:.2f} points from entry")
            print(f"      💡 This is more than the 0.1% buffer - may cause small losses")
        else:
            print(f"      ✅ Break-even SL is within 0.1% of entry (acceptable)")
    
    # 4. Check for Trailing Stop Activity
    print("\n" + "=" * 70)
    print("4. TRAILING STOP ACTIVITY CHECK")
    print("=" * 70)
    
    for trade in xau_trades:
        ticket = trade.get("ticket")
        entry = trade.get("entry_price", 0)
        exit_price = trade.get("exit_price", 0)
        
        if ticket == 177182974:
            breakeven_sl = 4478.58693
        elif ticket == 177182977:
            breakeven_sl = 4478.60391
        else:
            continue
        
        print(f"\n   📊 Ticket {ticket}:")
        print(f"      Entry: ${entry:.2f}")
        print(f"      Break-even SL: ${breakeven_sl:.2f}")
        print(f"      Exit Price: ${exit_price:.2f}")
        
        # Check if exit was above break-even
        if exit_price > breakeven_sl:
            distance_above_be = exit_price - breakeven_sl
            print(f"      ✅ Exit was ${distance_above_be:.2f} above break-even SL")
            print(f"      💡 Trailing stops SHOULD have activated")
            print(f"      💡 Trailing should have moved SL from ${breakeven_sl:.2f} toward ${exit_price:.2f}")
            
            # Check if there's evidence of trailing
            print(f"      🔍 Checking for trailing stop evidence...")
            print(f"         • Check Universal Manager logs for SL modifications")
            print(f"         • Check if SL was modified between break-even and exit")
            print(f"         • If no trailing occurred, may be due to:")
            print(f"           - Manual close before trailing activated (30s check cycle)")
            print(f"           - Trailing not enabled for this strategy")
            print(f"           - Trailing distance too large (would widen stop)")
        else:
            print(f"      ⚠️ Exit was at or below break-even SL")
            print(f"      💡 Trailing stops wouldn't activate if price didn't move above BE")
    
    # 5. Create Verification Script
    print("\n" + "=" * 70)
    print("5. CREATING VERIFICATION SCRIPT FOR FUTURE TRADES")
    print("=" * 70)
    
    verification_script = """\"\"\"
Verify that trades are properly managed by Universal Manager
Checks: Registration, Break-even, Trailing Stops
\"\"\"
import asyncio
import sqlite3
import os
from cursor_trading_bridge import get_bridge
from datetime import datetime

async def verify_trade_management():
    \"\"\"Verify trade management for open positions\"\"\"
    bridge = get_bridge()
    
    print("=" * 70)
    print("TRADE MANAGEMENT VERIFICATION")
    print("=" * 70)
    
    # Get open positions
    positions_result = await bridge.registry.execute("moneybot.getPositions", {})
    positions_data = positions_result.get("data", {})
    positions = positions_data.get("positions", [])
    
    if not positions:
        print("\\n⚠️ No open positions found")
        return
    
    print(f"\\n📊 Open Positions: {len(positions)}")
    
    # Check Universal Manager database
    db_paths = [
        "data/universal_sl_tp_manager.db",
        "universal_sl_tp_manager.db",
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
        
        print(f"\\n📊 Ticket {ticket} ({symbol}):")
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
                for table in tables:
                    if 'trade' in table.lower():
                        try:
                            cursor.execute(f"SELECT * FROM {table} WHERE ticket = ?", (ticket,))
                            if cursor.fetchone():
                                registered = True
                                print(f"   ✅ Registered with Universal Manager")
                                break
                        except:
                            pass
                
                if not registered:
                    print(f"   ⚠️ NOT registered with Universal Manager")
                    print(f"   💡 Trade may not get trailing stops")
                
                conn.close()
            except Exception as e:
                print(f"   ⚠️ Could not check registration: {e}")
        else:
            print(f"   ⚠️ Could not find Universal Manager database")
        
        # Check break-even status
        if entry and sl:
            distance_from_entry = abs(entry - sl)
            if distance_from_entry < entry * 0.001:  # Within 0.1%
                print(f"   ✅ Break-even set (SL within 0.1% of entry)")
            else:
                print(f"   ⏸️ Break-even not set (SL is {distance_from_entry:.2f} from entry)")
        
        # Check if trailing should be active
        if profit > 0 and abs(entry - sl) < entry * 0.001:
            print(f"   💡 Trailing stops should be active")
            print(f"      • Break-even triggered")
            print(f"      • Trade in profit")
            print(f"      • Universal Manager should be trailing SL")

if __name__ == "__main__":
    asyncio.run(verify_trade_management())
"""
    
    with open("verify_trade_management.py", "w") as f:
        f.write(verification_script)
    
    print(f"\n✅ Created verification script: verify_trade_management.py")
    print(f"   Run this script to verify future trades are properly managed")
    
    # Summary
    print("\n" + "=" * 70)
    print("INVESTIGATION SUMMARY")
    print("=" * 70)
    
    print(f"\n✅ Findings:")
    print(f"   1. Break-even SL calculation:")
    print(f"      • Uses: entry - spread - 0.1% buffer")
    print(f"      • For entry $4,483.07: BE = $4,483.07 - $0.15 - $4.48 = $4,478.44")
    print(f"      • Alert showed: $4,478.59 (close match)")
    print(f"      • ⚠️ Break-even is ~$4.48 below entry (0.1% buffer)")
    print(f"      • This is by design to account for spread/commissions")
    
    print(f"\n   2. Trailing Stop Status:")
    print(f"      • Exit price was $4,483.27 (above break-even $4,478.59)")
    print(f"      • Trailing SHOULD have activated")
    print(f"      • Possible reasons it didn't:")
    print(f"        - Manual close before 30s check cycle")
    print(f"        - Trailing distance too large (would widen stop)")
    print(f"        - Trade not properly registered with Universal Manager")
    
    print(f"\n   3. Recommendations:")
    print(f"      • Run verify_trade_management.py for future trades")
    print(f"      • Check console logs for Universal Manager activity")
    print(f"      • Let trades run longer to allow trailing to activate")
    print(f"      • Consider adjusting break-even to be closer to entry (reduce buffer)")

if __name__ == "__main__":
    asyncio.run(investigate())
