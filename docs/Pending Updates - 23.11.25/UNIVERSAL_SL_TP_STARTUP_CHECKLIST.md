# Universal Dynamic SL/TP Manager - Startup Checklist

**Date:** November 25, 2025  
**System:** Universal Dynamic SL/TP Adjustment System

---

## ✅ What You Should See After Restarting All Services

### 1. **Initialization Messages (in `chatgpt_bot.py` console/logs)**

When `chatgpt_bot.py` starts, you should see these messages in sequence:

#### ✅ **Success Indicators:**

```
✅ Universal Dynamic SL/TP Manager initialized and trades recovered
```

OR (if no trades to recover):

```
✅ Universal Dynamic SL/TP Manager initialized (recovery skipped)
```

#### **Database Initialization:**

```
Database initialized: data/universal_sl_tp_trades.db
```

#### **Config Loading:**

**If config file exists:**
```
Loaded config from config/universal_sl_tp_config.json
```

**If config file doesn't exist (uses defaults):**
```
⚠️ Config file not found: config/universal_sl_tp_config.json, using defaults
```
*(This is OK - system will use default configuration)*

#### **Trade Recovery (if you have open trades):**

**For each recovered trade:**
```
Recovered trade 123456 (BTCUSDc, breakout_ib_volatility_trap)
```

**If no trades to recover:**
```
No trades to recover from database
```

**If trades found but not universal-managed:**
```
Trade 123456 owned by legacy_exit_manager - skipping
```

#### **Scheduler Registration:**

```
✅ Universal Dynamic SL/TP Manager monitoring scheduled (every 30s)
```

#### **Background Monitoring Status:**

```
📊 Background Monitoring Active:
   ...
   ✅ Universal SL/TP Monitoring (every 30s)
```

---

### 2. **Files That Should Be Created**

#### **Database File:**
- **Location:** `data/universal_sl_tp_trades.db`
- **Size:** ~10-20 KB initially (grows with active trades)
- **Created:** Automatically on first initialization
- **Contains:** Active trade states (persisted for crash recovery)

#### **Config File (Optional):**
- **Location:** `config/universal_sl_tp_config.json`
- **Status:** Optional - system works with defaults if not present
- **Created:** Manually (if you want custom rules)

---

### 3. **Continuous Operation Messages (Every 30 Seconds)**

Once the system is running, you'll see periodic messages:

#### **If You Have Active Trades:**

**Monitoring Cycle (every 30 seconds):**
- Usually **silent** (no log messages unless action is taken)
- Only logs when:
  - Breakeven is triggered
  - Partial profit is taken
  - SL is modified (trailing stop)
  - Trade is closed

**Example SL Modification Log:**
```
123456 BTCUSDc breakout_ib_volatility_trap LONDON SL 84000.00→84150.00 r=1.25 reason=structure_trail
```

**Example Breakeven Log:**
```
123456 BTCUSDc breakout_ib_volatility_trap LONDON SL 83800.00→84000.00 r=1.00 reason=breakeven_trigger
```

**Example Partial Profit Log:**
```
Taking partial profit for 123456: closing 50% of position (0.005 lots)
```

#### **If You Have No Active Trades:**

- **No log messages** (system is idle, waiting for trades)
- Monitoring loop runs silently every 30 seconds
- Checks for new trades (none found, continues)

---

### 4. **Error/Warning Messages (What They Mean)**

#### ⚠️ **Non-Critical Warnings:**

**Config file not found:**
```
⚠️ Config file not found: config/universal_sl_tp_config.json, using defaults
```
**Action:** None needed - system uses default configuration

**MT5Service creation failed:**
```
Could not create MT5Service for Universal Manager: [error]
```
**Action:** System will use direct MT5 calls as fallback (still works)

**Trade recovery failed:**
```
⚠️ Trade recovery failed: [error]
✅ Universal Dynamic SL/TP Manager initialized (recovery skipped)
```
**Action:** System still works, but trades won't be recovered from previous session

#### ❌ **Critical Errors:**

**Import error:**
```
⚠️ Universal Dynamic SL/TP Manager not available: [ImportError]
```
**Action:** Check that `infra/universal_sl_tp_manager.py` exists and is importable

**Initialization failed:**
```
⚠️ Could not initialize Universal Dynamic SL/TP Manager: [error]
```
**Action:** Check error details in logs, verify database directory exists

**MT5 not initialized:**
```
MT5 not initialized - skipping trade monitoring
```
**Action:** Ensure MT5 is running and connected

---

### 5. **How to Verify It's Working**

#### **Check 1: Database File Exists**
```bash
# Windows PowerShell
Test-Path "data/universal_sl_tp_trades.db"
# Should return: True
```

#### **Check 2: Scheduler is Running**
Look for this in logs:
```
✅ Background scheduler started
✅ Universal Dynamic SL/TP Manager monitoring scheduled (every 30s)
```

#### **Check 3: Monitoring is Active**
Every 30 seconds, the system checks for trades. If you have an active trade:
- Open a trade with a universal-managed strategy (breakout, trend continuation, etc.)
- Wait 30-60 seconds
- Check logs for monitoring activity

#### **Check 4: Trade Registration**
When a new trade is opened via auto-execution with a universal-managed strategy, you should see:
- Trade registered in the system
- Trade state saved to database
- Trade appears in `active_trades` dict

---

### 6. **What Happens When a Trade is Opened**

#### **Auto-Execution Flow:**

1. **Trade Created:**
   - Auto-execution system creates trade plan
   - Plan has `strategy_type` in conditions

2. **Trade Executed:**
   - Auto-execution system executes trade
   - Checks if `strategy_type` is in `UNIVERSAL_MANAGED_STRATEGIES`
   - If yes, calls `universal_sl_tp_manager.register_trade()`

3. **Trade Registered:**
   - Universal Manager detects session (Asia/London/NY)
   - Calculates baseline ATR
   - Resolves trailing rules (strategy + symbol + session)
   - Saves to database
   - Adds to `active_trades` dict

4. **Monitoring Begins:**
   - Every 30 seconds, system checks the trade
   - Calculates R-achieved
   - Checks breakeven trigger
   - Checks partial profit trigger
   - Calculates trailing SL (if breakeven triggered)

---

### 7. **Expected Behavior by Trade Status**

#### **New Trade (Just Opened):**
- ✅ Registered in system
- ✅ Saved to database
- ✅ Monitoring active (every 30s)
- ⏳ Waiting for breakeven trigger (typically at +1.0R)

#### **Trade at +0.5R:**
- ✅ Monitoring active
- ⏳ Not yet at breakeven trigger
- ⏳ No actions taken

#### **Trade at +1.0R (Breakeven Trigger):**
- ✅ Breakeven triggered
- ✅ SL moved to entry price
- ✅ Logged: `reason=breakeven_trigger`
- ✅ Trailing enabled (if configured)

#### **Trade at +1.5R (Partial Profit Trigger):**
- ✅ Partial profit taken (typically 50% of position)
- ✅ Logged: `Taking partial profit`
- ✅ Remaining position continues with trailing

#### **Trade with Trailing Active:**
- ✅ SL adjusted based on structure/ATR
- ✅ Logged: `reason=structure_trail` or `reason=atr_trail`
- ✅ Cooldown prevents excessive modifications

---

### 8. **Troubleshooting**

#### **Problem: No initialization messages**

**Check:**
1. Is `chatgpt_bot.py` running?
2. Check for import errors in logs
3. Verify `infra/universal_sl_tp_manager.py` exists

#### **Problem: Database not created**

**Check:**
1. Does `data/` directory exist?
2. Check file permissions
3. Look for error messages in logs

#### **Problem: Trades not being monitored**

**Check:**
1. Is trade strategy in `UNIVERSAL_MANAGED_STRATEGIES`?
2. Was trade registered? (check logs for `register_trade` calls)
3. Is scheduler running? (check for scheduler start message)

#### **Problem: No SL modifications happening**

**Check:**
1. Is breakeven triggered? (check `r_achieved >= breakeven_trigger_r`)
2. Is trailing enabled? (check `trailing_enabled` in rules)
3. Is cooldown active? (check `last_sl_modification_time`)
4. Is minimum R-distance met? (check `min_sl_change_r`)

---

### 9. **Quick Verification Commands**

#### **Check Database:**
```python
import sqlite3
conn = sqlite3.connect("data/universal_sl_tp_trades.db")
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM universal_trades")
print(f"Active trades in DB: {cursor.fetchone()[0]}")
conn.close()
```

#### **Check Logs:**
```bash
# Windows PowerShell
Select-String -Path "logs/chatgpt_bot.log" -Pattern "Universal|SL/TP" | Select-Object -Last 20
```

#### **Check Scheduler:**
Look for these in logs:
```
✅ Background scheduler started
✅ Universal Dynamic SL/TP Manager monitoring scheduled (every 30s)
```

---

## ✅ Summary: What You Should See

### **On Startup:**
1. ✅ Database initialization message
2. ✅ Config loading message (or default warning)
3. ✅ Trade recovery messages (if applicable)
4. ✅ Scheduler registration message
5. ✅ Background monitoring status

### **During Operation:**
1. ✅ Silent monitoring every 30 seconds (no logs unless action taken)
2. ✅ Log messages when:
   - Breakeven triggered
   - Partial profit taken
   - SL modified (trailing)
   - Trade closed

### **Files Created:**
1. ✅ `data/universal_sl_tp_trades.db` (database)
2. ⚠️ `config/universal_sl_tp_config.json` (optional, uses defaults if missing)

---

**If you see all the ✅ items above, the system is working correctly!**

**Last Updated:** November 25, 2025

