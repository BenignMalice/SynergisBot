# Alert System - Structure Alert Testing Guide

## 🎯 Problem Identified

ChatGPT was receiving **incorrect instructions** in the knowledge document, causing it to use the wrong `condition` parameter for structure alerts.

### ❌ What Was Wrong:
```json
{
  "alert_type": "structure",
  "condition": "bos_bear",  // WRONG - this is not a valid AlertCondition enum
  "parameters": {
    "timeframe": "M15"
  }
}
```

### ✅ What's Correct:
```json
{
  "alert_type": "structure",
  "condition": "detected",  // CORRECT - this is the AlertCondition enum value
  "parameters": {
    "pattern": "bos_bear",  // The pattern goes in parameters
    "timeframe": "M15"
  }
}
```

---

## 🔧 What Was Fixed

### 1. **ChatGPT_Knowledge_Alert_System.md**
- Updated all structure alert examples to use `condition: "detected"`
- Added `pattern` field to `parameters` object
- Fixed all 4 structure patterns: `bos_bull`, `bos_bear`, `choch_bull`, `choch_bear`
- Updated quick reference card at the bottom

### 2. **openai.yaml**
- Enhanced alert examples with all 4 structure patterns:
  - `addAlert_BOSBull` - Bullish continuation
  - `addAlert_BOSBear` - Bearish continuation  
  - `addAlert_CHOCHBull` - Bullish reversal
  - `addAlert_CHOCHBear` - Bearish reversal
- Added `expires_hours: 48` and `one_time: true` to all examples
- Added comprehensive price alert examples (greater_than, less_than, crosses_above)

### 3. **CUSTOM_GPT_INSTRUCTIONS_ULTRA_CONCISE.md**
- Updated alert quick reference with correct format
- Added both BOS Bull and CHOCH Bear examples
- Clarified that `pattern` goes inside `parameters`

---

## 📊 Alert System Architecture

### AlertCondition Enum (Valid Values):
```python
class AlertCondition(Enum):
    EQUALS = "equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"
    DETECTED = "detected"  # For event-based alerts (structure, indicator, volatility)
```

### How Structure Alerts Work:

1. **ChatGPT calls:**
   ```json
   {
     "tool": "moneybot.add_alert",
     "arguments": {
       "symbol": "BTCUSD",
       "alert_type": "structure",
       "condition": "detected",
       "description": "BOS Bear on M15",
       "parameters": {
         "pattern": "bos_bear",
         "timeframe": "M15"
       }
     }
   }
   ```

2. **desktop_agent.py receives and validates:**
   - `AlertType("structure")` ✅
   - `AlertCondition("detected")` ✅
   - `parameters["pattern"] = "bos_bear"` ✅

3. **alert_monitor.py checks:**
   - Every 60 seconds, `check_all_alerts()` runs
   - For structure alerts, calls `_check_structure_alert()`
   - Extracts `pattern = "bos_bear"` from parameters
   - Checks candle data for BOS/CHOCH patterns
   - If detected, sends Telegram notification

4. **Telegram notification sent:**
   - User receives alert via Telegram bot
   - Alert is removed (if `one_time: true`)

---

## 🧪 Test Scenarios

### Test 1: BOS Bull Alert
**User says:** "Alert me when BOS Bull appears on M15"

**ChatGPT should call:**
```json
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "BTCUSD",
    "alert_type": "structure",
    "condition": "detected",
    "description": "BOS Bull detected on M15 timeframe",
    "parameters": {
      "pattern": "bos_bull",
      "timeframe": "M15"
    },
    "expires_hours": 48,
    "one_time": true
  }
}
```

**Expected result:** ✅ Alert created successfully

---

### Test 2: CHOCH Bear Alert
**User says:** "Notify me when bearish structure breaks on M15"

**ChatGPT should call:**
```json
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "EURUSD",
    "alert_type": "structure",
    "condition": "detected",
    "description": "CHOCH Bear detected on M15 - bearish reversal",
    "parameters": {
      "pattern": "choch_bear",
      "timeframe": "M15"
    },
    "expires_hours": 48,
    "one_time": true
  }
}
```

**Expected result:** ✅ Alert created successfully

---

### Test 3: Multiple Structure Alerts
**User says:** "Alert me for both BOS Bull and CHOCH Bear on M15"

**ChatGPT should call TWO tools:**

**Call 1:**
```json
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "BTCUSD",
    "alert_type": "structure",
    "condition": "detected",
    "description": "BOS Bull detected on M15",
    "parameters": {
      "pattern": "bos_bull",
      "timeframe": "M15"
    },
    "expires_hours": 48,
    "one_time": true
  }
}
```

**Call 2:**
```json
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "BTCUSD",
    "alert_type": "structure",
    "condition": "detected",
    "description": "CHOCH Bear detected on M15",
    "parameters": {
      "pattern": "choch_bear",
      "timeframe": "M15"
    },
    "expires_hours": 48,
    "one_time": true
  }
}
```

**Expected result:** ✅ Two alerts created successfully

---

### Test 4: Price + Structure Alert
**User says:** "Alert me when BTCUSD hits 115000 OR when BOS Bull appears"

**ChatGPT should call TWO tools:**

**Call 1 (Price):**
```json
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "BTCUSD",
    "alert_type": "price",
    "condition": "greater_than",
    "description": "BTCUSD reached $115,000",
    "parameters": {
      "price_level": 115000
    },
    "expires_hours": 48,
    "one_time": true
  }
}
```

**Call 2 (Structure):**
```json
{
  "tool": "moneybot.add_alert",
  "arguments": {
    "symbol": "BTCUSD",
    "alert_type": "structure",
    "condition": "detected",
    "description": "BOS Bull detected on M15",
    "parameters": {
      "pattern": "bos_bull",
      "timeframe": "M15"
    },
    "expires_hours": 48,
    "one_time": true
  }
}
```

**Expected result:** ✅ Two alerts created (one price, one structure)

---

## 🔍 Debugging Failed Alerts

### Error: "bos_bear is not a valid AlertCondition"
**Cause:** ChatGPT used `condition: "bos_bear"` instead of `condition: "detected"`
**Fix:** Update ChatGPT knowledge with correct format (already done)

### Error: "Missing required arguments: pattern"
**Cause:** `pattern` not provided in `parameters`
**Fix:** Ensure `parameters: {"pattern": "bos_bear", "timeframe": "M15"}`

### Error: "structure_break_bearish is not a valid AlertCondition"
**Cause:** ChatGPT invented a custom condition name
**Fix:** Use only valid AlertCondition enum values from knowledge doc

---

## 📋 Valid Structure Patterns

**All patterns use `condition: "detected"` with pattern in parameters:**

| Pattern | Meaning | Use Case |
|---------|---------|----------|
| `bos_bull` | Bullish Break of Structure | Continuation - Higher High in uptrend |
| `bos_bear` | Bearish Break of Structure | Continuation - Lower Low in downtrend |
| `choch_bull` | Bullish Change of Character | Reversal - Higher Low breaking downtrend |
| `choch_bear` | Bearish Change of Character | Reversal - Lower High breaking uptrend |

---

## ✅ Success Criteria

**Good alert creation flow:**
```
User: "Alert me when BOS Bull appears on M15"
  ↓
ChatGPT: *calls moneybot.add_alert with correct parameters*
  ↓
System: ✅ Alert created successfully
  ↓
ChatGPT: "✅ Alert created! You'll be notified when BOS Bull is detected on M15."
```

**Total messages: 2** (user request + confirmation)

---

## 🚨 Common Mistakes to Avoid

### ❌ DON'T use pattern as condition:
```json
{
  "condition": "bos_bear"  // WRONG!
}
```

### ✅ DO use "detected" with pattern in parameters:
```json
{
  "condition": "detected",
  "parameters": {
    "pattern": "bos_bear"  // CORRECT!
  }
}
```

---

### ❌ DON'T invent condition names:
```json
{
  "condition": "structure_break_bearish"  // Not a valid enum!
}
```

### ✅ DO use only valid AlertCondition values:
```json
{
  "condition": "detected"  // Valid enum value
}
```

---

### ❌ DON'T ask 10 confirmation questions:
```
ChatGPT: "What type of alert?"
User: "Structure"
ChatGPT: "What pattern?"
User: "BOS Bear"
ChatGPT: "What timeframe?"
... (10 more messages)
```

### ✅ DO infer from natural language:
```
User: "Alert me when BOS Bull appears on M15"
ChatGPT: *immediately calls tool with inferred parameters*
```

---

## 📝 Quick Copy-Paste Examples for Testing

### BOS Bull (M15):
```json
{"tool": "moneybot.add_alert", "arguments": {"symbol": "BTCUSD", "alert_type": "structure", "condition": "detected", "description": "BOS Bull M15", "parameters": {"pattern": "bos_bull", "timeframe": "M15"}, "expires_hours": 48, "one_time": true}}
```

### BOS Bear (M15):
```json
{"tool": "moneybot.add_alert", "arguments": {"symbol": "EURUSD", "alert_type": "structure", "condition": "detected", "description": "BOS Bear M15", "parameters": {"pattern": "bos_bear", "timeframe": "M15"}, "expires_hours": 48, "one_time": true}}
```

### CHOCH Bull (H1):
```json
{"tool": "moneybot.add_alert", "arguments": {"symbol": "XAUUSD", "alert_type": "structure", "condition": "detected", "description": "CHOCH Bull H1", "parameters": {"pattern": "choch_bull", "timeframe": "H1"}, "expires_hours": 48, "one_time": true}}
```

### CHOCH Bear (M15):
```json
{"tool": "moneybot.add_alert", "arguments": {"symbol": "BTCUSD", "alert_type": "structure", "condition": "detected", "description": "CHOCH Bear M15", "parameters": {"pattern": "choch_bear", "timeframe": "M15"}, "expires_hours": 48, "one_time": true}}
```

---

## 🎯 Next Steps

1. ✅ **Documentation updated** - All knowledge docs corrected
2. ✅ **Examples added to openai.yaml** - All 4 structure patterns
3. ✅ **Instructions updated** - Ultra-concise guide corrected
4. 🔄 **Test with ChatGPT** - Try the test scenarios above
5. 🔄 **Monitor alerts** - Verify they trigger correctly via Telegram

---

**Last Updated:** 2025-10-14  
**Issue:** ChatGPT using wrong `condition` for structure alerts  
**Resolution:** Updated all knowledge docs to use `condition: "detected"` with `pattern` in `parameters`

