# LRU Cache Eviction & Cache Size Limits - Explanation

## 📊 Current Cache Implementation

**Current State:**
```python
self._cache = {}  # {symbol: (data, timestamp)}
self._cache_ttl = 30  # seconds
```

**How it works now:**
- Cache stores confluence data for each symbol
- Entries expire after 30 seconds (TTL-based)
- **No size limit** - cache can grow indefinitely
- **No eviction** - only time-based expiration

---

## 🔍 The Problem: Memory Growth

### Scenario: What happens with current cache?

**Example:**
1. User requests confluence for `BTCUSDc` → Cache stores it
2. User requests confluence for `XAUUSDc` → Cache stores it
3. User requests confluence for `EURUSDc` → Cache stores it
4. User requests confluence for `GBPUSDc` → Cache stores it
5. ... and so on for 50+ symbols

**Result:**
- Cache grows to 50+ entries
- Each entry contains:
  - M1, M5, M15, H1 confluence data
  - Scores, grades, factors for each timeframe
  - Estimated size: ~2-5 KB per symbol
- **Total cache size: 50 × 3 KB = ~150 KB** (small, but can grow)

**If cache never expires (bug scenario):**
- Cache could grow to 1000+ symbols
- **Total: 1000 × 3 KB = ~3 MB** (still small, but unnecessary)

---

## ✅ Solution 1: Cache Size Limit

### What it does:
**Limit the maximum number of cached entries**

```python
self._cache = {}
self._max_cache_size = 50  # Maximum 50 symbols cached
```

**How it works:**
1. When cache reaches 50 entries
2. New symbol request comes in
3. **Remove oldest entry** (by timestamp)
4. Add new entry

**Example:**
```
Cache has 50 entries:
- BTCUSDc (oldest, accessed 2 minutes ago)
- XAUUSDc
- EURUSDc
- ... (47 more)
- GBPUSDc (newest, accessed 10 seconds ago)

New request: AUDUSDc
→ Remove BTCUSDc (oldest)
→ Add AUDUSDc
```

**Benefits:**
- ✅ Prevents unlimited memory growth
- ✅ Keeps most recently used symbols
- ✅ Simple to implement
- ✅ Predictable memory usage

**Drawbacks:**
- ❌ May evict frequently used symbols if they're old
- ❌ Doesn't consider access frequency

---

## ✅ Solution 2: LRU (Least Recently Used) Cache Eviction

### What it does:
**Remove the symbol that hasn't been accessed in the longest time**

**LRU = Least Recently Used**

### How it works:

**Track access order:**
```python
# Track access order (most recent → oldest)
self._access_order = []  # ['XAUUSDc', 'BTCUSDc', 'EURUSDc']

# When symbol accessed:
# 1. Move to front of list
# 2. If cache full, remove last item (least recently used)
```

**Example Flow:**

**Step 1: Cache has 3 entries (max 3)**
```
Cache: {BTCUSDc, XAUUSDc, EURUSDc}
Access order: [EURUSDc, XAUUSDc, BTCUSDc]  # EURUSDc most recent
```

**Step 2: Request for BTCUSDc**
```
Access order: [BTCUSDc, EURUSDc, XAUUSDc]  # Move BTCUSDc to front
```

**Step 3: Request for GBPUSDc (cache full)**
```
1. Remove XAUUSDc (least recently used - at end of list)
2. Add GBPUSDc to front
Access order: [GBPUSDc, BTCUSDc, EURUSDc]
```

**Benefits:**
- ✅ Keeps frequently accessed symbols
- ✅ Automatically removes unused symbols
- ✅ Better than simple size limit (considers usage)
- ✅ Industry-standard approach

**Drawbacks:**
- ❌ Slightly more complex (need to track access order)
- ❌ Small overhead (maintaining order list)

---

## 📈 Comparison: Current vs LRU vs Size Limit

### Scenario: 100 symbol requests, cache limit = 20

**Current (TTL only):**
```
After 30 seconds: All entries expire
Problem: If many requests in < 30s, cache grows to 100 entries
Memory: 100 × 3 KB = 300 KB (temporary spike)
```

**Size Limit (20 entries):**
```
Cache size: Always ≤ 20 entries
Memory: 20 × 3 KB = 60 KB (constant)
Problem: May remove frequently used symbols if they're old
```

**LRU (20 entries):**
```
Cache size: Always ≤ 20 entries
Memory: 20 × 3 KB = 60 KB (constant)
Benefit: Keeps the 20 most frequently accessed symbols
```

---

## 🎯 Real-World Example

### Trading Bot Scenario:

**User behavior:**
- Monitors 2 primary symbols: `BTCUSDc`, `XAUUSDc` (accessed every 5 seconds)
- Occasionally checks 10 other symbols: `EURUSDc`, `GBPUSDc`, etc. (accessed once)
- Total: 12 symbols requested

**Without LRU (current):**
```
Cache after 1 minute:
- All 12 symbols cached (if within 30s TTL)
- Memory: 12 × 3 KB = 36 KB
- If TTL bug: Could grow to 100+ symbols = 300 KB
```

**With LRU (max 5 entries):**
```
Cache after 1 minute:
- BTCUSDc (frequently accessed - kept)
- XAUUSDc (frequently accessed - kept)
- EURUSDc (recently accessed - kept)
- GBPUSDc (recently accessed - kept)
- AUDUSDc (recently accessed - kept)
- Other 7 symbols: Evicted (not recently used)
- Memory: 5 × 3 KB = 15 KB (predictable)
```

**Result:**
- ✅ Primary symbols always cached (frequently accessed)
- ✅ Memory usage predictable
- ✅ No memory leaks

---

## 💻 Implementation Example

### Simple Size Limit:
```python
def _evict_oldest_entry(self):
    """Remove oldest entry by timestamp"""
    if len(self._cache) >= self._max_cache_size:
        # Find oldest entry
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k][1]  # Compare timestamps
        )
        del self._cache[oldest_key]
        logger.debug(f"Evicted oldest cache entry: {oldest_key}")
```

### LRU Implementation:
```python
def __init__(self, indicator_bridge, cache_ttl: int = 30, max_cache_size: int = 50):
    self._cache = {}
    self._cache_ttl = cache_ttl
    self._max_cache_size = max_cache_size
    self._access_order = []  # Track access order for LRU
    self._cache_lock = threading.Lock()

def _get_cached_data(self, cache_key: str):
    """Get cached data and update access order"""
    with self._cache_lock:
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            
            # Update access order (move to front)
            if cache_key in self._access_order:
                self._access_order.remove(cache_key)
            self._access_order.insert(0, cache_key)
            
            return data, timestamp
    return None, None

def _evict_lru_entry(self):
    """Evict least recently used entry if cache is full"""
    if len(self._cache) >= self._max_cache_size:
        # Remove least recently used (last in access_order)
        if self._access_order:
            lru_key = self._access_order.pop()  # Remove from end
            del self._cache[lru_key]
            logger.debug(f"Evicted LRU cache entry: {lru_key}")
```

---

## 📊 Memory Impact Analysis

### Current Cache Entry Size:
```
Per symbol cache entry:
- M1, M5, M15, H1 data: ~2-5 KB
- Timestamp: ~50 bytes
- Total: ~3 KB per symbol
```

### Memory Scenarios:

**Scenario 1: Small bot (2-5 symbols)**
- Current: 5 × 3 KB = 15 KB ✅ Negligible
- With LRU (max 10): 10 × 3 KB = 30 KB ✅ Still negligible
- **Verdict: No need for LRU** (current is fine)

**Scenario 2: Medium bot (10-20 symbols)**
- Current: 20 × 3 KB = 60 KB ✅ Small
- With LRU (max 20): 20 × 3 KB = 60 KB ✅ Same
- **Verdict: LRU helpful** (prevents growth beyond 20)

**Scenario 3: Large bot (50+ symbols)**
- Current: 50 × 3 KB = 150 KB (could grow to 500 KB) ⚠️
- With LRU (max 50): 50 × 3 KB = 150 KB ✅ Predictable
- **Verdict: LRU recommended** (prevents memory growth)

---

## 🎯 Recommendation

### For Your Use Case (BTCUSDc, XAUUSDc):

**Current situation:**
- 2 primary symbols
- Cache size: ~6 KB
- **Verdict: ✅ No LRU needed** (memory usage is negligible)

**If you add more symbols later:**
- 10+ symbols: Consider LRU with max 20-30 entries
- 50+ symbols: **Definitely use LRU** with max 50 entries

**Implementation Priority:**
- **Low priority** for current use case
- **Medium priority** if you plan to support many symbols
- **High priority** if you see memory growth issues

---

## 🔧 When to Implement

**Implement LRU if:**
- ✅ You plan to support 20+ symbols
- ✅ You see memory usage growing over time
- ✅ You want predictable memory usage
- ✅ You want to optimize for frequently accessed symbols

**Don't implement if:**
- ❌ You only use 2-5 symbols (current case)
- ❌ Memory usage is already negligible
- ❌ TTL-based expiration is sufficient
- ❌ You have other higher-priority tasks

---

## 📝 Summary

**LRU Cache Eviction:**
- Removes least recently used entries when cache is full
- Keeps frequently accessed symbols
- Prevents unlimited memory growth
- Industry-standard approach

**Cache Size Limit:**
- Simple: Remove oldest entry when limit reached
- Less sophisticated than LRU
- Still prevents memory growth

**For your current use case:**
- **Not critical** - memory usage is already small
- **Nice to have** - if you expand to many symbols
- **Easy to add later** - when needed

**Bottom line:** Current TTL-based cache is sufficient for 2-5 symbols. LRU would be beneficial if you scale to 20+ symbols or see memory growth issues.

