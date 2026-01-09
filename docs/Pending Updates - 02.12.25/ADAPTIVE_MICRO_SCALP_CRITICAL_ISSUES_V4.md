# Adaptive Micro-Scalp Strategy Plan - Critical Issues V4 (Root Cause Analysis)

**Date:** 2025-12-03  
**Reviewer:** AI Assistant  
**Status:** 🔴 **CRITICAL SIGNATURE MISMATCH FOUND**

---

## 🔴 **ROOT CAUSE: Why So Many Errors?**

The fundamental issue is a **method signature mismatch** between the plan's assumptions and the actual base class implementation. This creates a cascade of errors:

1. **Base class methods expect individual parameters**, not a snapshot dict
2. **Plan assumes methods accept snapshot**, causing all strategy checkers to fail
3. **Each fix reveals another layer** of the same underlying problem

---

## 🔴 **CRITICAL ERROR #1: Method Signature Mismatch**

### **The Problem:**

**Plan Shows (WRONG):**
```python
# In strategy checker validate() method
location_result = self._check_location_filter(snapshot)  # ❌ WRONG
signal_result = self._check_candle_signals(snapshot)     # ❌ WRONG
```

**Actual Base Class Signature:**
```python
# In infra/micro_scalp_conditions.py
def _check_location_filter(self, symbol: str, candles: List[Dict[str, Any]],
                          current_price: float, vwap: float, atr1: Optional[float]) -> Dict[str, Any]:

def _check_candle_signals(self, symbol: str, candles: List[Dict[str, Any]],
                         current_price: float, vwap: float, atr1: Optional[float],
                         btc_order_flow: Optional[Dict[str, Any]]) -> Dict[str, Any]:
```

**Impact:**
- All strategy checkers will fail at runtime with `TypeError`
- Cannot call base class methods without extracting parameters from snapshot
- Every strategy checker needs to extract parameters before calling

**Fix Required:**
```python
# In each strategy checker's validate() method
# Extract parameters from snapshot FIRST
symbol = snapshot.get('symbol', '')
candles = snapshot.get('candles', [])
current_price = snapshot.get('current_price', 0.0)
vwap = snapshot.get('vwap', 0.0)
atr1 = snapshot.get('atr1')
btc_order_flow = snapshot.get('btc_order_flow')

# THEN call base class methods with correct signature
location_result = self._check_location_filter(
    symbol, candles, current_price, vwap, atr1
)
signal_result = self._check_candle_signals(
    symbol, candles, current_price, vwap, atr1, btc_order_flow
)
```

---

## 🔴 **CRITICAL ERROR #2: Missing `details` Field in ConditionCheckResult**

### **The Problem:**

**Plan Assumes:**
```python
@dataclass
class ConditionCheckResult:
    # ... other fields ...
    details: Dict[str, Any]  # ✅ Plan assumes this exists
```

**Actual Base Class (infra/micro_scalp_conditions.py line 26-35):**
```python
@dataclass
class ConditionCheckResult:
    """Result of condition checking"""
    passed: bool
    pre_trade_passed: bool
    location_passed: bool
    primary_triggers: int
    secondary_confluence: int
    confluence_score: float
    is_aplus_setup: bool
    reasons: List[str]
    # ❌ NO details field!
```

**Impact:**
- All `ConditionCheckResult` creations with `details=details` will fail
- Cannot store `range_structure`, `entry_type`, etc. in result
- Trade idea generation cannot access stored data

**Fix Required:**
**Option 1:** Add `details` field to base class (recommended):
```python
@dataclass
class ConditionCheckResult:
    """Result of condition checking"""
    passed: bool
    pre_trade_passed: bool
    location_passed: bool
    primary_triggers: int
    secondary_confluence: int
    confluence_score: float
    is_aplus_setup: bool
    reasons: List[str]
    details: Dict[str, Any] = field(default_factory=dict)  # ✅ ADD THIS
```

**Option 2:** Store data in snapshot instead of result.details (workaround):
```python
# Store in snapshot instead
snapshot['range_structure'] = range_structure
snapshot['near_edge'] = near_edge

# Access from snapshot in generate_trade_idea()
range_structure = snapshot.get('range_structure')
```

---

## 🔴 **CRITICAL ERROR #3: Strategy Checkers Must Override Base Methods**

### **The Problem:**

Strategy checkers inherit from `MicroScalpConditionsChecker`, which has:
- `_check_location_filter(symbol, candles, current_price, vwap, atr1)` - Generic edge detection
- `_check_candle_signals(symbol, candles, current_price, vwap, atr1, btc_order_flow)` - Generic signals

But strategy checkers need **strategy-specific** location and signal checks:
- VWAP Reversion: Deviation from VWAP, CHOCH at extreme
- Range Scalp: Price at range edge, sweep at edge
- Balanced Zone: Compression block, equal highs/lows

**Impact:**
- Cannot use base class methods (they check for generic "edge", not strategy-specific conditions)
- Each strategy checker must override `_check_location_filter()` and `_check_candle_signals()`
- Plan doesn't show these overrides

**Fix Required:**
Each strategy checker must override these methods:

```python
# In VWAPReversionChecker
def _check_location_filter(self, symbol: str, candles: List[Dict[str, Any]],
                          current_price: float, vwap: float, atr1: Optional[float]) -> Dict[str, Any]:
    """VWAP Reversion-specific location filter"""
    # Check deviation ≥2σ from VWAP
    vwap_std = self._calculate_vwap_std(candles, vwap)
    deviation_sigma = abs(current_price - vwap) / vwap_std if vwap_std > 0 else 0
    
    # Check VWAP slope
    vwap_slope = self._calculate_vwap_slope(candles, vwap)
    vwap_slope_ok = abs(vwap_slope) < 0.0001  # Not strongly trending
    
    # Check volume spike
    volume_spike = self._check_volume_spike(candles)
    
    return {
        'passed': deviation_sigma >= 2.0,
        'deviation_sigma': deviation_sigma,
        'vwap_slope_ok': vwap_slope_ok,
        'volume_spike': volume_spike,
        'reasons': [] if deviation_sigma >= 2.0 else ['Deviation < 2σ']
    }

def _check_candle_signals(self, symbol: str, candles: List[Dict[str, Any]],
                         current_price: float, vwap: float, atr1: Optional[float],
                         btc_order_flow: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """VWAP Reversion-specific candle signals"""
    # Check for CHOCH at deviation extreme
    choch_detected = False
    choch_direction = None
    if self.m1_analyzer:
        analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
        choch_bos = analysis.get('choch_bos', {})
        choch_detected = choch_bos.get('has_choch', False)
        choch_direction = choch_bos.get('direction', '')
    
    # Check volume confirmation
    volume_confirmed = self._check_volume_spike(candles)
    
    primary_count = 1 if choch_detected else 0
    secondary_count = 1 if volume_confirmed else 0
    
    return {
        'primary_count': primary_count,
        'secondary_count': secondary_count,
        'primary_triggers': ['CHOCH_AT_EXTREME'] if choch_detected else [],
        'secondary_confluence': ['VOLUME_CONFIRMED'] if volume_confirmed else []
    }
```

**Similar overrides needed for:**
- `RangeScalpChecker._check_location_filter()` - Check range edge proximity
- `RangeScalpChecker._check_candle_signals()` - Check sweep at edge
- `BalancedZoneChecker._check_location_filter()` - Check compression block
- `BalancedZoneChecker._check_candle_signals()` - Check fade/breakout signals

---

## 🔴 **CRITICAL ERROR #4: Missing `reasons` Field in ConditionCheckResult Returns**

### **The Problem:**

**Plan Shows:**
```python
return ConditionCheckResult(
    passed=True,
    pre_trade_passed=True,
    location_passed=True,
    primary_triggers=signal_result.get('primary_count', 0),
    secondary_confluence=signal_result.get('secondary_count', 0),
    confluence_score=confluence_score,
    is_aplus_setup=confluence_score >= min_score_aplus,
    reasons=reasons,  # ✅ This is correct
    details=details   # ❌ Field doesn't exist
)
```

**Actual Base Class:**
```python
@dataclass
class ConditionCheckResult:
    passed: bool
    pre_trade_passed: bool
    location_passed: bool
    primary_triggers: int
    secondary_confluence: int
    confluence_score: float
    is_aplus_setup: bool
    reasons: List[str]  # ✅ Exists
    # details: Dict[str, Any]  # ❌ Missing
```

**Fix:**
Either add `details` field OR remove it from all return statements.

---

## 📋 **Summary: Why So Many Errors?**

### **Root Causes:**

1. **Signature Mismatch Cascade:**
   - Plan assumes methods accept `snapshot`
   - Base class methods require individual parameters
   - Every strategy checker inherits this mismatch
   - Fixing one reveals the next layer

2. **Missing Field in Dataclass:**
   - Plan assumes `details` field exists
   - Base class doesn't have it
   - All return statements fail
   - Data storage pattern breaks

3. **Incomplete Method Override Documentation:**
   - Plan doesn't show strategy-specific overrides
   - Base class methods are generic
   - Strategy checkers need custom implementations
   - Missing implementation details

4. **Integration Assumptions:**
   - Plan assumes methods work with snapshot
   - Actual code requires parameter extraction
   - Data flow doesn't match assumptions
   - Each integration point needs fixing

### **Systemic Issues:**

1. **Lack of Base Class Review:**
   - Plan created without checking actual base class signatures
   - Assumptions made about method parameters
   - Return types assumed incorrectly

2. **Incremental Fix Approach:**
   - Each fix reveals another layer
   - Not addressing root cause
   - Fixing symptoms, not disease

3. **Missing Integration Testing:**
   - No validation against actual codebase
   - Plan written in isolation
   - Assumptions not verified

---

## ✅ **COMPREHENSIVE FIX REQUIRED**

### **Fix 1: Update Base Class (Recommended)**
```python
# In infra/micro_scalp_conditions.py
@dataclass
class ConditionCheckResult:
    passed: bool
    pre_trade_passed: bool
    location_passed: bool
    primary_triggers: int
    secondary_confluence: int
    confluence_score: float
    is_aplus_setup: bool
    reasons: List[str]
    details: Dict[str, Any] = field(default_factory=dict)  # ✅ ADD
```

### **Fix 2: Update Plan Method Calls**
```python
# In ALL strategy checker validate() methods
# Extract parameters FIRST
symbol = snapshot.get('symbol', '')
candles = snapshot.get('candles', [])
current_price = snapshot.get('current_price', 0.0)
vwap = snapshot.get('vwap', 0.0)
atr1 = snapshot.get('atr1')
btc_order_flow = snapshot.get('btc_order_flow')

# Call with correct signature
location_result = self._check_location_filter(
    symbol, candles, current_price, vwap, atr1
)
signal_result = self._check_candle_signals(
    symbol, candles, current_price, vwap, atr1, btc_order_flow
)
```

### **Fix 3: Document Strategy-Specific Overrides**
- Each strategy checker MUST override `_check_location_filter()`
- Each strategy checker MUST override `_check_candle_signals()`
- Base class methods are generic and won't work for strategy-specific logic

---

**End of Critical Issues V4 - Root Cause Analysis**

