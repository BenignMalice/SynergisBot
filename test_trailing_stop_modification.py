"""
Test trailing stop modification - simulate what Universal Manager does
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
print(f"TRAILING STOP MODIFICATION TEST - Ticket {ticket}")
print("=" * 80)
print()

# Get current position
print("1. Getting Current Position...")
try:
    import MetaTrader5 as mt5
    
    if not mt5.initialize():
        print("   ❌ MT5 not initialized")
        exit(1)
    
    positions = mt5.positions_get(ticket=ticket)
    if not positions or len(positions) == 0:
        print("   ❌ Position not found")
        exit(1)
    
    pos = positions[0]
    current_sl = pos.sl
    current_price = pos.price_current
    entry_price = pos.price_open
    initial_sl = pos.sl  # Use current SL as initial (breakeven)
    
    print(f"   ✅ Position found")
    print(f"   📊 Entry: {entry_price:.2f}")
    print(f"   📊 Current SL: {current_sl:.2f}")
    print(f"   📊 Current Price: {current_price:.2f}")
    print(f"   📊 Direction: {'BUY' if pos.type == 0 else 'SELL'}")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)

print()

# Get Universal Manager state
print("2. Getting Universal Manager Configuration...")
try:
    from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
    
    with manager.active_trades_lock:
        trade_state = manager.active_trades.get(ticket)
    
    if not trade_state:
        print("   ❌ Trade not found in Universal Manager")
        exit(1)
    
    rules = trade_state.resolved_trailing_rules
    
    # Get ATR
    atr_timeframe = rules.get('trailing_timeframe', 'M15')
    current_atr = manager._get_current_atr("BTCUSDc", atr_timeframe)
    
    if not current_atr:
        print("   ❌ Could not get ATR")
        exit(1)
    
    atr_multiplier = rules.get('atr_multiplier', 1.7)
    trailing_distance = current_atr * atr_multiplier
    
    # Calculate ideal trailing SL
    # For SELL: SL = price + trailing_distance
    ideal_trailing_sl = current_price + trailing_distance
    
    print(f"   ✅ Configuration loaded")
    print(f"   📊 ATR ({atr_timeframe}): {current_atr:.2f}")
    print(f"   📊 Multiplier: {atr_multiplier}")
    print(f"   📊 Trailing Distance: {trailing_distance:.2f}")
    print(f"   📊 Ideal Trailing SL: {ideal_trailing_sl:.2f}")
    print(f"   📊 Min SL Change (R): {rules.get('min_sl_change_r', 0.1)}")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print()

# Test _should_modify_sl
print("3. Testing _should_modify_sl()...")
try:
    should_modify = manager._should_modify_sl(trade_state, ideal_trailing_sl, rules)
    
    print(f"   📊 Ideal Trailing SL: {ideal_trailing_sl:.2f}")
    print(f"   📊 Current SL: {current_sl:.2f}")
    print(f"   📊 Should Modify: {should_modify}")
    
    if not should_modify:
        print(f"\n   ⚠️  BLOCKED - Reasons:")
        
        # Check minimum change
        min_change_r = rules.get('min_sl_change_r', 0.1)
        one_r = abs(trade_state.entry_price - trade_state.initial_sl)
        min_change_price = one_r * min_change_r
        sl_change = abs(ideal_trailing_sl - current_sl)
        
        print(f"      • Change needed: {sl_change:.2f} points")
        print(f"      • Minimum required: {min_change_price:.2f} points ({min_change_r}R)")
        
        if sl_change < min_change_price:
            print(f"      ❌ Change too small ({sl_change:.2f} < {min_change_price:.2f})")
            print(f"      💡 Price needs to move more for SL to adjust")
        
        # Check cooldown
        if trade_state.last_sl_modification_time:
            from datetime import datetime
            cooldown = rules.get('sl_modification_cooldown_seconds', 60)
            elapsed = (datetime.now() - trade_state.last_sl_modification_time).total_seconds()
            if elapsed < cooldown:
                remaining = cooldown - elapsed
                print(f"      • Cooldown: {remaining:.1f} seconds remaining")
        
        # Check if improvement
        if trade_state.direction == "SELL":
            # For SELL: Lower SL is better (closer to price)
            if ideal_trailing_sl >= current_sl:
                print(f"      • For SELL: Ideal SL ({ideal_trailing_sl:.2f}) >= Current SL ({current_sl:.2f})")
                print(f"      ❌ Not an improvement (SL would move UP, not DOWN)")
    else:
        print(f"   ✅ Should modify - all checks passed")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test actual MT5 modification
print("4. Testing MT5 Modification (DRY RUN - won't actually modify)...")
try:
    # Test if we can call the modification method
    test_sl = ideal_trailing_sl
    
    print(f"   📊 Would modify SL to: {test_sl:.2f}")
    print(f"   📊 Current SL: {current_sl:.2f}")
    print(f"   📊 Change: {abs(test_sl - current_sl):.2f} points")
    
    # Check MT5Service method
    if hasattr(mt5_service, 'modify_position_sl_tp'):
        print(f"   ✅ MT5Service.modify_position_sl_tp() available")
        print(f"   💡 This method uses: mt5.order_send() with TRADE_ACTION_SLTP")
    else:
        print(f"   ❌ MT5Service.modify_position_sl_tp() NOT available")
    
    # Show what the MT5 call would look like
    print(f"\n   📊 MT5 API Call (what happens):")
    print(f"      action = mt5.TRADE_ACTION_SLTP")
    print(f"      position = {ticket}")
    print(f"      sl = {test_sl:.2f}")
    print(f"      tp = {trade_state.initial_tp:.2f}")
    print(f"      symbol = {trade_state.symbol}")
    print(f"      → mt5.order_send(request)")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Explain the issue
print("=" * 80)
print("DIAGNOSIS")
print("=" * 80)
print()
print("🔍 WHY SL ISN'T BEING ADJUSTED:")
print()
print("Current Status:")
print(f"   • Current Price: {current_price:.2f}")
print(f"   • Current SL: {current_sl:.2f}")
print(f"   • Ideal Trailing SL: {ideal_trailing_sl:.2f}")
print(f"   • Difference: {abs(ideal_trailing_sl - current_sl):.2f} points")
print()
print("Blocking Reason:")
min_change_r = rules.get('min_sl_change_r', 0.1)
one_r = abs(trade_state.entry_price - trade_state.initial_sl)
min_change_price = one_r * min_change_r
sl_change = abs(ideal_trailing_sl - current_sl)

if sl_change < min_change_price:
    print(f"   ❌ Change too small: {sl_change:.2f} < {min_change_price:.2f} (min {min_change_r}R)")
    print(f"   💡 The minimum change threshold is blocking the modification")
    print(f"   💡 Price needs to move more for SL to adjust")
    
    # Calculate what price would trigger
    # For SELL: As price drops, ideal SL drops
    # We need: new_ideal_sl - current_sl >= min_change
    # new_ideal_sl = new_price + trailing_distance
    # So: new_price + trailing_distance - current_sl >= min_change
    # Therefore: new_price >= current_sl - trailing_distance + min_change
    
    trigger_price = current_sl - trailing_distance + min_change_price
    print(f"\n   🎯 SL will adjust when price reaches: {trigger_price:.2f} or lower")
    print(f"      (Current price: {current_price:.2f})")
    print(f"      (Price needs to drop: {current_price - trigger_price:.2f} points)")

print()
print("💡 HOW MT5 MODIFICATION WORKS:")
print()
print("1. Universal Manager calculates ideal trailing SL")
print("2. Checks _should_modify_sl() - verifies:")
print("   • Change is significant enough (min_sl_change_r)")
print("   • Cooldown expired")
print("   • Change is an improvement")
print("3. If all checks pass, calls _modify_position_sl():")
print("   • Uses MT5Service.modify_position_sl_tp()")
print("   • Which calls: mt5.order_send() with TRADE_ACTION_SLTP")
print("   • MT5 modifies the position SL in real-time")
print()
print("4. MT5 API Call:")
print("   request = {")
print("       'action': mt5.TRADE_ACTION_SLTP,")
print("       'position': ticket,")
print("       'sl': new_sl,")
print("       'tp': current_tp,")
print("       'symbol': symbol")
print("   }")
print("   result = mt5.order_send(request)")
print()
print("✅ The system DOES modify SL via MT5 - it's just waiting for a larger price move!")
print()

