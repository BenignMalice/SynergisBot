# 🚀 Phone Control System - Quick Startup Guide

## 🎯 3 Ways to Start the System

---

### **Method 1: One-Click Full Startup (EASIEST)** ⭐

**Double-click:** `start_with_tunnel.bat`

This opens 3 windows:
1. **Command Hub** (localhost:8001)
2. **Desktop Agent** (connects to hub + starts Binance)
3. **ngrok Tunnel** (exposes to internet)

**Copy the tunnel URL** from the ngrok window (look for "Forwarding"):
```
https://xxxx-xxxx-xxxx.ngrok-free.app
```

**Then update your Custom GPT:**
- Go to Actions → Edit schema
- Update `servers[0].url` with your ngrok URL
- Save

**Done!** Test from your phone.

---

### **Method 2: Manual Startup (More Control)**

**Terminal 1 - Command Hub:**
```powershell
cd c:\mt5-gpt\TelegramMoneyBot.v7
python hub/command_hub.py
```
→ Note the **Phone Bearer Token** and **Agent Secret**

**Terminal 2 - Desktop Agent:**
```powershell
cd c:\mt5-gpt\TelegramMoneyBot.v7
python desktop_agent.py
```
→ Should say "✅ Connected to command hub"

**Terminal 3 - ngrok Tunnel:**
```powershell
cd c:\mt5-gpt\TelegramMoneyBot.v7
ngrok http 8001
```
→ Copy the `https://...ngrok-free.app` URL from "Forwarding"

---

### **Method 3: Just Hub + Agent (Testing)**

**Double-click:** `start_phone_control.bat`

This opens 2 windows:
1. **Command Hub**
2. **Desktop Agent**

**Use this when:**
- Testing locally (no phone needed)
- ngrok already running in another window
- Just restarting after code changes

---

## 🔧 System Health Check

**Before starting, verify everything is ready:**

```powershell
python check_system.py
```

This checks:
- ✅ Command Hub connectivity
- ✅ MT5 connection
- ✅ Binance Service availability

**Fix any red ❌ issues before proceeding.**

---

## 📱 Custom GPT Setup

### **1. Update Instructions**

Copy contents of: `CUSTOM_GPT_INSTRUCTIONS.md`

Paste into: **Custom GPT → Configure → Instructions**

Character count: 5,504 / 8,000 ✅

---

### **2. Upload Knowledge Files**

Upload these to **Custom GPT → Configure → Knowledge:**

1. ✅ `ChatGPT_Knowledge_Binance_Integration.md`
2. ✅ `ChatGPT_Knowledge_Document.md`
3. ✅ `CUSTOM_GPT_INSTRUCTIONS_FULL.md`

---

### **3. Update Actions**

**Your current ngrok URL:** `https://verbally-faithful-monster.ngrok-free.app`

**Edit your Custom GPT Actions schema:**

```yaml
servers:
  - url: https://verbally-faithful-monster.ngrok-free.app
    description: Command hub (exposed via ngrok)
```

**If ngrok URL changed:**
- Look for "Forwarding" in ngrok window
- Update the `url` field in your Actions
- Save

**The schema is already in:** `openai_phone.yaml`

---

### **4. Set Authentication**

**In Custom GPT Actions:**

1. Click "Authentication"
2. Select "Bearer"
3. Paste the **Phone Bearer Token** from command hub startup logs

---

## ✅ Testing Checklist

### **From Your Phone ChatGPT:**

```
✅ "Ping the system"
   → Should respond with "Pong from desktop agent"

✅ "Check Binance feed status"
   → Should show 7 symbols with health status

✅ "Analyse BTCUSD"
   → Should return full analysis with Binance enrichment

✅ "Check open positions"
   → Should list current MT5 positions (or "No open positions")
```

### **Expected Response Format:**

```
📊 BTCUSD Analysis

Direction: BUY
Entry: 65,430.00
SL: 65,100.00
TP: 65,950.00
Confidence: 82%

📡 Binance Feed:
  ✅ Status: HEALTHY
  💰 Price: $65,432.50
  📈 Micro Momentum: +0.45%
  🔄 Offset: +2.5 pips

✅ Binance confirms BUY (momentum: +0.45%)

Would you like me to execute this trade?
```

---

## 🔥 Troubleshooting

### **Desktop Agent: "Connection error: remote computer refused"**

**Problem:** Command hub not running

**Fix:** Start command hub first:
```powershell
python hub/command_hub.py
```

Wait 3 seconds, then start agent:
```powershell
python desktop_agent.py
```

---

### **Phone GPT: "Agent offline"**

**Problem:** Desktop agent not connected to hub

**Check:**
1. Is command hub running? (Terminal 1)
2. Is desktop agent running? (Terminal 2)
3. Does agent say "✅ Connected to command hub"?

**Fix:** Restart desktop agent

---

### **Phone GPT: "Binance feed offline"**

**Problem:** Desktop agent started but Binance didn't initialize

**Check agent logs for:**
```
✅ Binance Service initialized and started
✅ Streaming 7 symbols: btcusdt, xauusd, eurusd, gbpusd, usdjpy, gbpjpy, eurjpy
```

**Fix:** No action needed - trades still work with MT5 only

---

### **Phone GPT: "Invalid token" or 403 error**

**Problem:** Bearer token mismatch

**Fix:**
1. Copy **Phone Bearer Token** from command hub logs
2. Update Custom GPT → Actions → Authentication
3. Paste new token
4. Save and retry

---

### **ngrok: "ERR_NGROK_108" or session expired**

**Problem:** ngrok free tier session expired (8 hours)

**Fix:**
1. Close ngrok window
2. Restart: `ngrok http 8001`
3. Copy new URL and update Custom GPT Actions
4. Save

**Note:** ngrok URLs change each restart on free tier

---

### **ngrok: "Action sets cannot have duplicate domains"**

**Problem:** Your ngrok URL is already used by another Custom GPT

**Fix:** You're already using this URL in your existing MoneyBot GPT. Just add the phone control actions to that same GPT. The schema should already be merged in `openai_phone.yaml`.

---

## 🎯 Production Recommendations

### **For Daily Use:**

1. **Keep ngrok running:**
   - Don't close the ngrok window
   - It will stay active until you close it or 8 hours pass (free tier)

2. **Monitor logs:**
   - Keep command hub window visible
   - Watch for "Command received" and "Result sent"
   - Check for any errors or warnings

3. **Regular health checks:**
   - Run `check_system.py` once per day
   - Verify all components green ✅

4. **Restart after code changes:**
   - Close agent window (hub can stay running)
   - Re-run: `python desktop_agent.py`
   - ngrok can stay running (no need to restart)

5. **If ngrok restarts:**
   - Note the new URL from ngrok window
   - Update Custom GPT Actions with new URL
   - Save (takes 5 seconds)

---

## 📊 What's Running Where

| Component | Port | Purpose |
|-----------|------|---------|
| Command Hub | 8001 | Routes phone ↔ desktop |
| Desktop Agent | - | Executes commands |
| Binance Stream | - | Real-time data (7 symbols) |
| MT5 | - | Execution layer |
| ngrok | 8001 | Exposes hub to internet |

---

## 🎉 You're Ready!

Once you see:
- ✅ Command hub running
- ✅ Desktop agent connected
- ✅ ngrok tunnel active (showing Forwarding URL)
- ✅ Custom GPT updated with ngrok URL

**You can trade from your phone!** 📱💰

Test with: **"Analyse GBPUSD"**

---

**Last Updated:** October 12, 2025  
**System Version:** 1.0.0  
**Tunnel:** ngrok (https://verbally-faithful-monster.ngrok-free.app)  
**Status:** Production Ready 🚀
