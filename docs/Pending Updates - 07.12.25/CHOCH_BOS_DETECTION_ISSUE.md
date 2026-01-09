# CHOCH/BOS Detection Logic Issue

**Date**: December 8, 2025  
**Status**: ❌ **CRITICAL ISSUE FOUND**

---

## Problem

The plan's CHOCH/BOS detection logic is **INCORRECT**. `DetectionSystemManager.get_choch_bos()` is **broken** and will always return `False` for all CHOCH/BOS fields.

---

## Root Cause

**`DetectionSystemManager.get_choch_bos()` (lines 336-366 in `infra/detection_systems.py`)**:
```python
def get_choch_bos(self, symbol: str, timeframe: str = "M15") -> Optional[Dict]:
    # ...
    structure = label_structure(bars, lookback=10)  # ❌ WRONG FUNCTION
    
    result = {
        "choch_bull": structure.get("choch_bull", False),  # ❌ This field doesn't exist!
        "choch_bear": structure.get("choch_bear", False),  # ❌ This field doesn't exist!
        "bos_bull": structure.get("bos_bull", False),      # ❌ This field doesn't exist!
        "bos_bear": structure.get("bos_bear", False),      # ❌ This field doesn't exist!
        # ...
    }
```

**`label_structure()` (lines 318-418 in `domain/market_structure.py`)**:
```python
def label_structure(...) -> Dict[str, object]:
    # ...
    return {"trend": trend, "break": brk, "micro_bias": micro}  # ❌ NO CHOCH/BOS FIELDS!
```

**Result**: `DetectionSystemManager.get_choch_bos()` will **always return `False`** for all CHOCH/BOS fields because `label_structure()` doesn't provide them.

---

## Correct Solution

**Use `detect_bos_choch()` instead** (lines 421-516 in `domain/market_structure.py`):

```python
def detect_bos_choch(
    swings: List[Dict[str, Any]],
    current_close: float,
    atr: float,
    bos_threshold: float = 0.2,
    sustained_bars: int = 1
) -> Dict[str, Any]:
    """
    Returns:
        {
            "bos_bull": bool,      # ✅ CORRECT
            "bos_bear": bool,      # ✅ CORRECT
            "choch_bull": bool,    # ✅ CORRECT
            "choch_bear": bool,    # ✅ CORRECT
            "bars_since_bos": int,
            "break_level": float
        }
    """
```

---

## Required Fix

**Option 1: Fix `DetectionSystemManager.get_choch_bos()` (Recommended)**
- Update `DetectionSystemManager.get_choch_bos()` to use `detect_bos_choch()` instead of `label_structure()`
- This fixes the broken method for all consumers

**Option 2: Use `detect_bos_choch()` directly in MTF analyzer**
- Skip `DetectionSystemManager.get_choch_bos()` entirely
- Call `detect_bos_choch()` directly in each timeframe analysis method
- Requires getting swings, current_close, and ATR for each timeframe

---

## Recommended Approach

**Fix `DetectionSystemManager.get_choch_bos()` first**, then use it in the MTF analyzer:

1. **Fix `DetectionSystemManager.get_choch_bos()`**:
   - Replace `label_structure()` call with `detect_bos_choch()`
   - Get swings from bars data
   - Calculate ATR
   - Call `detect_bos_choch(swings, current_close, atr)`

2. **Then use it in MTF analyzer** (as planned in Phase 0)

---

## Impact

- ❌ **CRITICAL**: Current plan will NOT work - CHOCH/BOS will always be `False`
- ❌ Must fix `DetectionSystemManager.get_choch_bos()` OR use `detect_bos_choch()` directly
- ⚠️ Plan needs to be updated before implementation

