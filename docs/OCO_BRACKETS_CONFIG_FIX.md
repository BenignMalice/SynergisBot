# ✅ OCO Brackets Config Fix - COMPLETE

## 🔧 **Issue Fixed**

**Warning:**
```
WARNING - OCO bracket calculation failed for XAUUSDc: module 'config.settings' has no attribute 'USE_OCO_BRACKETS'
WARNING - OCO bracket calculation failed for BTCUSDc: module 'config.settings' has no attribute 'USE_OCO_BRACKETS'
WARNING - OCO bracket calculation failed for EURUSDc: module 'config.settings' has no attribute 'USE_OCO_BRACKETS'
WARNING - OCO bracket calculation failed for USDJPYc: module 'config.settings' has no attribute 'USE_OCO_BRACKETS'
```

**Cause:** Missing `USE_OCO_BRACKETS` setting in `config/settings.py`

**Fix:** Added OCO bracket configuration setting

---

## 📝 **What Changed**

**File:** `config/settings.py` (line 541)

**Added:**
```python
# ===== OCO BRACKET SETTINGS =====
# Enable/disable OCO (One-Cancels-Other) bracket orders
USE_OCO_BRACKETS = False  # Disabled by default (experimental feature)
```

---

## 🎯 **What is USE_OCO_BRACKETS?**

**OCO (One-Cancels-Other) Brackets:**
- Places **two pending orders** at once (BUY and SELL)
- When **one fills**, the **other cancels** automatically
- Used for **range-bound** markets (not trending)

**Example:**
```
Current Price: 1.1500

OCO Bracket:
  BUY_LIMIT @ 1.1450 (if price drops)
  SELL_LIMIT @ 1.1550 (if price rises)

If BUY fills → SELL cancels
If SELL fills → BUY cancels
```

---

## 🎯 **Why Disabled by Default?**

**Reasons:**
1. **Experimental feature** - not fully tested
2. **Complex logic** - requires careful validation
3. **Not suitable for trending markets** - only for ranges
4. **Risk of confusion** - two orders at once

**When to Enable:**
- You understand OCO bracket strategy
- You trade range-bound markets
- You want automated bracket orders

---

## 🚀 **How to Enable (Optional)**

**If you want to use OCO brackets:**

1. Edit `config/settings.py`
2. Change:
   ```python
   USE_OCO_BRACKETS = False  # Disabled
   ```
   To:
   ```python
   USE_OCO_BRACKETS = True  # Enabled
   ```
3. Restart bot

**When enabled:**
- Signal scanner will calculate OCO brackets
- For **non-trending** markets only
- Places BUY and SELL pending orders
- One cancels the other when filled

---

## ✅ **Status**

**Fix Applied:** ✅  
**Setting Added:** `USE_OCO_BRACKETS = False`  
**Default State:** Disabled (safe)  
**Action Required:** Restart bot (warnings will disappear)

---

## 🚀 **Next Steps**

### **Restart Telegram Bot:**
```powershell
cd C:\mt5-gpt\TelegramMoneyBot.v7
python chatgpt_bot.py
```

**Should now see:**
```
✅ Signal scanner initialized
✅ Scanning for signals...
```

**Should NOT see:**
```
❌ module 'config.settings' has no attribute 'USE_OCO_BRACKETS'
```

---

## 📊 **Summary**

**Problem:** Missing OCO bracket configuration setting

**Solution:** Added `USE_OCO_BRACKETS = False` to `config/settings.py`

**Impact:** 
- ✅ Warnings will disappear
- ✅ Signal scanner will work without errors
- ✅ OCO brackets disabled by default (safe)

**Optional:** Enable OCO brackets if you want to use that strategy

---

**Bottom Line:** Simple missing config setting. Added with safe default (disabled). Restart bot to clear warnings! ✅

