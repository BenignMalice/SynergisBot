# Additional Review Issues - Second Pass

## 🔴 CRITICAL ISSUES

### 1. Missing `regime` Variable in `choose_and_build()` Example

**Issue:** The `choose_and_build()` function example references `regime` but doesn't extract it from `tech`.

**Current Code (Line 2429-2441):**
```python
def choose_and_build(...):
    # ... existing logic ...
    
    selected_plan = None
    for fn in _REGISTRY:
        # FIX: Check circuit breaker BEFORE calling strategy function
        strategy_name = _fn_to_strategy_name(fn)
        if _check_circuit_breaker(strategy_name):
            logger.debug(f"Strategy {strategy_name} disabled by circuit breaker, skipping")
            continue
        
        plan = None
        try:
            plan = fn(symbol, tech, regime)  # ❌ regime not defined!
```

**Actual Code:**
```python
regime = str(tech.get("regime") or tech.get("regime_label") or "UNKNOWN").upper()
```

**Fix:**
```python
def choose_and_build(...):
    # Extract regime from tech (like actual code)
    regime = str(tech.get("regime") or tech.get("regime_label") or "UNKNOWN").upper()
    
    # ... existing logic ...
    
    selected_plan = None
    for fn in _REGISTRY:
        # ... rest of code ...
```

---

### 2. Debug Function Bypasses Circuit Breaker

**Issue:** `log_strategy_selection_debug()` calls strategy functions directly, which bypasses circuit breaker checks.

**Current Code (Line 2324-2329):**
```python
for strategy_func in registry:
    strategy_name = strategy_func.__name__.replace("strat_", "")
    
    try:
        # Try to get strategy result
        result = strategy_func(symbol, tech, tech.get("regime", "UNKNOWN"))
        # ❌ This bypasses circuit breaker!
```

**Problem:**
- Debug function calls strategies directly
- Circuit breaker check is skipped
- Inconsistent behavior between debug and actual execution

**Solution:**
```python
def log_strategy_selection_debug(...):
    # ... setup ...
    
    for strategy_func in registry:
        strategy_name = _fn_to_strategy_name(strategy_func)  # Use helper
        
        # Check circuit breaker (same as choose_and_build)
        if _check_circuit_breaker(strategy_name):
            debug_info["strategy_checks"].append({
                "strategy": strategy_name,
                "selected": False,
                "reason": "Circuit breaker disabled"
            })
            continue
        
        try:
            regime = str(tech.get("regime") or tech.get("regime_label") or "UNKNOWN").upper()
            result = strategy_func(symbol, tech, regime)
            # ... rest of logic ...
```

---

### 3. Missing Import in Debug Function

**Issue:** `log_strategy_selection_debug()` uses `json.dumps()` but doesn't import `json`.

**Current Code (Line 2354):**
```python
logger.debug(f"Strategy Selection Debug for {symbol}: {json.dumps(debug_info, indent=2)}")
```

**Fix:**
```python
import json
# ... or at top of file ...
logger.debug(f"Strategy Selection Debug for {symbol}: {json.dumps(debug_info, indent=2)}")
```

---

### 4. Inconsistent Strategy Name Extraction

**Issue:** `_get_strategy_rejection_reason()` uses manual string replacement instead of `_fn_to_strategy_name()` helper.

**Current Code (Line 2368):**
```python
strategy_name = strategy_func.__name__.replace("strat_", "")
```

**Should Use:**
```python
strategy_name = _fn_to_strategy_name(strategy_func)
```

**Also in `log_strategy_selection_debug()` (Line 2325):**
```python
strategy_name = strategy_func.__name__.replace("strat_", "")
```

**Should Use:**
```python
strategy_name = _fn_to_strategy_name(strategy_func)
```

---

### 5. Simplified `choose_and_build()` Example Missing Critical Logic

**Issue:** The example `choose_and_build()` function is too simplified and doesn't show the actual flow.

**Current Example Shows:**
```python
if plan and not getattr(plan, "preview_only", False):
    selected_plan = plan
    break  # ❌ Too simple - actual code has more validation
```

**Actual Code Has:**
- Direction normalization (`_coerce_direction_if_misfit`)
- OCO skip in market mode
- Pending type finalization
- Phase 2 gates (`_phase2_apply_gates`)
- RR floor validation
- Preview handling
- Market mode conversion

**Fix:** Update example to show actual integration point, not full implementation:
```python
# In app/engine/strategy_logic.py, choose_and_build() function:
# ADD circuit breaker check BEFORE existing for loop:

regime = str(tech.get("regime") or tech.get("regime_label") or "UNKNOWN").upper()
# ... existing code ...

for fn in _REGISTRY:
    # NEW: Check circuit breaker BEFORE calling strategy
    strategy_name = _fn_to_strategy_name(fn)
    if _check_circuit_breaker(strategy_name):
        logger.debug(f"Strategy {strategy_name} disabled by circuit breaker, skipping")
        continue
    
    # Existing code continues unchanged:
    plan = None
    try:
        plan = fn(symbol, tech, regime)
        # ... rest of existing validation logic ...
```

---

## ⚠️ MEDIUM PRIORITY ISSUES

### 6. Missing `datetime` Import in Trade Recording Example

**Issue:** Trade recording integration code uses `datetime` but doesn't show import.

**Current Code (Line 1245-1246):**
```python
entry_time=datetime.fromtimestamp(opened_ts).isoformat() if opened_ts else None,
exit_time=datetime.fromtimestamp(closed_ts).isoformat() if closed_ts else None
```

**Fix:** Add import statement:
```python
from datetime import datetime
# ... in close_trade() method ...
```

---

### 7. Strategy Name Extraction Logic May Not Work

**Issue:** `_extract_strategy_name()` tries to parse from notes, but strategy name may not be stored there.

**Current Code (Line 1233-1265):**
```python
def _extract_strategy_name(self, ticket: int) -> Optional[str]:
    """Extract strategy name from trade notes or context"""
    # Check if strategy is stored in notes or context field
    row = self._conn.execute(
        "SELECT notes, context FROM trades WHERE ticket = ?", (ticket,)
    ).fetchone()
    
    if row:
        notes, context = row
        # Try to parse from notes (e.g., "strategy: order_block_rejection")
        if notes:
            for strategy in ["order_block_rejection", "fvg_retracement", "breaker_block", ...]:
                if strategy in notes.lower():
                    return strategy
```

**Problem:**
- Strategy name may not be in notes
- Hardcoded strategy list needs maintenance
- May return wrong strategy if multiple match

**Better Solution:**
```python
def _extract_strategy_name(self, ticket: int) -> Optional[str]:
    """Extract strategy name from trade notes or context"""
    row = self._conn.execute(
        "SELECT notes, context FROM trades WHERE ticket = ?", (ticket,)
    ).fetchone()
    
    if not row:
        return None
    
    notes, context = row
    
    # Try context JSON first (more reliable)
    if context:
        try:
            import json
            ctx = json.loads(context) if isinstance(context, str) else context
            strategy = ctx.get("strategy") or ctx.get("strategy_name")
            if strategy:
                return strategy
        except Exception:
            pass
    
    # Try notes parsing (fallback)
    if notes:
        # Look for explicit "strategy:" prefix
        if "strategy:" in notes.lower():
            parts = notes.lower().split("strategy:")
            if len(parts) > 1:
                strategy = parts[1].strip().split()[0]  # Get first word after "strategy:"
                return strategy
        
        # Fallback: check against known strategies (less reliable)
        known_strategies = [
            "order_block_rejection", "fvg_retracement", "breaker_block",
            "mitigation_block", "market_structure_shift", "inducement_reversal",
            "premium_discount_array", "kill_zone", "session_liquidity_run",
            "liquidity_sweep_reversal", "trend_pullback_ema", "pattern_breakout_retest",
            "opening_range_breakout", "range_fade_sr", "hs_or_double_reversal"
        ]
        for strategy in known_strategies:
            if strategy in notes.lower():
                return strategy
    
    return None
```

**Also Need:** Ensure strategy name is stored when trade is created. Check where trades are logged and add strategy name to context.

---

### 8. Missing Error Handling in Circuit Breaker Check

**Issue:** `_check_circuit_breaker()` may raise exception if circuit breaker fails to initialize.

**Current Code (Line 1126-1129):**
```python
def _check_circuit_breaker(strategy_name: str) -> bool:
    """Check if strategy is disabled by circuit breaker"""
    # FIX: Moved to choose_and_build() - this is kept for reference but not used in strategies
    from infra.strategy_circuit_breaker import StrategyCircuitBreaker
    breaker = StrategyCircuitBreaker()
    return not breaker.is_strategy_disabled(strategy_name)
```

**Problem:**
- If `StrategyCircuitBreaker()` fails to initialize, exception will propagate
- Should have graceful fallback

**Fix:**
```python
def _check_circuit_breaker(strategy_name: str) -> bool:
    """Check if strategy is disabled by circuit breaker"""
    try:
        from infra.strategy_circuit_breaker import StrategyCircuitBreaker
        breaker = StrategyCircuitBreaker()
        return not breaker.is_strategy_disabled(strategy_name)
    except Exception as e:
        # Graceful degradation: if circuit breaker fails, allow strategy
        logger.warning(f"Circuit breaker check failed for {strategy_name}: {e}")
        return True  # Allow strategy if we can't check
```

---

### 9. Missing Import for `logging` in Debug Function

**Issue:** `log_strategy_selection_debug()` uses `logger` but doesn't show import.

**Fix:** Add to imports section:
```python
import logging
logger = logging.getLogger(__name__)
```

---

### 10. Incomplete `choose_and_build()` Integration

**Issue:** The example shows `break` after finding a plan, but actual code continues validation.

**Current Example:**
```python
if plan and not getattr(plan, "preview_only", False):
    selected_plan = plan
    break  # ❌ Too early - actual code validates RR, etc.
```

**Actual Flow:**
1. Get plan from strategy
2. Normalize direction
3. Skip OCO in market mode
4. Finalize pending type
5. Apply phase 2 gates
6. Check RR floor
7. Handle preview
8. Convert to market if needed
9. Return plan

**Fix:** Show integration point more clearly:
```python
# ADD THIS BEFORE the existing for loop in choose_and_build():

for fn in _REGISTRY:
    # NEW: Circuit breaker check (add here)
    strategy_name = _fn_to_strategy_name(fn)
    if _check_circuit_breaker(strategy_name):
        logger.debug(f"Strategy {strategy_name} disabled by circuit breaker, skipping")
        continue
    
    # EXISTING CODE CONTINUES UNCHANGED:
    plan = None
    try:
        plan = fn(symbol, tech, regime)
        # ... all existing validation continues ...
```

---

## ✅ MINOR ISSUES

### 11. Missing Type Hints

**Issue:** Some helper functions don't have type hints.

**Fix:** Add type hints:
```python
from typing import Dict, Any, Optional, List, Callable

def _fn_to_strategy_name(fn: Callable) -> str:
    """Convert function name to normalized strategy name"""
    # ...

def _check_circuit_breaker(strategy_name: str) -> bool:
    """Check if strategy is disabled by circuit breaker"""
    # ...

def _get_confidence_threshold(strategy_name: str) -> float:
    """Get confidence threshold for strategy"""
    # ...
```

---

### 12. Inconsistent Error Messages

**Issue:** Some error messages use different formats.

**Fix:** Standardize error message format:
```python
logger.warning(f"Circuit breaker: Could not check {metric} for {strategy_name}: {e}")
```

---

### 13. Missing Documentation for Strategy Name Storage

**Issue:** Plan doesn't document where/how strategy name should be stored with trades.

**Fix:** Add section:
```markdown
### Strategy Name Storage in Trades

**Requirement:** Strategy name must be stored with each trade so performance tracker can record it.

**Storage Options:**
1. **Context JSON field** (Recommended):
   ```python
   context = {"strategy": "order_block_rejection", ...}
   ```

2. **Notes field** (Fallback):
   ```python
   notes = f"strategy: order_block_rejection; {other_notes}"
   ```

**Where to Add:**
- When trade is logged in `JournalRepo.log_trade()` or similar
- When plan is executed in auto-execution system
- Store in `context` JSON field for reliable parsing
```

---

## 📋 INTEGRATION CHECKLIST ADDITIONS

Add to checklist:
- [ ] Fix `regime` variable extraction in `choose_and_build()` example
- [ ] Fix debug function to use circuit breaker check
- [ ] Add missing imports (`json`, `datetime`, `logging`)
- [ ] Use `_fn_to_strategy_name()` consistently everywhere
- [ ] Add error handling to `_check_circuit_breaker()`
- [ ] Update `choose_and_build()` example to show actual integration point
- [ ] Improve `_extract_strategy_name()` logic
- [ ] Document strategy name storage requirements
- [ ] Add type hints to helper functions
- [ ] Standardize error message formats

