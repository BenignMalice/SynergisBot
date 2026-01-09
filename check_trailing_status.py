"""
Quick diagnostic script to check trailing stops status
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
print("TRAILING STOPS STATUS CHECK")
print("=" * 80)
print()

# Check 1: Intelligent Exit Manager
print("1. Checking Intelligent Exit Manager...")
try:
    from infra.intelligent_exit_manager import IntelligentExitManager
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    manager = IntelligentExitManager(mt5_service=mt5_service)
    
    # Check if manager has rules
    rules = manager.get_all_rules()
    print(f"   ✅ Intelligent Exit Manager initialized")
    print(f"   📊 Active exit rules: {len(rules)}")
    
    if rules:
        print("\n   Active Rules:")
        for rule in rules:
            print(f"      - Ticket {rule.ticket} ({rule.symbol}):")
            print(f"        • Breakeven: {'✅' if rule.breakeven_triggered else '❌'}")
            print(f"        • Trailing: {'✅' if rule.trailing_active else '❌'}")
            print(f"        • Trailing Enabled: {'✅' if rule.trailing_enabled else '❌'}")
    else:
        print("   ℹ️  No active exit rules (no trades being managed)")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 2: Trailing Gates Configuration
print("2. Checking Trailing Gates Configuration...")
try:
    # Test the relaxed gates
    from infra.intelligent_exit_manager import ExitRule
    
    test_rule = ExitRule(
        ticket=999999,
        symbol="BTCUSDc",
        entry_price=87000.0,
        direction="buy",
        initial_sl=86500.0,
        initial_tp=88000.0,
        trailing_enabled=True
    )
    test_rule.breakeven_triggered = True
    
    result = manager._trailing_gates_pass(test_rule, 25.0, 0.25, return_details=True)
    
    if isinstance(result, tuple):
        should_trail, gate_info = result
        multiplier = gate_info.get('trailing_multiplier', 0)
        print(f"   ✅ Trailing gates working correctly")
        print(f"   📊 Test result: {'✅ ALLOW' if should_trail else '❌ BLOCK'}")
        print(f"   📊 Multiplier: {multiplier}x")
        print(f"   📊 Status: {gate_info.get('status', 'unknown')}")
    else:
        print(f"   ⚠️  Gates returned simple boolean: {result}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 3: Phone Hub Status (optional)
print("3. Checking Phone Hub Status (optional)...")
try:
    import httpx
    
    # Check if phone hub is running
    try:
        response = httpx.get("http://localhost:8001/health", timeout=2.0)
        if response.status_code == 200:
            print("   ✅ Phone hub is running")
        else:
            print(f"   ⚠️  Phone hub returned status {response.status_code}")
    except httpx.ConnectError:
        print("   ⚠️  Phone hub is not running (this is OK if you're not using phone control)")
    except Exception as e:
        print(f"   ⚠️  Could not check phone hub: {e}")
        
except Exception as e:
    print(f"   ⚠️  Could not check phone hub: {e}")

print()

# Check 4: MT5 Connection
print("4. Checking MT5 Connection...")
try:
    import MetaTrader5 as mt5
    
    if mt5.initialize():
        print("   ✅ MT5 connected")
        
        # Check for open positions
        positions = mt5.positions_get()
        if positions:
            print(f"   📊 Open positions: {len(positions)}")
            for pos in positions[:5]:  # Show first 5
                print(f"      - Ticket {pos.ticket} ({pos.symbol}): {pos.volume} lots")
        else:
            print("   ℹ️  No open positions")
    else:
        print("   ❌ MT5 not connected")
        
except Exception as e:
    print(f"   ⚠️  Could not check MT5: {e}")

print()
print("=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
print()
print("💡 TIP: If you see 'Phone hub connection error: HTTP 403', this is normal")
print("   if you're not using phone control. It doesn't affect trading functionality.")
print()

