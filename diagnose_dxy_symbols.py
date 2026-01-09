"""
Diagnose which DXY symbols work with Twelve Data API
Tests multiple possible symbols and shows which ones return valid data
"""

import requests
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import settings

API_KEY = settings.TWELVE_DATA_API_KEY

print("\n" + "="*70)
print("TWELVE DATA - DXY SYMBOL DIAGNOSTIC")
print("="*70)

# List of symbols to test
test_symbols = [
    "DXY",           # Standard US Dollar Index
    "USDX",          # Alternative name
    "DX=F",          # Futures format
    "USDOLLAR",      # Alternative naming
    "USD/INDEX",     # Index format
    "DXY:INDX",      # Exchange suffix
    "USDOLLAR:IND",  # Index suffix
]

print(f"\nTesting {len(test_symbols)} possible symbols...")
print(f"API Key: {API_KEY[:8]}...{API_KEY[-4:]}\n")

working_symbols = []

for symbol in test_symbols:
    print(f"Testing: {symbol:20}", end=" -> ")
    
    try:
        # Test with quote endpoint (simpler, uses less credits)
        url = "https://api.twelvedata.com/quote"
        params = {
            "symbol": symbol,
            "apikey": API_KEY
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if 'status' in data and data['status'] == 'error':
            print(f"FAIL: {data.get('message', 'Unknown error')[:60]}")
        elif 'close' in data or 'price' in data:
            price = float(data.get('close', data.get('price', 0)))
            print(f"SUCCESS! Price: {price:.3f}")
            working_symbols.append((symbol, price))
        else:
            print(f"FAIL: Unexpected response format")
            
    except Exception as e:
        print(f"ERROR: {str(e)[:60]}")

print("\n" + "="*70)
print("SUMMARY")
print("="*70)

if working_symbols:
    print(f"\n[SUCCESS] Found {len(working_symbols)} working symbol(s):\n")
    for symbol, price in working_symbols:
        # Check if price is in expected DXY range (95-110)
        is_valid_range = 95 <= price <= 110
        status = "[VALID]" if is_valid_range else "[UNUSUAL - expected 95-110]"
        print(f"   {symbol:20} Price: {price:8.3f}  {status}")
    
    print(f"\n[RECOMMENDATION]:")
    # Find symbol with price in valid DXY range
    valid_dxy = [s for s, p in working_symbols if 95 <= p <= 110]
    if valid_dxy:
        print(f"   Use: {valid_dxy[0]}")
    else:
        print(f"   Use: {working_symbols[0][0]} (check if this is correct DXY data)")
else:
    print("\n[FAIL] No working symbols found!")
    print("\n[POSSIBLE REASONS]:")
    print("   1. DXY requires Twelve Data premium/pro plan")
    print("   2. Free plan only includes forex pairs, not indices")
    print("   3. Different symbol naming convention")
    
    print("\n[ALTERNATIVE SOLUTIONS]:")
    print("   1. Upgrade to Twelve Data premium plan")
    print("   2. Use alternative data source (Alpha Vantage, Yahoo Finance)")
    print("   3. Use MT5's built-in DXY symbol if available")
    print("   4. Calculate USD strength from forex pairs (EURUSD, USDJPY, etc.)")

print("\n" + "="*70)

