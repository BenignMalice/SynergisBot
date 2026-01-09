# MoneyBot Binance Integration - Custom GPT Knowledge Update

## ⚠️ IMPORTANT: System Architecture Updated (October 2025)

**Previous Architecture (OLD):**
```
Yahoo Finance → Macro data (DXY, VIX, US10Y)
MT5 Broker → All trading data
```

**Current Architecture (NEW - Phases 1-3 Complete):**
```
Binance WebSocket → Real-time price data (BTCUSD only, 1s updates)
MT5 Broker → Execution + indicators (all symbols)
Yahoo Finance → Macro data (DXY, VIX, US10Y)
```

---

## 🚀 Binance Integration Status: ACTIVE & PRODUCTION READY

### What Changed (October 12, 2025)

The MoneyBot system now includes **full Binance streaming integration** across 3 completed phases:

#### Phase 1: Data Ingestion ✅
- Real-time WebSocket streaming from Binance (1-second updates)
- Price cache for BTCUSD only (btcusdt)
- **Important:** Binance only supports crypto pairs - XAUUSD, EURUSD, GBPUSD, etc. are NOT available on Binance
- Automatic price offset calibration between Binance and MT5 broker
- Feed health monitoring and validation

#### Phase 2: Integration & Safety ✅
- High-level BinanceService wrapper
- Signal pre-filter with 9-point safety validation
- Desktop agent auto-starts Binance streams
- Symbol mapping (Binance format ↔ MT5 broker format)
- New tool: `moneybot.binance_feed_status`

#### Phase 3: Analysis Enhancement ✅
- MT5 indicator data enriched with Binance microstructure
- Micro-momentum calculation (sub-minute trend detection)
- Price velocity tracking
- Volume acceleration monitoring
- Signal confirmation (Binance validates MT5 signals)

#### Phase 4: Order Flow Service ✅ (November 2025)
- Lightweight Order Flow Service enabled for BTCUSD
- Order book depth streaming (20 levels @ 100ms)
- Whale detection ($50k+ institutional orders)
- Order book imbalance analysis
- Liquidity void detection
- Buy/sell pressure tracking
- **Note:** BTCUSD only - Binance doesn't provide order book depth for forex/commodities

#### Phase 5: BTC Order Flow Metrics ⭐ NEW (November 2025)
- **New Tool:** `moneybot.btc_order_flow_metrics`
- **Delta Volume:** Real-time buy/sell volume imbalance from Binance aggTrades
- **CVD (Cumulative Volume Delta):** Cumulative sum of delta volume with slope calculation
- **CVD Divergence:** Price vs CVD divergence detection for reversal signals
- **Absorption Zones:** Price levels where large orders are being absorbed (high volume + order book imbalance)
- **Buy/Sell Pressure:** Ratio of buy to sell volume/value
- **Data Source:** Binance WebSocket (aggTrades + order book depth)
- **Use Case:** Better entry/exit timing for BTC trades based on institutional order flow
- **When to Use:** When user asks for "order flow", "CVD", "delta volume", "absorption zones", or "buy/sell pressure" for BTC

---

## 📡 New Tools Available

### Tool 1: `moneybot.binance_feed_status`

**Purpose:** Check the health and status of real-time Binance data streams

**When to Use:**
- User asks about Binance feed
- User wants to verify data quality
- Before executing trades (optional check)
- Troubleshooting connectivity

**Arguments:**
```json
{
  "tool": "moneybot.binance_feed_status",
  "arguments": {
    "symbol": "BTCUSD"  // Optional - specific symbol or omit for all
  }
}
```

**Example Responses:**

**All symbols:**
```
📡 Binance Feed Status - All Symbols

Total Symbols: 1
✅ Healthy: 1
⚠️ Warning: 0
🔴 Critical: 0

✅ BTCUSDT: Offset +3.2 pips
```

**Note:** Only BTCUSD is streamed from Binance. Binance only supports cryptocurrency pairs (btcusdt, ethusdt, etc.). Forex pairs (EURUSD, GBPUSD, etc.) and commodities (XAUUSD) are not available on Binance and use MT5 data only.

---

## 🔬 M1 Microstructure vs Binance Enrichment ⭐ NEW

### Comparison

| Feature | M1 Microstructure | Binance Enrichment |
|---------|------------------|-------------------|
| **Symbol Support** | ALL symbols (XAUUSD, EURUSD, BTCUSD, etc.) | BTCUSD only (crypto pairs) |
| **CHOCH/BOS Detection** | ✅ Yes | ❌ No |
| **Liquidity Zones** | ✅ Yes (PDH/PDL, equal highs/lows) | ❌ No |
| **Volatility State** | ✅ Yes (CONTRACTING/EXPANDING/STABLE) | ❌ No |
| **Order Blocks** | ✅ Yes | ❌ No |
| **Rejection Wicks** | ✅ Yes | ❌ No |
| **Momentum Quality** | ✅ Yes (EXCELLENT/GOOD/FAIR/CHOPPY) | ❌ No |
| **Trend Context** | ✅ Yes (M1/M5/H1 alignment) | ❌ No |
| **Real-time Price** | ❌ No (1-minute candles) | ✅ Yes (1s updates) |
| **Micro-momentum** | ❌ No | ✅ Yes |
| **Order Flow** | ❌ No | ✅ Yes (BTCUSD only) |
| **Session Context** | ✅ Yes (session-adjusted parameters) | ❌ No |
| **Asset Personality** | ✅ Yes (symbol-specific behavior) | ❌ No |
| **Dynamic Thresholds** | ✅ Yes (adaptive confluence) | ❌ No |
| **Strategy Hints** | ✅ Yes (BREAKOUT/RANGE_SCALP/etc.) | ❌ No |

### When to Use Each

**For BTCUSD:**
- Use **both** M1 microstructure and Binance enrichment
- M1 for structure and liquidity (CHOCH/BOS, liquidity zones, volatility state)
- Binance for real-time price and order flow (micro-momentum, whale activity)
- Combined = maximum intelligence

**For Other Symbols (XAUUSD, EURUSD, etc.):**
- Use **M1 microstructure only** (Binance not available)
- M1 provides all microstructure insights (CHOCH/BOS, liquidity, volatility, order blocks)
- Still provides institutional-grade analysis

### Integration

Both are automatically included in `moneybot.analyse_symbol_full`:
- M1 microstructure: Always included (all symbols)
- Binance enrichment: Included for BTCUSD only

**Example Response Structure:**
```json
{
  "m1_microstructure": {
    "available": true,
    "signal_summary": "BULLISH_MICROSTRUCTURE",
    "choch_bos": {"has_choch": true, "confidence": 85},
    "liquidity_zones": [...],
    "volatility": {"state": "CONTRACTING", "squeeze_duration": 25},
    "momentum": {"quality": "EXCELLENT", "consistency": 89}
  },
  "binance_enrichment": {
    "available": true,  // Only for BTCUSD
    "real_time_price": 110298.5,
    "micro_momentum": 0.15,
    "order_flow": {...}
  }
}
```

**Single symbol:**
```
✅ Binance Feed Status - BTCUSD

Status: HEALTHY
Offset: +3.2 pips (Binance vs MT5)
Data Age: 2.5s
Tick Count: 850

Assessment: All checks passed
```

**If offline:**
```
⚠️ Binance feed not running

Status: offline
Message: Binance streaming service is not initialized
```

---

## 🎯 How Binance Data is Used

### 1. Real-Time Price Updates
- **Binance:** 1-second tick updates
- **MT5:** 1-minute candle updates
- **Benefit:** Faster price information, better timing

### 2. Price Offset Calibration
- Tracks price differences between Binance and MT5 broker
- Example: Binance BTC = $112,180, MT5 BTC = $112,120 → Offset = +60 pips
- **Automatically adjusts trade signals** for MT5 execution

### 3. Feed Health Monitoring
- Validates data freshness (< 60 seconds)
- Checks spread widths (< 3x normal)
- Detects feed divergence (< 5% difference)
- **Blocks trades if data quality is poor**

### 4. Analysis Enhancement (Phase 3) - BTCUSD Only
- **Micro-momentum:** Sub-minute price trend detection (BTCUSD only)
- **Price velocity:** Instantaneous acceleration/deceleration (BTCUSD only)
- **Volume acceleration:** Interest rising/fading (BTCUSD only)
- **Signal confirmation:** Does Binance agree with MT5 signal? (BTCUSD only)
- **Note:** Other symbols (XAUUSD, EURUSD, etc.) use MT5 data only - no Binance enhancement available

### 5. Pre-Execution Validation (BTCUSD Only)
When user says "Execute" for BTCUSD, the system validates:
- ✅ Feed health (Binance data quality)
- ✅ Price offset (< 100 pips)
- ✅ Spread validation (< 3x normal)
- ✅ Data freshness (< 60s)
- Plus 5 other safety checks

**Note:** For other symbols (XAUUSD, EURUSD, etc.), validation uses MT5 data only since Binance doesn't support these pairs.

### 6. Order Flow Analysis (BTCUSD Only) ⭐ NEW
- **Whale Detection:** Large institutional orders ($50k+) that may impact price
- **Order Book Imbalance:** Bid/ask pressure ratio (bullish if >1.0, bearish if <1.0)
- **Liquidity Voids:** Thin zones where slippage may occur
- **Buy/Sell Pressure:** Real-time institutional positioning
- **Order Flow Signals:** BULLISH/BEARISH/NEUTRAL with confidence scores
- **Contradiction Detection:** Flags when order flow opposes technical signals

---

## 📊 Enhanced Analysis Output

### Before Binance Integration:
```
📊 GBPUSD Analysis - BREAKOUT

Direction: BUY
Entry: 1.2650
SL: 1.2620 / TP: 1.2710
Confidence: 85%

💡 Strong breakout with volume
```

### After Binance Integration (Current - BTCUSD Only):
```
📊 BTCUSD Analysis - BREAKOUT

Direction: BUY
Entry: 112150
SL: 112000 / TP: 112400
Confidence: 85%

💡 Strong breakout with volume

📡 Binance Feed:
  ✅ Status: HEALTHY
  💰 Price: $112,180
  ⏱️ Age: 2.5s
  📈 Micro Momentum: +0.65%
  🔄 Offset: +3.2 pips

✅ Binance confirms BUY (momentum: +0.65%)
```

**For Other Symbols (XAUUSD, EURUSD, etc.):**
```
📊 GBPUSD Analysis - BREAKOUT

Direction: BUY
Entry: 1.2650
SL: 1.2620 / TP: 1.2710
Confidence: 85%

💡 Strong breakout with volume

⚠️ Binance Feed: Not available for GBPUSD
  → Binance only supports crypto pairs (BTCUSD, ETHUSD, etc.)
  → Analysis uses MT5 data only
```

**New Information Shown (BTCUSD only):**
1. Binance real-time price
2. Data age (freshness)
3. Micro-momentum (sub-minute trend)
4. Price offset (calibration)
5. Signal confirmation status

---

## 🔧 Symbols Monitored

**⚠️ IMPORTANT: Binance Symbol Support**

**Currently Streaming from Binance (1 symbol only):**

| Symbol | Binance Name | MT5 Name | Type | Binance Support |
|--------|--------------|----------|------|----------------|
| Bitcoin | btcusdt | BTCUSDc | Crypto | ✅ Supported |

**Other Symbols (MT5 Only - NOT on Binance):**

| Symbol | MT5 Name | Type | Binance Support |
|--------|----------|------|----------------|
| Gold | XAUUSDc | Commodity | ❌ Not available |
| Euro/Dollar | EURUSDc | Forex Major | ❌ Not available |
| Pound/Dollar | GBPUSDc | Forex Major | ❌ Not available |
| Dollar/Yen | USDJPYc | Forex Major | ❌ Not available |
| Pound/Yen | GBPJPYc | Forex Cross | ❌ Not available |
| Euro/Yen | EURJPYc | Forex Cross | ❌ Not available |

**Why Only BTCUSD?**
Binance only provides WebSocket streaming for cryptocurrency pairs (btcusdt, ethusdt, etc.). Traditional forex pairs (EURUSD, GBPUSD) and commodities (XAUUSD) are not available on Binance's public WebSocket API. These symbols use MT5 broker data only.

**User can ask about any symbol using:**
- Standard format: "BTCUSD", "EURUSD", "GBPJPY"
- MT5 format: "BTCUSDc", "EURUSDc" (system auto-converts)
- Binance format: "btcusdt" (for BTCUSD only)

---

## 💬 How to Respond to User Queries

### Query: "Check Binance feed status"

**Action:** Call `moneybot.binance_feed_status` with no arguments

**Response Pattern:**
```
I'll check the Binance feed status.

[Call tool]

📡 Binance Feed Status:
[Show tool result]

BTCUSD is streaming healthy data from Binance. Note: Other symbols (XAUUSD, EURUSD, etc.) use MT5 data only since Binance only supports crypto pairs.
```

### Query: "Is Binance feed working for BTCUSD?"

**Action:** Call `moneybot.binance_feed_status` with `{"symbol": "BTCUSD"}`

**Response Pattern:**
```
Let me check the Binance feed specifically for BTCUSD.

[Call tool]

✅ BTCUSD Binance feed is healthy:
[Show tool result]

The feed is receiving live data with a +3.2 pip offset from your MT5 broker.
```

### Query: "Analyse GBPUSD"

**Important:** When you call `moneybot.analyse_symbol`:
- **For BTCUSD:** Response includes Binance data automatically (real-time price, micro-momentum, signal confirmation)
- **For other symbols (XAUUSD, EURUSD, GBPUSD, etc.):** Response uses MT5 data only - Binance is not available for these symbols

**Response Pattern (BTCUSD):**
```
I'll analyse BTCUSD using MT5 indicators enhanced with real-time Binance data.

[Call moneybot.analyse_symbol]

[Present full analysis including the Binance section at the bottom]

Note: This analysis includes real-time Binance data showing micro-momentum of +0.65%, confirming the breakout signal from MT5.
```

**Response Pattern (Other Symbols):**
```
I'll analyse GBPUSD using MT5 indicators and technical analysis.

[Call moneybot.analyse_symbol]

[Present full analysis - no Binance section since GBPUSD is not available on Binance]

Note: Analysis based on MT5 data. Binance streaming is only available for crypto pairs (BTCUSD, ETHUSD, etc.).
```

---

## 🚨 Error Handling

### If Binance Feed is Offline

**Tool Response:**
```
⚠️ Binance feed not running
Status: offline
```

**How to Respond:**
```
The Binance feed is currently offline. This means:

✅ Your trades can still execute (MT5 is the execution layer)
✅ Analysis will use MT5 data only (1-minute candles)
❌ Real-time micro-momentum unavailable for BTCUSD
❌ Signal confirmation unavailable for BTCUSD

**Note:** For symbols other than BTCUSD (XAUUSD, EURUSD, etc.), Binance is never available anyway - these always use MT5 data only.

The system will work normally but without the enhanced real-time features for BTCUSD. The desktop agent needs to be running to enable Binance streaming.
```

### If Feed is Unhealthy

**Tool Response:**
```
🔴 Status: CRITICAL
Reason: Stale data (age: 120s)
```

**How to Respond:**
```
⚠️ The Binance feed is currently unhealthy (data is stale). 

The system's safety filter may block trade execution until the feed recovers. This is a protective measure to prevent trading on outdated information.

Suggestion: Wait a few moments and check again, or proceed with MT5-only analysis.
```

---

## 📋 Integration Status Summary

**For User Questions about System Status:**

```
Your MoneyBot system now includes:

✅ Binance Real-Time Streaming (Phases 1-4 Complete)
  • 1 symbol monitored (BTCUSD only - Binance limitation)
  • 1 symbol with full order flow (BTCUSD only)
  • 1-second price updates for BTCUSD
  • Automatic offset calibration (BTCUSD)
  • Feed health monitoring (BTCUSD)
  • Analysis enhancement with micro-momentum (BTCUSD only)
  • Signal confirmation (BTCUSD only)
  • Order Flow Service (BTCUSD: whales, imbalance, voids)
  • **Note:** Other symbols (XAUUSD, EURUSD, etc.) use MT5 data only

✅ MT5 Broker Integration
  • Execution layer (all symbols)
  • Indicator computation (all symbols)
  • Position management (all symbols)

✅ Yahoo Finance
  • Macro data (DXY, VIX, US10Y)

All systems are operational. BTCUSD gets enhanced Binance data; other symbols use MT5 data only (Binance doesn't support forex/commodities).
```

---

## 🎯 Key Points for Custom GPT

1. **Binance IS part of the system** (updated October 2025) - **BTCUSD ONLY**
2. **Binance data enhances MT5 analysis for BTCUSD** (not a replacement)
3. **Tool available:** `moneybot.binance_feed_status` (will show BTCUSD only)
4. **Analysis output includes Binance data automatically** - **for BTCUSD only**
5. **1 symbol actively monitored** from Binance (BTCUSD) - Binance only supports crypto pairs
6. **Other symbols (XAUUSD, EURUSD, etc.)** use MT5 data only - Binance doesn't support forex/commodities
7. **Order Flow Service:** BTCUSD only (Binance limitation for forex/commodities)
8. **System works with or without Binance** (graceful fallback)
9. **All tests passed:** 14/14 (100% success rate)
10. **Status:** Production ready and actively used

---

## 📖 Reference Documentation

**For detailed information, refer to:**
- `BINANCE_INTEGRATION_COMPLETE.md` - Complete overview
- `BINANCE_QUICK_START.md` - Quick start guide
- `PHASE2_BINANCE_INTEGRATION_COMPLETE.md` - Integration details
- `PHASE3_BINANCE_ENRICHMENT_COMPLETE.md` - Enhancement features
- `SYMBOL_MAPPING_REFERENCE.md` - Symbol conversion

**Testing:**
- 52 total tests across all phases
- 100% pass rate
- Production ready since October 12, 2025

---

## 🐋 Order Flow Service (NEW - November 2025)

### ⚠️ Important: BTCUSD Only

**Status:** ✅ **ENABLED** - Lightweight Order Flow Service active for BTCUSD

**Symbol Support:**
- ✅ **BTCUSD** - Full order flow analysis available
- ❌ **XAUUSD, EURUSD, GBPUSD, etc.** - Order flow NOT available (Binance doesn't offer order book depth for forex/commodities)

**Why Limited?**
Binance only provides order book depth streams (`@depth20@100ms`) for cryptocurrency pairs. Traditional forex pairs (EURUSD, GBPUSD) and commodities (XAUUSD) are not available on Binance's order book depth API.

### What Order Flow Provides (BTCUSD Only)

**Available Features:**
1. **🐋 Whale Detection** - Identifies large institutional orders ($50k+, $100k+, $500k+, $1M+)
2. **📊 Order Book Imbalance** - Bid/ask pressure analysis (ratio >1.0 = bullish, <1.0 = bearish)
3. **⚠️ Liquidity Void Detection** - Identifies thin zones where slippage may occur
4. **📈 Buy/Sell Pressure** - Real-time institutional positioning
5. **🔴 Order Flow Signals** - BULLISH/BEARISH/NEUTRAL with confidence scores

**How It Works:**
- RAM-only storage (no database writes)
- WebSocket streams: Order book depth (20 levels @ 100ms) + Aggregate trades
- Ultra-lightweight: ~2-5% CPU, ~50-100 KB RAM per symbol

### How Order Flow Appears in Analysis

**For BTCUSD (with order flow):**
```
📊 BTCUSD Analysis

...technical analysis...

🐋 Order Flow: BULLISH (Confidence: 82%)
  → 3 whales BUY ($1.8M total) in last 60s
  → Book Imbalance: 1.9x (heavy bid pressure)
  → Pressure Side: BUYERS DOMINATING
  → 0 liquidity voids ahead
  → Signal confirms BUY direction
```

**For XAUUSD/EURUSD/etc. (without order flow):**
```
📊 XAUUSD Analysis

...technical analysis...

⚠️ Order Flow: Not available
  → Binance doesn't provide order book depth for this symbol
  → Analysis uses MT5 data + technical indicators only
```

### When to Mention Order Flow

**DO mention order flow for BTCUSD:**
- "Order flow shows 2 large buy orders ($800k) confirming the bullish setup"
- "Whale activity detected - institutional accumulation in progress"
- "Book imbalance at 2.1x suggests strong bid pressure"

**DON'T mention order flow for XAUUSD/EURUSD/etc.:**
- These symbols don't have order flow data
- Just say: "Analysis based on MT5 indicators and technical structure"

---

**Last Updated:** November 19, 2025  
**Integration Status:** Phases 1-4 Complete ✅  
**Symbols Supported:** BTCUSD only (Binance limitation - only crypto pairs supported)  
**Order Flow Service:** ✅ Enabled (BTCUSD only)  
**Production Status:** Active and Operational 🚀

---

## ⚠️ CRITICAL CLARIFICATION

**Binance Symbol Support Reality:**
- ✅ **BTCUSD (btcusdt)** - Fully supported with real-time streaming, order flow, micro-momentum
- ❌ **XAUUSD, EURUSD, GBPUSD, USDJPY, GBPJPY, EURJPY** - NOT supported by Binance
  - These symbols use MT5 broker data only
  - No Binance enhancement available
  - No order flow analysis available
  - No micro-momentum detection available

**Why?** Binance's public WebSocket API only provides streaming for cryptocurrency pairs (btcusdt, ethusdt, etc.). Traditional forex pairs and commodities are not available on Binance.

