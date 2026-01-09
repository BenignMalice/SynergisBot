"""
Check Trailing Stop Status for Live XAU Trades
Shows if trailing stops are active and working for XAUUSD positions
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass

print("=" * 80)
print("XAU TRADING - TRAILING STOP STATUS CHECK")
print("=" * 80)
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Check 1: Get Open XAU Positions
print("[1/4] OPEN XAU POSITIONS")
print("-" * 80)
try:
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    if not mt5_service.connect():
        print("[ERROR] MT5 not connected")
        sys.exit(1)
    
    positions = mt5_service.get_positions()
    xau_positions = [p for p in positions if 'XAU' in p.symbol.upper() or 'GOLD' in p.symbol.upper()]
    
    if not xau_positions:
        print("[INFO] No open XAU positions found")
        print()
        print("=" * 80)
        print("SUMMARY: No XAU trades to check")
        print("=" * 80)
        sys.exit(0)
    
    print(f"[OK] Found {len(xau_positions)} open XAU position(s):")
    for pos in xau_positions:
        direction = "BUY" if pos.type == 0 else "SELL"
        profit = pos.profit
        print(f"   Ticket: {pos.ticket}")
        print(f"   Symbol: {pos.symbol}")
        print(f"   Direction: {direction}")
        print(f"   Entry: {pos.price_open:.2f}")
        print(f"   Current SL: {pos.sl:.2f}" if pos.sl else "   Current SL: None")
        print(f"   Current TP: {pos.tp:.2f}" if pos.tp else "   Current TP: None")
        print(f"   Current Price: {pos.price_current:.2f}")
        print(f"   Profit: {profit:.2f}")
        print()
    
except Exception as e:
    print(f"[ERROR] Failed to get positions: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Check 2: Universal SL/TP Manager Status
print("[2/4] UNIVERSAL SL/TP MANAGER STATUS")
print("-" * 80)
try:
    from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
    
    manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
    
    print("[OK] Universal Manager initialized")
    
    # Check each XAU position
    for pos in xau_positions:
        ticket = pos.ticket
        print(f"\n   Checking ticket {ticket} ({pos.symbol}):")
        
        with manager.active_trades_lock:
            trade_state = manager.active_trades.get(ticket)
        
        if trade_state:
            print(f"   [OK] Trade found in Universal Manager")
            print(f"      Breakeven triggered: {trade_state.breakeven_triggered}")
            print(f"      Trailing enabled: {trade_state.resolved_trailing_rules.get('trailing_enabled', True)}")
            print(f"      Trailing method: {trade_state.resolved_trailing_rules.get('trailing_method', 'N/A')}")
            print(f"      Last SL modification: {trade_state.last_sl_modification_time}")
            print(f"      Last trailing SL: {trade_state.last_trailing_sl}")
            
            # Check if trailing should be active
            if trade_state.breakeven_triggered:
                trailing_enabled = trade_state.resolved_trailing_rules.get('trailing_enabled', True)
                if trailing_enabled:
                    print(f"   [OK] Trailing should be ACTIVE (breakeven triggered + trailing enabled)")
                    
                    # Calculate what trailing SL should be
                    rules = trade_state.resolved_trailing_rules
                    atr_timeframe = rules.get('trailing_timeframe', 'M15')
                    current_atr = manager._get_current_atr(pos.symbol, atr_timeframe)
                    
                    if current_atr and current_atr > 0:
                        atr_multiplier = rules.get('atr_multiplier', 1.5)
                        trailing_distance = current_atr * atr_multiplier
                        
                        if pos.type == 0:  # BUY
                            ideal_trailing_sl = pos.price_current - trailing_distance
                        else:  # SELL
                            ideal_trailing_sl = pos.price_current + trailing_distance
                        
                        print(f"      ATR ({atr_timeframe}): {current_atr:.2f}")
                        print(f"      ATR Multiplier: {atr_multiplier}x")
                        print(f"      Trailing Distance: {trailing_distance:.2f}")
                        print(f"      Ideal Trailing SL: {ideal_trailing_sl:.2f}")
                        print(f"      Current SL: {pos.sl:.2f}" if pos.sl else "      Current SL: None")
                        
                        if pos.sl:
                            sl_diff = abs(ideal_trailing_sl - pos.sl)
                            if sl_diff < 1.0:  # Within 1 point
                                print(f"      [OK] SL is at trailing target (difference: {sl_diff:.2f})")
                            else:
                                print(f"      [WARN] SL differs from trailing target by {sl_diff:.2f}")
                                print(f"      -> Trailing may not have updated yet (checks every 30s)")
                    else:
                        print(f"      [WARN] ATR calculation failed - using fallback method")
                else:
                    print(f"   [INFO] Trailing is DISABLED for this strategy")
            else:
                print(f"   [INFO] Breakeven not triggered yet - trailing will activate after breakeven")
        else:
            print(f"   [WARN] Trade NOT found in Universal Manager")
            print(f"      -> Trade may be managed by Intelligent Exit Manager instead")
            print(f"      -> Or trade was opened before Universal Manager was initialized")
    
except Exception as e:
    print(f"[ERROR] Failed to check Universal Manager: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 3: Intelligent Exit Manager Status
print("[3/4] INTELLIGENT EXIT MANAGER STATUS")
print("-" * 80)
try:
    from infra.intelligent_exit_manager import IntelligentExitManager
    
    exit_manager = IntelligentExitManager(mt5_service=mt5_service)
    rules = exit_manager.get_all_rules()
    
    print(f"[OK] Intelligent Exit Manager initialized")
    print(f"   Active exit rules: {len(rules)}")
    
    xau_rules = [r for r in rules if 'XAU' in r.symbol.upper() or 'GOLD' in r.symbol.upper()]
    
    if xau_rules:
        print(f"\n   Found {len(xau_rules)} XAU exit rule(s):")
        for rule in xau_rules:
            print(f"\n      Ticket: {rule.ticket}")
            print(f"      Symbol: {rule.symbol}")
            print(f"      Direction: {rule.direction}")
            print(f"      Entry: {rule.entry_price:.2f}")
            print(f"      Breakeven triggered: {rule.breakeven_triggered}")
            print(f"      Trailing enabled: {rule.trailing_enabled}")
            print(f"      Trailing active: {rule.trailing_active}")
            print(f"      Last trailing SL: {rule.last_trailing_sl}")
            print(f"      Last check: {rule.last_check}")
            
            if rule.trailing_active:
                print(f"      [OK] Trailing is ACTIVE")
            elif rule.breakeven_triggered and rule.trailing_enabled:
                print(f"      [WARN] Breakeven triggered but trailing not active")
            elif not rule.breakeven_triggered:
                print(f"      [INFO] Breakeven not triggered yet")
    else:
        print(f"   [INFO] No XAU exit rules found")
        print(f"      -> XAU trades may be managed by Universal Manager only")
    
except Exception as e:
    print(f"[ERROR] Failed to check Intelligent Exit Manager: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 4: Recent Trailing Stop Activity (from logs)
print("[4/4] RECENT TRAILING STOP ACTIVITY (from logs)")
print("-" * 80)
try:
    log_files = [
        Path("desktop_agent.log"),
        Path("data/logs/auto_execution.log"),
        Path("data/logs/errors.log"),
    ]
    
    trailing_keywords = [
        "trailing stop",
        "trailing_stop",
        "ATR Trailing",
        "moved SL",
        "trailing_active"
    ]
    
    found_activity = False
    
    for log_file in log_files:
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    # Check last 200 lines
                    for line in lines[-200:]:
                        line_lower = line.lower()
                        # Check if it's XAU-related and contains trailing keywords
                        if ('xau' in line_lower or 'gold' in line_lower) and any(kw in line_lower for kw in trailing_keywords):
                            # Extract timestamp and message
                            if ' - ' in line:
                                parts = line.split(' - ', 2)
                                if len(parts) >= 3:
                                    timestamp = parts[0]
                                    message = parts[2].strip()
                                    print(f"   [{timestamp}] {message[:100]}")
                                    found_activity = True
            except Exception as e:
                pass  # Skip files that can't be read
    
    if not found_activity:
        print("   [INFO] No recent trailing stop activity found in logs")
        print("      -> Trailing may not have triggered yet")
        print("      -> Or activity is in different log file")
    
except Exception as e:
    print(f"[ERROR] Failed to check logs: {e}")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)

# Final summary
for pos in xau_positions:
    print(f"\nTicket {pos.ticket} ({pos.symbol}):")
    print(f"   Current SL: {pos.sl:.2f}" if pos.sl else "   Current SL: None")
    print(f"   Entry: {pos.price_open:.2f}")
    
    # Check if SL has moved from entry (indicates breakeven/trailing)
    if pos.sl:
        if pos.type == 0:  # BUY
            if pos.sl > pos.price_open:
                print(f"   [OK] SL moved above entry - breakeven/trailing active")
            elif abs(pos.sl - pos.price_open) < 1.0:
                print(f"   [INFO] SL at/near entry - breakeven may be active")
            else:
                print(f"   [INFO] SL below entry - initial stop loss")
        else:  # SELL
            if pos.sl < pos.price_open:
                print(f"   [OK] SL moved below entry - breakeven/trailing active")
            elif abs(pos.sl - pos.price_open) < 1.0:
                print(f"   [INFO] SL at/near entry - breakeven may be active")
            else:
                print(f"   [INFO] SL above entry - initial stop loss")

print()
print("=" * 80)
print("Next Steps:")
print("  1. If trailing not active, check if breakeven has been triggered")
print("  2. Monitor logs for 'ATR Trailing Stop' messages")
print("  3. Check Universal Manager is running and monitoring trades")
print("  4. Verify trailing_enabled is True in strategy config")
print("=" * 80)
