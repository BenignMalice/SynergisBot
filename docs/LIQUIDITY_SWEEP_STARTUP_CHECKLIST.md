# Liquidity Sweep Reversal Engine - Startup Checklist

## ✅ What to Look For When System Starts

### 1. Initialization Messages (Both Main API & Desktop Agent)

When the system starts, you should see these log messages in sequence:

```
🔍 Initializing Liquidity Sweep Reversal Engine...
   → Intelligent Exit Manager available for post-entry management
   → Discord notifications enabled
✅ Liquidity Sweep Reversal Engine started
   → Monitoring BTCUSD and XAUUSD for liquidity sweeps
   → Three-layer confluence stack (Macro → Setup → Trigger)
   → Automatic reversal trade execution when confluence ≥70%
Starting Liquidity Sweep Reversal Engine
LiquiditySweepReversalEngine initialized for symbols: ['BTCUSDc', 'XAUUSDc']
State loaded from file  # (if state file exists)
```

### 2. Expected Log Messages

#### ✅ Success Indicators:
- **"✅ Liquidity Sweep Reversal Engine started"** - Engine is running
- **"LiquiditySweepReversalEngine initialized for symbols: ['BTCUSDc', 'XAUUSDc']"** - Config loaded correctly
- **"State loaded from file"** - Previous setups restored (if any)
- **"Starting Liquidity Sweep Reversal Engine"** - Background task launched

#### ⚠️ Warning Indicators (Non-Critical):
- **"Config file not found: config/liquidity_sweep_config.json, using defaults"** - Will use default settings (still functional)
- **"Discord notifications not available"** - Engine works without Discord, but no alerts
- **"Intelligent Exit Manager not available"** - Engine works, but no auto-exit management

#### ❌ Error Indicators (Critical):
- **"⚠️ Liquidity Sweep Reversal Engine initialization failed"** - Engine did not start
- **"Failed to load state"** - State persistence issue (non-critical, will continue)
- **"VIX data not available"** - Macro context checks may fail (will skip trades)

### 3. Continuous Operation Messages

Once running, you'll see periodic messages:

#### Macro Context Checks (Every 15 minutes):
```
VIX too high (25.5), avoiding all reversals  # If VIX > 25
Outside active trading session (current hour: 3)  # If outside London/NY hours
```

#### Sweep Detection:
```
🔄 Liquidity sweep detected: BTCUSDc (bull sweep at 95234.50)
   → Setup score: 85.0%
   → Waiting for trigger confirmation...
```

#### Trade Execution:
```
✅ Type 1 reversal trade executed: BTCUSDc
   → Entry: 95120.00 | SL: 95250.00 | TP: 94890.00
   → Confluence: 72.5% (Macro: 80%, Setup: 75%, Trigger: 65%)
   → Registered with Intelligent Exit Manager
```

#### Discord Notifications:
- **Sweep Detected** alerts (if configured)
- **Trade Executed** notifications
- **Setup Invalidated** warnings

### 4. Startup Verification Steps

#### Step 1: Check Logs for Initialization
```powershell
# For Main API
Get-Content desktop_agent.log -Tail 50 | Select-String "Liquidity Sweep"

# For Desktop Agent
Get-Content desktop_agent.log -Tail 50 | Select-String "Liquidity Sweep"
```

#### Step 2: Verify Configuration File
```powershell
# Check if config exists
Test-Path config/liquidity_sweep_config.json

# View config
Get-Content config/liquidity_sweep_config.json | ConvertFrom-Json
```

#### Step 3: Check State File (Optional)
```powershell
# Check if state file exists (may not exist on first run)
Test-Path data/liquidity_sweep_state.json
```

#### Step 4: Verify Engine Status via API (Main API only)
```powershell
# Check if engine is running (if API endpoint exists)
Invoke-RestMethod http://localhost:8010/api/v1/streamer/status
```

### 5. Common Issues & Solutions

#### Issue: "⚠️ Liquidity Sweep Reversal Engine initialization failed"
**Possible Causes:**
- MT5 not connected
- Missing dependencies (`pandas`, `numpy`)
- Invalid config file JSON
- Import errors

**Solution:**
1. Check MT5 connection status
2. Verify all dependencies: `pip install pandas numpy`
3. Validate JSON: `python -c "import json; json.load(open('config/liquidity_sweep_config.json'))"`
4. Check Python imports: `python -c "from infra.liquidity_sweep_reversal_engine import LiquiditySweepReversalEngine"`

#### Issue: "State loaded from file" but no active setups
**Explanation:** This is normal - the state file may exist but be empty or have no active setups.

#### Issue: No Discord notifications
**Possible Causes:**
- `DISCORD_WEBHOOK_URL` not set in `.env`
- Discord webhook invalid/expired
- Notifications disabled in config

**Solution:**
1. Verify `.env` has `DISCORD_WEBHOOK_URL`
2. Test webhook: `python -c "from discord_notifications import DiscordNotifier; n = DiscordNotifier(); n.send_message('Test', message_type='INFO')"`

#### Issue: "VIX data not available"
**Possible Causes:**
- Market Indices Service not initialized
- Network issues
- API rate limiting

**Impact:** Macro context checks will return "avoid" - no trades will execute until VIX data is available.

### 6. Normal Operation Indicators

Once started successfully, the engine:
- ✅ Runs silently in the background
- ✅ Monitors M1 candles every 60 seconds (or as configured)
- ✅ Only logs when events occur (sweeps detected, trades executed)
- ✅ Respects session hours (London 7-10 UTC, NY 12-16 UTC)
- ✅ Skips trades if VIX > 25
- ✅ Checks confluence score before executing (must be ≥70%)

### 7. Monitoring Active Status

#### Check if Engine is Running:
- Look for **"Starting Liquidity Sweep Reversal Engine"** in logs
- Check if state file is being updated (modification time)
- Monitor Discord for sweep/trade notifications (if enabled)

#### Verify Background Task:
The engine runs as an `asyncio.create_task`, so it won't block the main thread. You should see it in the task list if using process monitoring.

### 8. First Run Expectations

On the **first run**, expect:
1. ✅ Config loaded (or default config used)
2. ✅ State file created at `data/liquidity_sweep_state.json` (empty initially)
3. ✅ No previous setups restored
4. ✅ Engine waits for valid trading session before monitoring
5. ✅ First sweep detection may take 5-60 minutes (depends on market conditions)

### 9. Testing Engine Status

You can verify the engine is working by:
1. **Check logs periodically** for sweep detection messages
2. **Monitor Discord** (if enabled) for notifications
3. **Check state file** for active setups: `Get-Content data/liquidity_sweep_state.json`
4. **Look for trade tickets** in MT5 terminal (if trades execute)

---

## Quick Reference: Startup Sequence

```
1. 🔍 Initializing Liquidity Sweep Reversal Engine...
2. → Intelligent Exit Manager available (or not available)
3. → Discord notifications enabled (or not available)
4. ✅ Liquidity Sweep Reversal Engine started
5. → Monitoring BTCUSD and XAUUSD for liquidity sweeps
6. → Three-layer confluence stack (Macro → Setup → Trigger)
7. → Automatic reversal trade execution when confluence ≥70%
8. Starting Liquidity Sweep Reversal Engine
9. LiquiditySweepReversalEngine initialized for symbols: ['BTCUSDc', 'XAUUSDc']
10. State loaded from file (if exists)
```

**If all 10 steps appear, the engine is running successfully!** 🎉

