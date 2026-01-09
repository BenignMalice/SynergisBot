# How to Run the Micro-Scalp System

## Quick Start

### 1. **Enable the System in Configuration**

Edit `config/micro_scalp_automation.json` and set `"enabled": true`:

```json
{
  "enabled": true,
  "symbols": ["BTCUSDc", "XAUUSDc"],
  "check_interval_seconds": 5,
  ...
}
```

### 2. **Start the Main API Server**

The micro-scalp system is automatically initialized when the main API server starts.

**Option A: Using the batch file (Windows)**
```bash
start_all_services.bat
```

**Option B: Manual start (Windows PowerShell)**
```powershell
cd "C:\Coding\MoneyBotv2.7 - 10 Nov 25"
python -m uvicorn app.main_api:app --host 0.0.0.0 --port 8000 --reload
```

**Option C: Direct Python execution**
```powershell
cd "C:\Coding\MoneyBotv2.7 - 10 Nov 25"
python app/main_api.py
```

### 3. **Verify the System is Running**

Check the startup logs. You should see:
```
✅ Micro-Scalp Monitor started
   → Continuous monitoring for micro-scalp setups
   → Independent from ChatGPT and auto-execution plans
   → Immediate execution when conditions are met
```

---

## Configuration Files

### **Main Configuration: `config/micro_scalp_automation.json`**

Controls whether the system is enabled and basic settings:

```json
{
  "enabled": true,                    // Set to true to enable
  "symbols": ["BTCUSDc", "XAUUSDc"], // Symbols to monitor
  "check_interval_seconds": 5,       // How often to check (seconds)
  "min_execution_interval_seconds": 60,  // Minimum time between trades
  "max_positions_per_symbol": 1,     // Max positions per symbol
  "risk_per_trade": 0.5,             // Risk percentage per trade
  "session_filters": {
    "enabled": false,                // Set to false to trade in any session
    "preferred_sessions": ["london", "ny", "overlap"],
    "disable_during_news": true
  },
  "rate_limiting": {
    "max_trades_per_hour": 10,
    "max_trades_per_day": 50
  },
  "position_limits": {
    "max_total_positions": 3,
    "max_per_symbol": 1
  },
  "execution_validation": {
    "max_spread_percent": 0.15,       // Max spread (15% for BTC, 0.15% for XAU)
    "check_tick_alignment": true,
    "use_spread_tracker": true
  },
  "news_blackout": {
    "enabled": true,
    "categories": ["macro", "crypto"]
  }
}
```

### **Strategy Configuration: `config/micro_scalp_config.json`**

Controls the adaptive micro-scalp strategy system (regime detection, thresholds, etc.)

---

## System Status and Monitoring

### **Check Status via API**

```bash
# Get system status
curl http://localhost:8000/micro-scalp/status

# View dashboard in browser
http://localhost:8000/micro-scalp/view
```

### **Check Status in Logs**

The system logs its activity. Look for:
- `Micro-Scalp Monitor heartbeat:` - Periodic status updates
- `Micro-Scalp conditions met for` - When conditions are detected
- `Micro-Scalp trade executed` - When trades are executed

---

## System Components

The micro-scalp system consists of:

1. **MicroScalpEngine** - Core engine that checks conditions
2. **MicroScalpMonitor** - Background monitor that continuously checks symbols
3. **MicroScalpExecutionManager** - Handles trade execution
4. **Adaptive Strategy System** - Regime detection and strategy routing
   - VWAP Reversion strategy
   - Range Scalp strategy
   - Balanced Zone strategy
   - Edge-Based fallback

---

## Dependencies

The system requires:

- ✅ **MT5 Service** - Must be connected
- ✅ **M1 Data Fetcher** - For M1 candle data
- ✅ **M1 Microstructure Analyzer** - For structure analysis
- ✅ **Multi-Timeframe Streamer** - For M5/M15 data
- ✅ **Session Manager** - For session filtering (optional)
- ✅ **News Service** - For news blackout (optional)
- ✅ **Spread Tracker** - For spread validation

All dependencies are automatically initialized when the main API starts.

---

## Troubleshooting

### **System Not Starting**

1. **Check if enabled in config:**
   ```json
   "enabled": true
   ```

2. **Check startup logs for errors:**
   - Look for `⚠️ Micro-Scalp Monitor initialization failed`
   - Check if all dependencies are initialized

3. **Verify MT5 is connected:**
   - Should see `MT5 connected successfully` in logs

### **System Not Executing Trades**

1. **Check if conditions are being met:**
   - View dashboard: `http://localhost:8000/micro-scalp/view`
   - Check logs for `Micro-Scalp conditions met`

2. **Check rate limiting:**
   - `max_trades_per_hour` and `max_trades_per_day` may be limiting

3. **Check position limits:**
   - `max_positions_per_symbol` and `max_total_positions` may be reached

4. **Check spread validation:**
   - Spread may be too wide (check `max_spread_percent`)

5. **Check session filters:**
   - If `session_filters.enabled: true`, ensure you're in a preferred session

6. **Check news blackout:**
   - If `news_blackout.enabled: true`, system won't trade during news events

### **System Disabled in Logs**

If you see:
```
⏸️ Micro-Scalp Monitor disabled in config
```

Set `"enabled": true` in `config/micro_scalp_automation.json` and restart the API server.

---

## Manual Testing

### **Test Condition Checking**

You can manually trigger a condition check via API:

```bash
# Check conditions for a symbol
curl -X POST http://localhost:8000/micro-scalp/check \
  -H "Content-Type: application/json" \
  -d '{"symbol": "XAUUSDc"}'
```

### **View Check History**

```bash
# Get detailed history
curl http://localhost:8000/micro-scalp/history?symbol=XAUUSDc&limit=20
```

---

## Stopping the System

### **Stop the API Server**

**Option A: Using batch file**
```bash
stop_all_services.bat
```

**Option B: Manual stop**
- Press `Ctrl+C` in the terminal running the API
- The system will automatically stop the monitor on shutdown

---

## Advanced Configuration

### **Adjust Check Interval**

In `config/micro_scalp_automation.json`:
```json
"check_interval_seconds": 5  // Check every 5 seconds (default)
```

Lower values = more frequent checks (higher CPU usage)
Higher values = less frequent checks (lower CPU usage)

### **Adjust Risk Per Trade**

```json
"risk_per_trade": 0.5  // Risk 0.5% per trade
```

### **Disable Session Filtering**

To trade in any session:
```json
"session_filters": {
  "enabled": false
}
```

### **Disable News Blackout**

```json
"news_blackout": {
  "enabled": false
}
```

---

## System Architecture

```
Main API Server (app/main_api.py)
    │
    ├── Startup Event
    │   ├── Initialize MT5 Service
    │   ├── Initialize M1 Data Fetcher
    │   ├── Initialize M1 Analyzer
    │   ├── Initialize Multi-Timeframe Streamer
    │   ├── Initialize MicroScalpEngine
    │   ├── Initialize MicroScalpExecutionManager
    │   └── Initialize MicroScalpMonitor
    │
    └── MicroScalpMonitor (Background Thread)
        ├── Check conditions every N seconds
        ├── Use MicroScalpEngine to validate
        └── Use MicroScalpExecutionManager to execute
```

---

## Next Steps

1. ✅ Enable the system in `config/micro_scalp_automation.json`
2. ✅ Start the main API server
3. ✅ Monitor the dashboard: `http://localhost:8000/micro-scalp/view`
4. ✅ Check logs for activity
5. ✅ Adjust configuration as needed

---

**Last Updated:** 2025-12-04

