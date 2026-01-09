# 🎉 Phone Control - Merged into Main API

## ✅ What Changed

Phone control endpoints are now **integrated into your main MoneyBot API** (`app/main_api.py`):

- **Port 8000**: Main API + Phone Control (merged)
- **ngrok URL**: `https://verbally-faithful-monster.ngrok-free.app` (already running)
- **No separate command hub needed!**

---

## 🚀 Quick Start (3 Steps)

### **Step 1: Start/Restart Main API**

If your main API is already running, **restart it** to load phone control:

```powershell
cd c:\mt5-gpt\TelegramMoneyBot.v7
python app/main_api.py
```

**Look for these lines in startup logs:**
```
🔐 Phone Control Tokens Generated:
   Phone Bearer Token: [COPY-THIS-TOKEN]
   Agent Secret: [COPY-THIS-SECRET]
```

**Copy both tokens!** You'll need them.

---

### **Step 2: Update Desktop Agent Config**

Edit `desktop_agent.py` (lines 42-43):

```python
HUB_URL = "ws://localhost:8000/agent/connect"  # Already correct!
AGENT_SECRET = "PASTE-AGENT-SECRET-HERE"  # Paste from main API logs
```

Save the file.

---

### **Step 3: Start Desktop Agent**

```powershell
python desktop_agent.py
```

**Should see:**
```
✅ Connected to command hub
✅ Binance Service initialized and started
✅ Streaming 7 symbols: btcusdt, xauusd, eurusd, gbpusd, usdjpy, gbpjpy, eurjpy
```

---

## 📱 Update Custom GPT

### **1. Update Instructions**

Copy contents of: `CUSTOM_GPT_INSTRUCTIONS.md`

Paste into: **Custom GPT → Configure → Instructions**

---

### **2. Upload Knowledge Files**

Upload these to **Custom GPT → Configure → Knowledge:**

1. ✅ `ChatGPT_Knowledge_Binance_Integration.md`
2. ✅ `ChatGPT_Knowledge_Document.md`
3. ✅ `CUSTOM_GPT_INSTRUCTIONS_FULL.md`

---

### **3. Update Actions**

Your existing `openai.yaml` already points to the correct ngrok URL:

```yaml
servers:
  - url: https://verbally-faithful-monster.ngrok-free.app
```

**Add phone control actions** by merging `openai_phone.yaml`:

Copy the `/dispatch` endpoint and related schemas from `openai_phone.yaml` and add to your existing `openai.yaml` in Custom GPT Actions.

**Or simply upload the complete merged schema** (both files combined).

---

### **4. Update Authentication**

**In Custom GPT Actions:**

1. Click "Authentication"
2. Select "Bearer"
3. Paste the **Phone Bearer Token** from main API logs

---

## ✅ Testing

### **From Your Phone ChatGPT:**

```
✅ "Ping the system"
   → Should respond with "Pong from desktop agent"

✅ "Check Binance feed status"
   → Should show 7 symbols with health status

✅ "Analyse BTCUSD"
   → Should return full analysis with Binance enrichment
```

---

## 📊 System Architecture

### **Before (Separate Hub):**
```
Phone → ngrok (8001) → Command Hub (8001) → Desktop Agent
                     ↓
          Main API (8000) ← ngrok (8000)
```

### **After (Merged):**
```
Phone → ngrok (8000) → Main API (8000) → Desktop Agent
                              ↓
                       All endpoints in one place!
```

---

## 🔥 Troubleshooting

### **Desktop Agent: "Connection error: remote computer refused"**

**Problem:** Main API not running or phone control not loaded

**Fix:**
1. Restart main API: `python app/main_api.py`
2. Check logs for "Phone Control Tokens Generated"
3. Update AGENT_SECRET in `desktop_agent.py`
4. Restart agent: `python desktop_agent.py`

---

### **Agent connects but authentication fails**

**Problem:** AGENT_SECRET mismatch

**Fix:**
1. Copy "Agent Secret" from main API logs
2. Update `desktop_agent.py` line 43
3. Restart agent

---

### **Phone GPT: "Invalid token" or 403 error**

**Problem:** Phone Bearer Token mismatch

**Fix:**
1. Copy "Phone Bearer Token" from main API logs
2. Update Custom GPT → Actions → Authentication
3. Save and retry

---

## 🎯 Daily Workflow

### **Normal Startup:**

**Terminal 1 - Main API (if not running):**
```powershell
cd c:\mt5-gpt\TelegramMoneyBot.v7
python app/main_api.py
```

**Terminal 2 - Desktop Agent:**
```powershell
python desktop_agent.py
```

**ngrok should already be running** from your existing setup.

---

### **After Code Changes:**

**Only restart the component you changed:**

- Changed `app/main_api.py`? → Restart main API
- Changed `desktop_agent.py`? → Restart agent
- Changed Binance components? → Restart agent

**ngrok can stay running** (no need to restart).

---

## 📋 New Endpoints Added to Main API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/dispatch` | POST | Send command from phone to agent |
| `/agent/connect` | WebSocket | Desktop agent connection |
| `/phone/health` | GET | Check phone control system health |

---

## ✅ Benefits of Merged Architecture

1. ✅ **Single ngrok tunnel** - No port conflicts
2. ✅ **One server to manage** - Simpler deployment
3. ✅ **Shared authentication** - Consistent security
4. ✅ **Same URL for all features** - Easier Custom GPT setup
5. ✅ **No separate command hub process** - Less resource usage

---

## 🎉 You're Ready!

Once you see:
- ✅ Main API running (port 8000)
- ✅ Desktop agent connected
- ✅ ngrok tunnel active (same URL as before)
- ✅ Custom GPT updated with phone bearer token

**You can trade from your phone!** 📱💰

Test with: **"Analyse GBPUSD"**

---

**Last Updated:** October 12, 2025  
**Integration:** Phone Control merged into Main API ✅  
**ngrok URL:** https://verbally-faithful-monster.ngrok-free.app  
**Status:** Production Ready 🚀

