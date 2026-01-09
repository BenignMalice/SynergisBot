# Discord Trading Alert System - Implementation Plan

## Overview

A lightweight alert dispatcher that monitors existing indicator calculations and sends structured alerts to Discord. You copy-paste the alert into ChatGPT, which analyzes and creates an auto-execution plan if warranted.

### Workflow

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  System detects  │ →  │  Discord alert   │ →  │  You copy-paste  │ →  │  ChatGPT creates │
│  alert condition │    │  sent to you     │    │  into ChatGPT    │    │  auto-exec plan  │
└──────────────────┘    └──────────────────┘    └──────────────────┘    └──────────────────┘
     (automatic)            (automatic)            (manual)               (automatic)
```

**Your role**: Review Discord alerts → Copy interesting ones to ChatGPT → ChatGPT does full analysis and creates plan if trade is valid.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXISTING INFRASTRUCTURE                       │
├─────────────────────────────────────────────────────────────────┤
│  multi_timeframe_streamer.py  →  M1/M5/M15/H1/H4 candles       │
│  m1_microstructure_analyzer.py → CHOCH, BOS, OB, Sweeps, VWAP  │
│  discord_notifications.py      →  Webhook sender                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    NEW: ALERT DISPATCHER                         │
│                 infra/discord_alert_dispatcher.py                │
├─────────────────────────────────────────────────────────────────┤
│  • Reads candles from multi_timeframe_streamer                  │
│  • Runs detection logic on M5/M15/H1 data                       │
│  • Applies throttling/deduplication                             │
│  • Formats alerts for ChatGPT copy-paste                        │
│  • Sends to Discord via existing webhook                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Alert Categories & Monitoring Frequency

### Monitoring Strategy: Multi-Timeframe Detection

**Approach**: Use `multi_timeframe_streamer.py` directly to get candles for each detection timeframe. The streamer already caches M1/M5/M15/H1/H4 data - we just read from it and run detection logic.

**Why this approach?**
- Streamer already fetches and caches all timeframe data
- No aggregation logic needed (M1→M5 conversion)
- Minimal CPU/RAM impact - just reading existing cached data
- Detection runs on correct timeframe data (M5 CHOCH uses real M5 candles, not aggregated M1)

### Detection Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALERT MONITORING LOOP                         │
│                    (runs every 60 seconds)                       │
├─────────────────────────────────────────────────────────────────┤
│  For each symbol in watchlist:                                  │
│    1. Get M5 candles from streamer → run CHOCH/BOS/Sweep detect │
│    2. Get M15 candles from streamer → run OB/BB/IB detect       │
│    3. Get H1 candles from streamer → get trend context          │
│    4. Apply throttling → send to Discord if new alert           │
└─────────────────────────────────────────────────────────────────┘
```

### Alert Detection by Timeframe

| Alert Category | Type Code | Detection TF | Data Source | Throttle |
|----------------|-----------|--------------|-------------|----------|
| Liquidity Sweeps | `BEAR_SWEEP` / `BULL_SWEEP` | M5 | `streamer.get_candles(symbol, 'M5', 50)` | 5 min |
| CHOCH | `CHOCH_BULL` / `CHOCH_BEAR` | M5 | `streamer.get_candles(symbol, 'M5', 50)` | 5 min |
| BOS | `BOS_BULL` / `BOS_BEAR` | M15 | `streamer.get_candles(symbol, 'M15', 50)` | 10 min |
| Order Blocks | `BULLISH_OB` / `BEARISH_OB` | M15 | `streamer.get_candles(symbol, 'M15', 50)` | 10 min |
| VWAP Deviation | `VWAP_DEV_HIGH` / `VWAP_DEV_LOW` | M15 | `streamer.get_candles(symbol, 'M15', 50)` | 15 min |
| BB Squeeze | `BB_SQUEEZE` | M15 | `streamer.get_candles(symbol, 'M15', 50)` | 15 min |
| BB Expansion | `BB_EXPANSION` | M5/M15 | `streamer.get_candles(symbol, tf, 50)` | 15 min |
| Inside Bar | `INSIDE_BAR` | M15 | `streamer.get_candles(symbol, 'M15', 50)` | 30 min |
| Momentum Divergence | `RSI_DIV_BULL` / `RSI_DIV_BEAR` | M15 | `streamer.get_candles(symbol, 'M15', 50)` | 15 min |
| Equal Highs/Lows | `EQUAL_HIGHS` / `EQUAL_LOWS` | H1 | `streamer.get_candles(symbol, 'H1', 50)` | 30 min |

**All checks run every 60 seconds** - throttle prevents duplicate alerts within cooldown window.

### Resource Impact (Option 2 - Streamer Direct)

| Resource | Impact | Notes |
|----------|--------|-------|
| **CPU** | Low | Detection logic runs on cached data, no new fetching |
| **RAM** | Minimal (~10-20MB) | Throttle cache only; streamer already has candle data |
| **SSD** | None | No persistent storage |
| **Network** | ~1KB per alert | Discord webhook only |

---

## Discord Alert Format (ChatGPT-Ready)

### Severity Levels & Embed Colors

| Level | Color | Hex Code | Meaning | Criteria |
|-------|-------|----------|---------|----------|
| 🔸 **INFO** | Yellow | `0xffff00` | Setup forming | Confluence < 60% |
| 🔶 **ACTION** | Orange | `0xff9900` | Meets confluence | Confluence 60-79% |
| 🔴 **CRITICAL** | Red | `0xff0000` | High-probability | Confluence ≥ 80% |

### Template Structure (JSON-like for easy parsing)

```
{SEVERITY_EMOJI} **{ALERT_TYPE}** | {SYMBOL} | {TIMEFRAME}

[ALERT]
Symbol: {SYMBOL}
Type: {ALERT_TYPE}
Timeframe: {TIMEFRAME}
Price: {CURRENT_PRICE}
Confidence: {CONFLUENCE_SCORE}
Session: {CURRENT_SESSION}
Trend: {H1_TREND}
Volatility: {VOLATILITY_STATE}
Time: {ISO_TIMESTAMP}
Alert_ID: {SHORT_HASH}
Cross_TF: {PASSED|FAILED|N/A}
Notes: {DESCRIPTION}

**📋 Copy to ChatGPT:**
```
Analyze {SYMBOL} {TIMEFRAME} for {ALERT_TYPE} alert.
Detection: {DESCRIPTION}
Price: {PRICE} | Time: {ISO_TIMESTAMP}
Confidence: {CONFLUENCE_SCORE}% | Session: {SESSION}
Context: {H1_TREND} trend, {VOLATILITY_STATE} volatility.
If valid setup, create auto-execution plan for {CONFIRMATION_TF} confirmation.
```

### Example Alerts

#### 1. Liquidity Sweep Alert (Critical - 85% Confluence)
```
🔴 **BEAR_SWEEP** | XAUUSDc | M5

[ALERT]
Symbol: XAUUSDc
Type: BEAR_SWEEP
Timeframe: M5
Price: 4148.20
Confidence: 85
Session: London
Trend: Bearish
Volatility: EXPANDING
Time: 2025-11-26T14:35:22Z
Alert_ID: a3f7b2
Cross_TF: PASSED
Notes: Stops above 4150.50 cleared, price rejected

**📋 Copy to ChatGPT:**
```
Analyze XAUUSDc M5 for BEAR_SWEEP alert.
Detection: Stops above 4150.50 cleared, price rejected.
Price: 4148.20 | Time: 2025-11-26T14:35:22Z
Confidence: 85% | Session: London
Context: Bearish trend, EXPANDING volatility.
If valid setup, create auto-execution plan for M1/M5 CHOCH confirmation.
```

#### 2. Order Block Alert (Actionable - 72% Confluence)
```
🔶 **BULLISH_OB** | BTCUSDc | M15

[ALERT]
Symbol: BTCUSDc
Type: BULLISH_OB
Timeframe: M15
Price: 94850
Confidence: 72
Session: New_York
Trend: Bullish
Volatility: STABLE
Time: 2025-11-26T14:30:45Z
Alert_ID: b8c4d1
Cross_TF: PASSED
Notes: Institutional buy zone formed at 94200-94500

**📋 Copy to ChatGPT:**
```
Analyze BTCUSDc M15 for BULLISH_OB alert.
Detection: Institutional buy zone formed at 94200-94500.
Price: 94850 | Time: 2025-11-26T14:30:45Z
Confidence: 72% | Session: New_York
Context: Bullish trend, STABLE volatility.
If valid setup, create auto-execution plan for M5 CHOCH confirmation at OB retest.
```

#### 3. CHOCH Alert (Actionable - 68% Confluence)
```
🔶 **CHOCH_BEAR** | GBPUSDc | M5

[ALERT]
Symbol: GBPUSDc
Type: CHOCH_BEAR
Timeframe: M5
Price: 1.2580
Confidence: 68
Session: London_NY_Overlap
Trend: Bearish (was Bullish)
Volatility: STABLE
Time: 2025-11-26T14:32:18Z
Alert_ID: c2e9f5
Cross_TF: PASSED
Notes: Lower high formed, structure shifted bearish

**📋 Copy to ChatGPT:**
```
Analyze GBPUSDc M5 for CHOCH_BEAR alert.
Detection: Lower high formed, structure shifted bearish.
Price: 1.2580 | Time: 2025-11-26T14:32:18Z
Confidence: 68% | Session: London_NY_Overlap
Context: Bearish (was Bullish) trend, STABLE volatility.
If valid setup, create auto-execution plan for M15 trend confirmation.
```

#### 4. Volatility Trap Alert (Info - 55% Confluence)
```
🔸 **INSIDE_BAR** | XAUUSDc | M15

[ALERT]
Symbol: XAUUSDc
Type: INSIDE_BAR
Timeframe: M15
Price: 4145.00
Confidence: 55
Session: Pre_London
Trend: Neutral
Volatility: CONTRACTING
Time: 2025-11-26T06:45:33Z
Alert_ID: d5a1c8
Cross_TF: N/A
Notes: Compression forming, range 4142-4148 (6pts), BB Width 1.2

**📋 Copy to ChatGPT:**
```
Analyze XAUUSDc M15 for INSIDE_BAR alert.
Detection: Compression forming, range 4142-4148 (6pts), BB Width 1.2.
Price: 4145.00 | Time: 2025-11-26T06:45:33Z
Confidence: 55% | Session: Pre_London
Context: Neutral trend, CONTRACTING volatility.
If valid setup, create bracket trade plan for London breakout.
```

#### 5. VWAP Deviation Alert (Actionable - 74% Confluence)
```
🔶 **VWAP_DEV_HIGH** | BTCUSDc | M15

[ALERT]
Symbol: BTCUSDc
Type: VWAP_DEV_HIGH
Timeframe: M15
Price: 95200
Confidence: 74
Session: New_York
Trend: Bullish
Volatility: EXPANDING
Time: 2025-11-26T15:00:12Z
Alert_ID: e7f3a2
Cross_TF: N/A
Notes: Price +2.3σ above VWAP (94100), $1100 deviation

**📋 Copy to ChatGPT:**
```
Analyze BTCUSDc M15 for VWAP_DEV_HIGH alert.
Detection: Price +2.3σ above VWAP (94100), $1100 deviation.
Price: 95200 | Time: 2025-11-26T15:00:12Z
Confidence: 74% | Session: New_York
Context: Bullish trend, EXPANDING volatility.
If valid setup, create auto-execution plan for mean reversion SELL scalp.
```

---

## Implementation Details

### File: `infra/discord_alert_dispatcher.py`

```python
# Core components:

class AlertThrottler:
    """Prevents alert spam - max 1 alert per symbol/type per cooldown period"""
    - In-memory cache: {(symbol, alert_type): last_alert_time}
    - Configurable cooldowns per alert type (from config)
    - Auto-cleanup of entries older than max cooldown
    - Deduplication window: configurable per alert type (5-30 min)

class AlertFormatter:
    """Formats alerts for ChatGPT copy-paste"""
    - JSON-like [ALERT] block for easy parsing
    - Severity emoji based on confluence score
    - ISO 8601 timestamps (2025-11-26T14:35:22Z)
    - Alert_ID: 6-char hash for traceability
    - Discord embed color based on severity level

class DiscordAlertDispatcher:
    """Main dispatcher - connects analyzers to Discord"""
    - Fetches candles from multi_timeframe_streamer
    - Runs detection logic per timeframe (M5/M15/H1)
    - Calculates confluence score from MTF alignment
    - Applies throttling before sending
    - Sends formatted alerts with severity-based embed colors
```

### Integration Points

1. **Multi-Timeframe Streamer** (`multi_timeframe_streamer.py`)
   - Primary data source for all timeframes
   - Constructor: `MultiTimeframeStreamer(config: StreamerConfig, mt5_service=None)`
   - Method: `get_candles(symbol: str, timeframe: str, limit: Optional[int] = None) -> List[Candle]`
   - Already caches M5/M15/H1/H4 candles with auto-refresh
   - Returns `Candle` dataclass objects (symbol, timeframe, time, open, high, low, close, volume, spread)
   - **Note**: Returns candles **newest first** (index 0 = most recent candle)
   - **Note**: `StreamerConfig` is a dataclass with `symbols`, `buffer_sizes`, `refresh_intervals` fields

2. **Detection Logic** (NEW - cannot directly reuse M1 detectors)
   - ⚠️ **Note**: Existing `MicroOrderBlockDetector` and `MicroLiquiditySweepDetector` are M1-specific
   - Need to create **lightweight multi-TF detection functions** (not classes)
   - CHOCH/BOS: Adapt logic from `m1_microstructure_analyzer.detect_choch_bos()` for M5/M15
   - Order Blocks: Simplified OB detection (last impulse candle before reversal)
   - Liquidity Sweeps: Simplified sweep detection (wick beyond recent high/low + rejection)
   - VWAP: Reuse calculation from `vwap_micro_filter.py`
   - BB Width / Inside Bar / RSI Divergence: Simple calculations on candle data

3. **Discord Notifications** (`discord_notifications.py`)
   - Method: `send_message(message, message_type, color, channel, custom_title)` - **synchronous**
   - Use `asyncio.to_thread()` to call from async loop
   - Route to private webhook (alerts are personal)

4. **Confluence Scoring** (NEW - simple logic)
   - Base score from alert type (e.g., sweep = 60, OB = 50)
   - +10 if H1 trend aligns with direction
   - +10 if session is active (London/NY)
   - +10 if volatility state matches strategy (EXPANDING for breakouts, etc.)
   - +10 if cross-timeframe confirmation present (optional upgrade)
   - Cap at 100

5. **Session Helper** (`infra/session_helpers.py`)
   - Reuse existing `SessionHelper.get_current_session()` method
   - Returns: "ASIAN", "LONDON", "NY", "LONDON_NY_OVERLAP", etc.

6. **Volatility State** (`infra/m1_microstructure_analyzer.py`)
   - Reuse `calculate_volatility_state(candles, symbol)` method
   - Returns dict with `state`: "CONTRACTING", "EXPANDING", "STABLE"

7. **H1 Trend Context** (NEW - simple calculation)
   - Calculate from H1 candles: compare close vs open over last 5-10 candles
   - Returns: "Bullish", "Bearish", "Neutral"

8. **Cross-Timeframe Confirmation** (OPTIONAL - reduces false positives)
   - For CRITICAL alerts only (confluence ≥ 80%), add MTF validation:
     - CHOCH alerts: Require M15 OB or sweep alignment in same direction
     - Sweep alerts: Require M5 CHOCH confirmation within lookback window
     - OB alerts: Require M5 structure alignment (BOS/CHOCH in OB direction)
   - **Directional consistency check**: OB polarity must match CHOCH direction
   - **Parameterized lookback**: `lookback_candles` configurable per alert type
   - If MTF confirmation fails: downgrade from CRITICAL → ACTION
   - Adds ~10-20ms per alert check (minimal impact)

### Configuration File: `config/discord_alerts_config.json`

```json
{
  "enabled": true,
  "symbols": ["BTCUSDc", "XAUUSDc", "GBPUSDc", "EURUSDc"],
  "alerts": {
    "liquidity_sweep": {
      "enabled": true,
      "timeframes": ["M5"],
      "cooldown_minutes": 5
    },
    "order_block": {
      "enabled": true,
      "timeframes": ["M15"],
      "cooldown_minutes": 10
    },
    "choch": {
      "enabled": true,
      "timeframes": ["M5"],
      "cooldown_minutes": 5
    },
    "bos": {
      "enabled": true,
      "timeframes": ["M15"],
      "cooldown_minutes": 10
    },
    "vwap_deviation": {
      "enabled": true,
      "timeframes": ["M15"],
      "min_sigma": 2.0,
      "cooldown_minutes": 15
    },
    "inside_bar": {
      "enabled": true,
      "timeframes": ["M15"],
      "cooldown_minutes": 30
    },
    "bb_squeeze": {
      "enabled": true,
      "timeframes": ["M15"],
      "max_bb_width": 1.5,
      "cooldown_minutes": 15
    },
    "bb_expansion": {
      "enabled": true,
      "timeframes": ["M5", "M15"],
      "min_bb_width": 2.0,
      "cooldown_minutes": 15
    },
    "rsi_divergence": {
      "enabled": true,
      "timeframes": ["M15"],
      "cooldown_minutes": 15
    },
    "equal_highs_lows": {
      "enabled": true,
      "timeframes": ["H1"],
      "cooldown_minutes": 30
    }
  },
  "cross_tf_confirmation": {
    "enabled": true,
    "required_for_critical": true,
    "directional_consistency": true,
    "rules": {
      "choch": {
        "confirmation_tf": "M15",
        "require": "ob_or_sweep",
        "lookback_candles": 5,
        "direction_must_match": true
      },
      "sweep": {
        "confirmation_tf": "M5",
        "require": "choch",
        "lookback_candles": 3,
        "direction_must_match": true
      },
      "order_block": {
        "confirmation_tf": "M5",
        "require": "structure_alignment",
        "lookback_candles": 5,
        "direction_must_match": true
      }
    }
  },
  "sessions": {
    "london_only": false,
    "ny_only": false,
    "overlap_priority": true
  },
  "quiet_hours": {
    "enabled": true,
    "start_utc": 22,
    "end_utc": 6
  }
}
```

---

## Implementation Steps

### Phase 1: Core Dispatcher (~1 hour)
1. Create `infra/discord_alert_dispatcher.py`
2. Implement `AlertThrottler` class
3. Implement `AlertFormatter` class
4. Implement `DiscordAlertDispatcher` class
5. Create `config/discord_alerts_config.json`

### Phase 2: Multi-TF Detection Logic (~2 hours)
1. Create lightweight detection functions (not classes) in `discord_alert_dispatcher.py`:
   - `detect_choch_bos(candles, timeframe)` - adapt logic from M1 analyzer
   - `detect_liquidity_sweep(candles)` - simplified sweep detection
   - `detect_order_block(candles)` - simplified OB detection
   - `detect_vwap_deviation(candles, threshold_sigma)` - reuse VWAP calc
   - `detect_bb_state(candles)` - squeeze/expansion detection
   - `detect_inside_bar(candles)` - pattern detection
   - `detect_rsi_divergence(candles)` - momentum divergence
   - `detect_equal_highs_lows(candles)` - liquidity zone detection
   - `get_h1_trend(candles)` - simple trend from H1 data
2. Implement confluence scoring logic
3. Test each detection function independently

### Phase 3: Integration & Startup (~30 min)
1. Add monitoring loop to `main_api.py` startup
2. Connect to streamer for candle data
3. Connect to Discord notifier for alerts

### Phase 4: Testing & Tuning (~30 min)
1. Test each alert type with live data
2. Verify alert formatting
3. Adjust throttle timings
4. Test copy-paste workflow with ChatGPT

---

## Startup Integration

Add to `main_api.py` startup:

In `main_api.py` `startup_event()` function (after line ~250):

```python
from infra.discord_alert_dispatcher import DiscordAlertDispatcher

# Global variable at top of file
alert_dispatcher: Optional[DiscordAlertDispatcher] = None
alert_dispatcher_task: Optional[asyncio.Task] = None

# Inside startup_event():
global alert_dispatcher, alert_dispatcher_task

# Initialize dispatcher (creates its own streamer/notifier internally)
# Dispatcher will create StreamerConfig with alert symbols from config/discord_alerts_config.json
alert_dispatcher = DiscordAlertDispatcher()
await alert_dispatcher.start()  # Starts internal streamer with proper StreamerConfig

# Create background task for detection loop (runs every 60 seconds)
async def alert_detection_loop():
    while True:
        try:
            await alert_dispatcher.run_detection_cycle()
        except Exception as e:
            logger.error(f"Alert detection error: {e}")
        await asyncio.sleep(60)

alert_dispatcher_task = asyncio.create_task(alert_detection_loop())
logger.info("Discord alert dispatcher started")
```

In `shutdown_event()`:

```python
global alert_dispatcher_task
if alert_dispatcher_task:
    alert_dispatcher_task.cancel()
    logger.info("Discord alert dispatcher stopped")
```

**Note**: 
- Uses `asyncio.create_task()` pattern (same as existing `oco_monitor_loop`)
- No APScheduler needed - main_api.py uses native asyncio
- Dispatcher creates its own `MultiTimeframeStreamer` and `DiscordNotifier` internally
- Uses `asyncio.to_thread()` to call the synchronous `discord_notifier.send_message()` method

---

## Expected Alert Volume

| Symbol | Alerts/Hour (Active Session) | Alerts/Day |
|--------|------------------------------|------------|
| XAUUSDc | 2-4 | 15-25 |
| BTCUSDc | 2-4 | 15-25 |
| GBPUSDc | 1-2 | 8-15 |
| EURUSDc | 1-2 | 8-15 |
| **Total** | **6-12** | **45-80** |

With throttling, expect **~50-80 alerts per day** across all symbols during active trading hours.

---

## Summary

| Aspect | Details |
|--------|---------|
| **New Files** | 1 (`discord_alert_dispatcher.py`) + 1 config |
| **Modified Files** | 1 (`main_api.py` - add startup hook) |
| **CPU Impact** | Low - detection runs on cached streamer data |
| **RAM Impact** | ~10-20MB (throttle cache only) |
| **SSD Impact** | None |
| **Development Time** | ~4 hours |
| **Dependencies** | None (uses existing infrastructure) |

---

## Why Option 2 (Streamer Direct) Over Option 1 (Aggregate M1)

| Criteria | Option 1: Aggregate M1 | Option 2: Streamer Direct ✅ |
|----------|------------------------|------------------------------|
| CPU | Higher - aggregation every 60s | Lower - read cached data |
| RAM | Higher - store aggregated candles | Lower - streamer already caches |
| Accuracy | Lower - synthetic candles | Higher - real broker candles |
| Complexity | More code | Less code |
| Maintenance | Sync issues possible | Clean separation |

