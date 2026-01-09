# Loss Cut Monitor - Quick Reference Card

## 🚀 Quick Start

### 1. Enable Loss Cut Monitor
Already enabled by default in `chatgpt_bot.py`! Just start the bot:
```bash
python chatgpt_bot.py
```

### 2. Configuration (Optional)
Edit `.env` file:
```bash
# Alert-only mode (default - RECOMMENDED)
AUTO_CUT_ENABLED=0

# Auto-execute mode (advanced - use with caution)
AUTO_CUT_ENABLED=1
```

---

## 📊 The 7 Categories

| # | Category | What It Detects | Example |
|---|----------|----------------|---------|
| 1️⃣ | **Structure** | EMA breaks, swing breaks | Price closes below EMA20 |
| 2️⃣ | **Momentum** | ADX weak, RSI divergence, MACD flip | ADX < 20 |
| 3️⃣ | **Volatility** | 2× ATR spikes, BB expansion | Candle > 2× ATR against you |
| 4️⃣ | **Confluence** | 67%+ indicators turn negative | 3/4 entry indicators now broken |
| 5️⃣ | **Time** | Trade stagnates | Scalp: 15min, Intraday: 4hr, Swing: 8hr |
| 6️⃣ | **Risk** | Max loss limits | -1.5R or 5% daily loss |
| 7️⃣ | **Sentiment** | News/macro shocks | ATR doubles (news event proxy) |

---

## ⚡ The 3-Strikes Rule

| Strikes | Urgency | Action | Meaning |
|---------|---------|--------|---------|
| **1** | ⚠️ WARNING | Tighten SL | Monitor closely |
| **2** | 🟠 CAUTION | Tighten SL or Cut 50% | Reduce exposure |
| **3+** | 🚨 CRITICAL | Cut 50% or Cut Full | Exit immediately |

---

## 📱 Telegram Alert Format

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
CRITICAL: 3 strikes detected - trade thesis invalidated

Signals Detected (3):
• [STRUCTURE] Price broke below EMA20
• [MOMENTUM] MACD histogram flipped negative
• [VOLATILITY] Volatility spike (2.5x ATR)
```

---

## 🎯 When to Cut

### ✅ Cut When:
1. **3+ strikes** detected (CRITICAL urgency)
2. **Structure broken** (price invalidates setup)
3. **Loss exceeds -1.5R** (risk limit)
4. **Daily loss exceeds 5%** (portfolio protection)
5. **Confluence breakdown** (67%+ indicators turn)

### ❌ Don't Cut When:
1. **0-1 strikes** (just monitor)
2. **Position in profit** (use Exit Monitor instead)
3. **Minor drawdown** (< -0.3R)
4. **Single indicator** (wait for confluence)

---

## 🔧 Customization

### Adjust Thresholds
Edit `infra/loss_cut_detector.py`:

```python
LossCutDetector(
    # Momentum
    adx_weak_threshold=20.0,        # Lower = more sensitive
    rsi_failure_threshold=10.0,     # Lower = more sensitive
    
    # Volatility
    atr_spike_multiplier=2.0,       # Lower = more sensitive
    
    # Time
    scalp_timeout=15,               # Shorter = more aggressive
    intraday_timeout=240,           # 4 hours
    swing_timeout=480,              # 8 hours
    
    # Risk
    max_loss_r=-1.5,                # Tighter = more conservative
    max_daily_loss_pct=0.05,        # 5%
)
```

---

## 🧪 Testing

```bash
# Run test suite
python test_loss_cut_detector.py

# Expected: 10/10 tests pass
```

---

## 📚 Full Documentation

- **User Guide**: `docs/LOSS_CUT_GUIDE.md` (3,000+ words)
- **Implementation**: `docs/LOSS_CUT_IMPLEMENTATION.md`
- **This Card**: `docs/LOSS_CUT_QUICK_REFERENCE.md`

---

## 💡 Pro Tips

1. **Start with alerts only** (`AUTO_CUT_ENABLED=0`)
2. **Review alerts for 1-2 weeks** before enabling auto-cut
3. **Adjust timeouts** based on your trading style
4. **Check alert history** in database for post-trade analysis
5. **Combine with Exit Monitor** for complete position management

---

## 🛡️ Safety Features

✅ Alert-only by default  
✅ 15-minute alert cooldown  
✅ Only monitors losing positions (≤ -0.3R)  
✅ Confidence scoring (0-1.0)  
✅ SL only moves in profitable direction  
✅ Database logging for all signals  

---

## 🔍 Monitoring

### Check Logs
```bash
# Main log
tail -f data/logs/chatgpt_bot.log | grep "Loss cut"

# Error log
tail -f data/logs/errors.log
```

### Check Database
```python
from infra.journal_repo import JournalRepo

journal = JournalRepo()
events = journal.get_events(event_type="loss_cut_signal")
```

---

## 🆘 Troubleshooting

### Not Receiving Alerts?
1. Check bot is running: `python chatgpt_bot.py`
2. Check position is losing: ≤ -0.3R
3. Check alert cooldown: 15 min minimum between alerts
4. Check logs: `data/logs/chatgpt_bot.log`

### Too Many Alerts?
1. Increase `min_loss_r` threshold (e.g., `-0.5`)
2. Increase `alert_cooldown_minutes` (e.g., `30`)
3. Adjust sensitivity thresholds (e.g., `adx_weak_threshold=15`)

### False Positives?
1. Review signal categories in alert
2. Adjust specific thresholds (e.g., `atr_spike_multiplier=2.5`)
3. Increase `strikes_for_critical` (e.g., `4`)

---

## 📞 Support

- **Documentation**: `docs/LOSS_CUT_GUIDE.md`
- **Test Suite**: `test_loss_cut_detector.py`
- **Code**: `infra/loss_cut_detector.py`, `infra/loss_cut_monitor.py`

---

**Remember**: Cut losses systematically when the reason for entry is no longer true. No hesitation. No hope. Just execution.
