# Confluence Score Calculation Guide

**Last Updated**: December 15, 2025  
**Version**: 2.0 (Symbol-Specific Logic)

---

## 📊 Overview

The confluence score is a composite metric (0-100) that evaluates trade setup quality across multiple technical factors. **IMPORTANT**: The calculation method varies by symbol - BTC and XAU use different logic.

### Key Concepts

- **Score Range**: 0-100 (higher = better setup)
- **Grade Scale**: A (90-100), B (80-89), C (70-79), D (60-69), F (<60)
- **Timeframes**: M1 (microstructure), M5, M15, H1 (standard TA)
- **Symbol-Specific**: BTC and XAU have different calculation methods

---

## 🎯 Symbol-Specific Logic

### BTCUSDc (Bitcoin)

**Volatility Assessment**: Uses **volatility regime** (STABLE/TRANSITIONAL/VOLATILE) instead of session-based volatility
- **Detection Method**: Uses **RegimeDetector** for accurate multi-timeframe regime detection (with automatic fallback to lightweight method if needed)
- **STABLE**: Normal trading conditions (80 points)
- **TRANSITIONAL**: Moderate volatility (75 points)
- **VOLATILE**: High volatility, can be profitable for BTC (85 points)
- **Note**: RegimeDetector provides more accurate regime classification by analyzing ATR ratios, Bollinger Band width, ADX, and volume patterns across M5, M15, and H1 timeframes

**ATR% Thresholds** (Volatility Health Factor):
- **Optimal Range**: 1.0% - 4.0% (scores 100)
- **Acceptable Range**: 0.8% - 5.0% (scores 60-100)
- **Too Low**: < 0.8% (scores < 60)
- **Too High**: > 5.0% (scores < 60)

**Why Different**: BTC is event-driven and naturally more volatile. Higher ATR% is normal and acceptable.

### XAUUSDc (Gold)

**Volatility Assessment**: Uses **session-based volatility tier** (LOW/NORMAL/HIGH/VERY_HIGH)
- **LOW**: 60 points
- **NORMAL**: 80 points
- **HIGH**: 90 points
- **VERY_HIGH**: 95 points

**ATR% Thresholds** (Volatility Health Factor):
- **Optimal Range**: 0.4% - 1.5% (scores 100)
- **Acceptable Range**: 0.3% - 2.0% (scores 60-100)
- **Too Low**: < 0.3% (scores < 60)
- **Too High**: > 2.0% (scores < 60)

**Why Different**: XAU is session-driven. Lower ATR% is normal during calm sessions.

### Other Symbols (EURUSDc, etc.)

**Volatility Assessment**: Uses session-based volatility tier (same as XAU)

**ATR% Thresholds** (Default):
- **Optimal Range**: 0.5% - 2.0% (scores 100)
- **Acceptable Range**: 0.3% - 3.0% (scores 60-100)

---

## 🔍 Factor Breakdown

### M1 Timeframe (Microstructure Analysis)

**Special Calculation**: Uses microstructure analysis, not standard technical indicators.

**Factors**:
1. **M1 Signal Confidence** (0-100): CHOCH/BOS detection quality
2. **Momentum Quality** (0-100): Momentum strength and direction
3. **Session Volatility Suitability** (0-100):
   - **BTC**: Based on volatility regime detected by **RegimeDetector** (STABLE=80, TRANSITIONAL=75, VOLATILE=85)
     - Uses RegimeDetector for accurate multi-timeframe analysis (with automatic fallback to lightweight method)
   - **XAU/Others**: Based on session volatility tier (LOW=60, NORMAL=80, HIGH=90, VERY_HIGH=95)
4. **Liquidity Proximity** (0-100): Distance to PDH/PDL, equal highs/lows
5. **Strategy Fit** (0-100): Alignment with recommended strategy

**Weighting**:
- Signal Confidence: 30%
- Momentum Quality: 25%
- Volatility Suitability: 20%
- Liquidity Proximity: 15%
- Strategy Fit: 10%

### M5, M15, H1 Timeframes (Standard Technical Analysis)

**Standard Calculation**: Uses traditional technical indicators.

**Factors**:
1. **Trend Alignment** (0-100): EMA alignment (20/50/200)
2. **Momentum Alignment** (0-100): RSI and MACD confirmation
3. **Support/Resistance** (0-100): Proximity to key levels
4. **Volume Confirmation** (0-100): Volume analysis (neutral: 60)
5. **Volatility Health** (0-100): ATR% assessment (symbol-specific thresholds)

**Weighting**:
- Trend Alignment: 30%
- Momentum Alignment: 25%
- Support/Resistance: 25%
- Volume: 10%
- Volatility Health: 10%

---

## 📈 Interpreting Scores

### Score Ranges

- **90-100 (Grade A)**: Excellent setup, high probability
- **80-89 (Grade B)**: Good setup, solid probability
- **70-79 (Grade C)**: Acceptable setup, moderate probability
- **60-69 (Grade D)**: Weak setup, low probability
- **<60 (Grade F)**: Poor setup, avoid

### Symbol-Specific Interpretation

**BTCUSDc**:
- Scores may be higher due to regime-based volatility assessment
- ATR% of 2.5% is **normal** and scores 100 (not penalized)
- VOLATILE regime actually scores **higher** (85) than STABLE (80) for volatility suitability
- Consider volatility regime when explaining setups

**XAUUSDc**:
- Scores use session-based volatility assessment
- ATR% of 0.8% is **optimal** and scores 100
- ATR% of 2.0% is **too high** and scores < 70
- Consider session context when explaining setups

### Factor Interpretation

**When analyzing a trade**:
1. Check confluence score for relevant timeframes (M1, M5, M15, H1)
2. Understand that BTC scores may be higher due to regime-based assessment
3. Interpret ATR% in context of symbol (2.5% ATR is normal for BTC, not for XAU)
4. Consider volatility regime when explaining BTC setups
5. Use session context for XAU, regime context for BTC

---

## 🎯 Usage in Analysis

### When Analyzing Trades

**Template**:
```
📊 Confluence Analysis: {symbol} {timeframe}

Score: {score}/100 (Grade: {grade})
Breakdown:
- Trend Alignment: {trend_score}/100 {explanation}
- Momentum: {momentum_score}/100 {explanation}
- Support/Resistance: {sr_score}/100 {explanation}
- Volume: {volume_score}/100 {explanation}
- Volatility Health: {volatility_score}/100 {explanation}
  {symbol-specific note: ATR% interpretation}
```

**Example (BTC)**:
```
📊 Confluence Analysis: BTCUSDc M1

Score: 85/100 (Grade: B)
Breakdown:
- Signal Confidence: 80/100 (Strong CHOCH detected)
- Momentum Quality: 85/100 (Strong bullish momentum)
- Volatility Suitability: 85/100 (VOLATILE regime - high volatility, can be profitable for BTC)
- Liquidity Proximity: 75/100 (Near PDH, good liquidity)
- Strategy Fit: 80/100 (Aligns with trend continuation)

Note: BTC uses volatility regime (VOLATILE) instead of session-based assessment.
ATR% of 2.5% is normal for BTC and scores 100 in volatility health.
```

**Example (XAU)**:
```
📊 Confluence Analysis: XAUUSDc M5

Score: 78/100 (Grade: B)
Breakdown:
- Trend Alignment: 80/100 (EMA alignment bullish)
- Momentum: 75/100 (RSI and MACD confirm)
- Support/Resistance: 70/100 (Near key resistance)
- Volume: 60/100 (Neutral volume)
- Volatility Health: 85/100 (ATR% 0.8% - optimal for XAU)

Note: XAU uses session-based volatility assessment.
ATR% of 0.8% is optimal for XAU and scores 100 in volatility health.
```

### When Creating Auto-Execution Plans

**Threshold Recommendations**:

**BTCUSDc**:
- **Minimum Confluence**: 70 (Grade C)
- **Recommended**: 80+ (Grade B)
- **Ideal**: 85+ (Grade A)

**XAUUSDc**:
- **Minimum Confluence**: 75 (Grade C+)
- **Recommended**: 80+ (Grade B)
- **Ideal**: 85+ (Grade A)

**Other Symbols**:
- **Minimum Confluence**: 75 (Grade C+)
- **Recommended**: 80+ (Grade B)

**Condition Examples**:
```
# BTC example
if confluence_score >= 80 and volatility_regime in ['STABLE', 'VOLATILE']:
    # Good setup for BTC

# XAU example
if confluence_score >= 80 and session_volatility_tier in ['NORMAL', 'HIGH']:
    # Good setup for XAU
```

---

## ⚠️ Important Notes

### Do NOT Assume

1. **Same ATR% = Same Score**: 2.5% ATR scores 100 for BTC but < 70 for XAU
2. **Higher Volatility = Lower Score**: For BTC, VOLATILE regime scores **higher** (85) than STABLE (80)
3. **Session Context for BTC**: BTC uses regime, not session, for volatility assessment
4. **Regime Context for XAU**: XAU uses session, not regime, for volatility assessment

### Always Consider

1. **Symbol Type**: BTC vs XAU vs Others
2. **Timeframe**: M1 (microstructure) vs M5/M15/H1 (standard TA)
3. **Context**: Regime (BTC) vs Session (XAU)
4. **ATR% Interpretation**: Symbol-specific thresholds

---

## 📚 Examples

### Example 1: BTC with High ATR

**Scenario**: BTCUSDc M5, ATR% = 3.5%

**Interpretation**:
- ATR% 3.5% is within optimal range (1.0%-4.0%) for BTC
- Volatility Health factor scores **100**
- This is **normal** for BTC, not a concern

**ChatGPT Response**:
> "BTCUSDc M5 confluence: 82/100 (Grade B). Volatility Health: 100/100 - ATR% of 3.5% is optimal for BTC (within 1.0%-4.0% range). This is normal volatility for Bitcoin and not a concern."

### Example 2: XAU with High ATR

**Scenario**: XAUUSDc M5, ATR% = 2.0%

**Interpretation**:
- ATR% 2.0% is at the high boundary (2.0%) for XAU
- Volatility Health factor scores **70** (slightly high)
- This is **elevated** for XAU, may indicate increased risk

**ChatGPT Response**:
> "XAUUSDc M5 confluence: 72/100 (Grade C). Volatility Health: 70/100 - ATR% of 2.0% is at the high boundary for XAU (optimal range is 0.4%-1.5%). This indicates elevated volatility, which may increase risk."

### Example 3: BTC Volatility Regime

**Scenario**: BTCUSDc M1, VOLATILE regime detected

**Interpretation**:
- VOLATILE regime scores **85** for volatility suitability (higher than STABLE=80)
- This is **appropriate** for BTC - high volatility can be profitable
- Not a negative signal for BTC

**ChatGPT Response**:
> "BTCUSDc M1 confluence: 87/100 (Grade A). Volatility Suitability: 85/100 - VOLATILE regime detected. For BTC, high volatility can be profitable, so this regime actually scores higher (85) than STABLE (80). This is a positive signal for BTC trading."

---

## 🔗 Related Documents

- `ChatGPT_Knowledge_Document.md` - Main trading rules (includes confluence basics)
- `ChatGPT_Knowledge_Volatility_Regime_Trading.md` - Volatility regime details
- `AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md` - Auto-execution plan creation

---

## 📝 Summary

1. **Confluence scores are symbol-specific**: BTC and XAU use different calculation methods
2. **BTC uses volatility regime**: STABLE/TRANSITIONAL/VOLATILE (not session-based)
3. **XAU uses session volatility**: LOW/NORMAL/HIGH/VERY_HIGH (not regime-based)
4. **ATR% thresholds differ**: BTC optimal is 1.0%-4.0%, XAU optimal is 0.4%-1.5%
5. **Interpret scores in context**: Consider symbol, timeframe, and volatility assessment method
6. **Use appropriate thresholds**: BTC minimum 70, XAU minimum 75 for auto-execution plans

