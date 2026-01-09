# Loss Cut Monitor - Implementation Summary

## 📋 Overview

The **Loss Cut Monitor** is a professional-grade systematic loss management system that implements the institutional framework: **"Cut losses when the reason for entry is no longer true."**

This system complements the existing **Exit Monitor** (profit protection) to provide complete position management:
- **Exit Monitor**: Protects profits on winning trades
- **Loss Cut Monitor**: Cuts losses on losing trades systematically

---

## 🎯 What Was Implemented

### 1. Core Detector (`infra/loss_cut_detector.py`)

**7-Category Analysis Framework**:
1. **Structural Invalidation**: EMA breaks, swing low/high breaks
2. **Momentum Failure**: ADX weak, RSI divergence, MACD flip
3. **Volatility Expansion**: 2× ATR spikes, Bollinger Band expansion
4. **Confluence Breakdown**: 67%+ indicators turn against position
5. **Time-Based Invalidation**: Scalp (15min), Intraday (4hr), Swing (8hr)
6. **Risk/Equity Limits**: Max -1.5R per trade, 5% daily loss
7. **Sentiment/News Shock**: ATR doubling (proxy for news events)

**3-Strikes Rule**:
- **1 strike** (WARNING) → Tighten SL
- **2 strikes** (CAUTION) → Tighten SL or Cut 50%
- **3+ strikes** (CRITICAL) → Cut 50% or Cut Full

**Key Classes**:
```python
class LossCutDetector:
    def analyze_loss_cut(
        direction, entry_price, entry_time, current_price, current_sl,
        features, bars, trade_type, daily_pnl_pct
    ) -> LossCutAnalysis
```

**Output**:
```python
@dataclass
class LossCutAnalysis:
    urgency: LossCutUrgency  # NONE, WARNING, CAUTION, CRITICAL
    strikes: int  # 0-7
    confidence: float  # 0.0-1.0
    signals: List[LossCutSignal]
    action: str  # "hold", "tighten_sl", "cut_50", "cut_full"
    rationale: str
    unrealized_r: float
    time_in_trade_minutes: int
```

---

### 2. Live Monitor (`infra/loss_cut_monitor.py`)

**Integration with MT5**:
- Monitors all open positions every 60 seconds
- Filters for losing positions (≤ -0.3R)
- Analyzes using `LossCutDetector`
- Sends Telegram alerts
- Optionally auto-executes cuts

**Key Features**:
- **Alert Cooldown**: 15 minutes minimum between alerts
- **Analysis History**: Tracks all loss cut signals per position
- **Database Logging**: Logs to `JournalRepo` for post-trade analysis
- **Safety First**: Alert-only by default (`AUTO_CUT_ENABLED=0`)

**Execution Actions**:
1. **Tighten SL**: Moves SL to max(breakeven, current_price - 0.5×ATR)
2. **Cut 50%**: Closes half the position (or full if volume < 0.01)
3. **Cut Full**: Closes entire position immediately

---

### 3. Telegram Integration (`chatgpt_bot.py`)

**New Functions**:
```python
async def check_loss_cuts_async(app: Application):
    """Check for loss cut signals and send Telegram alerts"""
```

**Integrated into `check_positions()`**:
```python
async def check_positions(app: Application):
    # 1. Check trailing stops
    await check_trailing_stops_async()
    
    # 2. Check exit signals (profit protection)
    await check_exit_signals_async(app)
    
    # 3. Check loss cuts (loss management) ← NEW
    await check_loss_cuts_async(app)
```

**Alert Format**:
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

---

### 4. Documentation

**Created**:
- `docs/LOSS_CUT_GUIDE.md`: Comprehensive user guide (3,000+ words)
- `docs/LOSS_CUT_IMPLEMENTATION.md`: This file (implementation summary)

**Covers**:
- 7-category framework explanation with examples
- 3-Strikes Rule decision logic
- Configuration and thresholds
- Telegram alert format
- Safety features
- Pro tips and best practices
- Example scenarios

---

### 5. Test Suite (`test_loss_cut_detector.py`)

**10 Comprehensive Tests**:
1. ✅ Structure Break (BUY)
2. ✅ Momentum Failure
3. ✅ Volatility Spike
4. ✅ Confluence Breakdown
5. ✅ Time Expiration
6. ✅ Risk Limits
7. ✅ 3-Strikes Rule (CRITICAL)
8. ✅ SELL Position Loss Cut
9. ✅ No Loss Cut (Profitable Position)
10. ✅ Confidence Scoring

**Run Tests**:
```bash
python test_loss_cut_detector.py
```

---

## 🔧 Configuration

### Environment Variables (`.env`)

```bash
# Loss Cut Monitor Settings
AUTO_CUT_ENABLED=0  # 0 = alerts only, 1 = auto-execute (use with caution)
```

### Thresholds (Customizable in `infra/loss_cut_detector.py`)

```python
LossCutDetector(
    # Structure
    structure_break_confirm_bars=1,
    
    # Momentum
    adx_weak_threshold=20.0,
    rsi_failure_threshold=10.0,
    macd_flip_confirm=True,
    
    # Volatility
    atr_spike_multiplier=2.0,
    bb_expansion_threshold=1.5,
    
    # Confluence
    min_confluence_indicators=3,
    confluence_break_threshold=0.67,
    
    # Time
    scalp_timeout=15,  # minutes
    intraday_timeout=240,  # 4 hours
    swing_timeout=480,  # 8 hours
    
    # Risk
    max_loss_r=-1.5,
    max_daily_loss_pct=0.05,
    
    # 3-Strikes Rule
    strikes_for_warning=1,
    strikes_for_caution=2,
    strikes_for_critical=3,
)
```

---

## 🚀 Usage

### 1. Start the Bot

```bash
python chatgpt_bot.py
```

**Initialization Log**:
```
🤖 Starting ChatGPT Telegram Bot with Background Monitoring...
  → Creating TradeMonitor...
✅ TradeMonitor initialized successfully
  → Creating ExitMonitor...
✅ ExitMonitor initialized (auto_exit=OFF - alerts only)
  → Creating LossCutMonitor...
✅ LossCutMonitor initialized (auto_cut=OFF - alerts only)

✅ Background monitoring started:
   → Position Monitor: every 60s (includes trailing stops)
   → TradeMonitor: Active (momentum-aware trailing stops)
   → ExitMonitor: Active (profit protection & exit signals)
   → LossCutMonitor: Active (systematic loss management - 3-Strikes Rule)
```

### 2. Receive Alerts

When a losing position triggers loss cut signals, you'll receive a Telegram alert with:
- Urgency level (WARNING/CAUTION/CRITICAL)
- Number of strikes (categories triggered)
- Recommended action
- Confidence score
- Detailed rationale
- List of signals detected

### 3. Review and Act

**Alert-Only Mode** (default):
- Review the alert
- Check your MT5 platform
- Decide whether to cut manually

**Auto-Cut Mode** (advanced):
- Set `AUTO_CUT_ENABLED=1` in `.env`
- System will execute cuts automatically
- Still receive alerts for confirmation

### 4. Post-Trade Analysis

Review loss cut history for closed positions:
```python
from infra.loss_cut_monitor import LossCutMonitor

# Get analysis history
history = loss_cut_monitor.get_loss_cut_history(ticket=123456)

for analysis in history:
    print(f"{analysis.timestamp}: {analysis.strikes} strikes, {analysis.action}")
```

---

## 🛡️ Safety Features

### 1. **Alert-Only by Default**
- `AUTO_CUT_ENABLED=0` by default
- Trader reviews and decides manually
- Build trust before enabling auto-execution

### 2. **Minimum Loss Threshold**
- Only monitors positions with ≤ **-0.3R** loss
- Avoids premature exits on minor drawdowns

### 3. **Alert Cooldown**
- 15-minute minimum between alerts for same position
- Prevents alert spam

### 4. **Confidence Scoring**
- Each signal has confidence score (0-1.0)
- Based on signal severity, strikes, and loss depth

### 5. **SL Protection**
- SL tightening only moves SL in profitable direction
- Never widens SL or moves it against position

### 6. **Database Logging**
- All signals logged to `JournalRepo`
- Enables post-trade analysis and system tuning

---

## 📊 Integration with Existing Systems

### Complete Position Management Stack

```
┌─────────────────────────────────────────────────────┐
│                 Position Lifecycle                  │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  1. Entry (ChatGPT + Strategy Logic)                │
│     - Market orders                                 │
│     - Pending orders (BUY/SELL LIMIT/STOP)          │
│     - OCO bracket orders                            │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  2. Monitoring (TradeMonitor)                       │
│     - Momentum-aware trailing stops                 │
│     - Runs every 60 seconds                         │
└─────────────────────────────────────────────────────┘
                         │
                ┌────────┴────────┐
                ▼                 ▼
┌───────────────────────┐  ┌───────────────────────┐
│  3a. Profit Protection│  │  3b. Loss Management  │
│  (ExitMonitor)        │  │  (LossCutMonitor)     │
│  - Phase 1: Early Warn│  │  - 1 Strike: WARNING  │
│  - Phase 2: Exhaustion│  │  - 2 Strikes: CAUTION │
│  - Phase 3: Breakdown │  │  - 3+ Strikes: CRITICAL│
│  - Tighten stops      │  │  - Tighten/Cut 50%/Full│
└───────────────────────┘  └───────────────────────┘
                │                 │
                └────────┬────────┘
                         ▼
┌─────────────────────────────────────────────────────┐
│  4. Exit                                            │
│     - Trailing stop hit                             │
│     - Exit signal executed                          │
│     - Loss cut executed                             │
│     - Take profit hit                               │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  5. Logging (JournalRepo)                           │
│     - Trade outcome                                 │
│     - Exit signals history                          │
│     - Loss cut signals history                      │
│     - Performance metrics                           │
└─────────────────────────────────────────────────────┘
```

---

## 💡 Key Differences: Exit Monitor vs Loss Cut Monitor

| Feature | Exit Monitor | Loss Cut Monitor |
|---------|-------------|------------------|
| **Purpose** | Protect profits | Cut losses systematically |
| **Monitors** | Profitable positions (≥ +0.5R) | Losing positions (≤ -0.3R) |
| **Framework** | 3-Phase Exit (Early/Exhaustion/Breakdown) | 7-Category + 3-Strikes Rule |
| **Indicators** | 20+ trend exhaustion indicators | Structure, momentum, volatility, confluence, time, risk, sentiment |
| **Actions** | Tighten stops → Exit | Tighten SL → Cut 50% → Cut Full |
| **Goal** | Exit before reversal | Exit when thesis invalidated |
| **Urgency** | LOW → MEDIUM → HIGH → CRITICAL | WARNING → CAUTION → CRITICAL |

**Together**: Complete position management system for both winning and losing trades.

---

## 📈 Example Workflow

### Scenario: XAUUSD Long Trade Goes Wrong

**Entry**:
```
BUY XAUUSD @ 3925
SL: 3915 (10 points = 1R)
TP: 3945 (20 points = 2R)
```

**T+15 minutes**: Price drops to 3920 (-0.5R)
- **LossCutMonitor**: Monitoring starts (≤ -0.3R threshold)
- No signals yet

**T+30 minutes**: Price drops to 3918 (-0.7R)
- **Signal 1**: Price breaks below EMA20 (3920) → STRUCTURE ⚠️
- **Alert**: "WARNING: 1 strike - tighten SL"
- **Action**: Trader tightens SL to 3918 (breakeven)

**T+45 minutes**: Price drops to 3912 (-1.3R)
- **Signal 2**: ADX drops to 15 → MOMENTUM ⚠️
- **Signal 3**: Large bearish candle (2.5× ATR) → VOLATILITY ⚠️
- **Alert**: "CRITICAL: 3 strikes - cut full position immediately"
- **Rationale**: Structure + momentum + volatility all broken
- **Action**: Trader exits at 3912 (saved 3 points vs SL)

**Result**:
- Loss: -13 points (-1.3R) vs potential -15 points (-1.5R)
- **Saved**: 2 points (13% of risk)
- **More importantly**: Exited systematically when thesis invalidated, not when SL hit

---

## 🔍 Monitoring and Debugging

### Check Initialization

```bash
# Bot startup logs
✅ LossCutMonitor initialized (auto_cut=OFF - alerts only)
   → LossCutMonitor: Active (systematic loss management - 3-Strikes Rule)
```

### Check Runtime Logs

```bash
# Loss cut signals detected
Loss cut signal: XAUUSD ticket=123456 | Urgency=critical | Strikes=3/7 | Action=cut_full | Confidence=0.87 | Loss=-1.30R

# Telegram alerts sent
📤 Loss cut alert sent for ticket 123456
```

### Check Database Logs

```python
from infra.journal_repo import JournalRepo

journal = JournalRepo()
events = journal.get_events(event_type="loss_cut_signal")

for event in events:
    print(f"{event['timestamp']}: {event['symbol']} - {event['details']}")
```

---

## 🧪 Testing

### Run Test Suite

```bash
python test_loss_cut_detector.py
```

**Expected Output**:
```
============================================================
LOSS CUT DETECTOR TEST SUITE
============================================================

=== Test 1: Structure Break (BUY) ===
[PASS] - Structure Break Detection (BUY)
    Strikes: 2, Urgency: caution, Action: tighten_sl

=== Test 2: Momentum Failure ===
[PASS] - Momentum Failure Detection
    Strikes: 2, Urgency: caution, ADX: 15

... (8 more tests) ...

============================================================
TEST SUMMARY
============================================================
Passed: 10/10
Failed: 0/10

ALL TESTS PASSED!
```

---

## 📚 Related Files

### Core Implementation
- `infra/loss_cut_detector.py`: 7-category detector logic
- `infra/loss_cut_monitor.py`: Live monitoring and MT5 integration
- `chatgpt_bot.py`: Telegram integration

### Documentation
- `docs/LOSS_CUT_GUIDE.md`: User guide
- `docs/LOSS_CUT_IMPLEMENTATION.md`: This file

### Testing
- `test_loss_cut_detector.py`: Test suite

### Related Systems
- `infra/exit_monitor.py`: Profit protection system
- `infra/trade_monitor.py`: Trailing stops
- `infra/journal_repo.py`: Database logging

---

## 🎓 Next Steps

### 1. **Start with Alerts Only**
- Use `AUTO_CUT_ENABLED=0` (default)
- Learn how the system detects signals
- Build confidence in the framework

### 2. **Review and Tune**
- Check alert accuracy over 1-2 weeks
- Adjust thresholds if needed (e.g., `adx_weak_threshold`, `atr_spike_multiplier`)
- Review loss cut history for closed trades

### 3. **Enable Auto-Cut (Optional)**
- Once confident, set `AUTO_CUT_ENABLED=1`
- Start with small position sizes
- Monitor closely for first few trades

### 4. **Analyze Performance**
- Compare trades with/without loss cut signals
- Calculate average loss saved per trade
- Refine thresholds based on data

---

## 🔒 Summary

The **Loss Cut Monitor** provides:

✅ **Systematic loss management** based on professional criteria  
✅ **7-category analysis** covering all aspects of trade invalidation  
✅ **3-Strikes Rule** for clear decision-making  
✅ **Telegram alerts** with detailed rationale  
✅ **Safety-first approach** (alerts by default)  
✅ **Complete integration** with existing systems  
✅ **Comprehensive testing** and documentation  

**Remember**: Professional traders don't lose because they're wrong. They lose because they stay wrong too long. The Loss Cut Monitor ensures you exit systematically when conditions change.

---

**Implementation Complete** ✅
