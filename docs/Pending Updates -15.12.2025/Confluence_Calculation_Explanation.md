# Confluence Calculation Methodology

**Date**: December 15, 2025  
**Symbols**: XAUUSDc, BTCUSDc  
**Timeframes**: M1, M5, M15, H1

---

## Overview

The confluence score (0-100) measures trade setup quality by combining multiple technical factors. Each timeframe uses a **weighted average** of 5 core factors, with different calculation methods for M1 vs. M5/M15/H1.

---

## M1 Timeframe (Microstructure Analysis)

**Method**: Uses `M1MicrostructureAnalyzer` for specialized microstructure analysis

### Factors & Weights:

1. **M1 Signal Confidence** (30% weight)
   - Source: CHOCH/BOS confidence score (0-100)
   - Measures: Strength of structure break signals on M1
   - Higher = stronger structural confirmation

2. **Momentum Quality** (25% weight)
   - Source: Momentum quality assessment
   - Values:
     - `EXCELLENT`: 95 points
     - `GOOD`: 80 points
     - `FAIR`: 60 points
     - `CHOPPY`: 40 points
   - Measures: Quality of price momentum (smooth vs. choppy)

3. **Session Volatility Suitability** (20% weight)
   - Source: Current session volatility tier
   - Values:
     - `VERY_HIGH`: 95 points
     - `HIGH`: 90 points
     - `NORMAL`: 80 points
     - `LOW`: 60 points
   - Measures: Whether current volatility is suitable for M1 trading

4. **Liquidity Proximity** (15% weight)
   - Source: Price location relative to liquidity zones (PDH/PDL)
   - Values:
     - `NEAR_PDH` or `NEAR_PDL`: 80 points
     - `BETWEEN`: 70 points
     - `AWAY`: 50 points
   - Measures: Proximity to key liquidity levels (previous day high/low)

5. **Strategy Fit** (10% weight)
   - Source: Trend alignment with strategy hint
   - Base: 70 points
   - Adjustments:
     - `STRONG` alignment: +20 points
     - `MODERATE` alignment: +10 points
   - Measures: How well current market conditions fit the identified strategy

### M1 Calculation Formula:
```
base_score = (signal_confidence × 0.30) + 
             (momentum_quality × 0.25) + 
             (volatility_suitability × 0.20) + 
             (liquidity_proximity × 0.15) + 
             (strategy_fit × 0.10)

adjusted_score = base_score × session_bias_factor (if available)
final_score = clamp(adjusted_score, 0, 100)
```

### M1 Factor Mapping (Display Names):
- `trend_alignment` → `strategy_fit`
- `momentum_alignment` → `momentum_quality`
- `support_resistance` → `liquidity_proximity`
- `volume_confirmation` → `m1_signal_confidence`
- `volatility_health` → `session_volatility_suitability`

---

## M5, M15, H1 Timeframes (Standard Technical Analysis)

**Method**: Uses standard technical indicators from `indicator_bridge.get_multi()`

### Factors & Weights:

1. **Trend Alignment** (30% weight)
   - **Indicators**: EMA20, EMA50, EMA200, Current Price
   - **Scoring**:
     - **100 points**: Perfect alignment
       - Bullish: `Price > EMA20 > EMA50 > EMA200`
       - Bearish: `Price < EMA20 < EMA50 < EMA200`
     - **70 points**: Partial alignment
       - `Price > EMA20 > EMA50` OR `Price < EMA20 < EMA50`
     - **40 points**: Weak alignment
       - `Price > EMA20` OR `Price < EMA20`
     - **0 points**: No alignment
   - **Measures**: How well price and EMAs are aligned (trend strength)

2. **Momentum Alignment** (25% weight)
   - **Indicators**: RSI, MACD, MACD Signal
   - **Scoring**:
     - **100 points**: Strong momentum
       - Bullish: `RSI > 60 AND MACD > Signal AND MACD > 0`
       - Bearish: `RSI < 40 AND MACD < Signal AND MACD < 0`
     - **70 points**: Moderate momentum
       - Bullish: `RSI > 50 AND MACD > Signal`
       - Bearish: `RSI < 50 AND MACD < Signal`
     - **50 points**: Neutral (`45 ≤ RSI ≤ 55`)
     - **30 points**: Weak/conflicting momentum
   - **Measures**: Alignment of momentum indicators (RSI + MACD)

3. **Support/Resistance Confluence** (25% weight)
   - **Indicators**: EMA20, EMA50, EMA200, Bollinger Bands (upper/lower), Current Price
   - **Tolerance**: 0.5% of price (e.g., for $100 price, tolerance = $0.50)
   - **Scoring**:
     - **100 points**: Near EMA200 (most significant level)
     - **85 points**: Near EMA50
     - **75 points**: Near Bollinger Band (upper or lower)
     - **70 points**: Near EMA20
     - **50 points**: Not near any key level (default neutral)
   - **Measures**: Proximity to key support/resistance levels

4. **Volume Confirmation** (10% weight)
   - **Current Status**: Returns neutral score (60 points)
   - **Reason**: Volume data may not be available for all symbols
   - **Future Enhancement**: Will check if volume supports the price move
   - **Measures**: Whether volume confirms the price direction

5. **Volatility Health** (10% weight)
   - **Indicators**: ATR14 (Average True Range), Current Price
   - **Calculation**: `ATR% = (ATR / Price) × 100`
   - **Scoring**:
     - **100 points**: Optimal range (0.5% - 2.0% ATR)
     - **70 points**: Acceptable
       - Too low: 0.3% - 0.5% (choppy market)
       - Slightly high: 2.0% - 3.0%
     - **40 points**: Too high (>3.0% ATR = risky/volatile)
     - **50 points**: Very low (<0.3%)
   - **Measures**: Whether volatility is in a healthy trading range

### M5/M15/H1 Calculation Formula:
```
score = (trend_alignment × 0.30) + 
        (momentum_alignment × 0.25) + 
        (support_resistance × 0.25) + 
        (volume_confirmation × 0.10) + 
        (volatility_health × 0.10)
```

---

## Grade Assignment

**Same for all timeframes:**

- **A**: 85-100 points (Excellent setup)
- **B**: 70-84 points (Good setup)
- **C**: 55-69 points (Fair setup)
- **D**: 40-54 points (Weak setup)
- **F**: 0-39 points (Poor setup)

---

## Key Differences: M1 vs. M5/M15/H1

| Aspect | M1 | M5/M15/H1 |
|--------|----|-----------|
| **Data Source** | M1 candles (200 candles) + microstructure analysis | Multi-timeframe indicator data |
| **Primary Focus** | Microstructure, liquidity, session context | Technical indicators (EMA, RSI, MACD, ATR) |
| **Trend Factor** | Strategy fit (trend alignment with strategy) | EMA alignment (Price vs. EMA20/50/200) |
| **Momentum Factor** | Momentum quality (EXCELLENT/GOOD/FAIR/CHOPPY) | RSI + MACD alignment |
| **Support/Resistance** | Liquidity proximity (PDH/PDL zones) | EMA + Bollinger Band proximity |
| **Volume** | M1 signal confidence (CHOCH/BOS) | Volume confirmation (currently neutral) |
| **Volatility** | Session volatility suitability | ATR percentage health check |
| **Session Awareness** | Yes (session context, volatility tier) | No (timeframe-agnostic) |

---

## Data Requirements

### M1:
- ✅ M1 candle data (minimum 50 candles, typically 200)
- ✅ MT5 connection (for real-time price)
- ✅ M1MicrostructureAnalyzer initialized
- ✅ M1DataFetcher available

### M5/M15/H1:
- ✅ Indicator bridge data for each timeframe
- ✅ EMA20, EMA50, EMA200 values
- ✅ RSI, MACD, MACD Signal values
- ✅ Bollinger Bands (upper/lower)
- ✅ ATR14 value
- ✅ Current price/close

---

## Example Calculation

### M5 Example (XAUUSDc):
```
Trend Alignment: 70 (partial EMA alignment)
Momentum Alignment: 30 (weak momentum)
Support/Resistance: 100 (near EMA200)
Volume Confirmation: 60 (neutral)
Volatility Health: 50 (low volatility)

Score = (70 × 0.30) + (30 × 0.25) + (100 × 0.25) + (60 × 0.10) + (50 × 0.10)
      = 21 + 7.5 + 25 + 6 + 5
      = 64.5 points
Grade = C
```

### M1 Example (BTCUSDc):
```
M1 Signal Confidence: 85
Momentum Quality: 80 (GOOD)
Session Volatility: 80 (NORMAL)
Liquidity Proximity: 70 (BETWEEN)
Strategy Fit: 80 (base 70 + 10 for MODERATE alignment)

Base Score = (85 × 0.30) + (80 × 0.25) + (80 × 0.20) + (70 × 0.15) + (80 × 0.10)
           = 25.5 + 20 + 16 + 10.5 + 8
           = 80 points
Grade = B
```

---

## Notes

1. **Symbol Independence**: Same calculation method applies to both XAUUSDc and BTCUSDc
2. **Caching**: Results are cached for 30 seconds to reduce API load
3. **Error Handling**: Missing data returns `available: false` for that timeframe
4. **Volume Factor**: Currently returns neutral (60) for M5/M15/H1 - can be enhanced when volume data is integrated
5. **M1 Availability**: M1 requires MT5 connection and M1 analyzer - may show as unavailable if MT5 is not connected

---

## References

- **Implementation**: `infra/confluence_calculator.py`
- **M1 Analysis**: `infra/m1_microstructure_analyzer.py`
- **API Endpoint**: `/api/v1/confluence/multi-timeframe/{symbol}`
- **Dashboard**: `/auto-execution/view`

