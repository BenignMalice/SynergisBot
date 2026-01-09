"""Analyze plan overfitting probability"""
import json

# Plan conditions
plan1 = {
    "choch_bull": True,
    "order_block": True,
    "order_block_type": "bull",
    "price_in_discount": True,
    "timeframe": "M5",
    "m1_choch_bos_combo": True,
    "min_volatility": 0.5,
    "price_near": 4216.0,
    "tolerance": 5.0,
    "strategy_type": "order_block_rejection"
}

plan2 = {
    "choch_bear": True,
    "order_block": True,
    "order_block_type": "bear",
    "price_in_premium": True,
    "timeframe": "M5",
    "m1_choch_bos_combo": True,
    "min_volatility": 0.5,
    "price_near": 4187.0,
    "tolerance": 5.0,
    "strategy_type": "order_block_rejection"
}

print("="*80)
print("PLAN OVERFITTING ANALYSIS")
print("="*80)

for plan_name, conditions in [("BUY Plan (chatgpt_a100dcfc)", plan1), ("SELL Plan (chatgpt_d492bc8b)", plan2)]:
    print(f"\n{plan_name}")
    print("-"*80)
    
    # Estimate probability of each condition (rough estimates)
    condition_probabilities = {
        "price_near": 0.3,  # Price within ±5.0 of entry (30% chance at any given time)
        "choch_bull/bear": 0.15,  # M5/M15 CHOCH occurs ~15% of the time
        "order_block": 0.25,  # Order blocks detected ~25% of the time
        "order_block_type_match": 0.5,  # 50% chance OB type matches direction
        "price_in_discount/premium": 0.3,  # Price in Fibonacci zone ~30% of time
        "m1_choch_bos_combo": 0.05,  # VERY RARE - M1 CHOCH+BOS combo ~5% of time
        "min_volatility": 0.6,  # Volatility ≥0.5 ~60% of time
    }
    
    # Calculate combined probability (assuming independence - worst case)
    prob = 1.0
    issues = []
    
    if "price_near" in conditions:
        prob *= condition_probabilities["price_near"]
        issues.append(f"price_near ({condition_probabilities['price_near']*100:.0f}%)")
    
    if "choch_bull" in conditions or "choch_bear" in conditions:
        prob *= condition_probabilities["choch_bull/bear"]
        issues.append(f"CHOCH ({condition_probabilities['choch_bull/bear']*100:.0f}%)")
    
    if "order_block" in conditions:
        prob *= condition_probabilities["order_block"]
        prob *= condition_probabilities["order_block_type_match"]
        issues.append(f"Order Block + Type Match ({condition_probabilities['order_block']*condition_probabilities['order_block_type_match']*100:.0f}%)")
    
    if "price_in_discount" in conditions or "price_in_premium" in conditions:
        prob *= condition_probabilities["price_in_discount/premium"]
        issues.append(f"Price in Zone ({condition_probabilities['price_in_discount/premium']*100:.0f}%)")
    
    if "m1_choch_bos_combo" in conditions:
        prob *= condition_probabilities["m1_choch_bos_combo"]
        issues.append(f"[CRITICAL] M1 CHOCH+BOS Combo ({condition_probabilities['m1_choch_bos_combo']*100:.0f}% - VERY RARE)")
    
    if "min_volatility" in conditions:
        prob *= condition_probabilities["min_volatility"]
        issues.append(f"Min Volatility ({condition_probabilities['min_volatility']*100:.0f}%)")
    
    print(f"\nConditions Required: {len(issues)}")
    print(f"Estimated Combined Probability: {prob*100:.2f}%")
    print(f"\nBreakdown:")
    for issue in issues:
        print(f"  - {issue}")
    
    if prob < 0.01:
        print(f"\n[CRITICAL] SEVERELY OVERFITTED - Less than 1% chance of execution")
    elif prob < 0.05:
        print(f"\n[WARNING] HIGHLY OVERFITTED - Less than 5% chance of execution")
    elif prob < 0.15:
        print(f"\n[CAUTION] MODERATELY OVERFITTED - Less than 15% chance of execution")
    else:
        print(f"\n[OK] REASONABLE - {prob*100:.0f}% chance of execution")

print("\n" + "="*80)
print("RECOMMENDATIONS")
print("="*80)
print("""
1. REMOVE m1_choch_bos_combo - This is the biggest overfitting factor
   - Documentation warns: "Very strict condition - may not occur frequently"
   - Reduces probability by 20x (from 5% to 0.25% if removed)

2. CONSIDER REMOVING price_in_discount/premium - Adds another filter
   - Price must be in Fibonacci zone (21-38% or 62-79% of range)
   - May not align with entry price

3. KEEP Core Conditions:
   - price_near + tolerance (essential for entry control)
   - choch_bull/bear (structure confirmation)
   - order_block (strategy requirement)
   - order_block_type (direction matching)

4. OPTIONAL: Keep min_volatility only if market is in dead zone
   - Otherwise, volatility is usually adequate

SIMPLIFIED PLAN EXAMPLE:
{
  "choch_bull": true,
  "order_block": true,
  "order_block_type": "bull",
  "price_near": 4216.0,
  "tolerance": 5.0,
  "timeframe": "M5",
  "strategy_type": "order_block_rejection"
}

This would have ~2-3% probability (still low but 10x better than current)
""")

