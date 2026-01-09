# Symbol Field Mandatory Update

**Date**: December 15, 2025  
**Issue**: ChatGPT was omitting `symbol` field from individual plan objects  
**Status**: ✅ **FIXED**

---

## Problem

ChatGPT was creating batch plans with `symbols` (plural) at the top level but omitting `symbol` from individual plan objects. The API was rejecting all plans with: "symbol is required (provide in plan or in top-level 'symbols' field)".

**Example of what ChatGPT was doing (WRONG)**:
```json
{
  "symbols": "EURUSDc",  // ✅ Top level correct
  "plans": [
    {
      "plan_type": "auto_trade",
      "direction": "BUY",
      // ❌ Missing "symbol" field
      ...
    }
  ]
}
```

## Root Cause

The instructions previously stated: "If using top-level 'symbols', you can omit 'symbol' from individual plans". However, the API validation requires the `symbol` field in each plan object for reliability, even though it has fallback logic.

## Solution

Updated all instructions to make `symbol` field **MANDATORY** in every plan object, regardless of whether `symbols` exists at the top level.

**Correct Format (REQUIRED)**:
```json
{
  "symbols": "EURUSDc",  // Optional, for convenience
  "plans": [
    {
      "plan_type": "auto_trade",
      "symbol": "EURUSDc",  // ✅ MANDATORY - must be in every plan
      "direction": "BUY",
      ...
    },
    {
      "plan_type": "choch",
      "symbol": "EURUSDc",  // ✅ MANDATORY - must be in every plan
      "direction": "SELL",
      ...
    }
  ]
}
```

## Changes Applied

### 1. openai.yaml - createMultipleAutoPlans Description
- ✅ Changed from: "If using top-level 'symbols', you can omit 'symbol' from individual plans"
- ✅ Changed to: "🚨 MANDATORY: Each plan object MUST include 'symbol' field"
- ✅ Added clear examples showing correct vs wrong format
- ✅ Added multiple ⚠️⚠️⚠️ warnings

### 2. openai.yaml - Batch Operations Section (STEP 3)
- ✅ Added: "🚨 MANDATORY: Each plan object MUST include 'symbol' field"
- ✅ Added: "❌ WRONG: Omitting 'symbol' from individual plans"
- ✅ Added: "✅ CORRECT: Every plan must have: { plan_type: 'auto_trade', symbol: 'BTCUSDc', ... }"

### 3. openai.yaml - Dual Plan Detection Rule
- ✅ Updated continuation plan validation to explicitly check for `symbol` field
- ✅ Added warning in batch creation instructions

### 4. openai.yaml - Pattern Matching Rules
- ✅ Updated both "Plan Portfolio Creation Pattern" and "Single Plan with Dual Strategy Pattern"
- ✅ Added mandatory symbol requirement to both patterns

### 5. openai.yaml - Example Code
- ✅ Example already shows `symbol` in each plan (lines 2383, 2394, 2404)
- ✅ Added comment clarifying the requirement

### 6. Knowledge Documents
- ✅ Updated `6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md`
- ✅ Updated `7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`
- ✅ Changed from: "symbol (or use top-level 'symbols' field)"
- ✅ Changed to: "symbol (🚨 MANDATORY - MUST be included in every plan object)"

## Key Instructions Now in Place

1. **🚨 MANDATORY**: Each plan object MUST include 'symbol' field (e.g., symbol: 'BTCUSDc')
2. **❌ WRONG**: Omitting 'symbol' from individual plans
3. **✅ CORRECT**: Every plan must have: { plan_type: 'auto_trade', symbol: 'BTCUSDc', direction: 'BUY', ... }
4. Top-level 'symbols' field is optional and can be used for convenience, but it does NOT replace the requirement for 'symbol' in each plan

## Testing

After this update, ChatGPT should:
- ✅ Always include `symbol` field in every plan object
- ✅ Never omit `symbol` from individual plans
- ✅ Create valid batch requests that pass API validation

---

**Status**: ✅ **FIXED** - All instructions updated to make `symbol` field mandatory in each plan object
