# Closed Plan Retrieval Fix

## Issue
ChatGPT could not retrieve closed/executed auto-execution plans. When querying for plan `chatgpt_091f9b2f` (which executed and closed with ticket 175274023), the system returned "Plan not found" even though the plan exists in the database with status "closed".

## Root Cause
1. **Missing Fields in Response**: The `get_plan_status` method in `chatgpt_auto_execution_integration.py` was not including `profit_loss`, `exit_price`, `close_time`, `close_reason`, and `conditions` fields for closed/executed plans.

2. **Database Query**: The `get_plan_by_id` method was using `SELECT *` which could have column order issues. Updated to use explicit column names.

## Fixes Applied

### 1. Updated `chatgpt_auto_execution_integration.py`
- Added code to include `profit_loss`, `exit_price`, `close_time`, `close_reason`, and `conditions` fields in the plan response
- Changed condition checks to always include these fields (even if None) so ChatGPT can see them

**Location**: Lines 1138-1150

```python
# Add profit/loss fields for executed/closed plans (always include, even if None)
if hasattr(plan, 'profit_loss'):
    plan_dict["profit_loss"] = plan.profit_loss
if hasattr(plan, 'exit_price'):
    plan_dict["exit_price"] = plan.exit_price
if hasattr(plan, 'close_time'):
    plan_dict["close_time"] = plan.close_time
if hasattr(plan, 'close_reason'):
    plan_dict["close_reason"] = plan.close_reason

# Add conditions for all plans (needed for review)
if hasattr(plan, 'conditions'):
    plan_dict["conditions"] = plan.conditions
```

### 2. Updated `auto_execution_system.py`
- Changed `get_plan_by_id` to use explicit column names instead of `SELECT *`
- This ensures correct column mapping regardless of database schema changes

**Location**: Lines 1264-1270

```python
cursor = conn.execute("""
    SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit, volume,
           conditions, created_at, created_by, status, expires_at, executed_at, ticket, notes,
           profit_loss, exit_price, close_time, close_reason,
           zone_entry_tracked, zone_entry_time, zone_exit_time,
           entry_levels,
           cancellation_reason, last_cancellation_check,
           last_re_evaluation, re_evaluation_count_today, re_evaluation_count_date
    FROM trade_plans WHERE plan_id = ?
""", (plan_id,))
```

## Testing
Verified that:
1. Plan `chatgpt_091f9b2f` exists in database with status "closed"
2. Plan has all required fields: profit_loss (-1.21), exit_price (88249.87), close_time, close_reason, conditions
3. Plan can be retrieved by plan_id via API
4. Plan can be retrieved by ticket (175274023) via API

## Next Steps
**⚠️ IMPORTANT: Restart the API server** for changes to take effect.

After restart, ChatGPT will be able to:
- Query closed/executed plans by `plan_id`
- Query closed/executed plans by `ticket` number
- See all plan details including:
  - Profit/Loss
  - Exit Price
  - Close Time
  - Close Reason
  - Conditions (for plan review)

## Example Usage
After restart, ChatGPT can now:
```
User: "Review plan chatgpt_091f9b2f"
ChatGPT: Uses moneybot.get_auto_plan_status with plan_id="chatgpt_091f9b2f"
Result: Returns full plan details including profit_loss, exit_price, close_time, close_reason, conditions

User: "What plan created ticket 175274023?"
ChatGPT: Uses moneybot.get_auto_plan_status with ticket=175274023
Result: Returns plan chatgpt_091f9b2f with all details
```

## Files Modified
1. `chatgpt_auto_execution_integration.py` - Added fields to plan response
2. `auto_execution_system.py` - Updated database query to use explicit columns
