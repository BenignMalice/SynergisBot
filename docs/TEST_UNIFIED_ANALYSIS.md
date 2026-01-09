# Unified Analysis Tool - Test Scenarios

## Overview

Test the `moneybot.analyse_symbol_full` tool with various market conditions to verify:
- All 4 layers are properly fetched and merged
- Priority logic works correctly
- Layered recommendations are appropriate
- Response time is under 5 seconds
- Confluence verdict is accurate

---

## Test Scenario 1: Bullish Confluence (Strong Buy)

**Setup:**
- Macro: Risk-on (VIX <15, S&P rising, DXY falling)
- SMC: BOS Bull confirmed on M15
- Advanced: RMAG -2.5 ATR (oversold)
- Technical: Decision engine says BUY

**Expected Result:**
```
🎯 CONFLUENCE VERDICT
🟢 STRONG BUY - Full Bullish Confluence
High-confidence long entry
Risk Level: LOW - All layers aligned bullish

📈 LAYERED RECOMMENDATIONS

SCALP (M5 entry, 2-4hr hold):
✅ BUY at [entry price]
SL: [below entry]
TP1: [target 1]
TP2: [target 2]
R:R: >2.0 | Confidence: >70%
Setup: M5 bullish + FVG support
Risk: With-trend scalp, standard risk

INTRADAY (M15 entry, 12-24hr hold):
✅ BUY SETUP AVAILABLE
Entry: M15 BOS Bull confirmed
Wait for: Pullback to M15 support/OB
Hold: 12-24 hours for intraday swing
```

**Validation:**
- [ ] Macro bias = BULLISH
- [ ] SMC trend = BULLISH
- [ ] Advanced features = oversold/stretched
- [ ] Confluence verdict = STRONG BUY
- [ ] Scalp recommendation = BUY
- [ ] Intraday recommendation = BUY SETUP
- [ ] Swing recommendation = NOT RECOMMENDED (user preference)
- [ ] Response time < 5 seconds

---

## Test Scenario 2: Bearish Confluence (Strong Sell)

**Setup:**
- Macro: Risk-off (VIX >20, S&P falling, DXY rising for Gold)
- SMC: BOS Bear confirmed on M15
- Advanced: RMAG +2.5 ATR (overbought)
- Technical: Decision engine says SELL

**Expected Result:**
```
🎯 CONFLUENCE VERDICT
🔴 STRONG SELL - Full Bearish Confluence
High-confidence short entry
Risk Level: LOW - All layers aligned bearish

📈 LAYERED RECOMMENDATIONS

SCALP (M5 entry, 2-4hr hold):
✅ SELL at [entry price]
SL: [above entry]
TP1: [target 1]
TP2: [target 2]
R:R: >2.0 | Confidence: >70%
Setup: M5 bearish + FVG resistance
Risk: With-trend scalp, standard risk

INTRADAY (M15 entry, 12-24hr hold):
✅ SELL SETUP AVAILABLE
Entry: M15 BOS Bear confirmed
Wait for: Bounce to M15 resistance/OB
Hold: 12-24 hours for intraday swing
```

**Validation:**
- [ ] Macro bias = BEARISH
- [ ] SMC trend = BEARISH
- [ ] Advanced features = overbought/stretched
- [ ] Confluence verdict = STRONG SELL
- [ ] Scalp recommendation = SELL
- [ ] Intraday recommendation = SELL SETUP
- [ ] Swing recommendation = NOT RECOMMENDED
- [ ] Response time < 5 seconds

---

## Test Scenario 3: Mixed Signals (Scalp Opportunity Only)

**Setup:**
- Macro: NEUTRAL (VIX 17, mixed signals)
- SMC: Bearish trend (H1 downtrend)
- Advanced: RMAG -3.0 ATR (extreme oversold), RSI 25
- Technical: Decision engine says HOLD or weak BUY

**Expected Result:**
```
🎯 CONFLUENCE VERDICT
🟡 SCALP BUY - Oversold Bounce
Counter-trend scalp long (tight SL required)
Risk Level: MEDIUM - Counter-trend, macro neutral allows bounce

📈 LAYERED RECOMMENDATIONS

SCALP (M5 entry, 2-4hr hold):
🟡 BUY at [entry price]
SL: [tight, below entry]
TP1: [conservative target]
TP2: [resistance level]
R:R: 2.0-3.0 | Confidence: 60-70%
Setup: M5 oversold bounce + macro neutral
Risk: Counter-trend scalp, TIGHT SL required

INTRADAY (M15 entry, 12-24hr hold):
⚪ WAIT - No M15 BOS confirmation yet
Current setup: Still bearish, no reversal confirmation

SWING (H1 entry, multi-day hold):
🔴 AVOID - H1 downtrend intact, macro not supportive enough
Wait for: H1 BOS Bull + macro risk-on
```

**Validation:**
- [ ] Macro bias = NEUTRAL
- [ ] SMC trend = BEARISH (but oversold)
- [ ] Advanced features = extreme oversold
- [ ] Confluence verdict = SCALP BUY (counter-trend)
- [ ] Scalp recommendation = BUY (with tight SL warning)
- [ ] Intraday recommendation = WAIT
- [ ] Swing recommendation = AVOID
- [ ] Risk disclosure mentions counter-trend
- [ ] Response time < 5 seconds

---

## Test Scenario 4: CHOCH Override (Immediate Exit Warning)

**Setup:**
- Macro: BULLISH (risk-on)
- SMC: **CHOCH DETECTED** (structure reversal)
- Advanced: RMAG -1.0 ATR (mildly oversold)
- Technical: Decision engine says BUY (but CHOCH overrides)

**Expected Result:**
```
🎯 CONFLUENCE VERDICT
🚨 CHOCH DETECTED - STRUCTURE REVERSAL
EXIT/TIGHTEN - Structure has broken, trend reversing
Risk Level: HIGH - Counter-trend signals emerging

📈 LAYERED RECOMMENDATIONS

SCALP (M5 entry, 2-4hr hold):
⚪ WAIT - CHOCH detected, avoid new entries
Structure reversing, wait for confirmation

INTRADAY (M15 entry, 12-24hr hold):
🔴 AVOID - CHOCH detected, structure reversing
Wait for new structure to form before intraday entry

SWING (H1 entry, multi-day hold):
🔴 AVOID - Structure break invalidates higher timeframe setups
```

**Validation:**
- [ ] CHOCH detection triggers override
- [ ] Confluence verdict = CHOCH DETECTED warning
- [ ] All recommendations = AVOID/WAIT
- [ ] Exit warning appears prominently
- [ ] Priority logic: CHOCH overrides bullish macro
- [ ] Response time < 5 seconds

---

## Test Scenario 5: Neutral All Layers (Clear WAIT)

**Setup:**
- Macro: NEUTRAL (VIX 17, DXY flat, S&P flat)
- SMC: No CHOCH, no BOS (choppy/ranging)
- Advanced: RMAG -0.5 ATR (neutral), RSI 50
- Technical: Decision engine says HOLD

**Expected Result:**
```
🎯 CONFLUENCE VERDICT
⚪ WAIT - Neutral Across All Layers
No clear setup, wait for confluence
Risk Level: N/A - No position recommended

📈 LAYERED RECOMMENDATIONS

SCALP (M5 entry, 2-4hr hold):
⚪ WAIT - No M5 setup currently
Current conditions don't support scalp entry

INTRADAY (M15 entry, 12-24hr hold):
⚪ WAIT - No M15 BOS confirmation yet
Current setup: Awaiting structure confirmation

SWING (H1 entry, multi-day hold):
🚫 NOT RECOMMENDED - User prefers scalp/intraday only
```

**Validation:**
- [ ] Macro bias = NEUTRAL
- [ ] SMC trend = UNKNOWN/CHOPPY
- [ ] Advanced features = neutral
- [ ] Confluence verdict = WAIT
- [ ] All recommendations = WAIT/NOT RECOMMENDED
- [ ] Clear explanation of why waiting
- [ ] Response time < 5 seconds

---

## Test Scenario 6: Conflicting Signals (Macro vs Structure)

**Setup:**
- Macro: BULLISH (risk-on, DXY falling)
- SMC: BEARISH trend (H1 downtrend, no reversal)
- Advanced: RMAG +1.5 ATR (overbought)
- Technical: Decision engine says SELL

**Expected Result:**
```
🎯 CONFLUENCE VERDICT
⚠️ CONFLICTING SIGNALS
Macro bullish but structure bearish - WAIT for clarity
Risk Level: HIGH - Mixed signals, avoid trading

📈 LAYERED RECOMMENDATIONS

SCALP (M5 entry, 2-4hr hold):
⚪ WAIT - Conflicting macro/structure signals
Risk too high, wait for alignment

INTRADAY (M15 entry, 12-24hr hold):
⚪ WAIT - Macro and structure diverging
Current setup: Conflicting layers, no clear direction

SWING (H1 entry, multi-day hold):
🔴 AVOID - Mixed signals increase risk
```

**Validation:**
- [ ] Macro bias = BULLISH
- [ ] SMC trend = BEARISH
- [ ] Confluence verdict = CONFLICTING SIGNALS
- [ ] All recommendations = WAIT/AVOID
- [ ] Clear explanation of conflict
- [ ] Risk level = HIGH
- [ ] Response time < 5 seconds

---

## Performance Tests

### Test 7: Response Time Verification

**Test for each symbol:**
- BTCUSD (crypto with all 6 macro indicators)
- XAUUSD (gold with DXY/US10Y emphasis)
- EURUSD (forex with standard macro)

**Expected:**
- [ ] BTCUSD analysis completes in <5 seconds
- [ ] XAUUSD analysis completes in <5 seconds
- [ ] EURUSD analysis completes in <5 seconds
- [ ] All layers present in each response
- [ ] No timeout errors
- [ ] Data is fresh (timestamp within last 60 seconds)

---

## Data Completeness Tests

### Test 8: Verify All Layers Present

**For any symbol call, verify response includes:**

**Macro Layer:**
- [ ] DXY value and trend
- [ ] VIX value and interpretation
- [ ] US10Y value and trend
- [ ] S&P 500 (for crypto)
- [ ] BTC Dominance (for crypto)
- [ ] Fear & Greed Index (for crypto)
- [ ] Macro bias (BULLISH/BEARISH/NEUTRAL)

**SMC Layer:**
- [ ] H1 structure status
- [ ] M15 structure status
- [ ] M5 structure status
- [ ] CHOCH detected (true/false)
- [ ] BOS detected (true/false)
- [ ] Structure trend (BULLISH/BEARISH/UNKNOWN)

**Advanced Layer:**
- [ ] RMAG value and interpretation
- [ ] VWAP zone
- [ ] Volatility regime
- [ ] Momentum pressure ratio
- [ ] Summary of technical conditions

**Confluence:**
- [ ] Clear verdict statement
- [ ] Action recommendation
- [ ] Risk level assessment

**Recommendations:**
- [ ] Scalp section with entry/SL/TP or WAIT
- [ ] Intraday section with setup or WAIT
- [ ] Swing section (always NOT RECOMMENDED per user preference)

---

## Integration Tests

### Test 9: Compare with Individual Tool Calls

**Run both:**
1. `moneybot.analyse_symbol_full(symbol: "BTCUSD")`
2. Individual calls:
   - `moneybot.macro_context(symbol: "BTCUSD")`
   - `moneybot.getMultiTimeframeAnalysis(symbol: "BTCUSD")`
   - `moneybot.getAdvancedFeatures(symbol: "BTCUSD")`

**Verify:**
- [ ] Data from unified call matches individual calls
- [ ] Macro bias is same
- [ ] SMC structure is same
- [ ] Advanced features are same
- [ ] Unified call is faster (single response vs 3 responses)
- [ ] Unified call has better formatted output
- [ ] Confluence logic adds value beyond raw data

---

## Edge Cases

### Test 10: Symbol Not Available

**Test:**
```
Call: moneybot.analyse_symbol_full(symbol: "INVALIDXX")
```

**Expected:**
- [ ] Graceful error message
- [ ] No crash
- [ ] Clear explanation that symbol is not available

### Test 11: MT5 Disconnected

**Test:**
```
Call: moneybot.analyse_symbol_full(symbol: "BTCUSD")
(with MT5 offline)
```

**Expected:**
- [ ] Error caught and reported
- [ ] Message: "MT5 service not initialized" or similar
- [ ] No partial data returned

---

## Success Criteria Summary

All tests must pass:
- ✅ All 4 layers properly fetched
- ✅ Priority logic correctly applied
- ✅ CHOCH overrides other signals
- ✅ Macro + SMC + Advanced confluence works
- ✅ Conflicting signals identified
- ✅ Layered recommendations appropriate
- ✅ Response time < 5 seconds
- ✅ Data completeness verified
- ✅ Error handling graceful
- ✅ Consistent with individual tool calls
- ✅ Output format clear and actionable

---

**Test Status:** Ready for execution
**Last Updated:** 2025-10-14
**Version:** 1.0

