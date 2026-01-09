"""
Diagnose why trailing stops didn't work and caused a loss
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
print(f"TRAILING STOP FAILURE DIAGNOSIS - Ticket {ticket}")
print("=" * 80)
print()

# Get current position
print("1. Current Position Status...")
try:
    import MetaTrader5 as mt5
    
    if not mt5.initialize():
        print("   ❌ MT5 not initialized")
        exit(1)
    
    positions = mt5.positions_get(ticket=ticket)
    if not positions or len(positions) == 0:
        print("   ⚠️  Position closed (likely hit SL)")
    else:
        pos = positions[0]
        print(f"   ✅ Position still open")
        print(f"   📊 Entry: {pos.price_open:.2f}")
        print(f"   📊 Current SL: {pos.sl:.2f}")
        print(f"   📊 Current Price: {pos.price_current:.2f}")
        print(f"   📊 Profit: ${pos.profit:.2f}")
        
        if pos.profit < 0:
            print(f"   ❌ Currently at a LOSS")
        else:
            print(f"   ✅ Currently in profit")
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Analyze what should have happened
print("2. What Should Have Happened...")
print()
print("   For SELL trade in profit:")
print("   • Price moves DOWN = more profit")
print("   • SL should trail DOWN (tighten) as price moves down")
print("   • SL should NEVER move UP (widen)")
print()
print("   The issue:")
print("   • Breakeven SL: 86645.44 (above entry)")
print("   • When price was 86528.20, ideal trailing SL = 86784.05")
print("   • This would WIDEN the stop (86784.05 > 86645.44)")
print("   • System correctly blocked this (don't widen)")
print()
print("   BUT:")
print("   • As price continued DOWN, trailing SL should have moved DOWN")
print("   • If price moved to 86400, trailing SL should be ~86655")
print("   • This would TIGHTEN the stop (86655 < 86645.44)")
print("   • System should have allowed this")
print()

# Check the logic
print("3. Checking Trailing Logic...")
try:
    from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
    
    with manager.active_trades_lock:
        trade_state = manager.active_trades.get(ticket)
    
    if trade_state:
        print(f"   ✅ Trade found in Universal Manager")
        
        # Simulate what should happen at different price levels
        rules = trade_state.resolved_trailing_rules
        atr_timeframe = rules.get('trailing_timeframe', 'M15')
        current_atr = manager._get_current_atr("BTCUSDc", atr_timeframe)
        
        if current_atr:
            atr_multiplier = rules.get('atr_multiplier', 1.7)
            trailing_distance = current_atr * atr_multiplier
            
            print(f"\n   📊 Trailing Configuration:")
            print(f"      ATR: {current_atr:.2f}")
            print(f"      Multiplier: {atr_multiplier}")
            print(f"      Trailing Distance: {trailing_distance:.2f}")
            print()
            
            # Test different price scenarios
            test_prices = [86528.20, 86400.00, 86300.00, 86200.00]
            current_sl = 86645.44  # Breakeven SL
            
            print(f"   📊 Trailing SL at Different Price Levels:")
            print(f"      Current SL (breakeven): {current_sl:.2f}")
            print()
            
            for test_price in test_prices:
                ideal_sl = test_price + trailing_distance
                would_tighten = ideal_sl < current_sl
                change = abs(ideal_sl - current_sl)
                
                print(f"      Price: {test_price:.2f}")
                print(f"         Ideal Trailing SL: {ideal_sl:.2f}")
                print(f"         Would tighten: {would_tighten} (ideal < current)")
                print(f"         Change: {change:.2f} points")
                
                if would_tighten:
                    print(f"         ✅ SHOULD MODIFY (tightens stop)")
                else:
                    print(f"         ❌ BLOCKED (would widen stop)")
                print()
    else:
        print(f"   ⚠️  Trade not found (may have been closed)")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# The real issue
print("=" * 80)
print("ROOT CAUSE")
print("=" * 80)
print()
print("🔍 The Problem:")
print()
print("   For a SELL trade:")
print("   • Entry: 86618.90")
print("   • Breakeven SL: 86645.44 (26.54 points above entry)")
print("   • Trailing distance: ~256 points")
print()
print("   When price was 86528.20:")
print("   • Ideal trailing SL = 86528.20 + 256 = 86784.05")
print("   • This is HIGHER than breakeven (86784.05 > 86645.44)")
print("   • System correctly blocked this (don't widen)")
print()
print("   BUT:")
print("   • The breakeven SL (86645.44) is VERY TIGHT")
print("   • It's only 26.54 points above entry")
print("   • For a trailing stop with 256 points distance,")
print("     price needs to be at 86645.44 - 256 = 86389.44")
print("   • Before trailing can activate")
print()
print("   💡 The issue: Breakeven is too tight for trailing to activate")
print("   💡 Solution: Trailing should start from breakeven, not wait")
print("                for price to move far enough")
print()

