# TESTING SCENARIOS
## Mandatory Data Usage Rules - Verification Tests

**Date:** 2025-12-07  
**Purpose:** Verify all mandatory data usage rules are enforced correctly  
**Status:** Ready for Testing

---

## TESTING STRATEGY

### Test Categories

1. **Global Rules Tests** - Verify global "never ignore data" rules
2. **Display = Usage Tests** - Verify display enforcement
3. **Priority Hierarchy Tests** - Verify conflict resolution
4. **Uncertainty Handling Tests** - Verify uncertainty description
5. **Final Verdict Tests** - Verify metric reference requirements
6. **Symbol-Specific Tests** - Verify BTCUSD, XAUUSD, Forex requirements
7. **Edge Case Tests** - Verify null fields, unusual patterns, missing data

---

## TEST SCENARIO 1: BTCUSD - Missing CVD Slope (Critical Test)

### Test Data
```json
{
  "symbol": "BTCUSD",
  "current_price": 89239.38,
  "order_flow": {
    "delta_volume": 31.7,
    "cvd": {
      "current": 32.22,
      "slope": -0.14
    },
    "cvd_divergence": {
      "strength": 0,
      "type": null
    },
    "buy_sell_pressure": {
      "ratio": 3.85,
      "dominant_side": "buy"
    }
  },
  "structure": {
    "choch": false,
    "bos": false,
    "trend": "unknown"
  },
  "volatility": {
    "regime": "transitional",
    "atr": 1.32
  }
}
```

### Expected Behavior

**✅ MUST Display:**
- Delta Volume: +31.7 (BUY pressure dominant)
- CVD: +32.22 (rising)
- **CVD Slope: -0.14/bar (weakening momentum - contradicts positive Delta)**
- CVD Divergence: None detected (strength: 0, type: null)
- Buy/Sell Pressure: 3.85:1 (Bullish but thin liquidity)

**✅ MUST Identify Contradiction:**
- "⚠️ CONTRADICTION: Buy pressure is weakening internally – negative CVD slope (-0.14/bar) contradicts positive Delta (+31.7). This signals potential exhaustion."

**✅ Final Verdict MUST Reference:**
- At least one structure field (CHOCH/BOS status)
- At least one volatility field (ATR, regime)
- At least one order flow field (CVD slope, Delta)

**❌ FORBIDDEN:**
- Omitting CVD Slope from display
- Generic verdict like "WAIT - no setup"
- Not identifying the contradiction

### Test Pass Criteria
- [ ] CVD Slope is displayed with interpretation
- [ ] Contradiction is explicitly identified
- [ ] Final verdict references specific metrics (structure, volatility, order flow)
- [ ] No generic statements

---

## TEST SCENARIO 2: BTCUSD - Null CVD Divergence

### Test Data
```json
{
  "symbol": "BTCUSD",
  "order_flow": {
    "cvd_divergence": {
      "strength": 0,
      "type": null
    }
  }
}
```

### Expected Behavior

**✅ MUST Display:**
- "CVD Divergence: None detected (strength: 0, type: null)"

**❌ FORBIDDEN:**
- Omitting CVD Divergence from display
- Stating "CVD Divergence not available" (when it IS available, just null)

### Test Pass Criteria
- [ ] CVD Divergence is displayed even though strength = 0
- [ ] Explicitly states "None detected" with values
- [ ] Not silently omitted

---

## TEST SCENARIO 3: BTCUSD - Order Flow vs HTF Trend Conflict

### Test Data
```json
{
  "symbol": "BTCUSD",
  "htf_trend": {
    "direction": "bullish",
    "ema_alignment": "EMA20 < EMA50 < EMA200"
  },
  "order_flow": {
    "delta_volume": 31.7,
    "cvd": {
      "slope": -0.14
    }
  }
}
```

### Expected Behavior

**✅ MUST Apply Priority Hierarchy:**
- Order flow (Priority 2) overrides HTF trend (Priority 5)
- Explicit resolution statement: "RESOLUTION: Order flow (priority 2) overrides HTF trend (priority 5). Verdict: WAIT - Order flow contradicts HTF structure."

**❌ FORBIDDEN:**
- Ignoring the conflict
- Choosing HTF trend over order flow without acknowledgment
- Generic resolution

### Test Pass Criteria
- [ ] Conflict is explicitly identified
- [ ] Priority hierarchy is applied correctly
- [ ] Resolution statement includes priority numbers
- [ ] Final verdict reflects order flow priority

---

## TEST SCENARIO 4: XAUUSD - Missing Macro Context

### Test Data
```json
{
  "symbol": "XAUUSD",
  "macro": {
    "dxy": 104.50,
    "us10y": 4.25,
    "real_yields": null
  },
  "volatility": {
    "atr": 45,
    "regime": "normal"
  },
  "structure": {
    "choch": false,
    "bos": false
  }
}
```

### Expected Behavior

**✅ MUST Display:**
- DXY: 104.50 (with direction if available)
- US10Y: 4.25% (with direction if available)
- Real Yields: null - "Field present but no real yields data available. This may indicate data collection gap."

**✅ Final Verdict MUST Reference:**
- At least one macro context field (DXY, US10Y)
- At least one volatility field (ATR, regime)
- At least one structure field (CHOCH/BOS status)

**❌ FORBIDDEN:**
- Omitting null Real Yields without acknowledgment
- Generic verdict like "WAIT - no clear structure"

### Test Pass Criteria
- [ ] All macro fields displayed (including null Real Yields)
- [ ] Null field explicitly acknowledged
- [ ] Final verdict references macro, volatility, and structure fields
- [ ] No generic statements

---

## TEST SCENARIO 5: Forex (USDJPY) - Missing US10Y (Critical)

### Test Data
```json
{
  "symbol": "USDJPY",
  "macro": {
    "us10y": 4.25,
    "usd_sentiment": "bearish"
  },
  "volatility": {
    "atr": 85,
    "regime": "normal"
  },
  "structure": {
    "choch": false
  }
}
```

### Expected Behavior

**✅ MUST Display:**
- US10Y: 4.25% (CRITICAL for USDJPY - 50% weight)
- USD Sentiment: Bearish
- Interpretation: "US10Y falling (4.25%) = bearish context for USDJPY"

**✅ Final Verdict MUST Reference:**
- US10Y (critical for USDJPY)
- Volatility field (ATR, regime)
- Structure field (CHOCH/BOS status)

**❌ FORBIDDEN:**
- Omitting US10Y from display
- Not emphasizing US10Y importance for USDJPY
- Generic verdict

### Test Pass Criteria
- [ ] US10Y is displayed and emphasized as critical
- [ ] Final verdict references US10Y, volatility, and structure
- [ ] No generic statements

---

## TEST SCENARIO 6: Uncertainty Handling - Unusual Pattern

### Test Data
```json
{
  "symbol": "BTCUSD",
  "order_flow": {
    "cvd": {
      "slope": -0.0001
    }
  }
}
```

### Expected Behavior

**✅ MUST Describe Uncertainty:**
- "CVD Slope: -0.0001/bar - Interpretation uncertain: Value is extremely small, may indicate near-zero momentum or calculation precision limit. Treating as neutral momentum signal."

**❌ FORBIDDEN:**
- Silently skipping the field
- Omitting interpretation
- Not acknowledging uncertainty

### Test Pass Criteria
- [ ] Field is displayed
- [ ] Uncertainty is explicitly described
- [ ] Interpretation provided despite uncertainty
- [ ] Not silently omitted

---

## TEST SCENARIO 7: Missing Optional Fields

### Test Data
```json
{
  "symbol": "BTCUSD",
  "order_flow": {
    "delta_volume": 31.7,
    "cvd": {
      "current": 32.22,
      "slope": -0.14
    },
    "whale_activity": null,
    "liquidity_voids": null
  }
}
```

### Expected Behavior

**✅ MUST Acknowledge Missing Fields:**
- "Whale Activity: Field not available in this snapshot"
- "Liquidity Voids: Field not available in this snapshot"

**OR if fields are present but null:**
- "Whale Activity: null - No whale activity detected in observation window"
- "Liquidity Voids: null - No liquidity voids detected"

**❌ FORBIDDEN:**
- Silently omitting fields
- Not acknowledging missing/null fields

### Test Pass Criteria
- [ ] Missing/null fields are explicitly acknowledged
- [ ] Reason for missing data is stated
- [ ] Not silently omitted

---

## TEST SCENARIO 8: Derived Metrics - CVD Slope Calculation

### Test Data
```json
{
  "symbol": "BTCUSD",
  "order_flow": {
    "cvd": {
      "current": 32.22,
      "previous": 32.36
    }
}
```

### Expected Behavior

**✅ MUST Treat Derived Metric as Mandatory:**
- If CVD Slope is calculated from CVD values, it MUST be displayed and interpreted
- "CVD Slope: -0.14/bar (calculated from CVD change: 32.22 - 32.36 = -0.14)"

**❌ FORBIDDEN:**
- Treating calculated slope as "optional"
- Omitting derived metrics

### Test Pass Criteria
- [ ] Derived metric (CVD Slope) is displayed
- [ ] Derived metric is interpreted
- [ ] Not treated as optional

---

## TEST SCENARIO 9: Final Verdict - Generic vs Specific

### Test Data
```json
{
  "symbol": "BTCUSD",
  "structure": {
    "choch": false,
    "bos": false
  },
  "volatility": {
    "regime": "transitional",
    "atr": 1.32
  },
  "order_flow": {
    "delta_volume": 31.7,
    "cvd": {
      "slope": -0.14
    }
  }
}
```

### Expected Behavior

**✅ REQUIRED Format:**
- "Verdict: WAIT - Structure unclear (no CHOCH/BOS), volatility transitional (ATR 1.32×), order flow shows weakening buy pressure (negative CVD slope -0.14/bar) despite positive Delta (+31.7), indicating potential exhaustion."

**❌ FORBIDDEN Formats:**
- "Verdict: WAIT - no setup"
- "Verdict: WAIT - no clear structure"
- "Verdict: WAIT - conditions not met"
- "Verdict: WAIT - unclear market"

### Test Pass Criteria
- [ ] Final verdict references specific structure field
- [ ] Final verdict references specific volatility field
- [ ] Final verdict references specific order flow field
- [ ] No generic statements
- [ ] Specific values included (ATR 1.32, CVD slope -0.14, etc.)

---

## TEST SCENARIO 10: Self-Verification Checklist Failure

### Test Data
```json
{
  "symbol": "BTCUSD",
  "order_flow": {
    "delta_volume": 31.7,
    "cvd": {
      "current": 32.22
    }
}
```

### Expected Behavior

**✅ MUST Halt and Regenerate:**
- If CVD Slope is missing from display, model MUST produce:
- "⚠️ VERIFICATION FAILED: Missing required elements. Regenerating analysis with complete data usage."

**❌ FORBIDDEN:**
- Proceeding with incomplete data
- Not self-verifying

### Test Pass Criteria
- [ ] Self-verification checklist is completed
- [ ] Missing elements trigger halt and regeneration
- [ ] Complete data usage in regenerated output

---

## TEST SCENARIO 11: XAUUSD - Macro Context Interpretation

### Test Data
```json
{
  "symbol": "XAUUSD",
  "macro": {
    "dxy": 104.50,
    "us10y": 4.25,
    "direction_dxy": "rising",
    "direction_us10y": "falling"
  }
}
```

### Expected Behavior

**✅ MUST Interpret Macro Context:**
- "DXY: 104.50 (rising) + US10Y: 4.25% (falling) = bearish macro context for gold"
- "This influences confidence assessment, NOT directional signals"

**❌ FORBIDDEN:**
- Using macro context as directional signal
- Omitting interpretation
- Not stating it's confidence-only

### Test Pass Criteria
- [ ] Macro context is interpreted
- [ ] States it's confidence-only (not directional)
- [ ] Directional interpretation is provided

---

## TEST SCENARIO 12: Forex (EURUSD) - DXY Alignment

### Test Data
```json
{
  "symbol": "EURUSD",
  "macro": {
    "dxy": 104.50,
    "direction_dxy": "rising"
  },
  "volatility": {
    "atr": 65,
    "regime": "normal"
  },
  "structure": {
    "choch": false
  }
}
```

### Expected Behavior

**✅ MUST Display and Interpret:**
- "DXY: 104.50 (rising) = bearish macro context for EUR"
- Final verdict: "Verdict: WAIT - DXY rising (104.50) = bearish macro context for EUR, volatility normal (ATR 65), structure unclear (no CHOCH/BOS), liquidity balanced between PDH/PDL."

**❌ FORBIDDEN:**
- Omitting DXY interpretation
- Generic verdict

### Test Pass Criteria
- [ ] DXY is displayed with interpretation
- [ ] Final verdict references DXY, volatility, structure
- [ ] No generic statements

---

## TEST SCENARIO 13: Field Collapsing Prevention

### Test Data
```json
{
  "symbol": "BTCUSD",
  "order_flow": {
    "delta_volume": 31.7,
    "cvd": {
      "current": 32.22,
      "slope": -0.14
    },
    "buy_sell_pressure": {
      "ratio": 3.85
    }
  }
}
```

### Expected Behavior

**✅ REQUIRED Format:**
- "Delta Volume: +31.7 (buy pressure). CVD: +32.22 (rising). CVD Slope: -0.14/bar (weakening momentum). Buy/Sell Pressure: 3.85:1 (Bullish)."

**❌ FORBIDDEN Formats:**
- "Order flow is mixed"
- "Order flow shows bullish bias"
- "Multiple order flow signals"

### Test Pass Criteria
- [ ] Each field has unique interpretation line
- [ ] No generic collapsed statements
- [ ] All fields displayed separately

---

## TEST SCENARIO 14: Priority Hierarchy - Structure vs Technical

### Test Data
```json
{
  "symbol": "BTCUSD",
  "structure": {
    "choch": false,
    "bos": false
  },
  "technical": {
    "rsi": 65,
    "macd": "bullish"
  }
}
```

### Expected Behavior

**✅ MUST Apply Priority Hierarchy:**
- Structure (Priority 1) overrides Technical (Priority 5)
- "Structure: No CHOCH/BOS (unclear). Technical: RSI bullish, MACD bullish. RESOLUTION: Structure (priority 1) overrides technical indicators (priority 5). Verdict: WAIT - Structure unclear despite bullish indicators."

**❌ FORBIDDEN:**
- Using technical indicators to override unclear structure
- Not applying priority hierarchy

### Test Pass Criteria
- [ ] Priority hierarchy is applied
- [ ] Structure priority is respected
- [ ] Resolution statement includes priority numbers

---

## TEST SCENARIO 15: Complete BTCUSD Analysis - All Fields

### Test Data
```json
{
  "symbol": "BTCUSD",
  "current_price": 89239.38,
  "order_flow": {
    "delta_volume": 31.7,
    "cvd": {
      "current": 32.22,
      "slope": -0.14
    },
    "cvd_divergence": {
      "strength": 0,
      "type": null
    },
    "absorption_zones": null,
    "buy_sell_pressure": {
      "ratio": 3.85,
      "dominant_side": "buy"
    },
    "order_book_imbalance": 4433,
    "whale_activity": {
      "buy": 6,
      "sell": 1
    },
    "liquidity_voids": 6
  },
  "microstructure": {
    "volatility_state": "contracting",
    "momentum_quality": "fair",
    "liquidity_zones": {
      "pdh": 89538,
      "pdl": 89058
    }
  },
  "structure": {
    "choch": false,
    "bos": false,
    "trend": "unknown"
  },
  "volatility": {
    "regime": "transitional",
    "atr": 1.32
  }
}
```

### Expected Behavior

**✅ MUST Display ALL Fields:**
- Delta Volume: +31.7 (BUY pressure dominant)
- CVD: +32.22 (rising)
- CVD Slope: -0.14/bar (weakening momentum - contradicts positive Delta)
- CVD Divergence: None detected (strength: 0, type: null)
- Absorption Zones: null - Field present but no absorption detected
- Buy/Sell Pressure: 3.85:1 (Bullish but thin liquidity)
- Order Book Imbalance: +4433% (upside liquidity voids forming)
- Whale Activity: 6 buy vs 1 sell → bullish bias
- Liquidity Voids: 6 zones detected — price may whipsaw
- Microstructure: Contracting volatility, fair momentum, liquidity between PDH/PDL
- Structure: No CHOCH/BOS (unclear)
- Volatility: Transitional (ATR 1.32×)

**✅ MUST Identify Contradiction:**
- CVD Slope negative while Delta positive

**✅ Final Verdict MUST Reference:**
- Structure field (no CHOCH/BOS)
- Volatility field (transitional, ATR 1.32)
- Order flow field (CVD slope -0.14, Delta +31.7)

### Test Pass Criteria
- [ ] All 11 order flow fields displayed
- [ ] All microstructure fields displayed
- [ ] All structure/volatility fields displayed
- [ ] Contradiction identified
- [ ] Final verdict references specific metrics
- [ ] No fields silently omitted

---

## TEST EXECUTION CHECKLIST

### Pre-Test Setup
- [ ] Load updated knowledge documents
- [ ] Prepare test data snapshots
- [ ] Clear any cached responses

### Test Execution
- [ ] Run Test Scenario 1 (Missing CVD Slope)
- [ ] Run Test Scenario 2 (Null CVD Divergence)
- [ ] Run Test Scenario 3 (Order Flow vs HTF Conflict)
- [ ] Run Test Scenario 4 (XAUUSD Missing Macro)
- [ ] Run Test Scenario 5 (USDJPY Missing US10Y)
- [ ] Run Test Scenario 6 (Uncertainty Handling)
- [ ] Run Test Scenario 7 (Missing Optional Fields)
- [ ] Run Test Scenario 8 (Derived Metrics)
- [ ] Run Test Scenario 9 (Final Verdict Format)
- [ ] Run Test Scenario 10 (Self-Verification)
- [ ] Run Test Scenario 11 (XAUUSD Macro Interpretation)
- [ ] Run Test Scenario 12 (EURUSD DXY Alignment)
- [ ] Run Test Scenario 13 (Field Collapsing)
- [ ] Run Test Scenario 14 (Priority Hierarchy)
- [ ] Run Test Scenario 15 (Complete BTCUSD Analysis)

### Post-Test Verification
- [ ] All test scenarios passed
- [ ] No fields silently omitted
- [ ] All contradictions identified
- [ ] All final verdicts reference specific metrics
- [ ] All uncertainty described
- [ ] All null fields acknowledged

---

## EXPECTED OUTCOMES SUMMARY

### Before Implementation (2025-12-07 Analysis)
- ❌ CVD Slope missing
- ❌ CVD Divergence missing
- ❌ Absorption Zones missing
- ❌ Generic verdict: "WAIT - no setup"
- ❌ No contradiction identification

### After Implementation (Expected)
- ✅ All order flow fields displayed
- ✅ All fields interpreted
- ✅ Contradictions explicitly identified
- ✅ Specific verdict: "WAIT - Structure unclear (no CHOCH/BOS), volatility transitional (ATR 1.32×), order flow shows weakening buy pressure (negative CVD slope -0.14/bar) despite positive Delta (+31.7)"
- ✅ Priority hierarchy applied
- ✅ Uncertainty described
- ✅ Null fields acknowledged

---

## TESTING NOTES

1. **Test with Real Snapshots:** Use actual market snapshots when possible
2. **Verify Self-Verification:** Check that self-verification checklist triggers when fields are missing
3. **Check Priority Hierarchy:** Verify conflicts are resolved using correct priority order
4. **Monitor Output Length:** More detailed output is expected (this is correct)
5. **Verify Symbol-Specific Rules:** Ensure BTCUSD, XAUUSD, Forex rules are applied correctly

---

**Test Document Created:** 2025-12-07  
**Status:** Ready for Execution  
**Next Steps:** Execute test scenarios and verify all pass criteria are met

