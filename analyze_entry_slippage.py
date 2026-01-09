"""
Analyze historical tick data to determine if entry was slippage or tolerance-triggered
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import json

def analyze_entry_slippage(symbol: str, execution_time: str, planned_entry: float, 
                          actual_entry: float, tolerance: float):
    """
    Analyze tick data around execution to determine slippage vs tolerance fill
    """
    
    print("=" * 80)
    print("ENTRY SLIPPAGE ANALYSIS")
    print("=" * 80)
    print()
    
    # Parse execution time
    try:
        exec_dt = datetime.fromisoformat(execution_time.replace('Z', '+00:00'))
        if exec_dt.tzinfo is None:
            exec_dt = exec_dt.replace(tzinfo=timezone.utc)
    except Exception as e:
        print(f"[ERROR] Could not parse execution time: {e}")
        return
    
    print(f"[EXECUTION DETAILS]")
    print(f"  Symbol: {symbol}")
    print(f"  Execution Time: {exec_dt.isoformat()}")
    print(f"  Planned Entry: ${planned_entry:.2f}")
    print(f"  Actual Entry: ${actual_entry:.2f}")
    print(f"  Tolerance: ±{tolerance:.2f}")
    print(f"  Difference: ${actual_entry - planned_entry:+.2f}")
    print()
    
    # Initialize MT5
    if not mt5.initialize():
        print(f"[ERROR] MT5 initialization failed: {mt5.last_error()}")
        return
    
    try:
        # Define time window: 2 minutes before to 1 minute after execution
        from_time = exec_dt - timedelta(minutes=2)
        to_time = exec_dt + timedelta(minutes=1)
        
        print(f"[FETCHING TICK DATA]")
        print(f"  Time Window: {from_time.isoformat()} to {to_time.isoformat()}")
        print(f"  (2 minutes before to 1 minute after execution)")
        print()
        
        # Get tick data
        ticks = mt5.copy_ticks_range(symbol, from_time, to_time, mt5.COPY_TICKS_ALL)
        
        if ticks is None or len(ticks) == 0:
            print(f"[ERROR] No tick data available for {symbol}")
            print(f"        Error: {mt5.last_error()}")
            return
        
        print(f"[TICK DATA RETRIEVED]")
        print(f"  Total ticks: {len(ticks)}")
        print()
        
        # Helper functions to access tick data (MT5 returns numpy structured arrays)
        def get_tick_time(tick):
            if hasattr(tick, 'time'):
                return tick.time
            elif hasattr(tick, 'dtype') and 'time' in tick.dtype.names:
                return tick['time']
            else:
                return tick[0] if isinstance(tick, (tuple, list)) else tick[0]
        
        def get_tick_bid(tick):
            if hasattr(tick, 'bid'):
                return tick.bid
            elif hasattr(tick, 'dtype') and 'bid' in tick.dtype.names:
                return tick['bid']
            else:
                return tick[1] if isinstance(tick, (tuple, list)) else tick[1]
        
        def get_tick_ask(tick):
            if hasattr(tick, 'ask'):
                return tick.ask
            elif hasattr(tick, 'dtype') and 'ask' in tick.dtype.names:
                return tick['ask']
            else:
                return tick[2] if isinstance(tick, (tuple, list)) else tick[2]
        
        # Analyze price movement
        print("=" * 80)
        print("PRICE MOVEMENT ANALYSIS")
        print("=" * 80)
        print()
        
        # Find closest tick to execution time
        exec_timestamp = exec_dt.timestamp()
        closest_tick_idx = None
        min_time_diff = float('inf')
        
        # MT5 ticks are numpy structured arrays with fields: time, bid, ask, last, volume, flags
        for i, tick in enumerate(ticks):
            tick_time = get_tick_time(tick)
            time_diff = abs(tick_time - exec_timestamp)
            if time_diff < min_time_diff:
                min_time_diff = time_diff
                closest_tick_idx = i
        
        closest_tick = ticks[closest_tick_idx] if closest_tick_idx is not None else None
        
        if closest_tick is not None:
            # Handle numpy structured array
            tick_time = get_tick_time(closest_tick)
            tick_bid = get_tick_bid(closest_tick)
            tick_ask = get_tick_ask(closest_tick)
            
            print(f"[TICK AT EXECUTION TIME]")
            print(f"  Time: {datetime.fromtimestamp(tick_time, tz=timezone.utc).isoformat()}")
            print(f"  Time difference: {min_time_diff:.2f} seconds")
            print(f"  Bid: ${tick_bid:.2f}")
            print(f"  Ask: ${tick_ask:.2f}")
            print(f"  Mid: ${(tick_bid + tick_ask) / 2:.2f}")
            print(f"  Spread: ${tick_ask - tick_bid:.2f}")
            print()
        
        # Analyze price range in tolerance window
        tolerance_lower = planned_entry - tolerance
        tolerance_upper = planned_entry + tolerance
        
        print(f"[TOLERANCE ZONE]")
        print(f"  Lower bound: ${tolerance_lower:.2f}")
        print(f"  Upper bound: ${tolerance_upper:.2f}")
        print(f"  Planned entry: ${planned_entry:.2f}")
        print()
        
        # Check if actual entry is within tolerance
        in_tolerance = tolerance_lower <= actual_entry <= tolerance_upper
        
        print(f"[TOLERANCE CHECK]")
        if in_tolerance:
            print(f"  [WITHIN TOLERANCE] Actual entry ${actual_entry:.2f} is within tolerance zone")
            print(f"                    This suggests tolerance-triggered execution")
        else:
            print(f"  [OUTSIDE TOLERANCE] Actual entry ${actual_entry:.2f} exceeds tolerance zone")
            print(f"                      This suggests true slippage")
        print()
        
        # Analyze price movement leading up to execution
        ticks_before = [t for t in ticks if get_tick_time(t) <= exec_timestamp]
        ticks_after = [t for t in ticks if get_tick_time(t) > exec_timestamp]
        
        if len(ticks_before) > 0:
            print(f"[PRICE MOVEMENT BEFORE EXECUTION]")
            first_tick = ticks_before[0]
            last_tick_before = ticks_before[-1]
            
            first_mid = (get_tick_bid(first_tick) + get_tick_ask(first_tick)) / 2
            last_mid_before = (get_tick_bid(last_tick_before) + get_tick_ask(last_tick_before)) / 2
            
            print(f"  First tick (2 min before): ${first_mid:.2f}")
            print(f"  Last tick before execution: ${last_mid_before:.2f}")
            print(f"  Price change: ${last_mid_before - first_mid:+.2f}")
            
            # Check for sudden jumps
            max_jump = 0
            jump_time = None
            prev_mid = first_mid
            
            for tick in ticks_before[1:]:
                mid = (get_tick_bid(tick) + get_tick_ask(tick)) / 2
                jump = abs(mid - prev_mid)
                if jump > max_jump:
                    max_jump = jump
                    jump_time = datetime.fromtimestamp(get_tick_time(tick), tz=timezone.utc)
                prev_mid = mid
            
            print(f"  Maximum single-tick jump: ${max_jump:.2f}")
            if jump_time and max_jump > 2.0:  # More than 2 points
                print(f"  [WARNING] Large jump detected at {jump_time.isoformat()}")
            print()
        
        # Analyze volatility around execution
        if len(ticks_before) > 10:
            print(f"[VOLATILITY ANALYSIS]")
            mids = [(get_tick_bid(t) + get_tick_ask(t)) / 2 for t in ticks_before[-30:]]  # Last 30 ticks
            
            if len(mids) > 1:
                price_range = max(mids) - min(mids)
                avg_price = sum(mids) / len(mids)
                volatility_pct = (price_range / avg_price) * 100 if avg_price > 0 else 0
                
                print(f"  Price range (last 30 ticks): ${price_range:.2f}")
                print(f"  Volatility: {volatility_pct:.2f}%")
                
                if volatility_pct > 0.1:  # More than 0.1%
                    print(f"  [HIGH VOLATILITY] Elevated volatility detected")
                print()
        
        # Check if price jumped over planned entry
        print(f"[SLIPPAGE DETECTION]")
        if closest_tick is not None:
            tick_ask = get_tick_ask(closest_tick)
            tick_bid = get_tick_bid(closest_tick)
            mid_at_exec = (tick_bid + tick_ask) / 2
            
            # Check if ask (entry price for BUY) was above planned entry
            if tick_ask > planned_entry + 1.0:  # More than 1 point above
                slippage_amount = tick_ask - planned_entry
                print(f"  [SLIPPAGE DETECTED] Ask price ${tick_ask:.2f} was ${slippage_amount:.2f} above planned entry")
                print(f"                    Market likely jumped over entry level")
            elif tick_ask <= planned_entry + tolerance:
                print(f"  [WITHIN TOLERANCE] Ask price ${tick_ask:.2f} was within tolerance zone")
                print(f"                    Execution triggered by tolerance, not slippage")
            else:
                print(f"  [MARGINAL] Ask price ${tick_ask:.2f} slightly above planned entry")
        print()
        
        # Summary
        print("=" * 80)
        print("CONCLUSION")
        print("=" * 80)
        print()
        
        if in_tolerance:
            print("[TOLERANCE-TRIGGERED EXECUTION]")
            print("  The actual entry price is within the tolerance zone.")
            print("  This was likely a tolerance-based execution, not true slippage.")
            print("  However, the tolerance may have been too wide for this volatility regime.")
        else:
            print("[TRUE SLIPPAGE DETECTED]")
            print("  The actual entry price exceeds the tolerance zone.")
            print("  This indicates true slippage - market jumped over the intended entry.")
            print("  Possible causes:")
            print("    - High volatility (RMAG > 2.5σ)")
            print("    - Thin liquidity at execution time")
            print("    - Fast price movement")
            print("    - News event or order flow imbalance")
        
        print()
        print("[RECOMMENDATIONS]")
        if actual_entry > planned_entry + tolerance:
            print("  1. Reduce tolerance for XAUUSDc (current: ±50, suggest: ±5-10)")
            print("  2. Add max_slippage check to reject fills > threshold")
            print("  3. Avoid execution during high volatility periods (RMAG > 2σ)")
            print("  4. Consider limit orders instead of market orders")
        else:
            print("  1. Tolerance zone may be too wide for current volatility")
            print("  2. Consider tightening tolerance to ±5-10 points")
            print("  3. Monitor RMAG before plan creation")
            print("  4. Add volatility-based tolerance adjustment")
        print()
        
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    # Plan chatgpt_b3bebd76 details
    symbol = "XAUUSDc"
    execution_time = "2026-01-07T20:22:43.543414+00:00"
    planned_entry = 4452.00
    actual_entry = 4460.41  # User reported
    tolerance = 50.0  # From conditions
    
    analyze_entry_slippage(symbol, execution_time, planned_entry, actual_entry, tolerance)
