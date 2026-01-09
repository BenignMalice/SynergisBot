"""
Check if trade 157495802 is registered with Universal SL/TP Manager.
"""

import sys
import sqlite3
from pathlib import Path

# Fix encoding for Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

ticket = 157495802

print("=" * 80)
print(f"CHECKING TRADE REGISTRATION: Ticket {ticket}")
print("=" * 80)
print()

# ============================================================================
# 1. Check Trade Registry (In-Memory)
# ============================================================================
print("[1/3] Checking Trade Registry (In-Memory)...")
print("-" * 80)

try:
    from infra.trade_registry import get_trade_state
    
    trade_state = get_trade_state(ticket)
    
    if trade_state:
        print(f"  [OK] Trade found in registry")
        print(f"  Managed by: {trade_state.managed_by}")
        print(f"  Strategy: {trade_state.strategy_type.value if trade_state.strategy_type else 'None'}")
        print(f"  Symbol: {trade_state.symbol}")
        print(f"  Direction: {trade_state.direction}")
        print(f"  Entry Price: {trade_state.entry_price}")
        print(f"  Initial SL: {trade_state.initial_sl}")
        print(f"  Initial TP: {trade_state.initial_tp}")
        print(f"  Breakeven Triggered: {trade_state.breakeven_triggered}")
        print(f"  Partial Taken: {trade_state.partial_taken}")
        print(f"  Registered At: {trade_state.registered_at}")
        
        if trade_state.managed_by == "universal_sl_tp_manager":
            print(f"\n  ✅ Trade IS registered with Universal SL/TP Manager")
            print(f"  Trailing Method: {trade_state.resolved_trailing_rules.get('trailing_method', 'N/A')}")
            print(f"  Trailing Enabled: {trade_state.resolved_trailing_rules.get('trailing_enabled', 'N/A')}")
        else:
            print(f"\n  ⚠️ Trade is managed by: {trade_state.managed_by}")
            print(f"  (Not Universal Manager)")
    else:
        print(f"  [WARN] Trade NOT found in in-memory registry")
        print(f"  (May be in database but not loaded in memory)")
        
except ImportError as e:
    print(f"  [ERROR] Could not import trade_registry: {e}")
except Exception as e:
    print(f"  [ERROR] Error checking registry: {e}")
    import traceback
    traceback.print_exc()

print()

# ============================================================================
# 2. Check Universal Manager Database
# ============================================================================
print("[2/3] Checking Universal Manager Database...")
print("-" * 80)

db_path = project_root / "data" / "universal_sl_tp_trades.db"

if db_path.exists():
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute("""
                SELECT 
                    ticket, symbol, strategy_type, direction, session,
                    entry_price, initial_sl, initial_tp,
                    managed_by, breakeven_triggered, partial_taken,
                    registered_at, plan_id
                FROM universal_trades 
                WHERE ticket = ?
            """, (ticket,))
            
            row = cursor.fetchone()
            
            if row:
                print(f"  [OK] Trade found in database")
                print(f"  Ticket: {row[0]}")
                print(f"  Symbol: {row[1]}")
                print(f"  Strategy: {row[2]}")
                print(f"  Direction: {row[3]}")
                print(f"  Session: {row[4]}")
                print(f"  Entry Price: {row[5]}")
                print(f"  Initial SL: {row[6]}")
                print(f"  Initial TP: {row[7]}")
                print(f"  Managed By: {row[8]}")
                print(f"  Breakeven Triggered: {bool(row[9])}")
                print(f"  Partial Taken: {bool(row[10])}")
                print(f"  Registered At: {row[11]}")
                print(f"  Plan ID: {row[12]}")
                
                if row[8] == "universal_sl_tp_manager":
                    print(f"\n  ✅ Trade IS registered with Universal SL/TP Manager")
                else:
                    print(f"\n  ⚠️ Trade is managed by: {row[8]}")
            else:
                print(f"  [WARN] Trade NOT found in Universal Manager database")
                print(f"  (Trade is not registered with Universal Manager)")
                
    except Exception as e:
        print(f"  [ERROR] Error querying database: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"  [WARN] Database file not found: {db_path}")

print()

# ============================================================================
# 3. Check Intelligent Exit Manager
# ============================================================================
print("[3/3] Checking Intelligent Exit Manager...")
print("-" * 80)

storage_path = project_root / "data" / "intelligent_exits.json"

if storage_path.exists():
    try:
        import json
        
        with open(storage_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        rules = data.get("rules", {})
        rule = rules.get(str(ticket))
        
        if rule:
            print(f"  [OK] Trade found in Intelligent Exit Manager")
            print(f"  Symbol: {rule.get('symbol')}")
            print(f"  Entry Price: {rule.get('entry_price')}")
            print(f"  Direction: {rule.get('direction')}")
            print(f"  Breakeven Triggered: {rule.get('breakeven_triggered', False)}")
            print(f"  Trailing Enabled: {rule.get('trailing_enabled', False)}")
            print(f"  Trailing Active: {rule.get('trailing_active', False)}")
            print(f"  Last Trailing SL: {rule.get('last_trailing_sl')}")
            
            print(f"\n  ⚠️ Trade IS managed by Intelligent Exit Manager")
            print(f"  (This explains why Intelligent Exit Manager activated trailing)")
        else:
            print(f"  [INFO] Trade NOT found in Intelligent Exit Manager storage")
            
    except Exception as e:
        print(f"  [ERROR] Error reading Intelligent Exit Manager storage: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"  [INFO] Intelligent Exit Manager storage not found: {storage_path}")

print()

# ============================================================================
# SUMMARY
# ============================================================================
print("=" * 80)
print("SUMMARY")
print("=" * 80)

# Re-check to provide summary
try:
    from infra.trade_registry import get_trade_state
    trade_state = get_trade_state(ticket)
    
    if trade_state:
        if trade_state.managed_by == "universal_sl_tp_manager":
            print(f"✅ Trade {ticket} IS registered with Universal SL/TP Manager")
            print(f"   Strategy: {trade_state.strategy_type.value if trade_state.strategy_type else 'None'}")
            print(f"   Breakeven Triggered: {trade_state.breakeven_triggered}")
            print(f"\n   Next Steps:")
            if trade_state.breakeven_triggered:
                print(f"   - Universal Manager should be managing trailing stops")
                print(f"   - Check Universal Manager logs for trailing activity")
            else:
                print(f"   - Intelligent Exit Manager will handle breakeven")
                print(f"   - Universal Manager will take over after breakeven")
        else:
            print(f"⚠️ Trade {ticket} is managed by: {trade_state.managed_by}")
            print(f"   (Not Universal Manager)")
            print(f"\n   This explains why Intelligent Exit Manager activated trailing")
    else:
        # Check database
        if db_path.exists():
            try:
                with sqlite3.connect(str(db_path)) as conn:
                    cursor = conn.execute("""
                        SELECT managed_by FROM universal_trades WHERE ticket = ?
                    """, (ticket,))
                    row = cursor.fetchone()
                    if row and row[0] == "universal_sl_tp_manager":
                        print(f"✅ Trade {ticket} IS in database (Universal Manager)")
                        print(f"   But not loaded in memory registry")
                        print(f"   Universal Manager should load it on next check")
                    else:
                        print(f"[X] Trade {ticket} is NOT registered with Universal Manager")
                        print(f"   Intelligent Exit Manager is managing it (expected)")
            except Exception:
                print(f"[X] Trade {ticket} is NOT registered with Universal Manager")
                print(f"   Intelligent Exit Manager is managing it (expected)")
        else:
            print(f"[X] Trade {ticket} is NOT registered with Universal Manager")
            print(f"   Intelligent Exit Manager is managing it (expected)")
            
except Exception as e:
    print(f"Error generating summary: {e}")

print()
print("=" * 80)

