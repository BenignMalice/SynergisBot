"""
Check why trailing stops aren't being executed
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure stdout encoding for Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

ticket = 172588621

print("=" * 80)
print(f"TRAILING STOP EXECUTION CHECK - Ticket {ticket}")
print("=" * 80)
print()

# Check 1: Current MT5 Position
print("1. Checking Current MT5 Position...")
try:
    import MetaTrader5 as mt5
    
    if not mt5.initialize():
        print("   ❌ MT5 not initialized")
    else:
        positions = mt5.positions_get(ticket=ticket)
        if positions and len(positions) > 0:
            pos = positions[0]
            print(f"   ✅ Position found")
            print(f"   📊 Symbol: {pos.symbol}")
            print(f"   📊 Entry: {pos.price_open}")
            print(f"   📊 Current SL: {pos.sl}")
            print(f"   📊 Current TP: {pos.tp}")
            print(f"   📊 Current Price: {pos.price_current}")
            print(f"   📊 Volume: {pos.volume}")
            print(f"   📊 Type: {'BUY' if pos.type == 0 else 'SELL'}")
            
            current_sl = pos.sl
            current_price = pos.price_current
        else:
            print(f"   ❌ Position not found")
            current_sl = None
            current_price = None
except Exception as e:
    print(f"   ❌ Error: {e}")
    current_sl = None
    current_price = None

print()

# Check 2: Universal Manager State
print("2. Checking Universal Manager State...")
try:
    from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
    
    with manager.active_trades_lock:
        trade_state = manager.active_trades.get(ticket)
    
    if trade_state:
        print(f"   ✅ Trade found in Universal Manager")
        print(f"   📊 Breakeven triggered: {trade_state.breakeven_triggered}")
        print(f"   📊 Trailing enabled: {trade_state.resolved_trailing_rules.get('trailing_enabled', True)}")
        print(f"   📊 Last SL modification: {trade_state.last_sl_modification_time}")
        print(f"   📊 Last trailing SL: {trade_state.last_trailing_sl}")
        
        # Check if trailing should be active
        if trade_state.breakeven_triggered:
            trailing_enabled = trade_state.resolved_trailing_rules.get('trailing_enabled', True)
            if trailing_enabled:
                print(f"   ✅ Trailing should be ACTIVE")
            else:
                print(f"   ⚠️  Trailing is DISABLED for this strategy")
        else:
            print(f"   ⏳ Breakeven not triggered yet (but you said it was?)")
        
        # Calculate what trailing SL should be
        rules = trade_state.resolved_trailing_rules
        atr_timeframe = rules.get('trailing_timeframe', 'M15')
        current_atr = manager._get_current_atr("BTCUSDc", atr_timeframe)
        
        if current_atr and current_price:
            atr_multiplier = rules.get('atr_multiplier', 1.7)
            trailing_distance = current_atr * atr_multiplier
            
            # For SELL: SL = price + trailing_distance
            ideal_trailing_sl = current_price + trailing_distance
            
            print(f"\n   📊 Trailing Calculation:")
            print(f"      Current Price: {current_price:.2f}")
            print(f"      ATR: {current_atr:.2f}")
            print(f"      Multiplier: {atr_multiplier}")
            print(f"      Trailing Distance: {trailing_distance:.2f}")
            print(f"      Ideal Trailing SL: {ideal_trailing_sl:.2f}")
            print(f"      Current SL: {current_sl:.2f}")
            
            if current_sl:
                sl_diff = abs(ideal_trailing_sl - current_sl)
                print(f"      Difference: {sl_diff:.2f}")
                
                # Check minimum change
                min_change_r = rules.get('min_sl_change_r', 0.1)
                one_r = abs(trade_state.entry_price - trade_state.initial_sl)
                min_change_price = one_r * min_change_r
                print(f"      Min change needed: {min_change_price:.2f}")
                
                if sl_diff >= min_change_price:
                    print(f"      ✅ Change is significant enough")
                else:
                    print(f"      ⏳ Change too small ({sl_diff:.2f} < {min_change_price:.2f})")
    else:
        print(f"   ❌ Trade NOT found in Universal Manager")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 3: MT5 Modification Method
print("3. Checking MT5 Modification Method...")
try:
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    
    # Check if modify_position_sl_tp exists
    if hasattr(mt5_service, 'modify_position_sl_tp'):
        print(f"   ✅ MT5Service has modify_position_sl_tp method")
        
        # Check method signature
        import inspect
        sig = inspect.signature(mt5_service.modify_position_sl_tp)
        print(f"   📊 Method signature: {sig}")
    else:
        print(f"   ❌ MT5Service does NOT have modify_position_sl_tp method")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check 4: Test MT5 Modification
print("4. Testing MT5 Modification Capability...")
try:
    import MetaTrader5 as mt5
    
    if mt5.initialize():
        positions = mt5.positions_get(ticket=ticket)
        if positions and len(positions) > 0:
            pos = positions[0]
            
            # Test if we can modify (dry run - don't actually modify)
            print(f"   ✅ Can access position")
            print(f"   📊 Current SL: {pos.sl}")
            print(f"   📊 Current TP: {pos.tp}")
            
            # Check MT5 connection
            account_info = mt5.account_info()
            if account_info:
                print(f"   ✅ MT5 connected (Account: {account_info.login})")
            else:
                print(f"   ❌ MT5 account info not available")
        else:
            print(f"   ❌ Position not found")
    else:
        print(f"   ❌ MT5 not initialized")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check 5: Monitor All Trades Execution
print("5. Checking if monitor_all_trades is being called...")
try:
    # Check if there are any logs or evidence of monitoring
    print(f"   💡 Universal Manager should call monitor_all_trades() every 30 seconds")
    print(f"   💡 Check chatgpt_bot.py logs for:")
    print(f"      - 'Universal Dynamic SL/TP Manager monitoring scheduled'")
    print(f"      - Any errors in 'Error in Universal SL/TP monitoring'")
    print(f"      - SL modification logs")
    
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check 6: Should Modify Check
print("6. Checking _should_modify_sl Logic...")
try:
    from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
    
    with manager.active_trades_lock:
        trade_state = manager.active_trades.get(ticket)
    
    if trade_state and current_price and current_sl:
        rules = trade_state.resolved_trailing_rules
        
        # Calculate ideal trailing SL
        atr_timeframe = rules.get('trailing_timeframe', 'M15')
        current_atr = manager._get_current_atr("BTCUSDc", atr_timeframe)
        
        if current_atr:
            atr_multiplier = rules.get('atr_multiplier', 1.7)
            trailing_distance = current_atr * atr_multiplier
            
            # For SELL: SL = price + trailing_distance
            ideal_trailing_sl = current_price + trailing_distance
            
            # Test _should_modify_sl
            should_modify = manager._should_modify_sl(trade_state, ideal_trailing_sl, rules)
            
            print(f"   📊 Ideal Trailing SL: {ideal_trailing_sl:.2f}")
            print(f"   📊 Current SL: {current_sl:.2f}")
            print(f"   📊 Should Modify: {should_modify}")
            
            if not should_modify:
                print(f"   ⚠️  _should_modify_sl returned False")
                print(f"   💡 Reasons could be:")
                print(f"      - Change too small (min_sl_change_r threshold)")
                print(f"      - Cooldown period not expired")
                print(f"      - Not an improvement (for SELL, SL must move down)")
    else:
        print(f"   ⚠️  Cannot test - missing data")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()
print("💡 HOW TRAILING STOPS WORK:")
print()
print("1. Universal Manager calls monitor_all_trades() every 30 seconds")
print("2. For each trade, calls monitor_trade(ticket)")
print("3. Calculates ideal trailing SL based on:")
print("   - Current price")
print("   - ATR × multiplier")
print("   - Strategy rules")
print("4. Checks _should_modify_sl() to verify:")
print("   - Change is significant enough (min_sl_change_r)")
print("   - Cooldown period expired")
print("   - Change is an improvement")
print("5. Calls _modify_position_sl() which:")
print("   - Uses MT5Service.modify_position_sl_tp() OR")
print("   - Falls back to direct MT5 order_send()")
print("6. MT5 modifies the position SL")
print()
print("🔍 CHECK LOGS FOR:")
print("   - 'Universal Dynamic SL/TP Manager monitoring scheduled'")
print("   - 'SL modified' or 'SL X.XX→Y.YY' messages")
print("   - Any errors in monitoring")
print()

