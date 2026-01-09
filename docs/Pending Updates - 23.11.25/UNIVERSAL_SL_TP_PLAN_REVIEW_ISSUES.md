# Universal Dynamic SL/TP Plan - Review Issues & Fixes

**Date:** November 23, 2025  
**Status:** Issues Identified - Fixes Required

---

## 🔴 Critical Issues

### 1. Duplicate Breakeven Check in Monitoring Loop

**Location:** Lines 1137-1141 and 1180-1185

**Problem:** The monitoring loop checks breakeven trigger twice:
- First check at line 1137-1141
- Second check at line 1180-1185 (duplicate)

**Impact:** Redundant code, potential confusion

**Fix:** Remove the duplicate check at lines 1180-1185. The first check (lines 1137-1141) is sufficient.

```python
# REMOVE THIS DUPLICATE:
# 7. Check breakeven trigger (separate from trailing)
# CRITICAL: BE logic is independent of trailing_enabled
if not trade_state.breakeven_triggered:
    if trade_state.r_achieved >= rules["breakeven_trigger_r"]:
        self._move_to_breakeven(ticket, trade_state)
        trade_state.breakeven_triggered = True
```

---

### 2. Missing Return Statement / Unreachable Code

**Location:** Line 1178

**Problem:** `_get_dynamic_partial_trigger()` returns at line 1178, but then code continues at line 1180 with another breakeven check that's unreachable.

**Impact:** Code will never execute after return statement

**Fix:** The function should end after `return base_partial_r`. The code at line 1180+ should be removed (it's duplicate anyway - see issue #1).

---

### 3. Session Detection Missing EURUSDc and US30c

**Location:** Lines 170-201

**Problem:** `detect_session()` function only handles `BTCUSDc` and `XAUUSDc`, but config includes `EURUSDc` and `US30c`.

**Impact:** EURUSDc and US30c trades will fail session detection or use wrong session

**Fix:** Add EURUSDc and US30c to session detection:

```python
def detect_session(symbol: str, current_time: datetime) -> Session:
    hour = current_time.hour  # UTC
    
    # All symbols use same session times (can be customized per symbol if needed)
    if 0 <= hour < 8:  # 00:00-08:00 UTC
        return Session.ASIA
    elif 8 <= hour < 13:  # 08:00-13:00 UTC
        return Session.LONDON
    elif 13 <= hour < 16:  # 13:00-16:00 UTC
        return Session.LONDON_NY_OVERLAP
    elif 16 <= hour < 21:  # 16:00-21:00 UTC
        return Session.NY
    else:  # 21:00-00:00 UTC
        return Session.LATE_NY
```

Or add symbol-specific logic if EURUSDc/US30c need different session times.

---

### 4. Recovery Uses Wrong Time for Session Detection

**Location:** Line 1009

**Problem:** During recovery, session is detected using `datetime.now()` instead of the position's open time or `registered_at` time.

**Impact:** If trade was opened in London session but recovered during NY session, it will get NY session rules (wrong!)

**Fix:** Use position open time or registered_at time:

```python
# Get position open time
position_open_time = datetime.fromtimestamp(position.time) if hasattr(position, 'time') else datetime.now()

# Or use registered_at from DB if available
session = detect_session(position.symbol, position_open_time)  # Use open time, not now()
```

---

### 5. Missing baseline_atr Initialization

**Location:** `register_trade()` function (not shown in detail)

**Problem:** `baseline_atr` is stored in TradeState but not shown being calculated/initialized in `register_trade()`.

**Impact:** `baseline_atr` will be None, causing volatility override logic to fail

**Fix:** Add baseline_atr calculation in register_trade:

```python
def register_trade(self, ticket, symbol, strategy_type, ...):
    # ... existing code ...
    
    # Calculate and store baseline ATR
    atr_timeframe = self._get_atr_timeframe(strategy_type, symbol)
    baseline_atr = self._get_current_atr(symbol, atr_timeframe)
    
    trade_state = TradeState(
        ...
        baseline_atr=baseline_atr,  # Store at trade open
        ...
    )
```

---

### 6. Missing min_sl_change_r in Rule Resolution

**Location:** `_resolve_trailing_rules()` function (line 820)

**Problem:** `min_sl_change_r` is in symbol_adjustments but not shown being merged into resolved rules.

**Impact:** `min_sl_change_r` won't be in resolved rules, causing `is_improvement()` to fail

**Fix:** Add min_sl_change_r to rule resolution:

```python
def _resolve_trailing_rules(self, strategy_type, symbol, session):
    rules = STRATEGY_RULES[strategy_type].copy()
    
    # Get symbol adjustments
    symbol_rules = SYMBOL_RULES[symbol]
    
    # Merge min_sl_change_r from symbol adjustments
    if "min_sl_change_r" in symbol_rules:
        rules["min_sl_change_r"] = symbol_rules["min_sl_change_r"]
    
    # ... rest of resolution logic ...
```

---

## 🟡 Medium Issues

### 7. Database Save Missing Fields

**Location:** Lines 1045-1076

**Problem:** `_save_trade_state_to_db()` doesn't save all TradeState fields:
- Missing: `trailing_active`
- Missing: `structure_state`
- Missing: `current_price`, `current_sl`, `r_achieved` (these are runtime, may not need saving)
- Missing: `last_check_time`

**Impact:** Recovery won't restore full state

**Fix:** Add missing fields to save function (or document which fields are runtime-only and don't need saving):

```python
state_dict = {
    # ... existing fields ...
    "trailing_active": 1 if trade_state.trailing_active else 0,
    "structure_state": json.dumps(trade_state.structure_state) if trade_state.structure_state else None,
    "last_check_time": trade_state.last_check_time.isoformat() if trade_state.last_check_time else None,
    # Note: current_price, current_sl, r_achieved are runtime and don't need saving
}
```

---

### 8. Ownership Check Missing in Recovery

**Location:** Line 1021

**Problem:** When reconstructing trades during recovery, it always sets `managed_by="universal_sl_tp_manager"` without checking if strategy_type is in UNIVERSAL_MANAGED_STRATEGIES.

**Impact:** Trades that shouldn't be managed by universal manager will be incorrectly assigned

**Fix:** Check strategy_type before setting managed_by:

```python
if strategy_type and strategy_type != "DEFAULT_STANDARD":
    # Check if this strategy should be managed by universal manager
    if strategy_type in UNIVERSAL_MANAGED_STRATEGIES:
        managed_by = "universal_sl_tp_manager"
    else:
        managed_by = "legacy_exit_manager"
    
    trade_state = TradeState(
        ...
        managed_by=managed_by,  # Set based on strategy type
        ...
    )
```

---

### 9. Volatility Override Not Passed to Trailing Calculation

**Location:** Lines 873-877

**Problem:** Shows `atr_multiplier_override` parameter but `_calculate_trailing_sl()` signature not shown accepting this parameter.

**Impact:** Volatility override won't work

**Fix:** Document that `_calculate_trailing_sl()` must accept optional `atr_multiplier_override`:

```python
def _calculate_trailing_sl(
    self, 
    trade_state: TradeState, 
    rules: Dict,
    atr_multiplier_override: Optional[float] = None
) -> Optional[float]:
    """
    Calculate trailing SL.
    If atr_multiplier_override provided, use it instead of rules["atr_multiplier"].
    """
    atr_multiplier = atr_multiplier_override if atr_multiplier_override else rules["atr_multiplier"]
    # ... rest of calculation ...
```

---

### 10. Missing Error Handling for MT5 Calls

**Location:** Throughout monitoring loop

**Problem:** No error handling shown for:
- `mt5.positions_get(ticket=ticket)` - could return None or raise exception
- `mt5.symbol_info(symbol)` - could return None
- `mt5.modify_position()` - could fail

**Impact:** Crashes if MT5 connection lost or calls fail

**Fix:** Add try-except blocks and None checks:

```python
def monitor_trade(self, ticket: int):
    try:
        position = mt5.positions_get(ticket=ticket)
        if not position or len(position) == 0:
            self._unregister_trade(ticket)
            return
        
        position = position[0]  # Get first (should be only one)
        
        # ... rest of logic ...
    except Exception as e:
        logger.error(f"Error monitoring trade {ticket}: {e}", exc_info=True)
        return
```

---

## 🟢 Minor Issues / Clarifications

### 11. TradeRegistry Initialization Not Documented

**Location:** Line 1091

**Problem:** Global `trade_registry` is shown but initialization/cleanup not documented

**Fix:** Document initialization in startup and cleanup on shutdown:

```python
# In __init__ or startup
trade_registry: Dict[int, TradeState] = {}

# On shutdown
def cleanup(self):
    """Clean up registry on shutdown"""
    trade_registry.clear()
```

---

### 12. Missing min_sl_change_r in Strategy Configs

**Location:** Strategy configs (lines 376-418)

**Problem:** `min_sl_change_r` is only in symbol_adjustments, not in strategy configs. Should it be in both or just symbol?

**Clarification Needed:** 
- If universal (0.1R for all), it should be in symbol_adjustments only (current design is correct)
- If strategy-specific, it should be in strategy configs too

**Current Design is Correct:** Since it's universal (0.1R for all), keeping it only in symbol_adjustments is fine. Just need to ensure it's merged during resolution (see issue #6).

---

### 13. Partial Close Detection Logic Incomplete

**Location:** Lines 1234-1242

**Problem:** Detects volume change but doesn't handle:
- What if volume increases? (scale-in)
- What if position is fully closed? (should unregister)
- What if volume change is due to partial TP hit?

**Fix:** Add complete handling:

```python
# Check if position volume changed
if position.volume != trade_state.initial_volume:
    if position.volume == 0:
        # Position fully closed
        self._unregister_trade(ticket)
        return
    elif position.volume < trade_state.initial_volume:
        # Manual partial close detected
        logger.info(f"Position {ticket} volume reduced: {trade_state.initial_volume} → {position.volume}")
        trade_state.initial_volume = position.volume  # Update for future checks
    elif position.volume > trade_state.initial_volume:
        # Scale-in (not supported, but log it)
        logger.warning(f"Position {ticket} volume increased: {trade_state.initial_volume} → {position.volume} (scale-in not supported)")
        trade_state.initial_volume = position.volume  # Update anyway
```

---

### 14. Missing Validation for Resolved Rules

**Location:** `_resolve_trailing_rules()`

**Problem:** No validation that required fields exist in resolved rules

**Impact:** Runtime errors if config is incomplete

**Fix:** Add validation:

```python
def _resolve_trailing_rules(self, strategy_type, symbol, session):
    rules = STRATEGY_RULES[strategy_type].copy()
    # ... merge logic ...
    
    # Validate required fields
    required_fields = ["breakeven_trigger_r", "trailing_method", "min_sl_change_r"]
    for field in required_fields:
        if field not in rules:
            logger.error(f"Missing required field {field} in resolved rules for {strategy_type}")
            raise ValueError(f"Missing required field: {field}")
    
    return rules
```

---

### 15. Session-Specific breakeven_trigger_r Not Resolved

**Location:** Line 378, 407

**Problem:** Config has `breakeven_trigger_r_asia` but resolution logic doesn't show selecting it based on session

**Impact:** Session-specific BE triggers won't work

**Fix:** Add session-specific resolution:

```python
def _resolve_trailing_rules(self, strategy_type, symbol, session):
    rules = STRATEGY_RULES[strategy_type].copy()
    
    # Apply session-specific breakeven trigger if exists
    session_be_key = f"breakeven_trigger_r_{session.value.lower()}"
    if session_be_key in rules:
        rules["breakeven_trigger_r"] = rules[session_be_key]
        # Remove the session-specific key to avoid confusion
        del rules[session_be_key]
    
    # ... rest of resolution ...
```

---

## 📋 Summary of Required Fixes

### Must Fix (Critical):
1. ✅ Remove duplicate breakeven check (lines 1180-1185)
2. ✅ Fix unreachable code after return (line 1178)
3. ✅ Add EURUSDc/US30c to session detection
4. ✅ Fix recovery session detection (use open time, not now)
5. ✅ Add baseline_atr initialization in register_trade
6. ✅ Add min_sl_change_r to rule resolution

### Should Fix (Medium):
7. ✅ Add missing fields to database save
8. ✅ Add ownership check in recovery
9. ✅ Document atr_multiplier_override parameter
10. ✅ Add error handling for MT5 calls

### Nice to Have (Minor):
11. ✅ Document TradeRegistry initialization
12. ✅ Clarify min_sl_change_r placement (already correct)
13. ✅ Complete partial close detection logic
14. ✅ Add validation for resolved rules
15. ✅ Fix session-specific breakeven_trigger_r resolution

---

## 🔧 Implementation Priority

1. **Phase 1 Fixes** (Before implementation):
   - Issues #1, #2, #3, #4, #5, #6 (Critical)

2. **Phase 2 Fixes** (During implementation):
   - Issues #7, #8, #9, #10 (Medium)

3. **Phase 3 Fixes** (Polish):
   - Issues #11-15 (Minor)

---

**End of Review**

