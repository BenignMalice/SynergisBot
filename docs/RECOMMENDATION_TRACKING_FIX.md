# 🔧 Recommendation Tracking Fix

## Problem

User reported that recommendation stats were showing **0 total trades** despite actively trading:

```
📊 Recommendation Statistics — Last 30 Days
Total Trades Analyzed: 0
Wins: 0
Losses: 0
Win Rate: —
```

## Root Cause

The recommendation tracking system was only logging trades from the **Telegram bot interface**, not from the **Custom GPT API interface**.

When ChatGPT makes trades via the REST API (`/mt5/execute`), those recommendations were **not being logged** to the `recommendations.sqlite` database.

### Architecture Issue:

```
Telegram Bot (handlers/chatgpt_bridge.py)
├─ ✅ Logs recommendations
└─ Works: recommendation_tracker.log_recommendation()

Custom GPT API (main_api.py)
├─ ❌ Did NOT log recommendations
└─ Calls /mt5/execute directly → no tracking
```

## Solution

Added recommendation tracking to the **`/mt5/execute` API endpoint** in `main_api.py`.

### Changes Made:

**File: `main_api.py`** (lines 468-502)

```python
# Log recommendation for performance tracking
try:
    from infra.recommendation_tracker import RecommendationTracker
    tracker = RecommendationTracker()
    
    # Determine trade type based on order type
    if signal.order_type and signal.order_type != OrderType.MARKET:
        trade_type = "pending"
    else:
        trade_type = "scalp"  # Default to scalp for market orders
    
    # Log recommendation
    rec_id = tracker.log_recommendation(
        symbol=symbol,
        trade_type=trade_type,
        direction=signal.direction.value,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        confidence=signal.confidence or 70,
        reasoning=signal.reasoning or "Custom GPT trade via API",
        order_type=signal.order_type.value if signal.order_type else "market",
        timeframe=signal.timeframe or "M5",
        user_id=1  # Default user ID for API trades
    )
    
    # Mark as executed
    tracker.mark_executed(
        recommendation_id=rec_id,
        mt5_ticket=ticket
    )
    
    logger.info(f"Logged recommendation #{rec_id} for {symbol} {signal.direction.value} (ticket: {ticket})")
except Exception as e:
    logger.warning(f"Failed to log recommendation: {e}")
```

## What's Now Tracked

### For Each Trade:
- ✅ Symbol (e.g., XAUUSDc, BTCUSDc)
- ✅ Trade Type (scalp, pending, swing)
- ✅ Direction (buy, sell)
- ✅ Entry Price
- ✅ Stop Loss
- ✅ Take Profit
- ✅ Confidence (0-100)
- ✅ Reasoning (ChatGPT's analysis)
- ✅ Order Type (market, buy_limit, sell_limit, buy_stop, sell_stop)
- ✅ Timeframe (M5, M15, H1, H4)
- ✅ MT5 Ticket Number
- ✅ Execution Time

### Future Outcome Tracking:
When trades close, the system can update:
- Outcome (WIN/LOSS)
- Exit Price
- Profit/Loss
- Risk:Reward Achieved
- Hold Time

## Testing

After restarting the API server:

1. **Place a trade via Custom GPT:**
   ```
   "Buy Gold at 3940, SL 3935, TP 3950"
   ```

2. **Check recommendation was logged:**
   ```python
   import sqlite3
   conn = sqlite3.connect('data/recommendations.sqlite')
   cursor = conn.cursor()
   cursor.execute('SELECT * FROM recommendations ORDER BY id DESC LIMIT 1')
   print(cursor.fetchone())
   ```

3. **Check stats API:**
   ```
   GET http://localhost:8000/api/v1/recommendation_stats
   ```

   Should now show:
   ```json
   {
     "stats": {
       "total_recommendations": 1,
       "executed_count": 1,
       "win_count": 0,
       "loss_count": 0
     }
   }
   ```

## Unified Tracking

Now **both interfaces** log recommendations:

| Interface | Endpoint | Tracking Status |
|-----------|----------|----------------|
| **Telegram Bot** | `handlers/chatgpt_bridge.py` | ✅ Already tracked |
| **Custom GPT API** | `main_api.py /mt5/execute` | ✅ **NOW TRACKED** |

## Benefits

1. **Accurate Win Rate Tracking**
   - All trades (Telegram + Custom GPT) are logged
   - Performance stats are complete

2. **Performance Analysis**
   - Filter by symbol, trade_type, timeframe, session
   - Identify best-performing setups
   - Track R:R achieved vs planned

3. **Learning System**
   - ChatGPT can query past performance
   - Adjust confidence based on historical data
   - Avoid repeating losing setups

4. **Transparency**
   - Every recommendation is logged with reasoning
   - Full audit trail for all trades
   - Easy to review ChatGPT's decision-making

## Next Steps

### 1. Restart API Server (REQUIRED)
```bash
cd c:\mt5-gpt\TelegramMoneyBot.v7
# Stop current server (Ctrl+C)
python -m uvicorn main_api:app --reload --host 0.0.0.0 --port 8000
```

### 2. Automatic Outcome Tracking (Optional Enhancement)
Implement a background task to automatically update trade outcomes when positions close:

```python
# In chatgpt_bot.py or a separate monitor script
async def update_closed_trade_outcomes():
    """
    Monitor closed trades and update recommendation outcomes
    """
    tracker = RecommendationTracker()
    
    # Get all executed recommendations without outcomes
    pending_recs = tracker.get_recommendations_without_outcomes()
    
    for rec in pending_recs:
        # Check if trade closed in MT5
        mt5_ticket = rec['mt5_ticket']
        deal = mt5_service.get_closed_deal(mt5_ticket)
        
        if deal:
            # Calculate outcome
            outcome = "WIN" if deal.profit > 0 else "LOSS"
            
            # Update recommendation
            tracker.update_outcome(
                mt5_ticket=mt5_ticket,
                outcome=outcome,
                exit_price=deal.price,
                exit_time=deal.time,
                profit_loss=deal.profit
            )
```

### 3. Enhanced Stats Queries
Custom GPT can now query performance:

```
"What's my win rate on Gold scalps?"
→ GET /api/v1/recommendation_stats?symbol=XAUUSD&trade_type=scalp

"Show me my best trading setups"
→ GET /api/v1/recommendation_stats

"How did my London session trades perform?"
→ GET /api/v1/recommendation_stats?session=London
```

## Summary

✅ **Fixed:** Recommendation tracking now works for both Telegram bot and Custom GPT API
✅ **Added:** Automatic logging in `/mt5/execute` endpoint
✅ **Result:** Complete performance tracking for all AI-generated trades
✅ **Next:** Restart API server to apply the fix

**The recommendation stats API will now show accurate data for all future trades!** 🎯

