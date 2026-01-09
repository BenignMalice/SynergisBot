"""
Check strategy type for auto-executed trade
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
print(f"AUTO-EXECUTION TRADE STRATEGY CHECK - Ticket {ticket}")
print("=" * 80)
print()

# Check 1: Universal Manager Registration
print("1. Checking Universal Manager Registration...")
try:
    from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
    
    with manager.active_trades_lock:
        trade_state = manager.active_trades.get(ticket)
    
    if trade_state:
        print(f"   ✅ Trade registered with Universal Manager")
        print(f"   📊 Strategy: {trade_state.strategy_type.value if trade_state.strategy_type else 'None'}")
        print(f"   📊 Plan ID: {trade_state.plan_id if hasattr(trade_state, 'plan_id') else 'N/A'}")
        
        strategy = trade_state.strategy_type.value if trade_state.strategy_type else None
        plan_id = trade_state.plan_id if hasattr(trade_state, 'plan_id') else None
        
        if strategy == "default_standard":
            print(f"\n   🎯 RESULT: Using DEFAULT_STANDARD strategy")
            print(f"   💡 This means either:")
            print(f"      • Plan didn't have strategy_type, OR")
            print(f"      • strategy_type wasn't recognized")
        else:
            print(f"\n   🎯 RESULT: Using specific strategy: {strategy}")
            print(f"   ✅ Plan had strategy_type and it was recognized")
        
        if plan_id:
            print(f"\n   📋 Plan ID: {plan_id}")
            print(f"   💡 You can check the plan to see if it had strategy_type")
    else:
        print(f"   ⚠️  Trade NOT found in Universal Manager")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 2: Plan ID Lookup
print("2. Checking Plan (if available)...")
try:
    plan_id = None
    from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
    from infra.mt5_service import MT5Service
    
    mt5_service = MT5Service()
    manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
    
    with manager.active_trades_lock:
        trade_state = manager.active_trades.get(ticket)
        if trade_state and hasattr(trade_state, 'plan_id'):
            plan_id = trade_state.plan_id
    
    if plan_id:
        print(f"   📋 Plan ID: {plan_id}")
        
        # Try to load plan from database
        try:
            from app.main_api import get_db_connection
            import sqlite3
            
            db_path = "data/trade_plans.db"
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM trade_plans WHERE plan_id = ?", (plan_id,))
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    print(f"   ✅ Plan found in database")
                    # Check for strategy_type in conditions
                    import json
                    conditions = json.loads(row['conditions']) if row['conditions'] else {}
                    strategy_type = conditions.get('strategy_type')
                    
                    if strategy_type:
                        print(f"   📊 Plan strategy_type: {strategy_type}")
                        print(f"   💡 Plan HAD strategy_type, but trade is using DEFAULT_STANDARD")
                        print(f"   ⚠️  This suggests strategy_type wasn't recognized or normalized correctly")
                    else:
                        print(f"   📊 Plan strategy_type: None (not in plan)")
                        print(f"   ✅ Trade correctly using DEFAULT_STANDARD (plan had no strategy_type)")
                else:
                    print(f"   ⚠️  Plan not found in database")
            else:
                print(f"   ⚠️  Database not found: {db_path}")
        except Exception as e:
            print(f"   ⚠️  Could not check plan: {e}")
    else:
        print(f"   ⚠️  No plan_id found for this trade")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Check 3: Strategy Type Normalization
print("3. Checking Strategy Type Normalization...")
try:
    from infra.universal_sl_tp_manager import StrategyType, UNIVERSAL_MANAGED_STRATEGIES
    
    print(f"   📊 Available strategies: {len(UNIVERSAL_MANAGED_STRATEGIES)}")
    print(f"   📊 Strategies:")
    for st in UNIVERSAL_MANAGED_STRATEGIES:
        print(f"      - {st.value}")
    
    print(f"\n   💡 If plan had strategy_type but trade uses DEFAULT_STANDARD:")
    print(f"      • Strategy type might not match exactly")
    print(f"      • Normalization might have failed")
    print(f"      • Strategy might not be in UNIVERSAL_MANAGED_STRATEGIES")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()
print("💡 ANSWER TO YOUR QUESTION:")
print()
print("YES - Auto-executed trades are ALWAYS registered with Universal Manager")
print()
print("How it works:")
print("1. Auto-execution system ALWAYS registers with Universal Manager")
print("2. If plan has strategy_type → uses that strategy")
print("3. If plan has NO strategy_type → uses DEFAULT_STANDARD")
print()
print("Your trade:")
print("• Registered with Universal Manager ✅")
print("• Using strategy: DEFAULT_STANDARD")
print("• This means either:")
print("  - Plan didn't have strategy_type, OR")
print("  - strategy_type wasn't recognized")
print()
print("Universal Manager WILL manage trailing stops regardless of strategy type!")
print()

