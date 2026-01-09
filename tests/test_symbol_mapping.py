"""
Symbol Mapping Test
Verifies Binance ↔ MT5 symbol conversion for all configured symbols.

Tests:
1. Binance → MT5 conversion (for offset calibration)
2. MT5 → Binance conversion (for user commands from phone)
3. Round-trip conversion (should return to original)
4. All 7 configured symbols

Usage:
    python test_symbol_mapping.py
"""

import sys
import codecs

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from infra.binance_service import BinanceService

def test_symbol_mappings():
    """
    Test all symbol conversions for the 7 configured symbols.
    """
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║              SYMBOL MAPPING VERIFICATION TEST                        ║")
    print("╚══════════════════════════════════════════════════════════════════════╝\n")
    
    # Create service instance
    service = BinanceService()
    
    # Test cases: (Binance symbol, Expected MT5 symbol)
    test_cases = [
        # Crypto
        ("btcusdt", "BTCUSDc"),
        ("ethusdt", "ETHUSDc"),
        
        # Commodities
        ("xauusd", "XAUUSDc"),
        
        # Forex Majors
        ("eurusd", "EURUSDc"),
        ("gbpusd", "GBPUSDc"),
        ("usdjpy", "USDJPYc"),
        
        # Forex Crosses
        ("gbpjpy", "GBPJPYc"),
        ("eurjpy", "EURJPYc"),
    ]
    
    all_passed = True
    
    print("="*70)
    print("TEST 1: Binance → MT5 Conversion")
    print("="*70)
    
    for binance_symbol, expected_mt5 in test_cases:
        result = service._convert_to_mt5_symbol(binance_symbol)
        status = "✅" if result == expected_mt5 else "❌"
        
        print(f"{status} {binance_symbol:12s} → {result:12s} (expected: {expected_mt5})")
        
        if result != expected_mt5:
            all_passed = False
            print(f"   ERROR: Got {result}, expected {expected_mt5}")
    
    print("\n" + "="*70)
    print("TEST 2: MT5 → Binance Conversion")
    print("="*70)
    
    for expected_binance, mt5_symbol in test_cases:
        result = service._convert_to_binance_symbol(mt5_symbol)
        status = "✅" if result == expected_binance else "❌"
        
        print(f"{status} {mt5_symbol:12s} → {result:12s} (expected: {expected_binance})")
        
        if result != expected_binance:
            all_passed = False
            print(f"   ERROR: Got {result}, expected {expected_binance}")
    
    print("\n" + "="*70)
    print("TEST 3: Round-Trip Conversion (Binance → MT5 → Binance)")
    print("="*70)
    
    for binance_symbol, _ in test_cases:
        # Binance → MT5
        mt5_symbol = service._convert_to_mt5_symbol(binance_symbol)
        # MT5 → Binance
        result = service._convert_to_binance_symbol(mt5_symbol)
        
        status = "✅" if result == binance_symbol else "❌"
        
        print(f"{status} {binance_symbol:12s} → {mt5_symbol:12s} → {result:12s}")
        
        if result != binance_symbol:
            all_passed = False
            print(f"   ERROR: Round-trip failed for {binance_symbol}")
    
    print("\n" + "="*70)
    print("TEST 4: User Input Variations (Case Insensitive)")
    print("="*70)
    
    # Test various user inputs from phone
    user_inputs = [
        ("BTCUSD", "BTCUSDc", "btcusdt"),      # User says BTCUSD
        ("btcusdc", "BTCUSDc", "btcusdt"),     # User says btcusdc
        ("BTCUSDc", "BTCUSDc", "btcusdt"),     # User says BTCUSDc (correct)
        ("GBPJPY", "GBPJPYc", "gbpjpy"),       # User says GBPJPY
        ("xauusd", "XAUUSDc", "xauusd"),       # User says xauusd
    ]
    
    for user_input, expected_mt5, expected_binance in user_inputs:
        # Convert user input to MT5
        mt5_result = service._convert_to_mt5_symbol(user_input)
        # Convert to Binance
        binance_result = service._convert_to_binance_symbol(user_input)
        
        mt5_ok = mt5_result == expected_mt5
        binance_ok = binance_result == expected_binance
        
        status = "✅" if (mt5_ok and binance_ok) else "❌"
        
        print(f"{status} Input: {user_input:12s} → MT5: {mt5_result:12s} | Binance: {binance_result:12s}")
        
        if not mt5_ok:
            all_passed = False
            print(f"   ERROR: MT5 conversion failed. Got {mt5_result}, expected {expected_mt5}")
        if not binance_ok:
            all_passed = False
            print(f"   ERROR: Binance conversion failed. Got {binance_result}, expected {expected_binance}")
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("\n✓ Binance symbols will correctly map to MT5 symbols ending in 'c'")
        print("✓ MT5 symbols will correctly map back to Binance symbols")
        print("✓ User inputs (from phone) will be handled correctly")
        print("✓ All 7 configured symbols are properly mapped")
    else:
        print("❌ SOME TESTS FAILED!")
        print("\n⚠️ Symbol mapping issues detected - review errors above")
    
    print("="*70 + "\n")
    
    # Print symbol mapping reference
    print("="*70)
    print("SYMBOL MAPPING REFERENCE")
    print("="*70)
    print("\n📊 Your Configured Symbols:\n")
    
    for binance_symbol, mt5_symbol in test_cases:
        print(f"  {binance_symbol.upper():12s} (Binance) ↔ {mt5_symbol:12s} (MT5)")
    
    print("\n💡 Notes:")
    print("  • Phone commands can use either format (BTCUSD or BTCUSDc)")
    print("  • System automatically converts between formats")
    print("  • Offset calibration uses MT5 symbols ending in 'c'")
    print("  • Binance streams use lowercase symbols without 'c'")
    
    print("\n" + "="*70 + "\n")
    
    return all_passed


if __name__ == "__main__":
    try:
        success = test_symbol_mappings()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

