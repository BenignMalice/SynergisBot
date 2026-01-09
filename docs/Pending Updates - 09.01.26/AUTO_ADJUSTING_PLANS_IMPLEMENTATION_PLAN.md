# Auto-Adjusting Plans (Proximity-Tracking) Implementation Plan

**Date:** 2026-01-10  
**Status:** 📋 **PLANNING COMPLETE - READY FOR IMPLEMENTATION**  
**Priority:** **MEDIUM** - Enhances plan execution quality and reduces stale plan issues  
**Estimated Time:** 20-30 hours (across 5 phases)

---

## 🎯 **Objectives**

1. **Implement reactive drift detection**: Automatically re-anchor plans when price drifts beyond threshold
2. **Add bias invalidation fence**: Prevent plans from following price into structurally invalid zones
3. **Implement strategy-specific SL/TP adaptation**: Dynamic stop-loss and take-profit adjustments based on strategy type
4. **Add predictive drift modeling**: Pre-emptive re-anchoring during expansion phases (Phase 3 only)
5. **Implement multi-factor adaptation**: Combine symbol, regime, and session context for optimal SL/TP scaling
6. **Enable hybrid approach**: Allow plans to opt-in/opt-out of proximity tracking via flag

---

## 📊 **Current System Analysis**

### **Existing Infrastructure (80-85% Ready)**

✅ **Already Available:**
- Real-time market snapshots via `getCurrentPrice()` (every 15-60 seconds)
- Active auto-plan update system (`update_multiple_auto_plans`, `update_plan`)
- Order flow engine (CVD, delta, tick variance detection)
- Volatility tracking (ATR, RMAG, volatility regime detection)
- Hybrid trailing and SL/TP maintenance
- Multi-timeframe analysis (H1/H4 bias detection)
- Phase detection engine (Phases 1-6 recognition)
- 15-second monitoring interval (recently optimized)
- Price caching system (LRU cache with 5s TTL)

❌ **Missing Components:**
- Drift monitoring daemon/loop
- Re-anchor logic (automatic entry recalculation)
- Anchor state persistence (store latest anchor values)
- Bias invalidation fence (HTF bias validation)
- Strategy-specific SL/TP adaptation logic
- Predictive drift modeling
- Multi-factor adaptation engine
- Proximity tracking flag per plan

### **Current Plan Update Flow**

**Location:** `auto_execution_system.py` → `_monitor_loop()` (line ~10825)

**Current Behavior:**
```
_monitor_loop() runs every 15 seconds:
  1. For each pending plan:
     - Check expiration
     - Check cancellation conditions
     - Check if conditions are met (_check_conditions)
     - If conditions met → _execute_trade() → executes immediately
     - Plan status → "executed"
     - Remove plan from memory
```

**Required Changes:**
- ⚠️ **NEW**: Add drift detection check before condition checking
- ⚠️ **NEW**: Re-anchor plans when drift > threshold (if proximity_tracking_enabled)
- ⚠️ **NEW**: Validate HTF bias before re-anchoring (bias invalidation fence)
- ⚠️ **NEW**: Adjust SL/TP proportionally during re-anchoring
- ⚠️ **NEW**: Store anchor state for each proximity-tracking plan

---

## 🏗️ **Implementation Phases**

### **Phase 1: Reactive Drift Detection**

**Objective:** Implement basic drift detection and re-anchoring when price moves beyond threshold

**Estimated Time:** 4-6 hours

#### **1.1 Add Proximity Tracking Fields to TradePlan**

**File:** `auto_execution_system.py`

**Location:** `TradePlan` dataclass (line ~27)

**New Fields:**
```python
proximity_tracking_enabled: Optional[bool] = False  # Opt-in flag
anchor_price: Optional[float] = None  # Current anchor (VWAP/microstructure reference)
anchor_type: Optional[str] = None  # "vwap", "swing", "tick_mean"
drift_threshold: Optional[float] = None  # Symbol-specific threshold (40 pts BTC, 0.4 pts XAU)
last_anchor_update: Optional[str] = None  # Timestamp of last re-anchoring
anchor_update_count: Optional[int] = 0  # Total updates (for rate limiting)
```

**Database Migration:**
- Add columns to `trade_plans` table in `_init_database()`:
  ```sql
  ALTER TABLE trade_plans ADD COLUMN proximity_tracking_enabled INTEGER DEFAULT 0;
  ALTER TABLE trade_plans ADD COLUMN anchor_price REAL;
  ALTER TABLE trade_plans ADD COLUMN anchor_type TEXT;
  ALTER TABLE trade_plans ADD COLUMN drift_threshold REAL;
  ALTER TABLE trade_plans ADD COLUMN last_anchor_update TEXT;
  ALTER TABLE trade_plans ADD COLUMN anchor_update_count INTEGER DEFAULT 0;
  ```

#### **1.2 Add Drift Detection Method**

**File:** `auto_execution_system.py`

**New Method:** `_check_drift_and_reanchor(plan: TradePlan) -> bool`
- Check if `proximity_tracking_enabled == True`
- Get current price via `getCurrentPrice()` or cached price
- Calculate drift: `abs(current_price - plan.anchor_price)`
- If drift > `plan.drift_threshold`:
  - Call `_recalculate_anchor(plan)` to compute new anchor
  - Call `_reanchor_plan(plan, new_anchor)` to update entry/SL/TP
  - Update `last_anchor_update` and increment `anchor_update_count`
- Return `True` if re-anchored, `False` otherwise

**Location:** Add before `_monitor_loop()` method (around line 10800)

#### **1.3 Add Anchor Recalculation Method**

**File:** `auto_execution_system.py`

**New Method:** `_recalculate_anchor(plan: TradePlan) -> float`
- Determine anchor type (default: VWAP if not specified)
- **VWAP anchor**: Get VWAP from `multi_timeframe_analyzer` or cached data
- **Swing anchor**: Use last 3 swing pivots (microstructure inflection)
- **Tick-mean anchor**: Use tick-volume weighted mean (if available)
- Return new anchor price

**Location:** Add after `_check_drift_and_reanchor()` method

#### **1.4 Add Re-anchoring Method**

**File:** `auto_execution_system.py`

**New Method:** `_reanchor_plan(plan: TradePlan, new_anchor: float) -> bool`
- Calculate entry offset from original plan: `original_offset = plan.entry_price - plan.anchor_price`
- New entry: `new_entry = new_anchor + original_offset`
- Calculate SL/TP offsets: `sl_offset = plan.entry_price - plan.stop_loss`, `tp_offset = plan.take_profit - plan.entry_price`
- New SL: `new_sl = new_entry - sl_offset`
- New TP: `new_tp = new_entry + tp_offset`
- Preserve R:R ratio (validate: `(new_tp - new_entry) / (new_entry - new_sl) ≈ original R:R`)
- Update plan via `update_plan()`:
  - `entry_price = new_entry`
  - `stop_loss = new_sl`
  - `take_profit = new_tp`
  - `anchor_price = new_anchor`
- Return `True` if successful

**Location:** Add after `_recalculate_anchor()` method

#### **1.5 Integrate Drift Check into Monitoring Loop**

**File:** `auto_execution_system.py`

**Location:** `_monitor_loop()` method (around line 10825)

**Changes:**
- Before condition checking, add:
  ```python
  # Check drift and re-anchor if needed (Phase 1)
  if plan.proximity_tracking_enabled:
      if self._check_drift_and_reanchor(plan):
          logger.info(f"Plan {plan.plan_id} re-anchored due to drift")
          # Continue to condition check with updated entry
  ```

#### **1.6 Add Symbol-Specific Drift Thresholds**

**File:** `auto_execution_system.py`

**New Method:** `_get_drift_threshold(symbol: str) -> float`
- Return default thresholds:
  - BTCUSDc: 40.0 points
  - XAUUSDc: 0.4 points
  - EURUSDc: 0.0003
  - GBPUSDc: 0.0004
  - USDJPYc: 0.03
  - Default: 0.5% of current price

**Location:** Add in `__init__` or as static method

#### **1.7 Update Plan Creation to Support Proximity Tracking**

**File:** `auto_execution_system.py`

**Location:** `add_plan()` method (line ~1551)

**Changes:**
- If `conditions.get("proximity_tracking_enabled") == True`:
  - Set `plan.proximity_tracking_enabled = True`
  - Initialize `plan.anchor_price = plan.entry_price` (or get VWAP if specified)
  - Set `plan.drift_threshold = self._get_drift_threshold(plan.symbol)`
  - Set `plan.anchor_type = conditions.get("anchor_type", "vwap")`

#### **1.8 Add Rate Limiting for Anchor Updates**

**File:** `auto_execution_system.py`

**Location:** `_check_drift_and_reanchor()` method

**Rate Limiting Logic:**
- Max updates per hour: 10 (configurable)
- Check: `if plan.anchor_update_count >= 10 and (now - last_update) < 3600 seconds`:
  - Skip re-anchoring, log warning
  - Reset counter after 1 hour

**Checklist:**
- [ ] Add proximity tracking fields to `TradePlan` dataclass
- [ ] Add database migration for new columns
- [ ] Implement `_check_drift_and_reanchor()` method
- [ ] Implement `_recalculate_anchor()` method (VWAP, swing, tick-mean)
- [ ] Implement `_reanchor_plan()` method (preserve R:R ratio)
- [ ] Add `_get_drift_threshold()` for symbol-specific thresholds
- [ ] Integrate drift check into `_monitor_loop()` (before condition checking)
- [ ] Update `add_plan()` to initialize proximity tracking fields
- [ ] Add rate limiting (max 10 updates/hour per plan)
- [ ] Add unit tests for drift detection and re-anchoring
- [ ] Add integration tests for full re-anchoring flow

**Testing:**
- Unit tests: `tests/test_phase1_reactive_drift.py`
  - Test drift detection (drift > threshold triggers re-anchor)
  - Test drift detection (drift < threshold no action)
  - Test anchor recalculation (VWAP, swing, tick-mean)
  - Test re-anchoring preserves R:R ratio
  - Test rate limiting (max 10 updates/hour)
  - Test symbol-specific drift thresholds

---

### **Phase 2: Bias Invalidation Fence**

**Objective:** Prevent plans from re-anchoring across higher-timeframe bias boundaries

**Estimated Time:** 3-4 hours

#### **2.1 Add Bias Detection Method**

**File:** `auto_execution_system.py`

**New Method:** `_get_htf_bias(symbol: str) -> str`
- Get H1 bias from `multi_timeframe_analyzer`
- Get H4 bias from `multi_timeframe_analyzer`
- Get VWAP side (above/below current price)
- Use majority vote: `majority_vote_bias()`
  - If 2+ of 3 are BULLISH → return "BUY"
  - If 2+ of 3 are BEARISH → return "SELL"
  - Otherwise → return "NEUTRAL"
- Cache result for 60 seconds (avoid redundant calls)

**Location:** Add after `_reanchor_plan()` method

#### **2.2 Add Bias Invalidation Check**

**File:** `auto_execution_system.py`

**New Method:** `_check_bias_invalidation(plan: TradePlan) -> tuple[bool, str]`
- Get HTF bias: `htf_bias = self._get_htf_bias(plan.symbol)`
- Map plan direction to bias: `plan_bias = "BUY" if plan.direction == "BUY" else "SELL"`
- Check if HTF bias opposes plan direction:
  - If `htf_bias != plan_bias` and `htf_bias != "NEUTRAL"`:
    - Return `(True, "Bias Invalidation Fence Triggered")`
- Return `(False, "")` if bias aligned

**Location:** Add after `_get_htf_bias()` method

#### **2.3 Add Plan Suspension/Re-arm Logic**

**File:** `auto_execution_system.py`

**New Fields in TradePlan:**
```python
plan_state: Optional[str] = "ACTIVE"  # ACTIVE, SUSPENDED, RE_ARMED
suspend_until: Optional[str] = None  # Timestamp when suspension expires
suspend_reason: Optional[str] = None  # Reason for suspension
```

**New Method:** `_handle_bias_invalidation(plan: TradePlan) -> bool`
- Check bias invalidation: `is_invalid, reason = self._check_bias_invalidation(plan)`
- If invalid:
  - Set `plan.plan_state = "SUSPENDED"`
  - Set `plan.suspend_until = now + timedelta(minutes=15)` (cooldown)
  - Set `plan.suspend_reason = reason`
  - Log suspension
  - Return `True` (plan suspended)
- If plan is SUSPENDED and cooldown expired:
  - Check if bias re-aligned: `htf_bias == plan_bias`
  - Check local confluence: `confluence_score >= 75` (if available)
  - If both true:
    - Set `plan.plan_state = "ACTIVE"`
    - Set `plan.suspend_reason = "Bias Re-aligned"`
    - Log re-arm
    - Return `False` (plan reactivated)
- Return `False` (plan active)

**Location:** Add after `_check_bias_invalidation()` method

#### **2.4 Add Hysteresis for Bias Flips**

**File:** `auto_execution_system.py`

**New Fields in TradePlan:**
```python
bias_flip_count: Optional[int] = 0  # Consecutive opposite-bias candles
last_bias_check: Optional[str] = None  # Last bias check timestamp
```

**Update `_check_bias_invalidation()`:**
- Track consecutive opposite-bias candles (require 2 consecutive HTF closes)
- OR: If decisive impulse (BOS + ATR > 1.5× baseline) → immediate suspension
- Prevent false triggers during VWAP whipsaws

#### **2.5 Integrate Bias Check into Re-anchoring**

**File:** `auto_execution_system.py`

**Location:** `_check_drift_and_reanchor()` method

**Changes:**
- Before re-anchoring, check bias:
  ```python
  # Check bias invalidation fence (Phase 2)
  if self._handle_bias_invalidation(plan):
      logger.warning(f"Plan {plan.plan_id} suspended due to bias invalidation")
      return False  # Don't re-anchor if suspended
  ```

#### **2.6 Update Monitoring Loop to Skip Suspended Plans**

**File:** `auto_execution_system.py`

**Location:** `_monitor_loop()` method

**Changes:**
- Skip condition checking for suspended plans:
  ```python
  if plan.plan_state == "SUSPENDED":
      # Check if cooldown expired and can re-arm
      self._handle_bias_invalidation(plan)
      continue  # Skip this plan
  ```

**Checklist:**
- [ ] Implement `_get_htf_bias()` with majority vote (H1, H4, VWAP)
- [ ] Implement `_check_bias_invalidation()` method
- [ ] Implement `_handle_bias_invalidation()` with suspension/re-arm logic
- [ ] Add hysteresis for bias flips (2 consecutive candles or decisive impulse)
- [ ] Add `plan_state`, `suspend_until`, `suspend_reason` fields to TradePlan
- [ ] Add database migration for new fields
- [ ] Integrate bias check into `_check_drift_and_reanchor()` (before re-anchoring)
- [ ] Update `_monitor_loop()` to skip suspended plans
- [ ] Add unit tests for bias detection and suspension logic
- [ ] Add integration tests for suspension and re-arm flow

**Testing:**
- Unit tests: `tests/test_phase2_bias_invalidation.py`
  - Test majority vote bias calculation
  - Test bias invalidation detection (opposing bias triggers suspension)
  - Test bias alignment (same bias allows re-anchoring)
  - Test suspension cooldown (15-minute cooldown enforced)
  - Test re-arm logic (bias re-aligned + confluence → reactivate)
  - Test hysteresis (2 consecutive candles required, or decisive impulse)

---

### **Phase 3: Strategy-Specific SL/TP Adaptation**

**Objective:** Implement dynamic SL/TP adjustments based on strategy type and volatility

**Estimated Time:** 5-6 hours

#### **3.1 Add Strategy Type Detection**

**File:** `auto_execution_system.py`

**New Method:** `_detect_strategy_type(plan: TradePlan) -> str`
- Analyze plan conditions to determine strategy:
  - Order Block Rejection (OBR): `order_block` condition present
  - Breaker Block (BB): `breaker` condition present
  - Liquidity Sweep Reversal (LSR): `liquidity_sweep` condition present
  - FVG Retracement: `fair_value_gap` condition present
  - Trend Continuation Pullback (TCP): `bos` + `trend_continuation` conditions
  - Mean Reversion / Range Scalp (MRS): `range_bound` or `vwap_mean_reversion` conditions
  - Session Liquidity Run (SLR): `session_liquidity` condition present
  - Premium/Discount Array (PDA): `fibonacci` or `premium_discount` conditions
  - Breaker / Inducement Combo (BIC): `breaker` + `inducement` conditions
- Return strategy type string or "default"

**Location:** Add after `_handle_bias_invalidation()` method

#### **3.2 Add Strategy-Specific Elasticity Parameters**

**File:** `auto_execution_system.py`

**New Method:** `_get_strategy_elasticity(strategy_type: str) -> tuple[float, float]`
- Return (alpha, beta) for SL and TP elasticity:
  ```python
  ELASTICITY_MAP = {
      "order_block_rejection": (0.6, 0.8),
      "breaker_block": (0.4, 0.6),
      "liquidity_sweep_reversal": (0.5, 0.9),
      "fvg_retracement": (0.7, 1.0),
      "trend_continuation_pullback": (0.3, 1.2),
      "mean_reversion_range_scalp": (0.9, 0.9),
      "session_liquidity_run": (0.5, 0.8),
      "premium_discount_array": (0.6, 0.7),
      "breaker_inducement_combo": (0.5, 1.0),
      "default": (0.5, 0.8)
  }
  ```
- Return tuple (alpha, beta)

**Location:** Add after `_detect_strategy_type()` method

#### **3.3 Add Volatility-Modulated SL/TP Calculation**

**File:** `auto_execution_system.py`

**New Method:** `_calculate_adaptive_sl_tp(plan: TradePlan, new_entry: float, strategy_type: str, current_atr: float, base_atr: float) -> tuple[float, float]`
- Get elasticity: `alpha, beta = self._get_strategy_elasticity(strategy_type)`
- Calculate ATR ratio: `atr_ratio = current_atr / base_atr`
- Calculate original SL/TP distances:
  - `sl_distance = plan.entry_price - plan.stop_loss`
  - `tp_distance = plan.take_profit - plan.entry_price`
- Apply volatility modulation:
  - `new_sl_distance = sl_distance * (1 + alpha * (atr_ratio - 1))`
  - `new_tp_distance = tp_distance * (1 + beta * (atr_ratio - 1))`
- Calculate new levels:
  - `new_sl = new_entry - new_sl_distance`
  - `new_tp = new_entry + new_tp_distance`
- Validate R:R ratio (maintain target R:R within tolerance)
- Return `(new_sl, new_tp)`

**Location:** Add after `_get_strategy_elasticity()` method

#### **3.4 Update Re-anchoring to Use Adaptive SL/TP**

**File:** `auto_execution_system.py`

**Location:** `_reanchor_plan()` method (from Phase 1)

**Changes:**
- Replace simple offset calculation with adaptive calculation:
  ```python
  # Get strategy type
  strategy_type = self._detect_strategy_type(plan)
  
  # Get current ATR and base ATR
  current_atr = self._get_current_atr(plan.symbol)
  base_atr = plan.conditions.get("base_atr", current_atr)  # Store on plan creation
  
  # Calculate adaptive SL/TP
  new_sl, new_tp = self._calculate_adaptive_sl_tp(
      plan, new_entry, strategy_type, current_atr, base_atr
  )
  ```

#### **3.5 Add ATR Tracking**

**File:** `auto_execution_system.py`

**New Method:** `_get_current_atr(symbol: str) -> float`
- Get ATR from `volatility_tolerance_calculator` or `multi_timeframe_analyzer`
- Cache for 60 seconds (avoid redundant calls)
- Return ATR value

**Location:** Add after `_calculate_adaptive_sl_tp()` method

#### **3.6 Store Base ATR on Plan Creation**

**File:** `auto_execution_system.py`

**Location:** `add_plan()` method

**Changes:**
- If `proximity_tracking_enabled`:
  - Get current ATR: `base_atr = self._get_current_atr(plan.symbol)`
  - Store in conditions: `plan.conditions["base_atr"] = base_atr`

**Checklist:**
- [ ] Implement `_detect_strategy_type()` method (analyze conditions)
- [ ] Implement `_get_strategy_elasticity()` with elasticity map
- [ ] Implement `_calculate_adaptive_sl_tp()` with volatility modulation
- [ ] Implement `_get_current_atr()` method
- [ ] Update `_reanchor_plan()` to use adaptive SL/TP calculation
- [ ] Update `add_plan()` to store base ATR
- [ ] Add unit tests for strategy detection and elasticity
- [ ] Add unit tests for adaptive SL/TP calculation
- [ ] Add integration tests for full adaptive re-anchoring flow

**Testing:**
- Unit tests: `tests/test_phase3_strategy_adaptation.py`
  - Test strategy type detection (all 9 strategy types)
  - Test elasticity parameters (alpha, beta for each strategy)
  - Test adaptive SL/TP calculation (volatility modulation)
  - Test R:R ratio preservation (within tolerance)
  - Test ATR tracking and caching

---

### **Phase 4: Predictive Drift Modeling (Phase 3 Only)**

**Objective:** Implement predictive re-anchoring during expansion phases to pre-empt drift

**Estimated Time:** 4-5 hours

#### **4.1 Add Phase Detection Integration**

**File:** `auto_execution_system.py`

**New Method:** `_get_current_phase(symbol: str) -> int`
- Get volatility regime from `volatility_tolerance_calculator` or `multi_timeframe_analyzer`
- Map regime to phase:
  - Phase 1 (Distribution): STABLE regime
  - Phase 2 (Compression): TRANSITIONAL regime
  - Phase 3 (Expansion): VOLATILE or PRE_BREAKOUT_TENSION regime
  - Phase 4 (Trend): POST_BREAKOUT_DECAY regime
  - Phase 5 (Exhaustion): FRAGMENTED_CHOP regime
  - Phase 6 (Reversion): SESSION_SWITCH_FLARE regime
- Cache for 60 seconds
- Return phase number (1-6)

**Location:** Add after `_get_current_atr()` method

#### **4.2 Add Predictive Drift Detection**

**File:** `auto_execution_system.py`

**New Method:** `_predict_drift(plan: TradePlan) -> float`
- Only enabled if `current_phase == 3` OR `vol_ratio > 1.25`
- Calculate delta velocity: `delta_velocity = (current_delta - previous_delta) / time_delta`
- Calculate VWAP curvature: Detect if VWAP slope is accelerating
- Calculate predicted drift: `predicted_drift = linear_regression_slope * prediction_horizon`
- Return predicted drift in points

**Location:** Add after `_get_current_phase()` method

#### **4.3 Add Predictive Re-anchoring Logic**

**File:** `auto_execution_system.py`

**Location:** `_check_drift_and_reanchor()` method

**Changes:**
- Add predictive check before reactive drift check:
  ```python
  # Check if predictive drift enabled (Phase 4)
  current_phase = self._get_current_phase(plan.symbol)
  vol_ratio = current_atr / base_atr
  
  if (current_phase == 3 or vol_ratio > 1.25) and \
     (range_break_detected or delta_velocity > threshold):
      predicted_drift = self._predict_drift(plan)
      if predicted_drift > plan.drift_threshold * 0.8:  # 80% of threshold
          # Pre-emptive re-anchor
          if self._recalculate_anchor(plan):
              new_anchor = self._recalculate_anchor(plan)
              if self._reanchor_plan(plan, new_anchor):
                  logger.info(f"Plan {plan.plan_id} pre-emptively re-anchored (predictive)")
                  return True
  ```

#### **4.4 Add Rate Limiting for Predictive Updates**

**File:** `auto_execution_system.py`

**New Fields in TradePlan:**
```python
predictive_update_count: Optional[int] = 0  # Predictive updates this hour
last_predictive_update: Optional[str] = None  # Last predictive update timestamp
```

**Rate Limiting Logic:**
- Max predictive updates per hour: 4 (configurable)
- Minimum spacing between predictive updates: 3 minutes
- Check in `_check_drift_and_reanchor()`:
  ```python
  if predictive_update_count >= 4 and (now - last_predictive_update) < 3600:
      return False  # Skip predictive update
  if (now - last_predictive_update) < 180:  # 3 minutes
      return False  # Skip predictive update
  ```

#### **4.5 Add Range Break Detection**

**File:** `auto_execution_system.py`

**New Method:** `_detect_range_break(symbol: str) -> bool`
- Check if price broke recent range (last 20-50 candles)
- Detect if volatility expanded suddenly (ATR spike)
- Return `True` if range break detected

**Location:** Add after `_predict_drift()` method

**Checklist:**
- [ ] Implement `_get_current_phase()` method (regime → phase mapping)
- [ ] Implement `_predict_drift()` method (delta velocity, VWAP curvature)
- [ ] Implement `_detect_range_break()` method
- [ ] Add predictive re-anchoring logic to `_check_drift_and_reanchor()`
- [ ] Add rate limiting for predictive updates (max 4/hour, 3min spacing)
- [ ] Add `predictive_update_count`, `last_predictive_update` fields to TradePlan
- [ ] Add database migration for new fields
- [ ] Add unit tests for phase detection
- [ ] Add unit tests for predictive drift calculation
- [ ] Add integration tests for predictive re-anchoring flow

**Testing:**
- Unit tests: `tests/test_phase4_predictive_drift.py`
  - Test phase detection (all 6 phases)
  - Test predictive drift activation (Phase 3 only, or vol_ratio > 1.25)
  - Test predictive drift calculation (delta velocity, VWAP curvature)
  - Test range break detection
  - Test rate limiting (max 4/hour, 3min spacing)
  - Test predictive re-anchoring triggers

---

### **Phase 5: Multi-Factor Adaptation (Symbol + Regime + Session)**

**Objective:** Combine symbol characteristics, market regime, and session context for optimal SL/TP scaling

**Estimated Time:** 6-8 hours

#### **5.1 Add Symbol-Specific Weight Calculation**

**File:** `auto_execution_system.py`

**New Method:** `_get_symbol_weight(symbol: str) -> float`
- Return symbol-specific multiplier:
  ```python
  SYMBOL_WEIGHTS = {
      "BTCUSDc": 1.4,  # High momentum, frequent spikes
      "XAUUSDc": 1.0,  # Mean-reverting, smoother flow
      "EURUSDc": 1.1,  # Stable volatility
      "USDJPYc": 0.9,  # Less whipsaw, narrower range
      "GBPUSDc": 1.2,  # Moderate volatility
  }
  ```
- Default: 1.0

**Location:** Add after `_detect_range_break()` method

#### **5.2 Add Regime-Based Weight Calculation**

**File:** `auto_execution_system.py`

**New Method:** `_get_regime_weight(phase: int) -> float`
- Return phase-specific multiplier:
  ```python
  REGIME_WEIGHTS = {
      1: 0.9,   # Distribution: tighten
      2: 1.0,   # Compression: baseline
      3: 1.3,   # Expansion: loosen
      4: 1.5,   # Trend: wide trailing
      5: 1.2,   # Exhaustion: protect profits
      6: 0.8,   # Reversion: tight stops
  }
  ```
- Default: 1.0

**Location:** Add after `_get_symbol_weight()` method

#### **5.3 Add Session-Specific Weight Calculation**

**File:** `auto_execution_system.py`

**New Method:** `_get_session_weight() -> float`
- Get current session from `session_service` or time-based detection
- Return session-specific multiplier:
  ```python
  SESSION_WEIGHTS = {
      "asian": 0.8,        # Narrow ranges, thin liquidity
      "london_open": 1.4,   # Breakout volatility
      "london_ny_overlap": 1.6,  # Max volatility
      "ny_afternoon": 0.8,  # Range contraction
      "default": 1.0
  }
  ```
- Default: 1.0

**Location:** Add after `_get_regime_weight()` method

#### **5.4 Add Multi-Factor Composite Calculation**

**File:** `auto_execution_system.py`

**New Method:** `_calculate_multi_factor_multiplier(plan: TradePlan) -> float`
- Get individual weights:
  - `symbol_weight = self._get_symbol_weight(plan.symbol)`
  - `regime_weight = self._get_regime_weight(current_phase)`
  - `session_weight = self._get_session_weight()`
- Calculate composite: `effective_multiplier = symbol_weight * regime_weight * session_weight`
- Return effective multiplier

**Location:** Add after `_get_session_weight()` method

#### **5.5 Update Adaptive SL/TP to Use Multi-Factor**

**File:** `auto_execution_system.py`

**Location:** `_calculate_adaptive_sl_tp()` method (from Phase 3)

**Changes:**
- Get multi-factor multiplier: `effective_multiplier = self._calculate_multi_factor_multiplier(plan)`
- Apply to SL/TP calculation:
  ```python
  new_sl_distance = sl_distance * effective_multiplier * (1 + alpha * (atr_ratio - 1))
  new_tp_distance = tp_distance * effective_multiplier * (1 + beta * (atr_ratio - 1))
  ```

#### **5.6 Add R:R Target Adjustment by Regime**

**File:** `auto_execution_system.py`

**New Method:** `_get_target_rr_by_regime(phase: int) -> float`
- Return target R:R by phase:
  ```python
  TARGET_RR = {
      1: 1.4,  # Distribution
      2: 1.3,  # Compression
      3: 1.8,  # Expansion
      4: 2.0,  # Trend
      5: 1.5,  # Exhaustion
      6: 1.2,  # Reversion
  }
  ```
- Default: 1.7

**Location:** Add after `_calculate_multi_factor_multiplier()` method

#### **5.7 Update SL/TP Calculation to Enforce Target R:R**

**File:** `auto_execution_system.py`

**Location:** `_calculate_adaptive_sl_tp()` method

**Changes:**
- Get target R:R: `target_rr = self._get_target_rr_by_regime(current_phase)`
- After calculating new_sl and new_tp, validate R:R:
  ```python
  calculated_rr = (new_tp - new_entry) / (new_entry - new_sl)
  if abs(calculated_rr - target_rr) > 0.1:  # 0.1 tolerance
      # Adjust TP to match target R:R
      new_tp = new_entry + (new_entry - new_sl) * target_rr
  ```

**Checklist:**
- [ ] Implement `_get_symbol_weight()` with symbol-specific multipliers
- [ ] Implement `_get_regime_weight()` with phase-specific multipliers
- [ ] Implement `_get_session_weight()` with session-specific multipliers
- [ ] Implement `_calculate_multi_factor_multiplier()` (composite calculation)
- [ ] Implement `_get_target_rr_by_regime()` method
- [ ] Update `_calculate_adaptive_sl_tp()` to use multi-factor multiplier
- [ ] Update `_calculate_adaptive_sl_tp()` to enforce target R:R by regime
- [ ] Add unit tests for all weight calculations
- [ ] Add unit tests for multi-factor composite calculation
- [ ] Add integration tests for full multi-factor adaptation flow

**Testing:**
- Unit tests: `tests/test_phase5_multi_factor.py`
  - Test symbol weight calculation (all symbols)
  - Test regime weight calculation (all 6 phases)
  - Test session weight calculation (all sessions)
  - Test multi-factor composite calculation
  - Test target R:R by regime
  - Test R:R enforcement in SL/TP calculation

---

## 🔧 **Hybrid Approach: Opt-In/Opt-Out Flag**

### **Implementation**

**File:** `auto_execution_system.py`

**Location:** `TradePlan` dataclass and `add_plan()` method

**Changes:**
- Add `proximity_tracking_enabled: Optional[bool] = False` field (already in Phase 1)
- Default: `False` (static plans by default)
- Only plans with `proximity_tracking_enabled = True` undergo drift detection and re-anchoring
- ChatGPT can specify `proximity_tracking_enabled: true` in plan conditions

**Strategy Recommendations:**
- **Enable proximity tracking for:**
  - Range scalps (VWAP mean reversion)
  - Compression phase setups (Phase 2)
  - VWAP-based entries
  - Microstructure swing trades
  
- **Keep static (disable proximity tracking) for:**
  - Liquidity sweeps with clear levels
  - Order block rejections with fixed zones
  - Breaker blocks with specific price levels
  - News event trades with fixed entry zones

---

## 📊 **Integration Points**

### **Existing Systems to Leverage**

1. **15-Second Monitoring Loop** (`_monitor_loop()`)
   - Add drift check before condition checking
   - Skip suspended plans
   - Integrate re-anchoring seamlessly

2. **Price Caching System** (Phase 1 of 15-second interval plan)
   - Use cached prices for drift detection
   - Reduce API calls

3. **Volatility Tolerance Calculator**
   - Get ATR values for adaptive SL/TP
   - Get volatility regime for phase detection

4. **Multi-Timeframe Analyzer**
   - Get H1/H4 bias for bias invalidation fence
   - Get VWAP for anchor calculation

5. **Order Flow Metrics** (CVD, Delta)
   - Use for predictive drift detection
   - Use for confluence scoring in re-arm logic

6. **Update Plan System** (`update_plan()`, `update_multiple_auto_plans()`)
   - Use for re-anchoring updates
   - Ensure thread-safe updates

---

## 🧪 **Testing Strategy**

### **Unit Tests (Per Phase)**

- **Phase 1:** `tests/test_phase1_reactive_drift.py` (10-12 tests)
- **Phase 2:** `tests/test_phase2_bias_invalidation.py` (8-10 tests)
- **Phase 3:** `tests/test_phase3_strategy_adaptation.py` (10-12 tests)
- **Phase 4:** `tests/test_phase4_predictive_drift.py` (8-10 tests)
- **Phase 5:** `tests/test_phase5_multi_factor.py` (10-12 tests)

### **Integration Tests**

- **File:** `tests/test_auto_adjusting_plans_integration.py`
- **Tests:**
  - Full re-anchoring flow (drift → re-anchor → SL/TP adjustment)
  - Bias invalidation → suspension → re-arm flow
  - Multi-factor adaptation across different scenarios
  - Rate limiting enforcement
  - Plan state transitions

### **E2E Tests**

- **File:** `tests/test_auto_adjusting_plans_e2e.py`
- **Tests:**
  - Plan creation with proximity tracking enabled
  - Drift detection and re-anchoring over multiple cycles
  - Suspension and re-arm in live scenario
  - Strategy-specific adaptation validation
  - Multi-factor adaptation validation

---

## 📝 **ChatGPT Integration**

### **Update Knowledge Documents**

**File:** `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`

**New Section:** `# PROXIMITY_TRACKING_CONDITION`

**Content:**
- Explanation of proximity tracking
- When to enable (`proximity_tracking_enabled: true`)
- Strategy recommendations (enable vs. disable)
- Anchor type options (`vwap`, `swing`, `tick_mean`)
- Drift threshold defaults (symbol-specific)

### **Update openai.yaml**

**File:** `openai.yaml`

**Changes:**
- Add `proximity_tracking_enabled` parameter to `create_auto_trade_plan` tool
- Add `anchor_type` parameter (optional)
- Add `drift_threshold` parameter (optional, auto-calculated if not provided)
- Update tool description with proximity tracking explanation

---

## ⚠️ **Critical Considerations**

### **1. Anchor Creep Prevention**

- ✅ Bias invalidation fence prevents crossing HTF boundaries
- ✅ Rate limiting prevents excessive updates
- ✅ Hysteresis prevents whipsaw triggers

### **2. Update Budget Management**

- Global throttle: Max 10 updates per 5 minutes per symbol
- Priority queue: Update highest-confidence plans first
- Circuit breaker: Suspend updates if API errors occur

### **3. Plan Density Control**

- Enforce hard caps per phase (from Auto_Adjusting_plans.md):
  - Phase 1: 8 plans
  - Phase 2: 12 plans
  - Phase 3: 6 plans
  - Phase 4: 4 plans
  - Phase 5: 4 plans
  - Phase 6: 8 plans
- Risk-weighted caps: Track `active_risk_units` per symbol
- Replacement logic: Pause lowest-confidence/oldest plans when cap exceeded

### **4. Performance Impact**

- Drift checks add ~50-100ms per plan per cycle
- With 15-second interval: ~3-7ms per plan per second (acceptable)
- Cache HTF bias, ATR, phase detection (60s TTL)
- Batch anchor updates when possible

### **5. Database Schema**

- All new fields added to `trade_plans` table
- Migration in `_init_database()` method
- Backward compatible (defaults for existing plans)

---

## 📈 **Expected Benefits**

1. **Reduced Stale Plans**: Plans stay relevant even during price drift
2. **Better Execution Timing**: Always trades at current microstructure context
3. **Improved R:R Consistency**: Adaptive SL/TP maintains risk ratios across volatility regimes
4. **Reduced Manual Intervention**: Plans self-adjust without manual recalibration
5. **Phase-Aware Adaptation**: System adapts to market regime automatically

---

## 🚀 **Rollout Strategy**

### **Phase 1 (Week 1)**
- Implement reactive drift detection
- Test on 1-2 plans (BTCUSDc or XAUUSDc)
- Monitor re-anchoring frequency and execution quality

### **Phase 2 (Week 2)**
- Add bias invalidation fence
- Expand to 5-10 plans
- Monitor suspension/re-arm behavior

### **Phase 3 (Week 3)**
- Add strategy-specific adaptation
- Expand to all eligible plans
- Monitor SL/TP adjustment quality

### **Phase 4 (Week 4)**
- Add predictive drift (Phase 3 only)
- Monitor predictive accuracy
- Fine-tune prediction parameters

### **Phase 5 (Week 5)**
- Add multi-factor adaptation
- Full system validation
- Performance optimization

---

## 📚 **Documentation Updates**

### **README.md**
- Add "Auto-Adjusting Plans" to Advanced Trading Systems section
- Document proximity tracking feature

### **.claude.md**
- Add detailed section on proximity tracking implementation
- Document all phases and integration points

---

## ✅ **Success Criteria**

1. ✅ Plans re-anchor when drift > threshold (Phase 1)
2. ✅ Plans suspend when HTF bias opposes direction (Phase 2)
3. ✅ SL/TP adapt based on strategy type and volatility (Phase 3)
4. ✅ Predictive re-anchoring works in Phase 3 (Phase 4)
5. ✅ Multi-factor adaptation combines symbol/regime/session (Phase 5)
6. ✅ Rate limiting prevents update storms
7. ✅ All unit tests pass (100%)
8. ✅ All integration tests pass (100%)
9. ✅ ChatGPT can create proximity-tracking plans
10. ✅ System performance remains acceptable (<10% CPU increase)

---

**Last Updated:** 2026-01-10  
**Status:** 📋 **PLANNING COMPLETE - READY FOR IMPLEMENTATION**
