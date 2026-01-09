# Optimized 10-Second Interval Monitoring Guide

**Date:** 2025-12-21  
**Purpose:** Guide for monitoring and verifying the optimized interval system

---

## Quick Verification

### 1. Check Config File
```bash
# Verify config file exists and is valid
python -m json.tool config/auto_execution_optimized_intervals.json
```

### 2. Check System Startup Logs
When the auto-execution system starts, look for these messages:

**Expected Startup Messages:**
```
[INFO] Smart caching: Pre-fetch thread started
[INFO] Optimized intervals system ENABLED:
[INFO]   - Adaptive intervals: ENABLED (M1 base: 10s)
[INFO]   - Smart caching: ENABLED
[INFO]   - Conditional checks: ENABLED
[INFO]   - Batch operations: ENABLED
```

**If Disabled:**
```
[INFO] Optimized intervals system: DISABLED (enable via config file)
```

---

## Monitoring Adaptive Intervals

### What to Look For

**Debug Log Messages:**
- `Adaptive interval for {plan_id} ({plan_type}): {interval}s (price: ..., entry: ..., distance: ..., tolerance: ...)`
- `Adaptive interval: Skipping {plan_id} - only {time}s since last check (required: {interval}s)`

**Expected Behavior:**
- M1 micro-scalp plans should show intervals of 5s, 10s, or 30s depending on price proximity
- Plans close to entry (within tolerance) → 5s interval
- Plans within 2× tolerance → 10s interval
- Plans far from entry → 30s interval

### Verification Steps

1. **Check Plan Type Detection:**
   - M1 plans with `liquidity_sweep`, `order_block`, `equal_lows/highs`, or `vwap_deviation` → `m1_micro_scalp`
   - Should use 10s base interval

2. **Monitor Check Frequency:**
   - Plans near entry should be checked more frequently (5-10s)
   - Plans far from entry should be checked less frequently (30s)

3. **Check Log Messages:**
   - Look for "Adaptive interval" messages in debug logs
   - Verify intervals match expected values based on price distance

---

## Monitoring Smart Caching

### What to Look For

**Info Log Messages:**
- `Smart caching: Invalidated M1 cache for {symbol} due to new candle close (candle time: ...)`
- `Smart caching: Pre-fetch thread started`

**Debug Log Messages:**
- `Smart caching: Pre-fetching M1 data for {symbol} ({time}s until expiry, cache age: ...)`

**Expected Behavior:**
- Cache invalidated immediately when new M1 candle closes
- Data pre-fetched 3 seconds before cache expiry
- Reduced MT5 API calls due to caching

### Verification Steps

1. **Check Cache Invalidation:**
   - Watch for "Invalidated M1 cache" messages every minute (when M1 candle closes)
   - Should happen automatically without manual cache clearing

2. **Monitor Pre-fetch Activity:**
   - Check debug logs for "Pre-fetching M1 data" messages
   - Should occur 3 seconds before cache expires (17s after cache creation)

3. **Verify Cache Usage:**
   - Monitor MT5 API call frequency
   - Should see fewer calls due to cache hits

---

## Monitoring Conditional Checks

### What to Look For

**Debug Log Messages:**
- `Conditional check: Skipping {plan_id} - price {price} is {distance} away from entry {entry} (threshold: {threshold}, tolerance: {tolerance})`

**Expected Behavior:**
- Plans with price > 2× tolerance away from entry are skipped
- Only plans within 2× tolerance are checked
- Reduces CPU usage for plans far from entry

### Verification Steps

1. **Check Skip Messages:**
   - Look for "Conditional check: Skipping" messages in debug logs
   - Verify plans far from entry are being skipped

2. **Monitor Check Frequency:**
   - Plans near entry should be checked normally
   - Plans far from entry should be skipped (no condition checks)

---

## Monitoring Batch Operations

### What to Look For

**Debug Log Messages:**
- `Batch price fetch: Retrieved prices for {count} symbols`

**Expected Behavior:**
- Prices fetched in batch for all active symbols
- Single batch call instead of individual calls per symbol
- Reduced MT5 API calls

### Verification Steps

1. **Check Batch Fetch Messages:**
   - Look for "Batch price fetch" messages in debug logs
   - Verify multiple symbols are fetched in one batch

2. **Monitor API Call Frequency:**
   - Should see fewer individual `symbol_info_tick()` calls
   - Batch fetching should reduce API load

---

## Using the Monitoring Script

Run the monitoring script to verify system status:

```bash
python monitor_optimized_intervals.py
```

**What It Checks:**
1. System status and config loading
2. M1 interval configuration
3. Config file structure
4. Live log monitoring (optional)

---

## Expected Log Patterns

### Normal Operation (Features Enabled)

```
[INFO] Smart caching: Pre-fetch thread started
[INFO] Optimized intervals system ENABLED:
[INFO]   - Adaptive intervals: ENABLED (M1 base: 10s)
[INFO]   - Smart caching: ENABLED
[INFO]   - Conditional checks: ENABLED
[INFO]   - Batch operations: ENABLED
[DEBUG] Batch price fetch: Retrieved prices for 3 symbols
[DEBUG] Adaptive interval for plan_123 (m1_micro_scalp): 10s (price: 90050.0, entry: 90000.0, distance: 50.0, tolerance: 50.0)
[DEBUG] Smart caching: Pre-fetching M1 data for BTCUSDc (2.1s until expiry, cache age: 17.9s)
[INFO] Smart caching: Invalidated M1 cache for BTCUSDc due to new candle close (candle time: 14:23:00 UTC)
```

### Normal Operation (Features Disabled)

```
[INFO] Optimized intervals system: DISABLED (enable via config file)
```

### Error Scenarios

```
[WARNING] Error fetching batch prices (non-fatal): ...
[DEBUG] Error calculating adaptive interval for plan_123: ...
[DEBUG] Error in adaptive interval check for plan_123: ...
```

---

## Troubleshooting

### Features Not Working

1. **Check Config File:**
   - Verify `config/auto_execution_optimized_intervals.json` exists
   - Check JSON syntax is valid
   - Verify `enabled: true` for desired features

2. **Check System Startup:**
   - Look for "Optimized intervals system ENABLED" message
   - If not present, config may not be loading correctly

3. **Check Log Level:**
   - Many messages are at DEBUG level
   - Ensure logging level is set to DEBUG to see all messages

### No Adaptive Interval Messages

- Verify adaptive intervals are enabled in config
- Check that plans are detected as `m1_micro_scalp` type
- Ensure plans have valid `tolerance` values
- Check debug log level is enabled

### No Cache Invalidation Messages

- Verify smart caching is enabled in config
- Check that `invalidate_on_candle_close` is `true`
- Ensure M1 data fetcher is available
- Monitor for new M1 candle closes (every minute)

### No Pre-fetch Messages

- Verify pre-fetch thread started (check startup logs)
- Check that cache TTL and pre-fetch timing are configured
- Ensure M1 data fetcher is available
- Pre-fetch messages are at DEBUG level

---

## Performance Metrics to Monitor

### CPU Usage
- Should decrease for plans far from entry (30s intervals vs 10s)
- Batch operations should reduce CPU spikes

### RAM Usage
- Tracking dicts should be minimal (< 1MB for 100 plans)
- Cache should be cleaned up automatically

### MT5 API Calls
- Should decrease due to:
  - Batch price fetching
  - Smart caching (20s TTL)
  - Conditional checks (skipping far plans)

### Check Frequency
- M1 plans near entry: ~5-10s intervals
- M1 plans far from entry: ~30s intervals
- Overall: Adaptive based on price proximity

---

## Success Criteria

✅ **System is working correctly if:**
1. Startup logs show "Optimized intervals system ENABLED"
2. Adaptive interval messages appear in debug logs
3. Cache invalidation happens on candle close
4. Pre-fetch messages appear before cache expiry
5. Conditional check skip messages appear for far plans
6. Batch price fetch messages show multiple symbols
7. M1 plans use 10s base interval when price is near entry

---

## Next Steps

1. **Enable Debug Logging:**
   - Set log level to DEBUG to see all messages
   - Monitor logs for adaptive interval and caching activity

2. **Monitor Performance:**
   - Track CPU/RAM usage over time
   - Monitor MT5 API call frequency
   - Verify intervals are working as expected

3. **Validate M1 Plans:**
   - Create test M1 micro-scalp plans
   - Verify they use 10s intervals when price is near entry
   - Monitor check frequency matches expected intervals
