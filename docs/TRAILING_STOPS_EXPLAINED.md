# How Trailing Stops Work for Live Trades

## Overview

Trailing stops are automatically managed by the **Intelligent Exit Manager** system, which runs continuously in the background via `chatgpt_bot.py`. Trailing stops activate **after breakeven** and automatically trail the stop loss as price moves in your favor, protecting profits while allowing trades to continue running.

---

## System Architecture

### Components:
1. **Intelligent Exit Manager** (`infra/intelligent_exit_manager.py`)
   - Manages breakeven, partial profits, and trailing stops
   - Monitors all open positions with exit rules
   - Executes actions via MT5

2. **Monitoring Loop** (`chatgpt_bot.py`)
   - Background scheduler runs `check_intelligent_exits_async()` every 30 seconds
   - Checks all positions and executes trailing stop updates
   - Sends Discord notifications when trailing stops move

---

## How Trailing Stops Work

### 1. **Activation Sequence**

Trailing stops activate **automatically** after breakeven is triggered:

```
Step 1: Trade Opens
├─ Entry: 3950
├─ Initial SL: 3900
└─ Initial TP: 4000

Step 2: Price Moves in Favor
├─ Current Price: 3956 (30% of potential profit)
└─ Breakeven Triggered ✅
   └─ SL moved to: 3950 (entry price + spread)

Step 3: Trailing Stops Activate
├─ rule.trailing_active = True ✅
└─ System now trails SL on every check cycle
```

### 2. **Trailing Stop Calculation**

**Formula:**
```
For BUY trades:
  New SL = Current Price - (1.5 × ATR)

For SELL trades:
  New SL = Current Price + (1.5 × ATR)
```

**Where:**
- **ATR** = Average True Range calculated from M30 candles (14-period)
- **1.5× ATR** = Professional standard trailing distance
- **Current Price** = Latest bid/ask price from MT5

### 3. **Real-Time Example**

**BUY Trade Example:**

```
Initial Setup:
- Entry: 3950
- Initial SL: 3900
- TP: 4000

Price Movement Timeline:

Time 10:00 - Price: 3950 (Entry)
└─ SL: 3900 (Initial)

Time 10:15 - Price: 3956 (30% to TP = Breakeven Triggered!)
└─ SL: 3950 (Moved to breakeven)
└─ Trailing: ✅ ACTIVATED

Time 10:30 - Price: 3960, ATR: 5.0
├─ Calculate: 3960 - (1.5 × 5.0) = 3952.50
├─ Current SL: 3950
├─ New SL: 3952.50 (Better! ✅)
└─ Action: SL updated to 3952.50

Time 10:45 - Price: 3965, ATR: 5.0
├─ Calculate: 3965 - (1.5 × 5.0) = 3957.50
├─ Current SL: 3952.50
├─ New SL: 3957.50 (Better! ✅)
└─ Action: SL updated to 3957.50

Time 11:00 - Price: 3960, ATR: 5.0
├─ Calculate: 3960 - (1.5 × 5.0) = 3952.50
├─ Current SL: 3957.50
├─ New SL: 3952.50 (Worse! ❌)
└─ Action: SKIPPED (never moves backwards)

Time 11:15 - Price: 3970, ATR: 5.2
├─ Calculate: 3970 - (1.5 × 5.2) = 3962.20
├─ Current SL: 3957.50
├─ New SL: 3962.20 (Better! ✅)
└─ Action: SL updated to 3962.20
```

---

## Key Features

### ✅ Safety Rules

1. **Never Moves Backwards**
   - Trailing stops only move SL in favorable direction
   - BUY: New SL must be > current SL
   - SELL: New SL must be < current SL

2. **Minimum Change Threshold**
   - Only updates if change > 0.05% of current price
   - Prevents excessive tiny adjustments

3. **ATR-Based Distance**
   - Adapts to market volatility automatically
   - High volatility = wider trailing distance
   - Low volatility = tighter trailing distance

4. **Gating System**
   - Trailing only activates when conditions are favorable:
     - Breakeven already triggered
     - Profit >= 0.6R OR partial profit already taken
     - Volatility not in squeeze state
     - Multi-timeframe alignment >= 2
     - Price not stretched beyond 2.0 ATR
     - Not near HVN (High Volume Node) magnet

---

## Monitoring Cycle

### Check Frequency

**Every 30 seconds:**
- `chatgpt_bot.py` runs `check_intelligent_exits_async()`
- Checks all positions with intelligent exit rules
- Calculates new trailing SL if conditions met
- Updates MT5 position if improvement found

### Data Sources

1. **Current Price**: From MT5 `position.price_current`
2. **ATR Calculation**: 
   - Fetches last 50 M30 candles via `mt5.copy_rates_from_pos()`
   - Calculates True Range (TR) for each candle
   - Averages last 14 TR values = ATR

3. **Position Data**: 
   - Current SL from `position.sl`
   - Entry price from `rule.entry_price`
   - Direction from `rule.direction`

---

## Code Flow

### 1. Background Scheduler
```python
# chatgpt_bot.py - Every 30 seconds
scheduler.add_job(
    check_intelligent_exits_async,
    'interval',
    seconds=30,
    id='intelligent_exits_check'
)
```

### 2. Check All Positions
```python
# intelligent_exit_manager.py
def check_exits() -> List[Dict]:
    positions = mt5.positions_get()
    for rule in self.rules.values():
        actions = self._check_position_exits(rule, position, vix_price)
        # Returns list of actions taken
```

### 3. Trailing Stop Logic
```python
# intelligent_exit_manager.py - _trail_stop_atr()
if rule.trailing_active and rule.breakeven_triggered:
    # Calculate ATR from M30 candles
    atr = calculate_atr(symbol, period=14)
    
    # Calculate new trailing SL
    trailing_distance = atr * 1.5
    new_sl = current_price - trailing_distance  # BUY
    
    # Only update if better than current
    if new_sl > current_sl:
        modify_position_sl(ticket, new_sl)
```

---

## When Trailing Stops DON'T Update

1. **Price Moves Against You**
   - If price retraces, new SL would be worse
   - System keeps current SL (never moves backwards)

2. **Change Too Small**
   - If change < 0.05% of price, skip update
   - Avoids broker fees from excessive modifications

3. **ATR Unavailable**
   - If can't fetch M30 candles
   - If ATR = 0 (insufficient data)
   - System waits for next cycle

4. **Gates Not Passed**
   - If advanced gates block trailing (volatility squeeze, stretched price, etc.)
   - Trailing remains disabled until conditions improve

---

## Viewing Trailing Stop Activity

### 1. **Discord Notifications**
- Real-time alerts when trailing stops update
- Shows: Old SL → New SL, ATR value, trailing distance

### 2. **Database Logs**
- All trailing stop actions logged to `intelligent_exits` database
- Includes: timestamp, old_sl, new_sl, atr, details

### 3. **DTMS Dashboard**
- View at `http://localhost:8010/dtms/status`
- Shows active trades and their protection status
- Action history shows trailing stop updates

---

## Configuration

### Settings (`config/settings.py`)

```python
INTELLIGENT_EXITS_TRAILING_ENABLED = True  # Enable/disable trailing
INTELLIGENT_EXITS_BREAKEVEN_PCT = 30.0     # % of TP to trigger breakeven
INTELLIGENT_EXITS_PARTIAL_PCT = 60.0       # % of TP to trigger partial
```

### Per-Trade Customization

When adding intelligent exit rule, you can customize:
- `trailing_enabled`: Enable/disable for this trade
- `breakeven_profit_pct`: When to move to breakeven
- Advanced features can adjust triggers based on market conditions

---

## Example Notification

When trailing stop updates, you'll receive a Discord notification:

```
📈 ATR Trailing Stop for XAUUSD (ticket 134832407):
3942.50 → 3947.50 | ATR=5.0, Distance=7.5

Details:
- Symbol: XAUUSD
- Direction: BUY
- Current Price: 3955.00
- Trailing Distance: 7.5 (1.5 × ATR)
- Profit Protected: +12.50 points
```

---

## Important Notes

1. **Requires chatgpt_bot.py Running**
   - Trailing stops only work when the bot is actively running
   - If bot stops, trailing stops pause until bot restarts

2. **After Breakeven Only**
   - Trailing activates after breakeven is triggered
   - Before breakeven, SL stays at initial level

3. **Continuous Updates**
   - System checks every 30 seconds
   - Updates SL whenever price improves by sufficient amount

4. **Never Moves Backwards**
   - If price retraces, SL stays at highest/lowest level achieved
   - Protects maximum profit locked in

---

## Summary

Trailing stops work by:
1. ✅ Activating automatically after breakeven
2. ✅ Calculating new SL = Current Price ± (1.5 × ATR) every 30 seconds
3. ✅ Only updating if new SL is better (protects profits)
4. ✅ Adapting to market volatility via ATR
5. ✅ Logging all actions to database and Discord

This ensures your profitable trades are protected while allowing them to continue running toward full TP.

