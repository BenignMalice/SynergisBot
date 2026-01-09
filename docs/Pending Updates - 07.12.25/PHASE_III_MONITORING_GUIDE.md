# Phase III Condition Monitoring Guide

**Date**: 2026-01-07  
**Status**: ✅ Plans Created - Monitoring Active

---

## Current Test Plans Status

### Plan 1: Multi-Timeframe Confluence
- **Plan ID**: `chatgpt_1d801fab`
- **Status**: PENDING ✅
- **UI Visible**: ✅ Yes (http://localhost:8000/auto-execution/view)
- **Phase III Conditions**:
  - `choch_bull_m5: true`
  - `choch_bull_m15: true`
  - `min_confluence: >=75`
  - `price_near: 4480.0 ±2.0`

### Plan 2: Volatility Pattern Recognition
- **Plan ID**: `chatgpt_be4af5f0`
- **Status**: PENDING ✅
- **UI Visible**: ✅ Yes (http://localhost:8000/auto-execution/view)
- **Phase III Conditions**:
  - `consecutive_inside_bars: 3`
  - `volatility_fractal_expansion: true`
  - `bb_expansion: true`
  - `price_above: 4480.0`
  - `price_near: 4482.0 ±2.0`
  - `min_confluence: >=70`

---

## How to Monitor Condition Checks

### 1. **API Server Console Window** (Primary Method)

**Location**: The console window where `app/main_api.py` is running

**What to Look For**:
- Condition check messages appear in real-time
- Look for messages containing plan IDs: `chatgpt_1d801fab` or `chatgpt_be4af5f0`
- Phase III condition checks may appear as:
  - `DEBUG` level: Detailed condition evaluation
  - `INFO` level: Plan check summaries
  - `WARNING` level: Condition failures or blocks

**Example Messages to Look For**:
```
[INFO] Checking plan chatgpt_1d801fab...
[DEBUG] Phase III: Checking choch_bull_m5 condition...
[DEBUG] Phase III: Checking choch_bull_m15 condition...
[INFO] Plan chatgpt_1d801fab: Conditions not met (waiting for CHOCH)
```

### 2. **Log File Monitoring** (Secondary Method)

**File**: `data/logs/chatgpt_bot.log`

**Command** (PowerShell):
```powershell
Get-Content "data\logs\chatgpt_bot.log" -Tail 50 -Wait
```

**What to Look For**:
- Auto-execution system activity messages
- Plan check summaries (every 30 seconds)
- Phase III initialization messages
- Condition check results (if logged at INFO level)

**Recent Activity**:
- System is checking 35 pending plans every 30 seconds
- Processing 4 order flow plans specifically
- Some plans blocked by news blackout windows

### 3. **UI Monitoring** (Visual Method)

**URL**: `http://localhost:8000/auto-execution/view`

**What to Monitor**:
- Plan status changes (PENDING → EXECUTING → EXECUTED)
- Condition fulfillment indicators
- Execution timestamps
- Plan cancellation reasons (if any)

**Current Status**:
- ✅ Both plans visible in UI
- ✅ Phase III conditions displayed correctly
- ✅ Status: PENDING (awaiting condition fulfillment)

---

## Expected Condition Check Behavior

### Plan 1: M5-M15 CHOCH Sync

**Conditions Checked Every 30 Seconds**:
1. `choch_bull_m5: true` - M5 structure must flip bullish
2. `choch_bull_m15: true` - M15 structure must flip bullish
3. `price_near: 4480.0 ±2.0` - Price must be within 2.0 points of 4480.0
4. `min_confluence: >=75` - Confluence score must be ≥75

**Execution Trigger**:
- All conditions must be TRUE simultaneously
- System validates multi-TF alignment automatically
- Plan executes when price enters tolerance zone AND both CHOCHs confirmed

### Plan 2: Volatility Fractal Expansion

**Conditions Checked Every 30 Seconds**:
1. `consecutive_inside_bars: 3` - Must detect 3+ consecutive inside bars
2. `volatility_fractal_expansion: true` - BB width expands >20% AND ATR increases >15%
3. `bb_expansion: true` - Bollinger Band expansion confirmed
4. `price_above: 4480.0` - Price must break above 4480.0
5. `price_near: 4482.0 ±2.0` - Price must be within 2.0 points of 4482.0
6. `min_confluence: >=70` - Confluence score must be ≥70

**Execution Trigger**:
- All conditions must be TRUE simultaneously
- Volatility pattern must be confirmed (compression → expansion)
- Plan executes when price breaks above 4480.0 AND enters tolerance zone

---

## Monitoring Checklist

### Immediate Checks
- [x] Plans created in database
- [x] Plans visible in UI
- [x] Phase III conditions stored correctly
- [x] Auto-execution system running
- [ ] Condition checks appearing in logs/console
- [ ] Plans executing when conditions met

### Ongoing Monitoring
- [ ] Check API server console every 30-60 seconds
- [ ] Monitor UI for status changes
- [ ] Review logs for condition check messages
- [ ] Verify Phase III conditions are being evaluated
- [ ] Confirm execution when all conditions met

---

## Troubleshooting

### If No Condition Checks Appear

1. **Check API Server Status**:
   - Verify API server is running
   - Check console window for errors
   - Restart if needed

2. **Check Plan Status**:
   - Verify plans are in `pending` status
   - Check if plans were cancelled
   - Verify plans haven't expired

3. **Check Logging Level**:
   - Condition checks may be at DEBUG level
   - Enable DEBUG logging if needed
   - Check console window (not just log file)

4. **Wait for Check Cycle**:
   - System checks every 30 seconds
   - Wait 30-60 seconds after plan creation
   - Check again after next cycle

### If Plans Don't Execute

1. **Verify Market Conditions**:
   - Plans only execute when conditions are met
   - Check if CHOCH/BOS has occurred
   - Verify volatility patterns are present
   - Confirm price is in tolerance zone

2. **Check for Blocks**:
   - News blackout windows may block execution
   - High-impact news events block plans
   - Check logs for BLOCKED messages

3. **Verify Data Availability**:
   - Phase III conditions require data sources
   - Multi-TF data must be available
   - Volatility pattern data must be current

---

## Next Steps

1. **Monitor Real-Time**: Watch API server console window
2. **Check UI Regularly**: Visit http://localhost:8000/auto-execution/view
3. **Review Logs**: Check `data/logs/chatgpt_bot.log` for activity
4. **Wait for Conditions**: Plans will execute automatically when conditions are met
5. **Test During Market Hours**: Best results during active trading hours

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-07  
**Status**: ✅ Monitoring Guide Complete

