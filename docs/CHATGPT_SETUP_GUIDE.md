# ChatGPT Custom GPT Setup Guide

## 📋 How to Configure Your Custom GPT

### **Step 1: Instructions Field (Max 8000 characters)**

**Copy and paste THIS file into the Instructions field:**
- ✅ `CUSTOM_GPT_INSTRUCTIONS_ULTRA_CONCISE.md` **(3493 characters - FITS!)**

**DO NOT use:**
- ❌ `CUSTOM_GPT_INSTRUCTIONS_CONCISE_SMC.md` (9036 characters - TOO LONG!)

---

### **Step 2: Knowledge Files (Upload These 9 Files)**

Upload these files to the "Knowledge" section:

**Core Documentation:**
1. ✅ `ChatGPT_Knowledge_Document.md` - Main trading rules & protocols
2. ✅ `ChatGPT_Knowledge_Smart_Money_Concepts.md` - SMC framework (CHOCH, BOS, OB, Liquidity)
3. ✅ `ChatGPT_Knowledge_Alert_System.md` - Alert creation guide (fixes the 10-message spam)

**Symbol-Specific Guides:**
4. ✅ `BTCUSD_ANALYSIS_QUICK_REFERENCE.md` - Bitcoin analysis (5 signals: VIX, S&P, DXY, BTC.D, F&G)
5. ✅ `GOLD_ANALYSIS_QUICK_REFERENCE.md` - Gold analysis (Macro + SMC)
6. ✅ `SYMBOL_GUIDE.md` - All symbols strategies (scalp & intraday)

**Clarifications:**
7. ✅ `WAIT_vs_AVOID_EXPLAINED.md` - Verdict types explained
8. ✅ `ChatGPT_Knowledge_Lot_Sizing.md` - Lot sizing rules

**Full Instructions (Reference):**
9. ✅ `CUSTOM_GPT_INSTRUCTIONS_CONCISE_SMC.md` - Complete instructions (ChatGPT can reference this even though it doesn't fit in Instructions field)

---

### **Step 3: Actions (API Configuration)**

1. **Import Schema:**
   - Upload `openai.yaml`
   - This defines all available tools (analyse_symbol, execute_trade, macro_context, etc.)

2. **Configure Authentication:**
   - Authentication Type: **Bearer**
   - Token: `YOUR_API_KEY` (from your .env file)

3. **Set Server URL:**
   - Server URL: `https://your-ngrok-url.ngrok-free.app`
   - Example: `https://verbally-faithful-monster.ngrok-free.app`

4. **Privacy:**
   - Set to **Server Only** (actions run on your server, not OpenAI's)

---

## ✅ Verification Checklist

### **Instructions Field:**
- [ ] Pasted `CUSTOM_GPT_INSTRUCTIONS_ULTRA_CONCISE.md` (3493 chars)
- [ ] Character count shows <8000
- [ ] Contains: Alerts rule, SMC framework, Gold/Bitcoin protocols

### **Knowledge Files (9 total):**
- [ ] ChatGPT_Knowledge_Document.md
- [ ] ChatGPT_Knowledge_Smart_Money_Concepts.md
- [ ] ChatGPT_Knowledge_Alert_System.md
- [ ] BTCUSD_ANALYSIS_QUICK_REFERENCE.md
- [ ] GOLD_ANALYSIS_QUICK_REFERENCE.md
- [ ] SYMBOL_GUIDE.md
- [ ] WAIT_vs_AVOID_EXPLAINED.md
- [ ] ChatGPT_Knowledge_Lot_Sizing.md
- [ ] CUSTOM_GPT_INSTRUCTIONS_CONCISE_SMC.md

### **Actions:**
- [ ] openai.yaml uploaded
- [ ] Bearer token configured
- [ ] Server URL set to your ngrok URL
- [ ] Privacy: Server Only

### **Desktop Agent:**
- [ ] desktop_agent.py running
- [ ] ngrok tunnel active (port 8000)
- [ ] Tools registered (check logs for "📋 Registered tool: moneybot.xxx")

---

## 🧪 Test Your Setup

### **Test 1: Macro Context**
Ask ChatGPT:
```
What's the macro context for Bitcoin?
```

**Expected:**
- Calls `moneybot.macro_context`
- Shows: VIX, S&P 500, DXY, BTC Dominance, Crypto Fear & Greed
- Displays fresh timestamp

---

### **Test 2: Symbol Analysis**
Ask ChatGPT:
```
Analyse BTCUSD
```

**Expected:**
- Calls `moneybot.macro_context` (Bitcoin macro)
- Calls `moneybot.analyse_symbol` (technical)
- Shows SMC analysis (CHOCH, BOS, Order Blocks, Liquidity)
- Gives verdict with entry/SL/TP

---

### **Test 3: Alert Creation (The Important One!)**
Ask ChatGPT:
```
Alert me when BTCUSD hits 115000 or when BOS Bull appears on M15
```

**Expected (GOOD):**
- ChatGPT calls `moneybot.add_alert` TWICE immediately
- Response: "✅ Two alerts created: [details]"
- **Total messages: 2** (your request + confirmation)

**If ChatGPT asks questions (BAD):**
```
ChatGPT: "What type?" → Upload ChatGPT_Knowledge_Alert_System.md
ChatGPT: "Please confirm..." → Check Instructions field has ALERTS rule
ChatGPT: "What platform?" → Re-upload knowledge files
```

---

### **Test 4: Trade Execution**
Ask ChatGPT:
```
Execute a BUY on BTCUSD at 64800, SL 64200, TP 67500
```

**Expected:**
- Calls `moneybot.execute_trade`
- Auto-calculates lot size (0.02 for BTCUSD)
- Returns: "✅ Trade executed: Ticket #123456"

---

### **Test 5: Position Management**
Ask ChatGPT:
```
Show my open positions
```

**Expected:**
- Calls `moneybot.getPositions`
- Lists all open trades with P&L

---

## 🔧 Troubleshooting

### **Problem: "Unknown tool: moneybot.xxx"**

**Cause:** Desktop agent not running or ngrok URL incorrect

**Fix:**
1. Restart desktop_agent.py
2. Check ngrok tunnel is active: `ngrok http 8000`
3. Update Server URL in ChatGPT Actions to match ngrok URL

---

### **Problem: "The alert couldn't be created" (10+ messages)**

**Cause:** ChatGPT doesn't have alert system knowledge

**Fix:**
1. Upload `ChatGPT_Knowledge_Alert_System.md` to Knowledge
2. Check Instructions field has ALERTS rule (line ~27)
3. Re-upload `CUSTOM_GPT_INSTRUCTIONS_ULTRA_CONCISE.md` to Instructions

---

### **Problem: ChatGPT still references "V8" instead of "Advanced"**

**Cause:** Old knowledge files still loaded

**Fix:**
1. Delete all knowledge files from ChatGPT
2. Re-upload all 9 files listed above (latest versions)
3. Restart desktop_agent.py to clear cache

---

### **Problem: "Symbol BTCUSD not available"**

**Cause:** Broker requires 'c' suffix

**Fix:**
- System auto-converts BTCUSD → BTCUSDc
- If still fails, restart desktop_agent.py
- Check MT5 has BTCUSDc in Market Watch

---

## 📊 What You Should See in ChatGPT Responses

### **Bitcoin Analysis:**
```
₿ Bitcoin Analysis — BTCUSD
📅 Data as of: 2025-10-14 14:30:00 UTC

📊 Risk Sentiment:
VIX: 21.8 (RISK_OFF)
S&P 500: 6654.72 (+1.56%) RISING
DXY: 99.15 (Falling)

🔷 Crypto Fundamentals:
BTC Dominance: 57.4% (STRONG)
Crypto Fear & Greed: 38/100 (Fear)

🎯 Sentiment Outlook: 🟢 BULLISH for Crypto

🏛️ Bitcoin Structure (SMC):
✅ BOS Bull confirmed (3x HH)
🟢 Bullish OB: $64,800-$65,200
🎯 Liquidity: Equal Highs at $69,800

📉 VERDICT: BUY at Order Block
Entry: $64,800-$65,200
SL: $64,200
TP1: $67,500 | TP2: $69,800
R:R: 1:4 to 1:8
```

### **Alert Creation:**
```
✅ Two alerts created:

1. Price Alert: BTCUSD ≥ $115,000
   - Expires in 48 hours
   - Triggers once

2. Structure Alert: BOS Bull on M15
   - Monitors continuously
   - Expires in 48 hours

You'll be notified when either condition triggers.
```

---

## 🎯 Success Criteria

✅ **ChatGPT calls APIs immediately** (no "I'll pull data" phrases)

✅ **Shows 5 Bitcoin signals** (VIX, S&P, DXY, BTC.D, F&G)

✅ **Uses SMC terminology** (CHOCH, BOS, Order Blocks, Liquidity)

✅ **Alert creation in 1-2 messages** (not 10+)

✅ **Fresh timestamps displayed** (within last 5 minutes)

✅ **Auto-converts symbols** (BTCUSD → BTCUSDc)

✅ **Direct recommendations** ("BUY at X, SL Y, TP Z" - not wishy-washy)

---

## 📚 File Organization Summary

**Paste into Instructions field (1 file):**
- `CUSTOM_GPT_INSTRUCTIONS_ULTRA_CONCISE.md` (3493 chars)

**Upload to Knowledge (9 files):**
- 3 core docs (main rules, SMC, alerts)
- 3 symbol guides (Bitcoin, Gold, general)
- 2 clarifications (WAIT/AVOID, lot sizing)
- 1 full instructions (reference only)

**Upload to Actions (1 file):**
- `openai.yaml`

**Total: 11 files**

---

**Status:** ✅ Setup guide complete!  
Follow this checklist to configure your Custom GPT correctly.
