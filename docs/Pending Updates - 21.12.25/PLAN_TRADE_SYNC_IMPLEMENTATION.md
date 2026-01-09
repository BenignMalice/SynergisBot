# Plan-Trade Sync Mechanism Implementation

**Date:** 2025-12-22  
**Status:** ✅ **COMPLETE**

---

## 🎯 **Goal**

Implement a sync mechanism between execution logs and plan effectiveness, allowing ChatGPT to review closed trades with their originating auto-execution plan context.

---

## ✅ **Implementation Summary**

### **1. Journal Database Schema Updates** ✅

**File:** `infra/journal_repo.py`

**Changes:**
- Added `plan_id` to `_EVENTS_EXT_COLS` list (auto-migrated if missing)
- Added `plan_id` column to `trades` table (migration with index)
- Updated `write_exec()` to accept and store `plan_id` parameter
- Updated `_insert_event_row()` to store `plan_id` in events table if column exists

**Migration:**
- Automatically adds `plan_id` column to `trades` table if missing
- Creates index on `plan_id` for efficient lookups
- Backward compatible (works with old schema)

---

### **2. Auto-Execution System Journal Logging** ✅

**File:** `auto_execution_system.py` (line ~6168)

**Changes:**
- Added journal logging in `_execute_trade()` method after successful execution
- Logs trade with `plan_id` linking execution to plan
- Includes all trade details (entry, SL, TP, volume, P/L, etc.)
- Graceful error handling (doesn't fail execution if journal logging fails)

**What Gets Logged:**
```python
journal_repo.write_exec({
    "ticket": ticket,
    "symbol": symbol_norm,
    "side": plan.direction,
    "entry": executed_price,
    "sl": plan.stop_loss,
    "tp": plan.take_profit,
    "lot": lot_size,
    "plan_id": plan.plan_id,  # NEW: Links trade to plan
    "notes": f"Auto-execution plan: {plan.plan_id} | {plan.notes}",
    # ... other fields
})
```

---

### **3. Plan-Trade Sync Module** ✅

**File:** `infra/plan_trade_sync.py` (NEW)

**Features:**
- `sync_closed_trades_to_plans()` - Syncs closed trades from journal to plan database
- `get_trade_with_plan()` - Gets closed trade with its originating plan details
- `get_recent_closed_trades_with_plans()` - Gets recent closed trades with plan context

**Sync Logic:**
- Queries journal database for closed trades with `plan_id`
- Updates plan database with trade outcomes (profit_loss, exit_price, close_time, close_reason)
- Only updates if data is missing or different (idempotent)
- Handles errors gracefully

---

### **4. ChatGPT Tools** ✅

**File:** `desktop_agent.py` (lines ~14350-14420)

**New Tools:**

#### **`moneybot.reviewClosedTrade`**
- **Purpose:** Review a closed trade with its originating plan details
- **Parameters:** `ticket` (required) - MT5 ticket number
- **Returns:** 
  - Trade details (entry, exit, P/L, duration, close reason)
  - Plan details (plan_id, conditions, strategy, notes, timeframe)
  - Whether plan exists (`has_plan`)

**Example Usage:**
```json
{
  "tool": "moneybot.reviewClosedTrade",
  "arguments": {
    "ticket": 123456789
  }
}
```

#### **`moneybot.syncPlanTrades`**
- **Purpose:** Sync closed trades from journal to plan effectiveness tracker
- **Parameters:** `days_back` (optional, default: 30) - Number of days to sync
- **Returns:** Sync statistics (synced_count, updated_count, errors)

**Example Usage:**
```json
{
  "tool": "moneybot.syncPlanTrades",
  "arguments": {
    "days_back": 30
  }
}
```

---

### **5. OpenAI YAML Configuration** ✅

**File:** `openai.yaml` (after `getAutoSystemStatus`)

**Added Tool Definitions:**
- `reviewClosedTrade` - Review closed trade with plan context
- `syncPlanTrades` - Sync mechanism for plan effectiveness

**Tool Descriptions:**
- Clear usage instructions
- Parameter documentation
- Example arguments
- Error handling guidance

---

## 📊 **Data Flow**

```
Auto-Execution Plan Executes
    ↓
Trade Executed (MT5)
    ↓
plan.ticket = ticket (stored in plan database)
    ↓
journal_repo.write_exec({..., plan_id: plan.plan_id}) (NEW)
    ↓
Trade Logged to Journal with plan_id
    ↓
Trade Closes (MT5)
    ↓
Journal Updated (closed_ts, exit_price, pnl, close_reason)
    ↓
syncPlanTrades() runs (manual or scheduled)
    ↓
Plan Database Updated (profit_loss, exit_price, close_time, close_reason)
    ↓
ChatGPT can review trade with plan context via reviewClosedTrade()
```

---

## 🔧 **Usage Examples**

### **For ChatGPT:**

**User:** "Review trade ticket 123456789"

**ChatGPT Response:**
```json
{
  "tool": "moneybot.reviewClosedTrade",
  "arguments": {
    "ticket": 123456789
  }
}
```

**Returns:**
- Trade: Entry, exit, P/L, duration, close reason
- Plan: Original plan conditions, strategy, notes, timeframe
- Analysis: Compare planned vs actual execution

---

### **Sync Trades to Plans:**

**User:** "Sync my closed trades to plan effectiveness"

**ChatGPT Response:**
```json
{
  "tool": "moneybot.syncPlanTrades",
  "arguments": {
    "days_back": 30
  }
}
```

**Returns:**
- Sync statistics
- Number of plans updated
- Any errors encountered

---

## ✅ **Benefits**

1. **Complete Trade Context:** ChatGPT can see both trade outcome AND original plan setup
2. **Plan Effectiveness:** Plans automatically updated with trade outcomes
3. **Performance Analysis:** Compare planned vs actual execution
4. **Learning:** Understand which plan conditions lead to wins/losses
5. **Backward Compatible:** Works with existing trades (plan_id may be null for old trades)

---

## 🔍 **Verification**

### **Check Journal Database:**
```sql
SELECT ticket, plan_id, pnl, exit_price, closed_ts 
FROM trades 
WHERE plan_id IS NOT NULL 
ORDER BY closed_ts DESC 
LIMIT 10;
```

### **Check Plan Database:**
```sql
SELECT plan_id, ticket, profit_loss, exit_price, close_time, close_reason
FROM trade_plans
WHERE status = 'executed' 
AND profit_loss IS NOT NULL
ORDER BY close_time DESC
LIMIT 10;
```

### **Test Sync:**
```python
from infra.plan_trade_sync import PlanTradeSync
sync = PlanTradeSync()
result = sync.sync_closed_trades_to_plans(days_back=30)
print(result)
```

### **Test Review:**
```python
from infra.plan_trade_sync import PlanTradeSync
sync = PlanTradeSync()
trade = sync.get_trade_with_plan(ticket=123456789)
print(trade)
```

---

## 📝 **Files Modified**

1. ✅ `infra/journal_repo.py` - Added plan_id column support
2. ✅ `auto_execution_system.py` - Added journal logging with plan_id
3. ✅ `infra/plan_trade_sync.py` - NEW: Sync mechanism module
4. ✅ `desktop_agent.py` - Added reviewClosedTrade and syncPlanTrades tools
5. ✅ `openai.yaml` - Added tool definitions

---

## 🚀 **Next Steps**

1. **Automatic Sync:** Consider adding scheduled sync (e.g., every hour) in `chatgpt_bot.py`
2. **Plan Effectiveness Updates:** Plan effectiveness tracker can now use synced data
3. **Historical Sync:** Run sync for older trades to backfill plan effectiveness data

---

## ✅ **Status**

**All implementation complete!** The system now:
- ✅ Logs plan_id when auto-execution plans execute
- ✅ Syncs closed trades to plan database
- ✅ Provides ChatGPT tools to review trades with plan context
- ✅ Maintains backward compatibility with existing trades

**Ready for testing and use!**
