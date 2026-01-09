# Fourth Review Issues - Final Pass

## 🔴 CRITICAL ISSUES

### 1. Row Index Mismatch in `_update_metrics()`

**Issue:** Row indices don't match the comment documentation.

**Comment Says (Line 642-645):**
```python
# Row indices (0-based): 0=strategy_name, 1=win_rate, 2=avg_rr, 3=total_trades,
# 4=total_wins, 5=total_losses, 6=total_breakeven, 7=consecutive_losses,
```

**Code Uses:**
```python
total_trades = row[2] + 1  # ❌ Should be row[3] if comment is correct
total_wins = row[3] + (1 if result == "win" else 0)  # ❌ Should be row[4]
total_losses = row[4] + (1 if result == "loss" else 0)  # ❌ Should be row[5]
total_breakeven = row[5] + (1 if result == "breakeven" else 0)  # ❌ Should be row[6]
current_avg_rr = row[1] if row[1] else 0.0  # ❌ Should be row[2] if comment is correct
avg_rr = row[1]  # ❌ Should be row[2]
consecutive_losses = row[7] + 1  # ✓ Correct
```

**Problem:** The code uses indices that are off by 1 from the comment. Either:
- The comment is wrong, OR
- The code is wrong

**Actual Schema Order:**
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

**Fix:** Code is WRONG. Should be:
```python
total_trades = row[3] + 1  # ✓
total_wins = row[4] + (1 if result == "win" else 0)  # ✓
total_losses = row[5] + (1 if result == "loss" else 0)  # ✓
total_breakeven = row[6] + (1 if result == "breakeven" else 0)  # ✓
current_avg_rr = row[2] if row[2] else 0.0  # ✓
avg_rr = row[2]  # ✓
```

---

### 2. Global Variable Initialization Issue

**Issue:** `_load_feature_flags()` uses `globals()` check which is unreliable.

**Current Code:**
```python
if '_feature_flags_cache' not in globals():
    _feature_flags_cache = None
    _feature_flags_cache_time = None
```

**Problem:**
- `globals()` check is unreliable
- Variables should be initialized at module level
- May cause issues in some Python environments

**Fix:**
```python
# At module level (top of file, after imports):
_feature_flags_cache: Optional[Dict[str, Any]] = None
_feature_flags_cache_time: Optional[float] = None

# In function:
def _load_feature_flags() -> Dict[str, Any]:
    """Load feature flags configuration from JSON file (with caching)"""
    import json
    import time
    from pathlib import Path
    
    global _feature_flags_cache, _feature_flags_cache_time
    cache_ttl = 60.0
    
    # Remove the globals() check - variables are already declared at module level
    if _feature_flags_cache is not None and _feature_flags_cache_time:
        if (time.time() - _feature_flags_cache_time) < cache_ttl:
            return _feature_flags_cache
    
    # ... rest of code ...
```

---

### 3. Missing `tf` Parameter in `_atr()` Call

**Issue:** Plan shows `_atr(tech)` but actual function signature is `_atr(tech, tf="M15", period=14)`.

**Current Code (Line 1463):**
```python
atr = _atr(tech)
```

**Actual Function:**
```python
def _atr(tech: dict, tf: str = "M15", period: int = 14) -> float | None:
```

**Fix:** Code is correct (uses default `tf="M15"`), but should document:
```python
atr = _atr(tech)  # Uses default tf="M15", period=14
# Or explicitly:
atr = _atr(tech, tf="M15", period=14)
```

---

### 4. Missing StrategyPlan Creation Examples

**Issue:** Strategy implementation sections don't show complete StrategyPlan creation.

**Current:** Only shows logic, not actual plan creation.

**Fix:** Add example:
```python
# After all calculations:
return StrategyPlan(
    symbol=symbol,
    strategy="order_block_rejection",
    regime=regime,
    direction="LONG" if ob_bull else "SHORT",
    pending_type="BUY_STOP" if ob_bull else "SELL_STOP",  # Or use _pending_type_from_entry()
    entry=entry_price,
    sl=sl_price,
    tp=tp_price,
    rr=_calc_rr("LONG" if ob_bull else "SHORT", entry_price, sl_price, tp_price),
    notes=f"Order Block Rejection: {ob_strength:.2f} strength, {len(ob_confluence)} confluence factors",
    ttl_min=None,
    oco_companion=None,
    blocked_by=[],
    preview_only=False,
    risk_pct=None
)
```

---

### 5. Missing Error Handling for Row Access

**Issue:** Code accesses `row[11]`, `row[10]`, etc. without checking if row has enough elements.

**Current Code:**
```python
current_equity = row[11] + pnl
peak_equity = max(row[10], current_equity) if row[10] else current_equity
```

**Problem:** If row doesn't have 12 elements, will raise `IndexError`.

**Fix:**
```python
# Safe access with defaults
current_equity = (row[11] if len(row) > 11 else 0.0) + pnl
peak_equity = max((row[10] if len(row) > 10 else 0.0), current_equity)
```

**Better Fix:** Use named columns or verify row length:
```python
if len(row) < 17:  # Need at least 17 columns
    logger.error(f"Row for {strategy_name} has insufficient columns: {len(row)}")
    return

# Or use row_factory for named access
```

---

## ⚠️ MEDIUM PRIORITY ISSUES

### 6. Missing Documentation for Helper Function Dependencies

**Issue:** Plan doesn't document that strategies depend on existing helper functions.

**Missing Documentation:**
- `_atr(tech, tf="M15", period=14)` - exists, takes tf parameter
- `_strat_cfg(strategy_name, symbol, tech, regime)` - exists
- `_allowed_here(cfg, tech, regime)` - exists
- `_determine_strategy_direction(tech, strategy_name)` - exists
- `_calc_rr(side, entry, sl, tp)` - exists
- `_pending_type_from_entry(side, entry, price_now, tol)` - exists

**Fix:** Add section:
```markdown
### Existing Helper Functions Available

Strategies can use these existing helper functions from `strategy_logic.py`:

- `_atr(tech, tf="M15", period=14)` - Get ATR value
- `_strat_cfg(strategy_name, symbol, tech, regime)` - Get strategy configuration
- `_allowed_here(cfg, tech, regime)` - Check if strategy allowed in current context
- `_determine_strategy_direction(tech, strategy_name)` - Determine direction from tech dict
- `_calc_rr(side, entry, sl, tp)` - Calculate risk-reward ratio
- `_pending_type_from_entry(side, entry, price_now, tol)` - Determine pending order type
- `_price(tech, tf=None)` - Get current price
- `_adx(tech)` - Get ADX value
```

---

### 7. Incomplete Strategy Implementation Examples

**Issue:** Strategy examples show logic but not complete implementation with all StrategyPlan fields.

**Fix:** Add complete example for at least one strategy showing:
- All early exit checks
- Direction determination
- Entry/SL/TP calculation
- StrategyPlan creation with all fields
- Error handling

---

### 8. Missing Type Hints in Some Functions

**Issue:** `_update_metrics()` doesn't have type hints for `cursor` parameter.

**Current:**
```python
def _update_metrics(self, strategy_name: str, result: str, pnl: float, rr: Optional[float], cursor):
```

**Fix:**
```python
from sqlite3 import Cursor

def _update_metrics(self, strategy_name: str, result: str, pnl: float, rr: Optional[float], cursor: Cursor):
```

---

## ✅ MINOR ISSUES

### 9. Missing Documentation for Strategy Name Storage

**Issue:** Plan doesn't specify WHERE strategy name should be stored when trade is created.

**Fix:** Add section:
```markdown
### Strategy Name Storage in Trades

**When Trade is Created:**
- Store strategy name in `context` JSON field: `{"strategy": "order_block_rejection", ...}`
- Or in `notes` field: `"strategy: order_block_rejection; ..."`

**Where to Add:**
- In auto-execution system when plan is executed
- In `JournalRepo.log_trade()` or similar trade logging function
- Ensure strategy name is available for `_extract_strategy_name()` to find
```

---

### 10. Missing Error Handling in Row Index Access

**Issue:** Multiple places access row indices without bounds checking.

**Fix:** Add helper function:
```python
def _safe_row_get(row: tuple, index: int, default: Any = None) -> Any:
    """Safely get row value by index"""
    try:
        if len(row) > index:
            return row[index]
        return default
    except (IndexError, TypeError):
        return default
```

---

## 📋 INTEGRATION CHECKLIST ADDITIONS

Add to checklist:
- [ ] Fix row index mismatches in `_update_metrics()`
- [ ] Initialize `_feature_flags_cache` at module level (not in function)
- [ ] Add complete StrategyPlan creation examples
- [ ] Document existing helper function dependencies
- [ ] Add error handling for row index access
- [ ] Add type hints to `_update_metrics()` cursor parameter
- [ ] Document strategy name storage requirements
- [ ] Add bounds checking for row access

