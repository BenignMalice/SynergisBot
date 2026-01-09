"""
Check BTC Trade Breakeven Status

Checks if live BTC trades have moved to breakeven by:
1. Getting open BTC positions from MT5
2. Checking Intelligent Exit Manager for breakeven status
3. Checking Universal SL/TP Manager for breakeven status
4. Comparing SL to entry price to determine if at breakeven
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import codecs
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

try:
    import MetaTrader5 as mt5
    if not mt5.initialize():
        print("[ERROR] MT5 initialization failed")
        sys.exit(1)
except ImportError:
    print("[ERROR] MetaTrader5 not available")
    sys.exit(1)

print("=" * 70)
print("BTC TRADE BREAKEVEN STATUS CHECK")
print("=" * 70)
print()

# Get open BTC positions
positions = mt5.positions_get()
if not positions:
    print("[INFO] No open positions found")
    sys.exit(0)

btc_positions = [p for p in positions if 'BTC' in p.symbol.upper()]

if not btc_positions:
    print("[INFO] No open BTC positions found")
    sys.exit(0)

print(f"[1/4] OPEN BTC POSITIONS")
print("-" * 70)
print(f"[OK] Found {len(btc_positions)} open BTC position(s):")
print()

for pos in btc_positions:
    direction = "BUY" if pos.type == 0 else "SELL"
    entry = pos.price_open
    current_sl = pos.sl if pos.sl else 0.0
    current_price = pos.price_current
    profit = pos.profit
    
    # Calculate if SL is at breakeven (within 0.1% of entry)
    sl_at_breakeven = False
    if current_sl > 0:
        if direction == "BUY":
            # For BUY, breakeven SL is at or slightly above entry
            sl_at_breakeven = abs(current_sl - entry) / entry < 0.001
        else:  # SELL
            # For SELL, breakeven SL is at or slightly above entry
            sl_at_breakeven = abs(current_sl - entry) / entry < 0.001
    
    print(f"   Ticket: {pos.ticket}")
    print(f"   Symbol: {pos.symbol}")
    print(f"   Direction: {direction}")
    print(f"   Entry: {entry:.2f}")
    current_sl_str = f"{current_sl:.2f}" if current_sl > 0 else "None"
    print(f"   Current SL: {current_sl_str}")
    print(f"   Current Price: {current_price:.2f}")
    print(f"   Profit: {profit:.2f}")
    print(f"   SL at Breakeven: {'[YES]' if sl_at_breakeven else '[NO]'}")
    if sl_at_breakeven:
        sl_distance = abs(current_sl - entry)
        print(f"   SL Distance from Entry: {sl_distance:.5f} ({sl_distance/entry*100:.3f}%)")
    print()

# Check Intelligent Exit Manager
print(f"[2/4] INTELLIGENT EXIT MANAGER STATUS")
print("-" * 70)
try:
    from infra.intelligent_exit_manager import IntelligentExitManager
    from infra.mt5_service import MT5Service
    
    # Initialize MT5 service for Intelligent Exit Manager
    mt5_service = MT5Service()
    exit_manager = IntelligentExitManager(mt5_service=mt5_service)
    
    for pos in btc_positions:
        # Get exit rule for this ticket
        rule = exit_manager.get_rule(pos.ticket)
        
        if rule:
            print(f"   Ticket {pos.ticket}:")
            print(f"      Breakeven triggered: {rule.breakeven_triggered}")
            print(f"      Trailing enabled: {rule.trailing_enabled}")
            print(f"      Trailing active: {rule.trailing_active}")
            print(f"      Last trailing SL: {rule.last_trailing_sl if rule.last_trailing_sl else 'None'}")
            print(f"      Entry price: {rule.entry_price:.2f}")
            print(f"      Initial SL: {rule.initial_sl:.2f}")
        else:
            print(f"   Ticket {pos.ticket}: No exit rule found")
        print()
except Exception as e:
    print(f"[WARN] Could not check Intelligent Exit Manager: {e}")
    import traceback
    traceback.print_exc()
    print()

# Check Universal SL/TP Manager
print(f"[3/4] UNIVERSAL SL/TP MANAGER STATUS")
print("-" * 70)
try:
    from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
    
    universal_manager = UniversalDynamicSLTPManager()
    
    for pos in btc_positions:
        # Check if trade is registered
        with universal_manager.active_trades_lock:
            trade_state = universal_manager.active_trades.get(pos.ticket)
        
        if trade_state:
            print(f"   Ticket {pos.ticket}:")
            print(f"      Breakeven triggered: {trade_state.breakeven_triggered}")
            print(f"      Trailing enabled: {trade_state.resolved_trailing_rules.get('trailing_enabled', False) if trade_state.resolved_trailing_rules else False}")
            print(f"      Last SL modification: {trade_state.last_sl_modification_time if trade_state.last_sl_modification_time else 'None'}")
        else:
            print(f"   Ticket {pos.ticket}: Not registered in Universal Manager")
        print()
except Exception as e:
    print(f"[WARN] Could not check Universal SL/TP Manager: {e}")
    print()

# Check recent logs for breakeven activity
print(f"[4/4] RECENT BREAKEVEN ACTIVITY (from logs)")
print("-" * 70)
try:
    import re
    from datetime import datetime, timedelta
    
    log_file = "data/logs/chatgpt_bot.log"
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Get last 500 lines
        recent_lines = lines[-500:] if len(lines) > 500 else lines
        
        # Search for breakeven activity for BTC trades
        btc_tickets = [str(p.ticket) for p in btc_positions]
        breakeven_activity = []
        
        for line in recent_lines:
            for ticket in btc_tickets:
                if ticket in line and ('breakeven' in line.lower() or 'moved to breakeven' in line.lower() or 'breakeven triggered' in line.lower()):
                    # Extract timestamp
                    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if timestamp_match:
                        breakeven_activity.append((timestamp_match.group(1), line.strip()))
        
        if breakeven_activity:
            print(f"   [OK] Found {len(breakeven_activity)} breakeven activity log(s):")
            for timestamp, log_line in breakeven_activity[-10:]:  # Last 10
                print(f"      {timestamp}: {log_line[:100]}...")
        else:
            print(f"   [INFO] No recent breakeven activity found in logs")
    else:
        print(f"   [WARN] Log file not found: {log_file}")
except Exception as e:
    print(f"   [WARN] Could not check logs: {e}")

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print()

for pos in btc_positions:
    direction = "BUY" if pos.type == 0 else "SELL"
    entry = pos.price_open
    current_sl = pos.sl if pos.sl else 0.0
    
    # Check if at breakeven
    sl_at_breakeven = False
    if current_sl > 0:
        sl_at_breakeven = abs(current_sl - entry) / entry < 0.001
    
    print(f"Ticket {pos.ticket} ({pos.symbol} {direction}):")
    print(f"   Entry: {entry:.2f}")
    current_sl_str = f"{current_sl:.2f}" if current_sl > 0 else "None"
    print(f"   Current SL: {current_sl_str}")
    
    if sl_at_breakeven:
        print(f"   [OK] SL is at breakeven (within 0.1% of entry)")
    else:
        sl_distance = abs(current_sl - entry) if current_sl > 0 else 0
        sl_percent = (sl_distance / entry * 100) if current_sl > 0 else 0
        if direction == "BUY":
            if current_sl < entry:
                print(f"   [INFO] SL is below entry ({sl_percent:.3f}% below) - not at breakeven yet")
            else:
                print(f"   [INFO] SL is above entry ({sl_percent:.3f}% above) - may be at breakeven")
        else:  # SELL
            if current_sl > entry:
                print(f"   [INFO] SL is above entry ({sl_percent:.3f}% above) - not at breakeven yet")
            else:
                print(f"   [INFO] SL is below entry ({sl_percent:.3f}% below) - may be at breakeven")
    print()

print("=" * 70)


