# Testing Enhanced Macro Context with S&P 500, BTC Dominance, and Crypto Fear & Greed

## ✅ Test 1: Local API Test (Desktop Agent)

### **Purpose:** Verify desktop_agent.py returns all new data fields

**Steps:**
1. Open terminal in project directory
2. Run test script:
```bash
python test_macro_context_enhanced.py
```

**Expected Results:**
- ✅ Test 1: General macro context - PASSED
- ✅ Test 2: Gold-specific context - PASSED
- ✅ Test 3: Bitcoin-specific context - PASSED
- ✅ Test 4: Data completeness check - PASSED

**What to verify:**
- DXY, US10Y, VIX present
- **S&P 500** present with % change
- **BTC Dominance** present (e.g., 57.3%)
- **Crypto Fear & Greed** present (e.g., 38/100)
- Bitcoin verdict: "🟢 BULLISH for Crypto" or similar

---

## ✅ Test 2: Ngrok Tunnel Test (API Accessibility)

### **Purpose:** Verify ChatGPT can reach your local API

**Steps:**
1. Start ngrok (if not already running):
```bash
ngrok http 8000
```

2. Copy ngrok URL (e.g., `https://verbally-faithful-monster.ngrok-free.app`)

3. Test the macro_context endpoint:
```bash
curl -X POST https://verbally-faithful-monster.ngrok-free.app/dispatch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "tool": "moneybot.macro_context",
    "arguments": {"symbol": "BTCUSD"}
  }'
```

**Expected Response:**
```json
{
  "status": "success",
  "result": {
    "summary": "🌍 Macro Market Context\n\n📊 Traditional Markets:\nDXY: 99.15 📉 Falling\n...",
    "data": {
      "dxy": 99.15,
      "vix": 21.78,
      "sp500": 6654.72,
      "sp500_change_pct": 1.56,
      "btc_dominance": 57.3,
      "crypto_fear_greed": 38,
      "crypto_sentiment": "Fear",
      "symbol_context": "🟢 BULLISH for Crypto...",
      "timestamp_human": "2025-10-14 13:26:45 UTC"
    }
  }
}
```

**What to verify:**
- `status: "success"`
- All new fields present in `data` object
- `timestamp_human` is recent (within last 5 minutes)
- Bitcoin-specific `symbol_context` is present

---

## ✅ Test 3: ChatGPT Integration Test

### **Purpose:** Verify Custom GPT can call the enhanced API and display results

**Prerequisites:**
1. ✅ Desktop agent running (`python desktop_agent.py`)
2. ✅ Ngrok tunnel active
3. ✅ ChatGPT configured with:
   - Updated `openai.yaml` uploaded
   - Bearer token configured
   - Actions connected to ngrok URL

### **Test 3A: Bitcoin Analysis**

**Ask ChatGPT:**
```
Analyse Bitcoin please
```

**Expected ChatGPT Response Should Include:**

```
₿ Bitcoin Analysis — BTCUSD
📅 Data as of: [RECENT TIMESTAMP]

📊 Risk Sentiment:
VIX: [VALUE] ([Risk-on/Risk-off])
S&P 500: [TREND] (+X.XX%) → Correlation +0.70
DXY: [VALUE] ([TREND]) → [Impact]

🔷 Crypto Fundamentals:
BTC Dominance: XX.X% ([STRONG/WEAK/NEUTRAL])
Crypto Fear & Greed: XX/100 ([Fear/Greed/etc])

🎯 Sentiment Outlook: [🟢 BULLISH / 🔴 BEARISH / ⚪ NEUTRAL]

🏛️ Bitcoin Structure (SMC):
[CHOCH/BOS analysis]
[Order Blocks]
[Liquidity Pools]

📉 VERDICT: [BUY/SELL/WAIT]
[Reasoning with macro + SMC]

🎯 Trade Plan:
Entry: $[PRICE]
Stop Loss: $[PRICE]
TP1/TP2: $[PRICES]
```

**What to verify:**
- ✅ Shows **5 Bitcoin signals** (VIX, S&P 500, DXY, BTC.D, Crypto F&G)
- ✅ Includes **S&P 500 percentage change**
- ✅ Shows **BTC Dominance** with interpretation (STRONG/WEAK)
- ✅ Displays **Crypto Fear & Greed** score (0-100)
- ✅ Provides **Bitcoin-specific verdict** (BULLISH/BEARISH for Crypto)
- ✅ Timestamp is fresh (not stale data)
- ✅ Integrates macro with SMC analysis

---

### **Test 3B: Gold Analysis**

**Ask ChatGPT:**
```
What's the market context for Gold?
```

**Expected ChatGPT Response Should Include:**

```
🌍 Market Context — Gold (XAUUSD)
📅 Data as of: [RECENT TIMESTAMP]

📊 Macro Fundamentals:
DXY: [VALUE] ([TREND])
→ [Bullish/Bearish impact on Gold]

US10Y: [VALUE]% ([TREND])
→ [Impact on Gold]

VIX: [VALUE] ([High/Normal/Low])
→ [Volatility context]

S&P 500: [VALUE] (+X.XX%)
→ [Risk sentiment]

🎯 Gold Outlook: [🟢🟢 STRONG BULLISH / 🔴🔴 STRONG BEARISH / ⚪ MIXED]
[3-signal confluence explanation]

📊 Technical Confluence: [Score]/100

📈 Verdict: [BUY/SELL/WAIT]
[Macro reasoning]
```

**What to verify:**
- ✅ Shows **DXY, US10Y, VIX** (traditional Gold signals)
- ✅ Now also shows **S&P 500** (bonus context)
- ✅ Provides **Gold-specific verdict** (BULLISH/BEARISH for Gold)
- ✅ Timestamp is fresh
- ✅ Macro integrated with technical analysis

---

### **Test 3C: Stale Data Check**

**Purpose:** Verify ChatGPT never uses cached/stale data

**Ask ChatGPT:**
```
What's Bitcoin's price right now?
```

**Then immediately ask:**
```
Is that data fresh? When was it fetched?
```

**Expected Response:**
```
Yes, the data is fresh! ✅
📅 Fetched at: [TIMESTAMP within last 1-2 minutes]

This data comes directly from your MT5 broker feed, not external sources.
```

**What to verify:**
- ✅ ChatGPT displays the `timestamp_human` field
- ✅ Timestamp is within last 2 minutes
- ✅ No "I'll pull fresh data" responses
- ✅ No external source citations (TradingView, Investing.com)

---

## ✅ Test 4: Data Source Verification

### **Purpose:** Verify all 3 new data sources are working

**Steps:**

1. **Check S&P 500 (Yahoo Finance):**
```python
import yfinance as yf
sp500 = yf.Ticker("^GSPC")
print(sp500.history(period="1d")['Close'].iloc[-1])
```
Expected: Recent S&P 500 price (e.g., 5800-5900)

2. **Check BTC Dominance (CoinGecko):**
```python
import requests
response = requests.get("https://api.coingecko.com/api/v3/global")
btc_dom = response.json()["data"]["market_cap_percentage"]["btc"]
print(f"BTC Dominance: {btc_dom}%")
```
Expected: BTC dominance 40-60% range

3. **Check Crypto Fear & Greed (Alternative.me):**
```python
import requests
response = requests.get("https://api.alternative.me/fng/")
fg_value = response.json()["data"][0]["value"]
fg_sentiment = response.json()["data"][0]["value_classification"]
print(f"Fear & Greed: {fg_value}/100 ({fg_sentiment})")
```
Expected: Score 0-100 with classification

**What to verify:**
- ✅ All 3 APIs respond (no 404/500 errors)
- ✅ Data is reasonable (not zeros or nulls)
- ✅ No API key required (all free)

---

## ✅ Test 5: Error Handling

### **Purpose:** Verify graceful degradation if APIs fail

**Test 5A: Simulate CoinGecko Failure**

**Steps:**
1. Temporarily block CoinGecko (optional):
   - Add `127.0.0.1 api.coingecko.com` to hosts file
2. Ask ChatGPT: "Analyse Bitcoin"

**Expected Behavior:**
- ✅ Macro context still returns (doesn't crash)
- ✅ DXY, VIX, S&P 500, US10Y still present
- ✅ `btc_dominance` may be `null` or fallback value
- ✅ ChatGPT proceeds with available data
- ✅ Warning logged: "⚠️ Failed to fetch BTC Dominance"

**Test 5B: All Crypto APIs Fail**

**Expected Behavior:**
- ✅ Traditional macro data still works (DXY, VIX, US10Y, S&P)
- ✅ ChatGPT can still analyze Gold
- ✅ Bitcoin analysis proceeds with 3/5 signals (VIX, S&P, DXY)
- ✅ No crash or empty response

---

## ✅ Test 6: Performance Test

### **Purpose:** Verify acceptable latency

**Steps:**
1. Time a macro_context call:
```python
import time
start = time.time()
result = await tool_macro_context({"symbol": "BTCUSD"})
end = time.time()
print(f"Latency: {end - start:.2f} seconds")
```

**Expected Latency:**
- ✅ **2-4 seconds** (acceptable for comprehensive analysis)
- Breakdown:
  - Yahoo Finance (3 calls): ~1-2 seconds
  - CoinGecko: ~0.5 seconds
  - Alternative.me: ~0.5 seconds

**Tolerance:**
- ✅ <5 seconds = Good
- ⚠️ 5-10 seconds = Acceptable (network delays)
- 🔴 >10 seconds = Check network/API issues

---

## ✅ Test 7: Real Trading Scenario

### **Purpose:** End-to-end test with trade recommendation

**Ask ChatGPT:**
```
I want to trade Bitcoin. Give me a full analysis with entry, stop loss, and take profit.
```

**Expected Flow:**
1. ✅ ChatGPT calls `moneybot.macro_context(symbol: "BTCUSD")`
2. ✅ Gets VIX, S&P 500, DXY, BTC.D, Crypto F&G
3. ✅ Calculates sentiment: BULLISH/BEARISH/MIXED
4. ✅ Calls `moneybot.analyse_symbol(symbol: "BTCUSD")`
5. ✅ Gets SMC analysis (CHOCH, BOS, Order Blocks, Liquidity)
6. ✅ Combines macro + SMC
7. ✅ Provides specific trade plan:
   - Entry price with reasoning
   - Stop loss (beyond invalidation level)
   - TP1 and TP2 (at liquidity pools)
   - R:R ratio
   - Position size recommendation

**What to verify:**
- ✅ Macro sentiment matches technical verdict (or explains conflict)
- ✅ All 5 Bitcoin signals mentioned
- ✅ Specific entry levels (not generic)
- ✅ SMC terminology used (Order Blocks, CHOCH, BOS)
- ✅ Trade plan is actionable

---

## 🐛 Troubleshooting Guide

### **Issue 1: ChatGPT says "data feed not available"**

**Cause:** Ngrok tunnel down or desktop agent not running

**Fix:**
1. Check ngrok is running: `ngrok http 8000`
2. Check desktop_agent is running: `python desktop_agent.py`
3. Verify ngrok URL in ChatGPT actions matches current tunnel

---

### **Issue 2: Missing S&P 500, BTC Dominance, or Crypto F&G**

**Cause:** Old version of desktop_agent.py still running

**Fix:**
1. Stop desktop_agent (Ctrl+C)
2. Pull latest code: `git pull origin main`
3. Restart: `python desktop_agent.py`
4. Verify commit: `git log --oneline -n 1` (should show "feat: Add S&P 500...")

---

### **Issue 3: BTC Dominance always null**

**Cause:** CoinGecko API rate limit or network block

**Fix:**
1. Test manually: `curl https://api.coingecko.com/api/v3/global`
2. If fails: Wait 1 minute (rate limit: 50 calls/min)
3. If blocked: Check firewall/antivirus settings

---

### **Issue 4: ChatGPT not using new fields**

**Cause:** Old knowledge documents still loaded

**Fix:**
1. Re-upload all knowledge documents to ChatGPT:
   - `openai.yaml`
   - `CUSTOM_GPT_INSTRUCTIONS_CONCISE_SMC.md`
   - `ChatGPT_Knowledge_Document.md`
   - `BTCUSD_ANALYSIS_QUICK_REFERENCE.md`
2. Edit ChatGPT instructions to explicitly mention:
   - "MUST use S&P 500 for Bitcoin analysis"
   - "MUST display BTC Dominance and Crypto Fear & Greed"

---

### **Issue 5: Stale timestamp showing**

**Cause:** ChatGPT caching response or not calling API

**Fix:**
1. Check ChatGPT instructions include: "ALWAYS display timestamp_human"
2. Ask: "Pull fresh data for Bitcoin right now"
3. Verify `cache_control: no-cache` header in API response

---

## ✅ Success Criteria Checklist

### **Desktop Agent (Backend):**
- [ ] All 4 tests pass in `test_macro_context_enhanced.py`
- [ ] S&P 500 fetched successfully (Yahoo Finance)
- [ ] BTC Dominance fetched successfully (CoinGecko)
- [ ] Crypto Fear & Greed fetched successfully (Alternative.me)
- [ ] No errors in desktop_agent logs
- [ ] Latency <5 seconds per call

### **API Integration:**
- [ ] Ngrok tunnel accessible
- [ ] `/dispatch` endpoint returns all new fields
- [ ] `timestamp_human` is recent (<2 min old)
- [ ] Bitcoin `symbol_context` includes all 5 signals

### **ChatGPT Behavior:**
- [ ] Displays all 5 Bitcoin signals (VIX, S&P, DXY, BTC.D, F&G)
- [ ] Shows S&P 500 percentage change
- [ ] Interprets BTC Dominance (STRONG/WEAK/NEUTRAL)
- [ ] Displays Crypto Fear & Greed with sentiment
- [ ] Provides Bitcoin-specific verdict
- [ ] Always shows fresh timestamp
- [ ] Integrates macro + SMC in recommendations
- [ ] Never says "I'll pull fresh data" (just pulls it)

### **Error Handling:**
- [ ] Continues if CoinGecko fails
- [ ] Continues if Alternative.me fails
- [ ] Logs warnings for missing data
- [ ] Never crashes on API failures

---

## 📊 Quick Test Script

Run this to verify everything at once:

```bash
# 1. Test local functionality
python test_macro_context_enhanced.py

# 2. Test API endpoint (replace with your ngrok URL and API key)
curl -X POST https://YOUR-NGROK-URL/dispatch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"tool": "moneybot.macro_context", "arguments": {"symbol": "BTCUSD"}}'

# 3. Check desktop agent logs for errors
# Look for "✅ S&P 500 fetched", "✅ BTC Dominance fetched", "✅ Crypto Fear & Greed fetched"
```

---

## 🎯 Expected Output Summary

When everything is working correctly:

**For Bitcoin:**
- 5 signals: VIX 21.8, S&P +1.56%, DXY 99.15, BTC.D 57.3%, F&G 38/100
- Verdict: "🟢 BULLISH for Crypto (3 of 5 bullish)"
- Timestamp: Within last 2 minutes

**For Gold:**
- 3 primary signals: DXY 99.15, US10Y 4.05%, VIX 21.78
- 2 bonus signals: S&P 500, Crypto sentiment
- Verdict: "🟢 BULLISH for Gold (DXY↓ + Yields↓)"

**Latency:**
- Macro context call: 2-4 seconds
- Total ChatGPT response: 5-10 seconds

**Cost:**
- $0/month (all APIs free)

---

**Status:** ✅ Ready to test!  
**Last Updated:** 2025-10-14  
**Implementation:** Phase 1 (Code) + Phase 2 (Docs) COMPLETE

