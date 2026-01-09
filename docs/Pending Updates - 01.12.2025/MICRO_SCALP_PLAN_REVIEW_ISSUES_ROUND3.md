# Micro-Scalp Automation Plan Review - Round 3 Issues

**Date:** 2025-12-01  
**Reviewer:** AI Assistant  
**Status:** Additional issues found

---

## 🔴 **Critical Issues**

### **1. Missing `load_config()` Function**

**Location:** Phase 3.1, `MicroScalpExecutionManager` initialization

**Problem:**
- Code uses `load_config("config/micro_scalp_config.json")` but this function doesn't exist
- Should use `json.load()` directly or check if there's a helper function

**Fix:**
```python
# Option 1: Use json.load() directly
import json
with open("config/micro_scalp_config.json", 'r') as f:
    config = json.load(f)

micro_scalp_execution_manager = MicroScalpExecutionManager(
    config=config,  # ✅ Use loaded config
    mt5_service=mt5_service,
    spread_tracker=spread_tracker,
    m1_fetcher=m1_data_fetcher
)

# Option 2: If load_config() exists elsewhere, import it
# from config.config_loader import load_config
```

---

### **2. News Service API Mismatch**

**Location:** Phase 1.1, `_is_news_blackout()` method

**Problem:**
- Plan uses `news_service.get_news_status()` but `NewsService` uses `is_blackout()` method
- Return structure is different

**Fix:**
```python
def _is_news_blackout(self, symbol: str) -> bool:
    """Check if symbol is in news blackout period"""
    if not self.news_service:
        return False
    
    try:
        # Fixed: Use is_blackout() method instead of get_news_status()
        # Check for macro blackout (affects all symbols)
        macro_blackout = self.news_service.is_blackout(category="macro")
        
        # Check for crypto blackout (affects BTCUSDc)
        crypto_blackout = False
        if symbol.upper().startswith('BTC'):
            crypto_blackout = self.news_service.is_blackout(category="crypto")
        
        return macro_blackout or crypto_blackout
    except Exception as e:
        logger.debug(f"News check failed: {e}")
        return False
```

---

## 🟡 **Medium Issues**

### **3. Config Reload Timing Inefficiency**

**Location:** Phase 5.1, `_monitor_loop()` method

**Problem:**
- Config reload is called on every loop iteration (every 5 seconds)
- Should only check every 60 seconds (config_reload_interval)

**Fix:**
```python
def _monitor_loop(self):
    """Main monitoring loop with config reload"""
    last_config_check = time.time()  # Fixed: track last check time
    
    while self.monitoring:
        loop_start = time.time()
        
        # Check for config changes (every 60 seconds, not every loop)
        current_time = time.time()
        if current_time - last_config_check >= self.config_reload_interval:
            self._reload_config_if_changed()
            last_config_check = current_time
        
        # ... existing monitoring code ...
        
        # Sleep until next cycle
        elapsed = time.time() - loop_start
        sleep_time = max(0, self.check_interval - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)
```

---

### **4. Session Manager API Mismatch**

**Location:** Phase 5.5, `_should_monitor_symbol()` method

**Problem:**
- Plan uses `session_manager.get_current_session()` which returns a dict
- But the exact structure may vary - need to handle different return types

**Fix:**
```python
def _should_monitor_symbol(self, symbol: str) -> bool:
    """Check if symbol should be monitored based on session"""
    if not self.session_adaptive or not self.session_manager:
        return True
    
    try:
        # Fixed: Handle different session manager types
        if hasattr(self.session_manager, 'get_current_session'):
            current_session = self.session_manager.get_current_session()
        elif hasattr(self.session_manager, 'get_session_info'):
            session_info = self.session_manager.get_session_info()
            current_session = {'name': session_info.primary_session if hasattr(session_info, 'primary_session') else session_info.get('primary_session', '')}
        else:
            # Fallback: use SessionHelpers
            from infra.session_helpers import SessionHelpers
            session_name = SessionHelpers.get_current_session()
            current_session = {'name': session_name}
        
        session_name = current_session.get('name', '').lower() if isinstance(current_session, dict) else str(current_session).lower()
        
        # Check if session is disabled
        if any(disabled in session_name for disabled in self.disabled_sessions):
            return False
        
        # Check if session is preferred
        if self.preferred_sessions:
            if not any(preferred in session_name for preferred in self.preferred_sessions):
                return False
        
        return True
    except Exception as e:
        logger.debug(f"Session check failed: {e}")
        return True  # Default to monitoring if check fails
```

---

### **5. Missing Error Handling for `_get_m1_candles()` in Monitor Loop**

**Location:** Phase 1.1, `_monitor_loop()` method

**Problem:**
- If `_get_m1_candles()` returns None, loop continues
- But if it raises an exception, it's caught by outer try/except
- Should handle None case explicitly

**Status:** Already handled correctly (checks `if not m1_candles: continue`)

---

### **6. Missing Initialization of `config_last_modified`**

**Location:** Phase 1.1, `__init__` method

**Problem:**
- `config_last_modified` is initialized in Phase 5.1 but not in Phase 1.1
- Should be initialized in main `__init__` for consistency

**Fix:**
Already fixed in Round 2 - `config_last_modified` is initialized in `__init__`

---

## 🟢 **Minor Issues**

### **7. Performance Metrics Initialization**

**Location:** Phase 5.4, `__init__` method

**Problem:**
- `performance_metrics` dict is initialized in Phase 5.4 but not in Phase 1.1
- Should be initialized in main `__init__` if Phase 5.4 is optional

**Fix:**
```python
def __init__(self, ...):
    # ... existing init ...
    
    # Performance metrics (initialized even if Phase 5.4 not implemented)
    self.performance_metrics = {
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'total_r_multiple': 0.0,
        'avg_r_multiple': 0.0,
        'avg_execution_latency_ms': 0.0,
        'avg_hold_time_seconds': 0.0,
        'largest_win_r': 0.0,
        'largest_loss_r': 0.0,
        'current_streak': 0,
        'best_streak': 0,
        'worst_streak': 0
    }
    
    self.open_positions: Dict[int, Dict] = {}  # For performance tracking
```

---

### **8. Missing Type Hints for Optional Parameters**

**Location:** Throughout plan

**Problem:**
- Some optional parameters lack type hints

**Status:** Minor - doesn't affect functionality

---

### **9. Inconsistent Error Messages**

**Location:** Throughout plan

**Problem:**
- Some error messages use different formats
- Should be consistent

**Status:** Minor - doesn't affect functionality

---

## ✅ **Summary**

**Critical Issues:** 2  
**Medium Issues:** 4  
**Minor Issues:** 3  

**Total Issues:** 9

**Priority Fixes:**
1. Fix `load_config()` usage (use `json.load()` directly)
2. Fix news service API (`is_blackout()` instead of `get_news_status()`)
3. Fix config reload timing (check every 60s, not every loop)
4. Fix session manager API handling (handle different return types)

---

**Status:** Ready for fixes  
**Next Step:** Apply fixes to plan

