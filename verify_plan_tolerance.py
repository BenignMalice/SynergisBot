"""Verify plan has tolerance in conditions and zone_entry_tracked field"""
import sqlite3
import json
import sys
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

db_path = Path("data/auto_execution.db")

if not db_path.exists():
    print(f"ERROR: Database not found at {db_path}")
    exit(1)

# Plan ID from ChatGPT response
plan_id = "chatgpt_ce8d0d52"

print(f"Verifying plan: {plan_id}\n")
print("=" * 80)

conn = sqlite3.connect(str(db_path))
cursor = conn.execute("""
    SELECT plan_id, symbol, direction, entry_price, conditions, 
           zone_entry_tracked, zone_entry_time, zone_exit_time
    FROM trade_plans 
    WHERE plan_id = ?
""", (plan_id,))

row = cursor.fetchone()

if not row:
    print(f"❌ Plan {plan_id} not found in database")
    exit(1)

plan_id_db, symbol, direction, entry_price, conditions_json, zone_entry_tracked, zone_entry_time, zone_exit_time = row

try:
    conditions = json.loads(conditions_json) if conditions_json else {}
except json.JSONDecodeError as e:
    print(f"❌ Error parsing conditions JSON: {e}")
    conditions = {}

print(f"Plan ID: {plan_id_db}")
print(f"Symbol: {symbol}")
print(f"Direction: {direction}")
print(f"Entry Price: {entry_price}")
print(f"\nConditions:")
print(json.dumps(conditions, indent=2))

print(f"\n{'='*80}")
print("VERIFICATION RESULTS:")
print("="*80)

# Check 1: Tolerance in conditions
tolerance = conditions.get("tolerance")
if tolerance:
    print(f"[PASS] Tolerance found in conditions: {tolerance} points")
    print(f"   Zone bounds: {entry_price - tolerance:.2f} - {entry_price + tolerance:.2f}")
else:
    print(f"[FAIL] Tolerance NOT found in conditions")
    print(f"   Expected: 'tolerance': 200")

# Check 2: Zone entry tracked field exists
if zone_entry_tracked is not None:
    print(f"[PASS] zone_entry_tracked field exists: {zone_entry_tracked}")
    if zone_entry_time:
        print(f"   Zone entry time: {zone_entry_time}")
    if zone_exit_time:
        print(f"   Zone exit time: {zone_exit_time}")
else:
    print(f"[FAIL] zone_entry_tracked field is None (may not exist in database)")

# Check 3: Required conditions for strategy
if "liquidity_sweep" in conditions:
    print(f"[PASS] Required condition 'liquidity_sweep' found: {conditions['liquidity_sweep']}")
else:
    print(f"[WARNING] 'liquidity_sweep' condition not found (may be required for strategy)")

print(f"\n{'='*80}")
print("SUMMARY:")
print("="*80)

all_passed = True
if not tolerance:
    all_passed = False
    print("[FAIL] Test 1.2 FAILED: Tolerance not found in conditions")
if zone_entry_tracked is None:
    all_passed = False
    print("[FAIL] Test 1.2 FAILED: zone_entry_tracked field missing")
if all_passed:
    print("[PASS] Test 1.2 PASSED: Plan has tolerance in conditions and zone_entry_tracked field exists")

conn.close()

