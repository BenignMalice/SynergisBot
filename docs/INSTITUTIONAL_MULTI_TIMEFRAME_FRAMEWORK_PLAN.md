# Institutional Multi-Timeframe Framework - Complete Implementation Plan

## 🎯 **EXECUTIVE SUMMARY**

**Objective:** Build institutional-grade multi-timeframe trading system (H4→H1→M30→M15→M5→M1) with <200ms latency, 90% false-signal reduction, and 80%+ win rate with 1:3+ R:R.

**Symbol Coverage:** EURUSDc, GBPUSDc, USDJPYc, USDCHFc, AUDUSDc, USDCADc, NZDUSDc, EURJPYc, GBPJPYc, EURGBPc, BTCUSDc, XAUUSDc

**Priority Order:** EURUSDc, GBPUSDc, USDJPYc (forex majors) → Cross pairs → BTCUSDc, XAUUSDc (crypto/commodity)

**Integration:** Replace current Intelligent Exits entirely with multi-timeframe DTMS system.

## 🚀 **KEY UPDATES IMPLEMENTED**

### **1. Accelerated Timeline (4 Weeks Total)**
- **Week 1:** Core framework + database (BTCUSDc, XAUUSDc, EURUSDc)
- **Week 2:** Advanced filters + database management (USDCHFc, AUDUSDc, USDCADc, NZDUSDc)  
- **Week 3:** DTMS integration + database optimization (EURJPYc, GBPJPYc, EURGBPc)
- **Week 4:** Production deployment + validation (BTCUSDc, XAUUSDc with Binance)

### **2. Symbol Priority Order**
- **Priority 1:** EURUSDc, GBPUSDc, USDJPYc (forex majors)
- **Priority 2:** USDCHFc, AUDUSDc, USDCADc, NZDUSDc (forex minors)
- **Priority 3:** EURJPYc, GBPJPYc, EURGBPc (cross pairs)
- **Priority 4:** BTCUSDc, XAUUSDc (crypto/commodity with Binance order book)

### **3. Enforced Lot Size Limits**
- **BTCUSDc/XAUUSDc:** ≤0.02 lots maximum
- **Forex Pairs:** ≤0.04 lots maximum  
- **Cross Pairs:** ≤0.03 lots maximum

### **4. Comprehensive Database Architecture**
- Multi-timeframe structure analysis storage
- M1 precision filters tracking
- Trade decisions with timeframe hierarchy
- DTMS exits with multi-timeframe logic
- Performance metrics by timeframe
- Data retention and compression policies

### **5. Binance Order Book Integration (BTCUSD)**
- WebSocket depth streams (`btcusdt@depth`)
- REST depth endpoints (`/api/v3/depth`)
- Large order detection algorithms
- Support/resistance level identification
- Market microstructure analysis

---

## 📊 **SYMBOL-SPECIFIC OPTIMIZATION MATRIX**

### **Crypto Assets**
| Symbol | Volatility Profile | VWAP Threshold | Delta Threshold | ATR Filter | Session Focus |
|--------|-------------------|----------------|-----------------|------------|---------------|
| **BTCUSDc** | High volatility, whale manipulation | ±0.2σ | 1.5× avg | M1 < 0.5× M5 | 24/7, London/NY overlap |
| **XAUUSDc** | Macro-sensitive, news spikes | ±0.15σ | 1.3× avg | M1 < 0.4× M5 | London/NY, news events |

### **Major Forex Pairs**
| Symbol | Liquidity Profile | VWAP Threshold | Delta Threshold | ATR Filter | Session Focus |
|--------|------------------|----------------|-----------------|------------|---------------|
| **EURUSDc** | Highest liquidity | ±0.1σ | 1.2× avg | M1 < 0.3× M5 | London/NY overlap |
| **GBPUSDc** | High volatility | ±0.15σ | 1.4× avg | M1 < 0.4× M5 | London session |
| **USDJPYc** | Carry trade sensitive | ±0.12σ | 1.3× avg | M1 < 0.35× M5 | Tokyo/London |
| **USDCHFc** | Safe haven flows | ±0.1σ | 1.2× avg | M1 < 0.3× M5 | London/NY |
| **AUDUSDc** | Commodity currency | ±0.15σ | 1.4× avg | M1 < 0.4× M5 | Sydney/London |
| **USDCADc** | Oil correlation | ±0.12σ | 1.3× avg | M1 < 0.35× M5 | London/NY |
| **NZDUSDc** | Risk-on/off sensitive | ±0.15σ | 1.4× avg | M1 < 0.4× M5 | Sydney/London |

### **Cross Currency Pairs**
| Symbol | Correlation Profile | VWAP Threshold | Delta Threshold | ATR Filter | Session Focus |
|--------|-------------------|----------------|-----------------|------------|---------------|
| **EURJPYc** | Risk sentiment | ±0.12σ | 1.3× avg | M1 < 0.35× M5 | Tokyo/London |
| **GBPJPYc** | High volatility | ±0.18σ | 1.5× avg | M1 < 0.45× M5 | London session |
| **EURGBPc** | Range-bound | ±0.08σ | 1.1× avg | M1 < 0.25× M5 | London session |

---

## ⚡ **PERFORMANCE SPECIFICATIONS**

### **Latency Budget (200ms Total) - REVISED**
```
Ingestion (MT5 ticks + Binance depth):    ≤10ms
Feature Compute (VWAP, ATR, delta):       ≤30ms  
Decision Engine (H1→M15→M5 hierarchy):     ≤10ms
Async DB Write (queued):                  ≤10ms
MT5 I/O + Overhead:                       ≤140ms
TOTAL:                                     ≤200ms
```

### **Hot Path Architecture (Memory-First) - IMPLEMENTATION DETAILS**
```
Ring Buffers: Preallocated per symbol/TF for ticks and features (N≈10k)
Compute: Numba (nopython, parallel) for VWAP/ATR/delta, GIL-free
Storage: Async batched writes (50-100 rows or 100-200ms), never block decision path
Concurrency: Thread-per-symbol ingestion + bounded queues + single DB writer
Backpressure: Drop context features first, never drop exits/stops
```

### **Critical Implementation Requirements**
```
MT5 I/O: Dedicated ingestion thread per symbol, non-blocking polling
Time Normalization: epoch_ms (INTEGER), source (mt5|binance), symbol_normalized
SQLite Optimization: WAL mode, NORMAL sync, MEMORY temp, 100k cache
Windows Scheduling: Thread priorities, time.perf_counter_ns(), no datetime.now()
```

## 🔧 **TECHNICAL IMPLEMENTATION DETAILS**

### **Signal Definitions (Explicit) - IMPLEMENTATION SPECS**
```
VWAP: Session anchor per asset (FX sessions vs 24/7 crypto), 60min sigma window
Delta Proxy: Mid-price change + tick direction, validate precision/recall vs moves
ATR Ratio: M1 ATR(14) vs M5 ATR(14), symbol-specific multipliers in config
Micro-BOS/CHOCH: Bar-count lookback + ≥0.25-0.5× ATR displacement + cooldown
Spread Filter: Rolling median(20) with outlier clip, exclude news windows
```

### **Database Schema & Optimization - IMPLEMENTATION SPECS**
```sql
-- Critical Indexes
CREATE INDEX IF NOT EXISTS idx_mtf_struct ON mtf_structure_analysis(symbol, timeframe, timestamp_utc DESC);
CREATE INDEX IF NOT EXISTS idx_mtf_decisions ON mtf_trade_decisions(symbol, timestamp_utc DESC);
CREATE INDEX IF NOT EXISTS idx_mtf_exits ON mtf_dtms_exits(symbol, timestamp_utc DESC);

-- SQLite PRAGMAs
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA temp_store=MEMORY;
PRAGMA busy_timeout=5000;
PRAGMA cache_size=-100000;
```

### **Data Architecture - IMPLEMENTATION DETAILS**
```
Primary: SQLite+WAL with batched INSERTs (single host)
Analytics: DuckDB for offline backtests
Indexing: Composite (symbol, timeframe, timestamp_utc DESC)
Partitioning: By symbol for heavy symbols
Retention: Cron + vacuum/analyze schedule
Rollups: Nightly aggregates into mtf_performance_metrics
JSON Storage: TEXT type, compact schemas for hot tables
```

### **Risk Controls (Process-External) - IMPLEMENTATION SPECS**
```
Lot Caps: Hard guards at order-entry with violation logging
Circuit Breakers: Redis flags or atomic files (all workers respect, TTL)
Staleness: Auto-demote to exits-only if ≥2× cadence
Backpressure: Drop context features first, never drop exits/stops
Queue Monitoring: Alarm when queues exceed thresholds
```

### **Testing Strategy - IMPLEMENTATION SPECS**
```
Tick Replay: Deterministic testing for 4 symbols with MT5 I/O shim
Property Tests: VWAP reclaim monotonicity, ATR boundary conditions, BOS displacement
Chaos Tests: Inject TF staleness and Binance disconnects, verify degrade to exits-only
Shadow Mode: Run DTMS alongside Intelligent Exits for 2-3 weeks
Decision Traces: Full feature vectors with hashes for error analysis
HDR Histograms: p50/p95/p99 per stage, per-queue depth metrics
```

## 🚀 **CONCRETE IMPLEMENTATION STEPS**

### **Phase 1 Immediate Actions**
```
1. Define event schemas and ring-buffer sizes
2. Add per-stage timers in unified_tick_pipeline/core/pipeline_manager.py
3. Add async DB writer and breaker flag checks
4. Ensure hot path never awaits I/O
5. Introduce shadow-mode toggles in infra/intelligent_exit_manager.py
6. Log full decision traces with feature vector hashes
7. Create per-symbol config file and loader
8. Wire thresholds for BTCUSDc, XAUUSDc, EURUSDc, GBPUSDc, USDJPYc first
```

### **Configuration Management**
```
Per-Symbol Config: TOML/JSON with thresholds, cadences, ATR windows
Hot-Reload: Atomic file swap mechanism
Logging: Structured JSON, low-cardinality labels (symbol, TF, stage)
Observability: Lightweight /health endpoint for latency/freshness breakers
```

### **Binance Context Integration**
```
Symbol Normalization: BTCUSDc vs Binance BTCUSDT mapping
Reconnect Strategy: Jittered exponential backoff, seq-id checks
Snapshot Re-sync: On gap detection
Context Features: Relative/context only, never hard gate
```

### **Accuracy Targets - REVISED**
- **Execution Latency:** <200ms end-to-end (p95)
- **False Signal Reduction:** ≥70% vs baseline (realistic target)
- **Win Rate:** Monitor as KPI, focus on drawdown control
- **Precision@Entry:** ≥0.5R without hitting -0.25R first
- **False Breakout Rate:** <10% (M1), <5% (M5) (realistic targets)

### **Portfolio-Level SLOs (Primary Focus)**
- **Daily Drawdown:** ≤2.0% (hard stop at 1.25%)
- **Weekly Drawdown:** ≤5.0%
- **Peak-to-Trough:** ≤12%
- **Latency p95:** ≤200ms sustained
- **Data Freshness:** All TFs within 2× cadence

### **Risk Controls**
```
Per-Trade Lot Size Limits:
- BTCUSD/XAUUSD: ≤0.02 lots maximum
- Forex Pairs: ≤0.04 lots maximum
- Cross Pairs: ≤0.03 lots maximum

Per-Trade Risk:
- FX Majors: 0.5% (default)
- XAU/BTC: 0.75% (default)
- Cross Pairs: 0.4% (default)

Drawdown Limits:
- Daily DD: ≤2.0% (hard stop at 1.25%)
- Weekly DD: ≤5.0%
- Monthly DD: ≤8-10%
- Peak-to-Trough: ≤12%

Circuit Breakers:
- Daily loss ≥1.5% → pause 60min
- Daily loss ≥2.0% → stop for day
- Weekly loss ≥3.5% → halve risk
- Weekly loss ≥5% → stop for week
```

---

## 🗄️ **DATABASE ARCHITECTURE & MANAGEMENT**

### **Multi-Timeframe Database Schema**
```sql
-- Multi-timeframe structure analysis
CREATE TABLE mtf_structure_analysis (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp_utc DATETIME NOT NULL,
    structure_type TEXT, -- 'BOS', 'CHOCH', 'OB', 'FVG'
    structure_data JSON,
    confidence_score REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- M1 precision filters
CREATE TABLE m1_precision_filters (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timestamp_utc DATETIME NOT NULL,
    vwap_reclaim BOOLEAN,
    delta_spike BOOLEAN,
    micro_bos BOOLEAN,
    atr_ratio_valid BOOLEAN,
    spread_valid BOOLEAN,
    filters_passed INTEGER,
    filter_score REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Multi-timeframe trade decisions
CREATE TABLE mtf_trade_decisions (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timestamp_utc DATETIME NOT NULL,
    h4_bias TEXT, -- 'BULLISH', 'BEARISH', 'NEUTRAL'
    h1_bias TEXT,
    m30_setup TEXT,
    m15_setup TEXT,
    m5_structure TEXT,
    m1_confirmation BOOLEAN,
    decision TEXT, -- 'BUY', 'SELL', 'HOLD'
    confidence REAL,
    risk_reward REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- DTMS multi-timeframe exits
CREATE TABLE mtf_dtms_exits (
    id INTEGER PRIMARY KEY,
    ticket INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    timestamp_utc DATETIME NOT NULL,
    h4_signal TEXT,
    h1_signal TEXT,
    m30_signal TEXT,
    m15_signal TEXT,
    m5_signal TEXT,
    m1_signal TEXT,
    exit_action TEXT, -- 'CLOSE', 'PARTIAL', 'TIGHTEN_SL'
    exit_percentage REAL,
    new_sl_price REAL,
    new_tp_price REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Performance metrics by timeframe
CREATE TABLE mtf_performance_metrics (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    date_utc DATE NOT NULL,
    total_signals INTEGER,
    successful_signals INTEGER,
    win_rate REAL,
    avg_rr REAL,
    max_drawdown REAL,
    latency_p50 REAL,
    latency_p95 REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### **Database Management Strategy**
```
Data Retention Policy:
- M1 data: Keep 7 days (high frequency)
- M5 data: Keep 30 days
- M15+ data: Keep 90 days
- Structure analysis: Keep 1 year
- Performance metrics: Keep 2 years

Compression Strategy:
- M1 data: Compress after 3 days
- Historical data: Archive after 30 days
- Index optimization: Daily maintenance

Query Performance:
- Primary indexes on (symbol, timeframe, timestamp)
- Composite indexes for multi-timeframe queries
- Partitioning by symbol for large datasets
```

### **Database Integration Points**
```
Real-Time Data Flow:
MT5 Ticks → M1 Processing → Database Storage
MT5 Bars → Multi-TF Analysis → Database Storage
Structure Detection → Decision Engine → Database Storage
DTMS Actions → Exit Management → Database Storage

Historical Analysis:
Database → Backtesting Engine → Performance Metrics
Database → Optimization Engine → Parameter Tuning
Database → Monitoring System → Alert Generation
```

---

## 🏗️ **TECHNICAL ARCHITECTURE**

### **Data Requirements & Sources**
```
Real-Time VWAP: ✅ Compute from MT5 ticks
Volume Delta: ✅ Proxy from tick classification  
Order Book: ✅ Binance depth streams (BTCUSD only)
MT5 Built-ins: ✅ ATR, EMA, RSI, etc.
Custom Features: ✅ VWAP, micro-BOS, OB/FVG, liquidity
Binance Integration: ✅ Depth streams + REST endpoints for BTCUSD
```

### **Ingestion Cadence**
```
M1: 1-second tick clusters → VWAP/delta + EMA(3) smoothing
M5: 5-10 second refresh
M15/M30: 30-60 second refresh  
H1/H4: 5-15 minute refresh
```

### **M1 Filter Requirements (≥3 must pass)**
```
1. VWAP reclaim/loss within symbol-specific threshold
2. Volume delta spike > symbol-specific threshold
3. Micro BOS close + retest validation
4. ATR ratio: M1 < symbol-specific × M5 ATR
5. Spread < median(20) for symbol
```

---

## 🧠 **MULTI-TIMEFRAME DECISION TREE**

### **Hierarchical Logic (H4 > H1 > M30 > M15 > M5 > M1)**

```
[Trade Active]
     ↓
[H4/H1 Bias Valid?] → No → Close Fully
     ↓ Yes
[M30/M15 Liquidity Sweep?] → Yes → Take Partial (30-50%)
     ↓
[M5/M1 Structural Weakness?] → Yes → Tighten Stop
     ↓
[M1 VWAP Break + Delta Divergence?] → Yes → Exit Fully
     ↓
Otherwise → Continue Monitoring
```

### **Timeframe Roles**
| Timeframe | Role | DTMS Action | Exit Trigger |
|-----------|------|-------------|--------------|
| **H4** | Macro bias | Hold/extend targets | CHOCH reversal |
| **H1** | Trend confirmation | Adjust trail distance | EMA200 break |
| **M30** | Intraday liquidity | Partial scaling | OB reentry |
| **M15** | Setup validation | Reduce position | Liquidity sweep |
| **M5** | Structure shift | Tighten stops | BOS/CHOCH |
| **M1** | Execution precision | Final exit | VWAP + Delta |

---

## 🔧 **IMPLEMENTATION PHASES**

### **Phase 1: Core Framework (Week 1)**
**Priority Symbols:** BTCUSDc, XAUUSDc, EURUSDc (Week 1) → USDCHFc, AUDUSDc, USDCADc, NZDUSDc (Week 2) → EURJPYc, GBPJPYc, EURGBPc (Week 3) → BTCUSDc, XAUUSDc (Week 4)

**Deliverables (REVISED SCOPE):**
- **H1→M15→M5** structure analysis engine (H4/M30 added later)
- **M1 confirmation filters** (post-confirm only)
- Basic multi-timeframe decision tree
- Symbol-specific parameter configuration
- **Hot-path architecture** with ring buffers and async writes
- **Binance Order Book Integration (BTCUSDc) - CONTEXT ONLY**
  - WebSocket depth streams (`btcusdt@depth`) for context features
  - REST depth endpoints (`/api/v3/depth`) for snapshots
  - **Never block decisions on Binance freshness**
  - Evaluate marginal lift before hardwiring

**Testing Framework:**
- **Unit Tests:** Structure detection algorithms, M1 filters, database operations
- **Integration Tests:** MT5 data flow, Binance WebSocket stability, database performance
- **Performance Tests:** Latency measurement, memory usage, CPU utilization
- **Symbol-Specific Tests:** Parameter validation for all 12 symbols
- **Binance Tests:** Order book data accuracy, WebSocket reconnection, depth analysis

**Success Criteria (REVISED):**
- Structure detection accuracy >75% (realistic target)
- M1 filter pass rate >60% (post-confirm only)
- Latency <200ms p95 on test hardware
- Hot-path architecture stable (no blocking on DB)
- **Binance integration stable with <10% data loss (context only)**
- **Shadow mode validation ready**

### **Phase 2: Advanced Filters + Database (Week 2)**
**Symbols:** USDCHF, AUDUSD, USDCAD, NZDUSD (forex minors)

**Deliverables:**
- Real-time VWAP calculation from MT5 ticks
- Volume delta proxy implementation
- ATR ratio and spread filters
- Symbol-specific optimization tuning
- Multi-timeframe database management system
- Data retention and compression
- **Enhanced Binance Integration**
  - Large order detection algorithms
  - Support/resistance level identification
  - Market depth visualization
  - Integration with MT5 M1 data

**Testing Framework:**
- **Unit Tests:** VWAP calculation accuracy, delta proxy logic, filter algorithms
- **Integration Tests:** MT5 tick processing, Binance-MT5 data fusion, database operations
- **Performance Tests:** VWAP computation speed, database query optimization
- **Accuracy Tests:** Filter effectiveness, false signal reduction measurement
- **Binance Advanced Tests:** Large order detection, depth analysis accuracy, data fusion quality

**Success Criteria:**
- VWAP accuracy within ±0.1σ
- Delta spike detection >90% accuracy
- False signal reduction >80%
- Database performance <50ms queries
- **Binance order book analysis accuracy >95%**
- **Large order detection precision >85%**

### **Phase 3: DTMS Integration + Database (Week 3)**
**Symbols:** EURJPY, GBPJPY, EURGBP (cross pairs)
**Integration:** Replace current Intelligent Exits

**Deliverables:**
- Multi-timeframe exit logic
- Dynamic stop management
- Partial scaling based on structure
- Circuit breaker implementation
- Database integration for trade management
- Historical analysis data storage

**Success Criteria:**
- Exit precision >80%
- R:R improvement >1:3
- Drawdown control within limits
- Database handles all trade operations

### **Phase 4: Optimization & Validation (Week 4)**
**Symbols:** BTCUSD, XAUUSD (crypto/commodity with Binance integration)
**Validation:** 12-month backtest + 2-week paper trading

**Deliverables:**
- Performance tuning
- Latency optimization
- Backtesting validation
- Production monitoring
- Database optimization and indexing
- Data management automation

**Success Criteria:**
- Win rate ≥80% with R:R ≥1:3
- Latency <200ms sustained
- All SLOs met in production
- Database performance optimized

---

## 📈 **EXPECTED PERFORMANCE IMPROVEMENTS**

### **Baseline vs Multi-Timeframe**
| Metric | Current System | Multi-Timeframe Target | Improvement |
|--------|----------------|------------------------|--------------|
| **Win Rate** | 72-74% | 80-82% | +8-10% |
| **Avg R:R** | 1:2.2 | 1:3.1-1:3.4 | +40-55% |
| **Entry Precision** | Baseline | +25-30% | +25-30% |
| **False Breakouts** | Baseline | -35-45% | -35-45% |
| **Stop Size** | Baseline | -15-20% | -15-20% |
| **Latency** | Variable | <200ms | Consistent |

### **Symbol-Specific Benefits**
```
BTCUSDc: Crypto volatility → Precision +30%, R:R +50%
XAUUSDc: Macro sensitivity → News protection +40%
EURUSDc: High liquidity → Execution +25%
GBPUSDc: Volatility → Risk management +35%
Cross Pairs: Correlation → Diversification +20%
```

---

## 🚨 **RISK MANAGEMENT INTEGRATION**

### **Dynamic Position Sizing**
```
H4+H1 Aligned: 100% position size
H1 Only: 75% position size
M30+M15 Only: 50% position size  
M5+M1 Only: 25% position size
```

### **Stop Management by Timeframe**
```
H4 Structure Intact: Allow 1.5× ATR trailing
H1 Structure Weakening: Tighten to 1.0× ATR
M30 OB Reentry: Move to breakeven
M5 CHOCH: Tighten to 0.5× ATR
```

### **Circuit Breaker Logic**
```
Latency SLO Breach (p95 >250ms for 10min) → Degrade to confirm-only
Data Freshness Breach (any TF stale >2× cadence) → Exits only
Daily DD ≥1.5% → Pause new entries 60min
Weekly DD ≥3.5% → Halve per-trade risk
```

---

## 📊 **MONITORING & ALERTS**

### **SLI Metrics (Every Minute)**
```
Latency: p50/p95 execution time
Freshness: TF staleness detection
Filter Pass Rate: M1 confirmation rate
Decision Counts: By timeframe cause
Exit Types: Partial vs full exits
```

### **Alert Thresholds**
```
Latency p95 >250ms for 10min → Alert
Freshness: Any TF stale >2× cadence → Alert
Filter pass rate drops >15% vs 7-day mean → Alert
Drawdown breaches → Immediate alert + action
```

---

## 🎯 **VALIDATION PROTOCOL**

### **Backtesting (12 months, 4 symbols)**
- **Symbols:** EURUSDc, GBPUSDc, XAUUSDc, BTCUSDc
- **Metrics:** Win rate, R:R distribution, drawdown, false breakout rate
- **Target:** All performance specifications met

### **Paper Trading (4-6 weeks)**
- **Live data:** No execution, full logging
- **Latency validation:** Confirm <200ms on production hardware
- **Decision logging:** Compare against baseline actions

### **Shadow Mode Implementation - DETAILED SPECS**
- **Duration:** 2-3 weeks parallel operation
- **Comparison:** DTMS vs Intelligent Exits decisions
- **Logging:** "would-close/partial" decisions with reasons and feature vector hashes
- **Metrics:** PNL comparison, decision accuracy, latency, queue backpressure
- **Go/No-Go Criteria:** Drawdown stability, queue backpressure incidence, p95 latency
- **Rollback:** Automatic if any breaker triggers twice in 5-day window

---

## 🏁 **SUCCESS CRITERIA SUMMARY**

### **Technical Performance (REVISED)**
- ✅ Latency <200ms end-to-end (p95)
- ✅ False signal reduction ≥70% (realistic)
- ✅ Drawdown control within limits (primary focus)
- ✅ All 12 symbols optimized
- ✅ Shadow mode validation complete

### **Risk Management**
- ✅ Drawdown limits enforced
- ✅ Circuit breakers functional
- ✅ Dynamic position sizing
- ✅ Multi-timeframe stop management

### **System Integration**
- ✅ Current Intelligent Exits replaced
- ✅ DTMS enhanced with multi-timeframe logic
- ✅ All symbols operational
- ✅ Production monitoring active

**This framework transforms your trading system into a professional-grade institution capable of competing with prop firms and hedge funds.**

---

## 🚀 **READY TO PROCEED?**

**Next Steps:**
1. **Confirm symbol priorities** (BTCUSDc, XAUUSDc, EURUSDc first)
2. **Approve implementation timeline** (4-week accelerated approach)
3. **Begin Phase 1 development** (Core framework + database)
4. **Set up monitoring infrastructure** (SLI tracking)

**Questions for Final Confirmation:**
- Any adjustments to symbol-specific parameters?
- Timeline acceptable for 4-week implementation?
- Risk management thresholds appropriate?
- Ready to begin Phase 1 development with BTCUSDc, XAUUSDc, EURUSDc?
