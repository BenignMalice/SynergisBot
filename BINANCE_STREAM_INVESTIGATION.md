# Binance Stream Investigation Report

**Date:** 2026-01-04  
**Issue:** Order flow service streams start but `trade_history` remains empty

---

## Problem Summary

- ✅ Order flow service is initialized and running
- ✅ Streams are started (`"Starting aggTrades streams"`)
- ❌ No connection logs (`"Connected to BTCUSDT aggTrades stream"` missing)
- ❌ `trade_history` is empty (`Available symbols: []`)
- ❌ Order flow metrics unavailable for all plans

---

## Root Cause Analysis

### Expected Flow

1. **Service Initialization** (`order_flow_service.py:52-78`)
   ```python
   await self.trades_stream.start(symbols, background=True)
   ```

2. **Stream Start** (`binance_aggtrades_stream.py:108-125`)
   ```python
   self.tasks = [asyncio.create_task(self.connect(sym)) for sym in symbols]
   ```

3. **Connection** (`binance_aggtrades_stream.py:48-87`)
   ```python
   async with websockets.connect(uri) as ws:
       logger.info(f"🐋 Connected to {symbol.upper()} aggTrades stream")
       async for message in ws:
           await self.callback(symbol.upper(), trade)
   ```

4. **Callback Chain** (`order_flow_service.py:48-50`)
   ```python
   async def _on_trade_update(self, symbol: str, trade: Dict):
       self.analyzer.update_trade(symbol, trade)
   ```

5. **Whale Detector Update** (`order_flow_analyzer.py:41-43`)
   ```python
   def update_trade(self, symbol: str, trade: Dict):
       self.whale_detector.update(symbol, trade)
   ```

6. **Trade History** (`binance_aggtrades_stream.py:170-180`)
   ```python
   def update(self, symbol: str, trade: Dict):
       if symbol not in self.trade_history:
           self.trade_history[symbol] = deque()
       self.trade_history[symbol].append(trade)
   ```

### What's Actually Happening

**Logs show:**
```
2026-01-04 07:41:13,043 - infra.binance_aggtrades_stream - INFO - 🚀 Starting aggTrades streams for 1 symbols
2026-01-04 07:41:13,044 - infra.binance_aggtrades_stream - INFO - ✅ AggTrades streams running in background
```

**Missing logs:**
- ❌ `"🐋 Connected to BTCUSDT aggTrades stream"` (line 58)
- ❌ Any whale order detections
- ❌ Any connection errors or retries

**This indicates:**
1. Tasks are created but may not be executing
2. WebSocket connection may be failing silently
3. Exceptions may be swallowed without logging

---

## Potential Issues

### Issue 1: Async Task Not Running

**Problem:** When `background=True`, tasks are created but not awaited. If the event loop isn't running or tasks fail immediately, they may not execute.

**Evidence:**
- No connection logs
- No error logs
- Tasks created but silent

**Code Location:**
```120:125:infra/binance_aggtrades_stream.py
self.tasks = [asyncio.create_task(self.connect(sym)) for sym in symbols]

if not background:
    await asyncio.gather(*self.tasks)
else:
    logger.info(f"✅ AggTrades streams running in background")
```

**Fix Needed:** Ensure tasks are properly scheduled and exceptions are logged.

### Issue 2: WebSocket Connection Failure

**Problem:** WebSocket connection may be failing due to:
- Network/firewall blocking
- Binance API changes
- SSL/TLS issues
- Invalid URI format

**Evidence:**
- No connection success logs
- No connection error logs (should log on line 102)

**Code Location:**
```48:107:infra/binance_aggtrades_stream.py
async def connect(self, symbol: str):
    uri = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@aggTrade"
    # ... connection code ...
```

**Fix Needed:** Add better error handling and logging.

### Issue 3: Exception Swallowing

**Problem:** Exceptions in async tasks may not be logged if not properly handled.

**Evidence:**
- No error logs despite likely failures
- Tasks may be failing silently

**Fix Needed:** Add exception handlers to tasks.

---

## Diagnostic Steps

### Step 1: Check Task Status

```python
# Check if tasks are running
from desktop_agent import registry
service = registry.order_flow_service
trades_stream = service.trades_stream
tasks = trades_stream.tasks

for task in tasks:
    print(f"Task: {task.done()=}, {task.cancelled()=}, {task.exception()=}")
```

### Step 2: Test Direct WebSocket Connection

```python
import asyncio
import websockets
import json

async def test():
    uri = "wss://stream.binance.com:9443/ws/btcusdt@aggTrade"
    async with websockets.connect(uri) as ws:
        print("Connected!")
        async for message in ws:
            data = json.loads(message)
            print(f"Trade: {data}")
            break

asyncio.run(test())
```

### Step 3: Check Event Loop

```python
# Verify event loop is running
import asyncio
print(f"Event loop: {asyncio.get_event_loop().is_running()}")
```

### Step 4: Check Trade History

```python
from desktop_agent import registry
service = registry.order_flow_service
whale_detector = service.analyzer.whale_detector
print(f"Trade history: {whale_detector.trade_history}")
```

---

## Recommended Fixes

### Fix 1: Add Task Exception Logging

**File:** `infra/binance_aggtrades_stream.py`

```python
async def start(self, symbols: list, background: bool = True):
    self.running = True
    
    logger.info(f"🚀 Starting aggTrades streams for {len(symbols)} symbols")
    
    self.tasks = []
    for sym in symbols:
        task = asyncio.create_task(self.connect(sym))
        # Add exception handler
        task.add_done_callback(lambda t: logger.error(f"Task failed: {t.exception()}") if t.exception() else None)
        self.tasks.append(task)
    
    if not background:
        await asyncio.gather(*self.tasks)
    else:
        logger.info(f"✅ AggTrades streams running in background")
```

### Fix 2: Add Connection Logging

**File:** `infra/binance_aggtrades_stream.py`

```python
async def connect(self, symbol: str):
    uri = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@aggTrade"
    
    logger.info(f"🔌 Attempting to connect to {symbol.upper()} aggTrades stream...")
    logger.debug(f"   URI: {uri}")
    
    retry_count = 0
    max_retries = 3
    
    while self.running and retry_count < max_retries:
        try:
            logger.debug(f"   Connecting (attempt {retry_count + 1}/{max_retries})...")
            async with websockets.connect(uri) as ws:
                logger.info(f"🐋 Connected to {symbol.upper()} aggTrades stream")
                retry_count = 0
                
                # ... rest of code ...
```

### Fix 3: Add Initial Connection Test

**File:** `infra/order_flow_service.py`

```python
async def start(self, symbols: List[str], background: bool = True):
    # ... existing code ...
    
    # Start trades stream
    await self.trades_stream.start(symbols, background=True)
    
    # Wait a moment and verify connection
    await asyncio.sleep(2)
    
    # Check if tasks are running
    if hasattr(self.trades_stream, 'tasks'):
        running_tasks = [t for t in self.trades_stream.tasks if not t.done()]
        if not running_tasks:
            logger.warning("⚠️ No active aggTrades stream tasks - connection may have failed")
        else:
            logger.info(f"✅ {len(running_tasks)} aggTrades stream task(s) running")
    
    logger.info("✅ Order flow service started")
```

---

## Immediate Actions

1. **Check Task Status:**
   - Verify tasks are actually running
   - Check for exceptions in tasks

2. **Test WebSocket Connection:**
   - Verify direct connection to Binance works
   - Check network/firewall settings

3. **Add Logging:**
   - Add connection attempt logs
   - Add exception logging in tasks
   - Add trade reception logs

4. **Monitor:**
   - Watch logs for connection messages
   - Check trade_history after 1-2 minutes
   - Verify whale detections appear

---

## Expected Behavior After Fix

Once fixed, logs should show:

```
🚀 Starting aggTrades streams for 1 symbols
🔌 Attempting to connect to BTCUSDT aggTrades stream...
🐋 Connected to BTCUSDT aggTrades stream
[Trade data starts flowing]
🐋 MEDIUM order detected: BTCUSDT BUY $125,000 @ 91,350.00
```

And `trade_history` should populate:
```python
whale_detector.trade_history = {
    'BTCUSDT': deque([...trades...])
}
```

---

## Code References

- **Stream Start:** `infra/binance_aggtrades_stream.py:108-125`
- **Connection:** `infra/binance_aggtrades_stream.py:48-107`
- **Callback:** `infra/order_flow_service.py:48-50`
- **Whale Detector:** `infra/binance_aggtrades_stream.py:170-180`
- **Metrics Check:** `infra/btc_order_flow_metrics.py:266-269`

---

**Report Generated:** 2026-01-04 08:20:00

