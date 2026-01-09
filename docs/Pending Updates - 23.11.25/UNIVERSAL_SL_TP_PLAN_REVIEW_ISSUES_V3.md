# Universal Dynamic SL/TP Plan - Third Review Issues

**Date:** November 23, 2025  
**Status:** Comprehensive Review - Additional Issues Identified

---

## 🔴 Critical Issues

### 1. Registration Timing Conflict with DTMS

**Location:** Lines 1604-1614 (Auto-Execution Integration)

**Problem:** The plan shows registering with Universal Manager after execution, but the auto-execution system **already registers with DTMS** at line 2265 in `auto_execution_system.py`. This creates a race condition:

1. Trade executes
2. Auto-execution system registers with DTMS (line 2265)
3. Auto-execution system registers with Universal Manager (plan line 1605)
4. Both systems may try to set `managed_by` flag

**Impact:** Ownership conflict - both systems may claim ownership of the same trade.

**Fix:** Add explicit registration order and conflict resolution:

```python
# In auto_execution_system.py _execute_trade()
# After position opened:
ticket = position.ticket

# 1. Check if strategy_type indicates Universal Manager should handle
strategy_type = plan.conditions.get("strategy_type")
if strategy_type and strategy_type in UNIVERSAL_MANAGED_STRATEGIES:
    # Register with Universal Manager FIRST
    universal_sl_tp_manager.register_trade(
        ticket=ticket,
        symbol=plan.symbol,
        strategy_type=strategy_type,
        direction=plan.direction,
        entry_price=plan.entry_price,
        initial_sl=plan.stop_loss,
        initial_tp=plan.take_profit,
        plan_id=plan.plan_id
    )
    # DO NOT register with DTMS if Universal Manager owns it
    logger.info(f"Trade {ticket} registered with Universal SL/TP Manager (strategy: {strategy_type})")
else:
    # Register with DTMS (existing behavior)
    try:
        from dtms_integration import auto_register_dtms
        executed_price = result.get("details", {}).get("price_executed") or result.get("details", {}).get("price_requested", 0.0)
        result_dict = {
            'symbol': symbol_norm,
            'direction': direction,
            'entry_price': executed_price,
            'volume': lot_size,
            'stop_loss': plan.stop_loss,
            'take_profit': plan.take_profit
        }
        auto_register_dtms(ticket, result_dict)
    except Exception:
        pass  # Silent failure
```

---

### 2. Missing Enum Definitions

**Location:** Throughout document

**Problem:** The plan references `Session` and `StrategyType` enums but never defines them.

**Impact:** Code will fail with `NameError: name 'Session' is not defined`.

**Fix:** Add enum definitions section:

```python
from enum import Enum

class Session(Enum):
    ASIA = "ASIA"
    LONDON = "LONDON"
    NY = "NY"
    LONDON_NY_OVERLAP = "LONDON_NY_OVERLAP"
    LATE_NY = "LATE_NY"

class StrategyType(Enum):
    BREAKOUT_IB_VOLATILITY_TRAP = "breakout_ib_volatility_trap"
    BREAKOUT_BOS = "breakout_bos"
    TREND_CONTINUATION_PULLBACK = "trend_continuation_pullback"
    TREND_CONTINUATION_BOS = "trend_continuation_bos"
    LIQUIDITY_SWEEP_REVERSAL = "liquidity_sweep_reversal"
    ORDER_BLOCK_REJECTION = "order_block_rejection"
    MEAN_REVERSION_RANGE_SCALP = "mean_reversion_range_scalp"
    MEAN_REVERSION_VWAP_FADE = "mean_reversion_vwap_fade"
    DEFAULT_STANDARD = "default_standard"
    MICRO_SCALP = "micro_scalp"  # Already handled separately
```

---

### 3. TradeRegistry Global Variable Not Initialized

**Location:** Lines 1368-1384

**Problem:** `trade_registry` is referenced as a global dictionary but initialization is not shown. Where is it defined? How is it shared across modules?

**Impact:** `NameError: name 'trade_registry' is not defined` when any module tries to access it.

**Fix:** Create a dedicated module for the registry:

```python
# infra/trade_registry.py
"""
Global trade registry for ownership tracking across all managers.
"""
from typing import Dict, Optional
from dataclasses import dataclass

# Global registry (initialized on import)
trade_registry: Dict[int, 'TradeState'] = {}

def get_trade_state(ticket: int) -> Optional['TradeState']:
    """Get trade state from registry."""
    return trade_registry.get(ticket)

def set_trade_state(ticket: int, trade_state: 'TradeState'):
    """Set trade state in registry."""
    trade_registry[ticket] = trade_state

def remove_trade_state(ticket: int):
    """Remove trade state from registry."""
    if ticket in trade_registry:
        del trade_registry[ticket]

def can_modify_position(ticket: int, manager_name: str) -> bool:
    """Check if manager can modify position."""
    trade_state = trade_registry.get(ticket)
    if not trade_state:
        return False
    return trade_state.managed_by == manager_name

def cleanup_registry():
    """Clear registry on shutdown."""
    trade_registry.clear()
```

Then import in all modules:
```python
from infra.trade_registry import trade_registry, get_trade_state, set_trade_state
```

---

### 4. Ownership Determination Logic Flaw

**Location:** Lines 776-795

**Problem:** The ownership determination logic checks `_is_dtms_managed(ticket)` **during registration**, but DTMS registration happens **after** execution. This creates a timing issue:

1. Trade executes
2. Universal Manager `register_trade()` is called
3. It checks `_is_dtms_managed(ticket)` - returns False (DTMS not registered yet)
4. Sets `managed_by = "universal_sl_tp_manager"`
5. DTMS registration happens later
6. DTMS tries to register but trade already owned by Universal Manager

**Impact:** DTMS may fail to register trades that should be managed by Universal Manager, or vice versa.

**Fix:** Determine ownership **before** registration based on strategy_type, not by checking if DTMS is already managing:

```python
def register_trade(self, ticket, strategy_type, ...):
    # Determine ownership based on strategy_type FIRST
    if strategy_type and strategy_type in UNIVERSAL_MANAGED_STRATEGIES:
        managed_by = "universal_sl_tp_manager"
    else:
        # Not a universal-managed strategy
        # Let DTMS or legacy managers handle it
        managed_by = "legacy_exit_manager"  # Will be overridden by DTMS if DTMS registers
    
    trade_state = TradeState(
        ticket=ticket,
        managed_by=managed_by,
        ...
    )
    
    # Store in global registry
    trade_registry[ticket] = trade_state
    
    # If DTMS tries to register later, it will check ownership and skip if already owned
```

**Alternative:** Make registration order explicit in auto-execution system (see Issue #1).

---

### 5. Missing Position Validation in register_trade()

**Location:** Lines 683-691

**Problem:** `register_trade()` tries to fetch position from MT5, but what if:
- Position doesn't exist yet (race condition)
- MT5 is disconnected
- Position was already closed

**Impact:** `register_trade()` may fail or register with incorrect data.

**Fix:** Add validation and error handling:

```python
def register_trade(self, ticket, symbol, strategy_type, entry_price, initial_sl, 
                   initial_tp, direction, plan_id=None, initial_volume=None):
    # Validate position exists
    try:
        positions = mt5.positions_get(ticket=ticket)
        if not positions or len(positions) == 0:
            logger.error(f"Position {ticket} not found - cannot register")
            return None
        
        position = positions[0]
        
        # Validate position data matches provided data
        if position.symbol != symbol:
            logger.warning(f"Position {ticket} symbol mismatch: {position.symbol} != {symbol}")
        
        # Use position data if not provided
        if initial_volume is None:
            initial_volume = position.volume
        
        if entry_price is None:
            entry_price = position.price_open
        
        if initial_sl is None:
            initial_sl = position.sl
        
        if initial_tp is None:
            initial_tp = position.tp
        
    except Exception as e:
        logger.error(f"Error validating position {ticket}: {e}")
        # Use provided data as fallback
        if initial_volume is None:
            initial_volume = 0.0
    
    # ... rest of registration ...
```

---

### 6. Recovery Logic Race Condition

**Location:** Lines 1230-1303

**Problem:** Recovery logic tries to reconstruct trades, but what if:
- DTMS also tries to recover the same trade
- Multiple managers try to set ownership
- Trade was closed but DB entry still exists

**Impact:** Ownership conflicts during recovery, duplicate registrations.

**Fix:** Add recovery coordination:

```python
def recover_trades_on_startup(self):
    """Recover all active trades from database on startup."""
    # 1. Get all open positions from MT5
    positions = mt5.positions_get()
    if not positions:
        logger.info("No open positions - nothing to recover")
        return
    
    open_tickets = {pos.ticket for pos in positions}
    
    # 2. Load TradeState from database
    recovered = 0
    for ticket in open_tickets:
        # Check if already registered by another system
        if ticket in trade_registry:
            existing_state = trade_registry[ticket]
            if existing_state.managed_by == "universal_sl_tp_manager":
                logger.info(f"Trade {ticket} already registered - skipping recovery")
                continue
        
        trade_state = self._load_trade_state_from_db(ticket)
        
        if trade_state:
            # Verify position still exists
            position = next((p for p in positions if p.ticket == ticket), None)
            if position:
                # Verify ownership matches
                if trade_state.managed_by == "universal_sl_tp_manager":
                    self.active_trades[ticket] = trade_state
                    trade_registry[ticket] = trade_state
                    recovered += 1
                    logger.info(f"Recovered trade {ticket} ({trade_state.strategy_type})")
                else:
                    logger.info(f"Trade {ticket} owned by {trade_state.managed_by} - skipping")
            else:
                logger.warning(f"Trade {ticket} in DB but not in MT5 - cleaning up")
                self._cleanup_trade_from_db(ticket)
        else:
            # No TradeState in DB - check if it should be managed
            # ... existing reconstruction logic ...
```

---

## 🟡 Medium Issues

### 7. Missing Config Validation

**Location:** Lines 1036-1071 (_resolve_trailing_rules)

**Problem:** `_resolve_trailing_rules()` accesses `SYMBOL_RULES[symbol]` and `STRATEGY_RULES[strategy_type]` but these are never defined. Where do they come from? What if symbol/strategy not in config?

**Impact:** `KeyError` if symbol or strategy not in config.

**Fix:** Add config loading and validation:

```python
def _resolve_trailing_rules(self, strategy_type, symbol, session):
    # Load config
    config = self.config
    strategies = config.get("strategies", {})
    symbol_adjustments = config.get("symbol_adjustments", {})
    
    # Get strategy rules
    strategy_key = strategy_type.value if hasattr(strategy_type, 'value') else str(strategy_type)
    if strategy_key not in strategies:
        logger.error(f"Strategy {strategy_key} not in config - using DEFAULT_STANDARD")
        strategy_key = "default_standard"
    
    rules = strategies[strategy_key].copy()
    
    # Get symbol adjustments
    if symbol not in symbol_adjustments:
        logger.warning(f"Symbol {symbol} not in config - using defaults")
        symbol_rules = {}
    else:
        symbol_rules = symbol_adjustments[symbol]
    
    # Validate session exists in symbol_rules
    session_adjustments = symbol_rules.get("session_adjustments", {})
    if session.value not in session_adjustments:
        logger.warning(f"Session {session.value} not in config for {symbol} - using defaults")
        session_adjustments = {"tp_multiplier": 1.0, "sl_tightening": 1.0}
    else:
        session_adjustments = session_adjustments[session.value]
    
    # ... rest of resolution ...
```

---

### 8. Missing MT5 Import Statements

**Location:** Multiple places (lines 685, 961, 2163, etc.)

**Problem:** Code uses `mt5.positions_get()`, `mt5.symbol_info()`, etc. but `import MetaTrader5 as mt5` is not shown in all code blocks.

**Impact:** `NameError: name 'mt5' is not defined`.

**Fix:** Add import statements to all code blocks that use MT5:

```python
import MetaTrader5 as mt5
```

Or use `self.mt5_service` consistently instead of direct MT5 calls.

---

### 9. Database Path Not Defined

**Location:** Line 95, 1346, 2486, etc.

**Problem:** `self.db_path` is used but never shown where it comes from. Is it passed to `__init__`? What's the default?

**Impact:** `AttributeError: 'UniversalDynamicSLTPManager' object has no attribute 'db_path'`.

**Fix:** Document database path initialization:

```python
def __init__(self, db_path: str = None, mt5_service=None):
    """
    Initialize the manager.
    
    Args:
        db_path: Path to SQLite database (default: "data/universal_trades.db")
        mt5_service: MT5Service instance for position modifications
    """
    self.db_path = db_path or "data/universal_trades.db"
    self.mt5_service = mt5_service
    # ... rest of init ...
```

---

### 10. Missing _calculate_trailing_sl Implementation

**Location:** Line 1461, 1110, etc.

**Problem:** `_calculate_trailing_sl()` is called but never fully implemented. Only signature is shown.

**Impact:** Method not implemented - will fail at runtime.

**Fix:** Add full implementation or at least stub with TODO:

```python
def _calculate_trailing_sl(
    self, 
    trade_state: TradeState, 
    rules: Dict,
    atr_multiplier_override: Optional[float] = None
) -> Optional[float]:
    """
    Calculate trailing SL based on strategy and rules.
    
    Returns:
        New SL price, or None if trailing not applicable
    """
    trailing_method = rules.get("trailing_method")
    atr_multiplier = atr_multiplier_override or rules.get("atr_multiplier", 1.5)
    
    if trailing_method == "structure_atr_hybrid":
        # Get structure-based SL
        structure_sl = self._get_structure_based_sl(trade_state, rules)
        # Get ATR-based SL
        atr_sl = self._get_atr_based_sl(trade_state, rules, atr_multiplier)
        # Return the better (closer to price) one
        if trade_state.direction == "BUY":
            return max(structure_sl, atr_sl)
        else:
            return min(structure_sl, atr_sl)
    
    elif trailing_method == "structure_based":
        return self._get_structure_based_sl(trade_state, rules)
    
    elif trailing_method == "atr_basic":
        return self._get_atr_based_sl(trade_state, rules, atr_multiplier)
    
    # ... other methods ...
    
    return None
```

---

### 11. Missing Structure-Based SL Calculation Methods

**Location:** Referenced but not implemented

**Problem:** Methods like `_get_structure_based_sl()`, `_get_atr_based_sl()`, `_get_m1_swing_lows()`, etc. are referenced but never implemented.

**Impact:** Trailing logic will fail.

**Fix:** Add implementation stubs or reference to existing structure detection services.

---

### 12. Partial Close Method Missing from MT5Service

**Location:** Line 2326

**Problem:** Code calls `self.mt5_service.close_position_partial(ticket, close_volume)` but this method may not exist in MT5Service.

**Impact:** `AttributeError: 'MT5Service' object has no attribute 'close_position_partial'`.

**Fix:** Check if method exists, or implement partial close differently:

```python
# Check if MT5Service has partial close method
if hasattr(self.mt5_service, 'close_position_partial'):
    result = self.mt5_service.close_position_partial(ticket, close_volume)
else:
    # Fallback: Use MT5 directly
    import MetaTrader5 as mt5
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": ticket,
        "symbol": trade_state.symbol,
        "volume": close_volume,
        "type": mt5.ORDER_TYPE_SELL if trade_state.direction == "BUY" else mt5.ORDER_TYPE_BUY,
        "price": mt5.symbol_info_tick(trade_state.symbol).bid if trade_state.direction == "BUY" else mt5.symbol_info_tick(trade_state.symbol).ask,
        "deviation": 20,
        "magic": 0,
        "comment": "PartialClose",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    # Convert to expected format
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        result = {"ok": True, "message": "Partial close successful"}
    else:
        result = {"ok": False, "message": result.comment if result else "Unknown error"}
```

---

## 🟢 Minor Issues / Clarifications

### 13. Missing Monitoring Loop Scheduler Integration

**Location:** Line 2031

**Problem:** Plan says "Add to `chatgpt_bot.py` scheduler" but doesn't show how.

**Fix:** Add example:

```python
# In chatgpt_bot.py
from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager

# Initialize
universal_sl_tp_manager = UniversalDynamicSLTPManager(
    db_path="data/universal_trades.db",
    mt5_service=mt5_service
)

# Add to scheduler
scheduler.add_job(
    universal_sl_tp_manager.monitor_all_trades,
    'interval',
    seconds=30,
    id='universal_sl_tp_monitoring',
    replace_existing=True
)
```

---

### 14. Missing _monitor_all_trades Method

**Location:** Referenced in scheduler but not defined

**Problem:** Plan references `monitor_all_trades()` but only `monitor_trade(ticket)` is shown.

**Fix:** Add method:

```python
def monitor_all_trades(self):
    """Monitor all active trades."""
    tickets = list(self.active_trades.keys())
    for ticket in tickets:
        try:
            self.monitor_trade(ticket)
        except Exception as e:
            logger.error(f"Error monitoring trade {ticket}: {e}", exc_info=True)
```

---

### 15. Config File Path Hardcoded

**Location:** Line 2582

**Problem:** Config path is hardcoded as `"config/universal_sl_tp_config.json"` - what if config is in different location?

**Fix:** Make configurable:

```python
def __init__(self, db_path: str = None, mt5_service=None, config_path: str = None):
    self.config_path = config_path or "config/universal_sl_tp_config.json"
    # ...
```

---

### 16. Missing Error Handling for Config Loading

**Location:** Lines 2580-2593

**Problem:** If config file is missing or invalid JSON, system continues with empty config. Should it fail or use defaults?

**Fix:** Add default config fallback:

```python
def _load_config(self) -> Dict:
    """Load configuration from JSON file."""
    try:
        with open(self.config_path, 'r') as f:
            config = json.load(f)
        return config.get("universal_sl_tp_rules", {})
    except FileNotFoundError:
        logger.warning(f"Config file not found: {self.config_path}, using defaults")
        return self._get_default_config()
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}, using defaults")
        return self._get_default_config()
    except Exception as e:
        logger.error(f"Error loading config: {e}", exc_info=True)
        return self._get_default_config()

def _get_default_config(self) -> Dict:
    """Return default configuration."""
    # Return minimal default config
    return {
        "strategies": {
            "default_standard": {
                "breakeven_trigger_r": 1.0,
                "trailing_method": "atr_basic",
                "trailing_timeframe": "M15",
                "atr_multiplier": 2.0,
                "trailing_enabled": True,
                "min_sl_change_r": 0.1,
                "sl_modification_cooldown_seconds": 60
            }
        },
        "symbol_adjustments": {}
    }
```

---

### 17. Missing _get_dtms_state Method

**Location:** Line 1768

**Problem:** `_can_dtms_modify_sl()` calls `self._get_dtms_state(ticket)` but this method is not defined.

**Fix:** Add method:

```python
def _get_dtms_state(self, ticket: int) -> Optional[str]:
    """Get DTMS state for trade."""
    try:
        from dtms_integration import get_dtms_trade_status
        status = get_dtms_trade_status(ticket)
        if status:
            return status.get('state')
    except Exception:
        pass
    return None
```

---

### 18. Incomplete _infer_strategy_type Query

**Location:** Line 2610

**Problem:** Query uses `WHERE ticket = ?` but `trade_plans` table may not have `ticket` column - it has `plan_id`.

**Fix:** Use plan_id from TradeState or query differently:

```python
# Try to get from plan_id first
if hasattr(trade_state, 'plan_id') and trade_state.plan_id:
    try:
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT conditions FROM trade_plans WHERE plan_id = ?",
                (trade_state.plan_id,)
            ).fetchone()
            
            if row:
                conditions = json.loads(row["conditions"])
                strategy_type_str = conditions.get("strategy_type")
                if strategy_type_str:
                    return self._normalize_strategy_type(strategy_type_str)
    except Exception:
        pass
```

---

### 19. Missing Database Commit

**Location:** Lines 1346-1354, 2486-2525

**Problem:** SQLite operations use `conn.execute()` but don't show `conn.commit()`. While context manager auto-commits, it's better to be explicit.

**Fix:** Add explicit commit or document that context manager handles it.

---

### 20. Missing Monitoring Loop Error Recovery

**Location:** Lines 1393-1481

**Problem:** If `monitor_trade()` fails for one trade, it may prevent monitoring of other trades.

**Fix:** Add error handling in `monitor_all_trades()` (see Issue #14).

---

## 📝 Summary

**Critical Issues:** 6
**Medium Issues:** 6
**Minor Issues:** 8

**Total Issues:** 20

**Key Areas Needing Attention:**
1. Registration timing and order with DTMS
2. Missing enum definitions
3. TradeRegistry initialization and sharing
4. Ownership determination logic
5. Position validation
6. Recovery coordination
7. Config validation and defaults
8. Missing method implementations

**Recommendation:** Address critical issues before implementation, especially registration order and ownership logic.

