# MoneyBot v1.0 - Advanced AI Trading System

An advanced AI-powered trading bot that integrates with MetaTrader 5 (MT5) and provides intelligent trading analysis, position management, and automated trade execution through Telegram. Features **full ChatGPT integration** with Custom GPT support, **Binance 1-second real-time streaming**, **institutional-grade order flow analysis**, **100% automatic intelligent exit management**, **enhanced news trading**, **professional trading strategies**, and **comprehensive risk management** with logging and analytics.

## 🌟 What Makes This Bot Different

### 🤖 True AI Trading Assistant
- **Natural Language Trading**: Talk to your bot like a professional trading assistant
- **Dual Interface**: Identical capabilities on Telegram bot AND Custom GPT (via phone/web)
- **Live Market Data**: Never quotes external sources - always uses broker prices
- **Mandatory Context Checks**: Automatically fetches DXY, US10Y, VIX for Gold/USD pairs
- **Complete Conversation Logging**: Every analysis and trade decision logged to database

### 🚀 Unified Tick Pipeline (DISABLED - Resource Conservation)
- **⚠️ STATUS: DISABLED** - The Unified Tick Pipeline with Binance WebSocket streams is **permanently disabled** for resource conservation (CPU ~10-20%, high RAM/SSD usage).
- **Why Disabled**: Extremely resource-intensive with continuous Binance WebSocket streams, real-time tick processing, and high database write frequency. Not suitable for personal laptops/desktops.
- **Alternative**: System uses lightweight **Multi-Timeframe Streamer** instead (see below) which provides efficient candlestick data with minimal resource usage.
- **Re-Enable Option**: Code remains available (commented out) in `app/main_api.py` and `desktop_agent.py`. Can be re-enabled on dedicated servers if Binance tick-level data is needed.
- **Original Features** (for reference):
  - Binance Dual Feeds: High-frequency tick data via WebSockets for BTCUSDT, XAUUSDT, ETHUSDT
  - MT5 M1 Streaming: Real-time M1 data streaming for forex pairs with sub-second updates
  - Dynamic Offset Engine: Calibrates price discrepancies between Binance and MT5 feeds
  - M5 Volatility Bridge: Aggregated M5 data for volatility context and execution timing
  - Institutional Order Flow: Whale detection, tape reading, order book imbalance
  - 37 Enrichment Fields: Price structure, volatility state, momentum quality, Z-score, pivots, liquidity, and more

### 📊 Multi-Timeframe Streamer (NEW!)
- **Efficient Candlestick Streaming**: Continuously streams M5, M15, M30, H1, H4 candlestick data for configured symbols
- **Incremental Fetching**: Only fetches new candles since last update (typically 1-5 per cycle, not full history)
- **Rolling Buffers**: Fixed-size deques that automatically expire old data (~50 KB per symbol for all timeframes)
- **Smart Refresh Rates**: Different intervals for each timeframe (M5: 5min, M15: 15min, M30: 30min, H1: 1hour, H4: 4hours)
- **Immediate Data Availability**: Fetches initial historical data at startup (populates buffers immediately, no waiting)
- **RAM-Only Mode**: Optional database storage (default disabled for safety)
- **API Endpoints**: 
  - `GET /api/v1/candles/{symbol}/{timeframe}` - Get candles with optional limit
  - `GET /api/v1/candles/{symbol}/{timeframe}/latest` - Get latest candle only
  - `GET /api/v1/streamer/status` - Streamer status and metrics
- **Resource Efficient**: ~50 KB per symbol, minimal CPU usage, minimal MT5 API calls (~50/hour for 10 symbols)
- **Configuration**: `config/multi_tf_streamer_config.json` - symbols, buffer sizes, refresh intervals
- **Documentation**: `docs/MULTI_TIMEFRAME_STREAMING_GUIDE.md` - Complete usage guide
- **Integration**: Starts automatically with Main API server (`app/main_api.py`)
- **Separation**: ChatGPT continues using direct MT5 calls (`IndicatorBridge.get_multi()`) for guaranteed fresh analysis data
- **Files**: `infra/multi_timeframe_streamer.py`, `app/main_api.py` (integration)

### 🔄 Liquidity Sweep Reversal Engine (NEW!)
- **Autonomous SMC Trading**: Continuously monitors BTCUSD and XAUUSD for liquidity sweeps (stop hunts)
- **Three-Layer Confluence Stack**: 
  - Macro Context (30%): VIX, session validation, trend bias, DXY, news blackout
  - Setup Context (40%): Sweep structure, volume spike, VWAP distance, PDH/PDL proximity
  - Trigger Context (30%): CHOCH/BOS, rejection candles, volume decline, ADX flattening
- **Automatic Execution**: Trades reversals when confluence score ≥70% (Type 1: instant, Type 2: retest)
- **Risk Management**: Integrates with Intelligent Exit Manager for post-entry management (breakeven, partial profits, trailing stops)
- **Session-Aware**: Only trades during London (07-10 UTC) or NY (12-16 UTC) sessions
- **Macro-Filtered**: Avoids trading through systemic shocks (VIX >25, high-impact news)
- **Discord Notifications**: Real-time alerts for sweep detection, trade execution, setup invalidation
- **Configuration**: `config/liquidity_sweep_config.json` - symbols, risk parameters, thresholds, notifications
- **State Persistence**: `data/liquidity_sweep_state.json` - active setups persist across restarts
- **Documentation**: `docs/LIQUIDITY_SWEEP_REVERSAL_ENGINE.md` - Complete implementation guide
- **Files**: `infra/liquidity_sweep_reversal_engine.py`, `config/liquidity_sweep_config.json`, `tests/test_liquidity_sweep_reversal_engine.py`

### 🛡️ Intelligent Profit Protection (NEW!)
- **Technical Analysis-Based**: 7-signal warning system (not random probability)
- **Tiered Response**: Monitor → Tighten SL → Exit based on signal strength
- **Critical Signals**: CHOCH (structure break), opposite engulfing (3 points each)
- **Medium Signals**: Liquidity rejection, divergence, S/R break (2 points each)
- **Minor Signals**: Momentum loss, session shift, whale orders (1 point each)
- **Weighted Scoring**: Score ≥5 = exit, score 2-4 = tighten, score <2 = monitor
- **Only for Profits**: Protects gains from turning into losses

### 📊 Comprehensive Loss Cutting System (NEW!)
- **7 Distinct Checks**: Early exit AI, structure collapse, momentum fade, time backstop, spread spike, ADX death, risk simulation
- **Confluent Logic**: Multiple factors must align before cutting
- **Automatic Execution**: Closes losing trades with retry logic (3 attempts, increasing deviation)
- **Discord Alerts**: Real-time notifications for all loss cut actions via Discord webhooks
- **Database Logging**: Full audit trail of all loss cutting decisions

### 🎯 Dynamic Risk-Based Lot Sizing (NEW!)
- **Symbol-Specific Risk**: BTCUSD/XAUUSD max 2% (0.02 lots), Forex max 4% (0.04 lots)
- **Risk-Percentage Based**: Consistent $ risk per trade regardless of SL distance
- **0.01 Lot Increments**: Proper rounding for broker compatibility
- **Automatic Calculation**: ChatGPT/bot calculates optimal volume if not specified
- **Account-Adaptive**: Scales with equity changes

### 📰 Enhanced News Trading (NEW!)
- **GPT-4 Sentiment Analysis**: Real-time news sentiment analysis with trading implications
- **115 Enhanced Events**: All news events enhanced with sentiment, risk assessment, and trading guidance
- **Strategy Knowledge Documents**: London Breakout Strategy and News Trading Strategy
- **Automated Enhancement**: News sentiment updated every 4 hours via Windows Task Scheduler
- **Risk-Based Trading**: HIGH/ULTRA_HIGH risk events with specific trading approaches
- **News-Aware Analysis**: ChatGPT references appropriate strategies for different market conditions
- **News Data Gathering**: Automated fetching from Forex Factory, breaking news scraping, and sentiment enhancement
  - `fetch_news_feed.py` - Forex Factory economic calendar fetcher
  - `priority2_breaking_news_scraper.py` - Real-time breaking news scraper
  - `fetch_news_sentiment.py` - GPT-4 sentiment enhancement

### 🔔 Discord Notifications (NEW!)
- **Rich Embed Messages**: Beautiful formatted notifications with color coding
- **Trade Alerts**: Real-time notifications for trade opens/closes with profit/loss
- **System Alerts**: Bot startup, errors, status updates
- **DTMS Alerts**: Defensive Trade Management System notifications
- **Risk Alerts**: Risk management warnings and actions
- **Error Alerts**: Component failures and system errors
- **Mobile Notifications**: Instant alerts on your phone via Discord app
- **Easy Setup**: Configure via Discord webhook URL in .env file

### 🔔 Enhanced Alert System (NEW!)
- **Intelligent Intent Parsing**: Natural language alert requests with advanced parameter mapping
- **Volatility-Aware Alerts**: Automatic VIX > 20 condition detection for high volatility scenarios
- **Broker Symbol Support**: Automatic 'c' suffix handling for broker compatibility (XAUUSDc, BTCUSDc)
- **Complex Condition Support**: Multi-factor alerts with price levels, volatility, and purpose detection
- **Real-Time Monitoring**: Automatic alert condition checking with Discord notifications
- **Purpose-Based Alerts**: First partials, entry signals, exit signals with context-aware descriptions
- **Enhanced Parameter Mapping**: Converts user intent to correct moneybot.add_alert parameters
- **Comma-Separated Number Support**: Handles price levels like "4,248" correctly
- **Context-Aware Symbol Detection**: Identifies symbols from price ranges and context

### 🎯 Professional Trading Strategies (NEW!)
- **London Breakout Strategy**: High-probability breakout setups for London session (07:00-10:00 UTC)
- **News Trading Strategy**: Event-driven trading for high-impact news (NFP, CPI, FOMC)
- **Strategy-Aware ChatGPT**: Automatically selects appropriate strategy based on market conditions
- **Institutional-Grade Approach**: Professional trading methodologies for retail traders
- **Complete Documentation**: Detailed strategy guides with entry/exit criteria and risk management

### 📈 Professional-Grade Logging (NEW!)
- **Desktop Agent (Phone Control)**:
  - ✅ Console logging (real-time)
  - ✅ File logging (`desktop_agent.log` - 10MB rotating, 5 backups)
  - ✅ Database logging (`journal.sqlite` - all trades, events, modifications)
  - ✅ V8 analytics logging (37 features → outcomes for ML)
  - ✅ Conversation logging (every ChatGPT interaction)
- **ChatGPT Bot**:
  - ✅ Automatic trade detection and logging
  - ✅ Closed trade detection (checks every 60s)
  - ✅ Discord notifications for all events
  - ✅ Background monitoring (positions, loss cuts, profit protection)

### 🗄️ Separate Database Architecture (NEW!)
- **`journal.sqlite`**: Trade logging (trades, events, equity snapshots) - ChatGPT Bot & Desktop Agent write
- **`advanced_analytics.sqlite`**: V8 analytics (37 features → outcomes for ML) - Desktop Agent writes
- **`conversations.sqlite`**: ChatGPT interactions and recommendations - Desktop Agent writes
- **`intelligent_exit_logger.db`**: Intelligent exit actions and modifications - System writes
- **`oco_tracker.db`**: OCO bracket trades tracking - System writes
- **`analysis_data.db`**: Analysis results and DTMS actions (Desktop Agent writes)
- **`system_logs.db`**: System logs and monitoring (API Server writes)
- **`shared_memory.json`**: Inter-process communication and coordination
- **Database Access Manager**: Enforces read/write permissions for each process
- **Concurrency Resolution**: Eliminates database locking issues with dedicated writers
- **Performance Optimization**: WAL mode and connection pooling for high-frequency operations
- **Full Audit Trail**: Every trade, modification, close, and decision logged across databases
- **⚠️ IMPORTANT: Tick Data NOT Saved**: Raw tick data is stored **ONLY in-memory buffers** (not in database) for real-time analysis. This prevents database bloat and ensures laptop-safe operation.

### ⚡ Dynamic Trade Management System (DTMS) (NEW!)
- **Multi-Timeframe Integration**: M1-M5-M15-H1-H4 structure analysis for trade management
- **CHOCH/BOS Detection**: Automatic structure shift detection with adaptive responses
- **Conflict Prevention**: Hierarchical control matrix prevents conflicting actions
- **3-Second Reevaluation**: Continuous monitoring with intelligent decision intervals
- **Automatic Stop Tightening**: Moves stops to breakeven based on structure changes
- **Hedge Management**: Intelligent hedging based on market structure shifts
- **Partial Profit Taking**: Scales out positions based on volatility and structure

### 🛡️ Enhanced Intelligent Exits System (NEW!)
- **Concurrent Operation**: Runs alongside DTMS with coordinated decision making
- **ATR + VIX + Volatility Gating**: Multi-factor volatility analysis for exit decisions
- **Dynamic Stop Adjustment**: Trailing stops based on volatility and trend strength
- **Partial Exit Logic**: Intelligent scaling out based on market conditions
- **Volatility-Aware Exits**: Different exit strategies for high/low volatility environments
- **Real-Time Monitoring**: Continuous position monitoring with sub-second updates
- **Sleep Recovery Engine**: Handles laptop sleep/wake cycles with data gap-filling
- **🎯 Adaptive Trade Type Classification (NEW!)**: Automatically classifies trades as SCALP or INTRADAY and applies appropriate exit parameters (25% breakeven for SCALP vs 30% for INTRADAY)
- **🐋 Automatic Whale Alert Protection (NEW!)**:
  - Detects large institutional orders ($500k+ for HIGH, $1M+ for CRITICAL) against positions
  - **Auto-tightens stop loss** when whales detected (0.15% for CRITICAL, 0.25% for HIGH)
  - **Auto-partial exit** to protect gains (50% for CRITICAL, 25% for HIGH)
  - Discord notifications with severity, whale side, and executed actions
  - BTCUSD-only (Binance order flow required)
- **⚠️ Automatic Liquidity Void Protection (NEW!)**:
  - Detects thin order book zones ahead of price movement
  - **Auto-full close** when price <0.05% from void (prevents slippage)
  - **Auto-partial exit** (50%) when price <0.08% from void
  - Discord warnings with void range, distance, and severity
  - Automatic execution prevents gap-through risks

### 📊 Institutional-Grade Analysis
- **3-Signal Gold System**: DXY + US10Y + VIX confluence (never skip API calls)
- **Multi-Timeframe Alignment**: H4 → H1 → M30 → M15 → M5 scoring (0-100)
- **Regime Detection**: TREND, RANGE, VOLATILE with adaptive strategies
- **37 Enrichment Fields**: Professional-grade institutional indicators
- **Economic Integration**: Real-time GDP, inflation, unemployment, CPI data
- **News Sentiment**: AI-powered sentiment analysis for major events
- **Order Flow & Liquidity Mapping**: Whale detection, order book imbalance, stop clusters, liquidity sweeps
- **🔄 Liquidity Sweep Reversal Engine (NEW!)**: Autonomous SMC trading system that detects liquidity sweeps (stop hunts) and executes reversal trades automatically using a three-layer confluence stack
- **Volatility Forecasting**: ATR momentum, BB width percentile, expansion/contraction signals
- **Enhanced Macro Bias**: Real yields, Fed expectations (2Y-10Y spread), NASDAQ correlation

---

## 🆕 Latest Updates (v8.6 - December 2025)

### 🎯 Adaptive Micro-Scalp Strategy System (NEW! - December 2-5, 2025) ⭐
- ✅ **Adaptive Strategy Selection**: Automatically switches between 3 distinct strategies based on market conditions
  - **VWAP Reversion Scalp**: Mean reversion when price deviates ≥2σ from VWAP
  - **Range Scalp**: Trading range edges (PDH/PDL or M15 bounds) with structure confirmation
  - **Balanced Zone Scalp**: Compression block mean reversion with EMA-VWAP equilibrium
  - **Edge-Based Fallback**: Generic strategy when no specific regime detected
- ✅ **Regime Detection System**: Intelligent market condition classification
  - **Confidence Scoring**: 0-100% confidence for each regime (VWAP: 70%, Range: 55%, Balanced: 65% thresholds)
  - **Anti-Flip-Flop Logic**: Prevents rapid switching between similar regimes (hysteresis)
  - **Regime Caching**: 3-bar rolling memory for stability
  - **Multi-Timeframe Analysis**: Uses M1, M5, M15 candles for detection
- ✅ **4-Layer Validation System**: Maintains existing validation structure with strategy-specific logic
  - **Pre-Trade Filters**: Volatility, spread, news blackout
  - **Location Filter**: Strategy-specific location requirements (VWAP deviation, range edges, compression zones)
  - **Candle Signals**: Primary + secondary signals (≥1 each required)
  - **Confluence Score**: Dynamic weighting per strategy (≥5 to trade, ≥7 for A+ setup)
- ✅ **Strategy-Specific Checkers**: Dedicated validation logic for each strategy
  - `VWAPReversionChecker`: Deviation ≥2σ, CHOCH at extreme, volume confirmation
  - `RangeScalpChecker`: Edge proximity, range respects ≥2, micro liquidity sweep
  - `BalancedZoneChecker`: Compression block, equal highs/lows, EMA-VWAP equilibrium
  - `EdgeBasedChecker`: Generic fallback with edge detection
- ✅ **Core Components**: All components implemented and tested
  - `infra/micro_scalp_regime_detector.py` - Regime detection engine
  - `infra/micro_scalp_strategy_router.py` - Strategy selection logic
  - `infra/micro_scalp_strategies/base_strategy_checker.py` - Base class with shared helpers
  - `infra/micro_scalp_strategies/vwap_reversion_checker.py` - VWAP reversion strategy
  - `infra/micro_scalp_strategies/range_scalp_checker.py` - Range scalp strategy
  - `infra/micro_scalp_strategies/balanced_zone_checker.py` - Balanced zone strategy
  - `infra/micro_scalp_strategies/edge_based_checker.py` - Edge-based fallback
  - `infra/micro_scalp_engine.py` - Updated with adaptive flow
  - `config/micro_scalp_config.json` - Regime detection configuration
- ✅ **Testing**: Comprehensive test suite (100+ tests)
  - Unit tests for all strategy checkers
  - Integration tests for engine flow
  - Edge case handling
  - Performance validation
  - Property-based testing
  - Concurrency testing
- ✅ **Web Dashboard**: Real-time monitoring interface
  - `http://localhost:8010/micro-scalp/view` - Live dashboard
  - Displays strategy, regime, confidence scores, condition breakdown
  - Symbol filtering and detailed regime detection reasons
  - Auto-refreshes every 10 seconds
- ✅ **Documentation**: 
  - `docs/Pending Updates - 02.12.25/ADAPTIVE_MICRO_SCALP_STRATEGY_PLAN.md` - Complete implementation plan
  - `docs/Pending Updates - 02.12.25/ADAPTIVE_MICRO_SCALP_IMPLEMENTATION_SUMMARY.md` - Implementation summary
  - `docs/MICRO_SCALP_REGIME_DETECTION_EXPLAINED.md` - Regime detection explanation
  - `docs/HOW_TO_RUN_MICRO_SCALP_SYSTEM.md` - Usage guide
- **Status**: ✅ **Fully Implemented & Tested** - Production Ready

### 🔄 Micro-Scalp Automation System (NEW! - December 1, 2025) ⭐
- ✅ **Continuous Monitoring**: Independent monitoring system operating separately from ChatGPT
  - **Fast Detection Cycle**: 5-second intervals (M1 timeframe)
  - **Immediate Execution**: No plan creation required - executes directly when conditions met
  - **Symbol-Specific Rate Limiting**: Prevents over-trading per symbol
  - **Session-Aware Filtering**: Only trades during configured sessions
  - **News Blackout Detection**: Avoids trading during high-impact news
- ✅ **Micro-Scalp Monitor**: Dedicated monitoring component
  - `infra/micro_scalp_monitor.py` - Continuous symbol scanning
  - `config/micro_scalp_automation.json` - Configuration (symbols, intervals, limits)
  - Integration with `MicroScalpEngine` for condition checking
  - Integration with `MicroScalpExecutionManager` for trade execution
- ✅ **Resource Efficient**: Minimal overhead
  - Uses existing streamer for M1 candle data
  - HTTP API endpoints for cross-process communication
  - Efficient data fetching with fallback to MT5
- ✅ **Web Dashboard**: Real-time status monitoring
  - Shows monitoring status, statistics, recent checks
  - Displays strategy, regime, confidence, condition breakdown
  - Symbol filtering and detailed check history
- ✅ **Documentation**: 
  - `docs/Pending Updates - 01.12.2025/MICRO_SCALP_AUTOMATION_IMPLEMENTATION_PLAN.md` - Complete plan
  - `docs/HOW_TO_RUN_MICRO_SCALP_SYSTEM.md` - Usage guide
- **Status**: ✅ **Fully Implemented** - Production Ready

### 🌐 Streamer API Endpoints (NEW! - December 2, 2025)
- ✅ **HTTP API Access**: Exposes Multi-Timeframe Streamer data via REST endpoints
  - `GET /streamer/candles/{symbol}/{timeframe}` - Get candlestick data (limit support)
  - `GET /streamer/status` - Streamer status and metrics
  - `GET /streamer/available` - List all symbols and timeframes being streamed
  - `GET /streamer/health` - Health check with buffer status and last update times
- ✅ **Cross-Process Communication**: Enables micro-scalp monitor to access streamer data
  - Micro-scalp monitor (port 8010) can fetch data from streamer (port 8000)
  - Fallback to direct streamer access if in same process
  - Final fallback to direct MT5 calls
- ✅ **Performance**: Minimal resource impact
  - CPU: <0.1% overhead
  - RAM: +0.1-0.15 MB
  - SSD: +50-100 KB/day for logs
- ✅ **Documentation**: 
  - `docs/Pending Updates - 02.12.25/STREAMER_API_ENDPOINTS_PLAN.md` - Implementation plan
  - `docs/Pending Updates - 02.12.25/STREAMER_API_RESOURCE_IMPACT.md` - Resource analysis
- **Status**: ✅ **Fully Implemented** - Production Ready

### 🔧 Auto-Execution System Improvements (NEW! - December 5, 2025)
- ✅ **Monitoring Status Verification**: System status checking and diagnostics
  - `/auto-execution/system-status` endpoint shows monitoring status
  - Web dashboard displays active/inactive status with green/red indicators
  - Automatic startup on server initialization
- ✅ **Plan Condition Fixes**: Enhanced condition handling
  - Fixed missing `timeframe` field in range scalp plans
  - Corrected `min_confluence` mapping to `range_scalp_confluence` for range scalping
  - Enhanced condition validation and display
- ✅ **WebSocket Reconnection**: Improved desktop agent reconnection logic
  - Graceful handling of server restarts (code 1012)
  - Differentiated error handling for various close codes
  - Faster reconnection (3 seconds for expected restarts)
  - Cleaner logs (INFO level for expected events)
- ✅ **Database Plan Management**: Automatic plan status updates
  - Expired plans automatically marked as "expired"
  - Executed plans properly tracked
  - Cancelled plans handled correctly
- ✅ **Documentation**: 
  - `CHATGPT_PLANS_VERIFICATION_SUMMARY.md` - Plan verification guide
  - `MONITORING_STATUS_EXPLANATION.md` - Monitoring status explanation
  - `WEBSOCKET_RECONNECTION_FIX.md` - WebSocket improvements
- **Status**: ✅ **Fully Implemented** - Production Ready

## 🆕 Previous Updates (v8.5 - November 2025)

### 🛡️ Universal Dynamic SL/TP Adjustment System (NEW! - November 25, 2025) ⭐
- ✅ **Strategy-Aware Trailing**: Different trailing methods per strategy type (breakout, trend continuation, sweep reversal, OB rejection, mean-reversion)
- ✅ **Symbol-Specific Behavior**: BTC, XAU, EURUSD, US30 have different trailing requirements
- ✅ **Session-Aware Adjustments**: Asia, London, NY, London-NY Overlap, Late NY require different SL/TP behavior
- ✅ **Zero Conflicts**: Explicit ownership prevents multiple managers modifying same trade
- ✅ **Anti-Thrash Safeguards**: Minimum distance (0.1R) + cooldown (30s) prevent MT5 spam
- ✅ **Frozen Rule Snapshots**: Resolved rules at trade open prevent config sprawl
- ✅ **R-Space Logic**: Primary decision-making based on R-multiples (risk units) for consistency
- ✅ **Mid-Trade Volatility Override**: Temporarily adjusts trailing distance (20% wider) if ATR spikes significantly
- ✅ **Dynamic Partial Profit Scaling**: Adjusts partial profit triggers (20% earlier) if volatility expands
- ✅ **Persistence & Recovery**: Database persistence with crash recovery and strategy inference
- ✅ **Rich Logging**: Standardized log format for all SL modifications with full context
- ✅ **Integration**: Works alongside DTMS and Intelligent Exit Manager with conflict prevention
- ✅ **ChatGPT Integration**: `create_auto_trade_plan` tool accepts `strategy_type` parameter
- ✅ **Comprehensive Testing**: 122 tests passing (0 failures, 0 errors)
- **Files**: 
  - `infra/universal_sl_tp_manager.py` - Main orchestrator (1,843 lines)
  - `tests/test_universal_sl_tp_phase1_2.py` - Phase 1 & 2 tests
  - `tests/test_universal_sl_tp_phase3.py` - Phase 3 tests
  - `tests/test_universal_sl_tp_phase4_safeguards.py` - Phase 4 tests
  - `tests/test_universal_sl_tp_phase5_integration.py` - Phase 5 tests
  - `tests/test_universal_sl_tp_phase6_monitoring.py` - Phase 6 tests
  - `tests/test_universal_sl_tp_phase7_persistence.py` - Phase 7 tests
- **Documentation**: 
  - `docs/Pending Updates - 23.11.25/UNIVERSAL_DYNAMIC_SL_TP_ADJUSTMENT_PLAN.md` - Complete implementation plan
  - `docs/Pending Updates - 23.11.25/UNIVERSAL_SL_TP_PLAN_FINAL_REVIEW.md` - Final review
- **Status**: ✅ **Fully Implemented & Tested** - Production Ready

### 📊 BTC Order Flow Metrics Integration (NEW! - November 22, 2025) ⭐
- ✅ **Comprehensive BTC Order Flow Analysis**: Advanced order flow metrics for BTCUSD trading
  - **Delta Volume**: Real-time buy/sell volume imbalance (net delta, dominant side)
  - **CVD (Cumulative Volume Delta)**: Cumulative volume delta with slope calculation
  - **CVD Divergence**: Price vs CVD divergence detection (bullish/bearish absorption)
  - **Absorption Zones**: Large buyer/seller defense levels with strength scoring
  - **Buy/Sell Pressure**: Pressure ratio calculation (buy volume / sell volume)
- ✅ **Automatic Integration**: BTC order flow metrics **automatically included** in `moneybot.analyse_symbol_full` for BTCUSD
  - No additional tool calls needed - metrics appear in analysis summary
  - Displayed in "💧 LIQUIDITY & ORDER FLOW" section
  - Real-time data from Binance WebSocket feed
- ✅ **Standalone Tool**: `moneybot.btc_order_flow_metrics` for dedicated order flow queries
  - Use when user explicitly requests only order flow metrics
  - Returns comprehensive metrics with interpretation
- ✅ **ChatGPT Integration**: Full integration with analysis, recommendations, and auto-execution plans
  - ChatGPT checks BTC order flow metrics before creating BTC auto-execution plans
  - Order flow signals validate entry timing and direction
  - Knowledge documents updated with usage guidance
- ✅ **Resource Efficient**: Uses existing Binance Order Flow Service (no additional overhead)
- ✅ **Enhanced Diagnostics**: Detailed error messages and troubleshooting guidance
- **Files**: 
  - `infra/btc_order_flow_metrics.py` - Core metrics calculation
  - `desktop_agent.py` - Integration into analysis pipeline
  - `openai.yaml` - Tool definition and usage guidance
- **Documentation**: 
  - `docs/BTC_ORDER_FLOW_METRICS_IMPLEMENTATION.md` - Implementation details
  - `docs/BTC_ORDER_FLOW_METRICS_QUICK_START.md` - Quick start guide
  - `docs/Pending Updates - 19.11.25/BTC_ORDER_FLOW_INTEGRATION_SUMMARY.md` - Integration summary
  - `docs/Pending Updates - 19.11.25/BTC_ORDER_FLOW_TROUBLESHOOTING.md` - Troubleshooting guide
- **Status**: ✅ **Fully Integrated** - Production Ready

### 🔄 Weekend-Only BTC Streaming (NEW! - November 22, 2025)
- ✅ **Resource Conservation**: Multi-Timeframe Streamer only streams BTC on weekends
  - **Weekend Detection**: Automatically detects Saturday/Sunday
  - **BTC-Only Mode**: Streams only BTCUSDc when forex markets are closed
  - **Weekday Mode**: Streams all configured symbols (BTCUSDc, XAUUSDc, etc.) during weekdays
  - **Automatic Switching**: No manual configuration needed
- ✅ **Integration Points**: Applied to all streamer initialization locations
  - `app/main_api.py` - Main API startup
  - `test_range_scalping_live.py` - Live integration tests
  - `test_range_scalp_api.py` - API tests
- ✅ **Benefits**: 
  - Reduced CPU/RAM/SSD usage during weekends
  - Forex symbols not streamed when markets are closed
  - BTC continues 24/7 streaming (crypto markets never close)
- **Files**: `app/main_api.py`, `test_range_scalping_live.py`, `test_range_scalp_api.py`
- **Status**: ✅ **Implemented** - Production Ready

### 🛡️ SL/TP Enforcement & Critical Discord Alerts (NEW! - November 20, 2025)
- ✅ **Post-Execution Verification**: System verifies SL/TP were actually set after trade execution
  - Checks `final_sl` and `final_tp` from execution result
  - Reads actual MT5 position to confirm levels
  - Logs detailed verification results
- ✅ **SL/TP Recalculation**: Automatic recalculation if original SL/TP invalid
  - Stores original SL/TP and entry price
  - Recalculates based on actual execution price
  - Maintains original distance ratios
  - Applies to both BUY and SELL orders
- ✅ **Critical Discord Alerts**: Sends immediate Discord notification if SL/TP missing
  - Alert includes: Plan ID, ticket, symbol, direction, entry price, missing level
  - Sent via `DiscordNotifier.send_error_alert()`
  - Critical priority for immediate attention
- ✅ **Enhanced Logging**: Comprehensive logging for troubleshooting
  - Logs original vs recalculated SL/TP
  - Logs execution price vs entry price
  - Logs distance calculations
  - Logs verification results
- **Files**: 
  - `infra/mt5_service.py` - SL/TP recalculation logic
  - `auto_execution_system.py` - Post-execution verification and Discord alerts
- **Status**: ✅ **Implemented** - Production Ready

### 🔧 Update Auto Plan Tool (NEW! - November 22, 2025)
- ✅ **New Tool**: `moneybot.update_auto_plan` - Update existing auto-execution plans
  - **Mandatory Parameter**: `plan_id` (required - use `moneybot.get_auto_plan_status` to find IDs)
  - **Updatable Fields**: entry_price, stop_loss, take_profit, volume, conditions, expires_hours, notes
  - **Restriction**: Only pending plans can be updated (executed/cancelled plans are immutable)
- ✅ **Condition Merging**: Smart condition merging when updating plans
  - New conditions merged with existing conditions
  - Validation and fixing applied after merge
  - Preserves existing conditions not being updated
- ✅ **Full Integration**: Complete integration across all layers
  - `auto_execution_system.py` - Core `update_plan()` method
  - `chatgpt_auto_execution_integration.py` - Integration layer
  - `chatgpt_auto_execution_tools.py` - ChatGPT tool wrapper
  - `app/auto_execution_api.py` - API endpoint (`POST /auto-execution/update-plan/{plan_id}`)
  - `openai.yaml` - Tool definition with mandatory `plan_id` guidance
- ✅ **Knowledge Documents**: Updated with usage examples and workflows
  - `AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md` - Tool documentation
  - `AUTO_EXECUTION_CHATGPT_INSTRUCTIONS.md` - Usage instructions with scenarios
  - `ChatGPT_Knowledge_Document.md` - Main knowledge document
- **Files**: `auto_execution_system.py`, `chatgpt_auto_execution_integration.py`, `chatgpt_auto_execution_tools.py`, `app/auto_execution_api.py`, `openai.yaml`
- **Status**: ✅ **Fully Implemented** - Production Ready

### 📋 Enhanced Plan Conditions (NEW! - November 22, 2025)
- ✅ **M1 Validation & Volatility Filters**: Recommended conditions for all auto-execution plans
  - **M1 Validation**: `m1_choch_bos_combo` - M1 CHOCH/BOS confirmation
  - **Volatility Filters**: `min_volatility`, `bb_width_threshold` - Volatility-based entry filters
  - **Price Proximity**: `price_near`, `tolerance` - Entry zone proximity checks
- ✅ **Condition Recommendations**: ChatGPT knowledge updated with recommended conditions
  - Strategy-to-condition mapping guide
  - Common mistakes and fixes
  - Recommended enhancements per strategy type
- ✅ **Web UI Enhancements**: Auto-execution view improvements
  - Detailed condition display with required vs recommended indicators
  - Strategy-specific condition checking
  - Improved sorting and filtering
- ✅ **Plan Review & Fixes**: Comprehensive review of existing plans
  - Fixed missing conditions in problematic plans
  - Updated plan validation logic
  - Enhanced condition checking accuracy
- **Files**: 
  - `app/auto_execution_api.py` - Condition merging in plan creation
  - `chatgpt_auto_execution_integration.py` - Condition validation
  - `app/main_api.py` - Web UI enhancements
  - `docs/Pending Updates - 19.11.25/PLAN_ENHANCEMENT_RECOMMENDATIONS.md` - Recommendations guide
- **Status**: ✅ **Implemented** - Production Ready

### 📊 Shared Data Service Planning (NEW! - November 19-20, 2025)
- ✅ **Comprehensive Implementation Plan**: Detailed plan for shared data service architecture
  - **Purpose**: Eliminate duplicate data fetches across alert and auto-execution systems
  - **Architecture**: Singleton pattern with fallback logic
  - **Integration**: M1RefreshManager, Desktop Agent, Alert Monitor integration
  - **Performance Targets**: <50ms cache access, <200ms fresh fetch, 30s refresh intervals
- ✅ **Review & Refinement**: Multiple review cycles with comprehensive fixes
  - Singleton pattern implementation
  - Fallback logic to direct MT5 calls
  - Thread safety and error handling
  - Cache synchronization and health checks
- ✅ **Documentation**: Complete implementation guide with all requirements
  - `docs/Pending Updates - 19.11.25/SHARED_DATA_SERVICE_IMPLEMENTATION_PLAN.md` - Full plan
  - `docs/Pending Updates - 19.11.25/SHARED_DATA_SERVICE_PLAN_REVIEW_V2.md` - Review issues
  - `docs/Pending Updates - 19.11.25/SHARED_DATA_SERVICE_PLAN_REVIEW_SUMMARY.md` - Review summary
- **Status**: 📋 **Planning Complete** - Ready for implementation

## 🆕 Previous Updates (v8.2 - November 2025)

### 🎯 Adaptive Intelligent Exit System - Phase 1 MVP (NEW!)
- ✅ **Trade Type Classification** (`infra/trade_type_classifier.py`): Automatically classifies trades as SCALP or INTRADAY at entry
  - 3-factor classifier: Stop size vs ATR, comment keywords, session strategy
  - SCALP mode: Fast profit capture (25% breakeven, 40% partial, 70% close)
  - INTRADAY mode: Profit maximization (30% breakeven, 60% partial, 50% close)
  - Classification confidence scoring (HIGH/MEDIUM/LOW)
  - Manual override flags in trade comments (`FORCE_SCALP`, `FORCE_INTRADAY`)
- ✅ **Metrics Collection** (`infra/classification_metrics.py`): Tracks classification performance and accuracy
  - Daily summaries at 17:00 UTC (Discord notifications)
  - Weekly summaries on Sundays at 17:00 UTC (Discord notifications)
  - Log summaries after every 100 trades
  - Classification confidence distribution tracking
- ✅ **Integration**: Seamlessly integrated with `enableIntelligentExits()` tool
  - Automatic parameter selection based on trade type
  - Discord notifications include trade type, confidence, and reasoning
  - Feature flag: `ENABLE_TRADE_TYPE_CLASSIFICATION` (default: enabled)
- ✅ **Configuration**: `config.py` settings for metrics and reporting
- ✅ **Documentation**: `docs/AIES_PHASE1_MVP_PLAN.md` - Complete implementation guide
- ✅ **Status**: Fully implemented and tested. Solves the problem of scalp trades missing profit-taking opportunities.

### 🎯 Range Scalping Auto-Execution (NEW!)
- ✅ **Auto-Execution Tool** (`moneybot.create_range_scalp_plan`): Creates auto-executing range scalping plans
  - Monitors confluence score (must reach >= 80 by default)
  - Requires M15 structure confirmation (CHOCH/BOS)
  - Waits for price near entry zone (auto-calculated tolerance)
  - Automatically executes when all conditions are met
- ✅ **Integration**: Full integration across auto-execution system
  - `chatgpt_auto_execution_integration.py`: Creates range scalp plans with special conditions
  - `auto_execution_system.py`: Monitors confluence, structure, and price proximity
  - `chatgpt_auto_execution_tools.py`: ChatGPT tool wrapper
  - `app/auto_execution_api.py`: API endpoint for plan creation
  - `main_api.py`: FastAPI endpoint registration
- ✅ **Parameters**: Configurable min_confluence (default: 80), price_tolerance (auto-calculated), expires_hours (default: 8)
- ✅ **Documentation**: Updated knowledge documents with usage examples and workflows
- ✅ **Status**: Fully implemented. ChatGPT can now create auto-executing range scalp plans.

### 🎯 Range Scalping System (Phase 1 Complete)
- ✅ **Range Boundary Detector** (`infra/range_boundary_detector.py`): Complete range detection system for scalping strategies
  - Session/daily/dynamic range detection using swing-based analysis
  - Critical gap calculation (0.15× range zones)
  - Range expansion/contraction detection (ATR + Bollinger Band width)
  - Range invalidation checks (2-candle close outside, VWAP slope, BB expansion, M15 BOS)
  - Imbalanced consolidation detection (false range identification)
  - Nested range hierarchy (H1/M15/M5 alignment)
- ✅ **Risk Filters** (`infra/range_scalping_risk_filters.py`): Comprehensive pre-trade risk mitigation
  - Data quality validation (candle freshness, VWAP recency, Binance order flow, news calendar)
  - Weighted 3-confluence scoring (Structure 40pts + Location 35pts + Confirmation 25pts = 80+ threshold)
  - Effective ATR calculation (max(atr_5m, bb_width × price_mid / 2))
  - VWAP momentum (% of ATR per bar method)
  - False range detection (volume, VWAP slope, candle expansion, CVD divergence)
  - Session filters with broker timezone offset support
  - Trade activity criteria (volume, price deviation, cooldown, news)
  - Multi-timeframe nested range alignment
  - Adaptive anchor refresh (PDH/PDL refresh logic)
- ✅ **Configuration System**: Complete config management with validation and versioning
  - `config/range_scalping_config.json`: Main configuration (position sizing, entry filters, risk mitigation, performance optimization)
  - `config/range_scalping_rr_config.json`: R:R targets per strategy with session adjustments
  - `config/range_scalping_config_loader.py`: Config loader with SHA hash versioning
- ✅ **Documentation**: Comprehensive master plan (`docs/RANGE_SCALPING_MASTER_PLAN_V2.md`)
- **Position Sizing**: Fixed 0.01 lots for all range scalps (no risk-based calculation)
- **Status**: Phase 1 (Core Infrastructure) complete. Phase 2 (Early Exit System) next.
- **Resource Usage**: Minimal impact (~50 MB RAM, <1% CPU, negligible SSD) - see `docs/RANGE_SCALPING_RESOURCE_USAGE.md`

### 📊 M1 Microstructure Integration (NEW! - November 2025) ⭐
- ✅ **M1 Data Fetcher Module**: Efficient M1 candlestick data fetching with rolling buffers (RAM-only, ~50 KB per symbol)
- ✅ **M1 Microstructure Analyzer**: Institutional-grade analysis with CHOCH/BOS detection, liquidity zones, volatility state, rejection wicks, order blocks, momentum quality
- ✅ **Session-Linked Volatility Engine**: Dynamic session-aware parameter adjustment (min_confluence, ATR multiplier, VWAP tolerance)
- ✅ **Asset Personality Model**: Symbol-specific volatility "DNA" (VWAP σ Tolerance, ATR Multiplier, Core Sessions, Preferred Strategy)
- ✅ **Dynamic Strategy Selector**: Automated trade-type classification (BREAKOUT, RANGE_SCALP, MEAN_REVERSION, TREND_CONTINUATION)
- ✅ **Dynamic Threshold Tuning**: Real-time adaptive confluence thresholds based on symbol, session, and ATR ratio
- ✅ **Real-Time Signal Learning**: Adaptive calibration system with performance metrics and optimal parameter calculation
- ✅ **Auto-Execution Integration**: Enhanced auto-execution with 12 M1 condition types and dynamic threshold checking
- ✅ **M1 Refresh Manager**: Periodic data refresh system (every 30 seconds) with weekend trading handling
- ✅ **Crash Recovery & Persistence**: CSV snapshot system with zstandard compression and startup recovery
- ✅ **Resource Monitoring**: Performance metrics tracking (CPU, memory, refresh latency, success rates)
- ✅ **Configuration System**: Centralized configuration for all M1-related settings
- ✅ **ChatGPT Integration**: Full integration with `analyse_symbol_full` and dedicated `get_m1_microstructure` tool
- ✅ **Comprehensive Testing**: 100+ tests covering unit, integration, performance, accuracy, edge cases, and end-to-end scenarios
- **Status**: ✅ **Phases 1-4 Complete, Phase 5 Testing Complete** - Production Ready
- **Files**: `infra/m1_*.py` (10 modules), `config/m1_*.json` (configuration files), `desktop_agent.py`, `auto_execution_system.py`
- **Documentation**: `docs/Pending Updates - 19.11.25/M1_MICROSTRUCTURE_INTEGRATION_PLAN.md`

### ⚡ Volatility Regime Detection & Strategy Selection (NEW! - November 2025)
- ✅ **Automatic Regime Detection**: Classifies market conditions as STABLE, TRANSITIONAL, or VOLATILE
  - **Multi-Timeframe Analysis**: Weighted analysis across M5 (20%), M15 (30%), H1 (50%)
  - **Detection Metrics**: ATR ratio (ATR(14)/ATR(50) > 1.3), Bollinger Band width (>1.8× median), ADX (>28), volume spikes (>150%), daily return stdev (>1.5× baseline)
  - **Confidence Scoring**: 0-100% confidence for each regime classification (≥70% = high confidence)
  - **Persistence Filters**: Requires ≥3 candles confirmation to prevent false signals
  - **Regime Inertia**: Prevents rapid flips between regimes (minimum hold duration)
  - **Auto-Cooldown**: Ignores fast reversals (<3 candles) to prevent false regime changes
  - **Event Logging**: Logs all regime shifts to `data/volatility_regime_events.sqlite` for analytics
- ✅ **Volatility-Aware Strategy Selection**: Automatically selects best strategy when VOLATILE regime detected
  - **4 Strategies**: Breakout-Continuation, Volatility Reversion Scalp, Post-News Reaction Trade, Inside Bar Volatility Trap
  - **Scoring System**: 0-100 score for each strategy based on market phase, structure quality, volume confirmation, session alignment, news context
  - **Selection Threshold**: Strategy must score ≥75 to be recommended
  - **WAIT Reasons**: Explicit reason codes when no suitable strategy found (SCORE_SHORTFALL, REGIME_CONFIDENCE_LOW)
  - **Trade Levels**: Automatically calculates Entry/SL/TP based on selected strategy and volatility regime
- ✅ **Volatility-Adjusted Risk Management**: Automatic risk parameter adjustments for volatile markets
  - **Position Sizing**: Reduced to 0.5% risk (from 1.0%) in VOLATILE regimes
  - **Stop Loss**: Widened to 1.5× ATR (from 1.0×) to account for increased volatility
  - **Take Profit**: Expanded to 3.0× ATR (from 2.0×) to capture larger moves
  - **Circuit Breakers**: Daily loss limits (2.0% max), trade cooldowns (5 min), spread gates (2.0× normal), slippage budgets (0.5% max)
- ✅ **ChatGPT Integration**: Fully integrated into `moneybot.analyse_symbol_full` - no additional user input required
  - **Automatic Detection**: Regime detected automatically when user requests analysis (e.g., "analyse BTCUSD")
  - **Prominent Display**: Regime status shown at top of every analysis with confidence, ATR ratio, phase, and risk level
  - **Strategy Transparency**: Explains why strategy selected (score, reasoning) or why WAIT recommended (reason codes)
  - **Risk Warnings**: Highlights position size reduction and wider stops in volatile regimes
  - **Confirmation Prompts**: Requests explicit confirmation before executing trades in VOLATILE regimes
  - **Multi-Symbol Comparison**: Rank symbols by volatility and opportunity when analyzing multiple symbols
- ✅ **Monitoring Dashboard**: Real-time volatility regime monitoring interface
  - **Web Interface**: `http://localhost:8010/volatility-regime/monitor` - Live dashboard showing regime status for all symbols
  - **API Endpoints**: `/volatility-regime/status/{symbol}`, `/volatility-regime/events/{symbol}` - Programmatic access
  - **Auto-Refresh**: Dashboard updates every 30 seconds with latest regime data
- **Files**: 
  - `infra/volatility_regime_detector.py` - Core regime detection logic
  - `infra/volatility_strategy_selector.py` - Strategy scoring and selection
  - `infra/volatility_risk_manager.py` - Risk parameter adjustments
  - `config/volatility_regime_config.py` - Configuration parameters
  - `desktop_agent.py` - Integration into analysis flow
  - `main_api.py` - Monitoring dashboard endpoints and API
- **Documentation**: 
  - `docs/VOLATILE_REGIME_TRADING_PLAN.md` - Complete implementation guide (Phases 1-3 complete)
  - `docs/ChatGPT Knowledge Documents/ChatGPT_Knowledge_Volatility_Regime_Trading.md` - ⭐ NEW: ChatGPT knowledge document
  - `docs/PHASE1_COMPLETION_SUMMARY.md`, `docs/PHASE2_COMPLETION_SUMMARY.md`, `docs/PHASE3_COMPLETION_SUMMARY.md` - Phase completion reports
- **Status**: ✅ **Phases 1, 2 & 3 Complete** - Production Ready

### 🔧 Critical System Fixes (October 2025)
- ✅ **Stop Loss & Take Profit Validation**: All market orders now require valid SL/TP to prevent unprotected trades
- ✅ **Auto-Execution System Overhaul**: Refactored to use `MT5Service` for robust error handling and structured responses
- ✅ **Background Task Reliability**: Fixed async execution issues in `chatgpt_bot.py` scheduler
- ✅ **Intelligent Exits Initialization**: Properly initializes Intelligent Exit Manager in main() function
- ✅ **Symbol Normalization**: Enhanced case-preserving logic for broker symbol compatibility
- ✅ **DTMS Auto-Registration**: All trade executions automatically register to DTMS for monitoring

## 🆕 Previous Updates (v8.0 - October 2025)

### 🎯 Advanced Liquidity & Order Flow Analysis (NEW!)
- ✅ **Stop Cluster Detection**: Wick-based liquidity zone detection (clusters of 3+ wicks > 0.5 ATR)
- ✅ **Enhanced Sweep Detection**: Improved liquidity grab identification with post-sweep validation
- ✅ **Order Flow Signals**: Whale activity, order book imbalance, liquidity voids (via Binance integration)
- ✅ **Equal Highs/Lows**: Resting liquidity detection with stop hunt warnings
- ✅ **HVN/LVN Analysis**: Volume profile proxy for price magnets and vacuum zones
- ✅ **Real-Time Integration**: All liquidity features integrated into ChatGPT analysis output
- ✅ **Distance Normalization**: All liquidity zones measured in ATR units for scale-independence
- ✅ **🐋 Automatic Whale Alert Execution (NEW!)**: Auto-tightens SL and takes partial exits when large orders detected (BTCUSD-only via Binance order flow)
- ✅ **⚠️ Automatic Liquidity Void Protection (NEW!)**: Auto-closes positions (full or partial) when approaching thin order book zones to prevent slippage

### 📊 Volatility Forecasting & Regime Awareness (NEW!)
- ✅ **ATR Momentum**: Rate of change detection (EXPANDING/CONTRACTING/STABLE)
- ✅ **Bollinger Band Width Percentile**: Extreme contraction/expansion identification
- ✅ **Session Volatility Curves** (Phase 3.3): Historical ATR patterns by trading session (Asia/London/NY)
  - Current session vs historical average (e.g., 1.3x = 30% higher than normal)
  - Percentile ranking (80th+ = high volatility, 20th- = low volatility)
  - Peak volatility session identification (helps time entries)
  - Session-specific stop adjustment guidance
- ✅ **Volatility Signal**: Real-time regime detection for stop placement and risk management
- ✅ **Range Probability**: Forecasts likelihood of breakouts vs mean reversion
- ✅ **Multi-Timeframe Volatility**: Volatility analysis across M5, M15, H1 timeframes
- ✅ **ChatGPT Integration**: Volatility signals with session curves displayed prominently in analysis output

### 🌍 Enhanced Macro Bias with Fed Expectations (NEW!)
- ✅ **2Y-10Y Treasury Spread**: Forward-looking Fed policy expectations (inverted/steep/flat)
- ✅ **Fed Expectations Impact**:
  - Inverted spread (< -0.2%): Recession signal → Bullish Gold (+0.15), USD weakens (+0.2 EUR/GBP)
  - Steep spread (> +0.5%): Growth expectations → Bearish Gold (-0.15), USD strengthens (-0.2 EUR/GBP)
- ✅ **Real Yield Calculation**: Nominal 10Y yield - 10Y breakeven inflation (Gold-specific)
- ✅ **FRED API Integration**: Free economic data from Federal Reserve (requires API key)
- ✅ **Intelligent Caching**: 60-minute cache for daily data (reduces API calls)
- ✅ **Multi-Asset Support**: Gold, USD pairs with Fed expectations; BTC with NASDAQ correlation
- ✅ **ChatGPT Display**: Fed expectations prominently shown in macro bias summary

### 🚀 Production Deployment Ready (NEW!)
- ✅ **Production Readiness Validation**: 87% production readiness score with comprehensive validation
- ✅ **Staged Rollout System**: Complete staged rollout framework with monitoring and rollback
- ✅ **Production Environment Setup**: Database security, monitoring, backup, and disaster recovery
- ✅ **Performance Validation**: Production load testing, test validation, and security hardening
- ✅ **System Integration Testing**: End-to-end testing with real market data and high volatility stress testing
- ✅ **Monitoring & Observability**: Production monitoring dashboard, alerting, log aggregation, and performance metrics
- ✅ **Documentation & Training**: Complete user manuals, troubleshooting guides, operational runbooks, and training materials
- ✅ **Automated Deployment**: Production deployment scripts with comprehensive monitoring and validation
- ✅ **Production Monitoring Dashboard**: Real-time system metrics, trading performance, component health monitoring
- ✅ **Rollback Procedures**: Comprehensive rollback management with automated triggers and verification
- ✅ **Stakeholder Sign-off System**: Multi-stakeholder approval process with escalation procedures
- ✅ **Deployment Automation**: Automated deployment management with pre/post-deployment validation

### 🚀 Real-Time Intelligence
- ✅ **Binance 1-Second Streaming**: WebSocket connection for microsecond-precision data
- ✅ **Order Flow Analysis**: Whale detection, order book imbalance, tape reading
- ✅ **37 Enrichment Fields**: Institutional-grade market microstructure indicators
- ✅ **Automatic Integration**: All analyses enhanced with Binance + Order Flow
- ✅ **Safe Retention System**: Intelligent database management preventing bloat while maintaining stability
- ✅ **Binance Disconnect Fix**: Resolved cross-thread MT5 access issues causing WebSocket disconnects
- ✅ **Multi-Timeframe Streamer**: Efficient candlestick streaming (M1, M5, M15, M30, H1, H4) with incremental fetching (lightweight, active)
- ✅ **Unified Tick Pipeline**: DISABLED for resource conservation (Binance WebSocket streams too heavy for personal hardware)
- ✅ **DTMS & Intelligent Exits**: Multi-timeframe trade management with conflict prevention
- ✅ **FRED Economic Data**: Real-time Fed Funds Rate, 2Y/10Y yields, breakeven inflation, CPI (FREE API)

### 🎯 Multi-Timeframe Framework (NEW!)
- ✅ **H4→H1→M30→M15→M5→M1 Analysis**: Hierarchical market structure analysis
- ✅ **Smart Money Concepts**: CHOCH, BOS, Order Blocks, Liquidity analysis
- ✅ **M1 Confirmation Filters**: VWAP reclaim/loss, volume delta spike, micro BOS, ATR ratio, spread filter
- ✅ **Hot-Path Architecture**: Memory-first approach with ring buffers and async DB writes
- ✅ **Performance Optimization**: <200ms latency, 100% test coverage, comprehensive validation

### 🛡️ Shadow Mode & Decision Tracing (NEW!)
- ✅ **Shadow Mode Toggles**: Run DTMS alongside Intelligent Exits for comparison
- ✅ **Decision Trace Logging**: Full feature vector hashes for error analysis
- ✅ **Per-Symbol Configuration**: Hot-reloadable JSON configurations for all symbols

### 🧪 Advanced Validation Systems (NEW!)
- ✅ **13 Comprehensive Validation Systems**: Structure detection, latency, database performance, VWAP accuracy
- ✅ **Delta Spike Detection**: >90% accuracy validation for volume delta analysis
- ✅ **False Signal Reduction**: >80% effectiveness in filtering noise from trading signals
- ✅ **Binance Order Book Analysis**: >95% accuracy for institutional-grade order flow analysis
- ✅ **Large Order Detection**: >85% precision for whale detection and market impact analysis
- ✅ **Exit Precision Validation**: >80% accuracy for trade exit signal generation
- ✅ **Risk-Reward Improvement**: >1:3 R:R ratio validation with comprehensive trade analysis
- ✅ **Drawdown Control**: Validates risk management within predefined limits
- ✅ **Database Operations**: Ensures all trade operations are properly handled
- ✅ **Win Rate Validation**: ≥80% win rate with R:R ≥1:3 validation
- ✅ **Sustained Latency**: Continuous monitoring of <200ms performance
- ✅ **SLOs Validation**: Production readiness with Service Level Objectives
- ✅ **Database Optimization**: Query performance and index efficiency validation
- ✅ **Structure Detection Validation**: >75% accuracy for market structure detection (BOS/CHOCH)
- ✅ **M1 Filter Validation**: >60% pass rate for M1 confirmation filters
- ✅ **Hot-Path Architecture Validation**: Ensures no blocking on database operations
- ✅ **Binance Integration Validation**: <10% data loss validation for Binance streaming
- ✅ **Shadow Mode Validation**: Shadow mode readiness and DTMS comparison validation
- ✅ **VWAP Accuracy Validation**: ±0.1σ tolerance for VWAP calculations

### 📊 Paper Trading & Backtesting (NEW!)
- ✅ **12-Month Backtesting**: Comprehensive historical validation for EURUSDc, GBPUSDc, XAUUSDc, BTCUSDc
- ✅ **Paper Trading System**: 4-6 weeks live data simulation with full logging
- ✅ **Staged Activation**: Gradual position size increase based on performance metrics
- ✅ **Symbol Optimization**: Automatic parameter tuning based on win rate, profit factor, Sharpe ratio
- ✅ **Performance Tracking**: Real-time metrics and improvement recommendations

### 🔧 System Integration & Testing (NEW!)
- ✅ **100% Test Coverage**: 194+ comprehensive tests with 100% pass rate
- ✅ **E2E Testing**: Complete end-to-end validation for all components
- ✅ **Integration Testing**: Cross-component functionality validation
- ✅ **Performance Testing**: Latency, memory, and CPU optimization validation
- ✅ **Chaos Testing**: System resilience under failure conditions
- ✅ **Property Testing**: Invariant validation for critical algorithms
- ✅ **HDR Histograms**: High-precision latency and performance metrics
- ✅ **Modern FastAPI**: Updated to use lifespan handlers instead of deprecated events
- ✅ **Threshold Wiring**: Production-ready configurations for BTCUSDc, XAUUSDc, EURUSDc, GBPUSDc, USDJPYc
- ✅ **Comprehensive Testing**: 194 tests passing with 100% success rate
- ✅ **Validation System Testing**: 13 comprehensive validation systems with 100% pass rate
- ✅ **Shadow Mode Testing**: 14 tests for shadow mode toggles and decision trace logging
- ✅ **Symbol Configuration Testing**: 17 tests for configuration loading and hot-reload
- ✅ **Threshold Wiring Testing**: 12 tests for symbol-specific configurations
- ✅ **Property Testing**: 16 tests for VWAP, ATR, BOS, and data structure validation
- ✅ **Queue Monitoring Testing**: 48 tests for queue monitoring and alarms
- ✅ **Risk Controls Testing**: 36 tests for lot caps, circuit breakers, and staleness detection
- ✅ **Tick Replay Testing**: 41 tests for deterministic testing and MT5 shim
- ✅ **Data Retention Testing**: 26 tests for data retention policies and compression

---

## 📁 New Files & Components

### 🏗️ Core Infrastructure
- **`trade_bot.py`** - **Main Trading Engine** - Complete automated trading system with AI analysis, signal scanning, trailing stops, and comprehensive monitoring
- **`app/core/hot_path_manager.py`** - Hot-path architecture with ring buffers and async processing
- **`app/core/optimized_ring_buffers.py`** - High-performance ring buffers for tick data
- **`app/core/async_db_writer.py`** - Asynchronous database writer for non-blocking operations
- **`app/core/numba_compute_engine.py`** - Numba-optimized calculations for VWAP, ATR, delta
- **`app/core/time_normalization.py`** - Consistent time handling across all data sources
- **`app/core/windows_scheduling.py`** - Windows-specific thread priority and scheduling
- **`app/core/backpressure_manager.py`** - Queue depth management and backpressure handling

### 🎯 Multi-Timeframe Engine
- **`app/engine/mtf_structure_analyzer.py`** - H4→H1→M30→M15→M5→M1 structure analysis
- **`app/engine/mtf_decision_tree.py`** - Hierarchical decision making across timeframes
- **`app/engine/m1_precision_filters.py`** - M1 confirmation filters (VWAP, delta, ATR, spread)
- **`app/engine/advanced_vwap_calculator.py`** - Real-time VWAP with session anchoring
- **`app/engine/advanced_delta_proxy.py`** - Volume delta proxy with precision validation
- **`app/engine/advanced_micro_bos_choch.py`** - Micro-BOS/CHOCH detection system
- **`app/engine/advanced_spread_filter.py`** - Spread filtering with news window exclusion
- **`app/engine/advanced_atr_ratio_system.py`** - ATR ratio validation across timeframes

### 🛡️ Validation Systems (13 Systems)
- **`infra/structure_validation.py`** - Market structure detection accuracy validation
- **`infra/m1_filter_validation.py`** - M1 filter pass rate validation
- **`infra/latency_validation.py`** - System latency validation (<200ms target)
- **`infra/hot_path_validation.py`** - Hot-path architecture stability validation
- **`infra/binance_integration_validation.py`** - Binance integration stability validation
- **`infra/shadow_mode_validation.py`** - Shadow mode readiness validation
- **`infra/vwap_accuracy_validation.py`** - VWAP accuracy validation (±0.1σ tolerance)
- **`infra/delta_spike_validation.py`** - Delta spike detection accuracy validation
- **`infra/false_signal_reduction_validation.py`** - False signal reduction validation
- **`infra/database_performance_validation.py`** - Database performance validation
- **`infra/binance_order_book_validation.py`** - Order book analysis accuracy validation
- **`infra/large_order_detection_validation.py`** - Large order detection precision validation
- **`infra/exit_precision_validation.py`** - Exit signal precision validation

### 📊 Advanced Analytics & Testing
- **`infra/backtesting_validation.py`** - 12-month backtesting validation system
- **`infra/paper_trading_system.py`** - Paper trading simulation system
- **`infra/staged_activation_system.py`** - Gradual system activation with rollback
- **`infra/win_rate_validation.py`** - Win rate and R:R validation system
- **`infra/sustained_latency_validation.py`** - Continuous latency monitoring
- **`infra/slos_validation.py`** - Service Level Objectives validation
- **`infra/database_optimization_validation.py`** - Database optimization validation
- **`infra/chaos_tests.py`** - Chaos engineering and resilience testing
- **`infra/hdr_histograms.py`** - High-precision performance metrics
- **`infra/tick_replay.py`** - Deterministic testing with tick replay

### 🔧 Configuration & Management
- **`config/symbol_config_loader.py`** - Per-symbol configuration management
- **`config/symbols/BTCUSDc.json`** - BTCUSDc-specific configuration
- **`config/symbols/XAUUSDc.json`** - XAUUSDc-specific configuration
- **`config/symbols/EURUSDc.json`** - EURUSDc-specific configuration
- **`config/symbols/GBPUSDc.json`** - GBPUSDc-specific configuration
- **`config/symbols/USDJPYc.json`** - USDJPYc-specific configuration
- **`infra/config_management.py`** - Configuration hot-reload system
- **`infra/observability.py`** - System health monitoring and observability

### 🚀 Production Deployment (NEW!)
- **`execute_production_deployment.py`** - Production deployment orchestrator
- **`monitor_production_deployment.py`** - Real-time deployment monitoring
- **`validate_production_readiness.py`** - Production readiness validator
- **`start_full_system.py`** - Complete system startup script
- **`STARTUP_GUIDE.md`** - Comprehensive startup and operation guide
- **`production_monitoring_dashboard.py`** - Production monitoring dashboard
- **`production_alerting_system.py`** - Production alerting system
- **`log_aggregation_analysis.py`** - Log aggregation and analysis
- **`performance_metrics_collection.py`** - Performance metrics collection
- **`production_load_testing.py`** - Production load testing system
- **`production_test_validation.py`** - Production test validation system
- **`security_hardening.py`** - Security hardening system
- **`production_validation_orchestrator.py`** - Production validation orchestrator
- **`system_integration_testing.py`** - System integration testing framework
- **`real_market_data_testing.py`** - Real market data testing system
- **`high_volatility_stress_testing.py`** - High volatility stress testing system
- **`system_integration_orchestrator.py`** - System integration orchestrator
- **`production_database_security.py`** - Production database security
- **`backup_disaster_recovery.py`** - Backup and disaster recovery system
- **`logging_audit_trail.py`** - Logging and audit trail system
- **`rollback_procedures.py`** - Rollback procedures and drills
- **`stakeholder_signoff_checklists.py`** - Stakeholder sign-off checklists
- **`deployment_scripts.py`** - Deployment scripts and documentation

### 🚀 Shadow Mode & Decision Tracing
- **`infra/shadow_mode.py`** - Shadow mode system for DTMS comparison
- **`infra/decision_traces.py`** - Decision trace logging with feature hashes
- **`infra/go_nogo_criteria.py`** - Go/no-go criteria for system activation
- **`infra/rollback_mechanism.py`** - Automatic rollback on system failures

### 🔄 Data Management & Integration
- **`app/database/mtf_database_manager.py`** - Multi-timeframe database management
- **`app/database/data_retention_manager.py`** - Intelligent data retention policies
- **`app/database/optimized_sqlite_manager.py`** - Optimized SQLite operations
- **`app/database/trade_management_db.py`** - Trade management database operations
- **`infra/reconnect_strategy.py`** - Binance WebSocket reconnection strategy
- **`infra/snapshot_resync.py`** - Data gap detection and resync
- **`infra/context_features.py`** - Context feature processing system

### 🧪 Testing Infrastructure
- **`test_chatgpt_timeframe_access.py`** - ChatGPT timeframe access testing
- **`test_chatgpt_pipeline_integration.py`** - ChatGPT pipeline integration testing
- **`test_desktop_agent_*.py`** - Desktop agent comprehensive testing (6 test files)
- **`test_api_*.py`** - API endpoint testing (4 test files)
- **`test_*_validation.py`** - Validation system testing (13+ test files)

### 🔔 Custom Alert System (NEW!)
- ✅ **4 Alert Types**: Price, Structure (BOS/CHOCH), Indicator (RSI/MACD), Volatility (ATR/BB)
- ✅ **Flexible Conditions**: Greater than, less than, crosses above/below
- ✅ **One-Time & Recurring**: Alerts auto-remove after trigger or persist for continuous monitoring
- ✅ **Discord Notifications**: Real-time alerts sent directly to Discord webhooks
- ✅ **Custom GPT Integration**: Create/manage alerts via ChatGPT commands
- ✅ **Persistent Storage**: Alerts survive bot restarts

### 📋 Pending Order Management (NEW!)
- ✅ **getPendingOrders Tool**: Custom GPT can now view all pending orders
- ✅ **Full Order Details**: Ticket, symbol, type, entry price, SL, TP, current price
- ✅ **Order Analysis**: ChatGPT can analyze if pending orders are still valid
- ✅ **Smart Modifications**: Adjust entry/SL/TP based on current market conditions
- ✅ **Auto-Cancellation**: Remove invalidated pending orders

### 🛡️ Intelligent Profit Protection
- ✅ **Technical Analysis System**: 7-signal warning framework (CHOCH, engulfing, divergence, etc.)
- ✅ **Weighted Scoring**: Score-based tiered response (exit/tighten/monitor)
- ✅ **Structure-Based Exits**: Tightens SL to swing highs/lows when warnings detected
- ✅ **Only for Profitable Trades**: Never cuts winning trades randomly
- ✅ **Anti-Spam Protection**: 5-minute cooldown on SL modifications

### 📉 Comprehensive Loss Cutting
- ✅ **7 Distinct Checks**: Multi-factor confluence system for losing trades
- ✅ **Automatic Execution**: Closes positions with retry logic and error handling
- ✅ **Discord Alerts**: Real-time notifications for all loss cut actions
- ✅ **Separate from Profit Protection**: Different logic for winning vs losing trades

### ⚡ Intelligent Exit Improvements (NEW!)
- ✅ **Auto-Cleanup**: Removes stale exit rules for closed positions on startup
- ✅ **20% Breakeven Trigger**: Updated from 25% (moves SL to entry at 0.2R profit)
- ✅ **50% Partial Profit**: Takes 50% position at 0.5R profit
- ✅ **Trailing Stops**: Activates after breakeven for maximum profit capture
- ✅ **Database Logging**: All exit actions logged with full context
- ✅ **Adaptive Trade Classification**: Automatically applies SCALP (25% breakeven, 40% partial, 70% close) or INTRADAY (30% breakeven, 60% partial, 50% close) parameters based on trade type

### 💰 Dynamic Lot Sizing
- ✅ **Risk-Percentage Based**: Consistent $ risk per trade
- ✅ **Symbol-Specific Limits**: BTCUSD/XAUUSD max 0.02, Forex max 0.04
- ✅ **0.01 Lot Increments**: Proper broker-compatible rounding
- ✅ **Automatic Calculation**: ChatGPT calculates optimal volume
- ✅ **Fixed API Integration**: Custom GPT now uses dynamic lot sizing correctly

### 📊 Professional Logging System
- ✅ **Desktop Agent Logging**: Console + File + Database + V8 + Conversations
- ✅ **Telegram Bot Logging**: Auto-detection, closed trades, modifications
- ✅ **5 Databases**: journal, advanced_analytics, conversations, intelligent_exit_logger, oco_tracker
- ✅ **Complete Audit Trail**: Every action logged with full context

### 🔧 Bug Fixes & Improvements
- ✅ **Market Hours Detection**: 3-layer validation (weekend + session + tick age)
- ✅ **MT5 Comment Removal**: Removed comment field from close orders (broker compatibility)
- ✅ **Position Display**: Shows all positions (not just 3) with real profit values
- ✅ **Phantom Trade Handling**: Gracefully handles old/orphaned database entries
- ✅ **Order Flow Errors**: Defensive null handling for incomplete order flow data
- ✅ **Alert System Initialization**: Fixed loading order to prevent startup errors
- ✅ **API Improvements**: Better error handling, validation, and logging
- ✅ **Decision Engine Integration Fix**: Fixed critical bug where unified analysis was ignoring decision_engine recommendations (changed from `getattr()` to `.get()` for dictionary access)
- ✅ **Binance Disconnect Fix**: Resolved cross-thread MT5 access causing WebSocket disconnects
- ✅ **Database Locking Resolution**: Separate database architecture eliminates concurrency issues
- ✅ **Safe Retention System**: Intelligent database management with safety measures
- ✅ **Enhanced Alert System**: Intelligent intent parsing with volatility-aware alerts
- ✅ **Shadow Mode Implementation**: Complete shadow mode toggles with decision trace logging
- ✅ **Configuration Management**: Per-symbol JSON configurations with hot-reload capability
- ✅ **Test Coverage**: 194+ comprehensive tests with 100% pass rate across all validation systems
- ✅ **Performance Optimization**: Ring buffers, Numba compute, async DB writes

### 🔧 Recent Fixes (October 2025)
- ✅ **Background Task Errors**: Fixed async wrapper for `scan_for_signals` in chatgpt_bot.py scheduler
- ✅ **Intelligent Exit Manager Initialization**: Added proper initialization in main() function to enable Intelligent Exits background tasks
- ✅ **SL/TP Validation**: Added mandatory stop loss and take profit validation in `MT5Service.market_order()` to prevent trades without protection (configurable via `REQUIRE_SL_TP_FOR_MARKET_ORDERS`)
- ✅ **Auto-Execution System Improvements**: Refactored to use `MT5Service` for robust trade execution with proper error handling and structured result dictionaries
- ✅ **Symbol Normalization**: Enhanced symbol handling with case-preserving logic for 'c' suffix (e.g., BTCUSDc vs BTCUSDC)
- ✅ **Discord Notification Fix**: Fixed notification error where `result.order` was accessed on dict object (now uses `plan.ticket`)
- ✅ **IndicatorBridge Integration**: Fixed `fetch_all()` error by using `get_multi()` method for M5 data access
- ✅ **DTMS Auto-Registration**: Improved auto-registration of trades to DTMS with one-liner wrapper function for all execution paths
- ✅ **Race Condition Fixes**: Added position verification checks before executing actions in both Intelligent Exits and DTMS systems
- ✅ **File Safety**: Implemented atomic write pattern for intelligent_exits.json to prevent corruption during concurrent writes

---

## 📋 System Architecture Overview

### **Service Architecture**

The system consists of multiple services that can be started individually or all at once:

#### **Core Services:**
1. **`app/main_api.py`** - Main FastAPI Server (Port 8000)
   - Primary API endpoint for ChatGPT and external integrations
   - Provides trading tools, analysis, and system management

2. **`hub/command_hub.py`** - Phone Control Command Hub (Port 8001)
   - Routes commands from phone Custom GPT to desktop agent
   - WebSocket connection hub for real-time communication
   - Authentication via bearer tokens

3. **`desktop_agent.py`** - Desktop Agent
   - Executes trading tools and connects to Command Hub
   - Provides tool execution for Custom GPT phone/web control
   - Monitors positions and manages trades

4. **`dtms_api_server.py`** - DTMS API Server
   - HTTP API for accessing DTMS system
   - External process integration for trade management

5. **`chatgpt_bot.py`** - ChatGPT Bot
   - Telegram bot interface with AI assistance
   - Natural language trading conversations
   - Automated monitoring and notifications

6. **Ngrok Tunnel**
   - Exposes local API to internet for Custom GPT access
   - Required for phone/web control functionality

#### **News Data Gathering Services:**
7. **`fetch_news_feed.py`** - News Feed Fetcher
   - Fetches Forex Factory economic calendar
   - Updates `data/news_events.json`

8. **`priority2_breaking_news_scraper.py`** - Breaking News Scraper
   - Scrapes breaking news from multiple sources
   - Real-time high-impact event detection

9. **`fetch_news_sentiment.py`** - News Sentiment Fetcher
   - Enhances news events with GPT-4 sentiment analysis
   - Updates news data with trading implications

### **Quick Start: All Services**

Use `start_all_services.bat` to launch all services at once:
```bash
start_all_services.bat
```

This starts all 9 services in separate windows with virtual environment activated.

### **Quick Feature Comparison**

| Feature | TelegramMoneyBot v8.0 | Typical Trading Bot |
|---------|----------------------|-------------------|
| **AI Integration** | ✅ Full ChatGPT + Custom GPT | ❌ Basic signals |
| **Binance Streaming** | ✅ 1-second real-time data | ❌ Delayed/aggregated |
| **Order Flow** | ✅ Institutional whale detection | ❌ Not available |
| **37 Enrichment Fields** | ✅ Professional-grade | ❌ Basic indicators |
| **Custom Alerts** | ✅ 4 types (price/structure/indicator/volatility) | ❌ None |
| **Pending Order Analysis** | ✅ ChatGPT can view & analyze | ❌ Not available |
| **Profit Protection** | ✅ 7-signal technical analysis | ❌ None |
| **Loss Cutting** | ✅ 7-check confluence system | ❌ Stop loss only |
| **Advanced-Enhanced Exits** | ✅ AI-adaptive (20-80% triggers) | ❌ Static only |
| **Intelligent Exits** | ✅ 100% automatic (0.2R, 0.5R) | ❌ Manual only |
| **Auto-Cleanup** | ✅ Removes stale exit rules | ❌ Manual cleanup |
| **Dynamic Lot Sizing** | ✅ Risk-based per symbol | ❌ Fixed lots |
| **Market Context** | ✅ DXY + US10Y + VIX auto-fetch | ❌ Single symbol |
| **Database Logging** | ✅ 5 databases, full audit trail | ⚠️ Basic CSV |
| **Advanced Analytics** | ✅ 37 features → outcomes (ML-ready) | ❌ None |
| **Conversation Logging** | ✅ Every ChatGPT interaction | ❌ None |
| **Closed Trade Detection** | ✅ Auto-detects manual closes | ❌ None |
| **OCO Brackets** | ✅ Auto-cancel opposite | ❌ Not supported |
| **Startup Recovery** | ✅ Auto-resumes monitoring | ❌ Lost on restart |
| **Natural Language** | ✅ "Analyze Gold for me" | ❌ Commands only |

---

## 🚀 Core Features

### 🤖 Main Trading Engine (trade_bot.py)
- **Complete Automated Trading System**: Full-featured trading bot with AI analysis and automated execution
- **Signal Scanning**: Automatic high-probability signal detection across multiple timeframes
- **Trailing Stops**: Advanced trailing stop management with trade monitoring
- **Position Management**: Real-time position monitoring with automatic notifications
- **Circuit Breaker**: Risk management with automatic trading suspension during adverse conditions
- **Feature Builder Integration**: Advanced technical indicators and market structure analysis
- **Prompt Router**: Intelligent command routing and user interaction management
- **Comprehensive Logging**: Full audit trail with both console and file logging
- **Background Jobs**: Automated monitoring with configurable intervals
- **Error Handling**: Robust error handling with fault detection and recovery
- **Modular Architecture**: Clean separation of concerns with handler-based design

### 🎯 Real-Time Intelligence

#### Binance 1-Second Streaming
- **WebSocket Connection**: Real-time price updates every second
- **Microsecond Precision**: Professional-grade timing accuracy
- **Automatic Reconnection**: Resilient connection handling
- **Symbol Mapping**: MT5 ↔ Binance symbol translation
- **Validation**: Price offset monitoring (warns if >10 pips difference)

#### Order Flow Analysis
- **Whale Detection**: Identifies large institutional orders (>100x avg volume)
- **Order Book Imbalance**: Bid/ask pressure analysis
- **Tape Reading**: Real-time trade flow analysis
- **Liquidity Voids**: Identifies gaps in order book depth
- **Dominant Side**: Bullish/bearish institutional pressure

#### 37 Enrichment Fields
```
📊 Price Structure (5): rmag_ema200_atr, rmag_vwap_atr, ema50_slope, ema200_slope, vwap_deviation

📈 Volatility State (3): vol_trend_state, vol_trend_bb_width, vol_trend_adx

💪 Momentum Quality (3): pressure_ratio, pressure_rsi, pressure_adx

🕯️ Candle Anatomy (3): candle_type, candle_body_atr, candle_w2b

💧 Liquidity (3): liquidity_pdl_dist_atr, liquidity_pdh_dist_atr, liquidity_equal_highs/lows

🌊 Microstructure (8): fvg_type, fvg_dist_atr, vwap_dev_atr, vwap_zone, accel_macd_slope, accel_rsi_slope, mtf_total, mtf_max

📊 Volume Profile (2): vp_hvn_dist_atr, vp_lvn_dist_atr

🐋 Order Flow (10): whale_count, order_book_imbalance, dominant_side, liquidity_voids, signal, confidence, pressure_side, tape_strength, trade_size_distribution, order_flow_warnings
```

### 🛡️ Intelligent Profit Protection

#### 7 Warning Signals

**Critical Signals (Weight: 3):**
1. **CHOCH (Change of Character)**: Market structure shift (breaks swing high/low)
2. **Opposite Engulfing**: Large opposite-direction candle (institutional reversal)

**Medium Signals (Weight: 2):**
3. **Liquidity Target Hit + Rejection**: Price reaches major level and gets rejected
4. **Momentum Divergence**: RSI/MACD divergence (price vs indicator mismatch)
5. **Dynamic S/R Break**: EMA 20/50 break, VWAP rejection, trendline break

**Minor Signals (Weight: 1):**
6. **Momentum Loss**: ATR dropping, smaller candles, weak push
7. **Session Shift / Time Risk**: Session changes, Friday close, weekend risk
8. **Whale Orders**: Opposite institutional order flow detected

#### Tiered Response
- **Score ≥ 5**: 🔴 **EXIT IMMEDIATELY** (multiple critical signals)
- **Score 2-4**: 🟡 **TIGHTEN SL** to structure (lock in most profit)
- **Score < 2**: 🟢 **MONITOR** (continue watching, log warning)

### 📉 Loss Cutting System

#### 7 Distinct Checks (For Losing Trades)
1. **Early Exit AI**: RSI/ADX momentum collapse (<45 RSI, <25 ADX)
2. **Structure Collapse**: Market structure breakdown
3. **Momentum Fade**: Sustained momentum loss across timeframes
4. **Time Backstop**: Trade held too long without progress (>122 min at -0.08R)
5. **Spread Spike**: Abnormal spread widening (risk of slippage)
6. **ADX Death**: Trend strength collapse (ADX <20)
7. **Risk Simulation**: Negative expected return (minor signal, low weight)

### 💰 Dynamic Lot Sizing

```python
# Symbol-Specific Risk Configuration
BTCUSD: 2% risk, max 0.02 lots
XAUUSD: 2% risk, max 0.02 lots
Forex:  4% risk, max 0.04 lots

# Formula
lot_size = (equity × risk_pct / 100) / (stop_distance_ticks × tick_value)
lot_size = round(lot_size, 2)  # 0.01 increments
lot_size = min(lot_size, MAX_LOT_SIZES[symbol])
lot_size = max(lot_size, MIN_LOT_SIZE)  # 0.01 minimum
```

### 📊 Database System

#### `data/journal.sqlite`
**Tables:**
- `trades`: Trade opens/closes, P&L, R-multiple, duration
- `events`: All events (SL/TP mods, loss cuts, errors, etc.)
- `equity`: Equity snapshots for performance tracking

#### `data/advanced_analytics.sqlite`
**Tables:**
- `advanced_trade_features`: 37 V8 fields at trade entry → outcomes
- `advanced_feature_importance`: Feature performance analysis
- `advanced_feature_combinations`: Combination effectiveness

#### `data/conversations.sqlite`
**Tables:**
- `conversations`: All ChatGPT interactions (user query, assistant response, tool calls)
- `analysis_requests`: Detailed analysis data (symbol, direction, confidence, reasoning)
- `recommendations`: Trade recommendations (was executed?, outcome, success rate)

#### `data/intelligent_exit_logger.db`
**Tables:**
- Exit management actions (breakeven, partial, trailing, modifications)

#### `data/oco_tracker.db`
**Tables:**
- OCO bracket trades tracking

#### `data/analysis_data.db` (Desktop Agent writes)
**Tables:**
- `analysis_results`: Technical analysis results and DTMS actions
- `trade_recommendations`: ChatGPT trade recommendations

#### `data/system_logs.db` (API Server writes)
**Tables:**
- `api_logs`: API request logs
- `system_health`: System health monitoring

### 💾 Memory Usage & Tick Data Storage

#### **Tick Data Storage: IN-MEMORY ONLY**
- ✅ **Tick data is NOT saved to database** - Only stored in optimized in-memory buffers
- ✅ **Real-time analysis**: 1000 ticks per symbol (~16 minutes of data at 1 tick/second)
- ✅ **Memory usage**: ~2-10 MB total (laptop-safe)
  - **Per symbol**: ~400 KB for tick buffers + ~20 KB for ring buffers
  - **5-10 active symbols**: ~2-4.5 MB total
  - **20 active symbols (worst case)**: ~8-10 MB maximum
- ✅ **No database I/O**: Eliminates disk writes, reduces heat, extends battery life
- ✅ **Performance**: No degradation - 1000 ticks sufficient for real-time indicators (VWAP, ATR, EMA)

**Configuration:**
- Tick buffer size: **1000 ticks/symbol** (reduced from 10,000)
- Ring buffer capacity: **1000-2000 ticks/symbol** (reduced from 5,000-20,000)
- Database storage: **DISABLED** (`enable_database_storage: False`)

---

## 📋 Prerequisites

### Required Software
- **Python 3.8+**
- **MetaTrader 5** (with active trading account)
- **Telegram Bot Token** (from @BotFather)
- **OpenAI API Key** (for AI analysis)
- **ngrok** (optional, for ChatGPT API integration)

### Python Dependencies
```bash
pip install -r requirements.txt
```

Key dependencies:
- `python-telegram-bot` - Telegram bot framework
- `MetaTrader5` - MT5 integration
- `pandas`, `numpy` - Data analysis
- `ta` - Technical analysis
- `fastapi`, `uvicorn` - Web framework for API
- `openai` - AI integration
- `websockets` - Binance streaming and WebSocket connections
- `yfinance` - Market data (DXY, VIX, US10Y, NASDAQ)
- `psutil` - System and process utilities (optional, for system monitoring)
- `requests` - HTTP client (for Discord webhooks, news fetching, FRED API)
- `beautifulsoup4` - Web scraping (for breaking news)
- `fredapi` - FRED economic data API (Fed Funds Rate, Treasury yields, inflation)
- `pandas`, `numpy` - Data analysis (volatility forecasting, order flow calculations)
- `ta` - Technical analysis library (Bollinger Bands, ATR calculations)

---

## ⚙️ Configuration

### Environment Variables
Create a `.env` file with the following variables:

```env
# Telegram Configuration (for chatgpt_bot.py)
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_BOT_CHAT_ID=your_chat_id
TELEGRAM_WEBHOOK_SECRET=your_webhook_secret

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini

# Phone Control Configuration (NEW!)
PHONE_BEARER_TOKEN=phone_control_bearer_token_2025_v1_secure
AGENT_SECRET=your_generated_agent_secret

# Discord Notifications (NEW!)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_url
DISCORD_BOT_NAME=Trading Bot

# MT5 Configuration
MT5_WINDOW_TITLE=Exness
MT5_FILES_DIR=C:\Users\Public\Documents\MetaQuotes\Terminal\Common\Files

# Trading Settings
DEFAULT_LOT_SIZE=0.01
SLIPPAGE_POINTS=50
MAGIC_NUMBER=202510
RISK_PCT=1.0

# Dynamic Lot Sizing
LOT_SIZING_ENABLED=True
LOT_SIZING_MIN=0.01
LOT_SIZING_BTCUSD_MAX=0.02
LOT_SIZING_XAUUSD_MAX=0.02
LOT_SIZING_FOREX_MAX=0.04

# Journal and Data Paths
JOURNAL_ENABLE=1
JOURNAL_DIR=./data
JOURNAL_DB=./data/journal.sqlite

# API Configuration (for ChatGPT integration)
API_KEY=your_secure_api_key
API_PORT=8000

# Binance Configuration
BINANCE_ENABLED=True
BINANCE_STREAM_INTERVAL=1  # seconds

# FRED API (for economic data - FREE, requires email signup)
FRED_API_KEY=your_fred_api_key
# Get your free API key at: https://fred.stlouisfed.org/docs/api/api_key.html

# Alpha Vantage (for economic data)
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
```

---

## 📚 New Knowledge Documents

### **Strategy Guides**
- **`LONDON_BREAKOUT_STRATEGY.md`** - Professional London session trading (07:00-10:00 UTC)
- **`NEWS_TRADING_STRATEGY.md`** - High-impact news event trading (NFP, CPI, FOMC)
- **`SYMBOL_GUIDE.md`** - Comprehensive guide for all 7 trading symbols

### **Setup Guides**
- **`CHATGPT_SETUP_GUIDE.md`** - Complete ChatGPT integration setup
- **`DISCORD_SETUP_GUIDE.md`** - Discord notifications setup
- **`WINDOWS_TASK_SCHEDULER_SETUP.md`** - News automation setup
- **`NEWS_TRADING_SETUP_COMPLETE.md`** - News trading system implementation

### **Technical Documentation**
- **`.claude.md`** - Complete codebase guide for AI assistants
- **`openai.yaml`** - Enhanced OpenAPI specification with strategy endpoints
- **`CUSTOM_GPT_INSTRUCTIONS_ULTRA_CONCISE.md`** - Optimized ChatGPT instructions

## 🚀 Quick Start

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/BenignMalice/TelegramMoneyBot.v7.git
cd TelegramMoneyBot.v7

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp env.example .env
# Edit .env with your configuration
```

### 2. Running the Bot

#### Option A: Main Trading Engine (Full Automated System)
```bash
# Start the complete automated trading system
python trade_bot.py
```

#### Option B: Telegram Bot Only (Manual Trading with AI)
```bash
python chatgpt_bot.py
```

#### Option C: Full System (All Components)
```bash
# Terminal 1: Start the main trading engine
python trade_bot.py

# Terminal 2: Start the API server
python -m uvicorn app.main_api:app --host 0.0.0.0 --port 8000 --reload

# Terminal 3: Start ngrok (for public API access)
ngrok http 8000

# Terminal 4: Start desktop agent (for Custom GPT phone/web control)
python desktop_agent.py

# Terminal 5: Start Telegram bot (optional, for additional interface)
python chatgpt_bot.py
```

#### Option C: Use Batch Files (Windows)
```bash
# Start all services at once (recommended)
start_all_services.bat

# Or start individually
python app/main_api.py              # Main API (port 8000)
python hub/command_hub.py           # Command Hub (port 8001)
python desktop_agent.py            # Desktop Agent
python dtms_api_server.py          # DTMS API Server
python chatgpt_bot.py              # ChatGPT Bot
python fetch_news_feed.py          # News Feed Fetcher
python priority2_breaking_news_scraper.py  # Breaking News Scraper
python fetch_news_sentiment.py     # News Sentiment Fetcher
ngrok http 8000 --url=your-url     # Ngrok tunnel
```

### 3. Using the Bot

#### Telegram Commands (chatgpt_bot.py)
```
/status       - Account & positions (shows ALL positions with real P&L)
/help         - Show all commands
/chatgpt      - Start AI conversation
/trade XAUUSD - Analyze a symbol
```

#### Custom GPT (Phone/Web via desktop_agent.py)
```
"Analyze XAUUSD for me"
"Place a BUY on EURUSD at 1.0850, SL 1.0800, TP 1.0920"
"Show my positions"
"What's the current DXY price?"
```

**Note**: Phone control requires Command Hub (`hub/command_hub.py`) and Desktop Agent (`desktop_agent.py`) to be running.

---

## 📱 Telegram Bot Commands

### Trading Commands
- `/status` - Account status & positions (shows ALL with real P&L)
- `/trade <symbol>` - Analyze a symbol and propose a trade
- `/pending` - Place pending orders (buy/sell stop/limit)
- `/positions` - Show open positions & P/L
- `/close` - Close a position
- `/manage` - Open trade manager for position management

### ChatGPT Commands
- `/chatgpt` - Start ChatGPT conversation mode
- `/endgpt` - End ChatGPT conversation
- **Interactive Menu**: Use "💬 Get Trade Plan" button for instant AI recommendations

### Account & Risk Commands
- `/balance` - Show account balance
- `/equity` - Show account equity
- `/risk` - Show current default risk percentage
- `/setrisk <value>` - Set default risk percentage

### Analysis Commands
- `/journal` - Show recent trade journal entries
- `/news` - Economic calendar and headlines
- `/fundamentals` - Daily fundamentals/sentiment snapshot
- `/scan` - Run multi-timeframe scanner
- `/dashboard` - Performance statistics

### System Commands
- `/pause` - Pause trading (circuit breaker ON)
- `/resume` - Resume trading (circuit breaker OFF)
- `/circuit` - Check circuit breaker status
- `/help` - Show available commands

---

## 🔧 Advanced Configuration

### Intelligent Exit Settings
```python
# config/settings.py

# Advanced-Enhanced Intelligent Exits
INTELLIGENT_EXITS_AUTO_ENABLE = True  # Auto-enable for all new positions
INTELLIGENT_EXITS_BREAKEVEN_PCT = 30.0  # Move SL to breakeven at 30% of potential profit (0.3R)
INTELLIGENT_EXITS_PARTIAL_PCT = 60.0  # Take partial profit at 60% of potential profit (0.6R)
INTELLIGENT_EXITS_PARTIAL_CLOSE_PCT = 50.0  # Close 50% of position at partial level
INTELLIGENT_EXITS_VIX_THRESHOLD = 18.0  # VIX level above which to widen stops
INTELLIGENT_EXITS_USE_HYBRID_STOPS = True  # Use hybrid ATR+VIX for stop adjustment
INTELLIGENT_EXITS_TRAILING_ENABLED = True  # Enable ATR trailing stops after breakeven
```

### Loss Cutting Settings
```python
# Early exit at -0.8R (80% of SL)
POS_EARLY_EXIT_R = -0.8

# Risk simulation threshold
POS_RISK_SCORE_THRESHOLD = 0.65

# Time backstop (minutes)
POS_TIME_BACKSTOP_MINUTES = 122

# Spread protection (ATR multiplier)
POS_SPREAD_ATR_CAP = 0.4
```

### Lot Sizing Settings
```python
# config/lot_sizing.py

MIN_LOT_SIZE = 0.01

MAX_LOT_SIZES = {
    "BTCUSD": 0.02,   # 2% risk
    "XAUUSD": 0.02,   # 2% risk
    # All other symbols default to 0.04 (4% risk)
}

RISK_PERCENTAGES = {
    "BTCUSD": 2.0,
    "XAUUSD": 2.0,
    # All other symbols default to 4.0
}
```

### Binance & Order Flow Settings
```python
# Binance streaming
BINANCE_ENABLED = True
BINANCE_CHECK_INTERVAL = 1  # seconds
BINANCE_PRICE_OFFSET_WARN_PIPS = 10  # warn if MT5 vs Binance > 10 pips

# Order Flow
ORDER_FLOW_ENABLED = True
ORDER_FLOW_WHALE_THRESHOLD_MULTIPLIER = 100  # 100x average volume
ORDER_FLOW_IMBALANCE_THRESHOLD = 0.3  # 30% imbalance
```

---

## 📊 Database Queries

### Check Recent Trades
```sql
-- Recent trades with outcome
SELECT ticket, symbol, side, entry_price, exit_price, pnl, r_multiple, 
       datetime(opened_ts, 'unixepoch') as opened, 
       datetime(closed_ts, 'unixepoch') as closed
FROM trades
WHERE closed_ts IS NOT NULL
ORDER BY closed_ts DESC
LIMIT 10;
```

### Check Advanced Analytics
```sql
-- Win rate by volatility state
SELECT 
    vol_trend_state,
    COUNT(*) as total_trades,
    SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate,
    ROUND(AVG(r_multiple), 2) as avg_r
FROM advanced_trade_features
WHERE outcome IN ('win', 'loss')
GROUP BY vol_trend_state
ORDER BY win_rate DESC;
```

### Check Conversation History
```sql
-- Recent ChatGPT interactions
SELECT 
    datetime(timestamp, 'unixepoch') as time,
    action,
    symbol,
    confidence,
    recommendation
FROM conversations
WHERE source = 'desktop_agent'
ORDER BY timestamp DESC
LIMIT 20;
```

---

## 🔒 Security

### Risk Controls
- **Circuit Breaker**: Automatic trading suspension during adverse conditions
- **Position Limits**: Symbol-specific maximum lot sizes
- **Profit Protection**: 7-signal technical analysis prevents profit givebacks
- **Loss Cutting**: 7-check system limits losses
- **Slippage Protection**: Configurable slippage limits

### Data Protection
- **API Key Authentication**: Secure API access via X-API-Key headers
- **Environment Variables**: Sensitive data in .env file
- **Audit Logging**: Comprehensive activity logging to multiple databases
- **Local Storage**: All databases stored locally (SQLite)

---

## 📝 License

This project is proprietary software. All rights reserved.

---

## 🤝 Support

For support and questions:
- Check the `/help` command in the bot
- Review documentation files:
  - `LOGGING_IMPLEMENTATION_COMPLETE.md` - Logging system details
  - `LOW_PRIORITY_LOGGING_COMPLETE.md` - V8 analytics & conversation logging
  - `PROFIT_PROTECTION_SYSTEM.md` - Profit protection documentation
  - `MODIFY_POSITION_FIX.md` - API modification fixes
  - `TELEGRAM_STATUS_FIX.md` - Position display fixes

---

## 📚 Documentation Files

### Setup & Configuration
- `QUICK_START.md` - Quick start guide
- `CHATGPT_INSTRUCTIONS.txt` - ChatGPT setup instructions
- `ChatGPT_Custom_Instructions.md` - Custom GPT instructions
- `openai.yaml` - ChatGPT Actions OpenAPI schema

### Feature Documentation
- `LOGGING_IMPLEMENTATION_COMPLETE.md` - Complete logging system (HIGH/MEDIUM priority)
- `LOW_PRIORITY_LOGGING_COMPLETE.md` - V8 analytics & conversation logging
- `PROFIT_PROTECTION_SYSTEM.md` - Intelligent profit protection details
- `TELEGRAM_STATUS_FIX.md` - Position display improvements
- `MODIFY_POSITION_FIX.md` - API position modification fixes
- `TRADE_CLOSE_LOGGER_FIX.md` - Closed trade detection system
- `PHANTOM_TRADES_FIX.md` - Graceful handling of orphaned trades

### System Architecture & Fixes
- `SAFE_RETENTION_INTEGRATION_GUIDE.md` - Safe retention system integration
- `RETENTION_INTEGRATION_SUMMARY.md` - Retention system summary
- `BINANCE_FIX_SUMMARY.md` - Binance disconnect fix details
- `BINANCE_FIX_IMPLEMENTATION_GUIDE.md` - Binance fix implementation
- `HYBRID_RETENTION_SYSTEM_GUIDE.md` - Complete retention system guide
- `UNIFIED_TICK_PIPELINE_KNOWN_ISSUES.md` - Known issues and solutions

### Bug Fixes
- `MODIFY_POSITION_FIX.md` - ChatGPT position modification
- `TRADE_CLOSE_LOGGER_FIX.md` - Missing methods implementation
- `PHANTOM_TRADES_FIX.md` - Phantom trade log spam fix
- `TELEGRAM_STATUS_FIX.md` - Profit display & position limit fixes

---

## ⚠️ Disclaimer

This software is for educational and research purposes. Trading involves substantial risk of loss. Past performance does not guarantee future results. Always trade responsibly and within your risk tolerance. The AI integration is experimental and should be thoroughly tested before live trading.

---

## 🎯 Quick Command Reference

### Most Used Commands
| Command | Description |
|---------|-------------|
| `/status` | Account & ALL positions with real P&L |
| `/chatgpt` | Start AI conversation |
| `/trade XAUUSD` | Analyze gold with full enrichment |
| `/positions` | View open positions |
| `/close` | Close a position |
| `/help` | Show all commands |

### Natural Language Examples (ChatGPT/Custom GPT)
```
"Analyze XAUUSD for me"
"Place a BUY on EURUSD at 1.0850, SL 1.0800, TP 1.0920"
"Show my positions"
"Show my pending orders"
"What's the current DXY price?"
"Move stop loss to breakeven on ticket 122387063"
"How many warning signals does my EURUSD trade have?"
"Alert me when XAUUSD drops below 2600"
"Create a BOS alert for BTCUSD on M15"
"Show all my active alerts"
"Remove alert for XAUUSD"
```

---

**Built with ❤️ for traders who want intelligent, automated trading analysis with institutional-grade market intelligence, comprehensive logging, and professional risk management**

**v8.6 - December 2025 - Now with Adaptive Micro-Scalp Strategy System (3-regime adaptive selection), Micro-Scalp Automation System (continuous monitoring), Streamer API Endpoints (cross-process communication), Auto-Execution System Improvements (monitoring status, plan fixes, WebSocket reconnection), and comprehensive testing suite**

**v8.5 - November 2025 - Now with BTC Order Flow Metrics Integration, Weekend-Only BTC Streaming, SL/TP Enforcement & Critical Discord Alerts, Update Auto Plan Tool, Enhanced Plan Conditions, M1 Microstructure Integration, Volatility Regime Detection & Strategy Selection, Adaptive Intelligent Exit System (AIES), Range Scalping Auto-Execution, Trade Type Classification, and Enhanced Exit Management**
