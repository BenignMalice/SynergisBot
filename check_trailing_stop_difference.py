"""
Check why trailing stops are working for one trade but not the other
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure stdout encoding for Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

print("=" * 80)
print("TRAILING STOP DIFFERENCE ANALYSIS")
print("=" * 80)
print()

# Check both trades
tickets = [172590811, 172592863]

try:
    from infra.intelligent_exit_manager import IntelligentExitManager
    from infra.mt5_service import MT5Service
    import MetaTrader5 as mt5
    
    if not mt5.initialize():
        print("❌ MT5 not initialized")
        sys.exit(1)
    
    mt5_service = MT5Service()
    manager = IntelligentExitManager(mt5_service=mt5_service)
    
    # Get positions from MT5
    positions = mt5.positions_get()
    position_dict = {p.ticket: p for p in positions} if positions else {}
    
    # Get rules from Intelligent Exit Manager
    rules = manager.get_all_rules()
    rule_dict = {r.ticket: r for r in rules} if rules else {}
    
    print("Comparing both trades:")
    print()
    
    for ticket in tickets:
        print(f"{'='*80}")
        print(f"TRADE {ticket}")
        print(f"{'='*80}")
        
        # Get position
        position = position_dict.get(ticket)
        if position:
            print(f"✅ Position found in MT5")
            print(f"   Symbol: {position.symbol}")
            print(f"   Type: {position.type}")
            print(f"   Volume: {position.volume}")
            print(f"   Price Open: {position.price_open}")
            print(f"   Price Current: {position.price_current}")
            print(f"   SL: {position.sl}")
            print(f"   TP: {position.tp}")
            print(f"   Profit: {position.profit}")
        else:
            print(f"❌ Position NOT found in MT5")
        
        print()
        
        # Get rule
        rule = rule_dict.get(ticket)
        if rule:
            print(f"✅ Intelligent Exit rule found")
            print(f"   Symbol: {rule.symbol}")
            print(f"   Direction: {rule.direction}")
            print(f"   Entry Price: {rule.entry_price}")
            print(f"   Initial SL: {rule.initial_sl}")
            print(f"   Current SL: {position.sl if position else 'N/A'}")
            print(f"   Breakeven Triggered: {rule.breakeven_triggered}")
            print(f"   Partial Triggered: {rule.partial_triggered}")
            print(f"   Trailing Active: {rule.trailing_active}")
            print(f"   Trailing Multiplier: {getattr(rule, 'trailing_multiplier', 'N/A')}")
            
            # Calculate current profit
            if position:
                if position.type == 0:  # BUY
                    profit_pct = ((position.price_current - position.price_open) / position.price_open) * 100
                    r_achieved = (position.price_current - rule.entry_price) / abs(rule.entry_price - rule.initial_sl) if rule.initial_sl else 0
                else:  # SELL
                    profit_pct = ((position.price_open - position.price_current) / position.price_open) * 100
                    r_achieved = (rule.entry_price - position.price_current) / abs(rule.entry_price - rule.initial_sl) if rule.initial_sl else 0
                
                print(f"   Current Profit: {profit_pct:.2f}%")
                print(f"   R-Multiple: {r_achieved:.2f}")
            
            # Check if trailing should be active
            print()
            print(f"   Trailing Status:")
            print(f"      • Breakeven Triggered: {rule.breakeven_triggered}")
            print(f"      • Partial Triggered: {rule.partial_triggered}")
            print(f"      • Trailing Active: {rule.trailing_active}")
            
            # Check if SL is at breakeven
            if position:
                if position.type == 0:  # BUY
                    sl_at_be = abs(position.sl - rule.entry_price) < (rule.entry_price * 0.0001)  # 0.01% tolerance
                else:  # SELL
                    sl_at_be = abs(position.sl - rule.entry_price) < (rule.entry_price * 0.0001)
                
                print(f"      • SL at Breakeven: {sl_at_be} (SL: {position.sl}, Entry: {rule.entry_price})")
        else:
            print(f"❌ Intelligent Exit rule NOT found")
        
        print()
    
    # Check for differences
    print(f"{'='*80}")
    print("DIFFERENCE ANALYSIS")
    print(f"{'='*80}")
    print()
    
    rule1 = rule_dict.get(172590811)
    rule2 = rule_dict.get(172592863)
    pos1 = position_dict.get(172590811)
    pos2 = position_dict.get(172592863)
    
    if rule1 and rule2:
        print("Rule Differences:")
        print(f"   Breakeven Triggered: {rule1.breakeven_triggered} vs {rule2.breakeven_triggered}")
        print(f"   Partial Triggered: {rule1.partial_triggered} vs {rule2.partial_triggered}")
        print(f"   Trailing Active: {rule1.trailing_active} vs {rule2.trailing_active}")
        
        if hasattr(rule1, 'trailing_multiplier') and hasattr(rule2, 'trailing_multiplier'):
            print(f"   Trailing Multiplier: {getattr(rule1, 'trailing_multiplier', 'N/A')} vs {getattr(rule2, 'trailing_multiplier', 'N/A')}")
        
        print()
        print("Possible Reasons for Difference:")
        print()
        
        if not rule1.trailing_active and rule2.trailing_active:
            print("   ⚠️  Trade 172590811: Trailing NOT active")
            print("   ✅ Trade 172592863: Trailing IS active")
            print()
            print("   Possible causes:")
            print("   1. Trailing gates failed for 172590811")
            print("   2. Different profit levels")
            print("   3. Different volatility conditions")
            print("   4. Different symbol/position characteristics")
            print("   5. Trailing gates check failed at different times")
        
        # Check if both have breakeven triggered
        if rule1.breakeven_triggered and rule2.breakeven_triggered:
            print("   ✅ Both trades have breakeven triggered")
        else:
            print(f"   ⚠️  Breakeven status differs: {rule1.breakeven_triggered} vs {rule2.breakeven_triggered}")
    
    print()
    print("💡 To investigate further:")
    print("   • Check trailing gates logic in intelligent_exit_manager.py")
    print("   • Check if gates are evaluated differently for each trade")
    print("   • Check logs for 'trailing gates' messages")
    print("   • Verify both trades meet the same conditions")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

