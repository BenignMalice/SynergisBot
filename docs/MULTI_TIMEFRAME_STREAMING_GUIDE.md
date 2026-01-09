# Multi-Timeframe Candlestick Streaming Guide

**Last Updated:** November 1, 2025

## Overview

The `MultiTimeframeStreamer` efficiently streams MT5 candlestick data from multiple timeframes (M1, M5, M15, M30, H1, H4) with minimal RAM and SSD usage.

**⭐ NEW Features:**
- ✅ M1 timeframe support for ultra-fast price detection
- ✅ Integrated with Intelligent Exit and DTMS systems
- ✅ Pattern detection uses streaming data
- ✅ StreamerDataAccess helper for unified data access

## Key Features

✅ **Incremental Fetching** - Only fetches new candles (typically 1-5 per cycle)  
✅ **Rolling Buffers** - Fixed-size deques that auto-expire old data  
✅ **Smart Refresh Rates** - Different intervals for each timeframe  
✅ **Optional Persistence** - Database storage with automatic cleanup  
✅ **Memory Efficient** - ~50 KB per symbol for all timeframes  
✅ **Disk Safe** - Minimal writes, batch operations, automatic cleanup  

## Resource Usage

### Memory (RAM)
- **Per symbol**: ~50 KB for all timeframes combined
- **20 symbols**: ~1 MB total
- **100 symbols**: ~5 MB total

### Disk (if database enabled)
- **Per symbol per day**: ~100 KB
- **20 symbols, 30 days**: ~60 MB total

## Configuration

### Basic Usage (RAM Only - Safest)

```python
from infra.multi_timeframe_streamer import MultiTimeframeStreamer, StreamerConfig

config = StreamerConfig(
    symbols=['BTCUSDc', 'XAUUSDc'],
    enable_database=False  # RAM only - no SSD writes
)

streamer = MultiTimeframeStreamer(config)
await streamer.start()

# Access candles
latest = streamer.get_latest_candle('BTCUSDc', 'M5')
candles = streamer.get_candles('XAUUSDc', 'H1', limit=50)
```

### With Database Persistence

```python
config = StreamerConfig(
    symbols=['BTCUSDc', 'XAUUSDc', 'EURUSDc'],
    enable_database=True,
    db_path='data/multi_tf_candles.db',
    retention_days=30  # Auto-delete after 30 days
)
```

## Buffer Sizes

Recommended buffer sizes (bars to keep in memory):

| Timeframe | Buffer Size | Days Covered | Memory | Use Case |
|-----------|-------------|--------------|--------|----------|
| M1        | 1440        | ~1 day       | ~92 KB | Ultra-fast breakeven/partial profit detection ⭐ NEW |
| M5        | 300         | ~2.5 days    | ~19 KB | Primary scalping timeframe |
| M15       | 150         | ~2.5 days    | ~9 KB  | Entry timing precision |
| M30       | 100         | ~2.5 days    | ~6 KB  | Trend confirmation |
| H1        | 100         | ~4 days      | ~6 KB  | Bias identification |
| H4        | 50          | ~8 days      | ~3 KB  | Macro structure |

**Total per symbol**: ~135 KB (with M1)

**Note:** M1 buffer (1440 bars = 24 hours) enables ultra-fast detection within 2 minutes of entry.

## Refresh Intervals

Recommended refresh intervals (seconds):

| Timeframe | Interval | Reason |
|-----------|----------|--------|
| M1        | 60       | New bar every minute ⭐ NEW |
| M5        | 300      | New bar every 5 minutes |
| M15       | 900      | New bar every 15 minutes |
| M30       | 1800     | New bar every 30 minutes |
| H1        | 3600     | New bar every hour |
| H4        | 14400    | New bar every 4 hours |

**Why this matters**: Don't poll H4 every 5 seconds - waste of resources!

**M1 Benefits:**
- Ultra-fast breakeven detection (within 2 minutes)
- Immediate partial profit triggers
- Real-time momentum shifts for scalping

## Callbacks

Register callbacks to be notified when new candles arrive:

```python
def on_new_candle(candle: Candle):
    print(f"New {candle.timeframe} candle: {candle.symbol}")
    print(f"Close: {candle.close}, Volume: {candle.volume}")
    
    # Process candle (e.g., update indicators, check conditions)
    if candle.timeframe == 'M5':
        update_indicators(candle)

streamer.add_callback(on_new_candle)
```

## Accessing Data

### Get Latest Candle
```python
latest = streamer.get_latest_candle('BTCUSDc', 'M5')
if latest:
    print(f"Close: {latest.close}, Time: {latest.time}")
```

### Get Multiple Candles
```python
# Get last 50 H1 candles
candles = streamer.get_candles('XAUUSDc', 'H1', limit=50)

for candle in candles:
    print(f"{candle.time}: O={candle.open} H={candle.high} L={candle.low} C={candle.close}")
```

### Get All Candles in Buffer
```python
# Get all M15 candles (up to buffer size)
all_candles = streamer.get_candles('EURUSDc', 'M15')
```

## Monitoring

### Get Metrics
```python
metrics = streamer.get_metrics()
print(f"Memory: {metrics['memory_usage_mb']:.2f} MB")
print(f"Database: {metrics['db_size_mb']:.2f} MB")
print(f"Candles fetched: {metrics['total_candles_fetched']}")
print(f"Errors: {metrics['errors']}")
```

### Metrics Explained
- `memory_usage_mb`: Current RAM usage
- `db_size_mb`: Database file size (if enabled)
- `total_candles_fetched`: Total candles fetched since start
- `total_candles_stored`: Total candles written to database
- `errors`: Number of errors encountered
- `last_update`: Last metrics update timestamp

## Safety Features

### Memory Limits
- Automatically monitors memory usage
- Warns if approaching `max_memory_mb` limit
- Rolling buffers prevent unlimited growth

### Database Limits
- Monitors database size
- Warns if approaching `max_db_size_mb` limit
- Automatic cleanup of old data

### Error Handling
- Continues streaming if individual fetches fail
- Retries on errors
- Tracks error count for monitoring

## Integration Examples

### Basic Usage

```python
from infra.multi_timeframe_streamer import MultiTimeframeStreamer, StreamerConfig
from infra.mt5_service import MT5Service

# Initialize MT5 service
mt5_service = MT5Service()

# Configure streamer
config = StreamerConfig(
    symbols=['BTCUSDc', 'XAUUSDc'],
    enable_database=False  # RAM only for safety
)

# Create streamer
streamer = MultiTimeframeStreamer(config, mt5_service=mt5_service)

# Add callback for real-time processing
def process_candle(candle: Candle):
    if candle.timeframe == 'M5':
        # Update M5 indicators
        update_m5_indicators(candle)
    elif candle.timeframe == 'H1':
        # Update H1 structure analysis
        update_h1_structure(candle)

streamer.add_callback(process_candle)

# Start streaming
await streamer.start()

# Your application code here
# ...

# When shutting down
await streamer.stop()
```

### Using StreamerDataAccess (Unified Access) ⭐ NEW

```python
from infra.streamer_data_access import StreamerDataAccess, set_streamer

# Register the streamer instance
set_streamer(streamer)

# Create data access helper
data_access = StreamerDataAccess()

# Get candles (automatically uses streamer, falls back to MT5)
candles = data_access.get_candles('BTCUSDc', 'M5', limit=50)

# Get latest candle with freshness check
latest = data_access.get_latest_candle('XAUUSDc', 'M1', max_age_seconds=120)

# Calculate ATR (uses streamer data if available)
atr = data_access.calculate_atr('BTCUSDc', 'M15', period=14)

# Detect structure breaks
break_detected = data_access.detect_structure_break('XAUUSDc', 'M5', lookback_bars=20)
```

### Integration with Intelligent Exit System

```python
# Intelligent Exit Manager automatically uses streamer data via StreamerDataAccess
from infra.intelligent_exit_manager import IntelligentExitManager

# The system will:
# 1. Fetch M1 candles for fast breakeven detection (within 2 minutes)
# 2. Use M1 + M30 ATR for hybrid stop adjustments
# 3. Fall back to direct MT5 if streamer unavailable
# 4. All handled automatically via StreamerDataAccess
```

### Integration with DTMS System

```python
# Position Watcher automatically uses streamer data via StreamerDataAccess
from infra.position_watcher import PositionWatcher

# The system will:
# 1. Fetch candlestick DataFrames from streamer (faster than MT5)
# 2. Calculate ATR using streamer data
# 3. Fall back to MT5 if streamer unavailable
# 4. Provides faster position monitoring with less MT5 API load
```

### Pattern Detection Integration

```python
# Pattern detection automatically uses streamer data
from infra.feature_builder_advanced import build_features_advanced

# When building advanced features, patterns are computed from streamer data:
features = build_features_advanced(
    symbol='BTCUSDc',
    mt5svc=mt5_service,
    bridge=indicator_bridge,
    timeframes=['M5', 'M15', 'H1']
)

# Patterns are now included:
# - features['features']['M5']['candlestick_flags']  # Single-bar patterns
# - features['features']['M5']['pattern_flags']      # Multi-bar patterns
# - features['features']['M5']['wick_metrics']        # Wick analysis
# - features['features']['M5']['pattern_strength']     # Strength score
```

## Best Practices

### 1. Start Small
- Begin with 1-3 symbols
- Monitor memory usage
- Scale up gradually

### 2. RAM vs Database
- **RAM only**: Best for real-time analysis, no historical access needed
- **Database**: Needed for backtesting, historical analysis, or restarts

### 3. Buffer Sizes
- Adjust based on your needs
- Larger buffers = more memory but more history
- Defaults are optimized for 2-4 days of data

### 4. Refresh Intervals
- Don't make them too frequent (wastes CPU/MT5 API)
- Don't make them too slow (miss updates)
- Defaults match timeframe frequencies

### 5. Monitoring
- Check metrics regularly
- Set up alerts if memory/disk usage spikes
- Review error logs

## Troubleshooting

### High Memory Usage
- Reduce buffer sizes in config
- Reduce number of symbols
- Check for memory leaks in callbacks

### High Disk Usage
- Reduce retention_days
- Disable database (RAM only mode)
- Run cleanup manually

### Missing Candles
- Check MT5 connection
- Verify symbol names are correct
- Check error logs for fetch failures

### Slow Performance
- Reduce number of symbols/timeframes
- Increase refresh intervals
- Check MT5 API rate limits

## Performance Tips

1. **Use RAM-only mode** if you don't need historical data
2. **Reduce buffer sizes** if memory is tight
3. **Disable unused timeframes** to save resources
4. **Batch process callbacks** instead of processing each candle immediately
5. **Use async/await** properly in callbacks to avoid blocking

## API Endpoints

The streamer is automatically exposed via FastAPI in `app/main_api.py`:

### Get Candles
```
GET /api/v1/candles/{symbol}/{timeframe}?limit=50
```
Returns candlestick data from streamer buffers.

### Get Latest Candle
```
GET /api/v1/candles/{symbol}/{timeframe}/latest
```
Returns the most recent candle for the symbol/timeframe.

### Get Streamer Status
```
GET /api/v1/streamer/status
```
Returns streamer metrics, configuration, and health status.

**Examples:**
- `GET /api/v1/candles/BTCUSDc/M1/latest` - Latest M1 candle
- `GET /api/v1/candles/XAUUSDc/M5?limit=100` - Last 100 M5 candles
- `GET /api/v1/streamer/status` - Streamer health check

## System Integration

### Intelligent Exit System
- ✅ Uses M1 data for ultra-fast breakeven detection (within 2 minutes)
- ✅ Uses M1 + M30 ATR for hybrid stop adjustments
- ✅ Automatic fallback to MT5 if streamer unavailable
- ✅ All via `StreamerDataAccess` helper

### DTMS System
- ✅ Uses streamer for faster DataFrame fetching
- ✅ Reduces MT5 API load
- ✅ Automatic fallback to MT5 if streamer unavailable

### Pattern Detection
- ✅ Advanced features builder uses streamer data automatically
- ✅ Patterns computed from M5, M15, H1 streaming data
- ✅ Includes 17 pattern types (Marubozu, Engulfing, Morning Star, etc.)
- ✅ Pattern strength and wick metrics included

### ChatGPT Analysis
- ✅ `moneybot.getAdvancedFeatures` includes pattern detection from streamer
- ✅ `moneybot.analyse_symbol_full` benefits from faster data access
- ✅ Multi-timeframe patterns available for scalping strategies

## Expected Performance

With default settings (6 timeframes including M1, 10 symbols):

- **Memory**: ~1.4 MB (includes M1 buffers)
- **CPU**: <1% (background streaming)
- **Disk I/O**: Minimal (if database enabled, ~200 writes/hour with batching)
- **MT5 API calls**: ~60 calls/hour (distributed across timeframes)

**M1 Impact:**
- **Memory**: +~920 KB per symbol (M1 buffer)
- **CPU**: +<0.1% (negligible)
- **Refresh**: Every 60 seconds (ultra-fast)

This is still very resource-efficient, with M1 providing ultra-fast detection capabilities!

