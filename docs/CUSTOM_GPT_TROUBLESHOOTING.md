# Custom GPT Troubleshooting Guide

## Issue: Custom GPT Not Fetching DXY, VIX, US10Y Data

### Problem Description
The Custom GPT says things like:
- "Perfect — as soon as the live macro feed is back online, I'll pull fresh data..."
- "once the data feed is restored..."
- "I'll combine this with macro analysis..."

**Instead of actually calling the APIs immediately.**

---

## Root Causes & Solutions

### 1. ✅ **Actions Not Enabled**

**Symptom:** Custom GPT doesn't make any API calls, just talks about what it will do.

**Check:**
1. Open Custom GPT settings
2. Go to **Configure** → **Actions**
3. Verify Actions are listed and enabled
4. Check "Privacy" setting - should allow API calls

**Fix:**
1. Make sure `openai.yaml` schema is pasted in Actions
2. Verify the server URL is correct (ngrok URL)
3. Test the schema - look for green checkmarks

---

### 2. ✅ **Server Not Running**

**Symptom:** Custom GPT tries to call API but gets errors.

**Check:**
```powershell
# Check if server is running
netstat -ano | findstr :8000
```

**Fix:**
```powershell
cd c:\mt5-gpt\TelegramMoneyBot.v7
python main_api.py
```

**Expected output:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

### 3. ✅ **ngrok Not Running**

**Symptom:** Custom GPT gets "Connection refused" or "Host not found" errors.

**Check:**
```powershell
# Check if ngrok is running
tasklist | findstr ngrok
```

**Fix:**
```powershell
# Start ngrok
ngrok http 8000
```

**Copy the URL** (e.g., `https://verbally-faithful-monster.ngrok-free.app`)

**Update Custom GPT:**
1. Go to Custom GPT → Configure → Actions
2. Update the server URL to the new ngrok URL
3. Click Save

---

### 4. ✅ **Instructions Not Clear Enough**

**Symptom:** Custom GPT understands it should fetch data but doesn't prioritize it.

**Fix:** Update Instructions with explicit anti-patterns:

```markdown
### ❌ NEVER SAY THESE PHRASES:
- "once the data feed is restored"
- "I'll pull fresh data"
- "as soon as the feed is back online"
- "when the macro data is available"

### ✅ ALWAYS DO THIS INSTEAD:
- IMMEDIATELY call getCurrentPrice("DXY")
- IMMEDIATELY call getCurrentPrice("US10Y")
- IMMEDIATELY call getCurrentPrice("VIX")
- NO PROMISES - FETCH NOW!
```

**Already added to your Instructions file.**

---

### 5. ✅ **API Call Failures (Silent)**

**Symptom:** Custom GPT tries to call APIs but they fail silently, so it assumes data is unavailable.

**Check Server Logs:**
```powershell
# Look for errors in the terminal where main_api.py is running
# Should see lines like:
# INFO:     74.7.36.79:0 - "GET /api/v1/price/DXY HTTP/1.1" 200 OK
```

**Check for Errors:**
```powershell
# Look for these error messages:
[ERROR] __main__: Error getting price for DXY: ...
```

**Test API Directly:**
```powershell
# Test DXY endpoint
curl http://localhost:8000/api/v1/price/DXY

# Expected response:
# {
#   "symbol": "DXY",
#   "bid": 99.427,
#   "ask": 99.427,
#   "mid": 99.427,
#   "spread": 0.0,
#   "timestamp": "2025-10-09T...",
#   "digits": 3,
#   "source": "Yahoo Finance (DX-Y.NYB)",
#   "note": "Real DXY from Yahoo Finance - broker doesn't provide DXY"
# }
```

**If API Returns Error:**
- Check internet connection
- Verify `yfinance` package is installed: `pip install yfinance`
- Check Yahoo Finance is accessible (not blocked by firewall)

---

### 6. ✅ **Custom GPT Context Window**

**Symptom:** In long conversations, Custom GPT "forgets" the instructions.

**Fix:**
1. Start a **new conversation** with Custom GPT
2. Test immediately: "What's the market context for Gold?"
3. If it works in new conversation but not old one → Context issue

**Solution:** Periodically remind in conversation:
```
For all Gold questions, you MUST call:
- getCurrentPrice("DXY")
- getCurrentPrice("US10Y")  
- getCurrentPrice("VIX")
- getCurrentPrice("XAUUSD")
IMMEDIATELY, not later!
```

---

### 7. ✅ **Schema Description Too Vague**

**Symptom:** Custom GPT doesn't understand when to use which endpoint.

**Fix:** Already updated `openai.yaml` with explicit Gold protocol:

```yaml
⚠️ CRITICAL GOLD ANALYSIS PROTOCOL:
When user asks about Gold (any question - price, context, analysis, trade ideas):
YOU MUST IMMEDIATELY CALL THESE 4 APIs IN PARALLEL:
1. getCurrentPrice(symbol: "DXY") - US Dollar Index
2. getCurrentPrice(symbol: "US10Y") - Treasury Yield  
3. getCurrentPrice(symbol: "VIX") - Volatility Index
4. getCurrentPrice(symbol: "XAUUSD") - Gold price

NEVER say "once the data feed is restored" - the feed is ALWAYS available!
NEVER say "I'll pull fresh data" - PULL IT IMMEDIATELY!
```

---

## How to Diagnose in Real-Time

### Step 1: Test the API Endpoint
```powershell
# Test DXY
curl http://localhost:8000/api/v1/price/DXY

# Test US10Y
curl http://localhost:8000/api/v1/price/US10Y

# Test VIX
curl http://localhost:8000/api/v1/price/VIX
```

**Expected:** All 3 should return valid JSON with prices.

**If Error:** Fix the API endpoint first (server/ngrok/Yahoo Finance).

---

### Step 2: Test Custom GPT Action

1. Ask Custom GPT: **"Call getCurrentPrice with symbol DXY"**
2. Look for: **"Talked to [your-ngrok-url]"**
3. Check response: Should show DXY price

**If No "Talked to" Message:**
- Actions are not enabled
- Schema is invalid
- Server URL is wrong

**If "Error talking to connector":**
- Server is not running
- ngrok is not running
- Firewall blocking connection

---

### Step 3: Test Gold Question

1. Start **new conversation** with Custom GPT
2. Ask: **"What's the market context for Gold?"**
3. Verify it **immediately** shows:
   - "Talked to [ngrok-url]" (multiple times for DXY, US10Y, VIX, XAUUSD)
   - Current DXY price
   - Current US10Y yield
   - Current VIX level
   - 3-signal Gold outlook (🟢🟢/🔴🔴/⚪)

**If It Says "I'll pull fresh data":**
- Instructions are not being followed
- Update Instructions with the explicit anti-patterns (see Fix #4)
- Try starting a brand new conversation

---

## Quick Test Script

Save this as `test_custom_gpt_api.ps1`:

```powershell
Write-Host "Testing Custom GPT API Endpoints..." -ForegroundColor Cyan

Write-Host "`n1. Testing DXY..." -ForegroundColor Yellow
curl http://localhost:8000/api/v1/price/DXY

Write-Host "`n2. Testing US10Y..." -ForegroundColor Yellow
curl http://localhost:8000/api/v1/price/US10Y

Write-Host "`n3. Testing VIX..." -ForegroundColor Yellow
curl http://localhost:8000/api/v1/price/VIX

Write-Host "`n4. Testing XAUUSD..." -ForegroundColor Yellow
curl http://localhost:8000/api/v1/price/XAUUSD

Write-Host "`nAll tests complete!" -ForegroundColor Green
```

Run it:
```powershell
cd c:\mt5-gpt\TelegramMoneyBot.v7
powershell -ExecutionPolicy Bypass -File test_custom_gpt_api.ps1
```

---

## Expected vs Actual Behavior

### ❌ Current Behavior (Wrong):
```
User: "What's the market context for Gold?"

GPT: "📉 Verdict:
Gold (XAUUSD) is currently neutral to bearish...
Wait for DXY and US10Y context or a technical breakout...

👉 Would you like me to combine this with macro analysis 
(DXY, US10Y, VIX) once the data feed is restored to 
confirm the bias?"

User: "yes"

GPT: "Perfect 👌 — as soon as the live macro feed 
(for DXY, US10Y, and VIX) is back online, I'll pull 
fresh data and give you a full 3-signal Gold outlook..."
```

**Problem:** Promising to fetch data "later" instead of fetching NOW.

---

### ✅ Expected Behavior (Correct):
```
User: "What's the market context for Gold?"

GPT: [Immediately calls APIs]
- getCurrentPrice("DXY")
- getCurrentPrice("US10Y")
- getCurrentPrice("VIX")
- getCurrentPrice("XAUUSD")

[Shows "Talked to verbally-faithful-monster.ngrok-free.app" 4 times]

GPT: "🌍 Market Context — Gold (XAUUSD)
Current Price: $3,962.78

📊 Macro Fundamentals:
DXY: 99.427 (Rising)
→ USD strengthening → Bearish for Gold

US10Y: 4.148% (Rising)
→ Rising yields → Bearish for Gold

VIX: 17.06 (Normal)

🎯 Gold Outlook: 🔴🔴 STRONG BEARISH
Both DXY and US10Y against Gold

📉 Verdict: WAIT - Don't buy Gold now
Macro fundamentals strongly bearish.

👉 Would you like me to set an alert when DXY reverses?"
```

**Correct:** Fetches data IMMEDIATELY, shows live prices, provides verdict.

---

## Final Checklist

Before asking Custom GPT about Gold:

- [ ] Server running (`python main_api.py`)
- [ ] ngrok running (`ngrok http 8000`)
- [ ] Actions enabled in Custom GPT settings
- [ ] `openai.yaml` updated with latest schema
- [ ] Instructions updated with anti-patterns
- [ ] API endpoints working (test with curl)
- [ ] Start new conversation (avoid context issues)

Then ask: **"What's the market context for Gold?"**

**Look for:** "Talked to [ngrok-url]" messages (should see 4 of them).

**If still not working:** Reply to this thread with:
1. Screenshot of Custom GPT response
2. Server logs (from terminal where `main_api.py` is running)
3. Result of `curl http://localhost:8000/api/v1/price/DXY`

---

## Immediate Action Items

1. **Update Custom GPT Instructions:**
   - Copy `CUSTOM_GPT_INSTRUCTIONS_CONCISE.md` to Instructions field
   - Includes the new anti-patterns (already done)

2. **Update Custom GPT Actions:**
   - Copy `openai.yaml` to Actions schema
   - Includes the explicit Gold protocol (already done)

3. **Test API Endpoints:**
   ```powershell
   curl http://localhost:8000/api/v1/price/DXY
   curl http://localhost:8000/api/v1/price/US10Y
   curl http://localhost:8000/api/v1/price/VIX
   ```

4. **Start New Conversation:**
   - Open Custom GPT
   - Start brand new conversation
   - Ask: "What's the market context for Gold?"
   - Verify it shows "Talked to..." and live prices

---

**Status:** Ready to test! 🚀

