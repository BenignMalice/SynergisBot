# Plan Review - Integration, Logic, and Consistency Issues

## 🔴 CRITICAL ISSUES

### 1. Trade Recording Integration Point Missing

**Issue:** The plan specifies that `performance_tracker.record_trade()` should be called "after trade closes" but doesn't specify WHERE in the codebase this should happen.

**Current State:**
- `JournalRepo.close_trade()` exists in `infra/journal_repo.py`
- `on_position_closed_app()` exists in `handlers/trading.py`
- `PaperTradingEngine._close_trade()` exists in `infra/paper_trading_system.py`

**Solution Required:**
- Add integration point in `JournalRepo.close_trade()` method
- Add integration point in `on_position_closed_app()` handler
- Specify how to extract strategy name from trade context
- Specify how to calculate RR from trade data

**Code Location to Add:**
```python
# In infra/journal_repo.py, close_trade() method:
def close_trade(self, ticket: int, exit_price: float, close_reason: str, 
                pnl: float = None, r_multiple: float = None, closed_ts: int = None) -> bool:
    # ... existing code ...
    
    # NEW: Record to performance tracker
    try:
        from infra.strategy_performance_tracker import StrategyPerformanceTracker
        tracker = StrategyPerformanceTracker()
        
        # Get strategy name from trade context or notes
        strategy_name = self._extract_strategy_name(ticket)  # Need to implement
        if strategy_name:
            result = "win" if pnl > 0 else ("loss" if pnl < 0 else "breakeven")
            tracker.record_trade(
                strategy_name=strategy_name,
                symbol=symbol,  # from trade record
                result=result,
                pnl=pnl or 0.0,
                rr=r_multiple,
                entry_price=entry_price,  # from trade record
                exit_price=exit_price,
                entry_time=entry_time,  # from trade record
                exit_time=datetime.fromtimestamp(closed_ts).isoformat() if closed_ts else None
            )
    except Exception as e:
        logger.warning(f"Failed to record trade to performance tracker: {e}")
```

**Missing Implementation:**
- `_extract_strategy_name()` method to get strategy from trade notes/context
- Strategy name storage in trade records

---

### 2. Circuit Breaker Integration Location Incorrect

**Issue:** The plan shows circuit breaker checks INSIDE each strategy function, but this is inefficient and violates DRY principle.

**Current Plan Shows:**
```python
def strat_order_block_rejection(...):
    if not _check_circuit_breaker("order_block_rejection"):
        return None
```

**Problem:**
- Every strategy function needs this check (code duplication)
- Circuit breaker should be checked ONCE in `choose_and_build()`, not in each strategy
- More efficient to check before iterating through strategies

**Solution Required:**
- Move circuit breaker check to `choose_and_build()` function
- Check circuit breaker BEFORE calling strategy function
- Remove circuit breaker checks from individual strategy functions

**Correct Implementation:**
```python
# In app/engine/strategy_logic.py, choose_and_build() function:
def choose_and_build(symbol: str, tech: Dict[str, Any], mode: Literal["market", "pending"] = "pending") -> Optional["StrategyPlan"]:
    # ... existing code ...
    
    for fn in _REGISTRY:
        # NEW: Check circuit breaker BEFORE calling strategy
        strategy_name = fn.__name__.replace("strat_", "").replace("_", "_")  # Extract name
        if _check_circuit_breaker(strategy_name):
            logger.debug(f"Strategy {strategy_name} disabled by circuit breaker, skipping")
            continue
        
        plan = None
        try:
            plan = fn(symbol, tech, regime)
            # ... rest of existing logic ...
```

**Note:** Need helper function to map function name to strategy name:
```python
def _fn_to_strategy_name(fn) -> str:
    """Convert function name to strategy name"""
    name = fn.__name__.replace("strat_", "")
    # Map: strat_order_block_rejection -> order_block_rejection
    return name
```

---

### 3. Performance Tracker Equity Calculation Issue

**Issue:** Hardcoded initial equity of 10000.0 in `_update_metrics()` method.

**Current Code:**
```python
initial_equity = 10000.0  # Starting equity
```

**Problem:**
- Should use actual account equity from MT5 or settings
- Hardcoded value doesn't reflect real account state
- Drawdown calculation will be incorrect

**Solution Required:**
- Get initial equity from account balance or settings
- Store initial equity per strategy or globally
- Use actual account equity for drawdown calculations

**Fix:**
```python
# In _update_metrics():
if not row:
    # Get initial equity from account or settings
    from config import settings
    initial_equity = getattr(settings, "INITIAL_EQUITY", 10000.0)
    # Or get from MT5 account:
    # from infra.mt5_service import MT5Service
    # mt5 = MT5Service()
    # initial_equity = mt5.account_balance() or 10000.0
    
    current_equity = initial_equity + pnl
    # ... rest of code ...
```

---

### 4. Variable Name Conflict in `_update_metrics()`

**Issue:** `timestamp` variable used before definition in update path.

**Current Code (Line 627-630):**
```python
# Update dates
last_win_date = timestamp if result == "win" else row[12]
last_loss_date = timestamp if result == "loss" else row[13]
last_breakeven_date = timestamp if result == "breakeven" else row[14]
timestamp = datetime.now().isoformat()  # Defined AFTER use!
```

**Problem:**
- `timestamp` is used on lines 627-629 but defined on line 630
- This will cause `NameError: name 'timestamp' is not defined`

**Solution:**
```python
# Fix: Define timestamp BEFORE using it
timestamp = datetime.now().isoformat()

# Update dates
last_win_date = timestamp if result == "win" else row[12]
last_loss_date = timestamp if result == "loss" else row[13]
last_breakeven_date = timestamp if result == "breakeven" else row[14]
```

---

### 5. Foreign Key Constraint Issue

**Issue:** `trade_results` table has foreign key to `strategy_performance`, but strategy might not exist in performance table yet.

**Current Schema:**
```sql
FOREIGN KEY (strategy_name) REFERENCES strategy_performance(strategy_name)
```

**Problem:**
- If strategy doesn't exist in `strategy_performance` table, INSERT will fail
- Foreign key constraint prevents inserting trade before strategy metrics exist
- Circular dependency: need strategy in performance table, but performance table is updated by trades

**Solution Options:**

**Option A: Remove Foreign Key (Recommended)**
```sql
-- Remove foreign key constraint
CREATE TABLE IF NOT EXISTS trade_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT NOT NULL,  -- No foreign key
    -- ... rest of fields ...
);
```

**Option B: Auto-create Strategy Entry**
```python
# In record_trade(), before INSERT:
# Ensure strategy exists in performance table
cursor.execute("SELECT 1 FROM strategy_performance WHERE strategy_name = ?", (strategy_name,))
if not cursor.fetchone():
    # Create empty entry
    cursor.execute("""
        INSERT INTO strategy_performance (strategy_name, last_updated)
        VALUES (?, ?)
    """, (strategy_name, datetime.now().isoformat()))
```

**Recommendation:** Use Option A (remove foreign key) - it's simpler and strategy names are just strings, not critical referential integrity.

---

### 6. Circuit Breaker Circular Dependency Risk

**Issue:** Circuit breaker checks performance metrics, but performance tracker might not be initialized or might fail.

**Current Code:**
```python
def _check_consecutive_losses(self, strategy_name: str, settings: Dict) -> bool:
    try:
        from infra.strategy_performance_tracker import StrategyPerformanceTracker
        tracker = StrategyPerformanceTracker()
        metrics = tracker.get_metrics(strategy_name)
        # ...
```

**Problem:**
- If performance tracker fails to initialize, circuit breaker will fail
- If database doesn't exist yet, circuit breaker will fail
- No graceful degradation

**Solution:**
```python
def _check_consecutive_losses(self, strategy_name: str, settings: Dict) -> bool:
    """Check if strategy has exceeded max consecutive losses"""
    max_losses = settings.get("max_consecutive_losses", 3)
    
    try:
        from infra.strategy_performance_tracker import StrategyPerformanceTracker
        tracker = StrategyPerformanceTracker()
        metrics = tracker.get_metrics(strategy_name)
        
        if metrics and metrics.get("consecutive_losses", 0) >= max_losses:
            return True
    except Exception as e:
        # Graceful degradation: if tracker fails, don't block strategy
        logger.warning(f"Circuit breaker: Could not check consecutive losses for {strategy_name}: {e}")
        return False  # Don't disable if we can't check
    
    return False
```

**Apply same pattern to:**
- `_check_win_rate()`
- `_check_drawdown()`

---

### 7. Strategy Name Consistency

**Issue:** Strategy names must match exactly across:
- `_REGISTRY` function names
- Feature flags JSON
- Performance tracker
- Circuit breaker
- Strategy map configuration

**Current Mismatch Risk:**
- Function: `strat_order_block_rejection`
- Strategy name in plan: `"order_block_rejection"`
- But what if feature flag uses different name?

**Solution Required:**
- Create mapping function to normalize strategy names
- Document exact strategy names to use everywhere
- Add validation to ensure consistency

**Implementation:**
```python
# In app/engine/strategy_logic.py:
STRATEGY_NAME_MAP = {
    "strat_order_block_rejection": "order_block_rejection",
    "strat_fvg_retracement": "fvg_retracement",
    "strat_breaker_block": "breaker_block",
    # ... etc
}

def _fn_to_strategy_name(fn) -> str:
    """Convert function to normalized strategy name"""
    fn_name = fn.__name__
    return STRATEGY_NAME_MAP.get(fn_name, fn_name.replace("strat_", ""))
```

---

### 8. Debug Parameter Doesn't Exist

**Issue:** Plan shows `choose_and_build()` with `debug` parameter, but actual codebase doesn't have this.

**Plan Shows:**
```python
def choose_and_build(..., debug: bool = False):
```

**Actual Code:**
```python
def choose_and_build(symbol: str, tech: Dict[str, Any], mode: Literal["market", "pending"] = "pending"):
```

**Solution:**
- Either add `debug` parameter to actual function
- Or remove from plan and use logger level instead
- Or use environment variable for debug mode

**Recommendation:** Use logger level instead:
```python
# In choose_and_build():
if logger.isEnabledFor(logging.DEBUG):
    log_strategy_selection_debug(...)
```

---

## ⚠️ MEDIUM PRIORITY ISSUES

### 9. Duplicate `consecutive_losses` Field

**Issue:** `circuit_breaker_status` table has `consecutive_losses` field, but this is also in `strategy_performance` table.

**Current Schema:**
```sql
-- circuit_breaker_status
consecutive_losses INTEGER DEFAULT 0

-- strategy_performance  
consecutive_losses INTEGER DEFAULT 0
```

**Problem:**
- Data duplication
- Risk of inconsistency
- Unnecessary storage

**Solution:**
- Remove `consecutive_losses` from `circuit_breaker_status`
- Always read from `strategy_performance` table
- Keep `circuit_breaker_status` for disable state only

---

### 10. Missing Strategy Name in Trade Records

**Issue:** Need to store strategy name with trade so performance tracker can record it.

**Current State:**
- `JournalRepo` stores trades but may not store strategy name
- Need to verify if `notes` or `context` field contains strategy name

**Solution:**
- Add `strategy` field to trades table (if not exists)
- Or parse strategy name from `notes` field
- Or store in `context` JSON field

**Check Required:**
- Review `JournalRepo` schema
- Verify how strategy name is currently stored
- Add strategy name extraction logic

---

### 11. Confidence Threshold Configuration Missing

**Issue:** Plan references `_get_confidence_threshold()` but doesn't specify where thresholds are configured.

**Current Code:**
```python
threshold = _get_confidence_threshold(strategy_name)
```

**Missing:**
- Configuration file for thresholds
- Default values
- Strategy-specific overrides

**Solution:**
```python
# In config/strategy_feature_flags.json:
{
  "confidence_thresholds": {
    "order_block_rejection": 0.5,
    "fvg_retracement": 0.6,
    "breaker_block": 0.55,
    # ... etc
  }
}

# Helper function:
def _get_confidence_threshold(strategy_name: str) -> float:
    """Get confidence threshold for strategy"""
    flags = _load_feature_flags()
    thresholds = flags.get("confidence_thresholds", {})
    return thresholds.get(strategy_name, 0.5)  # Default 0.5
```

---

### 12. Circuit Breaker Database Path Inconsistency

**Issue:** Circuit breaker and performance tracker use different database paths.

**Current:**
- Circuit breaker: `data/strategy_performance.db` (same file)
- Performance tracker: `data/strategy_performance.db` (same file)

**Actually:** They use the SAME database file, which is good, but:
- Circuit breaker creates `circuit_breaker_status` table
- Performance tracker creates `strategy_performance` and `trade_results` tables
- Need to ensure both initialize correctly

**Solution:**
- Both classes should handle missing tables gracefully
- Or create a shared database initialization function
- Document that they share the same database file

---

## ✅ MINOR ISSUES / CLARIFICATIONS

### 13. Strategy Plan Field Completeness

**Issue:** Plan examples don't show all required StrategyPlan fields.

**Required Fields (from codebase):**
```python
@dataclass
class StrategyPlan:
    symbol: str
    strategy: str
    regime: str
    direction: str
    pending_type: str
    entry: float
    sl: Optional[float]
    tp: Optional[float]
    rr: Optional[float]
    notes: str
    ttl_min: Optional[int] = None
    oco_companion: Optional[Dict[str, Any]] = None
    blocked_by: List[str] = field(default_factory=list)
    preview_only: bool = False
    risk_pct: Optional[float] = None
```

**Solution:**
- Ensure all strategy examples show complete StrategyPlan creation
- Include all required fields in examples

---

### 14. Feature Flag Default Behavior

**Issue:** What happens if feature flag file doesn't exist?

**Current Code:**
```python
def _load_feature_flags():
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}
```

**Problem:**
- Returns empty dict, so `_is_strategy_enabled()` will return `False`
- All strategies will be disabled by default
- Should strategies be enabled by default if file missing?

**Solution:**
- Document default behavior
- Or provide default enabled state for core strategies
- Or require feature flag file to exist

---

## 📋 INTEGRATION CHECKLIST

Before implementation, verify:

- [ ] Trade recording integration point identified and implemented
- [ ] Circuit breaker moved to `choose_and_build()` (not in strategies)
- [ ] Performance tracker equity calculation uses real account balance
- [ ] Variable name conflict fixed in `_update_metrics()`
- [ ] Foreign key constraint removed or handled
- [ ] Circuit breaker graceful degradation implemented
- [ ] Strategy name mapping function created
- [ ] Debug parameter removed or added to actual function
- [ ] Duplicate `consecutive_losses` field removed
- [ ] Strategy name storage in trades verified
- [ ] Confidence threshold configuration added
- [ ] Database initialization shared between components
- [ ] All StrategyPlan fields included in examples
- [ ] Feature flag default behavior documented

---

## 🔧 RECOMMENDED FIXES PRIORITY

1. **CRITICAL (Must Fix Before Implementation):**
   - Trade recording integration point (#1)
   - Circuit breaker integration location (#2)
   - Variable name conflict (#4)
   - Foreign key constraint (#5)

2. **HIGH (Fix During Implementation):**
   - Performance tracker equity (#3)
   - Circuit breaker graceful degradation (#6)
   - Strategy name consistency (#7)

3. **MEDIUM (Fix Before Production):**
   - Duplicate consecutive_losses (#9)
   - Strategy name in trades (#10)
   - Confidence threshold config (#11)

4. **LOW (Documentation/Clarification):**
   - Debug parameter (#8)
   - Database path consistency (#12)
   - StrategyPlan completeness (#13)
   - Feature flag defaults (#14)

