# Confluence Condition Format Clarification

**Date**: December 15, 2025  
**Status**: ✅ **CLARIFIED**

---

## Question

Must ChatGPT set confluence condition as `moneybot.create_auto_trade_plan` with `"min_confluence": 80` or as `confluence: >80`?

---

## Answer

✅ **CORRECT FORMAT**: `"min_confluence": 80` (numeric value in conditions dictionary)

❌ **WRONG FORMAT**: `"confluence": ">80"` or `"confluence": >80` or `"min_confluence": ">80"`

---

## Correct Usage

### When using `moneybot.create_auto_trade_plan`:

```json
{
  "tool": "moneybot.create_auto_trade_plan",
  "arguments": {
    "symbol": "BTCUSDc",
    "direction": "BUY",
    "entry": 105000.0,
    "stop_loss": 104500.0,
    "take_profit": 106000.0,
    "volume": 0.01,
    "conditions": {
      "min_confluence": 80,  // ✅ CORRECT: Numeric value (0-100)
      "price_near": 105000.0,
      "tolerance": 100.0
    }
  }
}
```

### When using `moneybot.create_range_scalp_plan`:

```json
{
  "tool": "moneybot.create_range_scalp_plan",
  "arguments": {
    "symbol": "BTCUSDc",
    "direction": "BUY",
    "entry": 105000.0,
    "stop_loss": 104500.0,
    "take_profit": 106000.0,
    "volume": 0.01,
    "min_confluence": 80  // ✅ CORRECT: Numeric value (0-100) as top-level parameter
  }
}
```

---

## System Implementation

The auto-execution system checks for confluence using:

```python
# In auto_execution_system.py
min_confluence_threshold = plan.conditions.get("min_confluence")
# Expects: integer/float value (0-100)
# Does NOT parse strings like ">80" or "confluence: >80"
```

**Key Points**:
1. System expects numeric value (0-100)
2. System automatically checks if `confluence_score >= min_confluence_threshold`
3. No need to include ">" in the value - the system handles the comparison
4. String formats like `">80"` or `"confluence: >80"` are **INVALID** and will cause errors

---

## Examples

### ✅ CORRECT Examples:

```json
// Example 1: General auto-trade plan
{
  "conditions": {
    "min_confluence": 75,  // ✅ Numeric value
    "price_near": 105000.0,
    "tolerance": 100.0
  }
}

// Example 2: Range scalp plan
{
  "conditions": {
    "range_scalp_confluence": 80,  // ✅ Numeric value
    "price_near": 105000.0,
    "tolerance": 100.0
  }
}

// Example 3: Hybrid mode (confluence + other conditions)
{
  "conditions": {
    "min_confluence": 70,  // ✅ Numeric value
    "price_near": 105000.0,
    "tolerance": 100.0,
    "bb_expansion": true,
    "structure_confirmation": true
  }
}
```

### ❌ WRONG Examples:

```json
// Example 1: String with comparison operator
{
  "conditions": {
    "confluence": ">80",  // ❌ WRONG: String format, wrong key name
    "price_near": 105000.0
  }
}

// Example 2: Wrong key name
{
  "conditions": {
    "confluence": 80,  // ❌ WRONG: Should be "min_confluence"
    "price_near": 105000.0
  }
}

// Example 3: String value
{
  "conditions": {
    "min_confluence": ">80",  // ❌ WRONG: Should be numeric 80
    "price_near": 105000.0
  }
}
```

---

## Updated Instructions

The following instructions have been updated in `openai.yaml`:

1. **Line ~531**: Added format clarification with ✅ CORRECT and ❌ WRONG examples
2. **Line ~2140**: Added format clarification in `createAutoTradePlan` description

**Key Instruction**:
```
⚠️ **FORMAT**: Use numeric value in conditions dict: `conditions: {"min_confluence": 80}` ✅ CORRECT
❌ **WRONG**: `conditions: {"confluence": ">80"}` or `conditions: {"confluence": >80}` - These are INVALID formats
```

---

## Summary

- ✅ **Use**: `"min_confluence": 80` (numeric value, 0-100) in conditions dictionary
- ❌ **Don't Use**: `"confluence": ">80"` or `"confluence": >80` or `"min_confluence": ">80"`
- ✅ **System handles**: The comparison (`>=`) is done automatically by the system
- ✅ **Format**: Always use numeric value, never strings with comparison operators

---

**Status**: ✅ **CLARIFIED** - Instructions updated to explicitly show correct vs wrong formats
