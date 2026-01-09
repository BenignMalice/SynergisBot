# Trade Setup Watcher

## Overview

The **Trade Setup Watcher** is an automated system that continuously monitors market conditions and sends you real-time Telegram notifications when all criteria for a trade setup are met. This solves the problem you identified where you receive a "WAIT" recommendation but don't know when conditions improve.

## Problem Solved

**Before:** You get a multi-timeframe analysis showing:
- H4: BULLISH (85%)
- H1: CONTINUATION (80%)
- M30: BUY_SETUP (80%)
- M15: NONE (50%) ❌ - **Conflict!**
- M5: NO_TRADE (30%) ❌
- **Recommendation: WAIT**

You're left wondering: "When will M15 and M5 align?"

**After:** The bot automatically watches the setup and alerts you the moment all conditions are met!

## How It Works

### 1. **Multi-Timeframe Condition Tracking**

The system monitors **15 different conditions** across 5 timeframes:

**H4 Timeframe:**
- RSI >= 50 (for BUY) or <= 50 (for SELL)
- ADX >= 25 (trend strength)
- EMA alignment (bullish/bearish)

**H1 Timeframe:**
- RSI >= 50 (for BUY) or <= 50 (for SELL)
- MACD status (bullish/bearish)
- Price vs EMA20 (above/below)

**M30 Timeframe:**
- RSI >= 50 (for BUY) or <= 50 (for SELL)
- EMA alignment (bullish/bearish)
- ATR >= 5.0 (sufficient volatility)

**M15 Timeframe:**
- RSI >= 50 (for BUY) or <= 50 (for SELL)
- MACD status (bullish/bearish)
- Price vs EMA20 (above/below)

**M5 Timeframe:**
- RSI >= 50 (for BUY) or <= 50 (for SELL)
- MACD status (bullish/bearish)
- Price vs EMA20 (above/below)

### 2. **Confidence Scoring**

Each condition has a weight:
- RSI condition: 20 points
- MACD status: 15 points
- Price vs EMA20: 15 points
- EMA alignment: 10 points
- ADX condition: 10 points
- ATR condition: 5 points

**Overall confidence** = (Total points earned) / (Number of conditions checked)

### 3. **Background Monitoring**

The system runs **every 30 seconds** in the background, checking:
- XAUUSDc (Gold)
- EURUSD
- GBPUSD
- USDJPY
- AUDUSD

You can customize this list in `chatgpt_bot.py`.

### 4. **Smart Alerts**

When conditions are met, you receive a detailed Telegram notification with:
- **Entry Price**: Current ask/bid price
- **Stop Loss**: Entry - (2 × ATR) for BUY, Entry + (2 × ATR) for SELL
- **Take Profit**: Entry + (3 × ATR) for BUY, Entry - (3 × ATR) for SELL
- **Risk/Reward Ratio**: Calculated from SL and TP
- **All conditions status**: ✅ for met, ❌ for not met

## Usage

### Command: `/watch`

**Syntax:**
```
/watch SYMBOL ACTION [CONFIDENCE]
```

**Parameters:**
- `SYMBOL`: Trading symbol (e.g., XAUUSDc, EURUSD)
- `ACTION`: BUY or SELL
- `CONFIDENCE`: (Optional) Minimum confidence % required (default: 70)

**Examples:**

1. **Watch for a BUY setup on Gold:**
   ```
   /watch XAUUSDc BUY
   ```

2. **Watch for a SELL setup on EURUSD with 80% confidence:**
   ```
   /watch EURUSD SELL 80
   ```

3. **Watch for a BUY setup on GBPUSD:**
   ```
   /watch GBPUSD BUY
   ```

### What Happens Next

**Scenario 1: Conditions Already Met**
```
🎯 BUY SETUP ALERT - XAUUSDc

Confidence: 85%

Entry Price: 2000.50000
Stop Loss: 1980.50000
Take Profit: 2030.50000
Risk/Reward: 1:1.5

Conditions Met:
✅ H4 RSI 75.0 >= 50
✅ H4 EMA bullish
✅ H4 ADX 50.0 >= 25
...
✅ All conditions met! Setup is ready.
```

**Scenario 2: Waiting for Conditions**
```
🔍 Watching BUY Setup - XAUUSDc

Current Confidence: 65%
Required: 70%

Conditions:
✅ H4 RSI 75.0 >= 50
✅ H4 EMA bullish
✅ H4 ADX 50.0 >= 25
...
❌ M15 RSI 43.0 >= 50
❌ M15 MACD bearish == bullish
❌ 2 conditions not met

⏰ I'll monitor this setup and alert you when conditions are met!
```

Then, when M15 and M5 align:
```
🎯 BUY SETUP ALERT - XAUUSDc

Confidence: 85%

Entry Price: 2005.75000
Stop Loss: 1985.75000
Take Profit: 2035.75000
Risk/Reward: 1:1.5

Conditions Met:
✅ H4 RSI 75.0 >= 50
✅ H4 EMA bullish
✅ H4 ADX 50.0 >= 25
✅ H1 RSI 60.0 >= 50
✅ H1 MACD bullish == bullish
✅ H1 Price above EMA20
✅ M30 RSI 55.0 >= 50
✅ M30 EMA bullish
✅ M30 ATR 8.00 >= 5.0
✅ M15 RSI 52.0 >= 50 ← NOW MET!
✅ M15 MACD bullish == bullish ← NOW MET!
✅ M15 Price above EMA20
✅ M5 RSI 50.0 >= 50
✅ M5 MACD bullish == bullish
✅ M5 Price above EMA20

Action Required: Review and execute if conditions align with your strategy.
```

## Configuration

All settings are in `config.py` and can be customized via environment variables:

### Setup Monitoring
```python
SETUP_WATCHER_ENABLE = True  # Enable/disable the watcher
SETUP_WATCHER_INTERVAL = 30  # Check interval in seconds
SETUP_WATCHER_MIN_CONFIDENCE = 70  # Minimum confidence for alerts
```

### Setup Conditions
```python
SETUP_BUY_RSI_MIN = 50  # Minimum RSI for BUY setups
SETUP_SELL_RSI_MAX = 50  # Maximum RSI for SELL setups
SETUP_ADX_MIN = 25  # Minimum ADX for trend strength
SETUP_ATR_MIN = 5.0  # Minimum ATR for volatility
```

### Risk Management
```python
SETUP_STOP_ATR_MULT = 2.0  # Stop loss = entry ± (ATR × 2.0)
SETUP_TP_ATR_MULT = 3.0  # Take profit = entry ± (ATR × 3.0)
```

## Architecture

### Files Modified/Created

1. **`infra/trade_setup_watcher.py` (NEW)**
   - `TradeSetupCondition`: Dataclass for individual conditions
   - `TradeSetupAlert`: Dataclass for complete trade alerts
   - `TradeSetupWatcher`: Main class that monitors and generates alerts

2. **`config.py` (MODIFIED)**
   - Added 9 new configuration parameters for the watcher

3. **`chatgpt_bot.py` (MODIFIED)**
   - Added `check_trade_setups_async()`: Background task that runs every 30 seconds
   - Added `watch_command()`: `/watch` command handler
   - Updated help text to include new feature

### Integration with Existing Systems

The Trade Setup Watcher integrates seamlessly with:

- **IndicatorBridge**: Gets multi-timeframe analysis and ATR data
- **MT5Service**: Retrieves current prices for entry/SL/TP calculation
- **SessionAnalyzer**: (Future) Can add session-aware filtering
- **ExitSignalDetector**: (Future) Can integrate with exit logic

### Background Task Schedule

```
Position Monitor:     Every 60 seconds
Signal Scanner:       Every 5 minutes
Circuit Breaker:      Every 2 minutes
Trade Setup Watcher:  Every 30 seconds  ← NEW!
```

## Benefits

### 1. **Never Miss a Setup**
The bot watches 24/7 so you don't have to constantly refresh your analysis.

### 2. **Reduced Decision Fatigue**
Instead of manually checking 15 conditions across 5 timeframes, the bot does it for you.

### 3. **Faster Execution**
Get notified within 30 seconds of conditions aligning, allowing for optimal entry timing.

### 4. **Multi-Symbol Monitoring**
Watch multiple symbols simultaneously without additional effort.

### 5. **Quantified Confidence**
Clear percentage-based confidence score helps you gauge setup quality.

### 6. **Detailed Breakdown**
See exactly which conditions are met and which are missing.

## Example Workflow

**Step 1:** Analyze XAUUSDc using ChatGPT
```
You: "Analyze XAUUSDc for me"
Bot: [Multi-timeframe analysis]
     Recommendation: WAIT (72% alignment)
     M15: NONE (RSI=43, MACD=bearish)
```

**Step 2:** Start watching
```
You: "/watch XAUUSDc BUY 75"
Bot: 🔍 Watching BUY Setup - XAUUSDc
     Current Confidence: 65%
     ❌ 2 conditions not met
     ⏰ I'll monitor and alert you!
```

**Step 3:** Continue with your day
The bot monitors in the background while you:
- Work on other tasks
- Trade other instruments
- Review other opportunities

**Step 4:** Receive alert when ready
```
Bot: 🎯 BUY SETUP ALERT - XAUUSDc
     Confidence: 85%
     Entry: 2005.75
     Stop Loss: 1985.75
     Take Profit: 2035.75
     Risk/Reward: 1:1.5
     ✅ All conditions met!
```

**Step 5:** Execute with confidence
Now you can execute the trade knowing all timeframes are aligned!

## Troubleshooting

### Issue: Not receiving alerts

**Check:**
1. Is the bot running? Look for "Background jobs configured" in logs
2. Is the watcher enabled? Check `SETUP_WATCHER_ENABLE` in config
3. Is MT5 connected? The watcher requires MT5 connection
4. Is monitored_chat_id set? Use `/status` command first

### Issue: Too many alerts

**Solution:**
- Increase `SETUP_WATCHER_MIN_CONFIDENCE` (default: 70)
- Example: `/watch XAUUSDc BUY 80` for stricter criteria

### Issue: Alerts for wrong direction

**Check:**
- Verify you specified the correct ACTION (BUY vs SELL)
- The system only alerts for the action you requested

### Issue: Alerts too late

**Solution:**
- Decrease `SETUP_WATCHER_INTERVAL` from 30 to 15 seconds
- Note: Lower intervals = more CPU/API usage

## Future Enhancements

Potential additions to consider:

1. **Session Filtering**: Only alert during specific trading sessions
2. **News Blackout**: Pause alerts during high-impact news
3. **Volume Confirmation**: Add volume divergence checks
4. **Pattern Recognition**: Include candlestick patterns
5. **Machine Learning**: Predict probability of setup success
6. **Auto-Execution**: Optionally execute trades automatically
7. **Risk Simulation**: Integrate with risk_simulation module
8. **Multi-User Support**: Allow multiple users to watch different setups

## Summary

The Trade Setup Watcher transforms your trading workflow from:

**Manual Monitoring:**
- Check conditions manually every few minutes
- Risk missing optimal entry
- Decision fatigue from constant checking

**To Automated Alerting:**
- Bot monitors 24/7 automatically
- Get notified within 30 seconds
- Focus on execution, not monitoring

**Result:** More profitable trades with less stress and better timing! 🎯
