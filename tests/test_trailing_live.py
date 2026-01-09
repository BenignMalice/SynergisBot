"""
Test Trailing Stops with Live MT5 Data
Tests the trailing stop functionality using real MT5 positions
"""

import sys
import MetaTrader5 as mt5
from infra.mt5_service import MT5Service
from infra.indicator_bridge import IndicatorBridge
from infra.trailing_stops import calculate_trailing_stop
from infra.momentum_detector import detect_momentum


def test_trailing_with_live_position():
    """Test trailing stops with actual MT5 position if available."""
    print("\n" + "="*70)
    print("LIVE TRAILING STOPS TEST")
    print("="*70)
    
    # Initialize MT5
    if not mt5.initialize():
        print("[ERROR] Failed to initialize MT5")
        return False
    
    # Get open positions
    positions = mt5.positions_get()
    
    if not positions or len(positions) == 0:
        print("\n[INFO] No open positions found.")
        print("To test trailing stops:")
        print("1. Open a position in MT5")
        print("2. Let it move into profit (+1R or more)")
        print("3. Run this test again")
        mt5.shutdown()
        return True
    
    print(f"\n[INFO] Found {len(positions)} open position(s)")
    
    # Test with first position
    pos = positions[0]
    
    print("\n" + "-"*70)
    print(f"Testing Position: {pos.ticket}")
    print("-"*70)
    print(f"Symbol: {pos.symbol}")
    print(f"Type: {'LONG' if pos.type == 0 else 'SHORT'}")
    print(f"Entry: {pos.price_open:.5f}")
    print(f"Current Price: {pos.price_current:.5f}")
    print(f"Current SL: {pos.sl:.5f}")
    print(f"Current TP: {pos.tp:.5f}")
    print(f"Profit: ${pos.profit:.2f}")
    
    # Get ATR
    try:
        mt5_service = MT5Service()
        bridge = IndicatorBridge(mt5_service)
        
        symbol = pos.symbol
        timeframe = "M5"
        
        # Get bars for feature calculation
        bars = bridge.get_bars(symbol, timeframe, count=100)
        if bars is None or len(bars) == 0:
            print(f"\n[ERROR] Could not get bars for {symbol}")
            mt5.shutdown()
            return False
        
        # Calculate ATR
        atr_values = bridge.calculate_atr(bars, period=14)
        if atr_values is None or len(atr_values) == 0:
            print(f"\n[ERROR] Could not calculate ATR")
            mt5.shutdown()
            return False
        
        atr = atr_values.iloc[-1]
        print(f"\nATR(14): {atr:.5f}")
        
        # Build features for momentum detection
        features = {}
        
        # MACD
        macd_line, signal_line, macd_hist = bridge.calculate_macd(bars)
        if macd_hist is not None and len(macd_hist) >= 3:
            features["macd_hist"] = macd_hist.iloc[-1]
            features["macd_hist_prev"] = macd_hist.iloc[-2]
            features["macd_hist_prev2"] = macd_hist.iloc[-3]
        
        # Range
        features["range_current"] = bars['high'].iloc[-1] - bars['low'].iloc[-1]
        features["range_median_20"] = (bars['high'].iloc[-20:] - bars['low'].iloc[-20:]).median()
        
        # Volume (if available)
        if 'tick_volume' in bars.columns:
            vol_mean = bars['tick_volume'].iloc[-20:].mean()
            vol_std = bars['tick_volume'].iloc[-20:].std()
            features["volume_zscore"] = (bars['tick_volume'].iloc[-1] - vol_mean) / vol_std if vol_std > 0 else 0
        else:
            features["volume_zscore"] = 0
        
        # ATR ratios
        atr_5_values = bridge.calculate_atr(bars, period=5)
        if atr_5_values is not None:
            features["atr_5"] = atr_5_values.iloc[-1]
            features["atr_14"] = atr
        
        print("\nFeatures extracted:")
        for key, val in features.items():
            if isinstance(val, (int, float)):
                print(f"  {key}: {val:.4f}")
        
        # Detect momentum
        momentum = detect_momentum(features)
        print(f"\nMomentum State: {momentum.state.value}")
        print(f"Score: {momentum.score:.2f}")
        print(f"Reasoning: {momentum.reasoning}")
        
        # Calculate trailing stop
        direction = "long" if pos.type == 0 else "short"
        
        result = calculate_trailing_stop(
            entry=pos.price_open,
            current_sl=pos.sl,
            current_price=pos.price_current,
            direction=direction,
            atr=atr,
            features=features,
            structure=None,  # Could add EMA/structure if needed
            trigger_r=1.0,
            wide_trail_atr=2.0,
            standard_trail_atr=1.5,
            tight_trail_r=0.5
        )
        
        print("\n" + "="*70)
        print("TRAILING STOP RESULT")
        print("="*70)
        print(f"Unrealized R: {result.unrealized_r:.2f}R")
        print(f"Trail Method: {result.trail_method}")
        print(f"Momentum: {result.momentum_state}")
        print(f"Current SL: {pos.sl:.5f}")
        print(f"New SL: {result.new_sl:.5f}")
        print(f"Trailed: {result.trailed}")
        print(f"Trail Distance: {result.trail_distance_atr:.2f}× ATR")
        print(f"\nRationale: {result.rationale}")
        
        if result.trailed:
            sl_improvement = abs(result.new_sl - pos.sl)
            pip_size = 0.0001 if "JPY" not in symbol else 0.01
            pips = sl_improvement / pip_size
            print(f"\n✅ SL would be moved {pips:.1f} pips")
            print(f"   Old SL: {pos.sl:.5f}")
            print(f"   New SL: {result.new_sl:.5f}")
            
            if direction == "long":
                improvement = "BETTER" if result.new_sl > pos.sl else "WORSE"
            else:
                improvement = "BETTER" if result.new_sl < pos.sl else "WORSE"
            print(f"   Direction: {improvement}")
        else:
            print(f"\n⏸️  No trailing action needed")
        
        print("\n" + "="*70)
        print("[SUCCESS] Live trailing stops test completed!")
        print("="*70)
        
        mt5.shutdown()
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        mt5.shutdown()
        return False


def test_manual_scenario():
    """Test with manual scenario (no position needed)."""
    print("\n" + "="*70)
    print("MANUAL SCENARIO TEST - No Position Required")
    print("="*70)
    
    # Simulate a LONG XAUUSD position
    print("\nSimulating: LONG XAUUSD position")
    print("Entry: 2650.00")
    print("Current SL: 2645.00 (5.0 risk)")
    print("Current Price: 2660.00 (+10 profit = +2.0R)")
    
    features = {
        "macd_hist": 0.5,
        "macd_hist_prev": 0.3,
        "macd_hist_prev2": 0.1,
        "range_current": 5.0,
        "range_median_20": 4.0,
        "volume_zscore": 1.2,
        "atr_5": 4.5,
        "atr_14": 4.0
    }
    
    result = calculate_trailing_stop(
        entry=2650.00,
        current_sl=2645.00,
        current_price=2660.00,
        direction="long",
        atr=4.0,
        features=features
    )
    
    print("\n" + "-"*70)
    print("RESULT:")
    print("-"*70)
    print(f"Unrealized R: {result.unrealized_r:.2f}R")
    print(f"Momentum: {result.momentum_state}")
    print(f"Trail Method: {result.trail_method}")
    print(f"Current SL: 2645.00")
    print(f"New SL: {result.new_sl:.2f}")
    print(f"Trailed: {result.trailed}")
    rationale_safe = result.rationale.encode('ascii', 'ignore').decode('ascii')
    print(f"Rationale: {rationale_safe}")
    
    if result.trailed:
        print(f"\n✅ SL improved by {result.new_sl - 2645.00:.2f} points")
    else:
        print(f"\n⏸️  No action taken")
    
    return True


if __name__ == "__main__":
    print("\n" + "="*70)
    print("TRAILING STOPS - LIVE TEST")
    print("="*70)
    
    # Try live test first
    success = test_trailing_with_live_position()
    
    # Always show manual scenario
    print("\n")
    test_manual_scenario()
    
    sys.exit(0 if success else 1)

