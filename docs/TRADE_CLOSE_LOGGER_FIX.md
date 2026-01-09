# 🔧 Trade Close Logger Fix

## 🐛 Issue

When starting the Telegram bot (`chatgpt_bot.py`), the closed trades monitor was crashing:

```
2025-10-13 19:14:09,882 - __main__ - INFO - 🔍 Starting closed trades monitor...
Error during force check: 'JournalRepo' object has no attribute 'get_open_trades'
Traceback (most recent call last):
  File "C:\mt5-gpt\TelegramMoneyBot.v7\infra\trade_close_logger.py", line 300, in force_check_all_open_trades
    open_trades = self.journal_repo.get_open_trades()
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AttributeError: 'JournalRepo' object has no attribute 'get_open_trades'
```

---

## 🔍 Root Cause

The `TradeCloseLogger` was calling `journal_repo.get_open_trades()`, but this method didn't exist in `JournalRepo`.

**Why it was missing:**
- `JournalRepo` had methods to write trades (`write_exec()`)
- It had methods to query closed trades (`get_trades_summary()`)
- But it had **NO** method to query open trades

---

## ✅ Fixes Applied

### **1. Added `get_open_trades()` Method**

**File:** `infra/journal_repo.py` lines 707-720

```python
def get_open_trades(self) -> list[dict]:
    """Get all currently open trades (closed_ts IS NULL)"""
    with self._lock, self._conn:
        cur = self._conn.execute(
            """
            SELECT ticket, symbol, side, entry_price, sl, tp, volume, 
                   strategy, regime, opened_ts
              FROM trades
             WHERE closed_ts IS NULL
             ORDER BY opened_ts DESC
            """
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
```

**What it does:**
- Queries the `trades` table
- Returns all trades where `closed_ts IS NULL` (i.e., still open)
- Returns a list of dictionaries with trade info

---

### **2. Added `close_trade()` Method**

**File:** `infra/journal_repo.py` lines 722-764

```python
def close_trade(
    self, 
    ticket: int, 
    exit_price: float, 
    close_reason: str, 
    pnl: float = None, 
    r_multiple: float = None,
    closed_ts: int = None
) -> None:
    """Update a trade to closed status"""
    import time
    if closed_ts is None:
        closed_ts = int(time.time())
    
    with self._lock, self._conn:
        # Calculate duration
        cur = self._conn.execute(
            "SELECT opened_ts FROM trades WHERE ticket = ?", (ticket,)
        )
        row = cur.fetchone()
        if not row:
            logger.warning(f"Trade {ticket} not found in database for closing")
            return
        
        opened_ts = row[0]
        duration_sec = closed_ts - opened_ts if opened_ts else None
        
        # Update the trade
        self._conn.execute(
            """
            UPDATE trades 
            SET closed_ts = ?,
                exit_price = ?,
                close_reason = ?,
                pnl = ?,
                r_multiple = ?,
                duration_sec = ?
            WHERE ticket = ?
            """,
            (closed_ts, exit_price, close_reason, pnl, r_multiple, duration_sec, ticket)
        )
        self._conn.commit()
        logger.debug(f"Trade {ticket} marked as closed in database")
```

**What it does:**
- Updates a trade's status from open to closed
- Calculates and stores trade duration
- Sets exit price, close reason, P&L, R-multiple
- Cleaner API for closing trades

---

### **3. Fixed Parameter Name Mismatch**

**File:** `infra/trade_close_logger.py` lines 214, 331

Changed:
```python
close_ts=close_info["close_time"]  # OLD (wrong)
```

To:
```python
closed_ts=close_info["close_time"]  # NEW (correct)
```

**Why:** The `close_trade()` method parameter is `closed_ts`, not `close_ts`.

---

## 🎯 How It Works Now

### **Flow:**

1. **Telegram bot starts** → Initializes `TradeCloseLogger`
2. **Every 60 seconds** → Checks for closed trades
3. **`check_for_closed_trades()`** calls `force_check_all_open_trades()`
4. **`get_open_trades()`** queries database for open trades
5. **Compares** DB open trades vs MT5 current positions
6. **If missing** → Trade was closed while offline
7. **`close_trade()`** updates database
8. **Logs event** → "trade_closed" with reason
9. **Updates V8** → Records outcome in V8 analytics

---

## 📊 Database Operations

### **Query Open Trades:**

```sql
SELECT ticket, symbol, side, entry_price, sl, tp, volume, 
       strategy, regime, opened_ts
FROM trades
WHERE closed_ts IS NULL
ORDER BY opened_ts DESC;
```

### **Close Trade:**

```sql
UPDATE trades 
SET closed_ts = 1728839649,
    exit_price = 4095.50,
    close_reason = 'manual',
    pnl = 13.50,
    r_multiple = 1.71,
    duration_sec = 3600
WHERE ticket = 122387063;
```

---

## ✅ Benefits

1. **No More Crashes** - `get_open_trades()` now exists
2. **Cleaner API** - `close_trade()` method simplifies closing logic
3. **Automatic Detection** - Catches trades closed while bot was offline
4. **Complete Tracking** - Duration, P&L, R-multiple calculated automatically
5. **Database Integrity** - All trades properly closed in database

---

## 🧪 Testing

### **Test Closed Trade Detection:**

1. **Start Telegram bot** (`chatgpt_bot.py`)
2. **Execute a trade** (via ChatGPT or phone control)
3. **Manually close** the trade in MT5
4. **Wait 60 seconds** for next check
5. **Check logs** for "Detected and logged X closed trades"
6. **Check database:**

```bash
sqlite3 data/journal.sqlite
SELECT * FROM trades WHERE ticket = 122387063;
```

Should show:
- `closed_ts` = timestamp
- `exit_price` = close price
- `close_reason` = "manual" or reason
- `pnl` = profit/loss
- `duration_sec` = trade duration

### **Test Force Check:**

```bash
# In Python console
from infra.trade_close_logger import get_close_logger

close_logger = get_close_logger()
close_logger.force_check_all_open_trades()
```

Should output:
```
🔍 Force checking all open trades in database...
✅ All 3 open trades are still open in MT5
```

Or if a trade closed:
```
⚠️ Trade 122387063 is open in DB but not in MT5 - logging close
✅ Logged missed close for ticket 122387063
```

---

## 📁 Files Modified

1. ✅ `infra/journal_repo.py`
   - Added `import logging` (line 8)
   - Added `logger = logging.getLogger(__name__)` (line 18)
   - Added `get_open_trades()` method (lines 707-720)
   - Added `close_trade()` method (lines 722-764)

2. ✅ `infra/trade_close_logger.py`
   - Fixed parameter name: `close_ts` → `closed_ts` (lines 214, 331)

---

## 🐛 Follow-up Fix

**Issue:** `NameError: name 'logger' is not defined`

The `close_trade()` method was using `logger.debug()` but logger wasn't imported.

**Fix:** Added `import logging` and `logger = logging.getLogger(__name__)` to `journal_repo.py`

---

## ✅ Status

**FIXED** ✅

The closed trades monitor should now start without errors!

---

**Issue Date:** October 13, 2025
**Fixed Date:** October 13, 2025
**Fix Type:** Missing method implementation + parameter mismatch

