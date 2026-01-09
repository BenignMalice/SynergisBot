# Loss Cut Monitor - Systematic Loss Management Guide

## 📋 Overview

The **Loss Cut Monitor** is a professional-grade system that detects when to cut losing trades **systematically**, not emotionally. It implements the institutional framework: **"Cut when the reason for entry is no longer true."**

### Key Features

- **7-Category Analysis Framework**: Structural, Momentum, Volatility, Confluence, Time, Risk, Sentiment
- **3-Strikes Rule**: Exit when 3+ categories trigger negative signals
- **Automatic or Alert-Only Modes**: Safety-first approach (alerts by default)
- **Telegram Integration**: Real-time loss cut signals with detailed rationale
- **Database Logging**: Track all loss cut signals for post-trade analysis

---

## 🎯 The 7-Category Framework

### 1. **Structural Invalidation** 🏗️
**What it means**: Your setup's market structure (trend, support/resistance) breaks.

**Signals**:
- Price closes below EMA20 (for longs) or above EMA20 (for shorts)
- Price breaks below swing low (longs) or above swing high (shorts)
- Breakout returns into broken range (false breakout)

**Example**:
```
You bought XAUUSD at $3,925 expecting bounce from EMA50.
If price closes below $3,918 → structure invalid → cut immediately.
```

---

### 2. **Momentum Failure** ⚡
**What it means**: Loss of energy/trend in your direction.

**Signals**:
- ADX drops below 20 → no trend left
- RSI fails to make new highs/lows in your direction (divergence)
- MACD histogram flips against your position
- Heikin Ashi color change against you

**Example**:
```
You're long EURUSD; RSI drops from 65 → 50 while price stalls.
Momentum dying = reduce exposure or exit.
```

---

### 3. **Volatility Expansion Against You** 💥
**What it means**: Sudden volatility spike in opposite direction = regime shift.

**Signals**:
- Candle size > 2× ATR against your position
- Bollinger Band expansion in opposite direction
- ATR spikes sharply while you're in drawdown

**Example**:
```
Gold prints a $12 bearish candle against your long with ATR = $5.
That's 2.4× normal volatility → regime shift → exit immediately.
```

---

### 4. **Confluence Breakdown** 🔗
**What it means**: Indicators that confirmed your entry now disagree.

**Signals**:
- 67%+ of entry indicators now contradict position
- RSI + EMA + ADX + MACD all turn negative

**Example**:
```
You entered long with:
✅ RSI rising, ✅ Price above EMA20, ✅ ADX > 25

Now:
❌ RSI flattening, ❌ Price below EMA20, ❌ ADX dropping
→ 3/3 gone = exit immediately.
```

---

### 5. **Time-Based Invalidation** ⏱️
**What it means**: Trade hasn't moved in your favor within expected timeframe.

**Timeouts**:
- **Scalps**: 15 minutes (3-5 M5 candles)
- **Intraday**: 4 hours
- **Swing**: 8 hours

**Rule**: Good trades move quickly. If stagnant + in drawdown → exit.

---

### 6. **Risk/Equity Limits** 🛡️
**What it means**: Portfolio protection overrides individual trade logic.

**Hard Limits**:
- Max loss per trade: **-1.5R**
- Max daily loss: **5% of account**
- If multiple correlated trades lose → cut all exposure

**Example**:
```
Position at -1.6R → forced cut (exceeds -1.5R limit).
Daily P&L at -5.2% → stop trading for the day.
```

---

### 7. **Sentiment/News Shock** 📰
**What it means**: External macro event reverses market sentiment.

**Signals**:
- Unexpected high-impact news (Fed, CPI, NFP)
- USD Index (DXY) or 10Y yields spike against your trade
- Safe-haven flow (Gold, JPY) starts suddenly

**Example**:
```
You're long AUDUSD; Fed statement turns hawkish → DXY spikes.
Close before momentum cascades.
```

---

## ⚖️ The 3-Strikes Rule

**Core Principle**: If **3 out of 7 categories** turn negative → exit immediately.

### Urgency Levels

| Strikes | Urgency | Action | Description |
|---------|---------|--------|-------------|
| 0 | NONE | Hold | No loss cut signals |
| 1 | WARNING | Tighten SL | Monitor closely, tighten SL |
| 2 | CAUTION | Tighten SL or Cut 50% | Reduce exposure |
| 3+ | CRITICAL | Cut 50% or Cut Full | Exit immediately |

### Decision Logic

**CRITICAL (3+ strikes)**:
- If **structure broken** OR **risk exceeded** → **Cut Full (100%)**
- Otherwise → **Cut 50%** and tighten SL on remainder

**CAUTION (2 strikes)**:
- If loss > **-0.8R** → **Cut 50%**
- Otherwise → **Tighten SL** to breakeven or 0.5× ATR

**WARNING (1 strike)**:
- **Tighten SL** and monitor closely

---

## 🔧 Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Loss Cut Monitor Settings
AUTO_CUT_ENABLED=0  # 0 = alerts only, 1 = auto-execute cuts (use with caution)
```

### Thresholds (in `infra/loss_cut_detector.py`)

```python
LossCutDetector(
    # Structure
    structure_break_confirm_bars=1,
    
    # Momentum
    adx_weak_threshold=20.0,
    rsi_failure_threshold=10.0,
    macd_flip_confirm=True,
    
    # Volatility
    atr_spike_multiplier=2.0,  # 2x ATR = volatility break
    bb_expansion_threshold=1.5,
    
    # Confluence
    min_confluence_indicators=3,
    confluence_break_threshold=0.67,  # 67% must break
    
    # Time
    scalp_timeout=15,  # minutes
    intraday_timeout=240,  # 4 hours
    swing_timeout=480,  # 8 hours
    
    # Risk
    max_loss_r=-1.5,  # Max -1.5R before forced cut
    max_daily_loss_pct=0.05,  # 5% daily loss limit
    
    # 3-Strikes Rule
    strikes_for_warning=1,
    strikes_for_caution=2,
    strikes_for_critical=3,
)
```

---

## 📱 Telegram Alerts

### Alert Format

```
🚨 Loss Cut Signal

XAUUSD (Ticket: 123456)
Unrealized Loss: -0.85R
Time in Trade: 45 minutes

🚨 Urgency: CRITICAL
⚡ Strikes: 3/7 categories triggered
🎯 Recommended: CUT FULL POSITION IMMEDIATELY
📈 Confidence: 87%

💡 Rationale:
CRITICAL: 3 strikes detected - trade thesis invalidated, cut immediately

Signals Detected (3):
• [STRUCTURE] Price broke below EMA20 (3918.50) - structure invalid
• [MOMENTUM] MACD histogram flipped negative (-0.0042) - momentum reversed
• [VOLATILITY] Volatility spike against position: 12.50 (2.5x ATR) - regime shift
```

### Alert Cooldown

- **15 minutes** minimum between alerts for the same position
- Prevents alert spam while position is being managed

---

## 🔍 How It Works

### 1. Position Monitoring

The `LossCutMonitor` runs every **60 seconds** (integrated with `check_positions`):

1. Fetches all open MT5 positions
2. Filters for **losing positions** (unrealized R ≤ -0.3R)
3. Analyzes each position using `LossCutDetector`
4. Sends Telegram alerts for WARNING/CAUTION/CRITICAL signals
5. Optionally auto-executes cuts (if `AUTO_CUT_ENABLED=1`)

### 2. Analysis Process

For each losing position:

```python
analysis = detector.analyze_loss_cut(
    direction="buy",
    entry_price=3925.0,
    entry_time=datetime(2025, 10, 6, 10, 30),
    current_price=3918.5,
    current_sl=3915.0,
    features={
        "rsi": 42,
        "ema20": 3920.0,
        "adx": 18,
        "macd_hist": -0.0042,
        "atr_14": 5.0,
        ...
    },
    bars=ohlcv_dataframe,  # Last 50 M15 bars
    trade_type="intraday",
    daily_pnl_pct=-0.02  # -2% daily P&L
)
```

### 3. Action Execution (if auto-cut enabled)

**Tighten SL**:
- Calculates new SL = max(breakeven, current_price - 0.5×ATR) for longs
- Only moves SL in profitable direction (up for longs, down for shorts)
- Sends MT5 `TRADE_ACTION_SLTP` request

**Cut 50%**:
- Closes half the position volume
- If volume < 0.01 lots, closes full position instead

**Cut Full**:
- Closes entire position immediately
- Comment: "Loss cut: {rationale}"

---

## 📊 Database Logging

All loss cut signals are logged to `JournalRepo`:

```python
journal.log_event(
    event_type="loss_cut_signal",
    symbol="XAUUSD",
    ticket=123456,
    details={
        "urgency": "critical",
        "strikes": 3,
        "action": "cut_full",
        "confidence": 0.87,
        "signal_count": 3,
        "executed": True
    }
)
```

### Analysis History

Track loss cut analysis over time:

```python
# Get latest analysis for a position
analysis = loss_cut_monitor.get_loss_cut_analysis(ticket=123456)

# Get full history
history = loss_cut_monitor.get_loss_cut_history(ticket=123456)
```

---

## 🧪 Testing

Run the test suite:

```bash
python test_loss_cut_detector.py
```

**Tests include**:
- Structure break detection (BUY/SELL)
- Momentum failure detection
- Volatility spike detection
- Confluence breakdown
- Time-based invalidation
- Risk limit breaches
- 3-Strikes Rule logic
- SL tightening calculations
- Alert message formatting

---

## 🛡️ Safety Features

### 1. **Alert-Only by Default**
- `AUTO_CUT_ENABLED=0` by default
- Sends Telegram alerts but doesn't execute cuts
- Trader reviews and decides manually

### 2. **Minimum Loss Threshold**
- Only monitors positions with ≤ **-0.3R** loss
- Avoids premature exits on minor drawdowns

### 3. **Alert Cooldown**
- 15-minute minimum between alerts for same position
- Prevents alert spam

### 4. **Confidence Scoring**
- Each loss cut signal has confidence score (0-1.0)
- Based on signal severity, strikes, and loss depth

### 5. **SL Protection**
- SL tightening only moves SL in profitable direction
- Never widens SL or moves it against position

---

## 💡 Pro Tips

### 1. **Use Alerts First**
Start with `AUTO_CUT_ENABLED=0` to:
- Learn how the system detects loss cut signals
- Calibrate thresholds to your trading style
- Build trust in the system

### 2. **Adjust Timeouts**
Customize timeouts based on your strategy:
- Scalpers: 10-15 minutes
- Day traders: 2-4 hours
- Swing traders: 6-12 hours

### 3. **Monitor Confluence**
If you enter with 5+ indicators, increase `min_confluence_indicators`:
```python
min_confluence_indicators=5
```

### 4. **Review Loss Cut History**
After closed trades, review loss cut history:
```python
history = loss_cut_monitor.get_loss_cut_history(ticket)
for analysis in history:
    print(f"{analysis.timestamp}: {analysis.strikes} strikes, {analysis.action}")
```

### 5. **Combine with Exit Monitor**
- **Exit Monitor**: Protects profits on winning trades
- **Loss Cut Monitor**: Cuts losses on losing trades
- Together: Complete position management system

---

## 📈 Example Scenarios

### Scenario 1: Structure Break (CRITICAL)

```
Position: BUY XAUUSD @ 3925, SL 3915, TP 3945
Current: 3917 (-0.8R)

Signals:
✅ STRUCTURE: Price broke below EMA20 (3920)
✅ MOMENTUM: ADX dropped to 18 (below 20)
✅ VOLATILITY: 2.3x ATR bearish candle

Strikes: 3/7 → CRITICAL
Action: Cut Full Position
Rationale: Structure + momentum + volatility all broken
```

### Scenario 2: Confluence Breakdown (CAUTION)

```
Position: SELL EURUSD @ 1.0850, SL 1.0870, TP 1.0820
Current: 1.0862 (-0.6R)

Signals:
✅ CONFLUENCE: 3/4 indicators now against position
✅ MOMENTUM: MACD histogram flipped positive

Strikes: 2/7 → CAUTION
Action: Cut 50% or Tighten SL
Rationale: Entry confluence broken, but structure still intact
```

### Scenario 3: Time Expiration (WARNING)

```
Position: BUY BTCUSD @ 95000, SL 94500, TP 96000
Current: 94800 (-0.4R)
Time in trade: 5 hours (intraday timeout: 4 hours)

Signals:
✅ TIME: Trade stagnant for 5 hours with -0.4R loss

Strikes: 1/7 → WARNING
Action: Tighten SL
Rationale: Trade not performing, reduce risk
```

---

## 🔒 Summary

### When to Cut a Losing Trade

1. **The reason for entry is invalidated** (structure/momentum broken)
2. **Market prints a volatility regime shift** against you
3. **Trade stagnates too long** without progress
4. **You reach your daily or position risk limit**

### The Golden Rule

**When any 2-3 of these conditions align → exit.**
**No hesitation. No "hope." Just execution.**

---

## 📚 Related Documentation

- [Exit Monitor Guide](EXIT_MONITOR_GUIDE.md) - Profit protection system
- [Trade Monitor Guide](../infra/trade_monitor.py) - Trailing stops
- [Risk Management](../app/engine/risk_model.py) - Position sizing

---

**Remember**: Professional traders don't lose because they're wrong. They lose because they stay wrong too long. The Loss Cut Monitor ensures you exit systematically when conditions change.
