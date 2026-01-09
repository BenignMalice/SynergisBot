# BB Retest Price History Tracking Implementation

**Purpose**: Explain how to implement price history tracking for `bb_retest` condition

---

## Overview

For `bb_retest` to work, you need to track:
1. **Initial BB Break**: When price first broke above/below a Bollinger Band
2. **BB Level**: Which BB level was broken (upper or lower)
3. **Retest Event**: When price returns to that same BB level
4. **Bounce/Rejection**: Price moves away from BB after retest

---

## Implementation Approaches

### **Approach 1: On-the-Fly Calculation (Simpler, Recommended)**

Calculate everything from recent candles each time the condition is checked. No persistent tracking needed.

**Pros**:
- ✅ Simple to implement
- ✅ No state management
- ✅ Always uses fresh data
- ✅ No memory overhead

**Cons**:
- ⚠️ Slightly more computation per check
- ⚠️ May miss breaks that happened many candles ago

**Best For**: Most use cases where you check recent history (last 20-50 candles)

---

### **Approach 2: In-Memory Cache (More Efficient)**

Store BB break events in memory cache, similar to existing `_breakout_cache` pattern.

**Pros**:
- ✅ More efficient (don't recalculate every time)
- ✅ Can track breaks over longer periods
- ✅ Better for multiple plans checking same symbol

**Cons**:
- ⚠️ Requires state management
- ⚠️ Need cache invalidation logic
- ⚠️ Memory overhead

**Best For**: High-frequency checking or tracking breaks over extended periods

---

## Recommended Implementation: On-the-Fly Calculation

### Step 1: Fetch Recent Candles

```python
# In auto_execution_system.py::_check_conditions()
# After existing bb_expansion check (around line 5204)

if plan.conditions.get("bb_retest"):
    try:
        # Get timeframe from conditions
        bb_tf = plan.conditions.get("timeframe", "M15")
        
        # Fetch enough candles to detect break and retest
        # Need: ~20 candles for BB calculation + ~10-20 more for break detection
        bb_candles = _get_recent_candles(symbol_norm, timeframe=bb_tf, count=50)
        bb_candles = _normalize_candles(bb_candles)
        
        if not bb_candles or len(bb_candles) < 30:
            logger.debug(f"Insufficient candles for BB retest check")
            return False
```

### Step 2: Calculate Bollinger Bands for Each Candle

```python
        # Calculate BB for each candle in history
        # This gives us BB levels at each point in time
        bb_history = []
        
        for i in range(20, len(bb_candles)):  # Start from candle 20 (need 20 for BB calc)
            # Get last 20 candles up to this point
            window_candles = bb_candles[i-19:i+1]  # 20 candles ending at i
            
            closes = [c['close'] if isinstance(c, dict) else c.close 
                     for c in window_candles]
            
            # Calculate BB
            sma = sum(closes) / len(closes)
            std_dev = (sum((c - sma) ** 2 for c in closes) / len(closes)) ** 0.5
            
            bb_upper = sma + (std_dev * 2)
            bb_lower = sma - (std_dev * 2)
            
            # Get current candle price
            current_candle = bb_candles[i]
            current_high = current_candle['high'] if isinstance(current_candle, dict) else current_candle.high
            current_low = current_candle['low'] if isinstance(current_candle, dict) else current_candle.low
            current_close = current_candle['close'] if isinstance(current_candle, dict) else current_candle.close
            
            bb_history.append({
                'candle_idx': i,
                'bb_upper': bb_upper,
                'bb_lower': bb_lower,
                'bb_middle': sma,
                'high': current_high,
                'low': current_low,
                'close': current_close
            })
```

### Step 3: Detect Initial BB Break

```python
        # Look for initial break (going backwards from recent to past)
        # Find most recent break that hasn't been retested yet
        initial_break = None
        break_direction = None  # "bullish" (broke above upper) or "bearish" (broke below lower)
        
        # Look back through history (excluding most recent 2-3 candles for retest detection)
        for i in range(len(bb_history) - 3, 10, -1):  # Start from 3 candles ago, go back to candle 10
            bb_data = bb_history[i]
            prev_bb_data = bb_history[i-1] if i > 0 else None
            
            if not prev_bb_data:
                continue
            
            # Check for bullish break (price broke above upper BB)
            if bb_data['high'] > bb_data['bb_upper'] and prev_bb_data['high'] <= prev_bb_data['bb_upper']:
                # Price just broke above upper BB
                initial_break = {
                    'candle_idx': i,
                    'bb_level': bb_data['bb_upper'],
                    'break_price': bb_data['high'],
                    'direction': 'bullish'
                }
                break_direction = 'bullish'
                break
            
            # Check for bearish break (price broke below lower BB)
            elif bb_data['low'] < bb_data['bb_lower'] and prev_bb_data['low'] >= prev_bb_data['bb_lower']:
                # Price just broke below lower BB
                initial_break = {
                    'candle_idx': i,
                    'bb_level': bb_data['bb_lower'],
                    'break_price': bb_data['low'],
                    'direction': 'bearish'
                }
                break_direction = 'bearish'
                break
        
        if not initial_break:
            logger.debug(f"BB retest: No initial break detected in recent history")
            return False
```

### Step 4: Detect Retest

```python
        # Check if price is now retesting the broken BB level
        # Look at recent candles (last 2-3) to see if price is near the break level
        current_bb_data = bb_history[-1]  # Most recent
        recent_bb_data = bb_history[-3:]   # Last 3 candles
        
        retest_detected = False
        retest_tolerance = plan.conditions.get("bb_retest_tolerance", 0.5)  # 0.5% tolerance
        
        for recent_data in recent_bb_data:
            if break_direction == 'bullish':
                # Retesting upper BB after bullish break
                # Price should be near or touching upper BB
                bb_level = recent_data['bb_upper']
                price_distance = abs(recent_data['close'] - bb_level) / bb_level * 100
                
                if price_distance <= retest_tolerance:
                    # Price is retesting upper BB
                    retest_detected = True
                    logger.debug(f"BB retest: Bullish break detected, now retesting upper BB at {bb_level:.2f}")
                    break
            
            elif break_direction == 'bearish':
                # Retesting lower BB after bearish break
                # Price should be near or touching lower BB
                bb_level = recent_data['bb_lower']
                price_distance = abs(recent_data['close'] - bb_level) / bb_level * 100
                
                if price_distance <= retest_tolerance:
                    # Price is retesting lower BB
                    retest_detected = True
                    logger.debug(f"BB retest: Bearish break detected, now retesting lower BB at {bb_level:.2f}")
                    break
        
        if not retest_detected:
            logger.debug(f"BB retest: Initial break found but no retest detected yet")
            return False
```

### Step 5: Verify Bounce/Rejection

```python
        # Verify that price bounces/rejects from BB (moves away after retest)
        # For bullish retest: Price should move down from upper BB
        # For bearish retest: Price should move up from lower BB
        
        current_data = bb_history[-1]
        prev_data = bb_history[-2] if len(bb_history) >= 2 else None
        
        if not prev_data:
            return False
        
        bounce_detected = False
        
        if break_direction == 'bullish':
            # After retesting upper BB, price should move down (rejection)
            if current_data['close'] < prev_data['close']:
                # Price moving down = rejection = bounce detected
                bounce_detected = True
                logger.info(f"BB retest: Bullish break → retest → rejection confirmed")
        
        elif break_direction == 'bearish':
            # After retesting lower BB, price should move up (bounce)
            if current_data['close'] > prev_data['close']:
                # Price moving up = bounce = bounce detected
                bounce_detected = True
                logger.info(f"BB retest: Bearish break → retest → bounce confirmed")
        
        if not bounce_detected:
            logger.debug(f"BB retest: Retest detected but no bounce/rejection yet")
            return False
        
        # All conditions met: Break → Retest → Bounce
        logger.info(f"BB retest condition met: {break_direction} break, retest, and bounce confirmed")
        return True
```

---

## Alternative: In-Memory Cache Approach

If you want to track breaks over longer periods or share state across multiple plans:

### Step 1: Add Cache to AutoExecutionSystem

```python
# In __init__ method
self._bb_break_cache: Dict[str, Dict[str, Optional[Dict]]] = {}
# Structure: {symbol: {timeframe: {break_info: {...}}}}
```

### Step 2: Detect and Cache Breaks

```python
# When checking bb_expansion or in separate method
def _detect_and_cache_bb_break(self, symbol: str, timeframe: str):
    """Detect BB break and cache it for retest detection"""
    
    # Calculate BB and check for break (similar to above)
    # ...
    
    if break_detected:
        cache_key = f"{symbol}_{timeframe}"
        if symbol not in self._bb_break_cache:
            self._bb_break_cache[symbol] = {}
        
        self._bb_break_cache[symbol][timeframe] = {
            'break_timestamp': datetime.now(timezone.utc),
            'bb_level': bb_level,
            'break_price': break_price,
            'direction': break_direction
        }
```

### Step 3: Check Cache for Retest

```python
# In bb_retest condition check
if plan.conditions.get("bb_retest"):
    cache_key = f"{symbol_norm}_{bb_tf}"
    cached_break = self._bb_break_cache.get(symbol_norm, {}).get(bb_tf)
    
    if not cached_break:
        logger.debug("No cached BB break found")
        return False
    
    # Check if price is retesting cached break level
    current_price = get_current_price(symbol_norm)
    cached_level = cached_break['bb_level']
    
    if abs(current_price - cached_level) / cached_level * 100 <= retest_tolerance:
        # Retest detected
        # Verify bounce...
        return True
```

### Step 4: Cache Invalidation

```python
# Invalidate cache when:
# 1. Retest completes (bounce confirmed)
# 2. Break expires (too old, e.g., > 24 hours)
# 3. Price moves too far from break level

def _invalidate_bb_break_cache(self, symbol: str, timeframe: str):
    """Invalidate cached break (after retest or expiration)"""
    if symbol in self._bb_break_cache:
        if timeframe in self._bb_break_cache[symbol]:
            del self._bb_break_cache[symbol][timeframe]
```

---

## Key Design Decisions

### 1. **Lookback Period**
- **On-the-fly**: Last 30-50 candles (sufficient for most cases)
- **Cache**: Can track breaks over hours/days

### 2. **Retest Tolerance**
- Default: 0.5% of BB level
- Configurable via `bb_retest_tolerance` in plan conditions

### 3. **Bounce Confirmation**
- **Simple**: Price moves away from BB (opposite direction)
- **Strict**: Require rejection candle (long wick, closes away from BB)

### 4. **Break Detection Window**
- **Recent**: Only detect breaks in last 20-30 candles
- **Extended**: Track breaks over longer periods (requires cache)

---

## Integration with Existing Code

### Location in `auto_execution_system.py`

Add after existing `bb_expansion` check (around line 5204):

```python
# After bb_expansion check (line 5204)

# Check BB retest condition
if plan.conditions.get("bb_retest"):
    # Implementation here (on-the-fly or cache-based)
    # ...
```

### Reuse Existing Functions

- `_get_recent_candles()` - Already exists, fetches candles
- `_normalize_candles()` - Already exists, normalizes candle format
- BB calculation logic - Similar to `bb_expansion` (lines 5184-5191)

---

## Performance Considerations

### On-the-Fly Approach
- **CPU**: ~5-10ms per check (calculates BB for ~30 candles)
- **Memory**: Minimal (no persistent state)
- **Accuracy**: Good for recent breaks (last 30-50 candles)

### Cache Approach
- **CPU**: ~1-2ms per check (just reads cache)
- **Memory**: ~100 bytes per symbol/timeframe
- **Accuracy**: Can track breaks over extended periods

**Recommendation**: Start with **on-the-fly** approach (simpler), add cache later if needed for performance.

---

## Example Usage

```python
# Plan conditions
{
    "bb_retest": true,
    "timeframe": "M15",
    "bb_retest_tolerance": 0.5,  # 0.5% tolerance
    "price_near": 91500.0,
    "tolerance": 100.0
}
```

**Execution Flow**:
1. System checks for BB break in last 30 candles
2. Finds bullish break (price broke above upper BB 10 candles ago)
3. Checks if price is now retesting upper BB (within 0.5%)
4. Verifies bounce (price moving down from upper BB)
5. If all conditions met → Execute trade

---

## Summary

**Recommended Implementation**: **On-the-fly calculation**

- ✅ Simple to implement
- ✅ No state management
- ✅ Reuses existing BB calculation logic
- ✅ Sufficient for most use cases (recent breaks)

**When to Use Cache**:
- Multiple plans checking same symbol/timeframe
- Need to track breaks over extended periods (>50 candles)
- High-frequency checking (every 5 seconds)

The on-the-fly approach calculates BB history from recent candles each check, detects the initial break, verifies retest, and confirms bounce - all without persistent state.

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-07

