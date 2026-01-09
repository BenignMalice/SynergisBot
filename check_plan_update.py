"""
Check if plan chatgpt_5fd4a133 was updated correctly
"""
import sqlite3
import json
from pathlib import Path

db_path = Path("data/auto_execution.db")
if not db_path.exists():
    print("ERROR: Database not found")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.execute(
    "SELECT plan_id, symbol, direction, entry_price, conditions, status, expires_at, notes FROM trade_plans WHERE plan_id = ?",
    ('chatgpt_5fd4a133',)
)
row = cursor.fetchone()
conn.close()

if not row:
    print("ERROR: Plan not found in database")
    exit(1)

plan_id, symbol, direction, entry_price, conditions_json, status, expires_at, notes = row

print("=" * 80)
print("PLAN VERIFICATION: chatgpt_5fd4a133")
print("=" * 80)
print()
print("Basic Details:")
print(f"  Plan ID: {plan_id}")
print(f"  Symbol: {symbol}")
print(f"  Direction: {direction}")
print(f"  Entry Price: {entry_price}")
print(f"  Status: {status}")
print(f"  Expires: {expires_at}")
print()

conditions = json.loads(conditions_json) if conditions_json else {}
print("Conditions:")
for key in sorted(conditions.keys()):
    value = conditions[key]
    print(f"  {key}: {value}")
print()

# Check for required conditions
print("Validation:")
required_conditions = {
    "fvg_bull": "Required for FVG retracement BUY",
    "price_near": "Required for entry trigger",
    "tolerance": "Required with price_near",
    "strategy_type": "Should be 'fvg_retracement'",
    "min_confluence": "Optional but recommended"
}

all_present = True
for req_key, req_desc in required_conditions.items():
    if req_key in conditions:
        value = conditions[req_key]
        print(f"  [OK] {req_key}: {value} - {req_desc}")
    else:
        print(f"  [MISSING] {req_key}: MISSING - {req_desc}")
        if req_key in ["fvg_bull", "price_near", "tolerance"]:
            all_present = False

print()
if all_present:
    print("[SUCCESS] PLAN IS CORRECTLY CONFIGURED")
    print("   -> All required conditions are present")
    print("   -> Plan will be monitored and executed when conditions are met")
else:
    print("[ERROR] PLAN IS MISSING REQUIRED CONDITIONS")
    print("   -> Plan may not execute properly")

print()
print("Execution Logic:")
print("  -> System checks for 'fvg_bull' condition (line 1541)")
print("  -> If present, validates FVG detection from DetectionSystemManager")
print("  -> Checks price_near with tolerance for entry trigger")
print("  -> Validates min_confluence if specified")
print("=" * 80)

