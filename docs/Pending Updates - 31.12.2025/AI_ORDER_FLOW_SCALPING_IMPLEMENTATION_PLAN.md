# AI Order-Flow Scalping Implementation Plan (Refined)

**Date:** 2025-12-31  
**Status:** 📋 **PLANNING**  
**Duration:** 4-6 weeks  
**Goal:** Real-time AI Order-Flow Scalping with tick-by-tick processing, enhanced divergence detection, pattern classification, and proxy support for XAUUSD/EURUSD

---

## 📊 **Overview**

This plan implements a comprehensive AI Order-Flow Scalping system that:
- Processes tick-by-tick data for real-time delta/CVD calculations
- Detects CVD and delta divergences with price bar alignment
- Uses weighted confluence pattern classification
- Provides real-time monitoring (5-second updates for order-flow plans)
- Includes order flow flip exit detection
- Supports proxy order flow for XAUUSD/EURUSD

**Resource Impact:**
- CPU: +18-32% (28-44% total)
- RAM: +130-230 MB (530-630 MB total)
- SSD: +60-120 MB (minimal)
- Network: +30-50 KB/s (80-100 KB/s total)

---

## 🚨 **Critical Issues Found and Fixes**

### **Issue 1: API Mismatch - CRITICAL BUG** ⚠️

**Problem:** Code calls `btc_flow.get_delta_volume()`, `btc_flow.get_cvd_trend()`, and `btc_flow.get_absorption_zones()`, but these methods **DO NOT EXIST**.

**All Broken Instances Found:**
```python
# auto_execution_system.py - 7 instances total:

# Line 3216-3217: Order block validation
delta = btc_flow.get_delta_volume()  # ❌
cvd_trend = btc_flow.get_cvd_trend()  # ❌

# Line 3245: Order block absorption zones
absorption_zones = btc_flow.get_absorption_zones()  # ❌

# Line 3305: Delta positive condition
delta = btc_flow.get_delta_volume()  # ❌

# Line 3325: CVD rising/falling condition
cvd_trend = btc_flow.get_cvd_trend()  # ❌

# Line 3387: Delta divergence bull condition
delta = btc_flow.get_delta_volume()  # ❌

# Line 3402: Delta divergence bear condition
delta = btc_flow.get_delta_volume()  # ❌
```

**Actual API:** `BTCOrderFlowMetrics` only has `get_metrics()` which returns an `OrderFlowMetrics` object with properties:
- `delta_volume` (float)
- `cvd_slope` (float)
- `cvd_divergence_type` (str or None)
- `cvd_divergence_strength` (float)
- `absorption_zones` (List[Dict])

**Comprehensive Fix:**

**Step 1: Create helper method to get metrics (cache for multiple checks)**
```python
# auto_execution_system.py - Add helper method
def _get_btc_order_flow_metrics(self, plan: TradePlan, window_seconds: int = 300) -> Optional[OrderFlowMetrics]:
    """Get BTC order flow metrics (cached per plan check)"""
    if not self.micro_scalp_engine or not hasattr(self.micro_scalp_engine, 'btc_order_flow'):
        return None
    
    try:
        btc_flow = self.micro_scalp_engine.btc_order_flow
        metrics = btc_flow.get_metrics("BTCUSDT", window_seconds=window_seconds)
        return metrics
    except Exception as e:
        logger.debug(f"Error getting order flow metrics for {plan.plan_id}: {e}")
        return None
```

**Step 2: Fix all 7 instances**

**Fix 1: Lines 3216-3217 (Order block validation)**
```python
# ❌ OLD
delta = btc_flow.get_delta_volume()
cvd_trend = btc_flow.get_cvd_trend()

# ✅ NEW
metrics = self._get_btc_order_flow_metrics(plan)
if not metrics:
    return False
delta = metrics.delta_volume
cvd_trend = {
    'trend': 'rising' if metrics.cvd_slope > 0 else 'falling' if metrics.cvd_slope < 0 else 'flat',
    'slope': metrics.cvd_slope
}
```

**Fix 2: Line 3245 (Order block absorption zones)**
```python
# ❌ OLD
absorption_zones = btc_flow.get_absorption_zones()

# ✅ NEW
metrics = self._get_btc_order_flow_metrics(plan)
if not metrics:
    return False
absorption_zones = metrics.absorption_zones or []
```

**Fix 3: Line 3305 (Delta positive condition)**
```python
# ❌ OLD
delta = btc_flow.get_delta_volume()

# ✅ NEW
metrics = self._get_btc_order_flow_metrics(plan)
if not metrics:
    return False
delta = metrics.delta_volume
```

**Fix 4: Line 3325 (CVD rising/falling condition)**
```python
# ❌ OLD
cvd_trend = btc_flow.get_cvd_trend()

# ✅ NEW
metrics = self._get_btc_order_flow_metrics(plan)
if not metrics:
    return False
cvd_trend = {
    'trend': 'rising' if metrics.cvd_slope > 0 else 'falling' if metrics.cvd_slope < 0 else 'flat',
    'slope': metrics.cvd_slope
}
```

**Fix 5: Line 3387 (Delta divergence bull)**
```python
# ❌ OLD
delta = btc_flow.get_delta_volume()

# ✅ NEW
metrics = self._get_btc_order_flow_metrics(plan)
if not metrics:
    return False
delta = metrics.delta_volume
```

**Fix 6: Line 3402 (Delta divergence bear)**
```python
# ❌ OLD
delta = btc_flow.get_delta_volume()

# ✅ NEW
metrics = self._get_btc_order_flow_metrics(plan)
if not metrics:
    return False
delta = metrics.delta_volume
```

**Fix 7: Line 3422 (Absorption zones check - already partially fixed)**
```python
# ✅ Already correct (uses get_metrics)
metrics = btc_flow.get_metrics("BTCUSDT", window_seconds=300)
if metrics and metrics.absorption_zones:
    # ... zone checking logic ...
```

**Action Required:** Fix all 7 instances **BEFORE** Phase 1 (Pre-Phase 0). This is a **CRITICAL** bug that prevents order flow conditions from working.

---

### **Issue 2: Async/Sync Mismatch**

**Problem:** `GeneralOrderFlowMetrics.get_order_flow_metrics()` is **async**, but `_check_conditions()` is **synchronous**.

**Fix:** Use `asyncio.run()` or `loop.run_until_complete()` pattern:
```python
# In _check_conditions() - sync function
import asyncio

try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

try:
    metrics = loop.run_until_complete(
        self._general_order_flow_metrics.get_order_flow_metrics(symbol_norm, 30)
    )
finally:
    # Don't close loop if it was already running
    try:
        current_loop = asyncio.get_event_loop()
        if loop != current_loop:
            loop.close()
    except RuntimeError:
        # No event loop running, safe to close
        loop.close()
```

**Note:** `GeneralOrderFlowMetrics._get_proxy_order_flow()` already uses `run_in_executor()` internally, so the async call is handled. However, we still need to handle the async wrapper properly.

---

### **Issue 3: Real-Time Update Loop Clarification**

**Problem:** Plan suggests separate 5-second loop, but system already has 30-second monitoring loop.

**Fix:** Modify existing loop to check order-flow plans every 5 seconds:
```python
def _monitor_loop(self):
    last_order_flow_check = 0
    order_flow_check_interval = 5  # 5 seconds
    
    while self.running:
        current_time = time.time()
        
        # High-frequency check for order-flow plans (every 5 seconds)
        if current_time - last_order_flow_check >= order_flow_check_interval:
            order_flow_plans = self._get_order_flow_plans()
            if order_flow_plans:
                self._check_order_flow_plans_quick(order_flow_plans)
            last_order_flow_check = current_time
        
        # Standard check for all plans (every 30 seconds)
        # ... existing code ...
        
        time.sleep(1)  # Sleep 1 second, check conditions above
```

---

### **Issue 4: MT5 get_bars Returns DataFrame, Not List of Dicts** ⚠️

**Problem:** Plan assumes `mt5_service.get_bars()` returns `List[Dict]`, but it actually returns `pandas.DataFrame`.

**Current (Incorrect) Assumption:**
```python
# Plan assumes:
price_bars = [{'high': 100, 'low': 99, ...}, ...]  # ❌ Wrong

# Actual:
price_bars = pd.DataFrame({'high': [...], 'low': [...], ...})  # ✅ Correct
```

**Fix:**
```python
# Get M1 bars (returns DataFrame)
m1_bars = self.mt5_service.get_bars(mt5_symbol, "M1", 50)
if m1_bars is None or len(m1_bars) < 20:
    return self._calculate_cvd_divergence_simplified(symbol)

# Convert DataFrame to list of dicts for processing
price_bars = []
for idx, row in m1_bars.iterrows():
    price_bars.append({
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'open': float(row['open']),
        'time': row['time']  # Timestamp for alignment
    })
```

**Alternative (Better):** Work directly with DataFrame:
```python
# Work with DataFrame directly (more efficient)
if m1_bars is None or len(m1_bars) < 20:
    return self._calculate_cvd_divergence_simplified(symbol)

# Access DataFrame columns directly
price_highs = m1_bars['high'].values[-20:]
price_lows = m1_bars['low'].values[-20:]
price_closes = m1_bars['close'].values[-20:]
```

---

### **Issue 5: Tick Data Source Clarification** ⚠️

**Problem:** Plan mentions "tick-by-tick" but Binance aggTrades are **aggregated trades**, not individual ticks.

**Clarification:**
- **Binance aggTrades:** Aggregated trades (multiple trades combined)
- **True Tick-by-Tick:** Individual price updates (not available from Binance aggTrades)
- **For Delta Calculation:** Use aggTrades with `side` (BUY/SELL) to calculate delta

**Fix:**
```python
# Tick-by-tick delta engine should use Binance aggTrades
# Each aggTrade has: price, quantity, side (BUY/SELL)
# Calculate delta per aggTrade:
#   - If side == "BUY": buy_volume += quantity
#   - If side == "SELL": sell_volume += quantity
#   - delta = buy_volume - sell_volume

def process_aggtrade(self, trade_data: Dict) -> Optional[DeltaMetrics]:
    """Process Binance aggTrade (aggregated trade, not true tick)"""
    side = trade_data.get("side")  # "BUY" or "SELL"
    quantity = trade_data.get("quantity", 0)
    
    if side == "BUY":
        buy_volume = quantity
        sell_volume = 0
    else:  # SELL
        buy_volume = 0
        sell_volume = quantity
    
    delta = buy_volume - sell_volume
    # ... rest of processing ...
```

**Note:** 
- Rename "Tick-by-Tick" to "AggTrade-by-AggTrade" or "Real-Time Delta" for accuracy
- Binance aggTrades provide `side` (BUY/SELL) which is sufficient for delta calculation
- True tick-by-tick data (individual price updates) is not available from Binance aggTrades stream
- For true tick data, would need Binance ticker stream (24hr ticker), but that doesn't provide buy/sell separation

---

### **Issue 6: Entry Delta Storage Location** ⚠️

**Problem:** Plan mentions storing `entry_delta` in `ExitRule.metadata`, but `ExitRule` doesn't have a `metadata` field.

**Current ExitRule Structure:**
- Has: `advanced_gate: Dict[str, Any]` (can be used)
- Missing: `metadata` field

**Fix Options:**

**Option A (Recommended):** Add `metadata` field to `ExitRule`:
```python
# infra/intelligent_exit_manager.py - Modify ExitRule.__init__()
def __init__(self, ...):
    # ... existing fields ...
    self.metadata: Dict[str, Any] = {}  # NEW: For storing entry_delta, etc.
```

**Option B:** Use existing `advanced_gate` field:
```python
# Store entry delta in advanced_gate
rule.advanced_gate['entry_delta'] = entry_delta

# Retrieve later
entry_delta = rule.advanced_gate.get('entry_delta')
```

**Option C:** Store in separate tracking dict:
```python
# In IntelligentExitManager.__init__()
self.entry_deltas: Dict[int, float] = {}  # ticket -> entry_delta

# When position opened
self.entry_deltas[ticket] = entry_delta

# When checking flip
entry_delta = self.entry_deltas.get(ticket)
```

**Recommendation:** Use Option A (add `metadata` field) for flexibility.

---

### **Issue 7: self.plans is Dict, Not List** ⚠️

**Problem:** Plan code assumes `self.plans` is a list, but it's actually a `Dict[str, TradePlan]`.

**Fix:**
```python
def _get_order_flow_plans(self) -> List[TradePlan]:
    """Get plans that have order flow conditions"""
    order_flow_conditions = [
        "delta_positive", "delta_negative",
        "cvd_rising", "cvd_falling",
        # ... etc ...
    ]
    
    # self.plans is a dict, so iterate over values
    return [
        plan for plan in self.plans.values()  # ✅ Correct
        if any(plan.conditions.get(cond) for cond in order_flow_conditions)
    ]
```

---

### **Issue 8: MT5 Service Parameter Missing in BTCOrderFlowMetrics** ⚠️

**Problem:** Plan assumes `BTCOrderFlowMetrics` can access `mt5_service`, but it's not in `__init__`.

**Fix:**
```python
# infra/btc_order_flow_metrics.py - Modify __init__()
def __init__(
    self,
    order_flow_service=None,
    mt5_service=None,  # NEW: Add MT5 service parameter
    cvd_window_seconds: int = 300,
    cvd_slope_period: int = 10,
    absorption_threshold_volume: float = 100000,
    absorption_threshold_imbalance: float = 1.5
):
    self.order_flow_service = order_flow_service
    self.mt5_service = mt5_service  # NEW: Store MT5 service
    # ... rest of init ...
```

**Integration:**
```python
# infra/micro_scalp_engine.py - Pass mt5_service
btc_order_flow = BTCOrderFlowMetrics(
    order_flow_service=order_flow_service,
    mt5_service=mt5_service  # NEW: Pass MT5 service
)
```

---

### **Issue 9: GeneralOrderFlowMetrics Uses run_in_executor** ⚠️

**Problem:** Plan shows direct async call, but `_get_proxy_order_flow()` already uses `run_in_executor()` internally.

**Actual Implementation:**
```python
# infra/general_order_flow_metrics.py line 173
loop = asyncio.get_event_loop()
bars = await loop.run_in_executor(
    None,
    lambda: self.mt5_service.get_bars(symbol, "M5", bars_needed)
)
```

**Fix:** Since `get_order_flow_metrics()` is async and uses `run_in_executor()` internally, we can call it directly with proper async handling:
```python
# In _check_conditions() - sync function
import asyncio

# Create new event loop for this call (safer)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

try:
    metrics = loop.run_until_complete(
        self._general_order_flow_metrics.get_order_flow_metrics(symbol_norm, 30)
    )
finally:
    loop.close()
    asyncio.set_event_loop(None)  # Clear event loop
```

---

### **Issue 10: Price Bar Format in Divergence Detection** ⚠️

**Problem:** Plan code accesses price bars as `price_bars[i]['high']`, but if using DataFrame, should use `price_bars.iloc[i]['high']` or convert to list first.

**Fix:**
```python
def _detect_divergence_from_bars(self, price_bars_df: pd.DataFrame, cvd_bars: List[float]) -> Dict:
    """Detect divergence from aligned price and CVD bars"""
    
    if len(price_bars_df) < 20 or len(cvd_bars) < 20:
        return {"type": None, "strength": 0.0}
    
    # Convert DataFrame to list for easier processing
    price_bars = []
    for idx, row in price_bars_df.iterrows():
        price_bars.append({
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'open': float(row['open']),
            'time': row['time']
        })
    
    # Now process as list of dicts
    # ... rest of divergence detection ...
```

**Alternative:** Work with DataFrame directly (more efficient):
```python
def _detect_divergence_from_bars(self, price_bars_df: pd.DataFrame, cvd_bars: List[float]) -> Dict:
    """Detect divergence - work with DataFrame directly"""
    
    if len(price_bars_df) < 20 or len(cvd_bars) < 20:
        return {"type": None, "strength": 0.0}
    
    # Get last 20 bars as arrays
    recent_bars = price_bars_df.tail(20)
    price_highs = recent_bars['high'].values
    price_lows = recent_bars['low'].values
    
    # Find swing highs/lows using numpy
    import numpy as np
    
    # Swing high: higher than previous and next
    swing_high_indices = []
    for i in range(1, len(price_highs) - 1):
        if price_highs[i] > price_highs[i-1] and price_highs[i] > price_highs[i+1]:
            swing_high_indices.append(i)
    
    # ... rest of detection using indices ...
```

---

### **Issue 11: CVD History Alignment with Price Bars** ⚠️

**Problem:** CVD is calculated per 1-minute bar, but price bars from MT5 may have different timestamps. Need proper alignment.

**Fix:**
```python
def _get_cvd_bars_aligned(self, symbol: str, price_bars_df: pd.DataFrame) -> List[float]:
    """Get CVD values aligned with price bars by timestamp"""
    
    if symbol not in self.cvd_history or len(self.cvd_history[symbol]) < len(price_bars_df):
        return []
    
    # Get price bar timestamps (convert to Unix timestamp)
    price_timestamps = []
    for idx, row in price_bars_df.iterrows():
        if isinstance(row['time'], pd.Timestamp):
            ts = int(row['time'].timestamp())
        else:
            ts = int(row['time'])
        price_timestamps.append(ts)
    
    # CVD history is stored per 1-minute bar
    # Each CVD value corresponds to a 1-minute window
    # Align by matching time windows (simplified: assume 1:1 if same count)
    cvd_values = list(self.cvd_history[symbol])
    
    # If counts match, assume alignment (1:1)
    if len(cvd_values) >= len(price_bars_df):
        return cvd_values[-len(price_bars_df):]
    
    return []
```

**Note:** Full timestamp alignment requires tracking CVD bar timestamps, which adds complexity. Simplified 1:1 alignment is acceptable for initial implementation.

---

### **Issue 12: Missing Error Handling in Several Places** ⚠️

**Problem:** Some code examples lack proper error handling.

**Fix:** Add try/except blocks:
```python
# Example: Enhanced CVD divergence with error handling
def _calculate_cvd_divergence(self, symbol: str) -> Optional[Dict]:
    """Enhanced CVD divergence with price bar alignment"""
    
    try:
        # 1. Get price bars from MT5
        if not hasattr(self, 'mt5_service') or not self.mt5_service:
            return self._calculate_cvd_divergence_simplified(symbol)
        
        mt5_symbol = symbol.replace("USDT", "USDc")
        
        try:
            m1_bars = self.mt5_service.get_bars(mt5_symbol, "M1", 50)
        except Exception as e:
            logger.debug(f"Error getting M1 bars for {symbol}: {e}")
            return self._calculate_cvd_divergence_simplified(symbol)
        
        if m1_bars is None or len(m1_bars) < 20:
            return self._calculate_cvd_divergence_simplified(symbol)
        
        # 2. Get CVD bars (aligned)
        try:
            cvd_bars = self._get_cvd_bars_aligned(symbol, m1_bars)
        except Exception as e:
            logger.debug(f"Error aligning CVD bars for {symbol}: {e}")
            return self._calculate_cvd_divergence_simplified(symbol)
        
        if not cvd_bars or len(cvd_bars) < 20:
            return self._calculate_cvd_divergence_simplified(symbol)
        
        # 3. Detect divergence
        try:
            divergence = self._detect_divergence_from_bars(m1_bars, cvd_bars)
            return divergence
        except Exception as e:
            logger.debug(f"Error detecting divergence for {symbol}: {e}")
            return self._calculate_cvd_divergence_simplified(symbol)
        
    except Exception as e:
        logger.error(f"Error calculating CVD divergence for {symbol}: {e}")
        return self._calculate_cvd_divergence_simplified(symbol)
```

---

## 🔧 **Pre-Phase 0: Critical Bug Fixes** (1-2 days)

**Priority:** ⚠️ **CRITICAL** - Must be fixed before Phase 1

### **Task 0.1: Fix API Usage in auto_execution_system.py**

**Files to Modify:**
- `auto_execution_system.py` lines 3301-3338

**Current (Broken) Code:**
```python
# Line 3305
delta = btc_flow.get_delta_volume()  # ❌ Doesn't exist

# Line 3325
cvd_trend = btc_flow.get_cvd_trend()  # ❌ Doesn't exist
```

**Fixed Code:**
```python
# Check delta conditions
if plan.conditions.get("delta_positive") or plan.conditions.get("delta_negative"):
    if self.micro_scalp_engine and hasattr(self.micro_scalp_engine, 'btc_order_flow'):
        try:
            btc_flow = self.micro_scalp_engine.btc_order_flow
            
            # Get metrics once (cached for multiple checks)
            metrics = btc_flow.get_metrics("BTCUSDT", window_seconds=300)
            if not metrics:
                logger.debug(f"Plan {plan.plan_id}: Could not get order flow metrics")
                return False
            
            # Extract delta from metrics
            delta = metrics.delta_volume
            
            if plan.conditions.get("delta_positive"):
                if delta is None or delta <= 0:
                    logger.debug(f"Plan {plan.plan_id}: delta_positive condition not met (delta: {delta})")
                    return False
            
            if plan.conditions.get("delta_negative"):
                if delta is None or delta >= 0:
                    logger.debug(f"Plan {plan.plan_id}: delta_negative condition not met (delta: {delta})")
                    return False
        except Exception as e:
            logger.debug(f"Error checking delta condition for {plan.plan_id}: {e}")
            return False

# Check CVD conditions
if plan.conditions.get("cvd_rising") or plan.conditions.get("cvd_falling"):
    if self.micro_scalp_engine and hasattr(self.micro_scalp_engine, 'btc_order_flow'):
        try:
            btc_flow = self.micro_scalp_engine.btc_order_flow
            
            # Get metrics (reuse if already fetched above, or fetch new)
            if 'metrics' not in locals():
                metrics = btc_flow.get_metrics("BTCUSDT", window_seconds=300)
                if not metrics:
                    logger.debug(f"Plan {plan.plan_id}: Could not get CVD metrics")
                    return False
            
            # Calculate CVD trend from slope
            cvd_slope = metrics.cvd_slope
            cvd_trend = {
                'trend': 'rising' if cvd_slope > 0 else 'falling' if cvd_slope < 0 else 'flat',
                'slope': cvd_slope
            }
            
            if plan.conditions.get("cvd_rising"):
                if cvd_trend.get('trend') != 'rising':
                    logger.debug(f"Plan {plan.plan_id}: cvd_rising condition not met (trend: {cvd_trend.get('trend')})")
                    return False
            
            if plan.conditions.get("cvd_falling"):
                if cvd_trend.get('trend') != 'falling':
                    logger.debug(f"Plan {plan.plan_id}: cvd_falling condition not met (trend: {cvd_trend.get('trend')})")
                    return False
        except Exception as e:
            logger.debug(f"Error checking CVD condition for {plan.plan_id}: {e}")
            return False
```

**Testing:**
- [ ] Verify ALL 7 instances are fixed (grep for `get_delta_volume|get_cvd_trend|get_absorption_zones` - should return 0 results)
- [ ] Verify delta checks work with real BTC plans
- [ ] Verify CVD trend checks work correctly
- [ ] Verify absorption zone checks work correctly
- [ ] Test error handling when metrics unavailable
- [ ] Test helper method caching (metrics reused across multiple checks)
- [ ] Verify no performance degradation
- [ ] Test with plans that have multiple order flow conditions (should reuse metrics)

---

## 📋 **Phase 1: Core Enhancements** (1-2 weeks)

**Impact:** CPU +8-13%, RAM +40-60 MB

### **Task 1.1: Tick-by-Tick Delta Engine**

**Files to Create/Modify:**
- **New:** `infra/tick_by_tick_delta_engine.py`
- **Modify:** `infra/btc_order_flow_metrics.py` (add tick processing methods)
- **Modify:** `infra/micro_scalp_engine.py` (integrate tick engine)

**Implementation:**
```python
# infra/tick_by_tick_delta_engine.py
"""
Tick-by-Tick Delta Engine
Real-time tick-by-tick delta calculation for order flow analysis
"""

import logging
import time
from typing import Dict, Optional, List
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DeltaMetrics:
    """Delta metrics for a single tick"""
    delta: float
    cvd: float
    timestamp: float
    buy_volume: float
    sell_volume: float

class TickByTickDeltaEngine:
    """Real-time tick-by-tick delta calculation"""
    
    def __init__(self, order_flow_service=None):
        self.order_flow_service = order_flow_service
        self.tick_buffer = deque(maxlen=1000)  # Last 1000 ticks
        self.delta_history = deque(maxlen=100)  # Last 100 delta values
        self.cvd_history = deque(maxlen=200)  # Last 200 CVD values
        self.current_delta = 0.0
        self.current_cvd = 0.0
        self.last_tick_time = 0.0
        
    def process_aggtrade(self, trade_data: Dict) -> Optional[DeltaMetrics]:
        """
        Process Binance aggTrade (aggregated trade) and calculate delta.
        
        Note: Binance aggTrades are aggregated trades, not individual ticks.
        Each aggTrade represents multiple trades combined.
        
        Args:
            trade_data: Dict with 'side' ("BUY"/"SELL"), 'quantity', 'timestamp'
        
        Returns:
            DeltaMetrics or None if insufficient data
        """
        try:
            # Extract from trade data (Binance aggTrade format)
            side = trade_data.get("side")  # "BUY" or "SELL"
            quantity = trade_data.get("quantity", 0)
            timestamp = trade_data.get("timestamp", time.time())
            
            # Calculate buy/sell volume
            if side == "BUY":
                buy_volume = quantity
                sell_volume = 0
            else:  # SELL
                buy_volume = 0
                sell_volume = quantity
            
            # Calculate delta
            delta = buy_volume - sell_volume
            
            # Update CVD (cumulative sum)
            self.current_cvd += delta
            self.cvd_history.append(self.current_cvd)
            
            # Store delta
            self.current_delta = delta
            self.delta_history.append(delta)
            
            # Store trade
            self.tick_buffer.append({
                "delta": delta,
                "cvd": self.current_cvd,
                "timestamp": timestamp,
                "buy_volume": buy_volume,
                "sell_volume": sell_volume
            })
            
            self.last_tick_time = timestamp
            
            return DeltaMetrics(
                delta=delta,
                cvd=self.current_cvd,
                timestamp=timestamp,
                buy_volume=buy_volume,
                sell_volume=sell_volume
            )
            
        except Exception as e:
            logger.error(f"Error processing aggTrade: {e}")
            return None
    
    def get_current_delta(self) -> float:
        """Get current delta volume"""
        return self.current_delta
    
    def get_cvd_value(self) -> float:
        """Get current CVD value"""
        return self.current_cvd
    
    def get_cvd_trend(self) -> Dict[str, any]:
        """Get CVD trend from recent history"""
        if len(self.cvd_history) < 2:
            return {"trend": "flat", "slope": 0.0}
        
        recent = list(self.cvd_history)[-10:]
        if len(recent) < 2:
            return {"trend": "flat", "slope": 0.0}
        
        slope = (recent[-1] - recent[0]) / len(recent) if len(recent) > 1 else 0.0
        
        return {
            "trend": "rising" if slope > 0 else "falling" if slope < 0 else "flat",
            "slope": slope
        }
    
    def get_delta_history(self, count: int = 20) -> List[float]:
        """Get recent delta history"""
        return list(self.delta_history)[-count:]
    
    def get_cvd_history(self, count: int = 20) -> List[float]:
        """Get recent CVD history"""
        return list(self.cvd_history)[-count:]
```

**Integration Points:**
- `infra/btc_order_flow_metrics.py`: Add `process_tick()` method that uses tick engine
- `infra/micro_scalp_engine.py`: Initialize tick engine in `__init__`
- `auto_execution_system.py`: Use tick engine for real-time delta checks

**Note:** Keep existing bar-based system for backward compatibility. Tick engine runs in parallel.

**Testing:**
- [ ] Unit tests for tick processing
- [ ] Verify delta calculation accuracy
- [ ] Test with 1000+ ticks/second
- [ ] Verify memory usage (deques with maxlen)

---

### **Task 1.2: Enhanced CVD Divergence**

**Files to Modify:**
- `infra/btc_order_flow_metrics.py` (enhance `_calculate_cvd_divergence()`)
- **New:** `infra/price_cvd_alignment.py` (price bar alignment utility)

**Implementation:**
```python
# infra/btc_order_flow_metrics.py - Enhance _calculate_cvd_divergence()
def _calculate_cvd_divergence(self, symbol: str) -> Optional[Dict]:
    """Enhanced CVD divergence with price bar alignment"""
    
    try:
        # 1. Get price bars from MT5 (M1 timeframe)
        # Note: Need to add mt5_service to BTCOrderFlowMetrics initialization
        if not hasattr(self, 'mt5_service') or not self.mt5_service:
            # Fallback: Use simplified divergence (existing code)
            return self._calculate_cvd_divergence_simplified(symbol)
        
        # Get M1 bars for price data (returns pandas DataFrame)
        mt5_symbol = symbol.replace("USDT", "USDc")
        
        try:
            m1_bars_df = self.mt5_service.get_bars(mt5_symbol, "M1", 50)
        except Exception as e:
            logger.debug(f"Error getting M1 bars for {symbol}: {e}")
            return self._calculate_cvd_divergence_simplified(symbol)
        
        if m1_bars_df is None or len(m1_bars_df) < 20:
            logger.debug(f"Insufficient M1 bars for {symbol}, using simplified divergence")
            return self._calculate_cvd_divergence_simplified(symbol)
        
        # 2. Get CVD bars (aligned with price bars by timestamp)
        try:
            cvd_bars = self._get_cvd_bars_aligned(symbol, m1_bars_df)
        except Exception as e:
            logger.debug(f"Error aligning CVD bars for {symbol}: {e}")
            return self._calculate_cvd_divergence_simplified(symbol)
        
        if not cvd_bars or len(cvd_bars) < 20:
            return self._calculate_cvd_divergence_simplified(symbol)
        
        # 3. Detect divergence
        try:
            divergence = self._detect_divergence_from_bars(m1_bars_df, cvd_bars)
            return divergence
        except Exception as e:
            logger.debug(f"Error detecting divergence for {symbol}: {e}")
            return self._calculate_cvd_divergence_simplified(symbol)
        
    except Exception as e:
        logger.error(f"Error calculating CVD divergence: {e}")
        return self._calculate_cvd_divergence_simplified(symbol)

def _get_cvd_bars_aligned(self, symbol: str, price_bars_df: pd.DataFrame) -> List[float]:
    """
    Get CVD values aligned with price bars by timestamp.
    
    Args:
        symbol: Trading symbol
        price_bars_df: pandas DataFrame with price bars (columns: 'time', 'high', 'low', 'close', etc.)
    
    Returns:
        List of CVD values aligned with price bars
    """
    if symbol not in self.cvd_history or len(self.cvd_history[symbol]) < len(price_bars_df):
        return []
    
    # Get CVD values for same time period as price bars
    # Simplified alignment: assume 1:1 if counts match (both are 1-minute bars)
    # Full timestamp alignment would require tracking CVD bar timestamps (future enhancement)
    cvd_values = list(self.cvd_history[symbol])
    
    # If counts match, assume alignment (1:1)
    if len(cvd_values) >= len(price_bars_df):
        return cvd_values[-len(price_bars_df):]
    
    return []

def _detect_divergence_from_bars(self, price_bars_df: pd.DataFrame, cvd_bars: List[float]) -> Dict:
    """
    Detect divergence from aligned price and CVD bars.
    
    Args:
        price_bars_df: pandas DataFrame with price bars
        cvd_bars: List of CVD values (aligned with price_bars_df)
    
    Returns:
        Dict with 'type' ('bearish'/'bullish'/'None') and 'strength' (0.0-1.0)
    """
    if len(price_bars_df) < 20 or len(cvd_bars) < 20:
        return {"type": None, "strength": 0.0}
    
    # Convert DataFrame to arrays for easier processing
    recent_bars = price_bars_df.tail(20)
    price_highs_array = recent_bars['high'].values
    price_lows_array = recent_bars['low'].values
    
    # Find price highs/lows (swing points)
    price_highs = []
    price_lows = []
    
    for i in range(1, len(price_highs_array) - 1):
        # Check for swing high
        if (price_highs_array[i] > price_highs_array[i-1] and 
            price_highs_array[i] > price_highs_array[i+1]):
            price_highs.append((i, float(price_highs_array[i])))
        # Check for swing low
        if (price_lows_array[i] < price_lows_array[i-1] and 
            price_lows_array[i] < price_lows_array[i+1]):
            price_lows.append((i, float(price_lows_array[i])))
    
    # Find CVD highs/lows
    cvd_highs = []
    cvd_lows = []
    
    for i in range(len(cvd_bars) - 20, len(cvd_bars)):
        if i > 0 and i < len(cvd_bars) - 1:
            if cvd_bars[i] > cvd_bars[i-1] and cvd_bars[i] > cvd_bars[i+1]:
                cvd_highs.append((i, cvd_bars[i]))
            if cvd_bars[i] < cvd_bars[i-1] and cvd_bars[i] < cvd_bars[i+1]:
                cvd_lows.append((i, cvd_bars[i]))
    
    # Detect bearish divergence: Price makes higher high, CVD makes lower high
    if len(price_highs) >= 2 and len(cvd_highs) >= 2:
        price_trend = price_highs[-1][1] > price_highs[-2][1]
        cvd_trend = cvd_highs[-1][1] < cvd_highs[-2][1]
        
        if price_trend and cvd_trend:
            strength = self._calculate_divergence_strength(price_highs, cvd_highs)
            return {"type": "bearish", "strength": strength}
    
    # Detect bullish divergence: Price makes lower low, CVD makes higher low
    if len(price_lows) >= 2 and len(cvd_lows) >= 2:
        price_trend = price_lows[-1][1] < price_lows[-2][1]
        cvd_trend = cvd_lows[-1][1] > cvd_lows[-2][1]
        
        if price_trend and cvd_trend:
            strength = self._calculate_divergence_strength(price_lows, cvd_lows)
            return {"type": "bullish", "strength": strength}
    
    return {"type": None, "strength": 0.0}

def _calculate_divergence_strength(self, price_points: List, cvd_points: List) -> float:
    """Calculate divergence strength (0.0-1.0)"""
    if len(price_points) < 2 or len(cvd_points) < 2:
        return 0.0
    
    # Calculate how opposite the trends are
    price_change = abs(price_points[-1][1] - price_points[-2][1])
    cvd_change = abs(cvd_points[-1][1] - cvd_points[-2][1])
    
    # Normalize to 0-1
    if price_change == 0:
        return 0.0
    
    # Strength based on relative change
    strength = min(1.0, (price_change + cvd_change) / (price_change * 2))
    return strength

def _calculate_cvd_divergence_simplified(self, symbol: str) -> Optional[Dict]:
    """Simplified CVD divergence (fallback when price bars unavailable)"""
    # Existing placeholder implementation
    return {"type": None, "strength": 0.0}
```

**Integration:**
- `auto_execution_system.py` lines 3351-3374: Use enhanced divergence
- `infra/btc_order_flow_metrics.py` `__init__`: Add `mt5_service` parameter
- `infra/micro_scalp_engine.py`: Pass `mt5_service` to `BTCOrderFlowMetrics`
- `auto_execution_system.py` `__init__`: Pass `mt5_service` when creating `BTCOrderFlowMetrics`

**Required Changes:**
```python
# infra/btc_order_flow_metrics.py - Modify __init__()
def __init__(
    self,
    order_flow_service=None,
    mt5_service=None,  # NEW: Add MT5 service
    cvd_window_seconds: int = 300,
    cvd_slope_period: int = 10,
    absorption_threshold_volume: float = 100000,
    absorption_threshold_imbalance: float = 1.5
):
    self.order_flow_service = order_flow_service
    self.mt5_service = mt5_service  # NEW: Store MT5 service
    # ... rest of init ...

# auto_execution_system.py - Modify BTCOrderFlowMetrics initialization (around line 665)
btc_order_flow = BTCOrderFlowMetrics(
    order_flow_service=order_flow_service,
    mt5_service=self.mt5_service  # NEW: Pass MT5 service
)
```

**Testing:**
- [ ] Test with various price/CVD patterns
- [ ] Verify strength calculation (0.0-1.0)
- [ ] Test edge cases (no divergence, weak divergence)
- [ ] Test fallback when MT5 unavailable
- [ ] Test DataFrame handling (not list of dicts)
- [ ] Test timestamp alignment (simplified 1:1 vs full alignment)

---

### **Task 1.3: Delta Divergence Detection**

**Files to Create/Modify:**
- **New:** `infra/delta_divergence_detector.py`
- **Modify:** `infra/btc_order_flow_metrics.py` (add delta divergence method)
- **Modify:** `auto_execution_system.py` (add delta divergence checks)

**Implementation:**
```python
# infra/delta_divergence_detector.py
"""
Delta Divergence Detector
Detects delta divergence (price trend vs delta trend)
"""

import numpy as np
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

class DeltaDivergenceDetector:
    """Detect delta divergence (price trend vs delta trend)"""
    
    def detect_delta_divergence(
        self, 
        price_bars_df: pd.DataFrame,
        delta_history: List[float]
    ) -> Optional[Dict]:
        """
        Detect bullish/bearish delta divergence.
        
        Args:
            price_bars_df: pandas DataFrame with price bars (columns: 'close', 'high', 'low', etc.)
            delta_history: List of delta values (aligned with price_bars_df)
        
        Returns:
            Dict with 'type' ('bullish'/'bearish'), 'strength' (0.0-1.0), or None
        """
        if price_bars_df is None or len(price_bars_df) < 20 or len(delta_history) < 20:
            return None
        
        try:
            # 1. Calculate price trend (slope of closes)
            # Get last 20 closes from DataFrame
            price_closes = price_bars_df['close'].values[-20:].tolist()
            price_slope = self._calculate_trend_slope(price_closes)
            
            # 2. Calculate delta trend (slope of delta values)
            delta_slope = self._calculate_trend_slope(delta_history[-20:])
            
            # 3. Detect divergence
            # Bullish: Price down (negative slope), Delta up (positive slope)
            # Bearish: Price up (positive slope), Delta down (negative slope)
            
            threshold = 0.001  # Minimum slope to consider significant
            
            if price_slope < -threshold and delta_slope > threshold:  # Bullish divergence
                strength = self._calculate_divergence_strength(price_slope, delta_slope)
                return {
                    "type": "bullish",
                    "strength": strength,
                    "price_slope": price_slope,
                    "delta_slope": delta_slope
                }
            elif price_slope > threshold and delta_slope < -threshold:  # Bearish divergence
                strength = self._calculate_divergence_strength(price_slope, delta_slope)
                return {
                    "type": "bearish",
                    "strength": strength,
                    "price_slope": price_slope,
                    "delta_slope": delta_slope
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting delta divergence: {e}")
            return None
    
    def _calculate_trend_slope(self, values: List[float]) -> float:
        """Calculate trend slope using linear regression"""
        if len(values) < 2:
            return 0.0
        
        try:
            x = np.arange(len(values))
            y = np.array(values)
            slope = np.polyfit(x, y, 1)[0]
            return float(slope)
        except Exception as e:
            logger.debug(f"Error calculating trend slope: {e}")
            return 0.0
    
    def _calculate_divergence_strength(self, price_slope: float, delta_slope: float) -> float:
        """Calculate divergence strength (0.0-1.0)"""
        # Strength based on how opposite the trends are
        slope_diff = abs(price_slope) + abs(delta_slope)
        strength = min(1.0, slope_diff / 0.01)  # Normalize
        return strength
```

**Integration:**
- `infra/btc_order_flow_metrics.py`: Add `get_delta_divergence()` method
- `auto_execution_system.py` lines 3376-3408: Replace proxy logic with real delta divergence
- `infra/btc_order_flow_metrics.py`: Add `mt5_service` parameter to `__init__`

**Delta Divergence Method:**
```python
# infra/btc_order_flow_metrics.py - Add method
def get_delta_divergence(self, symbol: str) -> Optional[Dict]:
    """Get delta divergence (price trend vs delta trend)"""
    try:
        if not self.mt5_service:
            return None
        
        # Get price bars (M1)
        mt5_symbol = symbol.replace("USDT", "USDc")
        price_bars_df = self.mt5_service.get_bars(mt5_symbol, "M1", 50)
        if price_bars_df is None or len(price_bars_df) < 20:
            return None
        
        # Get delta history from tick engine or calculate from recent trades
        delta_history = self._get_delta_history(symbol, count=20)
        if not delta_history or len(delta_history) < 20:
            return None
        
        # Use delta divergence detector
        from infra.delta_divergence_detector import DeltaDivergenceDetector
        detector = DeltaDivergenceDetector()
        return detector.detect_delta_divergence(price_bars_df, delta_history)
        
    except Exception as e:
        logger.debug(f"Error getting delta divergence for {symbol}: {e}")
        return None

def _get_delta_history(self, symbol: str, count: int = 20) -> List[float]:
    """Get recent delta history for divergence calculation"""
    # Get from tick engine if available, or calculate from recent trades
    if hasattr(self, 'tick_engine') and self.tick_engine:
        return self.tick_engine.get_delta_history(count)
    
    # Fallback: Calculate from recent pressure data
    if self.order_flow_service:
        # Get recent pressure data and extract deltas
        # This is simplified - full implementation would track delta per bar
        return []  # Placeholder
    
    return []
```

**Testing:**
- [ ] Test with various price/delta combinations
- [ ] Verify divergence detection accuracy
- [ ] Test with noisy data
- [ ] Test edge cases (no divergence, weak divergence)
- [ ] Test DataFrame handling (not list of dicts)

---

### **Phase 1 Deliverables:**
- [ ] Tick-by-tick delta engine working
- [ ] Enhanced CVD divergence with price alignment
- [ ] Delta divergence detection implemented
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Resource monitoring shows CPU +8-13%, RAM +40-60 MB

---

## 📋 **Phase 2: AI Pattern Classification** (1-2 weeks)

**Impact:** CPU +8-15%, RAM +30-50 MB

### **Task 2.1: Weighted Confluence System**

**Files to Create/Modify:**
- **New:** `infra/ai_pattern_classifier.py`
- **Modify:** `auto_execution_system.py` (integrate pattern classifier)
- **Modify:** `infra/micro_scalp_engine.py` (use pattern scores)

**Implementation:**
```python
# infra/ai_pattern_classifier.py
"""
AI Pattern Classifier
Weighted confluence pattern classification for order flow scalping
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class AIPatternClassifier:
    """Weighted confluence pattern classifier"""
    
    # Pattern weights (configurable via config file)
    DEFAULT_WEIGHTS = {
        'absorption': 0.30,
        'delta_divergence': 0.25,
        'liquidity_sweep': 0.20,
        'cvd_divergence': 0.15,
        'vwap_deviation': 0.10
    }
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.weights = self.config.get('pattern_weights', self.DEFAULT_WEIGHTS)
        self.threshold = self.config.get('pattern_threshold', 0.75)  # 75% minimum
    
    def classify_pattern(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify pattern and calculate probability.
        
        Args:
            signals: Dict with signal names and values
                - Boolean: True/False
                - Float: 0.0-1.0 (normalized)
                - Dict: {'strength': 0.0-1.0, ...}
        
        Returns:
            Dict with probability, pattern_type, signal_scores, etc.
        """
        signal_scores = {}
        total_score = 0.0
        
        # Check each signal
        for signal_name, weight in self.weights.items():
            signal_value = signals.get(signal_name, False)
            
            if isinstance(signal_value, bool):
                # Boolean signal: full weight if True
                score = weight if signal_value else 0.0
            elif isinstance(signal_value, (int, float)):
                # Numeric signal: normalize to 0-1, then apply weight
                normalized = min(max(float(signal_value), 0.0), 1.0)
                score = normalized * weight
            elif isinstance(signal_value, dict):
                # Complex signal: extract strength/confidence
                strength = signal_value.get('strength', 0.0)
                if isinstance(strength, (int, float)):
                    strength = min(max(float(strength), 0.0), 1.0)
                score = strength * weight
            else:
                score = 0.0
            
            signal_scores[signal_name] = score
            total_score += score
        
        # Calculate probability (0-100%)
        probability = min(total_score * 100, 100.0)
        
        # Classify pattern type
        pattern_type = self._classify_pattern_type(signals, signal_scores)
        
        return {
            "probability": probability,
            "pattern_type": pattern_type,
            "signal_scores": signal_scores,
            "total_score": total_score,
            "meets_threshold": probability >= (self.threshold * 100),
            "threshold": self.threshold * 100
        }
    
    def _classify_pattern_type(self, signals: Dict, scores: Dict) -> str:
        """Classify the dominant pattern type"""
        if not scores:
            return "unknown"
        
        # Find highest scoring signal
        max_signal = max(scores.items(), key=lambda x: x[1])
        if max_signal[1] > 0:
            return max_signal[0]
        return "unknown"
```

**Integration:**
- `auto_execution_system.py`: Add pattern classification before execution
- `infra/micro_scalp_engine.py`: Use pattern scores in condition validation

**Usage Example:**
```python
# In _check_conditions() before execution
signals = {
    'absorption': True,  # Absorption zone detected
    'delta_divergence': {'strength': 0.8, 'type': 'bullish'},
    'liquidity_sweep': True,
    'cvd_divergence': {'strength': 0.6, 'type': 'bullish'},
    'vwap_deviation': 0.7  # 70% deviation
}

classifier = AIPatternClassifier()
result = classifier.classify_pattern(signals)

if result['meets_threshold']:
    # Pattern probability >= 75%, proceed with execution
    logger.info(f"Pattern classified: {result['pattern_type']} ({result['probability']:.1f}%)")
else:
    # Pattern probability < 75%, block execution
    logger.debug(f"Pattern probability too low: {result['probability']:.1f}% < {result['threshold']:.1f}%")
    return False
```

**Testing:**
- [ ] Test with various signal combinations
- [ ] Verify probability calculation
- [ ] Test threshold logic (75% minimum)
- [ ] Test with missing signals

---

### **Task 2.2: Real-Time Update Loop (Modified Approach)**

**Files to Modify:**
- `auto_execution_system.py` (modify `_monitor_loop()`)
- **New:** `infra/order_flow_plan_filter.py` (identify order-flow plans)

**Implementation:**
```python
# auto_execution_system.py - Modify _monitor_loop()
def _monitor_loop(self):
    """Main monitoring loop with order-flow high-frequency checks"""
    thread_name = threading.current_thread().name
    logger.info(f"Auto execution system monitoring loop started (thread: {thread_name})")
    
    last_order_flow_check = 0
    order_flow_check_interval = 5  # 5 seconds for order-flow plans
    
    try:
        while self.running:
            current_time = time.time()
            
            # High-frequency check for order-flow plans (every 5 seconds)
            if current_time - last_order_flow_check >= order_flow_check_interval:
                order_flow_plans = self._get_order_flow_plans()
                if order_flow_plans:
                    self._check_order_flow_plans_quick(order_flow_plans)
                last_order_flow_check = current_time
            
            # Standard check for all plans (every 30 seconds)
            # ... existing code ...
            
            time.sleep(1)  # Sleep 1 second, check conditions above
            
    except Exception as e:
        logger.error(f"Error in monitor loop: {e}", exc_info=True)

def _get_order_flow_plans(self) -> List[TradePlan]:
    """
    Get plans that have order flow conditions.
    
    Note: self.plans is a Dict[str, TradePlan], so iterate over .values()
    """
    order_flow_conditions = [
        "delta_positive", "delta_negative",
        "cvd_rising", "cvd_falling",
        "cvd_div_bear", "cvd_div_bull",
        "delta_divergence_bull", "delta_divergence_bear",
        "avoid_absorption_zones", "absorption_zone_detected"
    ]
    
    # self.plans is a dict, so iterate over values
    with self.plans_lock:  # Thread-safe access
        return [
            plan for plan in self.plans.values()  # ✅ Correct - iterate over dict values
            if plan.status == "pending" and  # Only check pending plans
            any(plan.conditions.get(cond) for cond in order_flow_conditions)
        ]

def _check_order_flow_plans_quick(self, plans: List[TradePlan]):
    """Quick check for order-flow plans (only order flow conditions)"""
    for plan in plans:
        try:
            # Only check order flow conditions (skip other validations for speed)
            if self._check_order_flow_conditions_only(plan):
                # If order flow conditions met, trigger full check
                if self._check_conditions(plan):
                    self._execute_plan(plan)
        except Exception as e:
            logger.debug(f"Error in quick order-flow check for {plan.plan_id}: {e}")

def _check_order_flow_conditions_only(self, plan: TradePlan) -> bool:
    """Check only order flow conditions (faster than full check)"""
    symbol_norm = plan.symbol.upper().rstrip('Cc')
    
    # Check BTC order flow conditions
    if symbol_norm.startswith('BTC'):
        # ... order flow condition checks only ...
        pass
    
    # Check proxy order flow conditions
    elif symbol_norm in ["XAUUSDc", "EURUSDc"]:
        # ... proxy order flow condition checks only ...
        pass
    
    return True  # If all order flow conditions met
```

**Integration:**
- `auto_execution_system.py`: Modify `_monitor_loop()` as shown above
- Keep existing 30-second full check for all plans

**Testing:**
- [ ] Verify 5-second checks for order-flow plans
- [ ] Verify 30-second checks for all plans
- [ ] Test latency (<1s per update)
- [ ] Test error handling and recovery

---

### **Phase 2 Deliverables:**
- [ ] Weighted confluence system implemented
- [ ] Real-time 5-second update loop working
- [ ] Pattern classification accuracy >75%
- [ ] Latency <1s per update
- [ ] Resource monitoring shows CPU +8-15%, RAM +30-50 MB

---

## 📋 **Phase 3: Enhanced Exit Management** (1 week)

**Impact:** CPU +2-4%, RAM +20-30 MB

### **Task 3.1: Order Flow Flip Exit**

**Files to Modify:**
- `infra/intelligent_exit_manager.py` (add order flow flip detection)
- `auto_execution_system.py` (store entry delta when executing trades)

**Implementation:**
```python
# infra/intelligent_exit_manager.py - Add to check_exits()
def check_exits(self, vix_price: Optional[float] = None) -> List[Dict[str, Any]]:
    """Check exits including order flow flip detection"""
    
    actions = []
    
    if not self.rules:
        return actions
    
    # Connect to MT5
    if not self.mt5.connect():
        logger.warning("MT5 not connected, skipping exit check")
        return actions
    
    # Get VIX if not provided
    if vix_price is None:
        vix_price = self._get_vix_price()
    
    # Get all open positions
    positions = self.mt5.get_positions()
    
    for ticket, rule in self.rules.items():
        position = next((p for p in positions if p.ticket == ticket), None)
        if not position:
            continue
        
        # NEW: Check order flow flip exit first (highest priority)
        if self.order_flow_service and self.order_flow_service.running:
            flip_exit = self._check_order_flow_flip(ticket, rule, position)
            if flip_exit:
                actions.append({
                    "ticket": ticket,
                    "action": "close",
                    "reason": "order_flow_flip",
                    "details": flip_exit,
                    "priority": "high"
                })
                continue  # Skip other exit checks if flip detected
        
        # ... existing exit logic (breakeven, partial, trailing) ...
    
    return actions

def _check_order_flow_flip(
    self, 
    ticket: int, 
    rule: ExitRule, 
    position: Dict
) -> Optional[Dict]:
    """
    Check if order flow has flipped (≥80% reversal).
    
    Args:
        ticket: Position ticket
        rule: ExitRule for position
        position: Position dict from MT5
    
    Returns:
        Dict with flip details or None if no flip
    """
    try:
        # Get entry delta (stored when position opened)
        # Option A: Use metadata field (if added to ExitRule)
        entry_delta = getattr(rule, 'metadata', {}).get("entry_delta")
        
        # Option B: Use advanced_gate field (if metadata not available)
        if entry_delta is None:
            entry_delta = rule.advanced_gate.get("entry_delta")
        
        # Option C: Use separate tracking dict in IntelligentExitManager
        if entry_delta is None and hasattr(self, 'entry_deltas'):
            entry_delta = self.entry_deltas.get(ticket)
        
        if entry_delta is None:
            return None  # No entry delta stored
        
        # Get current delta
        symbol = position.get("symbol", "")
        binance_symbol = self._convert_to_binance_symbol(symbol)
        
        if not binance_symbol:
            return None
        
        pressure_data = self.order_flow_service.get_buy_sell_pressure(
            binance_symbol, window=30
        )
        if not pressure_data:
            return None
        
        current_delta = pressure_data.get("net_volume", 0)
        
        # Calculate flip percentage
        direction = position.get("type", 0)  # 0=BUY, 1=SELL
        
        if direction == 0:  # BUY position
            # Exit if delta flips negative ≥80% of entry delta
            if entry_delta > 0:
                flip_threshold = -0.8 * entry_delta
                if current_delta <= flip_threshold:
                    flip_pct = abs((current_delta - entry_delta) / entry_delta) * 100
                    return {
                        "flip_detected": True,
                        "entry_delta": entry_delta,
                        "current_delta": current_delta,
                        "flip_percentage": flip_pct,
                        "threshold": 80.0
                    }
        else:  # SELL position
            # Exit if delta flips positive ≥80% of entry delta
            if entry_delta < 0:
                flip_threshold = 0.8 * abs(entry_delta)
                if current_delta >= flip_threshold:
                    flip_pct = abs((current_delta - entry_delta) / abs(entry_delta)) * 100
                    return {
                        "flip_detected": True,
                        "entry_delta": entry_delta,
                        "current_delta": current_delta,
                        "flip_percentage": flip_pct,
                        "threshold": 80.0
                    }
        
        return None
        
    except Exception as e:
        logger.debug(f"Error checking order flow flip for {ticket}: {e}")
        return None

def _convert_to_binance_symbol(self, mt5_symbol: str) -> Optional[str]:
    """Convert MT5 symbol to Binance symbol"""
    symbol_map = {
        "BTCUSDc": "BTCUSDT",
        "XAUUSDc": None,  # Not available on Binance
        "EURUSDc": None  # Not available on Binance
    }
    return symbol_map.get(mt5_symbol)
```

**Integration:**
- `auto_execution_system.py`: Store entry delta when executing trades (around line 6422)
- `infra/intelligent_exit_manager.py`: Add flip detection to `check_exits()`
- `infra/intelligent_exit_manager.py`: Add `metadata` field to `ExitRule` OR use `entry_deltas` dict

**Required Changes to ExitRule:**
```python
# infra/intelligent_exit_manager.py - Modify ExitRule.__init__()
def __init__(self, ...):
    # ... existing fields ...
    self.metadata: Dict[str, Any] = {}  # NEW: For storing entry_delta, etc.
    # OR use separate tracking dict in IntelligentExitManager:
    # self.entry_deltas: Dict[int, float] = {}  # ticket -> entry_delta
```

**Store Entry Delta:**
```python
# In auto_execution_system.py when executing trade (around line 6422)
def _execute_trade(self, plan: TradePlan) -> bool:
    """Execute trade plan and store entry delta"""
    # ... existing execution code ...
    
    # After successful execution (ticket obtained)
    if ticket:
        # Store entry delta for flip exit detection
        entry_delta = None
        
        if plan.symbol.upper().startswith('BTC'):
            if self.micro_scalp_engine and hasattr(self.micro_scalp_engine, 'btc_order_flow'):
                try:
                    btc_flow = self.micro_scalp_engine.btc_order_flow
                    metrics = btc_flow.get_metrics("BTCUSDT", window_seconds=30)
                    if metrics:
                        entry_delta = metrics.delta_volume
                except Exception as e:
                    logger.debug(f"Error getting entry delta: {e}")
        
        # Store entry delta in IntelligentExitManager
        if entry_delta is not None and self.intelligent_exit_manager:
            try:
                # Option A: Add metadata field to ExitRule (recommended)
                # First, get the exit rule (may need to add it if not exists)
                if hasattr(self.intelligent_exit_manager, 'rules'):
                    # Exit rule should already exist (created when position opened)
                    # Add entry_delta to metadata
                    if not hasattr(self.intelligent_exit_manager.rules.get(ticket), 'metadata'):
                        # Add metadata field if it doesn't exist
                        rule = self.intelligent_exit_manager.rules.get(ticket)
                        if rule:
                            rule.metadata = getattr(rule, 'metadata', {})
                            rule.metadata['entry_delta'] = entry_delta
                
                # Option B: Use separate tracking dict
                if not hasattr(self.intelligent_exit_manager, 'entry_deltas'):
                    self.intelligent_exit_manager.entry_deltas = {}
                self.intelligent_exit_manager.entry_deltas[ticket] = entry_delta
                
            except Exception as e:
                logger.debug(f"Error storing entry delta: {e}")
```

**Testing:**
- [ ] Test with various delta scenarios
- [ ] Verify 80% threshold logic
- [ ] Test with different position directions
- [ ] Test with missing entry delta (should not error, return None gracefully)
- [ ] Test with BTC positions (entry delta available)
- [ ] Test with non-BTC positions (entry delta may be None, should handle gracefully)

---

### **Task 3.2: Enhanced Absorption Zones**

**Files to Modify:**
- `infra/btc_order_flow_metrics.py` (enhance `_detect_absorption_zones()`)
- `auto_execution_system.py` (improve zone detection)

**Implementation:**
```python
# infra/btc_order_flow_metrics.py - Enhance _detect_absorption_zones()
def _detect_absorption_zones(self, symbol: str) -> List[Dict]:
    """Enhanced absorption zone detection with price movement tracking"""
    
    zones = []
    
    if not self.order_flow_service:
        return zones
    
    try:
        # Get order book data
        signal = self.order_flow_service.get_order_flow_signal(symbol)
        if not signal or not signal.get("order_book"):
            return zones
        
        order_book = signal["order_book"]
        imbalance = order_book.get("imbalance", 1.0)
        imbalance_pct = order_book.get("imbalance_pct", 0.0)
        
        # Get recent trade volume
        pressure_data = self.order_flow_service.get_buy_sell_pressure(symbol, window=60)
        if not pressure_data:
            return zones
        
        total_volume = pressure_data.get("buy_volume", 0) + pressure_data.get("sell_volume", 0)
        net_volume = pressure_data.get("net_volume", 0)
        
        # Get price movement (from order book or MT5)
        price_movement = self._get_price_movement(symbol, window=60)
        
        # Check if conditions indicate absorption
        # High volume + high imbalance + low price movement = absorption
        if total_volume >= self.absorption_threshold_volume:
            if abs(imbalance - 1.0) >= (self.absorption_threshold_imbalance - 1.0):
                # Check price movement (low movement = absorption)
                price_stall = True
                if price_movement:
                    atr = self._get_atr(symbol)
                    if atr and price_movement < (atr * 0.1):  # <10% of ATR
                        price_stall = True
                    else:
                        price_stall = False
                
                if price_stall:
                    best_prices = self.order_flow_service.analyzer.depth_analyzer.get_best_bid_ask(symbol)
                    if best_prices:
                        mid_price = (best_prices["bid"] + best_prices["ask"]) / 2
                        
                        # Calculate absorption strength
                        volume_score = min(1.0, total_volume / (self.absorption_threshold_volume * 2))
                        imbalance_score = min(1.0, abs(imbalance_pct) / 50.0)
                        price_stall_score = 1.0 if price_stall else 0.5
                        strength = (volume_score + imbalance_score + price_stall_score) / 3.0
                        
                        if strength >= 0.5:  # Minimum threshold
                            zones.append({
                                "price_level": mid_price,
                                "strength": strength,
                                "volume_absorbed": total_volume,
                                "net_volume": net_volume,
                                "imbalance_ratio": imbalance,
                                "imbalance_pct": imbalance_pct,
                                "price_movement": price_movement,
                                "side": "BUY" if net_volume > 0 else "SELL",
                                "timestamp": time.time()
                            })
        
        return zones
        
    except Exception as e:
        logger.error(f"Error detecting absorption zones for {symbol}: {e}", exc_info=True)
        return zones

def _get_price_movement(self, symbol: str, window: int) -> Optional[float]:
    """Get price movement over window (for absorption detection)"""
    try:
        # Get best bid/ask
        best_prices = self.order_flow_service.analyzer.depth_analyzer.get_best_bid_ask(symbol)
        if not best_prices:
            return None
        
        current_price = (best_prices["bid"] + best_prices["ask"]) / 2
        
        # TODO: Track price history for better accuracy
        # For now, return None (will use simplified detection)
        return None
        
    except Exception as e:
        logger.debug(f"Error getting price movement: {e}")
        return None

def _get_atr(self, symbol: str) -> Optional[float]:
    """Get ATR for symbol (for price movement normalization)"""
    # TODO: Get ATR from MT5 or cached analysis
    # For now, return None (will use fixed threshold)
    return None
```

**Integration:**
- `auto_execution_system.py` lines 3410-3452: Use enhanced zones
- Add price movement tracking to `BTCOrderFlowMetrics`

**Testing:**
- [ ] Test zone detection accuracy
- [ ] Verify price level vs range detection
- [ ] Test with various market conditions
- [ ] Test with missing price movement data (fallback)
- [ ] Test DataFrame handling (price bars from MT5)
- [ ] Test with missing ATR data (fallback to fixed threshold)

---

### **Phase 3 Deliverables:**
- [ ] Order flow flip exit implemented
- [ ] Enhanced absorption zones working
- [ ] Exit logic tested and validated
- [ ] Resource monitoring shows CPU +2-4%, RAM +20-30 MB

---

## 📋 **Phase 4: Optimization** (1 week)

**Impact:** May reduce CPU by 5-10% through optimization

### **Task 4.1: Performance Tuning**

**Optimization Strategies:**

1. **Cache Metrics:**
```python
# infra/btc_order_flow_metrics.py - Add caching
class BTCOrderFlowMetrics:
    def __init__(self, ...):
        # ... existing init ...
        self._metrics_cache = {}  # symbol -> (metrics, timestamp)
        self._cache_ttl = 5  # 5 seconds cache
    
    def get_metrics(self, symbol: str, window_seconds: int = 30) -> Optional[OrderFlowMetrics]:
        """Get metrics with caching"""
        cache_key = f"{symbol}_{window_seconds}"
        current_time = time.time()
        
        # Check cache
        if cache_key in self._metrics_cache:
            cached_metrics, cache_time = self._metrics_cache[cache_key]
            if current_time - cache_time < self._cache_ttl:
                return cached_metrics  # Return cached
        
        # Calculate metrics
        metrics = self._calculate_metrics(symbol, window_seconds)
        
        # Update cache
        if metrics:
            self._metrics_cache[cache_key] = (metrics, current_time)
        
        return metrics
```

2. **Batch Processing:**
```python
# Process multiple plans in one metrics call
def _batch_check_order_flow_conditions(self, plans: List[TradePlan]):
    """Batch check order flow conditions for multiple plans"""
    # Group plans by symbol
    plans_by_symbol = {}
    for plan in plans:
        symbol = plan.symbol
        if symbol not in plans_by_symbol:
            plans_by_symbol[symbol] = []
        plans_by_symbol[symbol].append(plan)
    
    # Get metrics once per symbol
    for symbol, symbol_plans in plans_by_symbol.items():
        metrics = self._get_metrics_for_symbol(symbol)
        for plan in symbol_plans:
            # Check conditions using cached metrics
            self._check_plan_with_metrics(plan, metrics)
```

3. **Async Where Possible:**
```python
# Use async for I/O operations
async def _get_metrics_async(self, symbol: str):
    """Async version of get_metrics for non-blocking calls"""
    # ... async implementation ...
```

4. **Memory Optimization:**
```python
# Use deques with maxlen (already done in most places)
self.tick_buffer = deque(maxlen=1000)  # Auto-cleanup old data
```

5. **Numba JIT:**
```python
# Use Numba for numeric calculations
from numba import jit

@jit(nopython=True, cache=True)
def calculate_trend_slope(values: np.ndarray) -> float:
    """Fast trend slope calculation"""
    # ... numba-optimized code ...
```

---

### **Task 4.2: Testing and Validation**

**Testing Requirements:**

1. **Unit Tests:**
   - [ ] Test tick-by-tick delta engine
   - [ ] Test CVD divergence detection
   - [ ] Test delta divergence detection
   - [ ] Test pattern classifier
   - [ ] Test order flow flip exit
   - [ ] Test absorption zone detection

2. **Integration Tests:**
   - [ ] Test full order flow condition checking
   - [ ] Test real-time update loop
   - [ ] Test exit management integration
   - [ ] Test proxy order flow integration

3. **Performance Tests:**
   - [ ] Benchmark CPU usage
   - [ ] Benchmark RAM usage
   - [ ] Benchmark latency
   - [ ] Test with 1000+ ticks/second

4. **Backtesting:**
   - [ ] Backtest with historical data
   - [ ] Validate pattern classification accuracy
   - [ ] Validate exit logic

5. **Paper Trading:**
   - [ ] Paper trade for 1-2 weeks
   - [ ] Monitor execution quality
   - [ ] Validate resource usage

---

### **Phase 4 Deliverables:**
- [ ] Performance optimizations applied
- [ ] All tests passing
- [ ] Backtesting completed
- [ ] Paper trading validated
- [ ] Resource usage optimized (CPU reduction if possible)

---

## 📋 **Proxy Order Flow Integration for XAUUSD/EURUSD**

### **Task: Integrate Proxy Order Flow (with Async Fix)**

**Files to Modify:**
- `auto_execution_system.py` (add proxy order flow checks)
- `auto_execution_system.py` `__init__` (initialize general metrics)

**Implementation:**
```python
# auto_execution_system.py - Add after BTC order flow checks (around line 3452)

# ============================================================================
# Phase 1.2: Proxy Order Flow Support for XAUUSD/EURUSD Plans
# ============================================================================
# Check proxy order flow conditions for non-BTC symbols
proxy_symbols = ["XAUUSDc", "EURUSDc", "GBPUSDc", "USDJPYc", "GBPJPYc", "EURJPYc"]

if symbol_norm in proxy_symbols:
    # Check if plan has proxy order flow conditions
    if (plan.conditions.get("cvd_rising") or 
        plan.conditions.get("cvd_falling") or
        plan.conditions.get("aggressor_ratio") or
        plan.conditions.get("imbalance_score")):
        
        try:
            # Initialize general metrics if not already done
            if not hasattr(self, '_general_order_flow_metrics'):
                from infra.general_order_flow_metrics import GeneralOrderFlowMetrics
                self._general_order_flow_metrics = GeneralOrderFlowMetrics(
                    mt5_service=self.mt5_service,
                    order_flow_service=None  # Not needed for proxy
                )
            
            # Get proxy metrics (async call in sync context)
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            try:
                metrics = loop.run_until_complete(
                    self._general_order_flow_metrics.get_order_flow_metrics(
                        symbol_norm, 
                        window_minutes=30
                    )
                )
            finally:
                # Don't close loop if it was already running
                try:
                    current_loop = asyncio.get_event_loop()
                    if loop != current_loop:
                        loop.close()
                except RuntimeError:
                    # No event loop running, safe to close
                    loop.close()
            
            if not metrics or metrics.get("data_quality") == "unavailable":
                logger.debug(f"Plan {plan.plan_id}: Proxy order flow unavailable")
                return False
            
            # Check CVD conditions
            if plan.conditions.get("cvd_rising"):
                if metrics.get("cvd_slope") != "up":
                    logger.debug(
                        f"Plan {plan.plan_id}: cvd_rising condition not met "
                        f"(slope: {metrics.get('cvd_slope')})"
                    )
                    return False
            
            if plan.conditions.get("cvd_falling"):
                if metrics.get("cvd_slope") != "down":
                    logger.debug(
                        f"Plan {plan.plan_id}: cvd_falling condition not met "
                        f"(slope: {metrics.get('cvd_slope')})"
                    )
                    return False
            
            # Check aggressor ratio (buy/sell pressure)
            aggressor_ratio = plan.conditions.get("aggressor_ratio")
            if aggressor_ratio is not None:
                current_ratio = metrics.get("aggressor_ratio")
                if current_ratio is None:
                    logger.debug(f"Plan {plan.plan_id}: aggressor_ratio unavailable")
                    return False
                
                # For BUY plans: require aggressor_ratio > threshold (buying pressure)
                # For SELL plans: require aggressor_ratio < 1/threshold (selling pressure)
                if plan.direction == "BUY":
                    if current_ratio < aggressor_ratio:
                        logger.debug(
                            f"Plan {plan.plan_id}: aggressor_ratio condition not met "
                            f"(current: {current_ratio:.2f}, required: >={aggressor_ratio:.2f})"
                        )
                        return False
                else:  # SELL
                    # For SELL: aggressor_ratio < 1 means selling pressure
                    # Invert threshold: if threshold=1.2, we want ratio < 1/1.2 = 0.83
                    required_ratio = 1.0 / aggressor_ratio if aggressor_ratio > 0 else 0.0
                    if current_ratio > required_ratio:
                        logger.debug(
                            f"Plan {plan.plan_id}: aggressor_ratio condition not met "
                            f"(current: {current_ratio:.2f}, required: <={required_ratio:.2f})"
                        )
                        return False
            
            # Check imbalance score
            min_imbalance = plan.conditions.get("imbalance_score")
            if min_imbalance is not None:
                current_imbalance = metrics.get("imbalance_score", 0)
                if current_imbalance < min_imbalance:
                    logger.debug(
                        f"Plan {plan.plan_id}: imbalance_score condition not met "
                        f"(current: {current_imbalance}, required: >={min_imbalance})"
                    )
                    return False
                    
        except Exception as e:
            logger.debug(f"Error checking proxy order flow for {plan.plan_id}: {e}")
            return False
```

**Integration Points:**
- `auto_execution_system.py` lines ~3452: Add after BTC order flow checks
- `auto_execution_system.py` `__init__`: Initialize `_general_order_flow_metrics` lazily

**Supported Proxy Conditions for XAUUSD/EURUSD:**
```python
# Example plan conditions
{
    "cvd_rising": true,              # CVD slope = "up"
    "cvd_falling": true,             # CVD slope = "down"
    "aggressor_ratio": 1.2,          # Buying pressure > 1.2x selling
    "imbalance_score": 60,           # Market imbalance >= 60%
    "price_near": 4500.0,
    "tolerance": 5.0
}
```

**Testing:**
- [ ] Test with XAUUSD plans
- [ ] Test with EURUSD plans
- [ ] Verify proxy metrics are retrieved correctly
- [ ] Test condition validation logic
- [ ] Test async handling (no blocking)

---

## ✅ **Success Criteria**

### **Pre-Phase 0:**
- [ ] API bug fixed (get_delta_volume/get_cvd_trend)
- [ ] Delta checks working correctly
- [ ] CVD trend checks working correctly
- [ ] No performance degradation

### **Phase 1:**
- [ ] Tick-by-tick delta processing working
- [ ] CVD divergence detection accuracy >80%
- [ ] Delta divergence detection implemented
- [ ] CPU usage within +8-13% target
- [ ] RAM usage within +40-60 MB target

### **Phase 2:**
- [ ] Pattern classification accuracy >75%
- [ ] Real-time updates every 5 seconds
- [ ] Latency <1s per update
- [ ] CPU usage within +8-15% target
- [ ] RAM usage within +30-50 MB target

### **Phase 3:**
- [ ] Order flow flip exit working
- [ ] Absorption zone detection improved
- [ ] Exit logic validated
- [ ] CPU usage within +2-4% target
- [ ] RAM usage within +20-30 MB target

### **Phase 4:**
- [ ] Performance optimizations applied
- [ ] All tests passing
- [ ] Backtesting completed
- [ ] Paper trading validated
- [ ] Resource usage optimized

### **Proxy Integration:**
- [ ] XAUUSD plans can use proxy order flow conditions
- [ ] EURUSD plans can use proxy order flow conditions
- [ ] Proxy metrics retrieved correctly
- [ ] Condition validation working
- [ ] Async handling working (no blocking)

---

## 📅 **Timeline**

| Phase | Duration | Start | End |
|-------|----------|-------|-----|
| **Pre-Phase 0** | 1-2 days | Day 1 | Day 2 |
| **Phase 1** | 1-2 weeks | Day 3 | Day 16 |
| **Phase 2** | 1-2 weeks | Day 17 | Day 30 |
| **Phase 3** | 1 week | Day 31 | Day 37 |
| **Phase 4** | 1 week | Day 38 | Day 44 |
| **Total** | 4-6 weeks | Day 1 | Day 44 |

---

## 📊 **Resource Monitoring**

### **Monitoring Tools**

**CPU Monitoring:**
```python
# scripts/monitor_resources.py
import psutil
import time
import logging

logger = logging.getLogger(__name__)

def monitor_resources():
    """Monitor system resources during implementation"""
    process = psutil.Process()
    
    baseline_cpu = process.cpu_percent(interval=1)
    baseline_memory = process.memory_info().rss / 1024 / 1024
    
    logger.info(f"Baseline - CPU: {baseline_cpu:.1f}%, RAM: {baseline_memory:.1f} MB")
    
    while True:
        cpu_percent = process.cpu_percent(interval=1)
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        cpu_delta = cpu_percent - baseline_cpu
        memory_delta = memory_mb - baseline_memory
        
        logger.info(
            f"Current - CPU: {cpu_percent:.1f}% (+{cpu_delta:.1f}%), "
            f"RAM: {memory_mb:.1f} MB (+{memory_delta:.1f} MB)"
        )
        
        time.sleep(5)
```

**Latency Monitoring:**
```python
# In auto_execution_system.py
import time

def _check_order_flow_plans_quick(self, plans: List[TradePlan]):
    """Quick check with latency monitoring"""
    start_time = time.time()
    
    for plan in plans:
        # ... check conditions ...
    
    elapsed = time.time() - start_time
    if elapsed > 1.0:  # Warn if >1s
        logger.warning(f"Order flow check took {elapsed:.2f}s (target: <1s)")
```

---

## 🔍 **Risk Mitigation**

### **Risks and Mitigations:**

1. **Risk: API Changes Break Existing Code**
   - **Mitigation:** Fix Pre-Phase 0 bugs first, test thoroughly
   - **Impact:** High if not fixed

2. **Risk: Resource Usage Exceeds Estimates**
   - **Mitigation:** Monitor continuously, optimize in Phase 4
   - **Impact:** Medium - can scale back if needed

3. **Risk: Async/Sync Issues Cause Blocking**
   - **Mitigation:** Use proper async handling, test thoroughly
   - **Impact:** Medium - can cause performance issues

4. **Risk: Tick-by-Tick Processing Overloads System**
   - **Mitigation:** Use bounded buffers (deques with maxlen), optimize processing
   - **Impact:** Low - buffers are bounded

5. **Risk: Proxy Order Flow Accuracy Issues**
   - **Mitigation:** Document limitations, use conservative thresholds
   - **Impact:** Low - proxy is fallback, not primary

---

## 🔍 **Additional Issues Found and Fixed**

### **Issue 4: MT5 get_bars Returns DataFrame, Not List of Dicts** ⚠️
- **Problem:** Plan assumes `List[Dict]`, but returns `pandas.DataFrame`
- **Fix:** Convert DataFrame to list or work with DataFrame directly
- **Impact:** Medium - affects all price bar processing

### **Issue 5: Tick Data Source Clarification** ⚠️
- **Problem:** "Tick-by-tick" is misleading - Binance aggTrades are aggregated
- **Fix:** Rename to "AggTrade-by-AggTrade" or "Real-Time Delta"
- **Impact:** Low - terminology only

### **Issue 6: Entry Delta Storage Location** ⚠️
- **Problem:** `ExitRule` doesn't have `metadata` field
- **Fix:** Add `metadata` field to `ExitRule` OR use separate tracking dict
- **Impact:** Medium - affects flip exit implementation

### **Issue 7: self.plans is Dict, Not List** ⚠️
- **Problem:** Code assumes list, but it's `Dict[str, TradePlan]`
- **Fix:** Use `self.plans.values()` instead of `self.plans`
- **Impact:** Medium - affects plan filtering

### **Issue 8: MT5 Service Parameter Missing** ⚠️
- **Problem:** `BTCOrderFlowMetrics` doesn't have `mt5_service` parameter
- **Fix:** Add `mt5_service` to `__init__()` and pass from `micro_scalp_engine`
- **Impact:** High - required for price bar alignment

### **Issue 9: GeneralOrderFlowMetrics Uses run_in_executor** ⚠️
- **Problem:** Already uses `run_in_executor()` internally, but wrapper is async
- **Fix:** Proper async handling in sync context
- **Impact:** Medium - affects proxy integration

### **Issue 10: Price Bar Format in Divergence Detection** ⚠️
- **Problem:** Code accesses as dict, but DataFrame requires different access
- **Fix:** Convert DataFrame to list OR work with DataFrame directly
- **Impact:** Medium - affects divergence detection

### **Issue 11: CVD History Alignment** ⚠️
- **Problem:** CVD bars and price bars may have different timestamps
- **Fix:** Simplified 1:1 alignment (assume both are 1-minute bars)
- **Impact:** Low - simplified alignment acceptable for initial implementation

### **Issue 12: Missing Error Handling** ⚠️
- **Problem:** Several code examples lack proper try/except blocks
- **Fix:** Add comprehensive error handling throughout
- **Impact:** Medium - affects robustness

---

## 📝 **Notes**

1. **Start with Pre-Phase 0** - Critical bugs must be fixed first
2. **Test after each phase** - Don't proceed until phase is validated
3. **Monitor resources continuously** - Adjust if usage exceeds estimates
4. **Use paper trading** - Test thoroughly before live trading
5. **Document changes** - Keep track of all modifications
6. **Handle DataFrame format** - MT5 returns DataFrames, not lists
7. **Clarify data sources** - Binance aggTrades are aggregated, not true ticks
8. **Add metadata field** - ExitRule needs metadata for entry_delta storage
9. **Use dict.values()** - self.plans is a dict, iterate over values
10. **Add mt5_service parameter** - BTCOrderFlowMetrics needs MT5 service

---

## 🎯 **Summary**

This refined plan provides a structured approach to implementing AI Order-Flow Scalping with:

- ✅ **Critical bug fixes** identified and documented (12 issues found)
- ✅ **Proper async/sync handling** for proxy integration
- ✅ **DataFrame handling** for MT5 price bars (not list of dicts)
- ✅ **Entry delta storage** solution (metadata field or tracking dict)
- ✅ **Realistic resource estimates** with monitoring
- ✅ **Comprehensive testing requirements**
- ✅ **Proxy order flow support** for XAUUSD/EURUSD
- ✅ **Clear timeline and deliverables**
- ✅ **All integration points** clarified and documented

**Issues Fixed:**
1. ✅ API mismatch (7 instances: get_delta_volume/get_cvd_trend/get_absorption_zones don't exist)
   - Lines 3216-3217: Order block validation
   - Line 3245: Order block absorption zones
   - Line 3305: Delta positive condition
   - Line 3325: CVD rising/falling condition
   - Line 3387: Delta divergence bull condition
   - Line 3402: Delta divergence bear condition
2. ✅ Async/sync handling for proxy integration
3. ✅ Real-time update loop clarification
4. ✅ MT5 DataFrame format handling
5. ✅ Tick data source clarification (aggTrades, not true ticks)
6. ✅ Entry delta storage location
7. ✅ self.plans dict structure
8. ✅ MT5 service parameter missing
9. ✅ GeneralOrderFlowMetrics async handling
10. ✅ Price bar format in divergence detection
11. ✅ CVD history alignment
12. ✅ Missing error handling

**Next Steps:**
1. Fix Pre-Phase 0 bugs (API mismatch) - **CRITICAL** - Fix ALL 7 instances
2. Add `metadata` field to `ExitRule` OR use tracking dict
3. Add `mt5_service` parameter to `BTCOrderFlowMetrics`
4. Begin Phase 1 implementation
5. Monitor resources continuously
6. Test thoroughly at each phase

**Critical Bug Details:**
- **Issue 1:** 7 instances of non-existent API calls found:
  - `get_delta_volume()` - 5 instances (lines 3216, 3305, 3387, 3402)
  - `get_cvd_trend()` - 2 instances (lines 3217, 3325)
  - `get_absorption_zones()` - 1 instance (line 3245)
- **All 7 instances must be fixed** before Phase 1 implementation
- **Solution:** Use `get_metrics()` helper method for all order flow data access

---

**Status:** Ready for implementation (all issues identified and fixed)  
**Last Updated:** 2025-12-31  
**Total Issues Found:** 12 (3 critical, 9 important)  
**Critical Bug Instances:** 7 API mismatch bugs found and documented  
**Critical Bug Instances:** 7 API mismatch bugs found and documented

---

## 📚 **Quick Reference: Code Patterns**

### **Pattern 1: Get Metrics from BTCOrderFlowMetrics**
```python
# ✅ CORRECT
metrics = btc_flow.get_metrics("BTCUSDT", window_seconds=300)
delta = metrics.delta_volume
cvd_slope = metrics.cvd_slope
cvd_trend = 'rising' if metrics.cvd_slope > 0 else 'falling' if metrics.cvd_slope < 0 else 'flat'

# ❌ WRONG (methods don't exist)
delta = btc_flow.get_delta_volume()  # ❌
cvd_trend = btc_flow.get_cvd_trend()  # ❌
```

### **Pattern 2: Handle MT5 DataFrame**
```python
# ✅ CORRECT
m1_bars_df = mt5_service.get_bars(symbol, "M1", 50)  # Returns DataFrame
price_highs = m1_bars_df['high'].values[-20:]  # Access as DataFrame
# OR convert to list:
price_bars = [{'high': float(row['high']), ...} for _, row in m1_bars_df.iterrows()]

# ❌ WRONG
price_highs = [bar['high'] for bar in m1_bars]  # ❌ Assumes list of dicts
```

### **Pattern 3: Async Call in Sync Context**
```python
# ✅ CORRECT
import asyncio
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    metrics = loop.run_until_complete(
        general_metrics.get_order_flow_metrics(symbol, 30)
    )
finally:
    loop.close()
    asyncio.set_event_loop(None)
```

### **Pattern 4: Iterate Over self.plans**
```python
# ✅ CORRECT (self.plans is Dict[str, TradePlan])
with self.plans_lock:
    plans_list = list(self.plans.values())  # Convert dict values to list
    for plan in plans_list:
        # ... process plan ...

# ❌ WRONG
for plan in self.plans:  # ❌ Iterates over keys, not values
    pass
```

### **Pattern 5: Store Entry Delta**
```python
# ✅ CORRECT (Option A: Add metadata field)
rule.metadata = getattr(rule, 'metadata', {})
rule.metadata['entry_delta'] = entry_delta

# ✅ CORRECT (Option B: Use tracking dict)
if not hasattr(exit_manager, 'entry_deltas'):
    exit_manager.entry_deltas = {}
exit_manager.entry_deltas[ticket] = entry_delta
```

---

## ✅ **Implementation Checklist**

### **Pre-Phase 0 (MUST DO FIRST):**
- [ ] Fix API bug: Replace ALL 7 instances of `get_delta_volume()`/`get_cvd_trend()`/`get_absorption_zones()` with `get_metrics()`
  - [ ] Line 3216-3217: Order block validation
  - [ ] Line 3245: Order block absorption zones
  - [ ] Line 3305: Delta positive condition
  - [ ] Line 3325: CVD rising/falling condition
  - [ ] Line 3387: Delta divergence bull condition
  - [ ] Line 3402: Delta divergence bear condition
  - [ ] Line 3422: Absorption zones check (verify already correct)
- [ ] Add helper method `_get_btc_order_flow_metrics()` for code reuse
- [ ] Test delta checks work correctly
- [ ] Test CVD trend checks work correctly
- [ ] Test absorption zone checks work correctly
- [ ] Verify no performance degradation

### **Before Phase 1:**
- [ ] Add `mt5_service` parameter to `BTCOrderFlowMetrics.__init__()`
- [ ] Update `micro_scalp_engine.py` to pass `mt5_service` to `BTCOrderFlowMetrics`
- [ ] Add `metadata` field to `ExitRule` OR create `entry_deltas` tracking dict
- [ ] Test MT5 DataFrame handling in test script

### **During Phase 1:**
- [ ] Implement tick-by-tick delta engine (using aggTrades, not true ticks)
- [ ] Implement enhanced CVD divergence (handle DataFrame format)
- [ ] Implement delta divergence detection (handle DataFrame format)
- [ ] Test all divergence detection with real data

### **During Phase 2:**
- [ ] Implement pattern classifier
- [ ] Modify `_monitor_loop()` for 5-second checks
- [ ] Test pattern classification accuracy
- [ ] Verify latency <1s

### **During Phase 3:**
- [ ] Implement order flow flip exit
- [ ] Store entry delta when executing trades
- [ ] Enhance absorption zones
- [ ] Test exit logic

### **During Phase 4:**
- [ ] Add caching to `get_metrics()`
- [ ] Optimize performance
- [ ] Run comprehensive tests
- [ ] Paper trade validation

### **Proxy Integration:**
- [ ] Add proxy order flow checks to `_check_conditions()`
- [ ] Test async handling (no blocking)
- [ ] Test with XAUUSD/EURUSD plans
- [ ] Verify condition validation works

---

**Status:** Ready for implementation (all issues identified and fixed)  
**Last Updated:** 2025-12-31  
**Total Issues Found:** 12 (3 critical, 9 important)  
**Critical Bug Instances:** 7 API mismatch bugs found and documented
