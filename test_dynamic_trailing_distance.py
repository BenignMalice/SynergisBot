"""
Test dynamic trailing distance calculation
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
print("DYNAMIC TRAILING DISTANCE TEST")
print("=" * 80)
print()

# Test scenario: SELL trade with tight breakeven
print("Scenario: SELL trade with tight breakeven")
print()
print("Trade Details:")
print("  Entry: 86618.90")
print("  Breakeven SL: 86645.44 (26.54 points above entry)")
print("  Base ATR: 150.00")
print("  Base Multiplier: 1.7")
print("  Base Trailing Distance: 150.00 × 1.7 = 255.00 points")
print()

# Calculate dynamic trailing
breakeven_distance = 26.54
base_trailing_distance = 255.00

print("Analysis:")
print(f"  Breakeven distance: {breakeven_distance:.2f} points")
print(f"  Base trailing distance: {base_trailing_distance:.2f} points")
print(f"  Ratio: {breakeven_distance / base_trailing_distance:.2%}")
print()

if breakeven_distance < base_trailing_distance * 0.5:
    print("  ✅ Breakeven is TIGHT (< 50% of base trailing)")
    print("  → Dynamic trailing will REDUCE trailing distance")
    print()
    
    # Calculate adjusted multiplier
    tightness_ratio = breakeven_distance / base_trailing_distance
    adjusted_multiplier = 1.7 * (0.5 + 0.3 * tightness_ratio * 2)
    adjusted_distance = 150.00 * adjusted_multiplier
    
    print(f"  Tightness ratio: {tightness_ratio:.3f}")
    print(f"  Adjusted multiplier: {adjusted_multiplier:.2f} (from 1.7)")
    print(f"  Adjusted trailing distance: {adjusted_distance:.2f} points")
    print()
    
    # Test at different price levels
    print("Trailing Activation Test:")
    print()
    
    test_prices = [
        (86528.20, "Price when trailing was blocked"),
        (86450.00, "Price moved down 78 points"),
        (86400.00, "Price moved down 128 points"),
        (86350.00, "Price moved down 178 points"),
    ]
    
    current_sl = 86645.44
    
    for price, description in test_prices:
        ideal_sl = price + adjusted_distance
        would_tighten = ideal_sl < current_sl
        change = abs(ideal_sl - current_sl)
        
        print(f"  {description}:")
        print(f"    Price: {price:.2f}")
        print(f"    Ideal Trailing SL: {ideal_sl:.2f}")
        print(f"    Current SL: {current_sl:.2f}")
        print(f"    Would tighten: {would_tighten}")
        print(f"    Change: {change:.2f} points")
        if would_tighten:
            print(f"    ✅ TRAILING WOULD ACTIVATE")
        else:
            print(f"    ❌ Still blocked (would widen)")
        print()
    
    # Compare with base trailing
    print("Comparison with Base Trailing:")
    print()
    price = 86528.20
    base_ideal_sl = price + base_trailing_distance
    dynamic_ideal_sl = price + adjusted_distance
    
    print(f"  At price {price:.2f}:")
    print(f"    Base trailing SL: {base_ideal_sl:.2f} (would widen)")
    print(f"    Dynamic trailing SL: {dynamic_ideal_sl:.2f} (would {'tighten' if dynamic_ideal_sl < current_sl else 'widen'})")
    print()
    
    if dynamic_ideal_sl < current_sl:
        print("  ✅ Dynamic trailing allows activation SOONER!")
    else:
        print("  ⚠️  Still blocked, but requires less price movement")
        price_needed = current_sl - adjusted_distance
        print(f"  💡 Price needs to reach: {price_needed:.2f} (vs {current_sl - base_trailing_distance:.2f} with base)")
else:
    print("  ⚠️  Breakeven is NORMAL (>= 50% of base trailing)")
    print("  → Dynamic trailing will use FULL trailing distance")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()
print("✅ Dynamic trailing distance adapts to breakeven tightness:")
print("   • Tight breakeven (< 50% of base): Uses 50-80% of base trailing")
print("   • Normal breakeven (>= 50%): Uses full trailing distance")
print()
print("💡 Benefits:")
print("   • Trailing activates sooner when breakeven is tight")
print("   • Reduces risk of price reversal before trailing activates")
print("   • Still maintains proper trailing distance for normal breakeven")
print()

