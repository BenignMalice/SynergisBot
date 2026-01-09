"""
Diagnose why trailing stops work for one trade but not the other
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
print("TRAILING STOP DIAGNOSIS")
print("=" * 80)
print()

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
    
    # Get positions
    positions = mt5.positions_get()
    position_dict = {p.ticket: p for p in positions} if positions else {}
    
    # Get rules
    rules = manager.get_all_rules()
    rule_dict = {r.ticket: r for r in rules} if rules else {}
    
    print("Current State Analysis:")
    print()
    
    for ticket in tickets:
        print(f"{'='*80}")
        print(f"TRADE {ticket}")
        print(f"{'='*80}")
        
        position = position_dict.get(ticket)
        rule = rule_dict.get(ticket)
        
        if not position:
            print(f"⚠️  Position not found in MT5 (may be closed)")
        else:
            print(f"✅ Position found")
            print(f"   Symbol: {position.symbol}")
            print(f"   Type: {'BUY' if position.type == 0 else 'SELL'}")
            print(f"   Price Open: {position.price_open}")
            print(f"   Price Current: {position.price_current}")
            print(f"   SL: {position.sl}")
            print(f"   Profit: {position.profit}")
        
        if not rule:
            print(f"❌ Intelligent Exit rule NOT found")
            print(f"   💡 This trade may not be managed by Intelligent Exit Manager")
        else:
            print(f"✅ Intelligent Exit rule found")
            print(f"   Symbol: {rule.symbol}")
            print(f"   Direction: {rule.direction}")
            print(f"   Entry Price: {rule.entry_price}")
            print(f"   Initial SL: {rule.initial_sl}")
            print(f"   Current SL: {position.sl if position else 'N/A'}")
            print()
            print(f"   State Flags:")
            print(f"      • Breakeven Triggered: {rule.breakeven_triggered}")
            print(f"      • Partial Triggered: {rule.partial_triggered}")
            print(f"      • Trailing Enabled: {rule.trailing_enabled}")
            print(f"      • Trailing Active: {rule.trailing_active} ⬅️ KEY FLAG")
            print(f"      • Trailing Multiplier: {getattr(rule, 'trailing_multiplier', 'N/A')}")
            print()
            
            # Calculate current metrics
            if position:
                if position.type == 0:  # BUY
                    profit_pct = ((position.price_current - position.price_open) / position.price_open) * 100
                    r_achieved = (position.price_current - rule.entry_price) / abs(rule.entry_price - rule.initial_sl) if rule.initial_sl and abs(rule.entry_price - rule.initial_sl) > 0 else 0
                else:  # SELL
                    profit_pct = ((position.price_open - position.price_current) / position.price_open) * 100
                    r_achieved = (rule.entry_price - position.price_current) / abs(rule.entry_price - rule.initial_sl) if rule.initial_sl and abs(rule.entry_price - rule.initial_sl) > 0 else 0
                
                print(f"   Current Metrics:")
                print(f"      • Profit: {profit_pct:.2f}%")
                print(f"      • R-Multiple: {r_achieved:.2f}")
                print()
                
                # Check why trailing might not be active
                if not rule.trailing_active:
                    print(f"   ⚠️  TRAILING NOT ACTIVE - Possible Reasons:")
                    print()
                    
                    if not rule.breakeven_triggered:
                        print(f"      ❌ Breakeven not triggered (required for trailing)")
                        print(f"         Current SL: {position.sl}")
                        print(f"         Entry Price: {rule.entry_price}")
                        sl_at_be = abs(position.sl - rule.entry_price) < (rule.entry_price * 0.0001)
                        print(f"         SL at Breakeven: {sl_at_be}")
                    else:
                        print(f"      ✅ Breakeven is triggered")
                    
                    if not rule.trailing_enabled:
                        print(f"      ❌ Trailing not enabled for this rule")
                    else:
                        print(f"      ✅ Trailing is enabled")
                    
                    # Check if gates would pass
                    print()
                    print(f"   Checking Trailing Gates...")
                    try:
                        gate_result = manager._trailing_gates_pass(rule, profit_pct, r_achieved, return_details=True)
                        if isinstance(gate_result, tuple):
                            should_trail, gate_info = gate_result
                            print(f"      • Gates Pass: {should_trail}")
                            if gate_info:
                                print(f"      • Multiplier: {gate_info.get('trailing_multiplier', 'N/A')}")
                                print(f"      • Failed Gates: {gate_info.get('failed_gates', [])}")
                                print(f"      • Gate Status: {gate_info.get('status', 'N/A')}")
                        else:
                            print(f"      • Gates Pass: {gate_result}")
                    except Exception as e:
                        print(f"      ❌ Error checking gates: {e}")
                
                # Check if _trail_stop_atr would return an action
                if rule.trailing_active and rule.breakeven_triggered:
                    print()
                    print(f"   ✅ Trailing is ACTIVE - Checking if _trail_stop_atr would execute...")
                    try:
                        multiplier = getattr(rule, 'trailing_multiplier', 1.5)
                        action = manager._trail_stop_atr(rule, position, position.price_current, trailing_multiplier=multiplier)
                        if action:
                            print(f"      ✅ _trail_stop_atr would return action")
                            print(f"         New SL: {action.get('new_sl')}")
                        else:
                            print(f"      ❌ _trail_stop_atr returned None")
                            print(f"         Possible reasons:")
                            print(f"         • New SL would trail backwards (not allowed)")
                            print(f"         • ATR calculation failed")
                            print(f"         • Bars unavailable")
                    except Exception as e:
                        print(f"      ❌ Error calling _trail_stop_atr: {e}")
        
        print()
    
    # Compare both trades
    print(f"{'='*80}")
    print("COMPARISON")
    print(f"{'='*80}")
    print()
    
    rule1 = rule_dict.get(172590811)
    rule2 = rule_dict.get(172592863)
    pos1 = position_dict.get(172590811)
    pos2 = position_dict.get(172592863)
    
    if rule1 and rule2:
        print("Key Differences:")
        print()
        print(f"Trailing Active:")
        print(f"   Trade 172590811: {rule1.trailing_active}")
        print(f"   Trade 172592863: {rule2.trailing_active}")
        print()
        
        if rule1.trailing_active != rule2.trailing_active:
            print(f"⚠️  DIFFERENCE FOUND: Trailing active status differs")
            print()
            print(f"Trade 172590811 (NOT trailing):")
            print(f"   • Breakeven: {rule1.breakeven_triggered}")
            print(f"   • Trailing Enabled: {rule1.trailing_enabled}")
            print(f"   • Trailing Active: {rule1.trailing_active}")
            print()
            print(f"Trade 172592863 (IS trailing):")
            print(f"   • Breakeven: {rule2.breakeven_triggered}")
            print(f"   • Trailing Enabled: {rule2.trailing_enabled}")
            print(f"   • Trailing Active: {rule2.trailing_active}")
            print()
            print(f"💡 Root Cause:")
            if rule1.breakeven_triggered and rule1.trailing_enabled and not rule1.trailing_active:
                print(f"   Trade 172590811: Breakeven triggered, trailing enabled, but trailing_active=False")
                print(f"   This means the gates check failed when breakeven was triggered")
                print(f"   The gates check at line 1532 in intelligent_exit_manager.py returned False")
                print()
                print(f"   Solution: Check why _trailing_gates_pass() is returning False for this trade")
                print(f"   Possible causes:")
                print(f"   • R-achieved < 0.2 (but breakeven should override this)")
                print(f"   • Exception during gates check")
                print(f"   • Advanced gate data missing or invalid")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

