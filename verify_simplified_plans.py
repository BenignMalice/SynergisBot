"""Verify simplified plans are properly configured for monitoring"""
import sqlite3
import json
from pathlib import Path

db_path = Path("data/auto_execution.db")

plan_ids = ["chatgpt_b2dcbd59", "chatgpt_82d42dc8", "chatgpt_993ed80e", "chatgpt_e1cb3b86"]

print("="*80)
print("SIMPLIFIED PLANS VERIFICATION")
print("="*80)

conn = sqlite3.connect(str(db_path))
all_ok = True

for plan_id in plan_ids:
    cursor = conn.execute("""
        SELECT plan_id, symbol, direction, entry_price, conditions, status, expires_at
        FROM trade_plans 
        WHERE plan_id = ?
    """, (plan_id,))
    
    row = cursor.fetchone()
    
    if not row:
        print(f"\n[ERROR] Plan {plan_id} NOT FOUND in database")
        all_ok = False
        continue
    
    plan_id_db, symbol, direction, entry_price, conditions_json, status, expires_at = row
    
    try:
        conditions = json.loads(conditions_json) if conditions_json else {}
    except:
        conditions = {}
        print(f"\n[ERROR] Plan {plan_id} has invalid JSON in conditions")
        all_ok = False
        continue
    
    print(f"\n{plan_id_db} ({symbol} {direction})")
    print("-"*80)
    
    # Required conditions for order_block_rejection
    required = {
        "order_block": "Order Block (REQUIRED)",
    }
    
    # Recommended conditions
    recommended = {
        "price_near": "Price Near Entry",
        "tolerance": "Tolerance",
        "choch_bull": "CHOCH Bull (for BUY)",
        "choch_bear": "CHOCH Bear (for SELL)",
        "order_block_type": "Order Block Type",
        "timeframe": "Timeframe",
        "strategy_type": "Strategy Type"
    }
    
    # Check required
    missing_required = []
    for key, desc in required.items():
        if key not in conditions or not conditions[key]:
            missing_required.append(desc)
            all_ok = False
    
    # Check recommended
    present_recommended = []
    missing_recommended = []
    for key, desc in recommended.items():
        if key in conditions:
            present_recommended.append(f"{desc}: {conditions[key]}")
        else:
            missing_recommended.append(desc)
    
    # Status check
    if status != "pending":
        print(f"[WARNING] Status is '{status}' (expected 'pending')")
        if status in ["executed", "cancelled", "expired", "failed"]:
            all_ok = False
    
    # Results
    if missing_required:
        print(f"[FAIL] Missing Required Conditions:")
        for req in missing_required:
            print(f"  - {req}")
    else:
        print(f"[OK] All Required Conditions Present")
    
    if present_recommended:
        print(f"\n[OK] Recommended Conditions Present ({len(present_recommended)}):")
        for rec in present_recommended:
            print(f"  - {rec}")
    
    if missing_recommended:
        print(f"\n[INFO] Optional Conditions Not Set ({len(missing_recommended)}):")
        for rec in missing_recommended:
            print(f"  - {rec} (optional)")
    
    # Verify conditions will be monitored
    print(f"\n[VERIFICATION] Auto-Execution System Will Check:")
    checks = []
    
    if "order_block" in conditions:
        checks.append("[OK] Order Block detection (M1 + M5 validation)")
    if "choch_bull" in conditions or "choch_bear" in conditions:
        checks.append("[OK] CHOCH structure confirmation (M5/M15)")
    if "price_near" in conditions:
        checks.append(f"[OK] Price proximity check (entry: {entry_price}, tolerance: {conditions.get('tolerance', 'default')})")
    if "strategy_type" in conditions:
        checks.append(f"[OK] Strategy feature flag check ({conditions['strategy_type']})")
        checks.append("[OK] Circuit breaker check (if enabled)")
    
    for check in checks:
        print(f"  {check}")
    
    if not checks:
        print("  [WARNING] No conditions will be checked - plan may not execute")
        all_ok = False

conn.close()

print("\n" + "="*80)
if all_ok:
    print("[SUCCESS] All plans are properly configured and will be monitored")
    print("\nPlans will execute when:")
    print("  1. Price is within tolerance of entry")
    print("  2. CHOCH structure is confirmed (M5/M15)")
    print("  3. Order Block is detected and validated (M1 + M5)")
    print("  4. Order Block type matches plan direction")
    print("  5. Strategy feature flag is enabled")
    print("  6. Circuit breaker allows execution")
else:
    print("[WARNING] Some plans have issues - review above")
print("="*80)

