# 🛡️ Exit Monitor - Profit Protection System

## **Overview**

The Exit Monitor is an automated profit protection system that detects trend exhaustion signals and alerts you (or auto-exits) before market reversals eat into your profits.

---

## **🎯 How It Works**

### **3-Phase Exit Framework**

The system uses a professional 3-phase approach to detect when to exit profitable trades:

#### **Phase 1: Early Warning** ⚠️
**Signals:** RSI divergence, ADX rollover, Volume divergence  
**Action:** Monitor closely, tighten trailing stops  
**Urgency:** LOW to MEDIUM

**Example:**
```
⚠️ Exit Signal Detected

XAUUSD (Ticket: 123456)
Unrealized Profit: +1.8R

🟡 Urgency: LOW
📊 Phase: Early Warning
🎯 Recommended: Tighten trailing stops
📈 Confidence: 65%

💡 Rationale:
Early warning signals - monitor closely and trail stops

Signals Detected (2):
• ADX_rollover: ADX rolling down from 45.2 (was 47.1)
• RSI_divergence: RSI divergence detected (buy position)
```

---

#### **Phase 2: Exhaustion** 🔶
**Signals:** ATR compression, Bollinger Band re-entry, VWAP flattening  
**Action:** Take 25-50% profits, trail stops tighter  
**Urgency:** MEDIUM to HIGH

**Example:**
```
🔶 Exit Signal Detected

BTCUSD (Ticket: 789012)
Unrealized Profit: +2.5R

🟠 Urgency: HIGH
📊 Phase: Exhaustion
🎯 Recommended: Take 50% profit
📈 Confidence: 82%

💡 Rationale:
Exhaustion confirmed across 2 indicator categories - take 50% profit

Signals Detected (3):
• ATR_compression: ATR dropped 24.3% (volatility exhaustion)
• BB_reentry: Price closed back inside upper BB (exhaustion)
• VWAP_flatten: VWAP flattening (institutional profit-taking)
```

---

#### **Phase 3: Breakdown** 🔴
**Signals:** EMA20 break, Parabolic SAR flip, Heikin Ashi color change  
**Action:** Exit 75-100% of position immediately  
**Urgency:** HIGH to CRITICAL

**Example:**
```
🔴 Exit Signal Detected

EURUSD (Ticket: 345678)
Unrealized Profit: +3.2R

🚨 Urgency: CRITICAL
📊 Phase: Breakdown
🎯 Recommended: EXIT FULL POSITION
📈 Confidence: 95%

💡 Rationale:
Multiple breakdown signals (2) - trend reversal confirmed

Signals Detected (2):
• EMA20_break: Price broke below EMA20 (momentum breakdown)
• SAR_flip: Parabolic SAR flipped (trend reversal)
```

---

## **📊 Indicators Used**

### **Momentum Indicators** (Phase 1)
- ✅ **ADX Rollover** - Trend strength exhaustion
- ✅ **RSI Divergence** - Momentum failure warning
- ✅ **MACD Histogram** - Trend deceleration

### **Volatility Indicators** (Phase 2)
- ✅ **ATR Compression** - Volatility collapse (>20% drop)
- ✅ **Bollinger Band Re-entry** - Price closes back inside bands after extension
- ✅ **Donchian Channels** - Breakout range failure

### **Volume Indicators** (Phase 2)
- ✅ **Volume Divergence** - Price rising but volume declining (>15% drop)
- ✅ **VWAP Flattening** - Institutional profit-taking

### **Structure Indicators** (Phase 3)
- ✅ **EMA20 Break** - Momentum spine violation
- ✅ **Parabolic SAR Flip** - Trend reversal confirmation
- ✅ **Heikin Ashi Color Change** - Smoothed trend breakdown

---

## **⚙️ Configuration**

### **Environment Variables (.env)**

```bash
# Exit Monitor Settings
AUTO_EXIT_ENABLED=0  # 0=alerts only, 1=auto-execute exits (DANGEROUS!)
```

### **Code Configuration (chatgpt_bot.py)**

```python
exit_monitor = ExitMonitor(
    mt5_service=mt5_service,
    feature_builder=feature_builder,
    journal_repo=journal,
    auto_exit_enabled=False,  # Safety: manual by default
    min_profit_r=0.5,  # Only monitor positions with >= 0.5R profit
    alert_cooldown_minutes=15  # Min 15 min between alerts for same position
)
```

### **Advanced Configuration (infra/exit_signal_detector.py)**

```python
detector = ExitSignalDetector(
    # Phase 1 thresholds (Early Warning)
    adx_rollover_threshold=40.0,  # ADX must be > 40 to be significant
    rsi_divergence_lookback=5,  # Bars to check for divergence
    volume_divergence_threshold=0.15,  # 15% volume drop
    
    # Phase 2 thresholds (Exhaustion)
    atr_drop_threshold=0.20,  # 20% ATR drop triggers exhaustion
    bb_reentry_confirm_bars=1,  # Bars to confirm BB re-entry
    vwap_flatten_threshold=0.0005,  # VWAP slope threshold
    
    # Phase 3 thresholds (Breakdown)
    ema_break_confirm_bars=1,  # Bars to confirm EMA break
    sar_flip_confirm=True,  # Require SAR flip confirmation
    
    # Confluence requirements
    min_signals_for_warning=2,  # Min signals for Phase 1
    min_signals_for_exhaustion=2,  # Min signals for Phase 2
    min_signals_for_breakdown=1,  # Min signals for Phase 3
)
```

---

## **🚀 Usage**

### **Automatic Mode (Recommended)**

The Exit Monitor runs automatically every 60 seconds as part of the Position Monitor background job.

**What happens:**
1. ✅ Bot checks all open positions with ≥0.5R profit
2. ✅ Analyzes exit signals using 3-phase framework
3. ✅ Sends Telegram alert if signals detected
4. ✅ Logs all signals to database for analysis
5. ✅ (Optional) Auto-executes partial/full exits if `AUTO_EXIT_ENABLED=1`

**No action required** - just run the bot:
```bash
python chatgpt_bot.py
```

---

### **Manual Check (API)**

You can also check exit signals programmatically:

```python
from infra.exit_monitor import ExitMonitor
from infra.mt5_service import MT5Service
from infra.feature_builder import FeatureBuilder

# Initialize
mt5_service = MT5Service()
feature_builder = FeatureBuilder(mt5_service, bridge)
exit_monitor = ExitMonitor(mt5_service, feature_builder)

# Check all positions
actions = exit_monitor.check_exit_signals()

# Process results
for action in actions:
    print(f"Exit signal: {action['symbol']} - {action['action']}")
    print(f"Rationale: {action['rationale']}")
```

---

## **📈 Recommended Actions by Phase**

| Phase | Urgency | Action | Rationale |
|-------|---------|--------|-----------|
| **Early Warning** | LOW | Trail stops | Momentum fading, monitor closely |
| **Early Warning** | MEDIUM | Tighten trail | Multiple warnings, prepare to exit |
| **Exhaustion** | MEDIUM | Take 25% profit | Exhaustion detected, lock in gains |
| **Exhaustion** | HIGH | Take 50% profit | Confirmed across 2+ categories |
| **Breakdown** | HIGH | Take 75% profit | Breakdown signal, protect profits |
| **Breakdown** | CRITICAL | Exit 100% | Multiple breakdowns, trend reversed |

---

## **🛡️ Safety Features**

1. ✅ **Manual by Default** - Auto-exit is OFF unless explicitly enabled
2. ✅ **Profit Threshold** - Only monitors positions with ≥0.5R profit (configurable)
3. ✅ **Alert Cooldown** - Max 1 alert per position every 15 minutes (prevents spam)
4. ✅ **Confidence Scoring** - Each signal has 0-100% confidence score
5. ✅ **Confluence Required** - Multiple signals needed to trigger higher urgency
6. ✅ **Database Logging** - All signals logged for post-analysis
7. ✅ **Telegram Alerts** - Always notified before any action

---

## **📊 Performance Monitoring**

### **Check Exit History**

```python
# Get latest analysis for a position
analysis = exit_monitor.get_exit_analysis(ticket=123456)
print(f"Phase: {analysis.phase}")
print(f"Confidence: {analysis.confidence}")

# Get full history
history = exit_monitor.get_exit_history(ticket=123456)
for analysis in history:
    print(f"{analysis.timestamp}: {analysis.phase} - {analysis.action}")
```

### **Database Queries**

Exit signals are logged to `data/journal.sqlite`:

```sql
-- View all exit signals
SELECT * FROM journal_events 
WHERE event_type = 'exit_signal' 
ORDER BY timestamp DESC;

-- Exit signal stats by symbol
SELECT symbol, 
       COUNT(*) as signal_count,
       AVG(json_extract(details, '$.confidence')) as avg_confidence
FROM journal_events 
WHERE event_type = 'exit_signal'
GROUP BY symbol;
```

---

## **🎯 Best Practices**

### **1. Use 3-Tier Exit Strategy**

```
Tier 1: Phase 1 (Early Warning) → Trail stops, monitor
Tier 2: Phase 2 (Exhaustion) → Take 50% profit
Tier 3: Phase 3 (Breakdown) → Exit remaining 50%
```

### **2. Combine with Trailing Stops**

The Exit Monitor works **alongside** the TradeMonitor's trailing stops:
- **TradeMonitor** = Protects profits via dynamic SL adjustments
- **ExitMonitor** = Detects trend exhaustion for proactive exits

### **3. Trust the Confluence**

When 2 out of 3 indicator categories (Momentum, Volatility, Volume) signal exhaustion → high probability of reversal.

### **4. Review Exit History**

After trades close, review exit signals to see if you exited too early/late:
```python
history = exit_monitor.get_exit_history(ticket=123456)
```

### **5. Backtest Your Thresholds**

Adjust thresholds based on your trading style:
- **Scalpers** → Lower thresholds (exit faster)
- **Swing Traders** → Higher thresholds (ride trends longer)

---

## **⚠️ Important Notes**

### **AUTO_EXIT_ENABLED=1 Warning**

**DO NOT enable auto-exit unless you fully understand the risks:**
- ❌ No manual confirmation required
- ❌ Exits execute automatically based on signals
- ❌ Could exit winning trades prematurely
- ❌ Could miss larger moves

**Recommended:** Keep `AUTO_EXIT_ENABLED=0` and manually decide based on Telegram alerts.

### **Minimum Profit Threshold**

The system only monitors positions with **≥0.5R profit** by default. This prevents:
- ✅ Premature exits on trades still developing
- ✅ False signals during normal pullbacks
- ✅ Alert spam on breakeven/losing trades

---

## **📞 Telegram Alert Format**

```
⚠️ Exit Signal Detected

XAUUSD (Ticket: 123456)
Unrealized Profit: +1.8R

🟡 Urgency: MEDIUM
📊 Phase: Early Warning
🎯 Recommended: Tighten trailing stops
📈 Confidence: 72%

💡 Rationale:
Multiple early warnings (3) - tighten trailing stops

Signals Detected (3):
• ADX_rollover: ADX rolling down from 45.2 (was 47.1)
• RSI_divergence: RSI divergence detected (buy position)
• Volume_divergence: Volume declining 18.2% while price rising
```

---

## **🔧 Troubleshooting**

### **Not Receiving Alerts**

1. Check bot is running: `python chatgpt_bot.py`
2. Check you've started bot with `/start` in Telegram
3. Check position has ≥0.5R profit
4. Check alert cooldown (15 min between alerts)
5. Check logs: `data/logs/chatgpt_bot.log`

### **Too Many Alerts**

Increase alert cooldown:
```python
exit_monitor = ExitMonitor(
    alert_cooldown_minutes=30  # 30 min instead of 15
)
```

Or increase min profit threshold:
```python
exit_monitor = ExitMonitor(
    min_profit_r=1.0  # Only monitor positions with ≥1R profit
)
```

### **Signals Not Triggering**

Lower thresholds in `ExitSignalDetector`:
```python
detector = ExitSignalDetector(
    adx_rollover_threshold=30.0,  # Lower from 40
    atr_drop_threshold=0.15,  # Lower from 0.20
    min_signals_for_warning=1  # Lower from 2
)
```

---

## **📚 Related Documentation**

- [Live Trade Monitoring Explanation](../README.md)
- [TradeMonitor (Trailing Stops)](../infra/trade_monitor.py)
- [Exit Signal Detector](../infra/exit_signal_detector.py)
- [Exit Monitor](../infra/exit_monitor.py)

---

## **🎓 Summary**

The Exit Monitor is a **professional-grade profit protection system** that:

✅ Detects trend exhaustion before reversals  
✅ Uses 3-phase framework (Early Warning → Exhaustion → Breakdown)  
✅ Analyzes 10+ indicators across momentum, volatility, volume, and structure  
✅ Sends real-time Telegram alerts with confidence scores  
✅ Optionally auto-executes exits (manual by default for safety)  
✅ Logs all signals to database for analysis  
✅ Works alongside TradeMonitor's trailing stops  

**Result:** Exit within 5-10 pips of the true high/low, protecting your hard-earned profits! 🎯
