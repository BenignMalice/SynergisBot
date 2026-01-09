# Knowledge Documents Update Requirements - MTF Analysis Fixes

**Date**: December 8, 2025  
**Status**: Required Updates Identified  
**Related**: `MTF_ANALYSIS_IN_ANALYSE_SYMBOL_FULL_IMPLEMENTATION_PLAN.md`

---

## Summary

Based on the fixes applied to the implementation plan, the knowledge documents need updates to reflect:

1. **Correct data structure** (nested fields in `recommendation`)
2. **Correct field access paths** (convenience vs raw paths)
3. **Calculated/derived fields** (`choch_detected`, `bos_detected`, `trend`)
4. **Field availability** (optional fields like `advanced_insights`)

---

## Documents Requiring Updates

### 1. `1.KNOWLEDGE_DOC_EMBEDDING.md`

**Location**: `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/`  
**Section**: Tool execution rules (lines ~271-278)

**Required Updates**:

1. **Add MTF Data Access Section** with correct field paths:
   ```markdown
   - **MTF Data Access**: 
     - `response.data.smc.timeframes` (H4/H1/M30/M15/M5) - Per-timeframe analysis
     - `response.data.smc.alignment_score` - Multi-timeframe alignment (0-100)
     - `response.data.smc.recommendation` - Overall recommendation
     - `response.data.smc.market_bias` - Market bias (convenience path)
     - `response.data.smc.trade_opportunities` - Trade opportunities (convenience path)
     - `response.data.smc.volatility_regime` - Volatility regime (convenience path)
     - `response.data.smc.volatility_weights` - Volatility weights (convenience path)
     - `response.data.smc.advanced_insights` - Advanced insights (may be empty)
     - `response.data.smc.confidence_score` - Recommendation confidence
     - `response.data.smc.choch_detected` - CHOCH detected (calculated)
     - `response.data.smc.bos_detected` - BOS detected (calculated)
     - `response.data.smc.trend` - Primary trend from H4 bias (derived)
   ```

2. **Add Data Structure Note**:
   ```markdown
   - **⚠️ DATA STRUCTURE NOTE**: `market_bias`, `trade_opportunities`, `volatility_regime`, `volatility_weights` are nested inside `recommendation` in the raw data, but are also extracted to top-level `smc` for convenience. You can access them via `response.data.smc.market_bias` (convenience) or `response.data.smc.recommendation.market_bias` (raw structure).
   ```

3. **Update includes list** to mention complete MTF analysis

---

### 2. `7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`

**Location**: `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/`  
**Section**: Add new section "Multi-Timeframe Analysis in analyse_symbol_full"

**Required Updates**:

1. **Add complete MTF structure documentation** with:
   - Top-level fields (directly accessible)
   - Calculated/derived fields explanation
   - Field access paths (convenience vs raw)
   - Optional fields note

2. **Document calculated fields**:
   ```markdown
   **Calculated/Derived Fields**:
   - **choch_detected**: Boolean - CHOCH detected on any timeframe (calculated from timeframes data)
   - **bos_detected**: Boolean - BOS confirmed on any timeframe (calculated from timeframes data)
   - **trend**: String - Primary trend direction (extracted from H4 bias: "BULLISH", "BEARISH", "NEUTRAL", "UNKNOWN")
   ```

3. **Document nested structure**:
   ```markdown
   **Nested Fields in Recommendation**:
   - `market_bias`, `trade_opportunities`, `volatility_regime`, `volatility_weights` are nested inside `recommendation`
   - Accessible via convenience paths: `response.data.smc.market_bias`
   - Or via raw paths: `response.data.smc.recommendation.market_bias`
   ```

---

### 3. `6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md`

**Location**: `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/`  
**Section**: Tool selection guidance

**Required Updates**:

1. **Update tool selection rule** to mention MTF data is included:
   ```markdown
   **For General Analysis Requests** (e.g., "Analyse XAUUSD"):
   - ✅ **USE**: `moneybot.analyse_symbol_full`
   - ✅ **Includes**: Complete MTF analysis (timeframes, alignment_score, recommendation with nested fields, market_bias, trade_opportunities, volatility_regime, volatility_weights, advanced_insights), macro context, volatility regime, SMC structure, advanced features, M1 microstructure
   - ❌ **DO NOT**: Call `getMultiTimeframeAnalysis` separately - it's already included
   ```

2. **Add note about data structure**:
   ```markdown
   **⚠️ IMPORTANT**: When accessing MTF data from `analyse_symbol_full`:
   - Most fields are at top-level `response.data.smc.*` for convenience
   - `market_bias`, `trade_opportunities`, `volatility_regime`, `volatility_weights` are also nested in `response.data.smc.recommendation.*`
   - `choch_detected`, `bos_detected`, `trend` are calculated/derived fields, not direct from MTF analyzer
   ```

---

## Key Points to Document

### 1. Field Access Paths

**Convenience Paths** (extracted to top-level):
- `response.data.smc.market_bias`
- `response.data.smc.trade_opportunities`
- `response.data.smc.volatility_regime`
- `response.data.smc.volatility_weights`

**Raw Paths** (original nested location):
- `response.data.smc.recommendation.market_bias`
- `response.data.smc.recommendation.trade_opportunities`
- `response.data.smc.recommendation.volatility_regime`
- `response.data.smc.recommendation.volatility_weights`

**Both paths work** - convenience paths are provided for easier access, but raw paths are also valid.

---

### 2. Calculated/Derived Fields

These fields are **not** in the MTF analyzer return - they are calculated/derived:

- **`choch_detected`**: Calculated by checking all timeframes for CHOCH indicators (`choch_detected`, `choch_bull`, `choch_bear`)
- **`bos_detected`**: Calculated by checking all timeframes for BOS indicators (`bos_detected`, `bos_bull`, `bos_bear`)
- **`trend`**: Extracted from `H4.bias` (the primary trend indicator)

---

### 3. Optional Fields

These fields may be empty if advanced features are unavailable:

- **`advanced_insights`**: Only present if `advanced_features` is available
- **`advanced_summary`**: Only present if `advanced_features` is available

**Always check** if these fields exist before accessing nested properties.

---

### 4. Confidence Score

**`confidence_score`** uses `recommendation.confidence`, not a separate field.

Access: `response.data.smc.confidence_score` (convenience) or `response.data.smc.recommendation.confidence` (raw)

---

## Testing Checklist

After updating knowledge documents:

- [ ] Verify field access paths are correctly documented
- [ ] Verify calculated fields are marked as derived/calculated
- [ ] Verify nested structure is explained
- [ ] Verify optional fields are noted
- [ ] Verify no conflicting information
- [ ] Test ChatGPT can access fields via both convenience and raw paths
- [ ] Test ChatGPT understands calculated fields are derived
- [ ] Test ChatGPT handles optional fields gracefully

---

## Priority

**HIGH** - These updates are critical for ChatGPT to correctly understand and use the MTF data structure. Without these updates, ChatGPT may:

- Try to access fields that don't exist at the documented paths
- Not understand that some fields are calculated/derived
- Not know about the nested structure in `recommendation`
- Miss optional fields or try to access them when unavailable

---

## Related Documents

- `MTF_ANALYSIS_IN_ANALYSE_SYMBOL_FULL_IMPLEMENTATION_PLAN.md` - Implementation plan
- `PLAN_REVIEW_ISSUES_MTF_ANALYSIS.md` - Review issues that led to these fixes

