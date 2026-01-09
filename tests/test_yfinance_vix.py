"""
Test if Yahoo Finance has VIX data
"""

import yfinance as yf

print("\n" + "="*70)
print("YAHOO FINANCE - VIX TEST")
print("="*70)

# VIX symbol on Yahoo Finance
symbol = "^VIX"

print(f"\nFetching VIX data from Yahoo Finance...")
print(f"Symbol: {symbol}\n")

try:
    # Create ticker
    vix = yf.Ticker(symbol)
    
    # Get current price
    info = vix.info
    current_price = info.get('regularMarketPrice', info.get('previousClose'))
    
    print(f"Current VIX Price: {current_price:.2f}")
    
    # Get historical data
    hist = vix.history(period="5d", interval="1h")
    
    if len(hist) > 0:
        latest = hist.iloc[-1]
        print(f"Latest Close:    {latest['Close']:.2f}")
        print(f"Latest High:     {latest['High']:.2f}")
        print(f"Latest Low:      {latest['Low']:.2f}")
        print(f"Bars available:  {len(hist)}")
        
        # Interpret VIX level
        vix_level = latest['Close']
        print(f"\nVIX Interpretation:")
        if vix_level < 15:
            print(f"  VIX {vix_level:.2f} = LOW VOLATILITY (complacent market)")
            print(f"  Risk: LOW - Good for trend trading")
        elif vix_level < 20:
            print(f"  VIX {vix_level:.2f} = NORMAL VOLATILITY")
            print(f"  Risk: MODERATE - Standard conditions")
        elif vix_level < 30:
            print(f"  VIX {vix_level:.2f} = ELEVATED VOLATILITY (caution)")
            print(f"  Risk: HIGH - Wider stops needed")
        else:
            print(f"  VIX {vix_level:.2f} = HIGH VOLATILITY (fear/panic)")
            print(f"  Risk: VERY HIGH - Avoid new positions")
        
        print("\n[SUCCESS] Yahoo Finance VIX data is working!")
    else:
        print("\n[FAIL] No historical data available")
        
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)

