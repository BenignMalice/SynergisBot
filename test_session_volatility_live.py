"""
Test Phase 3.3: Session Volatility Curves with Live MT5 Data
Verify that session-specific volatility patterns work correctly with real MT5 data.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
from infra.volatility_forecasting import create_volatility_forecaster

def test_session_volatility_live():
    """Test session volatility curves with live MT5 data"""
    
    print("=" * 70)
    print("Phase 3.3: Session Volatility Curves - Live MT5 Test")
    print("=" * 70)
    
    # Initialize MT5
    print("\n1. Initializing MT5...")
    if not mt5.initialize():
        print("ERROR: MT5 initialization failed")
        print("   Make sure MetaTrader 5 is running and logged in")
        return False
    
    try:
        # Try multiple symbols (with and without 'c' suffix for broker compatibility)
        base_symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD"]
        test_symbols = []
        
        # Create list with both regular and 'c' suffix versions
        for base_symbol in base_symbols:
            test_symbols.append(base_symbol)  # Try regular first
            test_symbols.append(base_symbol + "c")  # Then with 'c' suffix
        
        symbol = None
        
        print("\n2. Finding available symbol...")
        for test_symbol in test_symbols:
            if mt5.symbol_select(test_symbol, True):
                symbol = test_symbol
                print(f"   Found symbol: {symbol}")
                break
            else:
                # Only print if it's a base symbol (avoid duplicate messages)
                if not test_symbol.endswith('c'):
                    print(f"   {test_symbol} not available")
        
        if symbol is None:
            print("\nERROR: No test symbols available in Market Watch")
            print("   Make sure MT5 is logged in and has symbols in Market Watch")
            print("   Tried: " + ", ".join(base_symbols) + " and their 'c' suffix versions")
            mt5.shutdown()
            return False
        
        print(f"\n3. Testing symbol: {symbol}")
        
        # Get M5 bars (need sufficient history for session analysis)
        print("\n4. Fetching M5 bars from MT5 (500 bars = ~1.7 days)...")
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 500)
        
        if rates is None:
            print("ERROR: No data returned from MT5")
            mt5.shutdown()
            return False
        
        if len(rates) < 100:
            print(f"ERROR: Insufficient bars ({len(rates)}) - need at least 100")
            print("   Make sure you have at least 1-2 days of historical data in MT5")
            mt5.shutdown()
            return False
        
        print(f"   Retrieved {len(rates)} bars from MT5")
        
        # Convert to DataFrame
        print("\n5. Converting MT5 data to DataFrame...")
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')  # MT5 returns Unix timestamps
        df = df.set_index('time')
        df = df.rename(columns={'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close'})
        
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")
        print(f"   Latest bar time: {df.index[-1]}")
        
        # Create volatility forecaster
        print("\n6. Creating VolatilityForecaster...")
        forecaster = create_volatility_forecaster()
        print("   VolatilityForecaster created")
        
        # Test session detection on current timestamp
        print("\n7. Testing session detection...")
        current_time = df.index[-1]
        detected_session = forecaster._get_session_from_timestamp(current_time)
        print(f"   Current timestamp: {current_time}")
        print(f"   UTC hour: {current_time.hour}")
        print(f"   Detected session: {detected_session}")
        
        # Calculate session volatility curves
        print("\n8. Calculating session volatility curves (7-day lookback)...")
        session_curves = forecaster.calculate_session_volatility_curves(df, lookback_days=7)
        
        # Check results
        print("\n9. Results:")
        print("-" * 70)
        
        current_session = session_curves.get("current_session", "UNKNOWN")
        current_atr = session_curves.get("current_session_atr", 0)
        
        print(f"Current Session: {current_session}")
        print(f"Current Session ATR: {current_atr:.6f}")
        
        # Check session curves
        curves = session_curves.get("session_curves", {})
        print("\nSession Statistics (from live MT5 data):")
        print("-" * 70)
        
        sessions_with_data = []
        for session in ["ASIA", "LONDON", "NY"]:
            curve = curves.get(session, {})
            avg_atr = curve.get("avg_atr", 0)
            median_atr = curve.get("median_atr", 0)
            sample_count = curve.get("sample_count", 0)
            vol_level = curve.get("volatility_level", "unknown")
            
            if sample_count > 0:
                sessions_with_data.append((session, avg_atr))
                print(f"\n{session}:")
                print(f"  Avg ATR: {avg_atr:.6f}")
                print(f"  Median ATR: {median_atr:.6f}")
                print(f"  Sample Count: {sample_count} bars")
                print(f"  Volatility Level: {vol_level}")
                print(f"  25th percentile: {curve.get('percentile_25', 0):.6f}")
                print(f"  75th percentile: {curve.get('percentile_75', 0):.6f}")
                print(f"  Min ATR: {curve.get('min_atr', 0):.6f}")
                print(f"  Max ATR: {curve.get('max_atr', 0):.6f}")
            else:
                print(f"\n{session}: No data (sample_count: {sample_count})")
        
        # Check current vs historical
        current_vs_hist = session_curves.get("current_vs_historical", {})
        print("\n" + "-" * 70)
        print("Current vs Historical Comparison:")
        print("-" * 70)
        
        if current_vs_hist:
            vs_avg = current_vs_hist.get("vs_avg", 1.0)
            vs_median = current_vs_hist.get("vs_median", 1.0)
            percentile = current_vs_hist.get("percentile", 50)
            interpretation = current_vs_hist.get("interpretation", "")
            
            print(f"Current ATR vs Average: {vs_avg:.2f}x")
            print(f"Current ATR vs Median: {vs_median:.2f}x")
            print(f"Percentile Ranking: {percentile}th percentile")
            print(f"Interpretation: {interpretation}")
            
            # Interpretation based on vs_avg
            if vs_avg >= 1.2:
                print(f"\n   -> Current {current_session} session has HIGHER volatility than normal")
                print(f"   -> Expect wider price moves")
            elif vs_avg <= 0.8:
                print(f"\n   -> Current {current_session} session has LOWER volatility than normal")
                print(f"   -> Expect tighter ranges")
            else:
                print(f"\n   -> Current {current_session} session volatility is NORMAL")
        else:
            print("No current vs historical comparison available")
            print("   (May need more historical data spanning multiple sessions)")
        
        # Validation
        print("\n10. Validation:")
        print("-" * 70)
        
        checks_passed = 0
        total_checks = 0
        
        # Check 1: MT5 connection successful
        total_checks += 1
        if rates is not None and len(rates) > 0:
            print(f"PASS: MT5 connection successful ({len(rates)} bars)")
            checks_passed += 1
        else:
            print("FAIL: MT5 connection failed")
        
        # Check 2: DataFrame conversion successful
        total_checks += 1
        if len(df) > 0 and isinstance(df.index, pd.DatetimeIndex):
            print("PASS: DataFrame conversion successful")
            checks_passed += 1
        else:
            print("FAIL: DataFrame conversion failed")
        
        # Check 3: Current session identified
        total_checks += 1
        if current_session != "UNKNOWN":
            print(f"PASS: Current session identified ({current_session})")
            checks_passed += 1
        else:
            print(f"FAIL: Current session not identified (likely weekend or outside trading hours)")
        
        # Check 4: Current ATR calculated
        total_checks += 1
        if current_atr > 0:
            print(f"PASS: Current session ATR calculated ({current_atr:.6f})")
            checks_passed += 1
        else:
            print("FAIL: Current session ATR not calculated")
        
        # Check 5: At least one session has statistics
        total_checks += 1
        if len(sessions_with_data) > 0:
            print(f"PASS: Statistics calculated for {len(sessions_with_data)} session(s)")
            checks_passed += 1
        else:
            print("FAIL: No session statistics calculated")
            print("   (May need more historical data spanning multiple sessions)")
        
        # Check 6: Current vs historical comparison available
        total_checks += 1
        if current_vs_hist and current_vs_hist.get("vs_avg", 0) > 0:
            print("PASS: Current vs historical comparison available")
            checks_passed += 1
        else:
            print("WARN: Current vs historical comparison not available")
            print("   (May need more historical data for current session)")
        
        # Check 7: Multiple sessions detected (good for validation)
        total_checks += 1
        if len(sessions_with_data) >= 2:
            print(f"PASS: Multiple sessions detected ({len(sessions_with_data)} sessions)")
            checks_passed += 1
        else:
            print(f"INFO: Only {len(sessions_with_data)} session(s) with data")
            print("   (This is OK if you're only testing during one trading session)")
        
        print("\n" + "=" * 70)
        print(f"Test Results: {checks_passed}/{total_checks} checks passed")
        print("=" * 70)
        
        if checks_passed >= 5:  # At least 5 core checks must pass
            print("\n[PASS] Phase 3.3: Session Volatility Curves - LIVE MT5 TEST PASSED")
            print("\nThe implementation works correctly with live MT5 data!")
            return True
        else:
            print("\n[FAIL] Phase 3.3: Session Volatility Curves - LIVE MT5 TEST FAILED")
            print("\nSome checks failed. Review the output above for details.")
            return False
        
    except Exception as e:
        print(f"\nERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        mt5.shutdown()
        print("\nMT5 connection closed")


if __name__ == "__main__":
    success = test_session_volatility_live()
    sys.exit(0 if success else 1)

