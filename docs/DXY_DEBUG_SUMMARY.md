# DXY/VIX/US10Y Not Working - Debug Summary

## Issue
Custom GPT is not fetching DXY, VIX, and US10Y data. When testing the API endpoint directly, we get:
```json
{"detail":"Symbol not found: DXYc"}
```

This error indicates the API is trying to fetch "DXYc" from MT5 instead of routing DXY to Yahoo Finance.

---

## Root Cause Investigation

### 1. Code is Correct
The routing logic in `main_api.py` lines 926-962 correctly checks for DXY and routes to Yahoo Finance:
```python
if symbol.upper() in ['DXY', 'DXYC', 'DX-Y.NYB']:
    # Fetch from Yahoo Finance
```

### 2. Service Works
Testing the service directly works fine:
```bash
python -c "from infra.market_indices_service import create_market_indices_service; indices = create_market_indices_service(); dxy = indices.get_dxy(); print(dxy)"
# Output: {'price': 99.472, 'trend': 'up', ...}
```

### 3. API Endpoint Fails
But calling the HTTP endpoint fails:
```bash
curl http://localhost:8000/api/v1/price/DXY
# Returns: {"detail":"Symbol not found: DXYc"}
```

---

## Debug Steps Added

I've added logging to `main_api.py` to diagnose the issue:

```python
logger.info(f"Price request for symbol: {symbol}, uppercase: {symbol.upper()}")

if symbol.upper() in ['DXY', 'DXYC', 'DX-Y.NYB']:
    logger.info(f"Routing {symbol} to Yahoo Finance (DXY)")
    # ... fetch logic
    logger.info(f"DXY price fetched successfully: {price}")
```

---

## Next Steps

### Step 1: Restart Server
You need to restart the server to pick up the debug logging:

1. **Stop the current server:**
   - Find the terminal where `python main_api.py` is running
   - Press `Ctrl+C`

2. **Start the server again:**
   ```bash
   cd c:\mt5-gpt\TelegramMoneyBot.v7
   python main_api.py
   ```

### Step 2: Test Again
After restarting, run this test:

```bash
cd c:\mt5-gpt\TelegramMoneyBot.v7
python -c "import requests; response = requests.get('http://localhost:8000/api/v1/price/DXY'); print('Status:', response.status_code); print('Response:', response.json())"
```

### Step 3: Check Server Logs
Look at the terminal where `main_api.py` is running. You should see:

**If routing works:**
```
INFO: Price request for symbol: DXY, uppercase: DXY
INFO: Routing DXY to Yahoo Finance (DXY)
INFO: DXY price fetched successfully: 99.472
INFO:     127.0.0.1:xxxxx - "GET /api/v1/price/DXY HTTP/1.1" 200 OK
```

**If routing doesn't work:**
```
INFO: Price request for symbol: DXY, uppercase: DXY
[No "Routing" message - check falls through to MT5 section]
ERROR: Symbol not found: DXYc
INFO:     127.0.0.1:xxxxx - "GET /api/v1/price/DXY HTTP/1.1" 500 Internal Server Error
```

---

## Possible Issues

### Issue A: Server Not Restarted
**Symptom:** Changes to code don't take effect  
**Solution:** Always restart server after code changes (unless using `--reload` flag)

### Issue B: Wrong File Being Executed
**Symptom:** Code looks correct but doesn't work  
**Solution:** Verify you're running the correct `main_api.py`:
```bash
cd c:\mt5-gpt\TelegramMoneyBot.v7
python main_api.py
```

### Issue C: Import Error
**Symptom:** Exception in try block causes fallthrough  
**Solution:** Check server logs for import errors or exceptions

### Issue D: yfinance Not Installed
**Symptom:** Yahoo Finance fetch fails  
**Solution:**
```bash
pip install yfinance
```

---

## Expected Behavior After Fix

### Test 1: DXY
```bash
curl http://localhost:8000/api/v1/price/DXY
```

**Expected Response:**
```json
{
  "symbol": "DXY",
  "bid": 99.472,
  "ask": 99.472,
  "mid": 99.472,
  "spread": 0.0,
  "timestamp": "2025-10-09T21:51:20",
  "digits": 3,
  "source": "Yahoo Finance (DX-Y.NYB)",
  "note": "Real DXY from Yahoo Finance - broker doesn't provide DXY"
}
```

### Test 2: US10Y
```bash
curl http://localhost:8000/api/v1/price/US10Y
```

**Expected Response:**
```json
{
  "symbol": "US10Y",
  "bid": 4.148,
  "ask": 4.148,
  "mid": 4.148,
  "spread": 0.0,
  "timestamp": "2025-10-09T21:51:20",
  "digits": 3,
  "source": "Yahoo Finance (^TNX)",
  "note": "Real US10Y from Yahoo Finance - broker doesn't provide US10Y",
  "gold_correlation": "inverse"
}
```

### Test 3: VIX
```bash
curl http://localhost:8000/api/v1/price/VIX
```

**Expected Response:**
```json
{
  "symbol": "VIX",
  "bid": 17.06,
  "ask": 17.06,
  "mid": 17.06,
  "spread": 0.0,
  "timestamp": "2025-10-09T21:51:20",
  "digits": 2,
  "source": "Yahoo Finance (^VIX)",
  "note": "Real VIX from Yahoo Finance - broker doesn't provide VIX"
}
```

---

## Once APIs Work

After confirming the APIs work, test the Custom GPT:

1. **Update Custom GPT** with the latest files:
   - `openai.yaml` → Actions
   - `CUSTOM_GPT_INSTRUCTIONS_CONCISE.md` → Instructions
   - `ChatGPT_Knowledge_Document.md` → Knowledge

2. **Start new conversation** with Custom GPT

3. **Ask:** "What's the market context for Gold?"

4. **Expected:** Custom GPT should:
   - Show "Talked to [ngrok-url]" (4 times for DXY, US10Y, VIX, XAUUSD)
   - Display current DXY price (e.g., 99.472)
   - Display current US10Y yield (e.g., 4.148%)
   - Display current VIX level (e.g., 17.06)
   - Calculate 3-signal Gold outlook (🟢🟢/🔴🔴/⚪)
   - Provide specific BUY/SELL/WAIT verdict

---

## Files Updated in This Session

1. ✅ `openai.yaml` - Added explicit Gold analysis protocol
2. ✅ `CUSTOM_GPT_INSTRUCTIONS_CONCISE.md` - Added anti-patterns for deferring API calls
3. ✅ `ChatGPT_Knowledge_Document.md` - Comprehensive Gold analysis documentation
4. ✅ `main_api.py` - Added debug logging for DXY routing
5. ✅ `CUSTOM_GPT_TROUBLESHOOTING.md` - Complete troubleshooting guide
6. ✅ `CUSTOM_GPT_SETUP_GUIDE.md` - Setup instructions
7. ✅ `CUSTOM_GPT_UPDATE_COMPLETE.md` - Summary of all changes

---

## Action Required from You

1. **Restart the server** (Ctrl+C, then `python main_api.py`)
2. **Run the test:** `python -c "import requests; response = requests.get('http://localhost:8000/api/v1/price/DXY'); print('Status:', response.status_code); print('Response:', response.json())"`
3. **Check server logs** for debug messages
4. **Reply with:** 
   - Test result (status code and response)
   - Server log output (the INFO messages)

Then I can diagnose further if needed!

