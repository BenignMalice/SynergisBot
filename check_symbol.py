#!/usr/bin/env python3
"""
Symbol Checker - Diagnostic tool to find correct symbol names in MT5
"""

import MetaTrader5 as mt5
import sys

def check_symbol(symbol_partial: str):
    """Check if a symbol exists and show available alternatives"""
    
    # Initialize MT5
    if not mt5.initialize():
        print(f"❌ Failed to initialize MT5: {mt5.last_error()}")
        return
    
    print(f"\n🔍 Searching for symbols matching: {symbol_partial}\n")
    
    # Get all symbols
    all_symbols = mt5.symbols_get()
    if not all_symbols:
        print("❌ No symbols found in MT5")
        mt5.shutdown()
        return
    
    # Find matches
    matches = []
    for s in all_symbols:
        if symbol_partial.upper() in s.name.upper():
            matches.append(s)
    
    if not matches:
        print(f"❌ No symbols found matching '{symbol_partial}'")
        print(f"\n💡 Try checking your MT5 Market Watch for the correct symbol name")
        print(f"   Common variations:")
        print(f"   - {symbol_partial}c (with 'c' suffix)")
        print(f"   - {symbol_partial}.cash")
        print(f"   - {symbol_partial}#")
        print(f"   - {symbol_partial}.raw")
    else:
        print(f"✅ Found {len(matches)} matching symbol(s):\n")
        
        for s in matches:
            # Check if symbol is selected/visible
            visible = "✅ VISIBLE" if s.visible else "❌ HIDDEN"
            
            # Get current quote
            tick = mt5.symbol_info_tick(s.name)
            if tick:
                bid = tick.bid
                ask = tick.ask
                price_info = f"Bid: {bid}, Ask: {ask}"
            else:
                price_info = "No price data"
            
            # Check historical data
            rates = mt5.copy_rates_from_pos(s.name, mt5.TIMEFRAME_M5, 0, 10)
            data_available = "✅ HAS DATA" if rates is not None and len(rates) > 0 else "❌ NO DATA"
            
            print(f"📊 Symbol: {s.name}")
            print(f"   Description: {s.description}")
            print(f"   Status: {visible}")
            print(f"   Data: {data_available}")
            print(f"   Price: {price_info}")
            print(f"   Digits: {s.digits}")
            print(f"   Point: {s.point}")
            print()
            
            # Try to enable if hidden
            if not s.visible:
                if mt5.symbol_select(s.name, True):
                    print(f"   ✅ Symbol enabled in Market Watch")
                else:
                    print(f"   ❌ Failed to enable symbol")
                print()
    
    # Show recommended symbol
    if matches:
        # Find the first visible symbol with data
        recommended = None
        for s in matches:
            if s.visible:
                rates = mt5.copy_rates_from_pos(s.name, mt5.TIMEFRAME_M5, 0, 10)
                if rates is not None and len(rates) > 0:
                    recommended = s.name
                    break
        
        if recommended:
            print(f"✅ RECOMMENDED: Use '{recommended}' for analysis")
        else:
            print(f"⚠️  No fully functional symbol found.")
            print(f"   Try enabling one of the symbols above in MT5 Market Watch first.")
    
    mt5.shutdown()

def list_crypto_symbols():
    """List all available crypto symbols in MT5"""
    
    if not mt5.initialize():
        print(f"❌ Failed to initialize MT5: {mt5.last_error()}")
        return
    
    print(f"\n💰 Available Crypto Symbols in MT5:\n")
    
    all_symbols = mt5.symbols_get()
    if not all_symbols:
        print("❌ No symbols found")
        mt5.shutdown()
        return
    
    crypto_keywords = ['BTC', 'ETH', 'XRP', 'LTC', 'BCH', 'ADA', 'DOT', 'LINK', 'UNI', 'DOGE']
    crypto_symbols = []
    
    for s in all_symbols:
        for keyword in crypto_keywords:
            if keyword in s.name.upper():
                crypto_symbols.append(s)
                break
    
    if not crypto_symbols:
        print("❌ No crypto symbols found")
    else:
        print(f"Found {len(crypto_symbols)} crypto symbols:\n")
        for s in crypto_symbols:
            visible = "✅" if s.visible else "❌"
            print(f"{visible} {s.name:20s} - {s.description}")
    
    mt5.shutdown()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        symbol_to_check = sys.argv[1]
        check_symbol(symbol_to_check)
    else:
        print("Usage:")
        print("  python check_symbol.py BTCUSD    # Check specific symbol")
        print("  python check_symbol.py BTC       # Find all BTC symbols")
        print()
        print("Or run without arguments to list all crypto symbols:")
        list_crypto_symbols()

