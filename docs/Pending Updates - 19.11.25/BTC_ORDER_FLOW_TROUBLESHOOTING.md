# BTC Order Flow Metrics Integration - Troubleshooting Guide

## Issue: Metrics Not Appearing in Analysis

If BTC order flow metrics are not appearing in `moneybot.analyse_symbol_full` analysis for BTCUSD, check the following:

### 1. Verify Order Flow Service Status

The metrics require the Order Flow Service to be initialized and collecting data:

```python
# Check service status
moneybot.order_flow_status(symbol: "BTCUSDc")
```

**Expected:** Service should be running and have data for BTCUSDT

### 2. Check Analysis Logs

When running `moneybot.analyse_symbol_full` for BTCUSD, look for these log messages:

```
[2.1/4] Fetching BTC order flow metrics...
✅ BTC order flow metrics retrieved: Delta=+X.XX, CVD=+X.XX, Status=success
```

**If you see:**
- `⚠️ BTC order flow metrics unavailable` → Service may not be running or data insufficient
- `⚠️ BTC order flow metrics error` → Check exception details in logs
- No log messages → Code may not be executing (check symbol normalization)

### 3. Verify Symbol Normalization

The code checks for `symbol_normalized == 'BTCUSDc'`. Verify:
- Input symbol: `BTCUSD` or `BTCUSDc`
- Normalized symbol should be: `BTCUSDc`
- Check logs for: `Normalized BTCUSD → BTCUSDc`

### 4. Test Tool Directly

Test the tool directly to verify it works:

```python
moneybot.btc_order_flow_metrics(symbol: "BTCUSDT", window_seconds: 30)
```

**Expected:** Should return metrics with `status: "success"`

### 5. Check Data Structure

The formatting function expects:
```python
{
    "status": "success",
    "delta_volume": {...},
    "cvd": {...},
    ...
}
```

If the structure is different, the formatting will fail silently.

### 6. Common Issues

**Issue:** Metrics fetched but not displayed
- **Cause:** Formatting function condition failing
- **Fix:** Check logs for `_format_btc_order_flow_metrics: status is...` messages

**Issue:** No metrics fetch attempted
- **Cause:** Symbol normalization issue or code not executing
- **Fix:** Verify `symbol_normalized == 'BTCUSDc'` in logs

**Issue:** Service not initialized
- **Cause:** Order Flow Service not started
- **Fix:** Ensure `chatgpt_bot.py` or main API has started the service

### 7. Expected Output

When working correctly, the analysis should include:

```
💧 LIQUIDITY & ORDER FLOW
[existing order flow data]

📊 BTC ORDER FLOW METRICS (Binance Real-Time):
💰 Delta Volume: -3.36 BTC (SELL) | Buy: 0.34 BTC | Sell: 2.09 BTC
📉 CVD: -4.85 (Slope: -2.52/bar, 10 bars)
⚖️ Buy/Sell Pressure: 0.62x (SELL)
```

### 8. Debug Steps

1. Check if analysis was generated after code fix
2. Verify Order Flow Service is running: `moneybot.order_flow_status`
3. Test tool directly: `moneybot.btc_order_flow_metrics`
4. Check analysis logs for fetch attempts
5. Verify symbol normalization in logs
6. Check formatting function logs for status issues

### 9. Code Flow

1. `tool_analyse_symbol_full` called with `symbol: "BTCUSD"`
2. Symbol normalized to `BTCUSDc`
3. Code checks `if symbol_normalized == 'BTCUSDc'`
4. Calls `tool_btc_order_flow_metrics({"symbol": "BTCUSDT"})`
5. Extracts `btc_metrics_result.get("data", {})`
6. Passes to `_format_unified_analysis(..., btc_order_flow_metrics=...)`
7. `_format_btc_order_flow_metrics()` formats the data
8. Included in summary string at line 1070

### 10. If Still Not Working

Check:
- Analysis timestamp vs code fix timestamp
- Service restart required after code changes
- Logs for any error messages
- Data structure matches expected format

