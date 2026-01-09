# ChatGPT Knowledge: Volatility Regime Trading System

## Overview

The MoneyBot system includes an **automatic volatility regime detection and strategy selection system** that analyzes market conditions and selects appropriate trading strategies when volatile regimes are detected. This system is fully integrated into `moneybot.analyse_symbol_full` and requires no additional user input.

**Key Principle:** When a user asks ChatGPT to "analyse BTCUSD", the system automatically:
1. Detects volatility regime (STABLE, TRANSITIONAL, VOLATILE)
2. Selects appropriate strategy if volatile regime detected
3. Provides trade recommendations with volatility-adjusted risk parameters
4. Includes mitigation layers to prevent false signals and over-optimization

---

## Volatility Regime Detection

### Regime Types

The system classifies market conditions into three regimes:

1. **STABLE** - Normal volatility conditions
   - ATR ratios near baseline (ATR(14)/ATR(50) < 1.3)
   - Bollinger Bands at normal width
   - ADX < 28 (weak trend)
   - Volume at normal levels

2. **TRANSITIONAL** - Volatility increasing but not yet sustained
   - ATR ratios elevated but not confirmed (1.2-1.3)
   - Some volatility indicators elevated
   - Requires confirmation before declaring VOLATILE

3. **VOLATILE** - High volatility conditions confirmed
   - ATR ratio > 1.3 (sustained over 3+ candles)
   - Bollinger Band width > 1.8× median
   - ADX > 28 (strong trend)
   - Volume > 150% of average
   - Daily return standard deviation > 1.5× baseline

### Detection Metrics

The system uses multiple indicators to detect volatility regimes:

- **ATR Ratio:** ATR(14) / ATR(50) - Measures short-term vs long-term volatility
- **Bollinger Band Width:** Current width vs 20-day median
- **ADX (14):** Trend strength indicator (>28 = strong trend)
- **Daily Return Standard Deviation:** 30-day rolling window
- **Volume Spike:** Volume vs 20-day average

### Confluence Score Integration

**IMPORTANT**: Volatility regime directly affects BTC confluence scores.

**For BTCUSDc M1 Timeframe**:
- **STABLE regime**: Volatility suitability scores **80 points**
- **TRANSITIONAL regime**: Volatility suitability scores **75 points**
- **VOLATILE regime**: Volatility suitability scores **85 points** (higher than STABLE)

**Why VOLATILE scores higher**: For BTC, high volatility can be profitable. The system recognizes this and scores VOLATILE regime higher (85) than STABLE (80) for volatility suitability in M1 confluence calculation.

**Example**:
- BTC in VOLATILE regime → M1 confluence volatility suitability: 85/100
- BTC in STABLE regime → M1 confluence volatility suitability: 80/100
- This affects overall M1 confluence score (20% weight)

**Note**: XAU and other symbols use session-based volatility tier (not regime) for confluence calculation. See `ChatGPT_Knowledge_Confluence_Calculation.md` for details.

---

### Multi-Timeframe Analysis

Volatility detection uses weighted multi-timeframe analysis:
- **M5:** 20% weight (micro volatility)
- **M15:** 30% weight (short-term volatility)
- **H1:** 50% weight (primary timeframe)

### Confidence Scoring

Each regime detection includes a confidence score (0-100%):
- **High Confidence (≥70%):** Regime is clearly identified
- **Low Confidence (<70%):** Regime is uncertain - system recommends WAIT

### Persistence Filters

To prevent false signals, the system requires:
- **Persistence:** Regime must hold for ≥3 candles before being declared
- **Regime Inertia:** New regime must hold for minimum duration before flipping
- **Auto-Cooldown:** Rapid reversals (<3 candles) are ignored

---

## Strategy Selection (VOLATILE Regimes Only)

When a VOLATILE regime is detected, the system automatically scores and selects from 4 volatility-aware strategies:

### 1. Breakout-Continuation
- **Use When:** ATR rising, structure break confirmed, volume spike
- **Entry:** Buy Stop above recent high (or Sell Stop below recent low)
- **Stop Loss:** 1.5× ATR from entry
- **Take Profit:** 3× ATR from entry
- **Risk:** High momentum, false breakouts possible

### 2. Volatility Reversion Scalp
- **Use When:** RSI extreme (>70 or <30), mean reversion setup
- **Entry:** Fade the extreme move
- **Stop Loss:** Tight (1.0× ATR)
- **Take Profit:** Quick (1.5× ATR)
- **Risk:** Reversion may not occur quickly

### 3. Post-News Reaction Trade
- **Use When:** High-impact news event occurred, initial reaction has settled
- **Entry:** Trade the continuation or reversal
- **Stop Loss:** 1.5× ATR
- **Take Profit:** 2.5× ATR
- **Risk:** News timing critical, false reactions possible

### 4. Inside Bar Volatility Trap
- **Use When:** Inside bar pattern in volatile regime, breakout pending
- **Entry:** Breakout direction (confirmed by next candle)
- **Stop Loss:** 1.5× ATR
- **Take Profit:** 3× ATR
- **Risk:** False breakouts from inside bars

### Selection Criteria

The system scores each strategy (0-100) based on:
- **Market Phase:** Expansion, Acceleration, Climax, Compression
- **Structure Quality:** Confirmed breaks, trend alignment
- **Volume Confirmation:** Volume spikes, order flow signals
- **Session Alignment:** London/NY overlap, session timing
- **News Context:** Recent news events, impact assessment

**Selection Threshold:** Strategy must score ≥75 to be recommended

**If No Strategy Meets Threshold:**
- System returns WAIT recommendation
- Includes reason code: "SCORE_SHORTFALL"
- Shows top strategy score and why it didn't meet threshold

---

## Risk Management Adjustments

When VOLATILE regime is detected, the system automatically adjusts:

### Position Sizing
- **Base Risk:** 1.0% per trade (normal)
- **Volatile Regime:** Reduced to 0.5% per trade (50% reduction)
- **Rationale:** Smaller positions reduce portfolio risk during high volatility

### Stop Loss Adjustments
- **Base Stop Loss:** 1.0× ATR
- **Volatile Regime:** 1.5× ATR (50% wider)
- **Rationale:** Wider stops account for increased volatility and reduce false stops

### Take Profit Adjustments
- **Base Take Profit:** 2.0× ATR
- **Volatile Regime:** 3.0× ATR (50% wider)
- **Rationale:** Wider targets capture larger moves in volatile conditions

### Circuit Breakers

The system includes automatic circuit breakers:
- **Daily Loss Limit:** Max 2.0% account risk per day
- **Trade Cooldown:** 5-minute cooldown after losses
- **Spread Gate:** Max 2.0× normal spread for volatile trades
- **Slippage Budget:** Max 0.5% slippage tolerance

---

## Response Format for ChatGPT

### Displaying Volatility Regime

**ALWAYS display volatility regime prominently at the top of analysis:**

```
⚡ VOLATILITY REGIME: VOLATILE (85% Confidence)
• ATR Ratio: 1.6× average (H1 elevated)
• Bollinger Width: 2.1× median (expanding)
• ADX: 32 (strong trend)
• Volume: 180% of average
• Phase: ACCELERATION
• Risk Level: HIGH - Position sizes reduced 50%
```

### Displaying Strategy Selection

**If VOLATILE regime and strategy selected:**

```
🎯 Recommended Strategy: Breakout-Continuation
• Strategy Score: 82/100 (above 75 threshold)
• Why: ATR rising (1.6×), structure break confirmed, volume spike
• Alternative: Reversion scored 68 (below threshold)
• Confidence: High (85% regime confidence)
• Entry: $110,500 (Buy Stop)
• Stop Loss: $110,200 (1.5× ATR)
• Take Profit: $111,200 (3× ATR)
• Risk:Reward: 1:2.3

⚠️ Volatile Regime Detected - Position Sizes Reduced 50%
⚠️ Max per-trade risk: 0.5% (reduced from 1.0%)
```

**If WAIT recommended:**

```
📊 Volatility Regime: TRANSITIONAL
• ATR Ratio: 1.25× average (not sustained)
• Strategy Scores: Breakout (68), Reversion (45), Post-News (52), Trap (71)
• Recommendation: WAIT - No strategy meets 75+ threshold
• Reason: Score Shortfall (top score: 71, below 75 threshold)
• Breakout: 68 (ATR rising but structure not confirmed)
• Reversion: 45 (RSI not extreme enough)
• Recommendation: Wait for clearer setup or higher confidence
```

### Risk Confirmation Prompts

**When recommending trade in VOLATILE regime:**

```
⚠️ VOLATILE REGIME TRADE - CONFIRMATION REQUIRED

Regime: VOLATILE (85% Confidence)
Position Size: 0.5% risk (reduced from 1.0%)
Stop Loss: 1.5× ATR (wider than normal)
Risk Warnings:
• Higher slippage risk
• Wider spreads possible
• False breakouts more likely
• Increased volatility

Proceed with trade? (yes/no)
```

---

## Data Structure in Response

The `moneybot.analyse_symbol_full` response includes a `volatility_regime` field:

```json
{
  "volatility_regime": {
    "regime": "VOLATILE",
    "confidence": 85,
    "atr_ratio": 1.6,
    "bb_width_ratio": 2.1,
    "adx": 32,
    "volume_ratio": 1.8,
    "phase": "ACCELERATION",
    "wait_reasons": [],
    "strategy_selection": {
      "selected_strategy": {
        "strategy": "BREAKOUT_CONTINUATION",
        "score": 82,
        "entry": 110500,
        "stop_loss": 110200,
        "take_profit": 111200,
        "risk_reward": 2.3
      },
      "all_scores": [
        {"strategy": "BREAKOUT_CONTINUATION", "score": 82},
        {"strategy": "VOLATILITY_REVERSION_SCALP", "score": 68},
        {"strategy": "POST_NEWS_REACTION_TRADE", "score": 45},
        {"strategy": "INSIDE_BAR_VOLATILITY_TRAP", "score": 71}
      ],
      "wait_reason": null
    }
  }
}
```

**If WAIT recommended:**

```json
{
  "volatility_regime": {
    "regime": "TRANSITIONAL",
    "confidence": 65,
    "atr_ratio": 1.25,
    "wait_reasons": [
      {
        "code": "REGIME_CONFIDENCE_LOW",
        "description": "Regime confidence 65.0% is below threshold (70%)",
        "severity": "medium",
        "threshold": 70,
        "actual": 65
      },
      {
        "code": "SCORE_SHORTFALL",
        "description": "No strategy scored above threshold (best: 71.0 < 75)",
        "severity": "medium",
        "threshold": 75,
        "actual": 71
      }
    ],
    "strategy_selection": {
      "selected_strategy": null,
      "all_scores": [
        {"strategy": "BREAKOUT_CONTINUATION", "score": 68},
        {"strategy": "VOLATILITY_REVERSION_SCALP", "score": 45},
        {"strategy": "POST_NEWS_REACTION_TRADE", "score": 52},
        {"strategy": "INSIDE_BAR_VOLATILITY_TRAP", "score": 71}
      ],
      "wait_reason": {
        "code": "SCORE_SHORTFALL",
        "description": "No strategy scored above threshold (best: 71.0 < 75)",
        "severity": "medium",
        "threshold": 75,
        "actual": 71
      }
    }
  }
}
```

---

## Best Practices for ChatGPT

1. **Always Display Regime Status:** Show volatility regime prominently at the top of every analysis
2. **Explain Strategy Selection:** When a strategy is selected, explain why it was chosen and show alternatives
3. **Transparency in WAIT:** When WAIT is recommended, clearly explain the reason codes
4. **Risk Warnings:** Always highlight risk adjustments (position size reduction, wider stops) in volatile regimes
5. **Confirmation Prompts:** Request explicit confirmation before executing trades in VOLATILE regimes
6. **Educational Context:** Explain what the volatility regime means for the user's trading
7. **Multi-Symbol Comparison:** When analyzing multiple symbols, compare volatility regimes and rank by opportunity

---

## Example ChatGPT Interactions

### Example 1: Volatile Regime with Strategy

**User:** "analyse BTCUSD"

**ChatGPT Response:**
```
📊 BTCUSD Analysis

🕒 2025-11-04 17:45 UTC | 💰 Price: $110,298.76

⚡ VOLATILITY REGIME: VOLATILE (85% Confidence)
• ATR Ratio: 1.6× average (H1 elevated)
• Bollinger Width: 2.1× median (expanding)
• ADX: 32 (strong trend)
• Volume: 180% of average
• Phase: ACCELERATION
• Risk Level: HIGH - Position sizes reduced 50%

🌍 Macro Context:
[Standard macro analysis...]

🎯 Recommended Strategy: Breakout-Continuation
• Strategy Score: 82/100 (above 75 threshold)
• Why: ATR rising (1.6×), structure break confirmed, volume spike
• Alternative: Reversion scored 68 (below threshold)
• Confidence: High (85% regime confidence)
• Entry: $110,500 (Buy Stop)
• Stop Loss: $110,200 (1.5× ATR)
• Take Profit: $111,200 (3× ATR)
• Risk:Reward: 1:2.3

⚠️ Volatile Regime Detected - Position Sizes Reduced 50%
⚠️ Max per-trade risk: 0.5% (reduced from 1.0%)

📈 Trade Setup:
[Detailed setup explanation...]
```

### Example 2: WAIT Recommendation

**User:** "analyse XAUUSD"

**ChatGPT Response:**
```
📊 XAUUSD Analysis

🕒 2025-11-04 17:45 UTC | 💰 Price: $2,651.50

⚡ VOLATILITY REGIME: TRANSITIONAL (65% Confidence)
• ATR Ratio: 1.25× average (not sustained)
• Bollinger Width: 1.6× median (expanding but not confirmed)
• ADX: 24 (moderate trend)
• Volume: 120% of average
• Risk Level: MODERATE

🌍 Macro Context:
[Standard macro analysis...]

🎯 Strategy Assessment:
• Breakout: 68/100 (ATR rising but structure not confirmed)
• Reversion: 45/100 (RSI not extreme enough)
• Post-News: 52/100 (No recent high-impact news)
• Inside Bar: 71/100 (Inside bar present but breakout not confirmed)

⚠️ Recommendation: WAIT
• Reason: Score Shortfall (top score: 71, below 75 threshold)
• Regime Confidence: 65% (below 70% threshold)
• Best Strategy (Inside Bar): 71/100 - Needs structure confirmation

💡 What to Watch:
• Wait for ATR to sustain above 1.3× (currently 1.25×)
• Confirm structure break on M15/H1
• Monitor for RSI extremes (>70 or <30) for reversion setup
• Wait for higher regime confidence (≥70%)

📈 Trade Setup:
No tradeable setup at this time. Monitor for volatility confirmation.
```

---

## Integration Notes

- **Automatic:** No user input required - regime detection happens automatically
- **Transparent:** All regime data, strategy scores, and WAIT reasons are included in response
- **Risk-Aware:** Position sizing and stop losses automatically adjusted for volatile regimes
- **Mitigation:** Multiple filters prevent false signals (persistence, inertia, cooldown)
- **Production Ready:** Phases 1, 2, and 3 complete - fully integrated and tested

---

## Related Documentation

- `docs/VOLATILE_REGIME_TRADING_PLAN.md` - Complete implementation guide
- `docs/PHASE1_COMPLETION_SUMMARY.md` - Phase 1 completion details
- `docs/PHASE2_COMPLETION_SUMMARY.md` - Phase 2 completion details
- `docs/PHASE3_COMPLETION_SUMMARY.md` - Phase 3 completion details

