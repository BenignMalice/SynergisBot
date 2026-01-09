"""
Test Universal Manager functionality - check if it's working
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

print("=" * 80)
print("UNIVERSAL MANAGER FUNCTIONALITY CHECK")
print("=" * 80)
print()

# Check 1: Universal Manager Import
print("1. Checking Universal Manager Import...")
try:
    from infra.universal_sl_tp_manager import (
        UniversalDynamicSLTPManager,
        StrategyType,
        UNIVERSAL_MANAGED_STRATEGIES
    )
    print("   ✅ Universal Manager imported successfully")
    print(f"   📊 Managed strategies: {len(UNIVERSAL_MANAGED_STRATEGIES)}")
    print(f"   📊 DEFAULT_STANDARD in managed: {StrategyType.DEFAULT_STANDARD in UNIVERSAL_MANAGED_STRATEGIES}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Check 2: Universal Manager Initialization
print("2. Checking Universal Manager Initialization...")
try:
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
    print("   ✅ Universal Manager initialized successfully")
    
    # Check active trades
    active_trades = manager.active_trades
    print(f"   📊 Active trades in memory: {len(active_trades)}")
    
    if active_trades:
        print("\n   Active Trades:")
        for ticket, trade_state in active_trades.items():
            print(f"      - Ticket {ticket} ({trade_state.symbol}):")
            print(f"        • Strategy: {trade_state.strategy_type.value if trade_state.strategy_type else 'None'}")
            print(f"        • Managed by: {trade_state.managed_by if hasattr(trade_state, 'managed_by') else 'N/A'}")
            print(f"        • Breakeven: {'✅' if trade_state.breakeven_triggered else '❌'}")
    else:
        print("   ℹ️  No active trades in memory")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 3: Database Check
print("3. Checking Database for Registered Trades...")
try:
    import MetaTrader5 as mt5
    
    if mt5.initialize():
        positions = mt5.positions_get()
        if positions:
            print(f"   📊 Open MT5 positions: {len(positions)}")
            
            # Check trade registry
            from infra.trade_registry import get_trade_state
            
            universal_trades = []
            for pos in positions:
                trade_state = get_trade_state(pos.ticket)
                if trade_state:
                    if hasattr(trade_state, 'managed_by') and trade_state.managed_by == "universal_sl_tp_manager":
                        universal_trades.append(pos.ticket)
            
            print(f"   📊 Trades registered with Universal Manager: {len(universal_trades)}")
            
            if universal_trades:
                print("\n   Universal Manager Trades:")
                for ticket in universal_trades:
                    trade_state = get_trade_state(ticket)
                    pos = next((p for p in positions if p.ticket == ticket), None)
                    if pos:
                        print(f"      - Ticket {ticket} ({pos.symbol}):")
                        print(f"        • Strategy: {trade_state.strategy_type.value if trade_state.strategy_type else 'None'}")
                        print(f"        • Breakeven: {'✅' if trade_state.breakeven_triggered else '❌'}")
            else:
                print("   ⚠️  NO TRADES REGISTERED WITH UNIVERSAL MANAGER!")
                print("   ℹ️  This is the problem - trades need to be registered")
        else:
            print("   ℹ️  No open positions")
    else:
        print("   ❌ MT5 not connected")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 4: Registration Logic Issue
print("4. Checking Registration Logic...")
try:
    # Read desktop_agent.py to check registration logic
    desktop_agent_path = os.path.join(os.path.dirname(__file__), "desktop_agent.py")
    if os.path.exists(desktop_agent_path):
        with open(desktop_agent_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check if registration requires strategy_type
        if 'if strategy_type:' in content and 'universal_manager_registered = False' in content:
            print("   ⚠️  ISSUE FOUND: Registration only happens if strategy_type is provided")
            print("   ⚠️  Code says 'ALWAYS' but has conditional: if strategy_type:")
            print("   ⚠️  This means trades without strategy_type won't be registered!")
            
            # Check if there's a fix
            if 'strategy_type_enum = None' in content and 'DEFAULT_STANDARD' in content:
                print("   ℹ️  Code mentions DEFAULT_STANDARD but doesn't use it when strategy_type is None")
        else:
            print("   ✅ Registration logic looks correct")
    else:
        print("   ⚠️  Could not find desktop_agent.py")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check 5: Monitoring Status
print("5. Checking Monitoring Status...")
try:
    # Check if monitoring is scheduled in chatgpt_bot.py
    chatgpt_bot_path = os.path.join(os.path.dirname(__file__), "chatgpt_bot.py")
    if os.path.exists(chatgpt_bot_path):
        with open(chatgpt_bot_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'monitor_universal_trades' in content and 'universal_sl_tp_manager.monitor_all_trades' in content:
            print("   ✅ Monitoring is scheduled in chatgpt_bot.py")
            
            # Check if universal_sl_tp_manager is initialized
            if 'universal_sl_tp_manager =' in content or 'universal_sl_tp_manager:' in content:
                print("   ✅ Universal Manager variable exists")
            else:
                print("   ⚠️  WARNING: universal_sl_tp_manager might not be initialized!")
        else:
            print("   ⚠️  Monitoring not found in chatgpt_bot.py")
    else:
        print("   ⚠️  Could not find chatgpt_bot.py")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()

# Check 6: Test Registration
print("6. Testing Registration Logic...")
try:
    # Simulate registration with None strategy_type
    print("   Testing: register_trade with strategy_type=None")
    
    # Check if register_trade accepts None
    import inspect
    sig = inspect.signature(manager.register_trade)
    params = list(sig.parameters.keys())
    
    if 'strategy_type' in params:
        param = sig.parameters['strategy_type']
        print(f"   📊 strategy_type parameter: {param}")
        print(f"   📊 Default value: {param.default}")
        
        if param.default == inspect.Parameter.empty:
            print("   ⚠️  strategy_type is required (no default)")
        else:
            print(f"   ✅ strategy_type has default: {param.default}")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
print()
print("💡 KEY FINDINGS:")
print("   1. Check if trades are being registered with Universal Manager")
print("   2. Check if registration requires strategy_type (it shouldn't)")
print("   3. Check if monitoring is running in chatgpt_bot.py")
print()

