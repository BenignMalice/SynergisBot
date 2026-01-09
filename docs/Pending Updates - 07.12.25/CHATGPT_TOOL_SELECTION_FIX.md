# ChatGPT Tool Selection Fix - December 8, 2025

## Issue Identified

ChatGPT was calling multiple tools separately instead of using `analyse_symbol_full`:

**Observed Behavior:**
1. ❌ Called `getCurrentPrice` separately
2. ❌ Called `getCurrentSession` separately  
3. ❌ Called `getNewsStatus` separately
4. ❌ Called `getMultiTimeframeAnalysis` separately
5. ❌ **Did NOT call `analyse_symbol_full` at all**

**Expected Behavior:**
1. ✅ Call `analyse_symbol_full` once
2. ✅ All data (price, session, news, MTF analysis) included in response
3. ✅ No separate tool calls needed

## Root Cause

Conflicting instructions in knowledge documents:

1. **"Fresh Price Rule"** in `1.KNOWLEDGE_DOC_EMBEDDING.md` said "Always call `moneybot.getCurrentPrice` before any analysis"
2. **"Approved Sequence"** listed separate calls for price, session, news before analysis
3. These rules didn't clarify that `analyse_symbol_full` already includes all this data

## Fixes Applied

### 1. Updated `1.KNOWLEDGE_DOC_EMBEDDING.md`

**Changed "Fresh Price Rule"** (lines 359-369):
- ✅ Added clarification that `analyse_symbol_full` includes current price
- ✅ Specified when to call `getCurrentPrice` separately (only if you need JUST price)
- ✅ Added explicit "DO NOT call separately" guidance

**Changed "Approved Sequence"** (lines 377-384):
- ✅ Added "For General Analysis (RECOMMENDED)" section
- ✅ Made `analyse_symbol_full` the primary tool
- ✅ Added explicit "DO NOT call separately" warnings
- ✅ Moved separate tool calls to "For Specific Data Only" section

### 2. Updated `openai.yaml`

**Enhanced `analyseSymbolFull` description** (line 1509):
- ✅ Added "🚨 MANDATORY TOOL" prefix
- ✅ Added "⚠️ CRITICAL: DO NOT call getCurrentPrice, getCurrentSession, getNewsStatus, or getMultiTimeframeAnalysis separately"
- ✅ Listed all included data upfront

### 3. Updated `7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`

**Updated PRICE_REQUIREMENT** (lines 36-43):
- ✅ Added clarification that `analyse_symbol_full` includes price
- ✅ Specified when to use `getCurrentPrice` separately

### 4. Updated `6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md`

**Updated "Fresh Price Requirement"** (lines 29-34):
- ✅ Added clarification that `analyse_symbol_full` includes price
- ✅ Specified when to call `getCurrentPrice` separately

## Expected Behavior After Fix

When user asks "Analyze BTCUSD":

**✅ CORRECT:**
```
Tool call: moneybot.analyse_symbol_full(symbol: "BTCUSD")
Result: Includes price, session, news, MTF analysis, volatility, SMC, order flow, etc.
```

**❌ WRONG (Old Behavior):**
```
Tool call: moneybot.getCurrentPrice(symbol: "BTCUSD")
Tool call: moneybot.getCurrentSession()
Tool call: moneybot.getNewsStatus(category: "crypto")
Tool call: moneybot.getMultiTimeframeAnalysis(symbol: "BTCUSD")
```

## Files Updated

1. ✅ `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/1.KNOWLEDGE_DOC_EMBEDDING.md`
2. ✅ `openai.yaml`
3. ✅ `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`
4. ✅ `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md`

## Next Steps

1. **Re-upload knowledge documents** to ChatGPT
2. **Re-upload openai.yaml** to ChatGPT
3. **Test** with a new analysis request
4. **Verify** ChatGPT calls `analyse_symbol_full` instead of separate tools

## Verification Checklist

After re-uploading, test with: "Analyze BTCUSD"

- [ ] ChatGPT calls `analyse_symbol_full` (not separate tools)
- [ ] ChatGPT does NOT call `getCurrentPrice` separately
- [ ] ChatGPT does NOT call `getCurrentSession` separately
- [ ] ChatGPT does NOT call `getNewsStatus` separately
- [ ] ChatGPT does NOT call `getMultiTimeframeAnalysis` separately
- [ ] Response includes all MTF data from `analyse_symbol_full`

---

**Status**: ✅ **FIXES APPLIED** - Ready for re-upload and testing

