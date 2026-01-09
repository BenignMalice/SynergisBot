"""
Calculate next SL change for SELL trade - Correct calculation
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

# From the image:
# Entry: 86618.90
# Current SL: 86645.44 (breakeven - above entry for SELL)
# Current Price: 86491.20 (below entry = in profit)
# Direction: SELL
# TP: 85300.00

print("=" * 80)
print(f"NEXT SL CHANGE CALCULATION - SELL Trade {ticket}")
print("=" * 80)
print()

print("📊 Current Trade Status:")
print(f"   Entry Price: 86618.90")
print(f"   Current SL: 86645.44 (breakeven)")
print(f"   Current Price: 86491.20")
print(f"   Direction: SELL")
print(f"   Profit: ~1.28R")
print()

# Get trade state
try:
    from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
    
    with manager.active_trades_lock:
        trade_state = manager.active_trades.get(ticket)
    
    if not trade_state:
        print("❌ Trade not found in Universal Manager")
        exit(1)
    
    rules = trade_state.resolved_trailing_rules
    
    # Get ATR
    atr_timeframe = rules.get('trailing_timeframe', 'M15')
    current_atr = manager._get_current_atr("BTCUSDc", atr_timeframe)
    
    if not current_atr:
        print("❌ Could not get ATR")
        exit(1)
    
    atr_multiplier = rules.get('atr_multiplier', 2.0)
    trailing_distance = current_atr * atr_multiplier
    
    print(f"📊 Configuration:")
    print(f"   ATR ({atr_timeframe}): {current_atr:.2f}")
    print(f"   ATR Multiplier: {atr_multiplier}")
    print(f"   Trailing Distance: {trailing_distance:.2f}")
    print(f"   Min SL Change (R): {rules.get('min_sl_change_r', 0.1)}")
    print(f"   Cooldown: {rules.get('sl_modification_cooldown_seconds', 60)} seconds")
    print()
    
    # Current values
    entry_price = 86618.90
    initial_sl = trade_state.initial_sl
    current_sl = 86645.44
    current_price = 86491.20
    
    # Calculate one R
    one_r = abs(entry_price - initial_sl)
    min_change_r = rules.get('min_sl_change_r', 0.1)
    min_change_price = one_r * min_change_r
    
    print(f"📊 Risk Calculation:")
    print(f"   One R: {one_r:.2f}")
    print(f"   Minimum change: {min_change_price:.2f} ({min_change_r}R)")
    print()
    
    # For SELL trade trailing:
    # SL should be ABOVE current price
    # As price moves DOWN (in profit), SL should move DOWN
    # Trailing SL = current_price + trailing_distance
    
    ideal_trailing_sl = current_price + trailing_distance
    print(f"📊 Trailing Calculation (SELL):")
    print(f"   Current Price: {current_price:.2f}")
    print(f"   Trailing Distance: {trailing_distance:.2f}")
    print(f"   Ideal Trailing SL: {ideal_trailing_sl:.2f} (price + distance)")
    print(f"   Current SL: {current_sl:.2f}")
    print()
    
    # Check if SL should move
    # For SELL: Lower SL is better (closer to price)
    # We want: ideal_trailing_sl < current_sl (move SL down)
    sl_change_needed = current_sl - ideal_trailing_sl
    
    print(f"📊 SL Change Analysis:")
    if sl_change_needed > 0:
        print(f"   ✅ SL should move DOWN by {sl_change_needed:.2f}")
        if sl_change_needed >= min_change_price:
            print(f"   ✅ Change is significant enough ({sl_change_needed:.2f} >= {min_change_price:.2f})")
            print(f"   ✅ SL will move to: {ideal_trailing_sl:.2f}")
        else:
            print(f"   ⏳ Change too small ({sl_change_needed:.2f} < {min_change_price:.2f})")
            print(f"   ⏳ Waiting for larger move")
    else:
        print(f"   ⏳ SL is already optimal or price hasn't moved enough")
        print(f"   ⏳ Current SL is at or below ideal trailing SL")
    
    print()
    
    # Calculate trigger price for NEXT change
    # For SELL: As price drops, trailing SL should drop
    # Next change when: new_price + trailing_distance < current_sl - min_change
    # So: new_price < current_sl - min_change - trailing_distance
    
    trigger_price = current_sl - min_change_price - trailing_distance
    new_sl_at_trigger = trigger_price + trailing_distance
    
    print(f"🎯 NEXT SL CHANGE TRIGGER:")
    print(f"   When price reaches: {trigger_price:.2f} or lower")
    print(f"   New SL will be: {new_sl_at_trigger:.2f}")
    print(f"   Current price: {current_price:.2f}")
    print(f"   Price needs to drop: {current_price - trigger_price:.2f} points")
    print()
    
    # Check cooldown
    if trade_state.last_sl_modification_time:
        from datetime import datetime
        cooldown = rules.get('sl_modification_cooldown_seconds', 60)
        elapsed = (datetime.now() - trade_state.last_sl_modification_time).total_seconds()
        remaining = max(0, cooldown - elapsed)
        
        print(f"⏱️  COOLDOWN:")
        print(f"   Last modification: {trade_state.last_sl_modification_time}")
        print(f"   Cooldown: {cooldown} seconds")
        print(f"   Elapsed: {elapsed:.1f} seconds")
        if remaining > 0:
            print(f"   ⏳ Remaining: {remaining:.1f} seconds")
            print(f"   ⏳ Next change possible after cooldown expires")
        else:
            print(f"   ✅ Cooldown expired - ready for next change")
    else:
        print(f"⏱️  COOLDOWN: No previous modification (ready to change)")
    
    print()
    print("=" * 80)
    print("ANSWER")
    print("=" * 80)
    print()
    print(f"🎯 NEXT SL CHANGE will be made when:")
    print(f"   Price reaches: {trigger_price:.2f} or lower")
    print(f"   New SL: {new_sl_at_trigger:.2f}")
    print(f"   Price drop needed: {current_price - trigger_price:.2f} points")
    print()
    print(f"📊 Current Status:")
    print(f"   Current Price: {current_price:.2f}")
    print(f"   Current SL: {current_sl:.2f}")
    print(f"   Ideal Trailing SL: {ideal_trailing_sl:.2f}")
    if sl_change_needed > 0 and sl_change_needed >= min_change_price:
        print(f"   ✅ SL should move NOW (if cooldown expired)")
    else:
        print(f"   ⏳ Waiting for price to move to trigger level")
    print()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

