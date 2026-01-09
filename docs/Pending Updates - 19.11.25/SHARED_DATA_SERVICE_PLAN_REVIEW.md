# Shared Data Service Implementation Plan - Review & Issues

## Issues Found

### 🔴 Critical Issues

#### Issue 1: Singleton Initialization Parameters
**Location:** Section 3.1 (Implementation Approach)

**Problem:**
The singleton pattern shown doesn't handle initialization parameters correctly. If `SharedDataService.get_instance(mt5_service, ...)` is called multiple times with different parameters, only the first set will be used.

**Current Code:**
```python
def __new__(cls, mt5_service=None, ...):
    if cls._instance is None:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
    return cls._instance
```

**Issue:** Parameters are ignored after first initialization.

**Fix Required:**
- Use `get_instance()` method instead of `__new__()` for initialization
- Store initialization parameters and validate on subsequent calls
- Or use lazy initialization pattern

**Recommended Fix:**
```python
class SharedDataService:
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls, mt5_service, ...):
        instance = cls.__new__(cls)
        if not cls._initialized:
            with cls._lock:
                if not cls._initialized:
                    instance._initialize(mt5_service, ...)
                    cls._initialized = True
        return instance
```

---

#### Issue 2: Fallback Logic Implementation
**Location:** Section 6.1 (Fallback Logic)

**Problem:**
The fallback code shows `self._fallback_get_m1_data()` method, but this doesn't exist. The fallback should create a new `M1DataFetcher` instance, not call a non-existent method.

**Current Code:**
```python
def get_m1_data(self, symbol: str, ...):
    if self.fallback_to_old:
        return self._fallback_get_m1_data(symbol, ...)  # ❌ Method doesn't exist
```

**Fix Required:**
- Store fallback M1DataFetcher instance
- Create fallback instance on initialization
- Use fallback instance when needed

**Recommended Fix:**
```python
class SharedDataService:
    def __init__(self, mt5_service, ...):
        self.mt5_service = mt5_service
        # Create fallback instance
        from infra.m1_data_fetcher import M1DataFetcher
        self._fallback_fetcher = M1DataFetcher(data_source=mt5_service, max_candles=200)
    
    def get_m1_data(self, symbol: str, ...):
        if self.fallback_to_old:
            return self._fallback_fetcher.fetch_m1_data(symbol, ...)
        # ... rest of implementation
```

---

#### Issue 3: Missing M1RefreshManager Integration
**Location:** Section 4.3 (Integration Points)

**Problem:**
The plan doesn't address how `M1RefreshManager` will work with the shared service. Auto execution uses `_batch_refresh_m1_data()` which relies on `m1_refresh_manager`.

**Current Usage:**
```python
def _batch_refresh_m1_data(self):
    if not self.m1_refresh_manager or not self.m1_data_fetcher:
        return
    # Uses m1_refresh_manager.refresh_symbols_batch()
```

**Fix Required:**
- Integrate M1RefreshManager into SharedDataService
- Or make SharedDataService compatible with M1RefreshManager
- Update batch refresh logic to use shared service

**Recommended Fix:**
- Add `M1RefreshManager` as a component of SharedDataService
- Expose refresh methods through shared service
- Update auto execution to use shared service refresh methods

---

### 🟡 Important Issues

#### Issue 4: Missing Desktop Agent Integration
**Location:** Section 4.3 (Integration Points)

**Problem:**
The plan only addresses Alert System and Auto Execution, but `desktop_agent.py` also uses `M1DataFetcher` (stored in registry). This is another integration point.

**Current Usage:**
```python
# desktop_agent.py
if not hasattr(registry, 'm1_data_fetcher') or registry.m1_data_fetcher is None:
    registry.m1_data_fetcher = M1DataFetcher(
        data_source=mt5_service,
        max_candles=200,
        cache_ttl=300
    )
```

**Fix Required:**
- Add Desktop Agent integration section
- Update registry to use shared service
- Ensure compatibility with existing usage

---

#### Issue 5: M1MicrostructureAnalyzer Dependencies
**Location:** Section 3.2 (Component 4: M1MicrostructureManager)

**Problem:**
The plan mentions integrating M1MicrostructureAnalyzer but doesn't fully address its dependencies:
- `session_manager` (SessionVolatilityProfile)
- `asset_profiles` (AssetProfileManager)
- `threshold_manager` (SymbolThresholdManager)

**Current Initialization:**
```python
m1_analyzer = M1MicrostructureAnalyzer(
    mt5_service=mt5_service,
    session_manager=session_manager,
    asset_profiles=asset_profiles,
    threshold_manager=threshold_manager
)
```

**Fix Required:**
- Document how these dependencies will be passed to SharedDataService
- Ensure shared service can initialize M1MicrostructureAnalyzer
- Handle dependency lifecycle (creation, sharing, cleanup)

---

#### Issue 6: Cache Synchronization
**Location:** Section 3.2 (Component 2: UnifiedCache)

**Problem:**
The plan mentions "unified cache" but doesn't address:
- How cache will be synchronized across different access patterns
- Cache invalidation strategy when data is updated
- Handling stale data during cache refresh

**Fix Required:**
- Document cache synchronization strategy
- Add cache versioning or timestamps
- Implement cache refresh coordination

---

#### Issue 7: API Method Signatures
**Location:** Section 3.3 (API Design)

**Problem:**
The API methods shown don't match the actual `M1DataFetcher` API:
- `M1DataFetcher.fetch_m1_data()` returns `List[Dict]`
- Plan shows `get_m1_data()` which is fine, but compatibility wrapper needs all methods

**Missing Methods in Compatibility Wrapper:**
- `get_latest_candle()` - used in some places
- `refresh_data()` - used for manual refresh
- `get_cache_age()` - used for cache monitoring
- `clear_cache()` - used for cache management

**Fix Required:**
- Complete compatibility wrapper with all M1DataFetcher methods
- Ensure return types match exactly
- Test all method signatures

---

### 🟢 Minor Issues

#### Issue 8: Thread Safety Details
**Location:** Section 3.1 (Design Pattern)

**Problem:**
The plan mentions "thread-safe" but doesn't specify:
- Which operations need locks
- Lock granularity (per-symbol, global, etc.)
- Deadlock prevention strategy

**Fix Required:**
- Document locking strategy
- Specify lock scope (per-symbol locks vs global locks)
- Add deadlock prevention measures

---

#### Issue 9: Error Handling Specifics
**Location:** Section 2.1 (FR6: Error Handling)

**Problem:**
The plan mentions "retry logic" but doesn't specify:
- Retry count
- Retry backoff strategy
- Which errors are retryable vs fatal

**Fix Required:**
- Specify retry parameters (count, backoff, timeout)
- Document retryable vs non-retryable errors
- Add circuit breaker pattern for repeated failures

---

#### Issue 10: Performance Target Validation
**Location:** Section 8 (Performance Targets)

**Problem:**
The plan mentions "30-50% CPU reduction" but doesn't specify:
- Baseline measurement methodology
- How to account for system variations
- What constitutes "acceptable" vs "target" performance

**Fix Required:**
- Define baseline measurement process
- Specify acceptable variance (e.g., ±5%)
- Add performance regression tests

---

## Missing Components

### Component 1: Configuration Management
**Issue:** Plan doesn't specify how configuration (TTL, cache sizes, etc.) will be managed.

**Required:**
- Configuration file structure
- Runtime configuration updates
- Environment-specific configs (dev, test, prod)

### Component 2: Health Check Implementation
**Issue:** Plan mentions health checks but doesn't specify implementation.

**Required:**
- Health check criteria
- Health check frequency
- Health check endpoint implementation

### Component 3: Metrics Collection
**Issue:** Plan mentions metrics but doesn't specify collection mechanism.

**Required:**
- Metrics library (Prometheus, custom, etc.)
- Metrics export format
- Metrics aggregation strategy

---

## Recommendations

### 1. Add Missing Sections

**Section: Configuration Management**
- Config file structure
- Runtime updates
- Environment-specific configs

**Section: Desktop Agent Integration**
- Registry integration
- Compatibility with existing usage
- Migration path

**Section: M1RefreshManager Integration**
- How refresh manager works with shared service
- Batch refresh coordination
- Refresh scheduling

### 2. Clarify Implementation Details

**Singleton Pattern:**
- Use proper initialization pattern
- Handle parameter validation
- Document thread safety

**Fallback Logic:**
- Implement actual fallback mechanism
- Store fallback instances
- Test fallback scenarios

**Cache Management:**
- Document cache synchronization
- Specify invalidation strategy
- Add cache versioning

### 3. Expand Testing Strategy

**Add Tests For:**
- Desktop Agent integration
- M1RefreshManager compatibility
- Cache synchronization
- Fallback mechanism
- Configuration updates

### 4. Update Timeline

**Consider:**
- Additional time for Desktop Agent integration
- Time for M1RefreshManager refactoring
- Buffer for unexpected issues (add 1-2 weeks)

---

## Summary

**Critical Issues:** 3
**Important Issues:** 4
**Minor Issues:** 3
**Missing Components:** 3

**Overall Assessment:**
The plan is comprehensive but needs refinement in:
1. Singleton initialization pattern
2. Fallback mechanism implementation
3. Missing integration points (Desktop Agent, M1RefreshManager)
4. Dependency management (M1MicrostructureAnalyzer)

**Recommendation:**
Address critical issues before starting implementation. Add missing sections for Desktop Agent and M1RefreshManager integration. Clarify singleton pattern and fallback logic implementation.

---

*Review Date: 2025-11-20*

