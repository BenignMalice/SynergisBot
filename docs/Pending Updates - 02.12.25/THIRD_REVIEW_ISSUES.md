# Third Review Issues - Final Pass

## 🔴 CRITICAL ISSUES

### 1. Missing `_load_feature_flags()` Implementation

**Issue:** Helper functions reference `_load_feature_flags()` but it's never defined in the plan.

**Current Code References:**
- Line 1104: `flags = _load_feature_flags()`
- Line 1149: `flags = _load_feature_flags()`

**Problem:**
- Function doesn't exist
- Will cause `NameError` when called
- No implementation provided

**Solution:**
```python
def _load_feature_flags() -> Dict[str, Any]:
    """Load feature flags configuration from JSON file"""
    import json
    from pathlib import Path
    
    config_path = Path("config/strategy_feature_flags.json")
    
    try:
        if config_path.exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            logger.warning(f"Feature flags file not found: {config_path}")
            return {}
    except Exception as e:
        logger.warning(f"Failed to load feature flags: {e}")
        return {}
```

**Add to Helper Functions section (after `_fn_to_strategy_name`):**
```python
def _load_feature_flags() -> Dict[str, Any]:
    """Load feature flags configuration from JSON file"""
    import json
    from pathlib import Path
    
    config_path = Path("config/strategy_feature_flags.json")
    
    try:
        if config_path.exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            logger.warning(f"Feature flags file not found: {config_path}")
            return {}
    except Exception as e:
        logger.warning(f"Failed to load feature flags: {e}")
        return {}
```

---

### 2. Missing Logger Definition in Helper Functions

**Issue:** Helper functions use `logger` but don't define it.

**Current Code:**
```python
def _check_circuit_breaker(strategy_name: str) -> bool:
    # ...
    logger.warning(f"Circuit breaker check failed for {strategy_name}: {e}")
    # ❌ logger not defined
```

**Problem:**
- `logger` is not defined in helper function scope
- Will cause `NameError`

**Solution:**
```python
# At top of strategy_logic.py (already exists):
logger = logging.getLogger("app.engine.strategy_logic")

# Helper functions can use this logger (it's module-level)
# OR add to each helper:
def _check_circuit_breaker(strategy_name: str) -> bool:
    """Check if strategy is disabled by circuit breaker"""
    import logging
    logger = logging.getLogger("app.engine.strategy_logic")
    # ... rest of code ...
```

**Better Solution:** Document that helper functions use module-level logger:
```python
# Helper Functions (add to strategy_logic.py)
# Note: These functions use the module-level logger defined at top of file

def _load_feature_flags() -> Dict[str, Any]:
    """Load feature flags configuration"""
    # Uses module-level logger
    # ...
```

---

### 3. Database Row Index Verification Issue

**Issue:** Need to verify row indices match database schema order.

**Schema Order (strategy_performance):**
```sql
0: strategy_name
1: win_rate
2: avg_rr
3: total_trades
4: total_wins
5: total_losses
6: total_breakeven
7: consecutive_losses
8: current_drawdown_pct
9: max_drawdown_pct
10: peak_equity
11: current_equity
12: last_win_date
13: last_loss_date
14: last_breakeven_date
15: last_updated
16: disabled_until
```

**Code Uses:**
- `row[2]` = total_trades ✓ (index 3 in schema)
- `row[3]` = total_wins ✓ (index 4 in schema)
- `row[4]` = total_losses ✓ (index 5 in schema)
- `row[5]` = total_breakeven ✓ (index 6 in schema)
- `row[7]` = consecutive_losses ✓ (index 7 in schema)
- `row[9]` = max_drawdown_pct ✓ (index 9 in schema)
- `row[10]` = peak_equity ✓ (index 10 in schema)
- `row[11]` = current_equity ✓ (index 11 in schema)
- `row[12]` = last_win_date ✓ (index 12 in schema)
- `row[13]` = last_loss_date ✓ (index 13 in schema)
- `row[14]` = last_breakeven_date ✓ (index 14 in schema)

**Problem:** Row indices are 0-based, but schema shows 1-based numbering in comments. Need to verify actual order.

**Solution:** Use named columns or verify exact order:
```python
# Better: Use column names instead of indices
cursor.execute("""
    SELECT strategy_name, win_rate, avg_rr, total_trades, total_wins, 
           total_losses, total_breakeven, consecutive_losses, 
           current_drawdown_pct, max_drawdown_pct, peak_equity, current_equity,
           last_win_date, last_loss_date, last_breakeven_date, last_updated, disabled_until
    FROM strategy_performance WHERE strategy_name = ?
""", (strategy_name,))

# Or use row_factory for named access
conn.row_factory = sqlite3.Row
row = cursor.fetchone()
if row:
    total_trades = row['total_trades']  # Named access
```

**Recommendation:** Add comment mapping indices to column names:
```python
# Row indices (0-based):
# 0: strategy_name, 1: win_rate, 2: avg_rr, 3: total_trades, 4: total_wins,
# 5: total_losses, 6: total_breakeven, 7: consecutive_losses,
# 8: current_drawdown_pct, 9: max_drawdown_pct, 10: peak_equity, 11: current_equity,
# 12: last_win_date, 13: last_loss_date, 14: last_breakeven_date,
# 15: last_updated, 16: disabled_until
```

---

## ⚠️ MEDIUM PRIORITY ISSUES

### 4. Missing Type Hints in Helper Functions

**Issue:** Some helper functions don't have complete type hints.

**Current:**
```python
def _fn_to_strategy_name(fn) -> str:
```

**Should Be:**
```python
from typing import Callable

def _fn_to_strategy_name(fn: Callable) -> str:
```

**Also:**
```python
def _load_feature_flags() -> Dict[str, Any]:
def _is_strategy_enabled(strategy_name: str) -> bool:
def _has_required_fields(tech: Dict[str, Any], required_fields: List[str]) -> bool:
def _check_circuit_breaker(strategy_name: str) -> bool:
def _get_confidence_threshold(strategy_name: str) -> float:
def _meets_confidence_threshold(tech: Dict[str, Any], strategy_name: str) -> bool:
```

---

### 5. Missing Error Handling in `_load_feature_flags()`

**Issue:** If `_load_feature_flags()` is called multiple times, it reads from disk each time (no caching).

**Solution:** Add caching:
```python
_feature_flags_cache: Optional[Dict[str, Any]] = None
_feature_flags_cache_time: Optional[float] = None

def _load_feature_flags(force_reload: bool = False) -> Dict[str, Any]:
    """Load feature flags configuration from JSON file (with caching)"""
    import json
    import time
    from pathlib import Path
    from typing import Optional
    
    global _feature_flags_cache, _feature_flags_cache_time
    
    # Cache for 60 seconds
    cache_ttl = 60.0
    
    if not force_reload and _feature_flags_cache is not None:
        if _feature_flags_cache_time and (time.time() - _feature_flags_cache_time) < cache_ttl:
            return _feature_flags_cache
    
    config_path = Path("config/strategy_feature_flags.json")
    
    try:
        if config_path.exists():
            with open(config_path, 'r') as f:
                _feature_flags_cache = json.load(f)
                _feature_flags_cache_time = time.time()
                return _feature_flags_cache
        else:
            logger.warning(f"Feature flags file not found: {config_path}")
            _feature_flags_cache = {}
            _feature_flags_cache_time = time.time()
            return {}
    except Exception as e:
        logger.warning(f"Failed to load feature flags: {e}")
        _feature_flags_cache = {}
        _feature_flags_cache_time = time.time()
        return {}
```

---

### 6. Missing Confidence Field Mapping for All Strategies

**Issue:** `_meets_confidence_threshold()` only has partial mapping.

**Current:**
```python
confidence_fields = {
    "order_block_rejection": "ob_strength",
    "fvg_retracement": "fvg_strength",
    "breaker_block": "breaker_block_strength",
    # ... etc
}
```

**Missing:**
- mitigation_block
- market_structure_shift
- inducement_reversal
- premium_discount_array
- kill_zone
- session_liquidity_run

**Fix:**
```python
confidence_fields = {
    "order_block_rejection": "ob_strength",
    "fvg_retracement": "fvg_strength",
    "breaker_block": "breaker_block_strength",
    "mitigation_block": "mitigation_block_strength",
    "market_structure_shift": "mss_strength",
    "inducement_reversal": "inducement_strength",
    "premium_discount_array": "fib_strength",  # Or None if not applicable
    "kill_zone": None,  # Time-based, no confidence score
    "session_liquidity_run": "session_liquidity_strength",
    # Existing strategies
    "liquidity_sweep_reversal": "sweep_strength",
    "trend_pullback_ema": None,  # May not have confidence score
    # ... etc
}
```

---

### 7. Equity Calculation Logic Issue

**Issue:** In `_update_metrics()`, when updating existing row, equity calculation uses `row[11] + pnl`, but `row[11]` is `current_equity` which already includes previous PnL.

**Current Code:**
```python
current_equity = row[11] + pnl  # row[11] is current_equity
```

**Problem:**
- If `current_equity` already includes all previous trades, adding `pnl` again would double-count
- OR if `current_equity` is the equity BEFORE this trade, then adding `pnl` is correct

**Need to Clarify:**
- Is `current_equity` the equity BEFORE this trade (needs +pnl)?
- OR is `current_equity` the equity AFTER all previous trades (shouldn't add pnl again)?

**Likely Correct (if current_equity is before this trade):**
```python
# current_equity is equity before this trade
current_equity = row[11] + pnl  # Add this trade's PnL
peak_equity = max(row[10], current_equity) if row[10] else current_equity
```

**But Need to Verify:** The logic assumes `current_equity` is the equity state BEFORE this trade, which seems correct.

---

### 8. Missing Initial Equity Tracking

**Issue:** Initial equity is only set on first trade. If strategy is reset or database is cleared, initial equity may be lost.

**Solution:** Store initial equity in database:
```sql
ALTER TABLE strategy_performance ADD COLUMN initial_equity REAL DEFAULT 10000.0;
```

**Or:** Track initial equity globally (not per strategy):
```python
# In _update_metrics():
if not row:
    # First trade for this strategy
    # Get initial equity (same for all strategies on first trade)
    initial_equity = _get_initial_equity()
    current_equity = initial_equity + pnl
    # ...
else:
    # Subsequent trades
    # Use stored initial_equity or calculate from first trade
    initial_equity = row.get('initial_equity') or _calculate_initial_from_history(strategy_name)
    current_equity = row[11] + pnl
```

---

## ✅ MINOR ISSUES

### 9. Missing Documentation for Helper Function Location

**Issue:** Plan doesn't specify WHERE helper functions should be added in `strategy_logic.py`.

**Solution:** Add section:
```markdown
### Helper Functions Location

**Where to Add:** Add all helper functions (`_load_feature_flags`, `_fn_to_strategy_name`, `_check_circuit_breaker`, etc.) to `app/engine/strategy_logic.py` near the top of the file, after imports and before strategy functions.

**Recommended Location:** After line ~100 (after existing helper functions like `_f()`, `_tf_blob()`, etc.)
```

---

### 10. Missing Error Handling in Strategy Name Extraction

**Issue:** `_extract_strategy_name()` may fail if database query fails.

**Current Code:**
```python
row = self._conn.execute(
    "SELECT notes, context FROM trades WHERE ticket = ?", (ticket,)
).fetchone()
```

**Problem:**
- No error handling if query fails
- No handling if `notes` or `context` columns don't exist

**Fix:**
```python
def _extract_strategy_name(self, ticket: int) -> Optional[str]:
    """Extract strategy name from trade notes or context"""
    from typing import Optional
    import json
    
    try:
        row = self._conn.execute(
            "SELECT notes, context FROM trades WHERE ticket = ?", (ticket,)
        ).fetchone()
    except Exception as e:
        logger.warning(f"Failed to query trade {ticket} for strategy name: {e}")
        return None
    
    if not row:
        return None
    
    try:
        notes, context = row
    except (ValueError, IndexError):
        # Row doesn't have expected columns
        return None
    
    # ... rest of logic ...
```

---

### 11. Missing Validation for Strategy Names

**Issue:** No validation that strategy names match between different systems.

**Solution:** Add validation function:
```python
def _validate_strategy_name(strategy_name: str) -> bool:
    """Validate that strategy name exists in registry"""
    valid_names = [
        "order_block_rejection", "fvg_retracement", "breaker_block",
        "mitigation_block", "market_structure_shift", "inducement_reversal",
        "premium_discount_array", "kill_zone", "session_liquidity_run",
        "liquidity_sweep_reversal", "trend_pullback_ema", "pattern_breakout_retest",
        "opening_range_breakout", "range_fade_sr", "hs_or_double_reversal"
    ]
    return strategy_name in valid_names
```

---

## 📋 INTEGRATION CHECKLIST ADDITIONS

Add to checklist:
- [ ] Implement `_load_feature_flags()` function
- [ ] Verify logger is available in helper functions (module-level)
- [ ] Verify database row indices match schema order
- [ ] Add type hints to all helper functions
- [ ] Add caching to `_load_feature_flags()`
- [ ] Complete confidence field mapping for all strategies
- [ ] Verify equity calculation logic
- [ ] Document helper function location in strategy_logic.py
- [ ] Add error handling to `_extract_strategy_name()`
- [ ] Add strategy name validation function

