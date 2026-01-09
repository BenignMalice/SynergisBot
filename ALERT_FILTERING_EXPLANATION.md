# Alert Filtering Explanation

**Date:** 2025-11-30  
**Issue:** Alerts detected but not sent to Discord

---

## ✅ **System is Working Correctly**

The Discord Alert Dispatcher is working as designed. Alerts are being **detected** but **filtered out** before sending because they don't meet the minimum confidence threshold.

---

## 📊 **Current Situation**

From your logs:
- **BB_SQUEEZE**: 65% confidence < 70% threshold → **Filtered**
- **INSIDE_BAR**: 60% confidence < 70% threshold → **Filtered**
- **EQUAL_HIGHS**: 45% confidence < 70% threshold → **Filtered**

All 3 alerts were detected but filtered due to low confidence scores.

---

## ⚙️ **Configuration**

The minimum confidence threshold is set in `config/discord_alerts_config.json`:

```json
{
  "min_confidence": 70,
  ...
}
```

This means only alerts with **70% or higher confidence** will be sent to Discord.

---

## 🔧 **Solutions**

### **Option 1: Lower the Confidence Threshold**

If you want to receive more alerts (including lower confidence ones), edit `config/discord_alerts_config.json`:

```json
{
  "min_confidence": 60,  // Changed from 70 to 60
  ...
}
```

This would allow:
- ✅ BB_SQUEEZE (65%) - would now be sent
- ✅ INSIDE_BAR (60%) - would now be sent
- ❌ EQUAL_HIGHS (45%) - still filtered

### **Option 2: Keep Current Threshold**

The current threshold (70%) is designed to only send **high-quality alerts**. This reduces noise and ensures you only get actionable signals.

---

## 📈 **Why Confidence Scores Vary**

Confidence is calculated based on:
- **Alert type** (CHOCH/BOS are higher confidence than INSIDE_BAR)
- **H1 trend alignment** (alerts aligned with trend = higher confidence)
- **Session** (London/NY sessions = higher confidence)
- **Volatility state** (expanding volatility = higher confidence)
- **Cross-timeframe confirmation** (M5/M15 alignment = +10% bonus)

Lower confidence alerts (like INSIDE_BAR at 60%) are still valid patterns, but they're less likely to result in profitable trades.

---

## 🎯 **Recommendation**

**Keep the threshold at 70%** for now. The system is working correctly - it's just that the current market conditions are producing lower-confidence signals.

When higher-quality alerts occur (CHOCH, BOS, Order Blocks with good confluence), they will be sent automatically.

---

## ✅ **Status**

- ✅ Webhook is configured correctly
- ✅ Alerts are being detected
- ✅ Filtering is working as designed
- ✅ System is functioning properly

**No action needed** - the system will send alerts when they meet the confidence threshold.

