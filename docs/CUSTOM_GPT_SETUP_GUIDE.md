# Custom GPT Setup Guide - Final Configuration

## ✅ What We Fixed

Your Custom GPT was giving generic educational responses instead of fetching live data for Gold questions. This has been fixed by:

1. **Shortened `openai.yaml` description** - Now under 300 char limit
2. **Created concise Instructions** - 7,395 chars (under 8,000 limit)
3. **Made Gold analysis mandatory** - Must fetch DXY + US10Y + VIX

---

## 🔧 How to Update Your Custom GPT

### Step 1: Update the Actions Schema (openai.yaml)

The `openai.yaml` file has been updated with:
- Shortened endpoint descriptions (under 300 chars)
- Explicit Gold analysis instructions in main description
- Clear instructions for DXY, US10Y, VIX calls

**File:** `openai.yaml` (already updated in your project)

**Action:** In your Custom GPT settings:
1. Go to **Configure** → **Actions**
2. Click **Edit** on your existing Action
3. Copy the entire contents of `openai.yaml`
4. Paste into the schema editor
5. Click **Save**

---

### Step 2: Update the Instructions

**File:** `CUSTOM_GPT_INSTRUCTIONS_CONCISE.md` (created in your project)

**Action:** In your Custom GPT settings:
1. Go to **Configure** → **Instructions**
2. Copy the entire contents of `CUSTOM_GPT_INSTRUCTIONS_CONCISE.md`
3. Paste into the Instructions field (replacing old content)
4. Click **Save**

**Important:** This concise version is **7,395 characters** (under the 8,000 limit).

---

### Step 3: Update the Knowledge Base (Optional but Recommended)

If you want to provide more detailed context, create a knowledge file:

**File:** `ChatGPT_Knowledge_Document.md`

**Contents:** Include detailed strategy explanations, examples, etc. (anything that doesn't fit in Instructions)

**Action:**
1. Go to **Configure** → **Knowledge**
2. Click **Upload files**
3. Upload `ChatGPT_Knowledge_Document.md`
4. Click **Save**

---

## 🧪 Test Your Custom GPT

After updating, test with these questions:

### Test 1: Gold Market Context
**Ask:** "What's the market context for Gold?"

**Expected Response:**
- ✅ Calls `getCurrentPrice("DXY")`
- ✅ Calls `getCurrentPrice("US10Y")`
- ✅ Calls `getCurrentPrice("VIX")`
- ✅ Calls `getCurrentPrice("XAUUSD")`
- ✅ Shows current prices with trends
- ✅ Calculates 3-signal Gold outlook (🟢🟢/🔴🔴/⚪)
- ✅ Gives specific BUY/SELL/WAIT verdict
- ❌ Does NOT give generic educational response

---

### Test 2: USD Pair Analysis
**Ask:** "Should I buy USDJPY?"

**Expected Response:**
- ✅ Calls `getCurrentPrice("DXY")` first
- ✅ Mentions DXY trend in analysis
- ✅ Checks if DXY aligns with USDJPY direction

---

### Test 3: Safety Check
**Ask:** "Is it safe to trade now?"

**Expected Response:**
- ✅ Calls session analysis endpoint
- ✅ Calls news/calendar endpoint
- ✅ Shows current session (Asian/London/NY)
- ✅ Shows news blackout status
- ✅ Gives specific Safe/Wait verdict

---

## 📊 Key Changes Summary

### Before (❌ Wrong Behavior):
```
User: "What's the market context for Gold?"

GPT: "Gold's market context is influenced by several factors:
1. Macro (H4) – Trend Identification
2. Gold's primary swing timeframe (H4) is used to define...
[Generic educational content, no live data]"
```

### After (✅ Correct Behavior):
```
User: "What's the market context for Gold?"

GPT: [Calls APIs for DXY, US10Y, VIX, XAUUSD]

"🌍 Market Context — Gold (XAUUSD)
Current Price: $3,962.78

📊 Macro Fundamentals:
DXY: 99.427 (Rising)
→ USD strengthening → Bearish for Gold

US10Y: 4.148% (Rising)
→ Rising yields → Bearish for Gold

VIX: 17.06 (Normal)

🎯 Gold Outlook: 🔴🔴 BEARISH
Both DXY and US10Y against Gold

📉 Verdict: WAIT - Don't buy Gold now
Macro fundamentals strongly bearish.

👉 Would you like me to set an alert when DXY reverses?"
```

---

## 🔑 Critical Rules in New Instructions

1. **Gold = ALWAYS fetch DXY + US10Y + VIX** (mandatory, no exceptions)
2. **USD pairs = ALWAYS fetch DXY first**
3. **Safety = ALWAYS fetch session + news**
4. **Price = ALWAYS call getCurrentPrice()** (never quote external sources)
5. **Format = ALWAYS use emojis, structure, specific verdicts**
6. **Follow-up = ALWAYS end with a question**

---

## 🚨 If Issues Persist

If Custom GPT still gives generic responses after updating:

1. **Check Actions are enabled:**
   - Go to Configure → Actions
   - Ensure "Privacy" is NOT blocking API calls

2. **Check ngrok is running:**
   ```bash
   # Should show your API URL
   ngrok http 8000
   ```

3. **Check server is running:**
   ```bash
   cd c:\mt5-gpt\TelegramMoneyBot.v7
   python main_api.py
   ```

4. **Test API directly:**
   ```bash
   # Should return DXY price from Yahoo Finance
   curl http://localhost:8000/api/v1/price/DXY
   ```

5. **Check Custom GPT logs:**
   - In ChatGPT conversation, click the "..." menu
   - Look for "Talked to [your-ngrok-url]"
   - If missing, Actions aren't being triggered

---

## 📁 Files Updated

1. ✅ `openai.yaml` - Shortened descriptions, added Gold instructions
2. ✅ `CUSTOM_GPT_INSTRUCTIONS_CONCISE.md` - Concise version (7,395 chars)
3. ✅ `CUSTOM_GPT_SETUP_GUIDE.md` - This file

---

## 🎯 Next Steps

1. Copy `openai.yaml` to Custom GPT Actions
2. Copy `CUSTOM_GPT_INSTRUCTIONS_CONCISE.md` to Custom GPT Instructions
3. Test with Gold question
4. Verify it fetches live data (not generic response)
5. Done! 🎉

---

**Questions?** Just ask!

