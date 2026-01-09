# Volatility Tracking Architecture

**Date**: 2025-12-07  
**Purpose**: Design document for tracking ATR slope, wick variance, and time since breakout

---

## 📊 OVERVIEW

This document explains how the system will track:
1. **ATR Slope/Trend** - Rate of change of ATR over time
2. **Wick Variance** - Rolling variance of wick-to-body ratios
3. **Time Since Breakout** - Timestamp tracking for breakout events

---

## 🏗️ ARCHITECTURE DESIGN

### Design Principles

1. **In-Memory First**: Fast access for real-time calculations
2. **Rolling Windows**: Use `deque` with `maxlen` for automatic cleanup
3. **On-Demand Calculation**: Calculate from recent candles when needed
4. **Persistent Storage**: Store key events (breakouts) in SQLite for persistence
5. **ChatGPT Access**: Expose via `analyse_symbol_full` response

---

## 📈 1. ATR SLOPE/TREND TRACKING

### Data Structure

**In-Memory Storage** (per symbol, per timeframe):
```python
# In RegimeDetector class
self._atr_history: Dict[str, Dict[str, deque]] = {
    "BTCUSDc": {
        "M5": deque(maxlen=20),   # Last 20 ATR(14) values
        "M15": deque(maxlen=20),
        "H1": deque(maxlen=20)
    }
}

# Each deque entry: (timestamp, atr_14_value, atr_50_value)
# Example: (datetime(2025, 12, 7, 10, 0), 150.5, 125.3)
```

### Calculation Method

**On-Demand Calculation** (no pre-calculation needed):
```python
def _calculate_atr_trend(
    self,
    symbol: str,
    timeframe: str,
    current_atr_14: float,
    current_atr_50: float,
    current_time: datetime
) -> Dict[str, float]:
    """
    Calculate ATR trend from recent history.
    
    Returns:
        {
            "current_atr": float,
            "slope": float,  # Rate of change per period
            "slope_pct": float,  # % change per period
            "is_declining": bool,
            "is_above_baseline": bool,
            "trend_direction": str  # "rising", "declining", "stable"
        }
    """
    
    # Get history for this symbol/timeframe
    history = self._atr_history.get(symbol, {}).get(timeframe, deque())
    
    # Add current value to history
    history.append((current_time, current_atr_14, current_atr_50))
    
    # Calculate slope if we have enough data (need at least 5 points)
    if len(history) < 5:
        return {
            "current_atr": current_atr_14,
            "slope": 0.0,
            "slope_pct": 0.0,
            "is_declining": False,
            "is_above_baseline": current_atr_14 / current_atr_50 > 1.2,
            "trend_direction": "insufficient_data"
        }
    
    # Extract ATR values and timestamps
    atr_values = [atr for _, atr, _ in list(history)]
    timestamps = [ts for ts, _, _ in list(history)]
    
    # Calculate slope using linear regression (last 5 points)
    recent_atr = atr_values[-5:]
    recent_times = [(ts - timestamps[-5]).total_seconds() / 60 for ts in timestamps[-5:]]
    
    # Simple linear regression: slope = (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)
    n = len(recent_atr)
    x = list(range(n))  # Time indices (0, 1, 2, 3, 4)
    y = recent_atr
    
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(x[i] * y[i] for i in range(n))
    sum_x2 = sum(x[i] ** 2 for i in range(n))
    
    if (n * sum_x2 - sum_x ** 2) != 0:
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
    else:
        slope = 0.0
    
    # Calculate percentage change per period
    if recent_atr[0] > 0:
        slope_pct = (slope / recent_atr[0]) * 100
    else:
        slope_pct = 0.0
    
    # Determine trend direction
    if slope_pct < -5.0:  # Declining > 5% per period
        trend_direction = "declining"
        is_declining = True
    elif slope_pct > 5.0:  # Rising > 5% per period
        trend_direction = "rising"
        is_declining = False
    else:
        trend_direction = "stable"
        is_declining = False
    
    # Check if above baseline
    is_above_baseline = current_atr_14 / current_atr_50 > 1.2
    
    return {
        "current_atr": current_atr_14,
        "slope": slope,
        "slope_pct": slope_pct,
        "is_declining": is_declining,
        "is_above_baseline": is_above_baseline,
        "trend_direction": trend_direction
    }
```

### When It's Calculated

**Trigger**: Every time `detect_regime()` is called
- Calculated on-demand from recent candle data
- Stored in rolling deque (auto-cleanup after 20 values)
- No database writes needed (calculated from live data)

### Storage Location

**Memory Only**:
- `self._atr_history[symbol][timeframe]` - Rolling deque
- Persists only while `RegimeDetector` instance is alive
- Lost on restart (recalculated from fresh candles)

**Optional Persistence** (if needed):
- Could store in `data/volatility_regime_events.sqlite` (existing database)
- Table: `atr_history` (symbol, timeframe, timestamp, atr_14, atr_50)
- Only if we need historical analysis across restarts

---

## 📊 2. WICK VARIANCE TRACKING

### Data Structure

**In-Memory Storage** (per symbol, per timeframe):
```python
# In RegimeDetector class
self._wick_ratios_history: Dict[str, Dict[str, deque]] = {
    "BTCUSDc": {
        "M5": deque(maxlen=20),   # Last 20 wick-to-body ratios
        "M15": deque(maxlen=20),
        "H1": deque(maxlen=20)
    }
}

# Each deque entry: (timestamp, wick_ratio)
# wick_ratio = max(upper_wick, lower_wick) / body_size
# Example: (datetime(2025, 12, 7, 10, 0), 1.85)
```

### Calculation Method

**Step 1: Calculate Wick Ratio for Each Candle**:
```python
def _calculate_wick_ratio(self, candle: Dict[str, float]) -> float:
    """
    Calculate wick-to-body ratio for a single candle.
    
    Args:
        candle: Dict with 'open', 'high', 'low', 'close'
    
    Returns:
        wick_ratio: max(upper_wick, lower_wick) / body_size
    """
    open_price = candle['open']
    high = candle['high']
    low = candle['low']
    close = candle['close']
    
    body_size = abs(close - open_price)
    upper_wick = high - max(open_price, close)
    lower_wick = min(open_price, close) - low
    
    max_wick = max(upper_wick, lower_wick)
    
    if body_size > 0:
        return max_wick / body_size
    else:
        return 0.0  # Doji candle
```

**Step 2: Calculate Rolling Variance**:
```python
def _calculate_wick_variance(
    self,
    symbol: str,
    timeframe: str,
    current_candle: Dict[str, float],
    current_time: datetime
) -> Dict[str, float]:
    """
    Calculate rolling variance of wick-to-body ratios.
    
    Returns:
        {
            "current_variance": float,
            "previous_variance": float,
            "variance_change_pct": float,
            "is_increasing": bool,
            "current_ratio": float,
            "mean_ratio": float
        }
    """
    import numpy as np
    
    # Calculate current wick ratio
    current_ratio = self._calculate_wick_ratio(current_candle)
    
    # Get history
    history = self._wick_ratios_history.get(symbol, {}).get(timeframe, deque())
    
    # Add current ratio to history
    history.append((current_time, current_ratio))
    
    # Need at least 10 values for meaningful variance
    if len(history) < 10:
        return {
            "current_variance": 0.0,
            "previous_variance": 0.0,
            "variance_change_pct": 0.0,
            "is_increasing": False,
            "current_ratio": current_ratio,
            "mean_ratio": current_ratio
        }
    
    # Extract ratios
    ratios = [ratio for _, ratio in list(history)]
    
    # Calculate current variance (last 10 values)
    current_window = ratios[-10:]
    current_variance = np.var(current_window)
    
    # Calculate previous variance (previous 10 values, if available)
    if len(ratios) >= 20:
        previous_window = ratios[-20:-10]
        previous_variance = np.var(previous_window)
    else:
        previous_variance = current_variance  # Use current as baseline
    
    # Calculate percentage change
    if previous_variance > 0:
        variance_change_pct = ((current_variance - previous_variance) / previous_variance) * 100
    else:
        variance_change_pct = 0.0
    
    # Determine if increasing (30%+ increase threshold)
    is_increasing = variance_change_pct >= 30.0
    
    return {
        "current_variance": current_variance,
        "previous_variance": previous_variance,
        "variance_change_pct": variance_change_pct,
        "is_increasing": is_increasing,
        "current_ratio": current_ratio,
        "mean_ratio": np.mean(current_window)
    }
```

### When It's Calculated

**Trigger**: Every time `detect_regime()` is called
- Calculated from recent candles (last 20 candles)
- Stored in rolling deque
- Variance calculated from last 10 wick ratios

### Storage Location

**Memory Only**:
- `self._wick_ratios_history[symbol][timeframe]` - Rolling deque
- Auto-cleanup after 20 values
- Recalculated from fresh candles on restart

---

## ⏱️ 3. TIME SINCE BREAKOUT TRACKING

### Data Structure

**Persistent Storage** (SQLite database):
```sql
-- Table: breakout_events
CREATE TABLE IF NOT EXISTS breakout_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    breakout_type TEXT NOT NULL,  -- "BOS_BULL", "BOS_BEAR", "CHOCH_BULL", "CHOCH_BEAR", "PRICE_BREAKOUT"
    breakout_price REAL NOT NULL,
    breakout_timestamp TEXT NOT NULL,  -- ISO format
    is_active INTEGER DEFAULT 1,  -- 1 = active, 0 = invalidated
    invalidated_at TEXT,  -- When breakout was invalidated
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_breakout_symbol_timeframe ON breakout_events(symbol, timeframe, is_active);
CREATE INDEX idx_breakout_timestamp ON breakout_events(breakout_timestamp);
```

**In-Memory Cache** (for fast access):
```python
# In RegimeDetector class
self._breakout_cache: Dict[str, Dict[str, Optional[Dict]]] = {
    "BTCUSDc": {
        "M5": {
            "last_breakout": {
                "type": "BOS_BULL",
                "price": 90000.0,
                "timestamp": datetime(2025, 12, 7, 10, 0),
                "time_since_minutes": 15
            }
        },
        "M15": None,  # No recent breakout
        "H1": None
    }
}
```

### Breakout Detection Integration

**Option 1: Integrate with Existing Structure Detection**:
```python
# In desktop_agent.py or structure detection system
def _detect_and_record_breakout(
    self,
    symbol: str,
    timeframe: str,
    structure_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Detect breakout and record to database.
    
    Returns:
        {
            "breakout_id": int,
            "type": str,
            "price": float,
            "timestamp": datetime
        } or None
    """
    # Check for BOS/CHOCH/Price breakout
    if structure_data.get("bos_bull") or structure_data.get("choch_bull"):
        breakout_type = "BOS_BULL" if structure_data.get("bos_bull") else "CHOCH_BULL"
        breakout_price = structure_data.get("price", 0.0)
        
        # Record to database
        breakout_id = self._save_breakout_event(
            symbol=symbol,
            timeframe=timeframe,
            breakout_type=breakout_type,
            breakout_price=breakout_price
        )
        
        # Update cache
        self._update_breakout_cache(symbol, timeframe, {
            "type": breakout_type,
            "price": breakout_price,
            "timestamp": datetime.now(),
            "breakout_id": breakout_id
        })
        
        return {
            "breakout_id": breakout_id,
            "type": breakout_type,
            "price": breakout_price,
            "timestamp": datetime.now()
        }
    
    return None
```

**Option 2: Detect from Price Action**:
```python
def _detect_price_breakout(
    self,
    symbol: str,
    timeframe: str,
    current_price: float,
    resistance_level: float,
    support_level: float
) -> Optional[Dict[str, Any]]:
    """
    Detect price breakout above resistance or below support.
    """
    # Breakout above resistance
    if current_price > resistance_level * 1.001:  # 0.1% buffer
        return self._record_breakout(
            symbol, timeframe, "PRICE_BREAKOUT_UP",
            current_price, resistance_level
        )
    
    # Breakout below support
    if current_price < support_level * 0.999:  # 0.1% buffer
        return self._record_breakout(
            symbol, timeframe, "PRICE_BREAKOUT_DOWN",
            current_price, support_level
        )
    
    return None
```

### Time Since Breakout Calculation

```python
def _get_time_since_breakout(
    self,
    symbol: str,
    timeframe: str,
    current_time: datetime
) -> Optional[Dict[str, Any]]:
    """
    Get time since last breakout.
    
    Returns:
        {
            "time_since_minutes": float,
            "time_since_hours": float,
            "breakout_type": str,
            "breakout_price": float,
            "breakout_timestamp": datetime,
            "is_recent": bool  # < 30 minutes
        } or None
    """
    # Check cache first
    cache_entry = self._breakout_cache.get(symbol, {}).get(timeframe)
    if cache_entry and cache_entry.get("last_breakout"):
        breakout = cache_entry["last_breakout"]
        breakout_time = breakout["timestamp"]
        
        # Calculate time difference
        time_diff = current_time - breakout_time
        time_since_minutes = time_diff.total_seconds() / 60
        time_since_hours = time_since_minutes / 60
        
        return {
            "time_since_minutes": time_since_minutes,
            "time_since_hours": time_since_hours,
            "breakout_type": breakout["type"],
            "breakout_price": breakout["price"],
            "breakout_timestamp": breakout_time,
            "is_recent": time_since_minutes < 30
        }
    
    # Fallback: Query database
    return self._query_breakout_from_db(symbol, timeframe, current_time)
```

### Database Operations

```python
def _save_breakout_event(
    self,
    symbol: str,
    timeframe: str,
    breakout_type: str,
    breakout_price: float
) -> int:
    """Save breakout event to database."""
    import sqlite3
    from datetime import datetime
    
    db_path = "data/volatility_regime_events.sqlite"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Invalidate previous active breakouts for this symbol/timeframe
    cursor.execute("""
        UPDATE breakout_events
        SET is_active = 0, invalidated_at = ?
        WHERE symbol = ? AND timeframe = ? AND is_active = 1
    """, (datetime.now().isoformat(), symbol, timeframe))
    
    # Insert new breakout
    cursor.execute("""
        INSERT INTO breakout_events 
        (symbol, timeframe, breakout_type, breakout_price, breakout_timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (symbol, timeframe, breakout_type, breakout_price, datetime.now().isoformat()))
    
    breakout_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return breakout_id

def _query_breakout_from_db(
    self,
    symbol: str,
    timeframe: str,
    current_time: datetime
) -> Optional[Dict[str, Any]]:
    """Query most recent active breakout from database."""
    import sqlite3
    from datetime import datetime
    
    db_path = "data/volatility_regime_events.sqlite"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT breakout_type, breakout_price, breakout_timestamp
        FROM breakout_events
        WHERE symbol = ? AND timeframe = ? AND is_active = 1
        ORDER BY breakout_timestamp DESC
        LIMIT 1
    """, (symbol, timeframe))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        breakout_type, breakout_price, breakout_timestamp_str = row
        breakout_timestamp = datetime.fromisoformat(breakout_timestamp_str)
        
        time_diff = current_time - breakout_timestamp
        time_since_minutes = time_diff.total_seconds() / 60
        
        return {
            "time_since_minutes": time_since_minutes,
            "time_since_hours": time_since_minutes / 60,
            "breakout_type": breakout_type,
            "breakout_price": breakout_price,
            "breakout_timestamp": breakout_timestamp,
            "is_recent": time_since_minutes < 30
        }
    
    return None
```

### When Breakouts Are Detected

**Integration Points**:
1. **Structure Detection**: When BOS/CHOCH detected in `tool_analyse_symbol_full()`
2. **Price Action**: When price breaks above/below key levels
3. **Auto-Execution**: When breakout plan executes (confirms breakout occurred)

**Trigger Locations**:
- `desktop_agent.py` → `tool_analyse_symbol_full()` (after structure analysis)
- `infra/detection_systems.py` → Structure detection methods
- `handlers/auto_execution_handler.py` → When breakout plan executes

---

## 🔄 DATA FLOW

### Calculation Flow

```
1. tool_analyse_symbol_full() called
   ↓
2. Fetch recent candles (M5, M15, H1)
   ↓
3. Calculate indicators (ATR, BB, ADX, etc.)
   ↓
4. Call regime_detector.detect_regime()
   ↓
5. Inside detect_regime():
   a. Calculate ATR trend (from recent ATR history)
   b. Calculate wick variance (from recent wick ratios)
   c. Get time since breakout (from database/cache)
   ↓
6. Use calculated values for volatility state detection
   ↓
7. Return in response with all metrics
```

### Storage Flow

**ATR History**:
```
Every detect_regime() call:
  → Calculate ATR(14) from candles
  → Add to self._atr_history[symbol][timeframe] deque
  → Calculate slope from last 5-10 values
  → Use for POST_BREAKOUT_DECAY detection
```

**Wick Variance**:
```
Every detect_regime() call:
  → Calculate wick ratio for each recent candle
  → Add to self._wick_ratios_history[symbol][timeframe] deque
  → Calculate variance from last 10 ratios
  → Compare to previous variance
  → Use for PRE_BREAKOUT_TENSION detection
```

**Breakout Events**:
```
When breakout detected:
  → Save to SQLite database (breakout_events table)
  → Update in-memory cache
  → Query on-demand for time_since_breakout
  → Use for POST_BREAKOUT_DECAY detection
```

---

## 💾 PERSISTENCE STRATEGY

### In-Memory (Fast, Temporary)

**ATR History**:
- Stored in `deque(maxlen=20)` per symbol/timeframe
- Lost on restart (recalculated from fresh candles)
- **Why**: ATR can be recalculated from candles, no need to persist

**Wick Ratios**:
- Stored in `deque(maxlen=20)` per symbol/timeframe
- Lost on restart (recalculated from fresh candles)
- **Why**: Wick ratios can be recalculated from candles

### Persistent (SQLite Database)

**Breakout Events**:
- Stored in `data/volatility_regime_events.sqlite`
- Table: `breakout_events`
- Persists across restarts
- **Why**: Breakout events are discrete events that need historical tracking

**Database Schema**:
```sql
-- Existing database: data/volatility_regime_events.sqlite
-- Add new table:

CREATE TABLE IF NOT EXISTS breakout_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    breakout_type TEXT NOT NULL,
    breakout_price REAL NOT NULL,
    breakout_timestamp TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    invalidated_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_breakout_symbol_timeframe ON breakout_events(symbol, timeframe, is_active);
CREATE INDEX idx_breakout_timestamp ON breakout_events(breakout_timestamp);
```

---

## 🔌 CHATGPT ACCESS

### Via `moneybot.analyse_symbol_full`

**Response Structure**:
```python
{
    "summary": "...",
    "data": {
        "volatility_metrics": {
            "regime": "POST_BREAKOUT_DECAY",
            "confidence": 85.5,
            "atr_ratio": 1.35,
            "bb_width_ratio": 1.6,
            
            # NEW METRICS
            "atr_trend": {
                "current_atr": 150.5,
                "slope": -2.3,  # Declining
                "slope_pct": -1.5,  # -1.5% per period
                "is_declining": True,
                "is_above_baseline": True,
                "trend_direction": "declining"
            },
            "wick_variance": {
                "current_variance": 0.45,
                "previous_variance": 0.32,
                "variance_change_pct": 40.6,  # 40.6% increase
                "is_increasing": True,
                "current_ratio": 1.85,
                "mean_ratio": 1.42
            },
            "time_since_breakout": {
                "time_since_minutes": 18.5,
                "time_since_hours": 0.31,
                "breakout_type": "BOS_BULL",
                "breakout_price": 90000.0,
                "breakout_timestamp": "2025-12-07T10:00:00Z",
                "is_recent": True  # < 30 minutes
            }
        }
    }
}
```

### ChatGPT Usage

**Example 1: POST_BREAKOUT_DECAY Detection**:
```python
# ChatGPT receives analysis response
volatility_metrics = response["data"]["volatility_metrics"]

if volatility_metrics["atr_trend"]["is_declining"] and \
   volatility_metrics["atr_trend"]["is_above_baseline"] and \
   volatility_metrics["time_since_breakout"]["is_recent"]:
    
    # POST_BREAKOUT_DECAY detected
    # Recommend: mean_reversion_range_scalp, avoid trend continuation
```

**Example 2: PRE_BREAKOUT_TENSION Detection**:
```python
if volatility_metrics["wick_variance"]["is_increasing"] and \
   volatility_metrics["bb_width_ratio"] < 0.015:  # Narrow BB
    
    # PRE_BREAKOUT_TENSION detected
    # Recommend: breakout_ib_volatility_trap, liquidity_sweep_reversal
```

---

## 🛠️ IMPLEMENTATION DETAILS

### Initialization

**In `RegimeDetector.__init__()`**:
```python
def __init__(self):
    # Existing
    self._regime_history: Dict[str, List[Tuple[datetime, VolatilityRegime, float]]] = {}
    self._last_regime_change: Dict[str, datetime] = {}
    self._cooldown_until: Dict[str, datetime] = {}
    self._last_regime: Dict[str, VolatilityRegime] = {}
    
    # NEW: ATR history tracking
    self._atr_history: Dict[str, Dict[str, deque]] = {}
    
    # NEW: Wick ratios tracking
    self._wick_ratios_history: Dict[str, Dict[str, deque]] = {}
    
    # NEW: Breakout cache
    self._breakout_cache: Dict[str, Dict[str, Optional[Dict]]] = {}
    
    # NEW: Database connection (lazy initialization)
    self._db_path = "data/volatility_regime_events.sqlite"
    self._init_breakout_table()
```

### Database Initialization

```python
def _init_breakout_table(self):
    """Initialize breakout_events table if it doesn't exist."""
    import sqlite3
    import os
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    conn = sqlite3.connect(self._db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS breakout_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            breakout_type TEXT NOT NULL,
            breakout_price REAL NOT NULL,
            breakout_timestamp TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            invalidated_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_breakout_symbol_timeframe 
        ON breakout_events(symbol, timeframe, is_active)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_breakout_timestamp 
        ON breakout_events(breakout_timestamp)
    """)
    
    conn.commit()
    conn.close()
```

### Integration in `detect_regime()`

```python
def detect_regime(...) -> Dict[str, Any]:
    # ... existing code ...
    
    # NEW: Initialize tracking structures if needed
    if symbol not in self._atr_history:
        self._atr_history[symbol] = {
            "M5": deque(maxlen=20),
            "M15": deque(maxlen=20),
            "H1": deque(maxlen=20)
        }
    
    if symbol not in self._wick_ratios_history:
        self._wick_ratios_history[symbol] = {
            "M5": deque(maxlen=20),
            "M15": deque(maxlen=20),
            "H1": deque(maxlen=20)
        }
    
    # NEW: Calculate ATR trend for each timeframe
    atr_trends = {}
    for tf_name in ["M5", "M15", "H1"]:
        if tf_name in timeframe_data:
            tf_data = timeframe_data[tf_name]
            atr_14 = tf_data.get("atr_14")
            atr_50 = tf_data.get("atr_50")
            
            if atr_14 and atr_50:
                atr_trends[tf_name] = self._calculate_atr_trend(
                    symbol, tf_name, atr_14, atr_50, current_time
                )
    
    # NEW: Calculate wick variance for each timeframe
    wick_variances = {}
    for tf_name in ["M5", "M15", "H1"]:
        if tf_name in timeframe_data:
            tf_data = timeframe_data[tf_name]
            rates = tf_data.get("rates")
            
            if rates is not None and len(rates) > 0:
                # Get last candle
                last_candle = self._get_last_candle(rates)
                wick_variances[tf_name] = self._calculate_wick_variance(
                    symbol, tf_name, last_candle, current_time
                )
    
    # NEW: Get time since breakout
    time_since_breakout = {}
    for tf_name in ["M5", "M15", "H1"]:
        time_since_breakout[tf_name] = self._get_time_since_breakout(
            symbol, tf_name, current_time
        )
    
    # ... existing regime detection logic ...
    # Use atr_trends, wick_variances, time_since_breakout for new state detection
    
    # Return with new metrics
    return {
        "regime": regime,
        "confidence": confidence,
        "indicators": indicators,
        "reasoning": reasoning,
        "atr_ratio": composite_atr_ratio,
        "bb_width_ratio": composite_bb_width,
        "adx_composite": composite_adx,
        "volume_confirmed": volume_confirmed_composite,
        "timestamp": current_time.isoformat(),
        # NEW METRICS
        "atr_trends": atr_trends,
        "wick_variances": wick_variances,
        "time_since_breakout": time_since_breakout
    }
```

---

## 📊 PERFORMANCE CONSIDERATIONS

### Memory Usage

**Per Symbol**:
- ATR history: 20 values × 3 timeframes × 3 floats = ~720 bytes
- Wick ratios: 20 values × 3 timeframes × 2 floats = ~480 bytes
- Breakout cache: ~200 bytes
- **Total per symbol**: ~1.4 KB

**For 6 symbols**: ~8.4 KB (negligible)

### Database Size

**Breakout Events Table**:
- ~50 bytes per event
- ~100 events per symbol per day = 5 KB per symbol per day
- **For 6 symbols**: ~30 KB per day
- **30 days retention**: ~900 KB (negligible)

### Calculation Overhead

**ATR Trend**: O(n) where n=5 (linear regression on 5 points) - **Negligible**

**Wick Variance**: O(n) where n=10 (variance calculation) - **Negligible**

**Time Since Breakout**: O(1) from cache, O(log n) from database - **Fast**

**Total Overhead**: < 1ms per `detect_regime()` call

---

## 🔍 RETRIEVAL METHODS

### For ChatGPT Analysis

**Via `analyse_symbol_full`**:
- All metrics included in response automatically
- No additional tool calls needed
- ChatGPT can use metrics directly in reasoning

### For System Components

**Direct Access**:
```python
# Get ATR trend
atr_trend = regime_detector._calculate_atr_trend(symbol, "M15", atr_14, atr_50, now)

# Get wick variance
wick_variance = regime_detector._calculate_wick_variance(symbol, "M15", candle, now)

# Get time since breakout
time_since = regime_detector._get_time_since_breakout(symbol, "M15", now)
```

### For Historical Analysis

**Database Query**:
```python
# Query all breakouts for a symbol
breakouts = query_breakout_events(symbol="BTCUSDc", timeframe="M15", limit=10)

# Query breakouts in time range
breakouts = query_breakout_events(
    symbol="BTCUSDc",
    start_time=datetime(2025, 12, 1),
    end_time=datetime(2025, 12, 7)
)
```

---

## 📝 SUMMARY

### Tracking Methods

1. **ATR Slope**: In-memory rolling deque (20 values), calculated on-demand
2. **Wick Variance**: In-memory rolling deque (20 values), calculated on-demand
3. **Time Since Breakout**: SQLite database + in-memory cache, queried on-demand

### Storage Strategy

- **Fast calculations**: In-memory deques (auto-cleanup)
- **Persistent events**: SQLite database (breakout events)
- **No pre-calculation**: All calculated on-demand from recent candles

### ChatGPT Access

- **Automatic**: Included in `analyse_symbol_full` response
- **Structured**: All metrics in `volatility_metrics` object
- **Ready to use**: ChatGPT can directly use metrics for reasoning

### Performance

- **Memory**: < 10 KB total for all symbols
- **Database**: < 1 MB for 30 days of breakout events
- **Overhead**: < 1ms per detection call

---

# END_OF_DOCUMENT

