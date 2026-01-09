# Range Scalping System - Resource Usage Estimates

**Date:** 2025-11-02  
**Based on:** Master Plan V2.1 + Gap Analysis integration

---

## 📊 **RESOURCE USAGE SUMMARY**

| Component | CPU Usage | RAM Usage | SSD I/O | Network I/O |
|-----------|-----------|-----------|---------|-------------|
| **Monitoring Loop** | ~0.05-0.1% | ~5-10 MB | Minimal | Low |
| **State Persistence** | <0.01% | ~1-2 MB | ~5-10 KB/5min | None |
| **Range Detection** | ~0.1-0.3% | ~10-20 MB | None | Low |
| **Data Quality Checks** | ~0.05-0.1% | ~2-3 MB | None | Low |
| **Error Handling** | <0.01% | ~1-2 MB | None | None |
| **Trade Registration** | <0.01% | ~0.5 MB/trade | ~2-3 KB/trade | None |
| **TOTAL (Normal Load)** | **~0.2-0.5%** | **~20-40 MB** | **~5-10 KB/5min** | **Low** |
| **TOTAL (Peak Load)** | **~1-2%** | **~50-80 MB** | **~20 KB/5min** | **Medium** |

---

## 🔍 **DETAILED BREAKDOWN**

### **1. Monitoring Loop (Background Thread)**

**Frequency:** Every 5 minutes (300 seconds)  
**Active CPU Time:** ~50-100ms per check cycle

**Per Check Cycle:**
- Iterate through active trades: <1ms per trade
- Get current prices (MT5 API): ~20-50ms per symbol (network latency)
- Range invalidation check: ~10-20ms per trade
- Early exit condition evaluation: ~10-30ms per trade
- State save (if changed): ~5-10ms

**Example with 3 active trades:**
- Total per cycle: ~150-300ms
- CPU usage: 300ms / 300,000ms = **0.1% per cycle**
- Average continuous: **~0.03% CPU**

**Memory:**
- Thread stack: ~2 MB
- Active trades dict: ~1-2 KB per trade
- Market data cache: ~5-10 MB (cached prices, indicators)
- **Total: ~5-15 MB**

**SSD I/O:**
- State file write: ~2-5 KB per save (every 5 min or on change)
- Atomic write (temp → rename): Minimal overhead
- **Total: ~5-10 KB every 5 minutes**

---

### **2. State Persistence (range_scalp_trades_active.json)**

**File Size Calculation:**
- Per trade: ~2-3 KB (JSON with metadata, range data)
- 1 active trade: ~2-3 KB
- 5 active trades: ~10-15 KB
- 10 active trades: ~20-30 KB

**Save Frequency:**
- Every 5 minutes (periodic backup)
- Immediately after state changes (registration, exit, breakeven move)

**SSD I/O:**
- Normal (1-2 state changes/hour): ~3-4 saves/hour × 3 KB = ~9-12 KB/hour
- Active (5-10 state changes/hour): ~10-12 saves/hour × 3 KB = ~30-36 KB/hour
- **Daily: ~200-500 KB**

**Memory:**
- In-memory dict: ~1-2 KB per trade
- File buffer during save: ~5-10 KB
- **Total: ~2-5 MB (for up to 20 active trades)**

**CPU:**
- JSON serialization: <1ms per trade
- File write: ~2-5ms (atomic write)
- **Total: <0.01% CPU**

---

### **3. Range Detection Calculations**

**Frequency (Optimized Schedule):**
- M15 structure: Every 15 minutes
- M5 micro-range: Every 5 minutes (if price moved >0.1%)
- H1 regime: Once per hour

**CPU per Calculation:**
- Range boundary detection: ~50-100ms (swing detection, gap calculation)
- Range validation: ~20-30ms
- Nested range detection: ~30-50ms (if multiple timeframes)
- **Total: ~100-180ms per calculation**

**Frequency Examples:**
- Low activity (price moves <0.1%): ~1 calculation per hour = 180ms/hour = **0.005% CPU**
- Normal activity: ~4-6 calculations/hour = 720-1080ms/hour = **0.02-0.03% CPU**
- High activity: ~12-15 calculations/hour = 2160-2700ms/hour = **0.06-0.08% CPU**

**Memory:**
- RangeStructure objects: ~5-10 KB per range (with nested ranges)
- Cached range data: ~20-50 KB per symbol
- **Total: ~10-20 MB**

---

### **4. Data Quality Checks**

**Frequency:**
- Before every trade analysis (on user request)
- During monitoring loop (if stale data detected)

**CPU per Check:**
- MT5 candle freshness: ~20-30ms (API call + timestamp check)
- VWAP recency: ~5-10ms (in-memory check)
- Binance order flow: ~50-100ms (API call, optional)
- News calendar: ~10-20ms (cached check)
- **Total: ~85-160ms per check**

**Frequency:**
- User-initiated analysis: ~1-5 checks/hour = 160-800ms/hour = **0.004-0.02% CPU**
- Monitoring loop validation: ~1-2 checks/hour = 160-320ms/hour = **0.004-0.009% CPU**

**Memory:**
- Quality report cache: ~2-3 MB
- **Total: ~2-3 MB**

**Network I/O:**
- MT5 API call: ~1-2 KB per request
- Binance API call: ~2-5 KB per request (if enabled)
- **Total: ~3-7 KB per check**

---

### **5. Error Handling & State Management**

**CPU:**
- Error classification: <0.1ms per error
- Auto-disable check: ~1-2ms per critical error
- **Total: <0.01% CPU (negligible)**

**Memory:**
- Error history deque: ~1-2 MB (last 100 errors)
- Critical error window: ~0.1 MB (last 10 errors)
- ErrorHandler state: ~0.5 MB
- **Total: ~1-2 MB**

---

### **6. Trade Registration (Per Trade)**

**CPU per Registration:**
- Dict creation: <0.1ms
- RangeStructure.to_dict(): ~0.5-1ms
- State save: ~5-10ms
- **Total: ~5-10ms per trade**

**Memory per Trade:**
- Trade metadata dict: ~1-2 KB
- Range data (serialized): ~1-2 KB
- **Total: ~2-4 KB per trade**

**SSD I/O per Trade:**
- JSON write (atomic): ~2-3 KB per trade

**Frequency:**
- Normal: ~1-3 trades/day = 6-12 KB/day
- Active: ~5-10 trades/day = 20-40 KB/day

---

## 📈 **SCALING SCENARIOS**

### **Scenario 1: Light Usage (1-2 Active Trades)**
- **CPU:** ~0.1-0.3%
- **RAM:** ~15-25 MB
- **SSD:** ~10-20 KB/hour
- **Network:** Low (periodic MT5 API calls)

### **Scenario 2: Normal Usage (3-5 Active Trades)**
- **CPU:** ~0.2-0.5%
- **RAM:** ~25-40 MB
- **SSD:** ~20-30 KB/hour
- **Network:** Low-Medium

### **Scenario 3: Active Usage (6-10 Active Trades, Multiple Symbols)**
- **CPU:** ~0.5-1.5%
- **RAM:** ~40-70 MB
- **SSD:** ~40-60 KB/hour
- **Network:** Medium (more frequent API calls)

### **Scenario 4: Peak Load (10+ Active Trades, High Volatility)**
- **CPU:** ~1-2%
- **RAM:** ~70-100 MB
- **SSD:** ~60-100 KB/hour
- **Network:** Medium-High

---

## 🆚 **COMPARISON TO EXISTING SYSTEM**

Based on existing system analysis:

**Current System (Without Range Scalping):**
- CPU: ~15-25% (ChatGPT bot, desktop agent, unified pipeline, DTMS, etc.)
- RAM: ~500-800 MB
- SSD: ~100-200 writes/minute (database, logs)

**With Range Scalping Added:**
- CPU: ~15.2-25.5% (+0.2-0.5%)
- RAM: ~520-840 MB (+20-40 MB)
- SSD: ~100-200 writes/minute + 1 write/5min (state file)

**Impact:**
- ✅ **CPU: Negligible** (<2% increase of current usage)
- ✅ **RAM: Minor** (~3-5% increase)
- ✅ **SSD: Negligible** (<0.01% of current I/O)

---

## 💻 **SYSTEM REQUIREMENTS**

### **Minimum Requirements (Light Usage):**
- **CPU:** Any modern CPU (2+ cores)
- **RAM:** +50 MB available (system already uses 500-800 MB)
- **SSD:** +1 MB free space (for state file)
- **Network:** Stable internet (for MT5/Binance API)

### **Recommended (Normal-Active Usage):**
- **CPU:** 4+ cores (for concurrent processing)
- **RAM:** +100 MB available
- **SSD:** +5 MB free space
- **Network:** Low-latency connection (<100ms to MT5)

### **Optimal (Peak Load):**
- **CPU:** 6+ cores (for multiple monitoring threads)
- **RAM:** +200 MB available
- **SSD:** +10 MB free space (for state file + backups)
- **Network:** Low-latency connection (<50ms to MT5)

---

## 🔋 **BATTERY IMPACT (Laptop)**

**Monitoring Loop:**
- Wakes CPU every 5 minutes: ~100ms active time
- CPU wakes from sleep: Minimal overhead
- **Battery impact: Negligible** (<0.1% per hour)

**State Saves:**
- Writes to SSD: ~2-5ms per save
- SSD power draw: ~0.1W for 5ms = **Negligible**

**Network Activity:**
- MT5 API calls: ~20-50ms per call
- Network adapter power: ~0.5W for 50ms = **Negligible**

**Total Battery Impact:**
- Additional power draw: <0.1W average
- Battery life reduction: **<1% per hour** (essentially negligible)

---

## ⚡ **OPTIMIZATION FEATURES (Already Built-In)**

The system includes optimizations to minimize resource usage:

1. **Lazy Evaluation:**
   - Range detection only recalculates if price moved >0.1%
   - Reduces unnecessary calculations by ~70-80%

2. **Scheduled Recalculations:**
   - M15: Every 15 min (not every minute)
   - H1: Once per hour (not continuous)
   - Reduces CPU usage by ~60-70%

3. **Efficient State Saves:**
   - Only saves if state changed OR >5 minutes elapsed
   - Atomic writes (temp → rename) prevent corruption without extra I/O

4. **Caching:**
   - Market data cached for 60 seconds
   - Range data cached between checks
   - Reduces API calls by ~50-60%

5. **Thread Safety:**
   - Minimizes lock time (copy data, process outside lock)
   - Reduces contention and CPU overhead

---

## 📊 **MONITORING & TRACKING**

**You can track actual resource usage:**
- Performance logging (Gap #19): Configurable latency tracking
- System metrics: Existing `SystemMonitor` class can track range scalping CPU/RAM
- State file size: Monitor `data/range_scalp_trades_active.json` size

**Expected Growth:**
- State file: Grows ~2-3 KB per active trade
- Memory: Grows ~2-4 KB per active trade
- No unbounded growth (trades are removed after exit)

---

## ✅ **CONCLUSION**

**Resource Impact: VERY LOW**

The range scalping system adds:
- **CPU:** <0.5% average, <2% peak (negligible)
- **RAM:** ~20-40 MB normal, ~70-100 MB peak (minor)
- **SSD:** ~50-100 KB/hour (negligible)
- **Network:** Low-Medium (similar to existing system)
- **Battery:** <1% per hour impact (negligible)

**Verdict:** ✅ **Safe to run on any modern laptop/desktop alongside existing system.**

The system is designed to be lightweight with built-in optimizations. Resource usage scales linearly with number of active trades, but remains minimal even at peak load.

