# Trailing Enabled - Default Behavior

**Date:** 2025-11-30

---

## ✅ **Answer: Yes, `trailing_enabled = True` is the DEFAULT**

**But:** One strategy explicitly disables it.

---

## 📊 **How `trailing_enabled` is Determined**

### **1. Default Behavior**

**Location:** `infra/universal_sl_tp_manager.py` (lines 588-590)

```python
# Set default trailing_enabled if not specified
if "trailing_enabled" not in resolved:
    resolved["trailing_enabled"] = True
```

**Result:** If `trailing_enabled` is **not specified** in the config, it defaults to **`True`**.

---

### **2. Strategy-Specific Configuration**

**Location:** `config/universal_sl_tp_config.json`

**Strategies with `trailing_enabled` explicitly set:**

#### ✅ **Trailing Enabled (True):**
- `default_standard`: `"trailing_enabled": true` (line 57)
- All other strategies: **Default to `True`** (not explicitly set, so default applies)

#### ❌ **Trailing Disabled (False):**
- `mean_reversion_range_scalp`: `"trailing_enabled": false` (line 48)

**Why Mean Reversion Disables Trailing:**
- Mean reversion trades are designed to hit TP quickly
- Trailing stops can interfere with mean reversion logic
- Strategy uses `"trailing_method": "minimal_be_only"` (only breakeven protection)

---

### **3. Runtime Check**

**Location:** `infra/universal_sl_tp_manager.py` (line 1922)

```python
if trade_state.breakeven_triggered and rules.get("trailing_enabled", True):
    # Calculate trailing SL
    new_sl = self._calculate_trailing_sl(trade_state, rules)
```

**Behavior:**
- Uses `rules.get("trailing_enabled", True)` 
- If `trailing_enabled` not in rules → defaults to `True`
- Only calculates trailing SL if both conditions met:
  1. `breakeven_triggered = True`
  2. `trailing_enabled = True` (or default True)

---

## 📋 **Summary by Strategy**

| Strategy | `trailing_enabled` | Trailing Method | Notes |
|----------|-------------------|-----------------|-------|
| `breakout_ib_volatility_trap` | ✅ **True** (default) | `structure_atr_hybrid` | Trailing enabled |
| `trend_continuation_pullback` | ✅ **True** (default) | `structure_based` | Trailing enabled |
| `liquidity_sweep_reversal` | ✅ **True** (default) | `micro_choch` | Trailing enabled |
| `order_block_rejection` | ✅ **True** (default) | `displacement_or_structure` | Trailing enabled |
| `mean_reversion_range_scalp` | ❌ **False** (explicit) | `minimal_be_only` | **Trailing disabled** - only breakeven |
| `default_standard` | ✅ **True** (explicit) | `atr_basic` | Trailing enabled |

---

## 🔍 **What This Means**

### **For Most Trades:**
- ✅ `trailing_enabled = True` by default
- ✅ Trailing stops will activate after breakeven
- ✅ Uses strategy-specific trailing method

### **For Mean Reversion Trades:**
- ❌ `trailing_enabled = False` (explicitly set)
- ✅ Breakeven protection still works
- ❌ No trailing stops (only breakeven)

### **For Trades Without Strategy Type:**
- ✅ Uses `DEFAULT_STANDARD` strategy
- ✅ `trailing_enabled = True` (explicitly set in config)
- ✅ Trailing stops will activate after breakeven

---

## 💡 **Key Takeaway**

**Yes, `trailing_enabled = True` is automatically set for all trades EXCEPT:**
- `mean_reversion_range_scalp` strategy (explicitly disabled)

**Default behavior:**
- If not specified → defaults to `True`
- Runtime check also defaults to `True` if missing

**Result:** 5 out of 6 strategies have trailing enabled, with only mean reversion explicitly disabling it.

---

**Files:**
- `infra/universal_sl_tp_manager.py` (line 588-590) - Default setting
- `config/universal_sl_tp_config.json` - Strategy configurations
- `infra/universal_sl_tp_manager.py` (line 1922) - Runtime check

