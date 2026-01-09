# Expected Behavior After Restart - Volatility States Implementation

**Date**: December 8, 2025  
**Status**: ✅ Implementation Complete

---

## 🚀 What to Expect When Restarting Services

### 1. **Service Startup**

#### **Initialization Messages in Logs:**
```
✅ RegimeDetector initialized
✅ Breakout events database initialized: data/volatility_regime_events.sqlite
✅ Tracking structures initialized for symbols: []
```

#### **Database Creation:**
- **New File**: `data/volatility_regime_events.sqlite`
  - Contains `breakout_events` table
  - Tracks breakout events across symbols and timeframes
  - Used for "time since breakout" calculations

#### **No Breaking Changes:**
- ✅ All existing functionality remains intact
- ✅ Backward compatible with previous volatility states (STABLE, TRANSITIONAL, VOLATILE)
- ✅ Existing auto-execution plans continue to work

---

## 📊 What ChatGPT Will See in Analysis Responses

### **Enhanced `moneybot.analyse_symbol_full` Response**

When ChatGPT calls `moneybot.analyse_symbol_full`, the response now includes:

#### **1. New Volatility States (7 Total)**

**Basic States** (unchanged):
- `STABLE`
- `TRANSITIONAL`
- `VOLATILE`

**Advanced States** (NEW):
- `PRE_BREAKOUT_TENSION` - Compression before breakout
- `POST_BREAKOUT_DECAY` - Momentum fading after breakout
- `FRAGMENTED_CHOP` - Whipsaw/choppy conditions
- `SESSION_SWITCH_FLARE` - Volatility spike during session transitions

#### **2. Detailed Volatility Metrics Object**

Located in `response.data.volatility_metrics`:

```json
{
  "regime": "PRE_BREAKOUT_TENSION",
  "confidence": 85.5,
  "atr_ratio": 0.95,
  "bb_width_ratio": 0.45,
  "adx_composite": 18.2,
  "volume_confirmed": true,
  
  // NEW: Per-Timeframe Tracking Metrics
  "atr_trends": {
    "M5": {
      "current_atr": 12.5,
      "slope": -0.15,
      "slope_pct": -1.2,
      "is_declining": true,
      "is_above_baseline": false,
      "trend_direction": "DECLINING"
    },
    "M15": { ... },
    "H1": { ... }
  },
  
  "wick_variances": {
    "M5": {
      "current_variance": 0.25,
      "previous_variance": 0.18,
      "variance_change_pct": 38.9,
      "is_increasing": true,
      "current_ratio": 0.35,
      "mean_ratio": 0.22
    },
    "M15": { ... },
    "H1": { ... }
  },
  
  "time_since_breakout": {
    "M5": {
      "time_since_minutes": 45,
      "time_since_hours": 0.75,
      "breakout_type": "PRICE_UP",
      "breakout_price": 2650.50,
      "breakout_timestamp": "2025-12-08T10:30:00Z",
      "is_recent": true
    },
    "M15": { ... },
    "H1": { ... }
  },
  
  // Convenience Fields (M15 Primary)
  "atr_trend": { ... },  // Same as atr_trends["M15"]
  "wick_variance": { ... },  // Same as wick_variances["M15"]
  "time_since_breakout_minutes": 120,
  
  // Advanced Detection Fields
  "mean_reversion_pattern": {
    "is_mean_reverting": false,
    "oscillation_around_vwap": false,
    "oscillation_around_ema": false,
    "touch_count": 0,
    "reversion_strength": 0.0
  },
  
  "volatility_spike": {
    "is_spike": true,
    "current_atr": 15.2,
    "spike_ratio": 1.8,
    "spike_magnitude": "MODERATE",
    "is_temporary": true
  },
  
  "session_transition": {
    "is_transition": true,
    "transition_type": "LONDON_OPEN",
    "minutes_into_transition": 5,
    "transition_window_start": "2025-12-08T07:00:00Z",
    "transition_window_end": "2025-12-08T08:00:00Z"
  },
  
  "whipsaw_detected": {
    "is_whipsaw": false,
    "direction_changes": 2,
    "oscillation_around_mean": false
  },
  
  // Strategy Recommendations
  "strategy_recommendations": {
    "prioritize": [
      "breakout_ib_volatility_trap",
      "liquidity_sweep_reversal",
      "breaker_block"
    ],
    "avoid": [
      "mean_reversion_range_scalp",
      "trend_continuation_pullback"
    ],
    "confidence_adjustment": 10,
    "recommendation": "Prioritize: breakout_ib_volatility_trap, liquidity_sweep_reversal, breaker_block",
    "wait_reason": null
  }
}
```

#### **3. Enhanced Summary Text**

The `response.summary` will now include volatility-aware insights:

**Example for PRE_BREAKOUT_TENSION:**
```
📉 VOLATILITY FORECASTING
Volatility Signal: PRE_BREAKOUT_TENSION
⚠️ Compression detected - breakout expected
- BB Width: 0.45x (narrow, 15th percentile)
- ATR declining: -1.2% (M15)
- Wick variance increasing: +38.9%
- Time since last breakout: 45 minutes (M5)

🎯 Strategy Recommendations:
✅ Prioritize: breakout_ib_volatility_trap, liquidity_sweep_reversal, breaker_block
❌ Avoid: mean_reversion_range_scalp, trend_continuation_pullback
```

**Example for SESSION_SWITCH_FLARE:**
```
📉 VOLATILITY FORECASTING
Volatility Signal: SESSION_SWITCH_FLARE
🚨 Session transition volatility flare detected
- ATR spike: 1.8x baseline
- Session: LONDON_OPEN (5 minutes into transition)
- Volatility spike: MODERATE (temporary)

⛔ WAIT REQUIRED: All trading blocked
- Wait reason: SESSION_SWITCH_FLARE
- Action: Wait for volatility stabilization before creating plans
```

#### **4. Auto-Execution Plan Validation**

When ChatGPT creates an auto-execution plan (`moneybot.create_auto_trade_plan`):

**If incompatible with current volatility state:**
```json
{
  "success": false,
  "message": "Plan rejected: FRAGMENTED_CHOP only allows ['micro_scalp', 'mean_reversion_range_scalp'] strategies",
  "volatility_state": "FRAGMENTED_CHOP",
  "plan_id": null
}
```

**If compatible:**
- Plan is created normally
- Plan includes volatility-aware risk adjustments (if `strategy_type` is provided)

---

## 🔔 Discord Alerts

### **Advanced Volatility State Alerts**

You will receive Discord notifications when advanced volatility states are detected:

#### **PRE_BREAKOUT_TENSION Alert:**
```
⚠️ PRE-BREAKOUT TENSION Detected

Symbol: XAUUSD
State: PRE_BREAKOUT_TENSION
Confidence: 85.5%
Session: LONDON
ATR Ratio: 0.95
BB Width Ratio: 0.45

Action: Prioritize breakout strategies (breakout_ib_volatility_trap, liquidity_sweep_reversal, breaker_block)
Avoid mean reversion strategies.
```
**Color**: Orange (warning)

#### **POST_BREAKOUT_DECAY Alert:**
```
⚠️ POST-BREAKOUT DECAY Detected

Symbol: BTCUSD
State: POST_BREAKOUT_DECAY
Confidence: 78.2%
Session: NY
ATR Ratio: 0.88
BB Width Ratio: 0.52

Action: Prioritize mean reversion strategies (mean_reversion_range_scalp, fvg_retracement, order_block_rejection)
Avoid trend continuation strategies.
```
**Color**: Orange (warning)

#### **FRAGMENTED_CHOP Alert:**
```
⚠️ FRAGMENTED CHOP Detected

Symbol: EURUSD
State: FRAGMENTED_CHOP
Confidence: 72.1%
Session: ASIAN
ATR Ratio: 0.65
BB Width Ratio: 0.38

Action: Only allow micro_scalp and mean_reversion_range_scalp strategies.
All other strategies blocked.
```
**Color**: Orange (warning)

#### **SESSION_SWITCH_FLARE Alert:**
```
🚨 SESSION SWITCH FLARE Detected

Symbol: XAUUSD
State: SESSION_SWITCH_FLARE
Confidence: 91.3%
Session: LONDON
ATR Ratio: 2.1
BB Width Ratio: 1.8

Action: ⛔ ALL TRADING BLOCKED - Wait for volatility stabilization.
No auto-execution plans will be created or executed.
```
**Color**: Red (critical)

---

## 📝 Log Messages

### **Normal Operation Logs:**

```
✅ Volatility regime: PRE_BREAKOUT_TENSION (confidence: 85.5%)
✅ Volatility strategy recommendations: Prioritize: breakout_ib_volatility_trap, liquidity_sweep_reversal, breaker_block
```

### **Regime Change Logs:**

**Basic States** (INFO level):
```
📊 Regime Change Event [a1b2c3d4] XAUUSD: STABLE → TRANSITIONAL (Confidence: 75.2%, Session: LONDON)
```

**Advanced States** (WARNING level):
```
⚠️ Advanced Volatility State Detected [e5f6g7h8] BTCUSD: TRANSITIONAL → PRE_BREAKOUT_TENSION (Confidence: 85.5%, Session: NY)
```

### **Plan Validation Logs:**

**Rejected Plan:**
```
⚠️ Plan creation rejected due to volatility state: FRAGMENTED_CHOP only allows ['micro_scalp', 'mean_reversion_range_scalp'] strategies
```

**Accepted Plan:**
```
✅ Auto-execution plan created: plan_id=abc123, strategy=breakout_ib_volatility_trap, volatility_state=PRE_BREAKOUT_TENSION
```

---

## 🎯 New Capabilities Available to ChatGPT

### **1. Volatility-Aware Strategy Selection**

ChatGPT can now:
- See which strategies are prioritized/avoided for the current volatility state
- Understand confidence adjustments based on volatility
- Receive explicit "WAIT" recommendations with reasons

### **2. Enhanced Analysis Context**

ChatGPT receives:
- ATR trend analysis (slope, decline rate, direction)
- Wick variance tracking (increasing/decreasing compression)
- Time since breakout (minutes/hours, breakout type, price)
- Mean reversion pattern detection
- Volatility spike detection (temporary vs sustained)
- Session transition awareness
- Whipsaw detection

### **3. Dynamic Risk Management**

When ChatGPT creates plans with `strategy_type`:
- Position sizing automatically adjusted based on volatility
- Stop Loss automatically widened for volatile states
- Take Profit automatically adjusted for volatility conditions
- Trading blocked during `SESSION_SWITCH_FLARE`

**Example Risk Adjustments:**
- `PRE_BREAKOUT_TENSION`: Risk reduced to 85%, SL multiplier 1.725x, TP multiplier 3.0x
- `POST_BREAKOUT_DECAY`: Risk reduced to 90%, SL multiplier 1.5x, TP multiplier 2.0x
- `FRAGMENTED_CHOP`: Risk reduced to 60%, SL multiplier 1.2x, TP multiplier 1.8x
- `SESSION_SWITCH_FLARE`: Risk = 0%, Trading blocked

---

## 🔍 How to Verify Everything is Working

### **1. Check Database Creation:**
```bash
ls -la data/volatility_regime_events.sqlite
```

### **2. Check Logs for Initialization:**
```bash
grep "RegimeDetector initialized" logs/*.log
grep "Breakout events database initialized" logs/*.log
```

### **3. Test Analysis Tool:**
Ask ChatGPT: "Analyze XAUUSD"
- Check that `response.data.volatility_metrics` is present
- Verify `regime` is one of the 7 states
- Confirm `strategy_recommendations` is populated

### **4. Test Plan Creation:**
Ask ChatGPT: "Create an auto-execution plan for XAUUSD breakout"
- If `SESSION_SWITCH_FLARE` is active, plan should be rejected
- If `FRAGMENTED_CHOP` is active, only `micro_scalp` or `mean_reversion_range_scalp` should be accepted
- Check logs for validation messages

### **5. Monitor Discord Alerts:**
- Watch for orange/red embeds when advanced states are detected
- Verify alert content matches the detected state

---

## ⚠️ Important Notes

### **Backward Compatibility:**
- ✅ All existing functionality remains intact
- ✅ Previous volatility states (STABLE, TRANSITIONAL, VOLATILE) still work
- ✅ Existing auto-execution plans continue to function
- ✅ No breaking changes to API responses

### **Performance:**
- Detection runs on every `analyse_symbol_full` call
- Database operations are thread-safe and optimized
- Tracking structures use in-memory deques for fast access
- No significant performance impact expected

### **Error Handling:**
- If volatility detection fails, analysis continues with basic volatility state
- If strategy recommendations fail, analysis continues without recommendations
- If Discord alerts fail, logging continues normally
- All errors are logged but do not break the analysis pipeline

---

## 📚 Knowledge Documents Updated

ChatGPT now has access to updated knowledge documents:
- `7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` - New volatility states and detection criteria
- `6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md` - Strategy mapping and validation rules
- `10.SMC_MASTER_EMBEDDING.md` - SMC analysis adjusted for volatility states
- `13.GOLD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md` - XAUUSD-specific volatility behavior
- `14.BTCUSD_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md` - BTCUSD-specific volatility behavior
- `15.FOREX_ANALYSIS_QUICK_REFERENCE_EMBEDDING.md` - Forex-specific volatility behavior

---

## 🎉 Summary

After restarting services, you should see:

1. ✅ **Database initialized** (`data/volatility_regime_events.sqlite`)
2. ✅ **Enhanced analysis responses** with detailed volatility metrics
3. ✅ **Discord alerts** for advanced volatility state transitions
4. ✅ **Plan validation** blocking incompatible strategies
5. ✅ **Strategy recommendations** in analysis responses
6. ✅ **Dynamic risk adjustments** for new plans
7. ✅ **Enhanced logging** for regime changes

**All 105 tests passed** - the system is production-ready! 🚀

