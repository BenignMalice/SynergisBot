# ⚡ Signal Scanner - Quick Reference

## 🎯 **TL;DR**

**What it monitors:** 50+ technical indicators across 4 timeframes (M5, M15, M30, H1)

**When it alerts:** Only when confidence ≥ 75% AND R:R ≥ 1.2

**Why "no signal":** Market doesn't meet strict criteria (protecting you from bad trades!)

---

## 📊 **Current Setup**

```
Symbols: XAUUSDc, BTCUSDc, EURUSDc, USDJPYc
Scan Frequency: Every 5 minutes
Min Confidence: 75%
Min Risk:Reward: 1.2
```

---

## 🔍 **What's Analyzed**

### **1. Market Regime**
- TREND (ADX > 35)
- RANGE (ADX < 28)
- VOLATILE (ATR spike)
- CHOP (ADX < 22)

### **2. Multi-Timeframe Confluence**
- M5, M15, M30, H1 alignment
- MTF Score 0-100
- Requires 3+ timeframes aligned

### **3. Technical Indicators (50+)**

**Trend:**
- EMA20, EMA50, EMA200
- ADX, MACD
- EMA Slope

**Momentum:**
- RSI (oversold <30, overbought >70)
- Stochastic
- ROC, Acceleration

**Volatility:**
- ATR, Bollinger Bands
- BB Width, Squeeze
- ATR Spike Detection

**Volume:**
- Volume, VWAP
- Volume Profile
- Volume Trend

**Price Action:**
- S/R Levels
- Swing Highs/Lows
- Liquidity Sweeps
- Fair Value Gaps

**Patterns:**
- Candle patterns (engulfing, pin bar, doji)
- Chart patterns (rectangles, triangles, flags)

---

## ✅ **Signal Requirements**

**Must have ALL:**
1. Direction = BUY or SELL (not HOLD)
2. Confidence ≥ 75%
3. Risk:Reward ≥ 1.2
4. Spread < 35% ATR
5. No news blackout
6. Circuit breaker OK

---

## ❌ **Why "No Signal"**

**Common reasons:**

1. **Choppy market** (ADX < 20)
2. **Low confidence** (< 75%)
3. **Conflicting timeframes** (MTF score < 70)
4. **Weak momentum** (RSI neutral 45-55)
5. **Poor R:R** (< 1.2)
6. **Wide spread** (> 35% ATR)
7. **News blackout** (high-impact event nearby)
8. **Circuit breaker** (daily loss limit reached)

---

## 📱 **What You See**

### **Signal Found:**
```
🔔 Signal Alert!

🟢 BUY XAUUSD
📊 Entry: $3950.00
🛑 SL: $3944.00
🎯 TP: $3965.00
💡 Oversold RSI, bullish EMA, strong trend
📈 Confidence: 82%
```

### **No Signal:**
**You get NO message** - scanner only alerts on high-confidence setups.

---

## ⚙️ **Configuration**

**Change symbols** (`config/settings.py`):
```python
SIGNAL_SCANNER_SYMBOLS = ["XAUUSDc", "BTCUSDc", ...]
```

**Change confidence threshold:**
```python
SIGNAL_SCANNER_MIN_CONFIDENCE = 75  # 70-80 recommended
```

**Change scan frequency** (`chatgpt_bot.py`):
```python
scheduler.add_job(scan_for_signals, 'interval', minutes=5)
```

---

## 💡 **Key Points**

1. ✅ **Very selective** - Only alerts on high-quality setups
2. ✅ **50+ indicators** - Comprehensive analysis
3. ✅ **4 timeframes** - Multi-timeframe confluence
4. ✅ **Risk management** - Spread, news, circuit breaker checks
5. ✅ **"No signal" is GOOD** - Protecting you from bad trades!

---

**Bottom Line:** The scanner is working correctly. It's just VERY selective (75%+ confidence required). Most of the time, market conditions don't meet the strict criteria. This is protecting you! 🎯✅

---

**Full details:** See `SIGNAL_SCANNER_EXPLAINED.md`

