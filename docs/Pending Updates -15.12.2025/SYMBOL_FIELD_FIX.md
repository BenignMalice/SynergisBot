# Symbol Field Fix for create_multiple_auto_plans

**Date**: December 15, 2025  
**Issue**: ChatGPT used `symbol` (singular) instead of `symbols` (plural) at top level  
**Status**: ✅ **FIXED**

---

## Problem

ChatGPT attempted to create multiple plans using:
```json
{
  "symbol": "XAUUSDc",  // ❌ WRONG - should be "symbols" (plural)
  "plans": [...]
}
```

**Error**: All plans failed with: "symbol is required (provide in plan or in top-level 'symbols' field)"

## Root Cause

The API expects `symbols` (plural) at the top level:
```python
class BatchCreatePlanRequest(BaseModel):
    plans: List[Dict[str, Any]]
    symbols: Optional[str] = None  # ← PLURAL
```

But ChatGPT used `symbol` (singular) at the top level.

## Fix Applied

Updated all instructions in `openai.yaml` and embedding knowledge documents to explicitly state:

⚠️⚠️⚠️ **CRITICAL**: Use 'symbols' (PLURAL) at top level, NOT 'symbol' (singular).

**Correct Format**:
```json
{
  "symbols": "BTCUSDc",  // ✅ CORRECT - plural
  "plans": [
    {
      "plan_type": "auto_trade",
      "direction": "BUY",
      // ... other fields
      // symbol field can be omitted if using top-level symbols
    }
  ]
}
```

**Wrong Format**:
```json
{
  "symbol": "BTCUSDc",  // ❌ WRONG - singular
  "plans": [...]
}
```

## Locations Updated

1. ✅ `openai.yaml` - Batch Operations Section (line ~733)
2. ✅ `openai.yaml` - createMultipleAutoPlans Description (line ~2265, ~2300)
3. ✅ `openai.yaml` - Pattern Matching Rules (line ~565, ~330)
4. ✅ `openai.yaml` - Dual Plan Detection Rule (line ~774)
5. ✅ `6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md`
6. ✅ `7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`

## Testing

After this fix, ChatGPT should correctly use `symbols` (plural) at the top level when creating multiple plans.

---

**Status**: ✅ **FIXED** - All instructions updated with explicit `symbols` (plural) requirement
