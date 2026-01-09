# BTC Order Flow Service - Troubleshooting Guide

**Date:** 2025-12-24  
**Issue:** Services show as not running even though `chatgpt_bot.py` is running

---

## 🔍 **Problem**

When checking service status via bridge:
- **Binance Service:** `Running: False`, `Status: offline`
- **Order Flow Service:** `Running: False`

Even though `chatgpt_bot.py` is running, the services are not accessible.

---

## 🔍 **Possible Causes**

### **1. Services Failed to Initialize**

**Check logs:**
```powershell
Get-Content desktop_agent.log -Tail 200 | Select-String -Pattern "Binance|Order Flow|Error|Failed|Exception"
```

**Look for:**
- ❌ `⚠️ BinanceService initialization failed`
- ❌ `⚠️ Order Flow Service initialization failed`
- ❌ `Exception` or `Error` messages

**Common errors:**
- WebSocket connection failed
- Binance API unavailable
- Network/firewall blocking connections
- MT5 not connected (required for Binance service)

---

### **2. Services Running in Different Process**

The bridge may be accessing a different process than where `chatgpt_bot.py` is running.

**Check:**
- Is `chatgpt_bot.py` running in the same Python process?
- Are services initialized in the main process or a subprocess?
- Does the bridge have access to the same `registry` object?

---

### **3. Services Stopped After Initialization**

Services might have started but then stopped due to:
- Connection loss
- Error in background task
- Resource constraints

**Check logs for:**
- `Order Flow Service stopped`
- `Binance streams stopped`
- `WebSocket disconnected`

---

## ✅ **Solutions**

### **Solution 1: Check Logs for Initialization**

```powershell
# Check recent logs
Get-Content desktop_agent.log -Tail 500 | Select-String -Pattern "Binance Service|Order Flow Service"
```

**Expected success messages:**
```
✅ Binance Service initialized and started
✅ Streaming 1 symbol: btcusdt
✅ Order Flow Service initialized
   📊 Order book depth: Active (20 levels @ 100ms)
   🐋 Whale detection: Active ($50k+ orders)
```

**If you see errors instead:**
- Note the error message
- Check if it's a connection issue
- Verify MT5 is connected
- Check internet connection

---

### **Solution 2: Restart chatgpt_bot.py**

If services failed to start:

1. **Stop current process:**
   - Press `Ctrl+C` in the terminal running `chatgpt_bot.py`
   - Or kill the process

2. **Restart:**
   ```powershell
   python chatgpt_bot.py
   ```

3. **Watch for initialization messages:**
   - Look for "✅ Binance Service initialized and started"
   - Look for "✅ Order Flow Service initialized"
   - If you see errors, note them

---

### **Solution 3: Check Service Status in Running Process**

If `chatgpt_bot.py` is running, the services might be accessible from within that process but not via the bridge.

**Try accessing via ChatGPT:**
- Use tool: `moneybot.binance_feed_status`
- Use tool: `moneybot.order_flow_status`
- Use tool: `moneybot.btc_order_flow_metrics`

**If tools work via ChatGPT but not via bridge:**
- Services are running in the main process
- Bridge is accessing a different process context
- This is expected - services are in the main `chatgpt_bot.py` process

---

### **Solution 4: Verify Services Are Actually Needed**

**Important:** Order flow conditions are **optional**. Plans work without them.

**What works without order flow:**
- ✅ R:R validation
- ✅ Session blocking
- ✅ News blackout checks
- ✅ Execution quality validation
- ✅ All other conditions (CHOCH, BOS, confluence, etc.)

**What requires order flow:**
- ⚠️ `delta_positive` / `delta_negative` conditions
- ⚠️ `cvd_rising` / `cvd_falling` conditions
- ⚠️ `avoid_absorption_zones` condition

**Recommendation:**
- If services aren't running, create plans without order flow conditions
- Plans will still work and benefit from other improvements
- Order flow conditions can be added later when services are running

---

## 🔧 **How Auto-Execution System Accesses Order Flow**

**From `auto_execution_system.py` (lines 638-652):**

The system tries to access `order_flow_service` from the `chatgpt_bot` module:

```python
try:
    import chatgpt_bot
    if hasattr(chatgpt_bot, 'order_flow_service'):
        order_flow_service = chatgpt_bot.order_flow_service
        if order_flow_service.running:
            # Use order flow service
        else:
            # Service exists but not running
except ImportError:
    # chatgpt_bot module not available
```

**This means:**
- Services must be initialized in the **same Python process** as `chatgpt_bot.py`
- If running in separate processes, services won't be accessible
- Bridge calls might be in a different process context

---

## 📝 **Summary**

**Current Status:**
- `chatgpt_bot.py` is running
- Services show as not running via bridge
- Possible causes: initialization failure, different process, or services stopped

**Next Steps:**
1. Check `desktop_agent.log` for initialization errors
2. Restart `chatgpt_bot.py` if needed
3. Verify services are accessible via ChatGPT tools
4. If services aren't available, create plans without order flow conditions (they're optional)

**Impact:**
- Order flow conditions cannot be used until services are running
- All other system improvements work normally
- Plans can still be created and executed successfully
