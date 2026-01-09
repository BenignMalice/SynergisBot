#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test lot size rounding to ensure only 0.01 increments
"""

import sys
import codecs

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from config.lot_sizing import calculate_lot_from_risk

# Test scenarios
test_cases = [
    {
        "symbol": "BTCUSDc",
        "entry": 65000,
        "stop_loss": 64800,  # 200 point stop
        "equity": 10000,
        "risk_pct": 0.75,
        "expected_max": 0.02
    },
    {
        "symbol": "EURUSDc",
        "entry": 1.1000,
        "stop_loss": 1.0980,  # 20 pip stop
        "equity": 10000,
        "risk_pct": 1.25,
        "expected_max": 0.04
    },
    {
        "symbol": "XAUUSDc",
        "entry": 3950,
        "stop_loss": 3940,  # 10 point stop
        "equity": 5000,  # Smaller equity
        "risk_pct": 1.0,
        "expected_max": 0.02
    }
]

print("=" * 70)
print("LOT SIZE ROUNDING TEST")
print("=" * 70)
print("\nTesting that all lot sizes are in 0.01 increments (0.01, 0.02, 0.03, 0.04)")
print("NOT fractional like 0.015 or 0.023\n")

all_passed = True

for i, test in enumerate(test_cases, 1):
    print(f"\nTest {i}: {test['symbol']}")
    print(f"  Entry: {test['entry']}, SL: {test['stop_loss']}")
    print(f"  Equity: ${test['equity']}, Risk: {test['risk_pct']}%")
    
    lot = calculate_lot_from_risk(
        symbol=test['symbol'],
        entry=test['entry'],
        stop_loss=test['stop_loss'],
        equity=test['equity'],
        risk_pct=test['risk_pct'],
        tick_value=1.0,
        tick_size=0.01,
        contract_size=100000
    )
    
    print(f"  Calculated Lot: {lot}")
    print(f"  Max Allowed: {test['expected_max']}")
    
    # Check if lot is in 0.01 increments
    remainder = (lot * 100) % 1
    is_valid_increment = abs(remainder) < 0.001  # Allow for floating point errors
    
    # Check if lot is within max
    is_within_max = lot <= test['expected_max']
    
    if is_valid_increment and is_within_max:
        print(f"  ✅ PASS - Lot size is in 0.01 increments and within max")
    else:
        print(f"  ❌ FAIL")
        if not is_valid_increment:
            print(f"     - Not in 0.01 increments (remainder: {remainder})")
        if not is_within_max:
            print(f"     - Exceeds maximum ({lot} > {test['expected_max']})")
        all_passed = False

print("\n" + "=" * 70)
if all_passed:
    print("✅ ALL TESTS PASSED - Lot sizes are correctly rounded to 0.01 increments")
else:
    print("❌ SOME TESTS FAILED - Check the output above")
print("=" * 70)

