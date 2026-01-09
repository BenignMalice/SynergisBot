"""
Calculate next SL change price for trade 172588621
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
# Current SL: 86645.44 (breakeven)
# Current Price: 86491.20
# Direction: SELL
# TP: 85300.00

print("=" * 80)
print(f"NEXT SL CHANGE CALCULATION - Ticket {ticket}")
print("=" * 80)
print()

print("📊 Current Trade Status:")
print(f"   Entry Price: 86618.90")
print(f"   Current SL: 86645.44 (breakeven)")
print(f"   Current Price: 86491.20")
print(f"   Direction: SELL")
print(f"   TP: 85300.00")
print(f"   Profit: ~1.28R (in profit)")
print()

# Check 1: Universal Manager Configuration
print("1. Checking Universal Manager Configuration...")
try:
    from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
    
    with manager.active_trades_lock:
        trade_state = manager.active_trades.get(ticket)
    
    if trade_state:
        print(f"   ✅ Trade found in Universal Manager")
        print(f"   📊 Strategy: {trade_state.strategy_type.value if trade_state.strategy_type else 'None'}")
        
        rules = trade_state.resolved_trailing_rules
        print(f"   📊 Trailing method: {rules.get('trailing_method', 'atr_basic')}")
        print(f"   📊 ATR multiplier: {rules.get('atr_multiplier', 2.0)}")
        print(f"   📊 ATR timeframe: {rules.get('trailing_timeframe', 'M15')}")
        print(f"   📊 Min SL change (R): {rules.get('min_sl_change_r', 0.1)}")
        print(f"   📊 Cooldown: {rules.get('sl_modification_cooldown_seconds', 30)} seconds")
        
        # Get current ATR
        atr_timeframe = rules.get('trailing_timeframe', 'M15')
        current_atr = manager._get_current_atr("BTCUSDc", atr_timeframe)
        
        if current_atr:
            print(f"   📊 Current ATR ({atr_timeframe}): {current_atr:.2f}")
            
            # Calculate trailing distance
            atr_multiplier = rules.get('atr_multiplier', 2.0)
            trailing_distance = current_atr * atr_multiplier
            print(f"   📊 Trailing distance: {trailing_distance:.2f} (ATR × {atr_multiplier})")
            
            # For SELL: SL should be above current price
            # Trailing SL = current_price + trailing_distance
            current_price = 86491.20
            ideal_trailing_sl = current_price + trailing_distance
            print(f"   📊 Ideal trailing SL: {ideal_trailing_sl:.2f}")
            
            # Current SL is 86645.44
            current_sl = 86645.44
            print(f"   📊 Current SL: {current_sl:.2f}")
            
            # Check if SL needs to move
            if ideal_trailing_sl < current_sl:
                print(f"   ✅ SL should move DOWN to {ideal_trailing_sl:.2f}")
                
                # Calculate minimum change threshold
                min_change_r = rules.get('min_sl_change_r', 0.1)
                one_r = abs(trade_state.entry_price - trade_state.initial_sl)
                min_change_price = one_r * min_change_r
                print(f"   📊 Minimum change: {min_change_price:.2f} ({min_change_r}R)")
                
                sl_change = abs(current_sl - ideal_trailing_sl)
                print(f"   📊 SL change needed: {sl_change:.2f}")
                
                if sl_change >= min_change_price:
                    print(f"   ✅ Change is significant enough - SL will move")
                else:
                    print(f"   ⏳ Change too small - waiting for larger move")
            else:
                print(f"   ⏳ SL is already optimal (or price hasn't moved enough)")
            
            # Calculate what price would trigger next change
            # For SELL: Price needs to move DOWN for SL to trail down
            # Next SL change when: new_trailing_sl < current_sl - min_change
            min_change_r = rules.get('min_sl_change_r', 0.1)
            one_r = abs(trade_state.entry_price - trade_state.initial_sl)
            min_change_price = one_r * min_change_r
            
            # Calculate trigger price
            # For SELL trailing: SL = price + trailing_distance
            # We want: (price + trailing_distance) < (current_sl - min_change)
            # So: price < (current_sl - min_change - trailing_distance)
            trigger_price = current_sl - min_change_price - trailing_distance
            print(f"\n   🎯 NEXT SL CHANGE TRIGGER:")
            print(f"      Price needs to move to: {trigger_price:.2f} or lower")
            print(f"      (Current price: {current_price:.2f})")
            print(f"      (Price needs to drop: {current_price - trigger_price:.2f} points)")
            
        else:
            print(f"   ⚠️  Could not get ATR")
    else:
        print(f"   ⚠️  Trade NOT found in Universal Manager")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 2: Intelligent Exit Manager (if also managing)
print("2. Checking Intelligent Exit Manager...")
try:
    from infra.intelligent_exit_manager import IntelligentExitManager
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    manager = IntelligentExitManager(mt5_service=mt5_service)
    
    rule = manager.get_rule(ticket)
    if rule:
        print(f"   ✅ Rule found in Intelligent Exit Manager")
        print(f"   📊 Trailing active: {rule.trailing_active}")
        print(f"   📊 Breakeven triggered: {rule.breakeven_triggered}")
        
        if rule.trailing_active:
            print(f"   💡 Intelligent Exit Manager also has trailing enabled")
            print(f"   ⚠️  But Universal Manager should be managing (check coordination)")
    else:
        print(f"   ⚠️  Rule NOT found in Intelligent Exit Manager")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check 3: Calculate exact trigger price
print("3. Detailed Calculation...")
try:
    from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
    
    with manager.active_trades_lock:
        trade_state = manager.active_trades.get(ticket)
    
    if trade_state:
        rules = trade_state.resolved_trailing_rules
        
        # Get ATR
        atr_timeframe = rules.get('trailing_timeframe', 'M15')
        current_atr = manager._get_current_atr("BTCUSDc", atr_timeframe)
        
        if current_atr:
            atr_multiplier = rules.get('atr_multiplier', 2.0)
            trailing_distance = current_atr * atr_multiplier
            
            # Current values
            entry_price = 86618.90
            initial_sl = trade_state.initial_sl
            current_sl = 86645.44
            current_price = 86491.20
            
            # Calculate one R
            one_r = abs(entry_price - initial_sl)
            print(f"   📊 One R: {one_r:.2f}")
            
            # Minimum change threshold
            min_change_r = rules.get('min_sl_change_r', 0.1)
            min_change_price = one_r * min_change_r
            print(f"   📊 Minimum change: {min_change_price:.2f} ({min_change_r}R)")
            
            # For SELL: Trailing SL = current_price + trailing_distance
            # We want SL to move down, so price needs to move down
            # New SL = new_price + trailing_distance
            # We want: new_sl < current_sl - min_change
            # So: new_price + trailing_distance < current_sl - min_change
            # Therefore: new_price < current_sl - min_change - trailing_distance
            
            trigger_price = current_sl - min_change_price - trailing_distance
            
            print(f"\n   🎯 CALCULATION RESULT:")
            print(f"      Current Price: {current_price:.2f}")
            print(f"      Current SL: {current_sl:.2f}")
            print(f"      Trailing Distance: {trailing_distance:.2f}")
            print(f"      Minimum Change: {min_change_price:.2f}")
            print(f"      Trigger Price: {trigger_price:.2f}")
            print(f"\n   ✅ NEXT SL CHANGE:")
            print(f"      When price reaches: {trigger_price:.2f} or lower")
            print(f"      New SL will be: {trigger_price + trailing_distance:.2f}")
            print(f"      Price needs to drop: {current_price - trigger_price:.2f} points")
            
            # Also check cooldown
            if trade_state.last_sl_modification_time:
                from datetime import datetime, timedelta
                cooldown = rules.get('sl_modification_cooldown_seconds', 30)
                elapsed = (datetime.now() - trade_state.last_sl_modification_time).total_seconds()
                remaining = max(0, cooldown - elapsed)
                print(f"\n   ⏱️  COOLDOWN:")
                print(f"      Last modification: {trade_state.last_sl_modification_time}")
                print(f"      Cooldown: {cooldown} seconds")
                print(f"      Remaining: {remaining:.1f} seconds")
                if remaining > 0:
                    print(f"      ⏳ Must wait {remaining:.1f} seconds before next change")
            else:
                print(f"\n   ⏱️  COOLDOWN: No previous modification (ready to change)")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()
print("💡 The next SL change will happen when:")
print("   1. Price moves to the trigger price (calculated above)")
print("   2. Cooldown period has passed (30 seconds)")
print("   3. Change is significant enough (minimum R threshold)")
print()

