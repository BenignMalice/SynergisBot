# How to Restart the API Server

## Problem
The API server is running with old code. It needs to be restarted to load the new AI endpoints.

---

## Quick Fix (Recommended)

### Option 1: Use --reload flag (Already Set)
If you started with `start_with_ngrok.bat`, the server should auto-reload. But if it's not detecting changes:

**Close and restart both windows:**
1. Close the "API Server" command window
2. Close the "ngrok Tunnel" command window
3. Double-click `start_with_ngrok.bat` again
4. Wait 10 seconds for both to initialize

---

### Option 2: Manual Restart

**Step 1: Kill all Python processes**
```powershell
taskkill /F /IM python.exe
```

**Step 2: Wait 2 seconds**
```powershell
Start-Sleep -Seconds 2
```

**Step 3: Start API server**
```powershell
cd C:\mt5-gpt\TelegramMoneyBot.v7
python -m uvicorn app.main_api:app --reload --host 0.0.0.0 --port 8000
```

**Step 4: In a NEW terminal, start ngrok**
```powershell
cd C:\mt5-gpt\TelegramMoneyBot.v7
ngrok http --url=verbally-faithful-monster.ngrok-free.app 8000
```

---

### Option 3: One-Command Restart (Easiest)

Open PowerShell in the project folder and run:
```powershell
cd C:\mt5-gpt\TelegramMoneyBot.v7
taskkill /F /IM python.exe 2>$null
Start-Sleep -Seconds 2
start_with_ngrok.bat
```

---

## Verify It's Working

### 1. Check API Docs
Open browser: http://localhost:8000/docs

You should see **16 endpoints** including:
- ✅ `/ai/analysis/{symbol}`
- ✅ `/ml/patterns/{symbol}`
- ✅ `/ai/exits/{symbol}`

### 2. Test the AI endpoint directly
```bash
curl "http://localhost:8000/ai/analysis/XAUUSD"
```

Should return JSON with `chatgpt_analysis` (not a 501 error)

### 3. Test via ngrok URL
```bash
curl "https://verbally-faithful-monster.ngrok-free.app/ai/analysis/XAUUSD"
```

Should return the same JSON

---

## Troubleshooting

### Problem: "Address already in use"
**Solution:** Another process is using port 8000
```powershell
# Find what's using port 8000
netstat -ano | findstr :8000

# Kill that process (replace PID with actual number)
taskkill /F /PID <PID>
```

### Problem: ngrok says "failed to start tunnel"
**Solution:** Previous ngrok is still running
```powershell
# Kill ngrok
taskkill /F /IM ngrok.exe
Start-Sleep -Seconds 2

# Restart
ngrok http --url=verbally-faithful-monster.ngrok-free.app 8000
```

### Problem: ChatGPT still gets errors
**Solution:** Wait 30 seconds after restart, then try again
- The server needs time to initialize
- ngrok needs time to establish tunnel
- ChatGPT may cache the old error

### Problem: Still getting 501 errors
**Solution:** Verify the file was saved
1. Open `app/main_api.py`
2. Search for `@app.get("/ai/analysis/{symbol}")`
3. Should see implementation (not "raise HTTPException(status_code=501)")
4. If still old code, the file wasn't saved properly

---

## Quick Verification Checklist

Before testing with ChatGPT:

- [ ] API server is running (check http://localhost:8000/docs)
- [ ] ngrok tunnel is running (shows "online" status)
- [ ] `/ai/analysis/{symbol}` endpoint is listed in docs
- [ ] Test endpoint with curl returns JSON (not 501)
- [ ] ngrok URL works: https://verbally-faithful-monster.ngrok-free.app/health
- [ ] Wait 30 seconds after restart before testing

---

## Expected Behavior After Restart

### Before (Old Code):
```
GET /ai/analysis/XAUUSD
→ HTTP 501: "AI analysis endpoint not yet implemented"
```

### After (New Code):
```
GET /ai/analysis/XAUUSD
→ HTTP 200: {
  "symbol": "XAUUSDc",
  "timestamp": "...",
  "chatgpt_analysis": { ... },
  "ml_insights": { ... }
}
```

---

## What ChatGPT Will See

After restart, when ChatGPT calls:
```
Tool: getAIAnalysis
Symbol: XAUUSD
```

ChatGPT will receive:
```json
{
  "symbol": "XAUUSDc",
  "chatgpt_analysis": {
    "trade_recommendation": {
      "direction": "BUY" or "SELL",
      "entry_price": 3850.0,
      "stop_loss": 3820.0,
      "take_profit": 3900.0,
      "confidence": 75,
      "reasoning": "Detailed analysis..."
    },
    "market_regime": "TRENDING",
    "confluence_score": 4
  }
}
```

**Instead of:** "Error talking to connector"

---

## Summary

**To fix the error:**
1. Close both command windows (API server + ngrok)
2. Double-click `start_with_ngrok.bat`
3. Wait 30 seconds
4. Try ChatGPT again

The new AI endpoints are implemented in the code, they just need to be loaded by restarting the server!

