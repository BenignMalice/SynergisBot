# How to Test Enhanced Macro Context (S&P 500, BTC Dominance, Crypto Fear & Greed)

## ⚡ Quick Test (30 seconds)

### **Step 1: Run Local Test**

```bash
python quick_test.py
```

**Expected output:**
```
[PASS] VIX
[PASS] DXY
[PASS] US10Y
[PASS] S&P 500                    ← NEW
[PASS] BTC Dominance              ← NEW
[PASS] Crypto Fear & Greed        ← NEW
[PASS] Bitcoin Verdict

Result: 7/7 checks passed

[SUCCESS] All new data sources working correctly!
```

If all pass ✅ → Continue to Step 2  
If any fail ❌ → See troubleshooting at bottom

---

### **Step 2: Test with ChatGPT**

#### **2A: Make sure services are running**

Open 2 terminals:

**Terminal 1 - Desktop Agent:**
```bash
cd C:\mt5-gpt\TelegramMoneyBot.v7
python desktop_agent.py
```

**Terminal 2 - Ngrok:**
```bash
ngrok http 8000
```

Copy the ngrok URL (e.g., `https://verbally-faithful-monster.ngrok-free.app`)

---

#### **2B: Update ChatGPT Configuration**

1. Go to your Custom GPT settings
2. Upload/update knowledge documents:
   - `openai.yaml` ✅
   - `CUSTOM_GPT_INSTRUCTIONS_CONCISE_SMC.md` ✅
   - `ChatGPT_Knowledge_Document.md` ✅
   - `BTCUSD_ANALYSIS_QUICK_REFERENCE.md` ✅
   - `GOLD_ANALYSIS_QUICK_REFERENCE.md` ✅
   
3. Update Actions:
   - Import `openai.yaml` (if not already)
   - Update server URL to your ngrok URL
   - Add Bearer token authentication

---

#### **2C: Test Bitcoin Analysis**

**Ask ChatGPT:**
```
Analyse Bitcoin
```

**What you should see:**

```
₿ Bitcoin Analysis — BTCUSD
📅 Data as of: 2025-10-14 13:41:18 UTC    ← MUST be fresh!

📊 Risk Sentiment:
VIX: 21.99 (RISK_OFF)                      ← Traditional
S&P 500: 6654.72 (+1.56%) RISING          ← NEW!
DXY: 99.18 (Falling)                       ← Traditional

🔷 Crypto Fundamentals:
BTC Dominance: 57.4% (STRONG)              ← NEW!
Crypto Fear & Greed: 38/100 (Fear)         ← NEW!

🎯 Sentiment Outlook: 🟢 BULLISH for Crypto
(3 of 5 signals bullish, mixed risk)

🏛️ Bitcoin Structure (SMC):
[CHOCH/BOS/Order Block analysis...]

📉 VERDICT: [BUY/SELL/WAIT with reasoning]
```

**✅ Success Criteria:**
- [ ] Shows **S&P 500** with percentage change
- [ ] Shows **BTC Dominance** (e.g., 57.4%)
- [ ] Shows **Crypto Fear & Greed** (e.g., 38/100)
- [ ] Displays **5 Bitcoin signals** (not just 2)
- [ ] Timestamp is **fresh** (within last 5 minutes)
- [ ] Provides **Bitcoin-specific verdict**

---

#### **2D: Test Gold Analysis**

**Ask ChatGPT:**
```
What's the market context for Gold?
```

**What you should see:**

```
🌍 Market Context — Gold (XAUUSD)
📅 Data as of: 2025-10-14 13:41:18 UTC

📊 Macro Fundamentals:
DXY: 99.18 (📉 Falling)
→ USD weakening → ✅ Bullish for Gold

US10Y: 4.051% (📉 Falling)
→ Lower yields → ✅ More Gold demand

VIX: 21.99 (⚠️ High)
→ Elevated volatility

S&P 500: 6654.72 (+1.56%)         ← NEW (bonus context)
→ Risk-on sentiment

🎯 Gold Outlook: 🟢🟢 STRONG BULLISH
Both DXY and US10Y falling → DOUBLE TAILWIND!
```

**✅ Success Criteria:**
- [ ] Shows traditional signals (DXY, US10Y, VIX)
- [ ] Now also shows **S&P 500** (bonus)
- [ ] Provides **Gold-specific verdict**
- [ ] Timestamp is fresh

---

## 🧪 Advanced Tests

### **Test 3: Data Freshness Check**

**Ask ChatGPT:**
```
What's Bitcoin's price? Is that data fresh?
```

**Expected:**
```
Current Bitcoin Price: $[PRICE]
📅 Data fetched at: 2025-10-14 13:41:18 UTC (2 minutes ago)

✅ Yes, this data is fresh from your MT5 broker feed.
```

**What to verify:**
- ✅ ChatGPT displays the timestamp
- ✅ Timestamp is within last 5 minutes
- ✅ NO phrases like "I'll pull fresh data"

---

### **Test 4: Multi-Signal Verdict**

**Ask ChatGPT:**
```
Should I buy Bitcoin right now?
```

**Expected reasoning:**
```
📊 Analyzing 5 Bitcoin signals:

1. VIX: 21.99 (RISK_OFF) → ⚠️ Bearish
2. S&P 500: +1.56% (RISING) → ✅ Bullish
3. DXY: 99.18 (FALLING) → ✅ Bullish
4. BTC Dominance: 57.4% (STRONG) → ✅ Bullish
5. Crypto Fear & Greed: 38/100 (Fear) → ⚠️ Mixed

Result: 3 of 5 signals bullish

🏛️ SMC Analysis:
[Technical confluence...]

📉 VERDICT: [BUY/WAIT/SELL]
Macro shows mixed signals (elevated VIX but positive equity momentum).
Wait for [specific technical level] for confirmation.
```

**✅ Success Criteria:**
- [ ] All 5 signals analyzed individually
- [ ] Signal count tallied (e.g., "3 of 5 bullish")
- [ ] Macro integrated with SMC
- [ ] Specific action plan provided

---

## 🔧 Troubleshooting

### **Problem: S&P 500 missing**

**Symptoms:**
```
[FAIL] S&P 500
```

**Cause:** Yahoo Finance API timeout or network issue

**Fix:**
```python
# Test manually:
import yfinance as yf
sp500 = yf.Ticker("^GSPC")
print(sp500.history(period="1d")['Close'].iloc[-1])
```

If this fails → Check internet connection or try again in 1 minute

---

### **Problem: BTC Dominance missing**

**Symptoms:**
```
[FAIL] BTC Dominance
```

**Cause:** CoinGecko rate limit (50 calls/min) or network block

**Fix:**
```bash
# Test manually:
curl https://api.coingecko.com/api/v3/global
```

If fails:
1. Wait 1 minute (rate limit)
2. Check firewall settings
3. Try from different network

---

### **Problem: Crypto Fear & Greed missing**

**Symptoms:**
```
[FAIL] Crypto Fear & Greed
```

**Cause:** Alternative.me API down (rare)

**Fix:**
```bash
# Test manually:
curl https://api.alternative.me/fng/
```

If fails:
1. Wait 5 minutes
2. Check https://alternative.me/crypto/fear-and-greed-index/ in browser
3. If site down, system will continue without it

---

### **Problem: ChatGPT not showing new fields**

**Symptoms:** ChatGPT only shows VIX and DXY for Bitcoin

**Cause:** Old knowledge documents loaded

**Fix:**
1. Re-upload these files to ChatGPT:
   - `openai.yaml` ✅
   - `CUSTOM_GPT_INSTRUCTIONS_CONCISE_SMC.md` ✅
   - `ChatGPT_Knowledge_Document.md` ✅
   - `BTCUSD_ANALYSIS_QUICK_REFERENCE.md` ✅

2. Edit ChatGPT instructions to add:
```
For Bitcoin analysis, MUST display all 5 signals:
1. VIX (risk sentiment)
2. S&P 500 (equity correlation)
3. DXY (USD strength)
4. BTC Dominance (crypto sentiment)
5. Crypto Fear & Greed Index (sentiment score)
```

---

### **Problem: Old version of desktop_agent.py**

**Symptoms:** quick_test.py fails with errors

**Cause:** Code not updated

**Fix:**
```bash
git pull origin main
git log --oneline -n 1
# Should show: "feat: Add S&P 500, Bitcoin Dominance..."
```

If not on latest:
```bash
git fetch origin
git reset --hard origin/main
```

---

## 📊 What Success Looks Like

### **Backend (quick_test.py):**
```
[PASS] VIX
[PASS] DXY
[PASS] US10Y
[PASS] S&P 500               ← NEW
[PASS] BTC Dominance         ← NEW
[PASS] Crypto Fear & Greed   ← NEW
[PASS] Bitcoin Verdict       ← NEW

Result: 7/7 checks passed
```

### **ChatGPT:**
- Shows **5 Bitcoin signals** (not 2)
- Includes **S&P 500 with % change**
- Shows **BTC Dominance** interpretation
- Displays **Crypto Fear & Greed** score
- Provides **Bitcoin-specific verdict**
- Timestamp is **fresh** (<5 min old)

### **Performance:**
- Latency: 2-4 seconds
- Cost: $0/month
- Success rate: 95%+ (occasional API timeouts OK)

---

## ✅ Final Checklist

Before going live:

- [ ] Run `python quick_test.py` → All pass
- [ ] Desktop agent running → No errors in logs
- [ ] Ngrok tunnel running → URL accessible
- [ ] ChatGPT configured → Knowledge docs uploaded
- [ ] Ask "Analyse Bitcoin" → Shows 5 signals
- [ ] Ask "Analyse Gold" → Shows macro verdict
- [ ] Timestamp always fresh → Within 5 minutes
- [ ] No "I'll pull data" phrases → ChatGPT pulls immediately

---

## 🚀 Ready to Trade!

Once all tests pass, you have:
- ✅ **Institutional-grade Bitcoin analysis**
- ✅ **5 comprehensive signals** (VIX, S&P 500, DXY, BTC.D, F&G)
- ✅ **Auto-calculated verdicts** (BULLISH/BEARISH for Crypto)
- ✅ **Real-time data** (no stale prices)
- ✅ **FREE data sources** (Yahoo Finance, CoinGecko, Alternative.me)

**Next:** Start asking ChatGPT for Bitcoin trade recommendations! 🎯

