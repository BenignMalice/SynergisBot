# Fresh Flag Explanation

## Why `fresh=False`?

**Your case:**
- **Age**: 13.1 minutes
- **Timeframe**: M5 (5-minute candles)
- **Threshold**: 5.5 minutes (M5 period + 0.5 min buffer)
- **Result**: `13.1 min > 5.5 min` → `fresh=False`

### Freshness Thresholds:

| Timeframe | Threshold | Reason |
|-----------|-----------|--------|
| M1 | 1.5 min | 1 min period + 0.5 min buffer |
| **M5** | **5.5 min** | **5 min period + 0.5 min buffer** |
| M15 | 15.5 min | 15 min period + 0.5 min buffer |
| H1 | 60.5 min | 60 min period + 0.5 min buffer |

**Why 13.1 minutes is stale:**
- M5 candles close every 5 minutes
- Latest complete candle should be ≤ 5.5 minutes old
- 13.1 minutes means the streamer database hasn't been updated in ~2.5 candle periods
- This indicates the streamer refresh loop may not be working, or data is from an old database read

## What Happens When `fresh=False`?

### 1. **Automatic Fallback to MT5** (If from Streamer Database)

When data is read from the streamer database and `fresh=False`:
- **Action**: System raises `ValueError` to trigger immediate MT5 fetch
- **Log**: `"🔄 Streamer data stale (13.1 min > 5.5 min threshold) - fetching fresh from MT5 on-demand"`
- **Result**: System attempts to get fresh data directly from MT5 API

### 2. **If MT5 Fetch Also Returns Stale Data**

If MT5 direct fetch also returns stale data:
- **Log**: `"ℹ️ MT5 direct fetch returned 13.1 min old candle (threshold: 5.5 min). This is the freshest available from MT5."`
- **Meaning**: Market may be genuinely slow, or MT5 connection issues

### 3. **Trade Blocking** (In `check_data_quality()`)

When `fresh=False` is returned from `_check_candle_freshness()`:
- **Action**: Sets `all_available = False`
- **Warning Added**: `"❌ MT5 candles unavailable/stale (13.1 min old) - BLOCKING TRADE"`
- **Result**: **Trade is BLOCKED** - range scalping analysis will not proceed

### 4. **What Doesn't Happen When `fresh=False`:**

- ❌ Range scalping analysis does NOT proceed
- ❌ No trade execution
- ❌ No confluence calculation
- ❌ No range detection
- ❌ System waits for fresh data before continuing

## Why This Matters:

**Data Quality Requirement:**
- Range scalping requires **fresh, real-time data** to:
  - Calculate accurate VWAP
  - Detect current range boundaries
  - Assess confluence correctly
  - Make valid trading decisions

**13.1 minutes is too old because:**
- Market conditions can change significantly in 13 minutes
- VWAP calculations become inaccurate
- Range boundaries may have shifted
- Price may have moved outside the detected range

## Expected Behavior:

**Normal Operation:**
- Streamer should refresh M5 candles every 5 minutes
- Age should be ≤ 5.5 minutes
- `fresh=True` should be the norm

**When `fresh=False`:**
- System attempts to fetch fresh data from MT5
- If still stale after MT5 fetch → Trade is blocked
- This is a **safety feature** to prevent trading on stale data

## Potential Issues:

1. **Streamer not refreshing**: Streamer database may not be updating
2. **Database read from old snapshot**: Reading from cached/old database state
3. **MT5 connection issues**: If MT5 also returns stale data, connection may be down
4. **Market closure**: For forex, >6 hours old = market closed

## What to Check:

1. Is the streamer running? (`streamer.is_running`)
2. Is the streamer updating the database?
3. Is MT5 connection active?
4. Are there any streamer errors in logs?

