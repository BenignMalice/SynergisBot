"""
Test Phase 1.1: Update Default Tolerance
Tests that XAUUSDc default tolerance is updated from 5.0 to 7.0
"""

import sys
from infra.tolerance_helper import get_price_tolerance

def test_phase1_1():
    """Test Phase 1.1: Default tolerance update"""
    print("Testing Phase 1.1: Update Default Tolerance...")
    
    # Test XAUUSDc
    xau_tolerance = get_price_tolerance('XAUUSDc')
    assert xau_tolerance == 7.0, f"XAUUSDc: Expected 7.0, got {xau_tolerance}"
    print(f"  [PASS] XAUUSDc tolerance: {xau_tolerance} (expected 7.0)")
    
    # Test XAUUSD (without 'c')
    xau_tolerance2 = get_price_tolerance('XAUUSD')
    assert xau_tolerance2 == 7.0, f"XAUUSD: Expected 7.0, got {xau_tolerance2}"
    print(f"  [PASS] XAUUSD tolerance: {xau_tolerance2} (expected 7.0)")
    
    # Test GOLD
    gold_tolerance = get_price_tolerance('GOLD')
    assert gold_tolerance == 7.0, f"GOLD: Expected 7.0, got {gold_tolerance}"
    print(f"  [PASS] GOLD tolerance: {gold_tolerance} (expected 7.0)")
    
    # Test other symbols unchanged
    btc_tolerance = get_price_tolerance('BTCUSDc')
    assert btc_tolerance == 100.0, f"BTCUSDc: Expected 100.0, got {btc_tolerance}"
    print(f"  [PASS] BTCUSDc tolerance: {btc_tolerance} (expected 100.0, unchanged)")
    
    eth_tolerance = get_price_tolerance('ETHUSDc')
    assert eth_tolerance == 10.0, f"ETHUSDc: Expected 10.0, got {eth_tolerance}"
    print(f"  [PASS] ETHUSDc tolerance: {eth_tolerance} (expected 10.0, unchanged)")
    
    # Test forex
    eur_tolerance = get_price_tolerance('EURUSDc')
    assert eur_tolerance == 0.001, f"EURUSDc: Expected 0.001, got {eur_tolerance}"
    print(f"  [PASS] EURUSDc tolerance: {eur_tolerance} (expected 0.001, unchanged)")
    
    print("\n[PASS] Phase 1.1: All tests passed!")
    return True

if __name__ == '__main__':
    try:
        test_phase1_1()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
