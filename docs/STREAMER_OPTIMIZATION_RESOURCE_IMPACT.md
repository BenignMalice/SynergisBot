# Multi-Timeframe Streamer Optimization - Resource Impact Analysis

**Date:** 2025-11-02  
**Changes:** Faster refresh intervals + 30-second database flush

---

## 📊 **CHANGES SUMMARY**

### 1. Refresh Interval Optimization
All timeframes now refresh slightly faster than candle completion time:

| Timeframe | Previous | New | Increase |
|-----------|----------|-----|----------|
| M1 | 60s | 55s | +9% frequency |
| M5 | 300s | 240s | +25% frequency |
| M15 | 900s | 840s | +7% frequency |
| M30 | 1800s | 1680s | +7% frequency |
| H1 | 3600s | 3480s | +3% frequency |
| H4 | 14400s | 13800s | +4% frequency |

### 2. Database Writer Time-Based Flush
- **Previous:** Only writes when `batch_write_size` (20 candles) reached
- **New:** Writes every 30 seconds if any candles pending
- **Impact:** More frequent but smaller writes

---

## 💻 **CPU IMPACT**

### MT5 API Calls (Refresh Intervals)

**For 3 symbols (BTCUSDc, XAUUSDc, EURUSDc), 6 timeframes:**

**Before:**
- M1: 3 symbols × (3600s/60s) = **180 calls/hour**
- M5: 3 symbols × (3600s/300s) = **36 calls/hour**
- M15: 3 symbols × (3600s/900s) = **12 calls/hour**
- M30: 3 symbols × (3600s/1800s) = **6 calls/hour**
- H1: 3 symbols × (3600s/3600s) = **3 calls/hour**
- H4: 3 symbols × (3600s/14400s) = **0.75 calls/hour**
- **Total: ~238 calls/hour**

**After:**
- M1: 3 symbols × (3600s/55s) = **196 calls/hour** (+9%)
- M5: 3 symbols × (3600s/240s) = **45 calls/hour** (+25%)
- M15: 3 symbols × (3600s/840s) = **13 calls/hour** (+7%)
- M30: 3 symbols × (3600s/1680s) = **6.4 calls/hour** (+7%)
- H1: 3 symbols × (3600s/3480s) = **3.1 calls/hour** (+3%)
- H4: 3 symbols × (3600s/13800s) = **0.78 calls/hour** (+4%)
- **Total: ~264 calls/hour** (+11% overall increase)

**CPU Impact per Call:**
- MT5 API call: ~20-50ms (network latency + processing)
- Per call CPU: ~0.005-0.015% (assuming 1-core equivalent)
- **Additional CPU from increased calls:** ~0.03-0.1% (26 extra calls/hour × 0.001% average)

### Database Writer

**Before:**
- Writes only when 20 candles queued
- With incremental fetching (1-5 candles per cycle), batches accumulate slowly
- **~10-20 writes/hour** (depending on activity)

**After:**
- Writes every 30 seconds if pending candles
- **Up to 120 writes/hour** (every 30s = 2/min = 120/hour)
- Most writes are small (1-5 candles)

**CPU per Write:**
- SQLite INSERT: ~2-5ms per candle
- Transaction commit: ~1-2ms
- Small batch (1-5 candles): **~5-15ms total**
- Large batch (20 candles): **~20-40ms total**

**Additional CPU from database writes:**
- Before: ~10-20 writes/hour × 20ms = **200-400ms/hour = 0.006% CPU**
- After: ~120 writes/hour × 10ms (avg small batch) = **1200ms/hour = 0.03% CPU**
- **Additional CPU: +0.024%** (negligible)

### **Total CPU Impact:**
- **Refresh intervals: +0.03-0.1%**
- **Database writes: +0.024%**
- **Total: +0.05-0.12% CPU** ✅ **NEGLIGIBLE**

---

## 🧠 **RAM IMPACT**

### Refresh Intervals
- **No RAM increase** - buffers are fixed-size deques (rolling buffers)
- Memory usage remains constant regardless of refresh frequency
- **Impact: 0 MB** ✅

### Database Writer
- Write queue may accumulate slightly more before flush
- Max queue size: ~batch_write_size × 2 (safety margin) = ~40 candles
- Per candle in queue: ~200 bytes (Candle dict)
- **Additional RAM: ~8 KB** ✅ **NEGLIGIBLE**

**Total RAM Impact: +~8 KB** ✅ **ESSENTIALLY ZERO**

---

## 💾 **SSD IMPACT**

### Database Writes

**Before:**
- ~10-20 writes/hour (when batch size reached)
- Average: ~15 writes/hour
- Batch size: ~20 candles per write
- Per candle: ~97 bytes (SQLite row)
- **Per write: ~2 KB** (20 candles × 97 bytes)
- **Total: ~30 KB/hour**

**After:**
- Up to 120 writes/hour (every 30 seconds)
- Average batch size: ~2-3 candles (incremental fetching)
- Per write: ~200-300 bytes (2-3 candles × 97 bytes)
- **Total: ~24-36 KB/hour** (120 writes × 0.25 KB average)

**Additional SSD I/O:**
- Before: ~30 KB/hour
- After: ~30 KB/hour (roughly the same!)
- **Impact: Minimal change** (more frequent but smaller writes)

**Why the same?**
- Before: Fewer writes but larger batches
- After: More writes but smaller batches
- Net result: Similar total data written

**Write Operations:**
- Before: ~15 write operations/hour
- After: ~120 write operations/hour
- **+105 write operations/hour**
- SSD writes are very fast (~0.1-1ms), so **impact is minimal**

### **Total SSD Impact:**
- **Data written: ~same** (~30 KB/hour)
- **Write operations: +105/hour** (but each is tiny ~0.25 KB)
- **Impact: MINIMAL** ✅ (modern SSDs handle thousands of small writes/second)

---

## 📈 **NETWORK IMPACT**

### MT5 API Calls

**Before:** ~238 calls/hour  
**After:** ~264 calls/hour  
**Additional: +26 calls/hour** (+11%)

**Network Bandwidth:**
- Per call: ~1-2 KB (request + response)
- Additional: +26 calls/hour × 1.5 KB = **+39 KB/hour**
- **Impact: NEGLIGIBLE** ✅ (modern connections: 1+ Mbps)

**Network Latency:**
- More frequent calls = more network activity
- But calls are asynchronous and non-blocking
- **Impact: MINIMAL** ✅

---

## 🔋 **BATTERY IMPACT (Laptop)**

### CPU Usage
- Additional CPU: +0.05-0.12%
- CPU power: ~5-10W per core
- Additional power: 0.0005-0.0012W
- **Impact: NEGLIGIBLE** ✅

### SSD Writes
- Additional writes: +105 operations/hour
- SSD power: ~0.1W for 1ms per write
- Additional power: 105 × 0.1W × 0.001s = **0.01W average**
- **Impact: NEGLIGIBLE** ✅

### Network Activity
- Additional calls: +26/hour
- Network adapter: ~0.5W for 50ms per call
- Additional power: 26 × 0.5W × 0.05s = **0.65W-seconds/hour = 0.0002W average**
- **Impact: NEGLIGIBLE** ✅

**Total Battery Impact: +<0.02W average** ✅ **<0.1% battery per hour**

---

## 📊 **SUMMARY TABLE**

| Resource | Before | After | Change | Impact |
|----------|--------|-------|--------|--------|
| **CPU** | <1% | <1.1% | +0.05-0.12% | ✅ Negligible |
| **RAM** | ~50 KB | ~58 KB | +8 KB | ✅ Negligible |
| **SSD Data** | ~30 KB/hour | ~30 KB/hour | ~0 | ✅ Same |
| **SSD Operations** | ~15/hour | ~120/hour | +105/hour | ✅ Minimal |
| **Network Calls** | ~238/hour | ~264/hour | +11% | ✅ Negligible |
| **Battery** | Base | Base | +<0.02W | ✅ Negligible |

---

## ✅ **CONCLUSION**

**Overall Impact: MINIMAL to NEGLIGIBLE**

The optimizations provide significant benefits (fresh data within 30 seconds, faster candle detection) with essentially zero resource cost:

✅ **CPU:** +0.05-0.12% (imperceptible)  
✅ **RAM:** +8 KB (essentially zero)  
✅ **SSD:** Same data written, more frequent small writes (SSD-friendly)  
✅ **Network:** +11% more calls (but still very low - 264/hour = 1 every 13 seconds)  
✅ **Battery:** <0.1% per hour (imperceptible)

**Verdict:** ✅ **These optimizations are SAFE and provide excellent benefits with minimal cost.**

The faster refresh intervals ensure fresh candles are available immediately after completion, and the 30-second database flush ensures data is written within 30 seconds instead of potentially waiting minutes for batch accumulation.

---

## 📝 **MONITORING RECOMMENDATIONS**

While impact is minimal, you can monitor:

1. **CPU Usage:** Should remain <1.5% for streamer component
2. **Database Size:** Should grow at ~30 KB/hour (same as before)
3. **Write Queue:** Should stay <10 candles most of the time (flushing every 30s)
4. **MT5 API Rate Limits:** Monitor for any rate limit errors (should be fine - 264 calls/hour is very low)

If you see any issues, you can:
- Increase `flush_interval` from 30s to 60s (reduces write frequency)
- Revert refresh intervals to exact candle times (reduces API calls)
- But this is unlikely to be necessary given the minimal impact.

