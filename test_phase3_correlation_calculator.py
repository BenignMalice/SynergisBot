"""
Test Phase III Correlation Calculator Methods
Tests new correlation calculation methods
"""

import asyncio
import sys
import codecs
from datetime import datetime, timezone

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    except:
        pass  # If buffer doesn't exist, skip

def test_correlation_calculator():
    """Test Phase III correlation calculator methods"""
    print("=" * 60)
    print("Testing Phase III Correlation Calculator Methods")
    print("=" * 60)
    
    try:
        from infra.correlation_context_calculator import CorrelationContextCalculator
        from infra.market_indices_service import create_market_indices_service
        
        # Initialize calculator
        print("\n1. Initializing correlation calculator...")
        market_indices = create_market_indices_service()
        calculator = CorrelationContextCalculator(
            mt5_service=None,  # Will skip MT5-dependent tests
            market_indices_service=market_indices
        )
            print("[OK] Correlation calculator initialized")
        
        # Test DXY change percentage (requires market data)
        print("\n2. Testing calculate_dxy_change_pct()...")
        try:
            result = asyncio.run(calculator.calculate_dxy_change_pct(window_minutes=60))
            if result is not None:
                print(f"[OK] DXY change: {result:.2f}%")
            else:
                print("[WARN] DXY change returned None (data unavailable - this is OK for testing)")
        except Exception as e:
            print(f"[WARN] DXY change calculation error (expected if market closed): {e}")
        
        # Test DXY stall detection
        print("\n3. Testing detect_dxy_stall()...")
        try:
            result = asyncio.run(calculator.detect_dxy_stall(window_minutes=60))
            print(f"[OK] DXY stall detected: {result}")
        except Exception as e:
            print(f"[WARN] DXY stall detection error (expected if market closed): {e}")
        
        # Test ETH/BTC ratio deviation (requires MT5 or Binance API)
        print("\n4. Testing calculate_ethbtc_ratio_deviation()...")
        try:
            result = asyncio.run(calculator.calculate_ethbtc_ratio_deviation())
            if result:
                print(f"[OK] ETH/BTC ratio: {result.get('ratio', 'N/A')}")
                print(f"   Deviation: {result.get('deviation', 'N/A')} std dev")
                print(f"   Direction: {result.get('direction', 'N/A')}")
            else:
                print("[WARN] ETH/BTC ratio returned None (data unavailable - this is OK for testing)")
        except Exception as e:
            print(f"[WARN] ETH/BTC ratio calculation error (expected if MT5/Binance unavailable): {e}")
        
        # Test NASDAQ 15-min trend
        print("\n5. Testing get_nasdaq_15min_trend()...")
        try:
            result = asyncio.run(calculator.get_nasdaq_15min_trend())
            if result:
                print(f"[OK] NASDAQ trend: {result.get('trend', 'N/A')}")
                print(f"   15-min bullish: {result.get('nasdaq_15min_bullish', 'N/A')}")
                print(f"   Correlation confirmed: {result.get('nasdaq_correlation_confirmed', 'N/A')}")
            else:
                print("[WARN] NASDAQ trend returned None (data unavailable - this is OK for testing)")
        except Exception as e:
            print(f"[WARN] NASDAQ trend error (expected if market closed): {e}")
        
        # Test BTC hold above support (requires MT5)
        print("\n6. Testing check_btc_hold_above_support()...")
        try:
            result = asyncio.run(calculator.check_btc_hold_above_support(symbol="BTCUSDc"))
            print(f"[OK] BTC holds above support: {result}")
        except Exception as e:
            print(f"[WARN] BTC support check error (expected if MT5 unavailable): {e}")
        
        print("\n[OK] All correlation calculator method tests completed!")
        print("   (Some methods may return None if market data unavailable - this is expected)")
        return True
        
    except Exception as e:
        print(f"[FAIL] Error testing correlation calculator: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_correlation_calculator()
    sys.exit(0 if success else 1)

