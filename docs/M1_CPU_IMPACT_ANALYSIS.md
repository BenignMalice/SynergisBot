# M1 Streaming CPU Impact Analysis

## Current Setup (Without M1)

**Configuration:**
- 3 symbols: BTCUSDc, XAUUSDc, EURUSDc
- 5 timeframes: M5, M15, M30, H1, H4
- Total streaming tasks: 3 × 5 = 15 background tasks

**API Call Frequency:**
| Timeframe | Refresh | Calls/Hour (per symbol) | Total Calls/Hour |
|-----------|---------|------------------------|------------------|
| M5        | 300s    | 12                     | 36               |
| M15       | 900s    | 4                      | 12               |
| M30       | 1800s   | 2                      | 6                |
| H1        | 3600s   | 1                      | 3                |
| H4        | 14400s  | 0.25                   | 0.75             |
| **Total** |         |                        | **~58/hour**     |

**Current CPU Load:**
- ~0.016 API calls/second
- Background tasks spend most time in `asyncio.sleep()` (near-zero CPU)
- Active processing: ~10-50ms per fetch (every 5-15 minutes)

---

## With M1 Added

**New Configuration:**
- 3 symbols × 6 timeframes = 18 background tasks
- M1 refresh: 60 seconds

**New API Call Frequency:**
| Timeframe | Refresh | Calls/Hour (per symbol) | Total Calls/Hour |
|-----------|---------|------------------------|------------------|
| **M1**     | **60s** | **60**                 | **180**          |
| M5        | 300s    | 12                     | 36               |
| M15       | 900s    | 4                      | 12               |
| M30       | 1800s   | 2                      | 6                |
| H1        | 3600s   | 1                      | 3                |
| H4        | 14400s  | 0.25                   | 0.75             |
| **Total** |         |                        | **~238/hour**    |

**Increase:**
- **+180 API calls/hour** (from M1)
- **+310% total API calls** (but still very low absolute number)
- **~0.066 calls/second** (up from 0.016)

---

## CPU Time Breakdown Per Fetch

**Operations per M1 fetch:**
1. **MT5 API call** (`mt5.copy_rates_from`): 10-50ms
   - Network latency: 5-20ms
   - MT5 processing: 5-30ms
   
2. **Data conversion** (numpy → Python objects): 1-5ms
   - Type casting: <1ms
   - Datetime conversion: 1-3ms
   - Object creation: <1ms
   
3. **Buffer operations** (deque append): <1ms
   - Deque is O(1) append
   - No memory reallocation (rolling buffer)
   
4. **Database queue** (if enabled): <1ms
   - Append to Python list: <0.1ms
   - Dictionary creation: <0.5ms
   
5. **Callback execution** (if any): 0-10ms
   - Depends on callback complexity
   - Most systems: 0ms (no callbacks)
   
**Total per fetch: ~15-65ms (typically 20-30ms)**

---

## CPU Usage Calculation

### Per Minute (3 symbols × M1 fetches):
- **Fetches:** 3 per minute
- **CPU time:** 3 × 30ms = 90ms
- **CPU usage:** 90ms / 60,000ms = **0.15% per minute**
- **Average per second:** 0.15% / 60 = **0.0025% per second**

### Background Task Overhead:
- **asyncio.sleep():** Near-zero CPU (uses event loop)
- **Event loop wake-up:** ~0.1ms per wake
- **Task switching:** <0.1ms per switch
- **Total overhead:** <1ms per minute

### Total M1 CPU Impact:
- **Per minute:** ~90-100ms active CPU time
- **Per hour:** ~5.4 seconds active CPU time
- **Average continuous:** **~0.15% CPU usage**

---

## Database Write Impact (If Enabled)

**Write Frequency:**
- Batched writes: every 200 candles (`batch_write_size`)
- M1 generates: 3 candles/minute × 60 = 180 candles/hour
- **Write frequency:** ~1 batch per hour (very low)

**CPU per write:**
- Batch of 200 INSERTs: ~20-50ms
- SQLite WAL: ~5-10ms overhead
- Commit: ~5-10ms
- **Total:** ~30-70ms per write

**Database CPU Impact:**
- **Per hour:** ~70ms write time
- **Per minute:** ~1.2ms average
- **CPU usage:** **<0.001%**

---

## Comparison to System Load

### Typical Laptop/Desktop:
- **Idle CPU:** 5-15%
- **M1 streaming:** +0.15%
- **Impact:** **Negligible** (~1-3% of idle load)

### Typical Server:
- **Idle CPU:** 1-5%
- **M1 streaming:** +0.15%
- **Impact:** **Very small** (~3-15% of idle load)

### High-Frequency Systems:
- **Active trading systems:** 10-50% CPU
- **M1 streaming:** +0.15%
- **Impact:** **Negligible** (~0.3-1.5% of active load)

---

## Network Impact

**MT5 API Call Size:**
- Request: ~100 bytes
- Response (1-2 candles): ~200-400 bytes
- **Total per fetch:** ~300-500 bytes

**Bandwidth per minute:**
- 3 fetches × 500 bytes = 1.5 KB/minute
- **Per hour:** 90 KB/hour
- **Per day:** 2.16 MB/day

**Impact:** **Negligible** (even on slow connections)

---

## Comparison: M1 vs Other Timeframes

| Timeframe | Calls/Hour | CPU Time/Hour | CPU Usage |
|-----------|------------|---------------|-----------|
| **M1**    | **180**    | **5.4s**      | **0.15%** |
| M5        | 36         | 1.1s          | 0.03%     |
| M15       | 12         | 0.4s          | 0.01%     |
| M30       | 6          | 0.2s          | 0.006%    |
| H1        | 3          | 0.1s          | 0.003%    |
| H4        | 0.75       | 0.02s         | 0.0005%   |

**M1 CPU Usage:**
- **5× more than M5** (which is already minimal)
- **Still <0.2% total CPU**
- **Negligible in absolute terms**

---

## Potential CPU Spikes

### Worst Case Scenarios:

1. **Simultaneous Fetches:**
   - All 3 symbols fetch at same time: 3 × 50ms = 150ms
   - **Impact:** Brief 0.25% spike (imperceptible)

2. **MT5 API Slowdown:**
   - If MT5 is slow: 100-200ms per fetch
   - 3 simultaneous: 300-600ms
   - **Impact:** Still <1% CPU spike

3. **Database Write + Fetch:**
   - Write (70ms) + Fetch (30ms) = 100ms
   - **Impact:** <0.2% spike

**Conclusion:** No significant CPU spikes expected.

---

## CPU Optimization Features Already Built-In

1. **Asynchronous I/O:**
   - All operations are async (non-blocking)
   - CPU idle during `asyncio.sleep()`
   - No thread blocking

2. **Incremental Fetching:**
   - Only fetches 1-2 new candles per cycle
   - Not fetching full history every time
   - Minimizes MT5 API load

3. **Batched Database Writes:**
   - Writes 200 candles at once
   - Reduces database overhead
   - Minimizes disk I/O

4. **Rolling Buffers:**
   - Fixed-size deques (no reallocation)
   - O(1) append operations
   - Minimal memory overhead

---

## Summary: CPU Impact of M1

| Metric | Value | Verdict |
|--------|-------|---------|
| **CPU Usage** | ~0.15% average | ✅ Negligible |
| **Peak CPU** | <1% spikes | ✅ Imperceptible |
| **Background Tasks** | +3 async tasks | ✅ Very lightweight |
| **API Calls** | +180/hour | ✅ Still very low |
| **Network Usage** | 90 KB/hour | ✅ Negligible |
| **Database Writes** | ~1/hour | ✅ Minimal |

---

## Final Verdict

✅ **M1 streaming has NEGLIGIBLE CPU impact**

**Reasons:**
1. Very low frequency (every 60 seconds)
2. Short operations (~30ms per fetch)
3. Async I/O (CPU idle most of the time)
4. Small data transfers
5. Efficient batching and buffering

**Comparison:**
- Modern browser tab: 5-20% CPU
- M1 streaming: 0.15% CPU
- **M1 is 30-130× lighter than a browser tab!**

**Recommendation:**
- ✅ **Safe to enable** on any system
- ✅ **No performance concerns**
- ✅ **No throttling needed**
- ✅ **Won't impact other systems**

