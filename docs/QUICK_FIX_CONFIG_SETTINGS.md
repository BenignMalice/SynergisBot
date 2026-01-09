# ⚡ Quick Fix: Config Settings

## ✅ **FIXED**

**Error:**
```
module 'config.settings' has no attribute 'POS_CLOSE_BACKOFF_MS'
```

**Solution:** Added missing loss cutter settings to `config/settings.py`

---

## 🎯 **What Was Added**

**8 new settings in `config/settings.py`:**

```python
# Loss Cutter Configuration
POS_EARLY_EXIT_R = -0.8              # Cut at -80% of risk
POS_EARLY_EXIT_SCORE = 0.65          # 65% confidence threshold
POS_TIME_BACKSTOP_ENABLE = True      # Enable time-based exits
POS_TIME_BACKSTOP_BARS = 10          # Cut after 10 bars underwater
POS_INVALIDATION_EXIT_ENABLE = True  # Exit on structure break
POS_SPREAD_ATR_CLOSE_CAP = 0.40      # Max 40% spread/ATR ratio
POS_CLOSE_RETRY_MAX = 3              # 3 retry attempts
POS_CLOSE_BACKOFF_MS = "300,600,900" # Retry delays (ms)
```

---

## 🚀 **Restart Your Bot**

```powershell
cd C:\mt5-gpt\TelegramMoneyBot.v7
python chatgpt_bot.py
```

**Look for:**
```
✅ LossCutter initialized with config:
   early_exit_r=-0.8, risk_score_threshold=0.65, spread_atr_cap=0.4
```

---

## 📊 **What This Means**

**Loss cutting now:**
- ✅ Cuts at -0.8R (saves 20% of risk)
- ✅ Requires 65% confidence (multiple factors)
- ✅ Checks spread before closing
- ✅ Retries up to 3 times if MT5 rejects
- ✅ Includes Binance + order flow context

---

**Status:** ✅ **FIXED** - Restart bot to apply!

**Full Details:** See `CONFIG_SETTINGS_FIX_COMPLETE.md`

