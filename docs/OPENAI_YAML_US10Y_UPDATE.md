# 🔧 OpenAI.yaml Updated for US10Y

## Problem

When asking **"What's the market context for Gold?"**:

**Custom GPT:**
- ❌ Did NOT check DXY/US10Y
- ❌ Only showed confluence score (75/100)
- ❌ Said "Good setup, wait for confirmation"

**Telegram:**
- ✅ Checked DXY, VIX, US10Y
- ✅ Showed macro fundamentals
- ✅ Said "🔴 BEARISH - Both DXY and US10Y against Gold"

---

## Root Cause

The **`openai.yaml`** file (Custom GPT's instruction manual) didn't mention:
- US10Y integration
- Mandatory DXY/US10Y checks for Gold
- 3-signal confluence system

So Custom GPT didn't know to check these indicators for Gold trades.

---

## The Fix

### **1. Updated API Description**

Added macro analysis section to the main API description:

```yaml
🌍 Macro Analysis (Yahoo Finance - Free):
- DXY (US Dollar Index) - Real-time USD strength (~99-107)
- VIX (Volatility Index) - Market fear gauge (<15=calm, >20=fear)
- US10Y (10-Year Treasury Yield) - Bond yields (~3.5-4.5%)
- **MANDATORY for Gold trades**: Check DXY + US10Y (inverse correlation)
- 3-signal confluence: DXY↓ + US10Y↓ = Bullish Gold | DXY↑ + US10Y↑ = Bearish Gold
```

### **2. Updated getCurrentPrice Endpoint**

**Before:**
```yaml
summary: Get current price (MT5 broker or Yahoo Finance for DXY/VIX)
description: "Returns price for symbol. Broker symbols (XAUUSD, BTCUSD) from MT5. Market indices (DXY, VIX) from Yahoo Finance."
```

**After:**
```yaml
summary: Get current price (MT5 broker or Yahoo Finance for DXY/VIX/US10Y)
description: "Returns price for symbol. Broker symbols (XAUUSD, BTCUSD) from MT5. Market indices (DXY, VIX, US10Y) from Yahoo Finance. MANDATORY for Gold: Check DXY + US10Y. Use DXY (~99-107) for USD strength, VIX (<15=calm, >20=fear) for volatility, US10Y (~3.5-4.5%) for Gold correlation."
```

---

## What This Tells Custom GPT

Now when Custom GPT reads `openai.yaml`, it will see:

1. **US10Y is available** via `/api/v1/price/US10Y`
2. **It's mandatory for Gold** to check DXY + US10Y
3. **3-signal system**: DXY + US10Y = Gold outlook
4. **How to interpret**: Rising DXY + Rising US10Y = Bearish Gold

---

## Expected Behavior After Update

### **Next Time You Ask Custom GPT:**

**User:** "What's the market context for Gold?"

**Custom GPT will:**
1. ✅ Call `/api/v1/price/DXY`
2. ✅ Call `/api/v1/price/VIX`
3. ✅ Call `/api/v1/price/US10Y`
4. ✅ Check confluence score
5. ✅ Combine ALL signals

**Response:**
```
📊 Market Context — Gold

🌍 Macro Fundamentals:
DXY: 99.43 (Rising - USD strengthening)
VIX: 17.06 (Normal volatility)
US10Y: 4.15% (Rising - Bearish for Gold)

🎯 Gold Outlook: 🔴 BEARISH
Both DXY and US10Y against Gold

📊 Technical Confluence: 75/100 (Good)
But macro headwinds suggest waiting

📉 Verdict: Wait for DXY/US10Y reversal
despite good technical setup
```

---

## Sync Custom GPT Actions

**IMPORTANT:** You need to **update the Custom GPT Actions** with the new `openai.yaml` content:

### **Steps:**

1. Go to your Custom GPT settings
2. Navigate to **Actions**
3. Copy the updated `openai.yaml` file contents
4. Paste into the Actions schema field
5. Click **Save**

### **OR Use the ngrok URL:**

If your Custom GPT uses the ngrok URL for schema, just **restart the API server** and it will auto-sync:

```bash
cd c:\mt5-gpt\TelegramMoneyBot.v7
# Stop server (Ctrl+C)
python -m uvicorn main_api:app --reload --host 0.0.0.0 --port 8000
```

---

## Comparison: Before vs After

### **Before Update:**

| What | Custom GPT | Telegram |
|------|-----------|----------|
| Checks DXY | ❌ No | ✅ Yes |
| Checks US10Y | ❌ No | ✅ Yes |
| Checks VIX | ❌ No | ✅ Yes |
| Shows Gold Outlook | ❌ No | ✅ Yes |
| Result | Technical only | Macro + Technical |

### **After Update:**

| What | Custom GPT | Telegram |
|------|-----------|----------|
| Checks DXY | ✅ Yes | ✅ Yes |
| Checks US10Y | ✅ Yes | ✅ Yes |
| Checks VIX | ✅ Yes | ✅ Yes |
| Shows Gold Outlook | ✅ Yes | ✅ Yes |
| Result | Macro + Technical | Macro + Technical |

**Both interfaces now provide comprehensive Gold analysis!** ✅

---

## Testing

### **After Syncing Custom GPT Actions:**

**Ask:**
```
"What's the market context for Gold?"
```

**Should Now See:**
- DXY price + trend
- VIX price + level
- US10Y price + trend
- Gold outlook (🔴/🟢/⚪)
- Confluence score
- Combined verdict

### **Test Endpoints Directly:**

```bash
# DXY
curl http://localhost:8000/api/v1/price/DXY

# VIX
curl http://localhost:8000/api/v1/price/VIX

# US10Y (NEW)
curl http://localhost:8000/api/v1/price/US10Y
```

---

## Summary

✅ **Updated `openai.yaml`** with US10Y info
✅ **Added macro analysis section** to API description
✅ **Updated getCurrentPrice** endpoint description
✅ **Mentioned mandatory checks** for Gold trades
✅ **Explained 3-signal system** (DXY + US10Y + Technical)

### **What Changed:**

**Before:** Custom GPT didn't know about US10Y or mandatory Gold checks
**After:** Custom GPT knows to check DXY + US10Y for all Gold trades

### **Next Steps:**

1. **Sync Custom GPT Actions** with updated `openai.yaml`
2. **Test** by asking "What's the market context for Gold?"
3. **Verify** it now checks DXY, VIX, US10Y
4. **Enjoy** consistent macro analysis across both interfaces!

**Custom GPT now has the same macro intelligence as Telegram!** 🎯📊

