# M1 Streaming Resource Usage Calculation

## For BTCUSDc and XAUUSDc

### Per Candle Size Estimation

**In RAM (Python deque with Candle objects):**
- Symbol name: ~12 bytes (string)
- Timeframe: ~3 bytes (string "M1")
- Datetime object: ~48 bytes
- Float values (open, high, low, close, spread): 5 × 8 = 40 bytes
- Integer values (volume, real_volume): 2 × 8 = 16 bytes
- Python object overhead: ~56 bytes
- Deque node overhead: ~24 bytes
- **Total per candle: ~200 bytes** (conservative estimate)

**In Database (SQLite):**
- Each row stores: symbol (10), timeframe (3), time (8), open/high/low/close/spread (40), volume/real_volume (16)
- SQLite row overhead: ~20 bytes
- **Total per candle: ~97 bytes** (compressed/stored format)

---

## RAM Usage Scenarios

### Scenario 1: Minimal Buffer (1 hour context)
- **Buffer size:** 60 candles (1 hour of M1)
- **Per symbol:** 60 × 200 bytes = 12 KB
- **2 symbols (BTCUSDc + XAUUSDc):** 24 KB
- **Verdict:** ✅ Negligible (< 0.1 MB)

### Scenario 2: Moderate Buffer (8 hours context)
- **Buffer size:** 480 candles (8 hours of M1)
- **Per symbol:** 480 × 200 bytes = 96 KB
- **2 symbols:** 192 KB
- **Verdict:** ✅ Very small (~0.2 MB)

### Scenario 3: Trading Buffer (1 day context)
- **Buffer size:** 1,440 candles (24 hours of M1)
- **Per symbol:** 1,440 × 200 bytes = 288 KB
- **2 symbols:** 576 KB
- **Verdict:** ✅ Small (~0.6 MB)

### Scenario 4: Analysis Buffer (2 days context)
- **Buffer size:** 2,880 candles (48 hours of M1)
- **Per symbol:** 2,880 × 200 bytes = 576 KB
- **2 symbols:** 1.15 MB
- **Verdict:** ✅ Acceptable (~1.2 MB)

### Scenario 5: Extended Buffer (1 week context)
- **Buffer size:** 10,080 candles (7 days × 24 hours × 60 min)
- **Per symbol:** 10,080 × 200 bytes = 2.0 MB
- **2 symbols:** 4.0 MB
- **Verdict:** ⚠️ Moderate (4 MB, but probably overkill for M1)

---

## SSD Usage (Database Storage)

### With 30-day Retention Policy

**Candles per day per symbol:**
- M1 candles per day: 1,440 candles/day
- 30 days: 1,440 × 30 = 43,200 candles

**Storage per symbol:**
- 43,200 candles × 97 bytes = 4.19 MB per symbol

**2 symbols (BTCUSDc + XAUUSDc):**
- Total: 4.19 MB × 2 = **8.38 MB**

**With SQLite overhead (indexes, metadata):**
- Add ~20% overhead: 8.38 MB × 1.2 = **~10 MB**

### With WAL (Write-Ahead Logging)
- Temporary WAL file: ~2-5 MB (varies with write frequency)
- Total with WAL: **~12-15 MB**

---

## Refresh Frequency for M1

**Recommended refresh interval:** 60 seconds (1 minute)
- M1 candles close every 60 seconds
- Need to fetch new candle every minute
- Very lightweight (1-2 candles per fetch)

**API calls per day:**
- 2 symbols × (1440 minutes / day) = 2,880 MT5 API calls/day
- Or: 2,880 / 86,400 seconds = **~0.033 calls/second**
- ✅ Extremely low API load

---

## Recommended Configuration

```json
{
  "buffer_sizes": {
    "M1": 1440,  // 1 day (24 hours) - good balance
    // Alternative options:
    // 480,   // 8 hours - minimal
    // 2880,  // 2 days - extended analysis
  },
  "refresh_intervals": {
    "M1": 60   // Every 60 seconds (1 minute)
  }
}
```

---

## Summary for BTCUSDc + XAUUSDc M1 Streaming

| Metric | Value | Notes |
|--------|-------|-------|
| **RAM (1 day buffer)** | ~0.6 MB | Negligible impact |
| **RAM (2 day buffer)** | ~1.2 MB | Still very small |
| **SSD (30-day DB)** | ~12-15 MB | With WAL overhead |
| **SSD per day** | ~0.4 MB | Minimal growth |
| **API calls/day** | 2,880 | Very low frequency |
| **API calls/sec** | 0.033 | Negligible load |

---

## Comparison to Current M5 Streaming

| Timeframe | Current Buffer | RAM Usage | M1 Equivalent |
|-----------|---------------|-----------|---------------|
| **M5** | 300 candles | ~60 KB | 1,500 M1 candles = 300 KB |
| **M1** | 1,440 candles | ~288 KB | Same |
| **Difference** | - | +228 KB | Only 4× more for same time period |

**Conclusion:** M1 streaming is extremely lightweight! Even with 2-day buffers, it uses < 1.5 MB RAM.

---

## Final Recommendation

✅ **M1 streaming is HIGHLY RECOMMENDED for BTCUSDc and XAUUSDc**

**Why:**
- RAM usage is negligible (< 1 MB for practical buffers)
- SSD usage is minimal (~15 MB for 30 days)
- API load is extremely low
- Provides real-time data that DTMS/Intelligent Exits need
- Enables high-frequency analysis without impacting system resources

**Suggested Buffer Size:** 1,440 candles (1 day)
- Provides full trading day context
- Minimal memory footprint
- Covers most analysis needs

