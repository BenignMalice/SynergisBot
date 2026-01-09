"""
Test ATR calculation for XAUUSD to diagnose failures

Usage:
    # Activate venv first (Windows PowerShell):
    .venv\Scripts\Activate.ps1
    
    # Then run:
    python test_atr_calculation.py
    
    # Or directly with venv Python (Windows):
    .venv\Scripts\python.exe test_atr_calculation.py
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Check if running in venv
if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    venv_python = os.path.join(os.path.dirname(__file__), '.venv', 'Scripts', 'python.exe')
    if os.path.exists(venv_python):
        print(f"[INFO] Not running in venv. Use: {venv_python} {__file__}")
        print(f"[INFO] Or activate venv with: .venv\\Scripts\\activate (Windows)")
    else:
        print("[INFO] Venv not found. Using system Python.")

async def test_atr():
    """Test ATR calculation for XAUUSD"""
    print("=" * 70)
    print("ATR CALCULATION TEST FOR XAUUSD")
    print("=" * 70)
    
    try:
        from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
        from infra.mt5_service import MT5Service
        
        # Initialize MT5
        print("\n1. Initializing MT5...")
        import MetaTrader5 as mt5
        if not mt5.initialize():
            error = mt5.last_error()
            print(f"   ERROR: MT5 initialization failed: {error}")
            return
        print("   OK: MT5 initialized")
        
        # Create Universal Manager
        print("\n2. Creating Universal Manager...")
        manager = UniversalDynamicSLTPManager()
        print("   OK: Universal Manager created")
        
        # Test ATR calculation for different timeframes
        print("\n3. Testing ATR Calculation:")
        print("-" * 70)
        
        symbol = "XAUUSDc"
        timeframes = ["M1", "M5", "M15", "M30", "H1"]
        
        for tf in timeframes:
            print(f"\n   Testing {symbol} {tf}:")
            
            # Method 1: Streamer
            print(f"      Method 1: Streamer Data Access")
            try:
                from infra.streamer_data_access import StreamerDataAccess
                streamer = StreamerDataAccess()
                atr = streamer.calculate_atr(symbol, tf, period=14)
                
                if atr and atr > 0:
                    print(f"      OK: Streamer ATR: {atr:.4f}")
                else:
                    print(f"      FAILED: Streamer returned: {atr}")
            except ImportError as e:
                print(f"      WARNING: StreamerDataAccess not available: {e}")
            except Exception as e:
                print(f"      ERROR: Streamer error: {e}")
            
            # Method 2: Universal Manager
            print(f"      Method 2: Universal Manager")
            atr = manager._get_current_atr(symbol, tf, period=14)
            
            if atr and atr > 0:
                print(f"      OK: Universal Manager ATR: {atr:.4f}")
            else:
                print(f"      FAILED: Universal Manager returned: {atr}")
            
            # Method 3: Direct MT5
            print(f"      Method 3: Direct MT5")
            try:
                import numpy as np
                
                tf_map = {
                    "M1": mt5.TIMEFRAME_M1,
                    "M5": mt5.TIMEFRAME_M5,
                    "M15": mt5.TIMEFRAME_M15,
                    "M30": mt5.TIMEFRAME_M30,
                    "H1": mt5.TIMEFRAME_H1,
                }
                
                mt5_tf = tf_map.get(tf)
                if mt5_tf:
                    bars = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, 50)
                    
                    if bars is None:
                        error = mt5.last_error()
                        print(f"      FAILED: MT5 returned no bars: {error}")
                    elif len(bars) < 16:
                        print(f"      WARNING: Insufficient bars: {len(bars)} (need 16+)")
                    else:
                        # Calculate ATR
                        highs = bars['high']
                        lows = bars['low']
                        closes = bars['close']
                        
                        high_low = highs[1:] - lows[1:]
                        high_close = np.abs(highs[1:] - closes[:-1])
                        low_close = np.abs(lows[1:] - closes[:-1])
                        
                        tr = np.maximum(high_low, np.maximum(high_close, low_close))
                        atr = np.mean(tr[-14:]) if len(tr) >= 14 else 0
                        
                        if atr > 0:
                            print(f"      OK: Direct MT5 ATR: {atr:.4f} (from {len(bars)} bars)")
                        else:
                            print(f"      FAILED: Direct MT5 ATR calculation returned 0")
                else:
                    print(f"      FAILED: Unknown timeframe: {tf}")
            except Exception as e:
                print(f"      ERROR: Direct MT5 error: {e}")
        
        # Test fallback methods
        print("\n4. Testing Fallback Methods:")
        print("-" * 70)
        
        # Create test rules
        test_rules = {
            "fallback_trailing_methods": ["fixed_distance", "percentage"],
            "fallback_fixed_distance": 1.5,
            "fallback_trailing_pct": 0.001
        }
        
        # Create a mock trade state for testing
        from infra.universal_sl_tp_manager import TradeState, StrategyType, Session
        from datetime import datetime
        
        test_trade_state = TradeState(
            ticket=999999,
            symbol="XAUUSDc",
            strategy_type=StrategyType.DEFAULT_STANDARD,
            direction="BUY",
            entry_price=4483.0,
            initial_sl=4479.0,
            initial_tp=4490.0,
            session=Session.LONDON,
            resolved_trailing_rules=test_rules,
            managed_by="universal_sl_tp_manager",
            initial_volume=0.01,
            current_price=4485.0,
            current_sl=4478.59,
            breakeven_triggered=True
        )
        
        print(f"\n   Testing Fixed Distance Fallback:")
        print(f"      Current Price: ${test_trade_state.current_price:.2f}")
        print(f"      Current SL: ${test_trade_state.current_sl:.2f}")
        fixed_sl = manager._get_fallback_trailing_sl(test_trade_state, test_rules, "fixed_distance")
        if fixed_sl:
            print(f"      OK: Fixed distance SL: {fixed_sl:.2f}")
            print(f"      Improvement: {fixed_sl - test_trade_state.current_sl:.2f} points")
        else:
            print(f"      FAILED: Fixed distance failed")
        
        print(f"\n   Testing Percentage Fallback:")
        pct_sl = manager._get_fallback_trailing_sl(test_trade_state, test_rules, "percentage")
        if pct_sl:
            print(f"      OK: Percentage SL: {pct_sl:.2f}")
            print(f"      Improvement: {pct_sl - test_trade_state.current_sl:.2f} points")
        else:
            print(f"      FAILED: Percentage failed")
        
        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        
        print(f"\nOK: Tests Completed:")
        print(f"   - ATR calculation tested for multiple timeframes")
        print(f"   - Fallback methods tested")
        print(f"   - Check results above to identify issues")
        
        print(f"\nRecommendations:")
        print(f"   - If all ATR methods fail: Check MT5 historical data")
        print(f"   - If streamer fails: Check streamer data access")
        print(f"   - If direct MT5 fails: Check MT5 connection and symbol data")
        print(f"   - Fallback methods should work even if ATR fails")
        
    except Exception as e:
        print(f"\nERROR: Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_atr())
