"""
Quick test script for enhanced macro_context
Run this to verify S&P 500, BTC Dominance, and Crypto Fear & Greed are working
"""
import asyncio
import sys
sys.path.insert(0, '.')

from desktop_agent import tool_macro_context

async def quick_test():
    print("\n" + "="*70)
    print("QUICK TEST: Enhanced Macro Context")
    print("="*70 + "\n")
    
    # Test Bitcoin analysis
    print("Testing Bitcoin Analysis...")
    print("-" * 70)
    
    try:
        result = await tool_macro_context({"symbol": "BTCUSD"})
        
        data = result["data"]
        
        print("\n[SUCCESS] Bitcoin Macro Context Retrieved\n")
        
        print("Traditional Markets:")
        print(f"  VIX: {data.get('vix', 'N/A'):.2f} ({data.get('risk_sentiment', 'N/A')})")
        print(f"  DXY: {data.get('dxy', 'N/A'):.2f} ({data.get('dxy_trend', 'N/A')})")
        print(f"  US10Y: {data.get('us10y', 'N/A'):.3f}%")
        
        print(f"\n  S&P 500: {data.get('sp500', 'N/A'):.2f} ({data.get('sp500_change_pct', 0):+.2f}%) [{data.get('sp500_trend', 'N/A')}]")
        sp500_status = "PASS" if data.get('sp500') else "FAIL"
        print(f"    Status: [{sp500_status}] S&P 500 integration")
        
        print("\nCrypto Fundamentals:")
        
        btc_dom = data.get('btc_dominance')
        if btc_dom:
            print(f"  BTC Dominance: {btc_dom:.1f}% ({data.get('btc_dominance_status', 'N/A')})")
            print(f"    Status: [PASS] Bitcoin Dominance integration")
        else:
            print(f"  BTC Dominance: Not available")
            print(f"    Status: [FAIL] Bitcoin Dominance missing")
        
        fg = data.get('crypto_fear_greed')
        if fg:
            print(f"  Crypto Fear & Greed: {fg}/100 ({data.get('crypto_sentiment', 'N/A')})")
            print(f"    Status: [PASS] Crypto Fear & Greed integration")
        else:
            print(f"  Crypto Fear & Greed: Not available")
            print(f"    Status: [FAIL] Crypto Fear & Greed missing")
        
        print("\nBitcoin Verdict:")
        print(f"  {data.get('symbol_context', 'No verdict available')}")
        
        print(f"\nTimestamp: {data.get('timestamp_human', 'N/A')}")
        
        # Summary
        print("\n" + "="*70)
        print("SUMMARY:")
        print("="*70)
        
        checks = [
            ("VIX", data.get('vix') is not None),
            ("DXY", data.get('dxy') is not None),
            ("US10Y", data.get('us10y') is not None),
            ("S&P 500", data.get('sp500') is not None),
            ("BTC Dominance", data.get('btc_dominance') is not None),
            ("Crypto Fear & Greed", data.get('crypto_fear_greed') is not None),
            ("Bitcoin Verdict", data.get('symbol_context') is not None)
        ]
        
        passed = sum(1 for _, status in checks if status)
        total = len(checks)
        
        for name, status in checks:
            status_icon = "[PASS]" if status else "[FAIL]"
            print(f"  {status_icon} {name}")
        
        print(f"\nResult: {passed}/{total} checks passed")
        
        if passed == total:
            print("\n[SUCCESS] All new data sources working correctly!")
            print("\nNext Steps:")
            print("  1. Test with ChatGPT: Ask 'Analyse Bitcoin'")
            print("  2. Verify ChatGPT displays all 5 signals")
            print("  3. Check timestamp is fresh")
        else:
            print(f"\n[WARNING] {total - passed} checks failed")
            print("\nTroubleshooting:")
            if not data.get('sp500'):
                print("  - S&P 500 failed: Check Yahoo Finance connection")
            if not data.get('btc_dominance'):
                print("  - BTC Dominance failed: Check CoinGecko API")
            if not data.get('crypto_fear_greed'):
                print("  - Crypto F&G failed: Check Alternative.me API")
        
    except Exception as e:
        print(f"\n[FAIL] Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(quick_test())

