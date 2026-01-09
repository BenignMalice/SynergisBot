# Discord Alert Delivery Fix

**Date:** 2025-11-30  
**Issue:** Alerts logged as "sent" but Discord messages not received

---

## 🔍 **Root Cause**

The code was logging "Alert sent" **BEFORE** the actual Discord webhook request completed. This meant:
1. Log showed "Alert sent" ✅
2. But webhook request could fail silently ❌
3. Errors were logged separately but not connected to the "Alert sent" message

---

## ✅ **Fixes Applied**

### **1. Proper Success/Failure Tracking**
**File:** `infra/discord_alert_dispatcher.py`

**Changes:**
- `_send_to_webhook()` now returns `True`/`False` to indicate success
- `_send_alert()` waits for send to complete before logging
- Only logs "Alert sent" if Discord actually received it
- Logs "Alert NOT sent" if delivery failed

**Before:**
```python
await asyncio.to_thread(self._send_to_webhook, ...)
logger.info(f"Alert sent: ...")  # ❌ Logged before send completes
```

**After:**
```python
send_success = await asyncio.to_thread(self._send_to_webhook, ...)
if send_success:
    logger.info(f"Alert sent: ...")  # ✅ Only if actually sent
else:
    logger.error(f"Alert NOT sent: ...")  # ✅ Clear error message
```

### **2. Better Error Handling**
**File:** `infra/discord_alert_dispatcher.py`

**Changes:**
- Catches `requests.exceptions.Timeout` separately
- Catches `requests.exceptions.RequestException` separately
- Logs HTTP error status codes and response text
- Full traceback for unexpected errors

**Before:**
```python
except Exception as e:
    logger.error(f"Failed to send to webhook: {e}")  # ❌ Generic error
```

**After:**
```python
except requests.exceptions.Timeout:
    logger.error(f"Webhook request timed out after 10 seconds")
    return False
except requests.exceptions.RequestException as e:
    logger.error(f"Webhook request failed: {e}")
    return False
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return False
```

### **3. Improved Webhook Configuration Logging**
**File:** `infra/discord_alert_dispatcher.py`

**Changes:**
- Logs which webhook is being used (channel-specific vs default)
- Warns if no channel webhooks configured
- Errors if DiscordNotifier is None

---

## 📋 **What to Check Now**

After restarting `main_api.py`, check logs for:

### **✅ Success Indicators:**
```
Alert sent: CHOCH_BULL BTCUSDc M5 (confidence: 85%)
Alert sent to custom webhook successfully
```

### **❌ Failure Indicators:**
```
Alert NOT sent to Discord: CHOCH_BULL BTCUSDc M5 (confidence: 85%)
Webhook returned error status 404: ...
Webhook request timed out after 10 seconds
Discord notifier is None - alert NOT sent
```

### **⚠️ Configuration Issues:**
```
No channel webhooks configured - using default DiscordNotifier
Discord notifier disabled - alert NOT sent
Invalid webhook URL: ...
Webhook URL does not match Discord format: ...
```

---

## 🎯 **Next Steps**

1. **Restart `main_api.py`** to activate fixes
2. **Check logs** for the new error messages
3. **Verify webhook configuration:**
   - Check `.env` for `DISCORD_WEBHOOK_CRYPTO` (for BTCUSDc)
   - Check if webhook URL is valid
   - Test webhook manually if needed
4. **Check Discord server:**
   - Verify webhook is still active
   - Check if webhook was deleted/regenerated
   - Verify bot has permissions

---

## ✅ **Status**

- ✅ Success/failure tracking fixed
- ✅ Error handling improved
- ✅ Configuration logging added
- ⚠️ **Need to restart main_api.py** to activate
- ⚠️ **Check logs** after restart to see actual errors

