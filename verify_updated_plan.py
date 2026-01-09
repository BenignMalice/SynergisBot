import json

# New plan conditions from user query
new_plan_conditions = {
    "price_below": 89680.0,
    "price_near": 89680.0,
    "tolerance": 120,
    "choch_bear": True,
    "liquidity_sweep": True,
    "min_confluence": 70,
    "timeframe": "M15",
    "strategy_type": "liquidity_sweep_reversal"
}

# Old plan conditions (from previous check)
old_plan_conditions = {
    "liquidity_sweep": True,
    "price_near": 89680.0,
    "tolerance": 120,
    "timeframe": "M15"
}

print("=" * 80)
print("LIQUIDITY SWEEP PLAN VALIDATION")
print("=" * 80)

print("\nOLD PLAN (chatgpt_db0df95c):")
print(f"  Conditions: {json.dumps(old_plan_conditions, indent=2)}")
old_issues = []
if not old_plan_conditions.get("choch_bear"):
    old_issues.append("[CRITICAL] Missing choch_bear: true - system will BLOCK execution")
if "price_below" not in old_plan_conditions and "price_above" not in old_plan_conditions:
    old_issues.append("[WARNING] Missing price_below/price_above - sweep detection may not work correctly")
if old_issues:
    print("  Issues:")
    for issue in old_issues:
        print(f"    {issue}")
else:
    print("  [OK]")

print("\nNEW PLAN (chatgpt_802de570):")
print(f"  Conditions: {json.dumps(new_plan_conditions, indent=2)}")

# Required conditions for SELL liquidity sweep reversal
required = {
    "liquidity_sweep": "CRITICAL - Plan won't detect sweeps without this",
    "choch_bear": "CRITICAL - System BLOCKS execution without CHOCH confirmation (for SELL plans)",
    "price_near": "REQUIRED - For execution control",
    "timeframe": "REQUIRED - For structure-based conditions"
}

recommended = {
    "price_below": "RECOMMENDED - For proper sweep detection",
    "price_above": "RECOMMENDED - Alternative to price_below",
    "min_confluence": "OPTIONAL - Adds confluence filter",
    "strategy_type": "OPTIONAL - For SL/TP management"
}

print("\n  Validation:")
all_good = True
for key, description in required.items():
    if key in new_plan_conditions and new_plan_conditions[key]:
        print(f"    [OK] {key}: {description}")
    else:
        print(f"    [MISSING] {key}: {description}")
        all_good = False

for key, description in recommended.items():
    if key in new_plan_conditions:
        print(f"    [OK] {key}: {description}")
    else:
        print(f"    [OPTIONAL] {key}: {description}")

print("\n" + "=" * 80)
print("COMPARISON")
print("=" * 80)
print("\nWhat was fixed:")
print("  [ADDED] choch_bear: true - This was the critical missing condition!")
print("  [ADDED] price_below: 89680.0 - Improves sweep detection")
print("  [ADDED] min_confluence: >=70 - Adds confluence filter")
print("  [ADDED] strategy_type: liquidity_sweep_reversal - For SL/TP management")

print("\nExecution Flow:")
print("  1. System checks if liquidity_sweep: true -> YES")
print("  2. System detects liquidity sweep using M1 microstructure analysis")
print("  3. System checks if choch_bear: true in conditions -> YES")
print("  4. System verifies CHOCH Bear is confirmed in M1 data -> Required for execution")
print("  5. System checks if price is near 89680.0 ±120 -> Required")
print("  6. System checks if price_below 89680.0 -> Required")
print("  7. System checks min_confluence >= 70 -> Required")
print("  8. System checks timeframe M15 -> Required")
print("  9. [BTCUSD ONLY] System checks CVD divergence -> Required for BTC")

if all_good:
    print("\n[RESULT] Plan is CORRECT and will execute when all conditions are met!")
else:
    print("\n[RESULT] Plan has issues that need to be fixed!")
