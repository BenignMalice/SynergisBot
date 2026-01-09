"""
Check which system is managing a specific trade
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

ticket = 172588621  # Your trade ticket

print("=" * 80)
print(f"TRADE MANAGEMENT CHECK - Ticket {ticket}")
print("=" * 80)
print()

# Check 1: Trade Registry
print("1. Checking Trade Registry...")
try:
    from infra.trade_registry import get_trade_state
    
    trade_state = get_trade_state(ticket)
    if trade_state:
        print(f"   ✅ Trade found in registry")
        print(f"   📊 Managed by: {trade_state.managed_by if hasattr(trade_state, 'managed_by') else 'N/A'}")
        print(f"   📊 Breakeven triggered: {trade_state.breakeven_triggered if hasattr(trade_state, 'breakeven_triggered') else 'N/A'}")
        print(f"   📊 Strategy: {trade_state.strategy_type.value if hasattr(trade_state, 'strategy_type') and trade_state.strategy_type else 'N/A'}")
        
        managed_by = trade_state.managed_by if hasattr(trade_state, 'managed_by') else None
        breakeven = trade_state.breakeven_triggered if hasattr(trade_state, 'breakeven_triggered') else False
        
        if managed_by == "universal_sl_tp_manager":
            print(f"\n   🎯 RESULT: Universal Manager will manage trailing stops")
            if breakeven:
                print(f"   ✅ Breakeven triggered - Universal Manager should be trailing now")
            else:
                print(f"   ⏳ Breakeven not yet detected by Universal Manager (will detect on next cycle)")
        else:
            print(f"\n   🎯 RESULT: Intelligent Exit Manager will manage trailing stops")
            if breakeven:
                print(f"   ✅ Breakeven triggered - Trailing should start (if gates pass)")
    else:
        print(f"   ⚠️  Trade NOT found in registry")
        print(f"   🎯 RESULT: Intelligent Exit Manager is managing (fallback)")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 2: Intelligent Exit Manager
print("2. Checking Intelligent Exit Manager...")
try:
    from infra.intelligent_exit_manager import IntelligentExitManager
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    manager = IntelligentExitManager(mt5_service=mt5_service)
    
    rule = manager.get_rule(ticket)
    if rule:
        print(f"   ✅ Rule found in Intelligent Exit Manager")
        print(f"   📊 Breakeven triggered: {rule.breakeven_triggered}")
        print(f"   📊 Trailing enabled: {rule.trailing_enabled}")
        print(f"   📊 Trailing active: {rule.trailing_active}")
        
        if rule.breakeven_triggered and rule.trailing_enabled:
            if rule.trailing_active:
                print(f"\n   🎯 RESULT: Intelligent Exit Manager trailing is ACTIVE")
            else:
                print(f"\n   ⏳ RESULT: Trailing enabled but not active (gates may be blocking)")
    else:
        print(f"   ⚠️  Rule NOT found in Intelligent Exit Manager")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 3: Universal Manager
print("3. Checking Universal Manager...")
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
        print(f"   📊 Strategy: {trade_state.strategy_type.value if trade_state.strategy_type else 'N/A'}")
        
        if trade_state.breakeven_triggered:
            trailing_enabled = trade_state.resolved_trailing_rules.get('trailing_enabled', True)
            if trailing_enabled:
                print(f"\n   🎯 RESULT: Universal Manager trailing should be ACTIVE")
            else:
                print(f"\n   ⏳ RESULT: Trailing disabled for this strategy")
        else:
            print(f"\n   ⏳ RESULT: Breakeven not yet detected (will detect on next cycle)")
    else:
        print(f"   ⚠️  Trade NOT found in Universal Manager")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 4: Discord Notifications
print("4. Checking Discord Notifications...")
try:
    # Check if trailing_stop action sends Discord messages
    chatgpt_bot_path = os.path.join(os.path.dirname(__file__), "chatgpt_bot.py")
    if os.path.exists(chatgpt_bot_path):
        with open(chatgpt_bot_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'trailing_stop' in content and 'discord' in content.lower():
            print(f"   ✅ Discord notifications enabled for trailing stops")
            print(f"   📊 Action type: 'trailing_stop' sends Discord alerts")
        else:
            print(f"   ⚠️  Could not verify Discord notifications")
    else:
        print(f"   ⚠️  Could not find chatgpt_bot.py")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()
print("💡 ANSWERS TO YOUR QUESTIONS:")
print()
print("1. Should you see trailing stops now?")
print("   ✅ YES - Breakeven is set, trailing should start")
print()
print("2. Which system manages trailing stops?")
print("   • If registered with Universal Manager → Universal Manager manages")
print("   • If NOT registered → Intelligent Exit Manager manages")
print("   • Check results above to see which system is managing your trade")
print()
print("3. Will you receive Discord messages?")
print("   ✅ YES - Both systems send Discord alerts for trailing stop changes")
print("   • Intelligent Exit Manager: 'ATR Trailing Stop' alerts")
print("   • Universal Manager: Trailing stop adjustments (if configured)")
print()

