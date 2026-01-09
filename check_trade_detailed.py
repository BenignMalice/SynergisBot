"""
Detailed check for trade 157495802 - check database, MT5, and logs.
"""

import sys
import sqlite3
from pathlib import Path
import json

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

project_root = Path(__file__).parent
ticket = 157495802

print("=" * 80)
print(f"DETAILED TRADE CHECK: Ticket {ticket}")
print("=" * 80)
print()

# ============================================================================
# 1. Check Database File Exists and Structure
# ============================================================================
print("[1/4] Checking Universal Manager Database...")
print("-" * 80)

db_path = project_root / "data" / "universal_sl_tp_trades.db"

if db_path.exists():
    print(f"  [OK] Database file exists: {db_path}")
    print(f"  Size: {db_path.stat().st_size} bytes")
    
    try:
        with sqlite3.connect(str(db_path)) as conn:
            # Check table structure
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"  Tables: {', '.join(tables)}")
            
            if 'universal_trades' in tables:
                # Count total trades
                cursor = conn.execute("SELECT COUNT(*) FROM universal_trades")
                count = cursor.fetchone()[0]
                print(f"  Total trades in database: {count}")
                
                # Check for our ticket
                cursor = conn.execute("""
                    SELECT ticket, symbol, strategy_type, managed_by, registered_at, 
                           breakeven_triggered, last_trailing_sl
                    FROM universal_trades 
                    WHERE ticket = ?
                """, (ticket,))
                
                row = cursor.fetchone()
                if row:
                    print(f"\n  [OK] Trade FOUND in database:")
                    print(f"    Ticket: {row[0]}")
                    print(f"    Symbol: {row[1]}")
                    print(f"    Strategy: {row[2]}")
                    print(f"    Managed By: {row[3]}")
                    print(f"    Registered At: {row[4]}")
                    print(f"    Breakeven Triggered: {bool(row[5])}")
                    print(f"    Last Trailing SL: {row[6]}")
                else:
                    print(f"\n  [WARN] Trade NOT in database")
                    
                    # Show recent trades
                    cursor = conn.execute("""
                        SELECT ticket, symbol, strategy_type, registered_at 
                        FROM universal_trades 
                        ORDER BY registered_at DESC 
                        LIMIT 5
                    """)
                    recent = cursor.fetchall()
                    if recent:
                        print(f"\n  Recent trades in database:")
                        for r in recent:
                            print(f"    Ticket {r[0]}: {r[1]} ({r[2]}) - {r[3]}")
                    else:
                        print(f"\n  [INFO] Database is empty")
            else:
                print(f"  [WARN] 'universal_trades' table not found")
                
    except Exception as e:
        print(f"  [ERROR] Error querying database: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"  [WARN] Database file not found: {db_path}")

print()

# ============================================================================
# 2. Check Intelligent Exit Manager Storage
# ============================================================================
print("[2/4] Checking Intelligent Exit Manager Storage...")
print("-" * 80)

storage_path = project_root / "data" / "intelligent_exits.json"

if storage_path.exists():
    print(f"  [OK] Storage file exists: {storage_path}")
    print(f"  Size: {storage_path.stat().st_size} bytes")
    
    try:
        with open(storage_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        rules = data.get("rules", {})
        print(f"  Total rules in storage: {len(rules)}")
        
        rule = rules.get(str(ticket))
        if rule:
            print(f"\n  [OK] Trade FOUND in Intelligent Exit Manager:")
            print(f"    Symbol: {rule.get('symbol')}")
            print(f"    Entry Price: {rule.get('entry_price')}")
            print(f"    Direction: {rule.get('direction')}")
            print(f"    Breakeven Triggered: {rule.get('breakeven_triggered', False)}")
            print(f"    Trailing Enabled: {rule.get('trailing_enabled', False)}")
            print(f"    Trailing Active: {rule.get('trailing_active', False)}")
            print(f"    Last Trailing SL: {rule.get('last_trailing_sl')}")
        else:
            print(f"\n  [WARN] Trade NOT in Intelligent Exit Manager storage")
            
            # Show recent tickets
            if rules:
                print(f"\n  Recent tickets in storage:")
                for t, r in list(rules.items())[:5]:
                    print(f"    Ticket {t}: {r.get('symbol')} - {r.get('created_at', 'N/A')}")
            else:
                print(f"\n  [INFO] Storage is empty")
                
    except Exception as e:
        print(f"  [ERROR] Error reading storage: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"  [WARN] Storage file not found: {storage_path}")

print()

# ============================================================================
# 3. Check MT5 Position
# ============================================================================
print("[3/4] Checking MT5 Position...")
print("-" * 80)

try:
    import MetaTrader5 as mt5
    
    if not mt5.initialize():
        print(f"  [ERROR] MT5 not initialized")
    else:
        position = mt5.positions_get(ticket=ticket)
        
        if position:
            pos = position[0]
            print(f"  [OK] Position EXISTS in MT5:")
            print(f"    Ticket: {pos.ticket}")
            print(f"    Symbol: {pos.symbol}")
            print(f"    Type: {pos.type}")
            print(f"    Volume: {pos.volume}")
            print(f"    Price Open: {pos.price_open}")
            print(f"    Price Current: {pos.price_current}")
            print(f"    SL: {pos.sl}")
            print(f"    TP: {pos.tp}")
            print(f"    Profit: {pos.profit}")
            print(f"    Time: {pos.time}")
        else:
            print(f"  [WARN] Position NOT found in MT5 (may be closed)")
            
            # Check all open positions
            all_positions = mt5.positions_get()
            if all_positions:
                print(f"\n  Open positions in MT5: {len(all_positions)}")
                for p in all_positions[:5]:
                    print(f"    Ticket {p.ticket}: {p.symbol} {p.type} @ {p.price_open}")
            else:
                print(f"\n  [INFO] No open positions in MT5")
        
        mt5.shutdown()
        
except ImportError:
    print(f"  [WARN] MetaTrader5 not available")
except Exception as e:
    print(f"  [ERROR] Error checking MT5: {e}")
    import traceback
    traceback.print_exc()

print()

# ============================================================================
# 4. Check Logs for Registration
# ============================================================================
print("[4/4] Checking Logs for Registration Events...")
print("-" * 80)

log_path = project_root / "data" / "logs" / "chatgpt_bot.log"

if log_path.exists():
    print(f"  [OK] Log file exists: {log_path}")
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Search for ticket in logs
        relevant_lines = [line for line in lines if str(ticket) in line]
        
        if relevant_lines:
            print(f"\n  Found {len(relevant_lines)} log entries for ticket {ticket}")
            print(f"\n  Key events:")
            
            # Filter for key events
            key_events = [
                l for l in relevant_lines 
                if any(keyword in l.lower() for keyword in [
                    'registered', 'breakeven', 'trailing', 'activated', 
                    'intelligent exit', 'universal', 'executed'
                ])
            ]
            
            for line in key_events[-10:]:  # Last 10 key events
                # Extract timestamp and message
                parts = line.split(' - ', 2)
                if len(parts) >= 3:
                    timestamp = parts[0]
                    module = parts[1]
                    message = parts[2].strip()
                    print(f"    [{timestamp}] {module}: {message[:100]}")
        else:
            print(f"\n  [WARN] No log entries found for ticket {ticket}")
    except Exception as e:
        print(f"  [ERROR] Error reading logs: {e}")
else:
    print(f"  [WARN] Log file not found: {log_path}")

print()

# ============================================================================
# SUMMARY
# ============================================================================
print("=" * 80)
print("SUMMARY")
print("=" * 80)

# Re-check key findings
try:
    # Check database
    db_found = False
    if db_path.exists():
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute("SELECT managed_by FROM universal_trades WHERE ticket = ?", (ticket,))
            row = cursor.fetchone()
            if row:
                db_found = True
                print(f"✅ Trade {ticket} IS in Universal Manager database")
                print(f"   Managed by: {row[0]}")
    
    # Check Intelligent Exit Manager
    iem_found = False
    if storage_path.exists():
        with open(storage_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if str(ticket) in data.get("rules", {}):
                iem_found = True
                print(f"✅ Trade {ticket} IS in Intelligent Exit Manager storage")
    
    # Check MT5
    mt5_found = False
    try:
        import MetaTrader5 as mt5
        if mt5.initialize():
            position = mt5.positions_get(ticket=ticket)
            if position:
                mt5_found = True
                print(f"✅ Trade {ticket} EXISTS in MT5 (still open)")
            mt5.shutdown()
    except:
        pass
    
    if not db_found and not iem_found and not mt5_found:
        print(f"❌ Trade {ticket} NOT found in:")
        print(f"   - Universal Manager database")
        print(f"   - Intelligent Exit Manager storage")
        print(f"   - MT5 (position may be closed)")
        print(f"\n   This suggests the trade was closed and cleaned up.")
        print(f"   However, logs show it WAS registered at 11:33:30.")
        print(f"   Check if there's a cleanup mechanism that removes closed trades.")
    elif db_found:
        print(f"\n   Trade IS registered with Universal Manager")
        print(f"   Universal Manager should be managing trailing stops")
    elif iem_found:
        print(f"\n   Trade IS managed by Intelligent Exit Manager")
        print(f"   Intelligent Exit Manager is handling breakeven and trailing")
        
except Exception as e:
    print(f"Error generating summary: {e}")

print()
print("=" * 80)

