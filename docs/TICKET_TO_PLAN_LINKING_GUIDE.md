# How ChatGPT Links MT5 Ticket Numbers to Auto-Execution Plan IDs

## Overview

When a user provides MT5 ticket numbers and asks ChatGPT to review the auto-execution plan for those trades, ChatGPT can now directly look up the plan information using the ticket number.

---

## How It Works

### 1. **When Auto-Execution Plan Executes**

When an auto-execution plan successfully executes a trade:

```python
# In auto_execution_system.py, _execute_trade() method
plan.status = "executed"
plan.executed_at = datetime.now(timezone.utc).isoformat()
plan.ticket = ticket  # <-- MT5 ticket number is stored here
self._update_plan_status(plan)  # <-- Saves to database
```

**Database Storage:**
- `plan_id` (e.g., "chatgpt_10ef0d76") → Unique identifier for the plan
- `ticket` (e.g., 169674998) → MT5 position ticket number
- `status` → "executed"
- `executed_at` → Timestamp when trade was executed

**The Connection:**
```
plan_id (chatgpt_10ef0d76) ←→ ticket (169674998) ←→ MT5 Position
```

---

### 2. **ChatGPT Tool: `moneybot.get_auto_plan_status`**

ChatGPT can now query plans by ticket number:

**Query by Ticket Number:**
```json
{
  "ticket": 169674998
}
```

**Query by Plan ID:**
```json
{
  "plan_id": "chatgpt_abc123"
}
```

**Get All Plans:**
```json
{}
```

---

### 3. **How ChatGPT Uses This**

**When User Says:**
- "Review ticket 169674998"
- "What plan created ticket 169674999?"
- "Show me the auto-execution plan for ticket 169675000"

**ChatGPT Should:**
1. Use `moneybot.get_auto_plan_status` with `ticket` parameter
2. The system automatically:
   - Looks up `plan_id` from `ticket` in the database
   - Retrieves full plan details
   - Returns plan information including:
     - Plan ID, symbol, direction
     - Entry price, stop loss, take profit
     - Conditions that triggered execution
     - Status, execution timestamp
     - Notes and reasoning

**Example Response:**
```json
{
  "summary": "Plan chatgpt_abc123: BTCUSDc BUY - Status: executed (Ticket: 169674998)",
  "data": {
    "success": true,
    "plan": {
      "plan_id": "chatgpt_abc123",
      "symbol": "BTCUSDc",
      "direction": "BUY",
      "entry_price": 90181.21,
      "stop_loss": 90131.20,
      "take_profit": 90320.00,
      "status": "executed",
      "ticket": 169674998,
      "executed_at": "2025-12-14T04:44:06Z",
      "conditions": {
        "price_near": 90181.21,
        "tolerance": 100.0,
        "choch_bull": true,
        "timeframe": "M5"
      },
      "notes": "CHOCH Bull setup - wait for M5 structure confirmation"
    }
  }
}
```

---

### 4. **API Endpoint**

**Endpoint:** `GET /auto-execution/status`

**Query Parameters:**
- `plan_id` (optional): Plan ID string
- `ticket` (optional): MT5 ticket number (integer)
- `include_all` (optional): Include executed/cancelled plans (default: false)

**Examples:**
- `GET /auto-execution/status?ticket=169674998`
- `GET /auto-execution/status?plan_id=chatgpt_abc123`
- `GET /auto-execution/status?include_all=true` (get all plans)

---

### 5. **Database Query**

The system queries the database:

```sql
SELECT plan_id FROM trade_plans WHERE ticket = ?
```

If found, retrieves the full plan details and returns them.

---

### 6. **Error Handling**

**If Ticket Not Found:**
```json
{
  "success": false,
  "message": "No auto-execution plan found for ticket 169674998"
}
```

**Possible Reasons:**
- Ticket number doesn't exist in database
- Trade was executed manually (not from auto-execution plan)
- Trade was executed before auto-execution system was implemented
- Database connection issue

---

## Summary

**For ChatGPT:**
- When user provides ticket numbers, use `moneybot.get_auto_plan_status` with `ticket` parameter
- The system automatically links ticket → plan_id → full plan details
- Returns complete plan information for review

**For Users:**
- Simply provide ticket numbers from MT5
- ChatGPT can look up and review the auto-execution plan that created each trade
- See entry conditions, SL/TP, reasoning, and execution details

---

## Files Modified

1. ✅ `app/auto_execution_api.py` - Added `ticket` parameter to `/status` endpoint
2. ✅ `chatgpt_auto_execution_tools.py` - Added `ticket` parameter support to `tool_get_auto_plan_status`
3. ✅ `openai.yaml` - Updated tool description to mention ticket lookup
4. ✅ `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_INSTRUCTIONS.md` - Added ticket lookup documentation
5. ✅ `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md` - Added ticket lookup documentation

**Status:** ✅ **Implemented** - ChatGPT can now look up plans by ticket number
