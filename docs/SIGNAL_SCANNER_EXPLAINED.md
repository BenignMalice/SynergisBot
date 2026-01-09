# 📡 Signal Scanner - What Market Conditions Are Monitored

## 🎯 **Quick Answer**

The Telegram bot's signal scanner monitors **4 symbols** every **5 minutes** and checks for **high-confidence trade setups** (≥75% confidence) using a comprehensive analysis of **50+ technical indicators** and **market structure**.

---

## 📊 **What Symbols Are Monitored**

**Default symbols** (from `config/settings.py`):
```python
SIGNAL_SCANNER_SYMBOLS = ["XAUUSDc", "BTCUSDc", "EURUSDc", "USDJPYc"]
```

**Scan frequency:** Every 5 minutes (300 seconds)

**Minimum confidence:** 75% (only alerts on strong signals)

---

## 🔍 **What Market Conditions Are Analyzed**

The signal scanner uses the **Decision Engine** (`decision_engine.py`) which analyzes **50+ technical factors** across **4 timeframes** (M5, M15, M30, H1).

### **1. Market Regime Detection**

**Determines current market state:**

- **TREND** - Strong directional movement (ADX > 35)
- **RANGE** - Consolidation/sideways (ADX < 28, low BB width)
- **VOLATILE** - High volatility, choppy (ATR spike, wide BB)
- **CHOP** - Weak trend, low volatility (ADX < 22)

**Indicators used:**
- ADX (Average Directional Index) - Trend strength
- Bollinger Band Width - Volatility measure
- ATR (Average True Range) - Volatility
- EMA200 slope - Long-term trend direction

---

### **2. Multi-Timeframe Confluence (MTF)**

**Checks alignment across 4 timeframes:**

**Bullish confluence (BUY signal):**
- M5: Price > EMA20, RSI > 55, bullish momentum
- M15: Price > EMA20, trend aligned
- M30: Bullish structure
- H1: Bullish bias

**Bearish confluence (SELL signal):**
- M5: Price < EMA20, RSI < 45, bearish momentum
- M15: Price < EMA20, trend aligned
- M30: Bearish structure
- H1: Bearish bias

**MTF Score:** 0-100 (higher = stronger alignment)

**Indicators used:**
- EMA20, EMA50, EMA200 (trend direction)
- RSI (momentum)
- Price action relative to EMAs
- Cross-timeframe structure

---

### **3. Technical Indicators (50+ Factors)**

#### **A) Trend Indicators**
- **EMA20, EMA50, EMA200** - Moving average alignment
- **EMA Slope** - Trend acceleration/deceleration
- **ADX** - Trend strength (>35 = strong, <22 = weak)
- **MACD** - Momentum and divergence

#### **B) Momentum Indicators**
- **RSI** - Overbought (>70) / Oversold (<30)
- **Stochastic** - Momentum oscillator
- **ROC (Rate of Change)** - Price velocity
- **Momentum Acceleration** - Change in momentum

#### **C) Volatility Indicators**
- **ATR (Average True Range)** - Volatility measure
- **Bollinger Bands** - Volatility envelope
- **BB Width** - Squeeze detection
- **BB Width Change** - Volatility expansion/contraction
- **ATR Spike Detection** - Sudden volatility

#### **D) Volume Indicators**
- **Volume** - Trading activity
- **VWAP (Volume Weighted Average Price)** - Fair value
- **VWAP Deviation** - Distance from fair value
- **Volume Profile** - Price acceptance zones
- **Volume Trend** - Increasing/decreasing volume

#### **E) Support/Resistance**
- **S/R Levels** - Key price levels
- **Nearest S/R** - Distance to key levels
- **S/R Touch Count** - Level validity
- **S/R Strength** - Historical significance

#### **F) Price Action**
- **Swing Highs/Lows** - Market structure
- **Liquidity Sweeps** - Stop hunts
- **Fair Value Gaps (FVG)** - Imbalance zones
- **Order Blocks** - Institutional levels
- **Break of Structure (BOS)** - Trend changes

#### **G) Candle Patterns**
- **Engulfing** - Reversal pattern
- **Pin Bar** - Rejection pattern
- **Inside Bar** - Consolidation
- **Doji** - Indecision
- **Hammer/Shooting Star** - Reversal signals

#### **H) Chart Patterns**
- **Rectangles** - Range consolidation
- **Triangles** - Compression patterns
- **Double Tops/Bottoms** - Reversal patterns
- **Flags/Pennants** - Continuation patterns
- **Channels** - Trend channels

---

### **4. Advanced Features (If Available)**

**RMAG (Regime Magnitude):**
- Measures trend strength and momentum quality
- Detects regime transitions (trend → range)

**Pressure:**
- Buy/sell pressure analysis
- Institutional order flow

**Liquidity:**
- Liquidity voids (thin order book zones)
- High liquidity zones (support/resistance)

**Fair Value Gaps:**
- Price imbalances
- Unfilled gaps

**Candle Profile:**
- Body-to-wick ratio
- Rejection strength
- Momentum quality

---

### **5. Risk Management Filters**

**Pre-filters (must pass to generate signal):**

#### **A) Spread Check**
- Spread must be < 35% of ATR
- Ensures execution quality

#### **B) ATR Spike Filter**
- Blocks trades during extreme volatility
- ATR must be < 1.8x normal

#### **C) News Blackout**
- Checks for high-impact news events
- Blocks trades 15 min before/after major news

#### **D) Circuit Breaker**
- Checks if daily loss limit reached
- Blocks new trades if max loss exceeded

#### **E) Exposure Guard**
- Checks currency correlation
- Prevents over-exposure to single currency

---

### **6. Signal Strength Calculation**

**Confidence score (0-100%) based on:**

1. **MTF Alignment** (30 points)
   - All timeframes aligned = +30
   - 3 of 4 aligned = +20
   - 2 of 4 aligned = +10

2. **Trend Strength** (20 points)
   - ADX > 35 = +20
   - ADX 25-35 = +15
   - ADX 20-25 = +10

3. **RSI Confirmation** (15 points)
   - RSI aligned with direction = +15
   - RSI extreme (>70 or <30) = +10

4. **Pattern Confirmation** (15 points)
   - Strong pattern detected = +15
   - Weak pattern = +5

5. **S/R Alignment** (10 points)
   - Near key S/R = +10
   - Breakout confirmed = +10

6. **Volume Confirmation** (10 points)
   - Volume increasing = +10
   - Volume decreasing = -5

**Total:** 100 points maximum

**Threshold:** ≥75% required for signal alert

---

## 🎯 **Signal Generation Logic**

### **BUY Signal Requirements:**

**Must have ALL of:**
1. ✅ Direction = BUY from decision engine
2. ✅ Confidence ≥ 75%
3. ✅ Risk:Reward ≥ 1.2
4. ✅ Spread < 35% ATR
5. ✅ No news blackout
6. ✅ Circuit breaker not tripped

**Ideal conditions:**
- RSI < 30 (oversold)
- Price > EMA20 > EMA50 (bullish structure)
- ADX > 20 (trend strength)
- MTF score > 70 (strong alignment)
- Near support level
- Bullish candle pattern

---

### **SELL Signal Requirements:**

**Must have ALL of:**
1. ✅ Direction = SELL from decision engine
2. ✅ Confidence ≥ 75%
3. ✅ Risk:Reward ≥ 1.2
4. ✅ Spread < 35% ATR
5. ✅ No news blackout
6. ✅ Circuit breaker not tripped

**Ideal conditions:**
- RSI > 70 (overbought)
- Price < EMA20 < EMA50 (bearish structure)
- ADX > 20 (trend strength)
- MTF score > 70 (strong alignment)
- Near resistance level
- Bearish candle pattern

---

### **HOLD (No Signal):**

**Reasons for HOLD:**
- Confidence < 75%
- Risk:Reward < 1.2
- Spread too wide
- News blackout active
- Circuit breaker tripped
- Choppy market (ADX < 20)
- No clear direction
- Conflicting timeframes

---

## 📱 **What You See in Telegram**

### **When Signal Found (Confidence ≥ 75%):**

```
🔔 Signal Alert!

🟢 BUY XAUUSD
📊 Entry: $3950.00
🛑 SL: $3944.00
🎯 TP: $3965.00
💡 Oversold (RSI=28.5), bullish EMA crossover, strong trend (ADX=38.2)
📈 Confidence: 82%
```

---

### **When No Signal (Confidence < 75%):**

**You get NO message.** The scanner only alerts on high-confidence setups.

**Why no alert:**
- Market is choppy (ADX < 20)
- Conflicting timeframes (MTF score < 70)
- Weak momentum (RSI neutral 45-55)
- No clear pattern
- Risk:Reward too low (< 1.2)
- Spread too wide

---

## 🔍 **Example: Why "No Signal"**

### **Scenario 1: Choppy Market**

```
Symbol: BTCUSD
ADX: 18 (weak trend)
RSI: 52 (neutral)
MTF Score: 45 (conflicting timeframes)
Confidence: 42%

Result: NO SIGNAL (below 75% threshold)
```

---

### **Scenario 2: Low Risk:Reward**

```
Symbol: EURUSD
Direction: BUY
Entry: 1.1000
SL: 1.0995 (5 pips)
TP: 1.1008 (8 pips)
Risk:Reward: 1.6

BUT: Spread = 2 pips (40% of 5 pip SL)

Result: NO SIGNAL (spread too wide relative to SL)
```

---

### **Scenario 3: News Blackout**

```
Symbol: XAUUSD
Direction: SELL
Confidence: 85%
Risk:Reward: 2.5

BUT: Fed announcement in 10 minutes

Result: NO SIGNAL (news blackout active)
```

---

## ⚙️ **Configuration**

### **Change Monitored Symbols:**

Edit `config/settings.py`:

```python
SIGNAL_SCANNER_SYMBOLS = [
    "XAUUSDc",    # Gold
    "BTCUSDc",    # Bitcoin
    "EURUSDc",    # Euro
    "USDJPYc",    # Yen
    "GBPUSDc",    # Pound (add more)
]
```

---

### **Change Confidence Threshold:**

```python
SIGNAL_SCANNER_MIN_CONFIDENCE = 75  # Lower = more signals (but lower quality)
```

**Recommendations:**
- **75%** - Good balance (default)
- **80%** - Fewer but higher quality signals
- **70%** - More signals but some false positives

---

### **Change Scan Frequency:**

In `chatgpt_bot.py`:

```python
scheduler.add_job(
    scan_for_signals,
    'interval',
    minutes=5,  # Change to 3 or 10 minutes
    args=[app],
    id='signal_scanner',
    max_instances=1
)
```

---

## 📊 **Current Setup (Your Bot)**

```python
Symbols: ["XAUUSDc", "BTCUSDc", "EURUSDc", "USDJPYc"]
Scan Frequency: Every 5 minutes
Min Confidence: 75%
Min Risk:Reward: 1.2
Max Spread: 35% of ATR
```

**This means:**
- Bot checks 4 symbols every 5 minutes
- Only alerts if confidence ≥ 75%
- Only alerts if R:R ≥ 1.2
- Filters out wide-spread conditions
- Respects news blackouts and circuit breaker

---

## 💡 **Why You're Getting "No Signal"**

**Possible reasons:**

1. **Market is choppy** (ADX < 20)
   - No clear trend direction
   - Conflicting timeframes

2. **Confidence below 75%**
   - Weak momentum
   - Poor MTF alignment
   - No clear patterns

3. **Risk:Reward too low** (< 1.2)
   - SL too wide relative to TP
   - Not worth the risk

4. **Spread too wide** (> 35% ATR)
   - Execution quality poor
   - Slippage risk high

5. **News blackout active**
   - High-impact news event nearby
   - Avoiding volatility spike

6. **Circuit breaker tripped**
   - Daily loss limit reached
   - No new trades allowed

---

## 🎯 **Summary**

**The signal scanner analyzes:**

✅ **50+ technical indicators** (trend, momentum, volatility, volume)
✅ **4 timeframes** (M5, M15, M30, H1) for confluence
✅ **Market structure** (S/R, swings, liquidity, FVG)
✅ **Chart patterns** (rectangles, triangles, flags, etc.)
✅ **Candle patterns** (engulfing, pin bars, doji, etc.)
✅ **Risk management** (spread, ATR, news, circuit breaker)
✅ **Advanced features** (RMAG, pressure, liquidity)

**Only alerts when:**
- ✅ Confidence ≥ 75%
- ✅ Risk:Reward ≥ 1.2
- ✅ Spread acceptable
- ✅ No news blackout
- ✅ Circuit breaker OK

**"No signal" means:**
- ❌ Market conditions don't meet the strict criteria
- ❌ Not a high-probability setup
- ❌ Better to wait for clearer opportunity

**This is GOOD!** The scanner is protecting you from low-quality trades. 🎯✅

---

## 📚 **Related Files**

- **`decision_engine.py`** - Main analysis logic (50+ indicators)
- **`chatgpt_bot.py`** - Signal scanner implementation (line 895)
- **`config/settings.py`** - Scanner configuration
- **`infra/signal_scanner.py`** - Signal scanner class (if exists)
- **`app/main_api.py`** - `/ai/analysis` endpoint (simplified version)

---

**Bottom Line:** The signal scanner is VERY selective. It analyzes 50+ factors and only alerts on high-confidence setups (≥75%). "No signal" means the market doesn't meet the strict criteria - which is protecting you from bad trades! 🎯✅

