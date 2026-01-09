"""
Check if DXY is available in MT5 broker
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import MetaTrader5 as mt5

print("\n" + "="*70)
print("MT5 - DXY SYMBOL CHECK")
print("="*70)

# Initialize MT5
if not mt5.initialize():
    print("\n[FAIL] Could not initialize MT5")
    print(f"Error: {mt5.last_error()}")
    sys.exit(1)

print("\n[SUCCESS] MT5 initialized")

# List of possible DXY symbols
test_symbols = [
    "DXY",
    "USDX",
    "DXYc",
    "USDXc",
    "USDOLLAR",
    "USDOLLARc",
    "DX",
    "DXc"
]

print(f"\nSearching for DXY symbols in MT5...\n")

found_symbols = []

for symbol in test_symbols:
    # Try to get symbol info
    info = mt5.symbol_info(symbol)
    
    if info is not None:
        # Try to get current price
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            price = tick.bid
            print(f"[FOUND] {symbol:20} Price: {price:10.3f}")
            found_symbols.append((symbol, price))
        else:
            print(f"[FOUND] {symbol:20} (no tick data)")
            found_symbols.append((symbol, None))

if not found_symbols:
    print("[NO SYMBOLS FOUND]")
    print("\nSearching all symbols for 'USD' or 'DOLLAR'...")
    
    # Get all symbols
    all_symbols = mt5.symbols_get()
    usd_symbols = [s for s in all_symbols if 'USD' in s.name.upper() and 'INDEX' in s.name.upper() or 'DOLLAR' in s.name.upper()]
    
    if usd_symbols:
        print(f"\nFound {len(usd_symbols)} potential matches:")
        for s in usd_symbols[:10]:  # Show first 10
            print(f"   {s.name}")
    else:
        print("\n[NO USD INDEX SYMBOLS FOUND]")

mt5.shutdown()

print("\n" + "="*70)
print("SUMMARY")
print("="*70)

if found_symbols:
    print(f"\n[SUCCESS] Found {len(found_symbols)} DXY symbol(s) in MT5:\n")
    for symbol, price in found_symbols:
        if price:
            is_valid = 95 <= price <= 110
            status = "[VALID RANGE]" if is_valid else "[CHECK PRICE]"
            print(f"   {symbol:20} Price: {price:10.3f}  {status}")
        else:
            print(f"   {symbol:20} [NO PRICE DATA]")
    
    # Recommend best symbol
    valid = [(s, p) for s, p in found_symbols if p and 95 <= p <= 110]
    if valid:
        print(f"\n[RECOMMENDATION]: Use '{valid[0][0]}' from MT5")
    else:
        print(f"\n[RECOMMENDATION]: Use '{found_symbols[0][0]}' from MT5 (verify price)")
else:
    print("\n[FAIL] DXY not available in your MT5 broker")
    print("\n[NEXT STEPS]:")
    print("   1. Check if Exness offers DXY/USDX in another account type")
    print("   2. Use alternative free data source (yfinance, Alpha Vantage)")
    print("   3. Calculate USD strength from major pairs (recommended)")

print("\n" + "="*70)

