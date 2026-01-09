# Shared Data Service Implementation Plan

## Executive Summary

This plan outlines the implementation of a **Shared Data Service** to eliminate duplicate data fetching between the Alert System and Auto Execution System. The service will centralize all market data fetching, caching, and indicator calculations, reducing CPU usage by 30-50% and RAM usage by 20-30%.

**Key Principles:**
- ✅ Zero downtime migration
- ✅ Backward compatibility during transition
- ✅ Comprehensive testing with fallback logic
- ✅ Gradual rollout with feature flags
- ✅ Performance monitoring and validation

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Requirements](#requirements)
3. [Implementation Approach](#implementation-approach)
4. [Integration Strategy](#integration-strategy)
5. [Testing Strategy](#testing-strategy)
6. [Fallback Logic](#fallback-logic)
7. [Migration Phases](#migration-phases)
8. [Performance Targets](#performance-targets)
9. [Risk Mitigation](#risk-mitigation)
10. [Success Criteria](#success-criteria)
11. [Monitoring & Observability](#monitoring--observability)
12. [Documentation](#documentation)
13. [Configuration Management](#configuration-management)
14. [Health Check Implementation](#health-check-implementation)
15. [Metrics Collection](#metrics-collection)
16. [Timeline Summary](#timeline-summary)
17. [Additional Test Suites](#additional-test-suites)
18. [Next Steps](#next-steps)
19. [Plan Updates & Review Status](#plan-updates--review-status)

---

## 1. Architecture Overview

### 1.1 Current Architecture (Before)

```
┌─────────────────┐         ┌─────────────────┐
│  Alert System   │         │ Auto Execution  │
│                 │         │     System      │
├─────────────────┤         ├─────────────────┤
│ M1DataFetcher   │         │ M1DataFetcher   │
│ (Instance 1)    │         │ (Instance 2)    │
│                 │         │                 │
│ IndicatorBridge │         │ IndicatorBridge │
│ (Shared)        │         │ (Shared)        │
│                 │         │                 │
│ M1 Cache        │         │ M1 Cache        │
│ (Separate)      │         │ (Separate)      │
└────────┬────────┘         └────────┬────────┘
         │                           │
         └───────────┬───────────────┘
                     │
              ┌──────▼──────┐
              │  MT5Service │
              │  (Shared)   │
              └─────────────┘
```

**Problems:**
- Duplicate M1 data fetches
- Duplicate M5/M15 fetches
- Separate caches (wasted RAM)
- No coordination between systems

### 1.2 Target Architecture (After)

```
┌─────────────────┐         ┌─────────────────┐
│  Alert System   │         │ Auto Execution  │
│                 │         │     System      │
└────────┬────────┘         └────────┬────────┘
         │                           │
         └───────────┬───────────────┘
                     │
         ┌───────────▼───────────┐
         │  Shared Data Service  │
         │                       │
         │  - M1 Data Manager    │
         │  - M5/M15 Manager     │
         │  - Indicator Manager  │
         │  - Unified Cache      │
         │  - Request Queue      │
         └───────────┬───────────┘
                     │
              ┌──────▼──────┐
              │  MT5Service │
              │  (Shared)   │
              └─────────────┘
```

**Benefits:**
- Single source of truth for all data
- Unified cache (shared between systems)
- Coordinated fetching (batch requests)
- Reduced API calls to MT5

---

## 2. Requirements

### 2.1 Functional Requirements

#### FR1: Data Fetching
- **FR1.1**: Fetch M1 candlestick data (200 candles max)
- **FR1.2**: Fetch M5 candlestick data (100 candles max)
- **FR1.3**: Fetch M15 candlestick data (50 candles max)
- **FR1.4**: Fetch H1 candlestick data (24 candles max)
- **FR1.5**: Support multiple symbols simultaneously
- **FR1.6**: Handle symbol normalization (add 'c' suffix)

#### FR2: Caching
- **FR2.1**: Cache M1 data with TTL (30-60 seconds)
- **FR2.2**: Cache M5/M15/H1 data with TTL (60-120 seconds)
- **FR2.3**: Cache indicator calculations (30-60 seconds)
- **FR2.4**: Cache M1 microstructure analysis (60 seconds)
- **FR2.5**: Automatic cache invalidation on TTL expiry
- **FR2.6**: Manual cache invalidation API
- **FR2.7**: Cache size limits (prevent memory bloat)

#### FR3: Indicator Calculations
- **FR3.1**: Calculate multi-timeframe indicators (RSI, MACD, ATR, etc.)
- **FR3.2**: Cache indicator results
- **FR3.3**: Support indicator bridge compatibility
- **FR3.4**: Batch indicator calculations

#### FR4: M1 Microstructure Integration
- **FR4.1**: Integrate with M1MicrostructureAnalyzer
- **FR4.2**: Cache microstructure analysis results
- **FR4.3**: Support session-aware analysis
- **FR4.4**: Support asset profile integration

#### FR5: Request Coordination
- **FR5.1**: Batch multiple requests for same symbol/timeframe
- **FR5.2**: Queue requests during active fetch
- **FR5.3**: Return cached data immediately if available
- **FR5.4**: Handle concurrent requests safely (thread-safe)

#### FR6: Error Handling
- **FR6.1**: Graceful degradation on MT5 connection failure
- **FR6.2**: Retry logic for transient failures
  - **Retry Count**: 3 attempts for transient failures
  - **Retry Backoff**: Exponential backoff (1s, 2s, 4s)
  - **Retry Timeout**: 30 seconds total timeout
  - **Retryable Errors**: Connection errors, timeout errors, temporary MT5 errors
  - **Non-Retryable Errors**: Invalid symbol, invalid parameters, authentication errors
  - **Circuit Breaker**: After 5 consecutive failures, circuit opens for 60 seconds
- **FR6.3**: Fallback to old system if service unavailable
- **FR6.4**: Comprehensive error logging

### 2.2 Non-Functional Requirements

#### NFR1: Performance
- **NFR1.1**: Cache hit rate > 80% (after warm-up)
- **NFR1.2**: Response time < 50ms for cached data
- **NFR1.3**: Response time < 500ms for fresh fetch
- **NFR1.4**: Support 10+ concurrent requests
- **NFR1.5**: Memory usage < 50 MB for 10 symbols

#### NFR2: Reliability
- **NFR2.1**: 99.9% uptime (excluding MT5 outages)
- **NFR2.2**: Automatic recovery from transient failures
- **NFR2.3**: No data corruption
- **NFR2.4**: Thread-safe operations

#### NFR3: Compatibility
- **NFR3.1**: Backward compatible API (drop-in replacement)
- **NFR3.2**: Support existing code patterns
- **NFR3.3**: No breaking changes during migration

#### NFR4: Observability
- **NFR4.1**: Comprehensive logging (cache hits/misses, fetch times)
- **NFR4.2**: Performance metrics (CPU, RAM, latency)
- **NFR4.3**: Health check endpoint
- **NFR4.4**: Cache statistics API

### 2.3 Integration Requirements

#### IR1: Alert System Integration
- **IR1.1**: Replace `M1DataFetcher` instance with shared service
- **IR1.2**: Use shared service for M5/M15 data
- **IR1.3**: Use shared service for indicator data
- **IR1.4**: Maintain backward compatibility during transition
- **IR1.5**: Feature flag to enable/disable shared service

#### IR2: Auto Execution Integration
- **IR2.1**: Replace `M1DataFetcher` instance with shared service
- **IR2.2**: Use shared service for M5/M15 data
- **IR2.3**: Use shared service for indicator data
- **IR2.4**: Maintain backward compatibility during transition
- **IR2.5**: Feature flag to enable/disable shared service

#### IR3: Fallback Logic
- **IR3.1**: Automatic fallback to old system on service failure
- **IR3.2**: Manual fallback via feature flag
- **IR3.3**: Log all fallback events
- **IR3.4**: Alert on repeated fallbacks

---

## 3. Implementation Approach

### 3.1 Design Pattern: Singleton with Dependency Injection

**Rationale:**
- Single instance ensures unified cache
- Dependency injection allows testing and flexibility
- Thread-safe singleton pattern

**Implementation:**
```python
class SharedDataService:
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    _init_params = None
    
    def __new__(cls):
        """Create singleton instance (no parameters in __new__)"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls, mt5_service, session_manager=None, asset_profiles=None, 
                     threshold_manager=None, m1_refresh_manager=None):
        """
        Get singleton instance with initialization parameters.
        Parameters are validated on first call and stored for validation.
        
        Args:
            mt5_service: MT5Service instance (required)
            session_manager: SessionVolatilityProfile instance (optional)
            asset_profiles: AssetProfileManager instance (optional)
            threshold_manager: SymbolThresholdManager instance (optional)
            m1_refresh_manager: M1RefreshManager instance (optional, will be created if None)
        """
        instance = cls.__new__(cls)
        if not cls._initialized:
            with cls._lock:
                if not cls._initialized:
                    # Store initialization parameters
                    cls._init_params = {
                        'mt5_service': mt5_service,
                        'session_manager': session_manager,
                        'asset_profiles': asset_profiles,
                        'threshold_manager': threshold_manager,
                        'm1_refresh_manager': m1_refresh_manager
                    }
                    # Initialize instance
                    instance._initialize(mt5_service, session_manager, asset_profiles, 
                                       threshold_manager, m1_refresh_manager)
                    cls._initialized = True
        else:
            # Validate parameters match initial initialization
            if cls._init_params['mt5_service'] != mt5_service:
                logger.warning("SharedDataService already initialized with different mt5_service")
        return instance
    
    def _initialize(self, mt5_service, session_manager, asset_profiles, 
                   threshold_manager, m1_refresh_manager):
        """Initialize the singleton instance"""
        self.mt5_service = mt5_service
        self.session_manager = session_manager
        self.asset_profiles = asset_profiles
        self.threshold_manager = threshold_manager
        
        # Create internal M1DataFetcher for shared service
        from infra.m1_data_fetcher import M1DataFetcher
        self._internal_m1_fetcher = M1DataFetcher(data_source=mt5_service, max_candles=200)
        
        # Create or use provided M1RefreshManager
        if m1_refresh_manager is None:
            from infra.m1_refresh_manager import M1RefreshManager
            self.m1_refresh_manager = M1RefreshManager(
                fetcher=self._internal_m1_fetcher,
                refresh_interval_active=30,
                refresh_interval_inactive=300
            )
        else:
            self.m1_refresh_manager = m1_refresh_manager
        
        # ... rest of initialization
```

**Thread Safety:**
- **Global Lock**: Used for singleton creation (prevents race conditions during initialization)
- **Per-Symbol Locks**: Used for cache operations (allows concurrent access to different symbols)
- **Lock Granularity**: 
  - Global lock: Singleton creation, initialization
  - Per-symbol locks: Cache read/write operations
  - Request queue locks: Request coordination
- **Deadlock Prevention**: 
  - Always acquire locks in consistent order (global → symbol → queue)
  - Use timeout on locks (5 seconds max)
  - Avoid nested locks where possible

### 3.2 Core Components

#### Component 1: DataFetcherManager
- Manages all data fetching (M1, M5, M15, H1)
- Coordinates requests (batch, queue)
- Handles symbol normalization
- Thread-safe operations

#### Component 2: UnifiedCache
- Single cache for all data types
- TTL-based expiration
- Size limits (LRU eviction)
- Cache statistics
- **Cache Synchronization:**
  - **Versioning**: Each cache entry has version number (increments on update)
  - **Timestamps**: Each entry has creation and last-access timestamps
  - **Invalidation Strategy**: 
    - TTL-based: Automatic expiration after TTL
    - Manual: Clear by symbol/timeframe
    - On-error: Invalidate on fetch failure
    - On-update: Invalidate related entries (e.g., M1 update invalidates M1 analysis)
  - **Stale Data Handling**: 
    - Check timestamp before returning cached data
    - Return stale data with warning if fresh fetch fails
    - Background refresh for stale data (async)
  - **Thread Safety**: Per-symbol locks for cache operations

#### Component 3: IndicatorManager
- Wraps IndicatorBridge
- Maps `get_multi_indicators()` to `IndicatorBridge.get_multi()`
- Caches indicator calculations
- Batch processing
- Compatibility layer

#### Component 4: M1MicrostructureManager
- Integrates M1MicrostructureAnalyzer
- Caches analysis results
- Session-aware analysis
- Asset profile integration
- **Dependencies Management:**
  - `session_manager` (SessionVolatilityProfile) - passed during initialization
  - `asset_profiles` (AssetProfileManager) - passed during initialization
  - `threshold_manager` (SymbolThresholdManager) - passed during initialization
  - All dependencies are shared across all consumers (single instance)
  - Dependencies lifecycle: Created once, shared for lifetime of service

#### Component 5: RequestCoordinator
- Queues concurrent requests
- Batches same-symbol requests
- Prevents duplicate fetches
- Thread-safe request handling

### 3.3 API Design

#### Primary API Methods

```python
class SharedDataService:
    # M1 Data
    def get_m1_data(symbol: str, count: int = 200, use_cache: bool = True) -> List[Dict]
    def get_m1_data_async(symbol: str, count: int = 200, use_cache: bool = True) -> Awaitable[List[Dict]]
    
    # M5/M15/H1 Data
    def get_candles(symbol: str, timeframe: str, count: int, use_cache: bool = True) -> List[Dict]
    
    # Indicators
    def get_indicators(symbol: str, timeframe: str = "M5", use_cache: bool = True) -> Dict
    def get_multi_indicators(symbol: str, use_cache: bool = True) -> Dict
    
    # M1 Microstructure
    def get_m1_analysis(symbol: str, current_price: float, use_cache: bool = True) -> Dict
    
    # Cache Management
    def clear_cache(symbol: str = None, timeframe: str = None)
    def get_cache_stats() -> Dict  # Returns dict with 'symbols' (List[str]), 'hits', 'misses', 'size_mb', etc.
    def get_cache_hit_rate() -> float
    def get_cache_age(symbol: str, timeframe: str) -> Optional[float]
    
    # Refresh Management
    def refresh_symbol(symbol: str, force: bool = False) -> bool
    def refresh_symbols_batch(symbols: List[str]) -> Dict[str, bool]
    def check_and_refresh_stale(symbol: str, max_age_seconds: int = 180) -> bool
    
    # Health & Status
    def health_check() -> Dict
    def get_performance_metrics() -> Dict
```

#### Compatibility Wrapper

```python
class M1DataFetcherCompat:
    """Compatibility wrapper for existing M1DataFetcher API"""
    def __init__(self, shared_service: SharedDataService):
        self.shared_service = shared_service
    
    def fetch_m1_data(self, symbol: str, count: int = 200, use_cache: bool = True) -> List[Dict]:
        """Fetch M1 data - matches M1DataFetcher.fetch_m1_data() signature"""
        return self.shared_service.get_m1_data(symbol, count, use_cache)
    
    async def fetch_m1_data_async(self, symbol: str, count: int = 200, use_cache: bool = True) -> List[Dict]:
        """Async fetch M1 data - matches M1DataFetcher.fetch_m1_data_async() signature"""
        return await self.shared_service.get_m1_data_async(symbol, count, use_cache)
    
    def get_latest_m1(self, symbol: str) -> Optional[Dict]:
        """Get latest M1 candle - matches M1DataFetcher.get_latest_m1() signature"""
        data = self.shared_service.get_m1_data(symbol, count=1, use_cache=True)
        return data[-1] if data else None
    
    def refresh_symbol(self, symbol: str) -> bool:
        """Refresh M1 data for symbol - matches M1DataFetcher.refresh_symbol() signature"""
        return self.shared_service.refresh_symbol(symbol, force=True)
    
    def force_refresh(self, symbol: str) -> bool:
        """Force refresh on error/stale data - matches M1DataFetcher.force_refresh() signature"""
        return self.shared_service.refresh_symbol(symbol, force=True)
    
    def get_data_age(self, symbol: str) -> Optional[float]:
        """Get data age in seconds - matches M1DataFetcher.get_data_age() signature"""
        return self.shared_service.get_cache_age(symbol, "M1")
    
    def get_all_symbols(self) -> List[str]:
        """Get list of all symbols with cached data - matches M1DataFetcher.get_all_symbols() signature"""
        # Get cache stats and extract symbol list
        # Note: get_cache_stats() should return a dict with 'symbols' key containing list of cached symbols
        stats = self.shared_service.get_cache_stats()
        return list(stats.get('symbols', []))
    
    def is_data_stale(self, symbol: str, max_age_seconds: int = 180) -> bool:
        """Check if cached data is stale - matches M1DataFetcher.is_data_stale() signature"""
        age = self.get_data_age(symbol)
        if age is None:
            return True
        return age > max_age_seconds
    
    def clear_cache(self, symbol: str = None) -> None:
        """Clear cache - matches M1DataFetcher.clear_cache() signature"""
        self.shared_service.clear_cache(symbol=symbol, timeframe="M1")
```

---

## 4. Integration Strategy

### 4.1 Feature Flags

**Implementation:**
- Environment variable: `USE_SHARED_DATA_SERVICE=true/false`
- Config file: `config/shared_data_service.json`
- Runtime toggle: API endpoint to enable/disable

**Usage:**
```python
USE_SHARED_DATA_SERVICE = os.getenv("USE_SHARED_DATA_SERVICE", "false").lower() == "true"

if USE_SHARED_DATA_SERVICE:
    data_service = SharedDataService.get_instance(mt5_service, ...)
    m1_fetcher = M1DataFetcherCompat(data_service)
else:
    m1_fetcher = M1DataFetcher(mt5_service, ...)  # Old system
```

### 4.2 Gradual Migration Path

#### Step 1: Shadow Mode (Phase 1)
- Run both systems in parallel
- Compare results
- Log discrepancies
- No production impact

#### Step 2: Read-Only Integration (Phase 2)
- Use shared service for reads only
- Keep old system for writes
- Validate data consistency
- Monitor performance

#### Step 3: Full Integration (Phase 3)
- Replace old system completely
- Remove fallback code
- Optimize performance

### 4.3 Integration Points

#### Desktop Agent Integration

**File**: `desktop_agent.py`

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

**Changes:**
```python
# After
if USE_SHARED_DATA_SERVICE:
    from infra.shared_data_service import SharedDataService, M1DataFetcherCompat
    if not hasattr(registry, 'shared_data_service') or registry.shared_data_service is None:
        registry.shared_data_service = SharedDataService.get_instance(
            mt5_service=mt5_service,
            session_manager=session_manager,
            asset_profiles=asset_profiles,
            threshold_manager=threshold_manager,
            m1_refresh_manager=None
        )
    registry.m1_data_fetcher = M1DataFetcherCompat(registry.shared_data_service)
else:
    if not hasattr(registry, 'm1_data_fetcher') or registry.m1_data_fetcher is None:
        registry.m1_data_fetcher = M1DataFetcher(
            data_source=mt5_service,
            max_candles=200,
            cache_ttl=300
        )
```

**Integration Points:**
1. `tool_analyse_symbol_full()` - M1 data fetching
2. `tool_get_m1_microstructure()` - M1 microstructure analysis
3. Any other functions using `registry.m1_data_fetcher`

**Migration Path:**
- Phase 1: Add shared service alongside existing M1DataFetcher (shadow mode)
- Phase 2: Switch to shared service with feature flag
- Phase 3: Remove old M1DataFetcher initialization

#### Alert System Integration

**File**: `infra/alert_monitor.py`

**Changes:**
```python
# Before
self.m1_data_fetcher = M1DataFetcher(mt5_service, max_candles=200)

# After
if USE_SHARED_DATA_SERVICE:
    from infra.shared_data_service import SharedDataService, M1DataFetcherCompat
    shared_service = SharedDataService.get_instance(mt5_service, ...)
    self.m1_data_fetcher = M1DataFetcherCompat(shared_service)
else:
    self.m1_data_fetcher = M1DataFetcher(mt5_service, max_candles=200)
```

**Integration Points:**
1. `_check_order_block_alert()` - M1 data fetching
2. `_check_structure_alert()` - M5/M15 data fetching
3. `_check_volatility_alert()` - Indicator data fetching

#### Auto Execution Integration

**File**: `auto_execution_system.py`

**Changes:**
```python
# Before
self.m1_data_fetcher = M1DataFetcher(data_source=mt5_service, max_candles=200)
self.m1_refresh_manager = M1RefreshManager(...)

# After
if USE_SHARED_DATA_SERVICE:
    from infra.shared_data_service import SharedDataService, M1DataFetcherCompat
    shared_service = SharedDataService.get_instance(
        mt5_service=mt5_service,
        session_manager=session_manager,
        asset_profiles=asset_profiles,
        threshold_manager=threshold_manager,
        m1_refresh_manager=None  # Shared service manages refresh internally
    )
    self.m1_data_fetcher = M1DataFetcherCompat(shared_service)
    # Use shared service refresh methods instead of m1_refresh_manager
    self.m1_refresh_manager = None  # Replaced by shared service
else:
    self.m1_data_fetcher = M1DataFetcher(data_source=mt5_service, max_candles=200)
    self.m1_refresh_manager = M1RefreshManager(...)
```

**Integration Points:**
1. `_check_conditions()` - M1 data for order blocks
2. `_check_conditions()` - M5/M15 data for structure
3. `_check_conditions()` - Indicator data for volatility
4. `_batch_refresh_m1_data()` - Use shared service batch refresh method

**M1RefreshManager Integration:**
- Shared service creates its own M1RefreshManager instance internally during initialization
- Uses shared service's internal M1DataFetcher (or compatibility wrapper) as the fetcher parameter
- Exposes refresh methods through shared service API:
  - `refresh_symbol(symbol: str, force: bool = False) -> bool`
  - `refresh_symbols_batch(symbols: List[str]) -> Dict[str, bool]`
  - `check_and_refresh_stale(symbol: str, max_age_seconds: int = 180) -> bool`
- Auto execution uses shared service refresh methods instead of direct M1RefreshManager
- Batch refresh coordination handled by shared service's internal M1RefreshManager
- If `m1_refresh_manager` parameter is provided to `get_instance()`, it will be used; otherwise, shared service creates its own

---

## 5. Testing Strategy

### 5.1 Unit Tests

#### Test Suite 1: SharedDataService Core
- **Test 1.1**: Singleton pattern (single instance)
- **Test 1.2**: Thread safety (concurrent requests)
- **Test 1.3**: Cache TTL expiration
- **Test 1.4**: Cache size limits (LRU eviction)
- **Test 1.5**: Symbol normalization
- **Test 1.6**: Error handling (MT5 failure)

#### Test Suite 2: Data Fetching
- **Test 2.1**: M1 data fetch (fresh)
- **Test 2.2**: M1 data fetch (cached)
- **Test 2.3**: M5/M15/H1 data fetch
- **Test 2.4**: Batch requests (same symbol)
- **Test 2.5**: Concurrent requests (different symbols)

#### Test Suite 3: Caching
- **Test 3.1**: Cache hit/miss tracking
- **Test 3.2**: Cache invalidation (TTL)
- **Test 3.3**: Cache invalidation (manual)
- **Test 3.4**: Cache statistics accuracy
- **Test 3.5**: Memory usage limits

#### Test Suite 4: Compatibility Wrapper
- **Test 4.1**: M1DataFetcherCompat API compatibility
- **Test 4.2**: Return format compatibility
- **Test 4.3**: Error handling compatibility

### 5.2 Integration Tests

#### Test Suite 5: Alert System Integration
- **Test 5.1**: Order block detection (shared service)
- **Test 5.2**: Structure alerts (shared service)
- **Test 5.3**: Volatility alerts (shared service)
- **Test 5.4**: Fallback to old system on failure
- **Test 5.5**: Performance comparison (old vs new)

#### Test Suite 6: Auto Execution Integration
- **Test 6.1**: Order block condition check (shared service)
- **Test 6.2**: Structure condition check (shared service)
- **Test 6.3**: Indicator condition check (shared service)
- **Test 6.4**: Fallback to old system on failure
- **Test 6.5**: Performance comparison (old vs new)

#### Test Suite 7: Shadow Mode
- **Test 7.1**: Run both systems in parallel
- **Test 7.2**: Compare results (data consistency)
- **Test 7.3**: Log discrepancies
- **Test 7.4**: Performance metrics comparison

### 5.3 Performance Tests

#### Test Suite 8: Load Testing
- **Test 8.1**: 10 concurrent requests (same symbol)
- **Test 8.2**: 10 concurrent requests (different symbols)
- **Test 8.3**: 100 requests over 1 minute
- **Test 8.4**: Cache hit rate under load
- **Test 8.5**: Memory usage under load

#### Test Suite 9: Stress Testing
- **Test 9.1**: MT5 connection failure handling
- **Test 9.2**: Cache exhaustion (memory limits)
- **Test 9.3**: Concurrent cache invalidation
- **Test 9.4**: Long-running stability (24 hours)

### 5.4 A/B Testing

#### Test Suite 10: Production A/B Test
- **Test 10.1**: 10% traffic to shared service
- **Test 10.2**: Monitor error rates
- **Test 10.3**: Monitor performance metrics
- **Test 10.4**: Gradual rollout (10% → 50% → 100%)

### 5.5 Test Data & Fixtures

**Mock MT5 Service:**
- Simulate MT5 responses
- Simulate connection failures
- Simulate slow responses
- Simulate data gaps

**Test Symbols:**
- XAUUSDc (Gold)
- BTCUSDc (Bitcoin)
- EURUSDc (Forex)

**Test Scenarios:**
- Normal operation
- High load
- MT5 failure
- Cache expiration
- Concurrent requests

---

## 6. Fallback Logic

### 6.1 Automatic Fallback

**Trigger Conditions:**
1. Shared service initialization failure
2. Service health check failure (3 consecutive failures)
3. Data fetch failure (with retry exhausted)
4. Cache corruption detected
5. Performance degradation (response time > 1 second)

**Fallback Implementation:**
```python
class SharedDataService:
    def _initialize(self, mt5_service, ...):
        self.mt5_service = mt5_service
        self.fallback_enabled = True
        self.fallback_to_old = False
        self.failure_count = 0
        self.max_failures = 3
        
        # Create fallback M1DataFetcher instance
        from infra.m1_data_fetcher import M1DataFetcher
        self._fallback_fetcher = M1DataFetcher(data_source=mt5_service, max_candles=200)
        
        # Create fallback IndicatorBridge if needed
        from infra.indicator_bridge import IndicatorBridge
        self._fallback_indicator_bridge = IndicatorBridge(None)
    
    def get_m1_data(self, symbol: str, ...):
        if self.fallback_to_old:
            logger.debug(f"Using fallback M1DataFetcher for {symbol}")
            return self._fallback_fetcher.fetch_m1_data(symbol, ...)
        
        try:
            result = self._get_m1_data_internal(symbol, ...)
            self.failure_count = 0  # Reset on success
            return result
        except Exception as e:
            self.failure_count += 1
            logger.error(f"Shared service error: {e}, failure count: {self.failure_count}")
            
            if self.failure_count >= self.max_failures:
                logger.warning("Enabling fallback to old system")
                self.fallback_to_old = True
                return self._fallback_fetcher.fetch_m1_data(symbol, ...)
            
            raise  # Re-raise for retry logic
```

### 6.2 Manual Fallback

**Via Feature Flag:**
```python
# Disable shared service
USE_SHARED_DATA_SERVICE = False
```

**Via API Endpoint:**
```python
POST /api/shared-data-service/disable
POST /api/shared-data-service/enable
```

**Via Config File:**
```json
{
  "shared_data_service": {
    "enabled": false,
    "fallback_reason": "Manual disable due to performance issues"
  }
}
```

### 6.3 Fallback Monitoring

**Metrics to Track:**
- Fallback activation count
- Fallback duration
- Error rates (shared service vs fallback)
- Performance comparison (shared service vs fallback)

**Alerts:**
- Alert on fallback activation
- Alert on repeated fallbacks
- Alert on performance degradation

---

## 7. Migration Phases

### Phase 1: Foundation (Week 1-2)

**Goals:**
- Create SharedDataService core
- Implement basic caching
- Unit tests (80%+ coverage)

**Deliverables:**
- `infra/shared_data_service.py`
- `infra/shared_data_cache.py`
- Unit test suite
- Documentation

**Success Criteria:**
- All unit tests pass
- Code coverage > 80%
- Performance targets met (cache hit rate > 80%)

### Phase 2: Integration - Alert System (Week 3-4)

**Goals:**
- Integrate with Alert System
- Shadow mode testing
- Fallback logic implementation

**Deliverables:**
- Alert System integration code
- Shadow mode test suite
- Fallback logic
- Integration tests

**Success Criteria:**
- Shadow mode runs without errors
- Data consistency validated (100% match)
- Fallback works correctly
- Performance improved (30%+ CPU reduction)

### Phase 3: Integration - Auto Execution (Week 5-6)

**Goals:**
- Integrate with Auto Execution System
- Shadow mode testing
- Full system validation

**Deliverables:**
- Auto Execution integration code
- Full system test suite
- Performance benchmarks
- Migration guide

**Success Criteria:**
- Both systems use shared service
- Data consistency validated
- Performance improved (30%+ CPU reduction)
- No production errors

### Phase 4: Integration - Desktop Agent (Week 7)

**Goals:**
- Integrate with Desktop Agent
- Registry integration
- Tool function updates

**Deliverables:**
- Desktop Agent integration code
- Registry updates
- Tool function modifications
- Integration tests

**Success Criteria:**
- Desktop Agent uses shared service
- Registry properly initialized
- Tool functions work correctly
- No breaking changes

### Phase 5: Production Rollout (Week 8-9)

**Goals:**
- Gradual production rollout
- Monitor performance
- Optimize based on metrics

**Deliverables:**
- Production deployment
- Monitoring dashboard
- Performance reports
- Optimization recommendations

**Success Criteria:**
- 100% traffic on shared service
- CPU usage reduced by 30-50%
- RAM usage reduced by 20-30%
- Zero production incidents

### Phase 6: Cleanup (Week 10)

**Goals:**
- Remove old code
- Final optimizations
- Documentation update

**Deliverables:**
- Removed duplicate code
- Final performance report
- Updated documentation
- Lessons learned document

**Success Criteria:**
- Old code removed
- Documentation updated
- Performance targets met

---

## 8. Performance Targets

**Baseline Measurement Methodology:**
1. **Measurement Period**: 7 days of normal operation
2. **Measurement Times**: 
   - Peak hours (market open): 08:00-17:00 UTC
   - Off-peak hours: 17:00-08:00 UTC
3. **Metrics Collected**:
   - Average CPU % (1-minute intervals)
   - Peak CPU % (5-minute windows)
   - RAM usage (peak and average)
   - Cache hit rates
   - Response times
4. **System Variations**: 
   - Account for market volatility (high volatility = higher CPU)
   - Account for number of active symbols
   - Account for number of active plans/alerts
5. **Acceptable Variance**: ±5% (account for natural system variations)

### 8.1 CPU Reduction

**Target:** 30-50% reduction in CPU usage

**Measurement:**
- Baseline: Current CPU usage (alerts + auto-execution) - measured over 7 days
- Target: CPU usage with shared service - measured over 7 days
- Metric: Average CPU % over 24 hours
- **Acceptable Performance**: 25-55% reduction (accounts for ±5% variance)
- **Target Performance**: 30-50% reduction

**Validation:**
- Monitor CPU usage for 1 week
- Compare before/after metrics
- Validate target achieved (within acceptable range)
- **Performance Regression Tests**: Run automated tests comparing old vs new system performance

### 8.2 RAM Reduction

**Target:** 20-30% reduction in RAM usage

**Measurement:**
- Baseline: Current RAM usage (alerts + auto-execution)
- Target: RAM usage with shared service
- Metric: Peak RAM usage over 24 hours

**Validation:**
- Monitor RAM usage for 1 week
- Compare before/after metrics
- Validate target achieved

### 8.3 Cache Performance

**Target:** Cache hit rate > 80%

**Measurement:**
- Cache hits / (Cache hits + Cache misses)
- Metric: Average over 1 hour windows

**Validation:**
- Monitor cache hit rate for 1 week
- Validate target achieved
- Optimize if below target

### 8.4 Response Time

**Target:** 
- Cached data: < 50ms
- Fresh fetch: < 500ms

**Measurement:**
- P50, P95, P99 latencies
- Metric: Average over 1 hour windows

**Validation:**
- Monitor response times for 1 week
- Validate targets achieved
- Optimize if above targets

---

## 9. Risk Mitigation

### Risk 1: Service Failure

**Impact:** High (both systems affected)

**Mitigation:**
- Comprehensive error handling
- Automatic fallback to old system
- Health check monitoring
- Alert on service failures

### Risk 2: Data Inconsistency

**Impact:** High (incorrect trade decisions)

**Mitigation:**
- Shadow mode validation
- Data consistency tests
- Comprehensive logging
- Gradual rollout

### Risk 3: Performance Degradation

**Impact:** Medium (slower response times)

**Mitigation:**
- Performance benchmarks
- Load testing
- Cache optimization
- Monitoring and alerting

### Risk 4: Cache Corruption

**Impact:** Medium (incorrect data returned)

**Mitigation:**
- Cache validation
- TTL-based expiration
- Cache invalidation on errors
- Fallback on corruption detection

### Risk 5: Thread Safety Issues

**Impact:** High (race conditions, data corruption)

**Mitigation:**
- Thread-safe design
- Comprehensive concurrency tests
- Lock mechanisms
- Code review

---

## 10. Success Criteria

### 10.1 Functional Success

- ✅ All unit tests pass (100%)
- ✅ All integration tests pass (100%)
- ✅ Shadow mode validation (100% data consistency)
- ✅ Fallback logic works correctly
- ✅ Zero production errors

### 10.2 Performance Success

- ✅ CPU usage reduced by 30-50%
- ✅ RAM usage reduced by 20-30%
- ✅ Cache hit rate > 80%
- ✅ Response time targets met
- ✅ No performance degradation

### 10.3 Operational Success

- ✅ Zero downtime migration
- ✅ No data loss
- ✅ No incorrect trade executions
- ✅ Monitoring and alerting functional
- ✅ Documentation complete

### 10.4 Business Success

- ✅ Reduced infrastructure costs
- ✅ Improved system reliability
- ✅ Better resource utilization
- ✅ Scalability improved

---

## 11. Monitoring & Observability

### 11.1 Metrics to Track

**Performance Metrics:**
- Cache hit rate
- Response time (P50, P95, P99)
- Request throughput
- Error rate
- CPU usage
- RAM usage

**Operational Metrics:**
- Service uptime
- Fallback activation count
- MT5 connection status
- Cache size
- Active symbols

### 11.2 Logging

**Log Levels:**
- DEBUG: Cache hits/misses, request details
- INFO: Service status, cache statistics
- WARNING: Fallback activation, performance issues
- ERROR: Service failures, data errors

**Log Format:**
```json
{
  "timestamp": "2025-11-20T17:30:00Z",
  "level": "INFO",
  "service": "SharedDataService",
  "symbol": "XAUUSDc",
  "timeframe": "M1",
  "cache_hit": true,
  "response_time_ms": 15,
  "cache_size": 1024
}
```

### 11.3 Alerts

**Alert Conditions:**
- Service health check failure (3 consecutive)
- Cache hit rate < 70%
- Response time > 1 second (P95)
- Error rate > 1%
- Fallback activation
- Memory usage > 80%

### 11.4 Dashboards

**Dashboard 1: Service Health**
- Service status
- Health check results
- Error rates
- Uptime

**Dashboard 2: Performance**
- Cache hit rate
- Response times
- Throughput
- CPU/RAM usage

**Dashboard 3: Cache Statistics**
- Cache size
- Cache evictions
- TTL distribution
- Memory usage

---

## 12. Documentation

### 12.1 Developer Documentation

- API reference
- Integration guide
- Testing guide
- Troubleshooting guide

### 12.2 Operational Documentation

- Deployment guide
- Monitoring guide
- Incident response guide
- Performance tuning guide

### 12.3 User Documentation

- Feature overview
- Migration guide
- FAQ
- Best practices

---

## 13. Configuration Management

### 13.1 Configuration File Structure

**File**: `config/shared_data_service.json`

```json
{
  "enabled": true,
  "cache": {
    "m1_ttl_seconds": 30,
    "m5_ttl_seconds": 60,
    "m15_ttl_seconds": 120,
    "h1_ttl_seconds": 300,
    "indicator_ttl_seconds": 60,
    "microstructure_ttl_seconds": 60,
    "max_cache_size_mb": 50,
    "eviction_policy": "LRU"
  },
  "performance": {
    "max_concurrent_requests": 10,
    "request_timeout_seconds": 5,
    "retry_count": 3,
    "retry_backoff_seconds": [1, 2, 4],
    "circuit_breaker_threshold": 5,
    "circuit_breaker_timeout_seconds": 60
  },
  "fallback": {
    "enabled": true,
    "max_failures": 3,
    "auto_fallback": true
  },
  "refresh": {
    "batch_size": 10,
    "refresh_interval_active_seconds": 30,
    "refresh_interval_inactive_seconds": 300,
    "lazy_loading": true
  }
}
```

### 13.2 Runtime Configuration Updates

**API Endpoints:**
```python
# Get current configuration
GET /api/shared-data-service/config

# Update configuration
POST /api/shared-data-service/config
{
  "cache": {
    "m1_ttl_seconds": 45  # Update M1 TTL
  }
}

# Reset to defaults
POST /api/shared-data-service/config/reset
```

**Programmatic Updates:**
```python
shared_service = SharedDataService.get_instance(...)
shared_service.update_config({
    "cache": {"m1_ttl_seconds": 45}
})
```

### 13.3 Environment-Specific Configs

**Development**: `config/shared_data_service.dev.json`
- Longer TTLs for testing
- More verbose logging
- Lower cache limits

**Production**: `config/shared_data_service.prod.json`
- Optimized TTLs
- Standard logging
- Higher cache limits

**Testing**: `config/shared_data_service.test.json`
- Short TTLs for fast tests
- Mock MT5 service
- Minimal cache

---

## 14. Health Check Implementation

### 14.1 Health Check Criteria

**Health Status Levels:**
- **HEALTHY**: All systems operational, cache hit rate > 80%, response time < 500ms
- **DEGRADED**: Some issues but functional, cache hit rate 50-80%, response time 500-1000ms
- **UNHEALTHY**: Critical issues, cache hit rate < 50%, response time > 1000ms, fallback active

**Health Check Components:**
1. **MT5 Connection**: Verify MT5 is connected and responsive
2. **Cache Status**: Verify cache is operational and within limits
3. **Performance**: Verify response times within targets
4. **Error Rate**: Verify error rate < 1%
5. **Memory Usage**: Verify memory usage < 80% of limit

### 14.2 Health Check Frequency

- **Internal Checks**: Every 30 seconds
- **API Endpoint**: On-demand (GET /api/shared-data-service/health)
- **Alert Checks**: Every 5 minutes (for alerting)

### 14.3 Health Check Endpoint Implementation

```python
@app.get("/api/shared-data-service/health")
async def health_check():
    health = shared_service.health_check()
    status_code = 200 if health['status'] == 'HEALTHY' else 503
    return JSONResponse(content=health, status_code=status_code)
```

**Response Format:**
```json
{
  "status": "HEALTHY",
  "timestamp": "2025-11-20T17:30:00Z",
  "components": {
    "mt5_connection": "OK",
    "cache": "OK",
    "performance": "OK",
    "error_rate": 0.1
  },
  "metrics": {
    "cache_hit_rate": 85.5,
    "avg_response_time_ms": 45,
    "memory_usage_mb": 32,
    "active_symbols": 5
  }
}
```

---

## 15. Metrics Collection

### 15.1 Metrics Library

**Implementation**: Custom metrics collection (lightweight, no external dependencies)

**Alternative**: Prometheus (if monitoring infrastructure available)

### 15.2 Metrics Export Format

**Format**: JSON (for easy integration with existing monitoring)

**Metrics Collected:**
```json
{
  "cache": {
    "hits": 1250,
    "misses": 250,
    "hit_rate": 83.3,
    "size_mb": 32.5,
    "evictions": 15
  },
  "performance": {
    "avg_response_time_ms": 45,
    "p95_response_time_ms": 120,
    "p99_response_time_ms": 250,
    "requests_per_second": 5.2
  },
  "errors": {
    "total": 5,
    "rate": 0.4,
    "by_type": {
      "mt5_connection": 2,
      "timeout": 2,
      "invalid_symbol": 1
    }
  },
  "system": {
    "cpu_percent": 12.5,
    "memory_mb": 32.5,
    "active_symbols": 5,
    "uptime_seconds": 86400
  }
}
```

### 15.3 Metrics Aggregation Strategy

**Aggregation Windows:**
- **Real-time**: Last 1 minute
- **Short-term**: Last 1 hour (1-minute intervals)
- **Long-term**: Last 24 hours (5-minute intervals)

**Storage:**
- In-memory for real-time metrics
- Optional: Export to file/database for historical analysis

**Export Endpoints:**
```python
GET /api/shared-data-service/metrics/realtime
GET /api/shared-data-service/metrics/hourly
GET /api/shared-data-service/metrics/daily
```

---

## 16. Timeline Summary

| Phase | Duration | Key Activities |
|-------|----------|----------------|
| **Phase 1: Foundation** | 2 weeks | Core service, caching, unit tests |
| **Phase 2: Alert Integration** | 2 weeks | Alert system integration, shadow mode |
| **Phase 3: Auto Execution Integration** | 2 weeks | Auto execution integration, validation |
| **Phase 4: Desktop Agent Integration** | 1 week | Desktop agent integration, registry updates |
| **Phase 5: Production Rollout** | 2 weeks | Gradual rollout, monitoring |
| **Phase 6: Cleanup** | 1 week | Code cleanup, documentation |
| **Total** | **10 weeks** | Full implementation (added 1 week buffer for unexpected issues) |

---

## 17. Additional Test Suites

### 17.1 Desktop Agent Integration Tests

#### Test Suite 11: Desktop Agent Integration
- **Test 11.1**: Registry integration (shared service in registry)
- **Test 11.2**: Compatibility with existing usage patterns
- **Test 11.3**: Tool functions using shared service
- **Test 11.4**: Fallback to old system on failure
- **Test 11.5**: Performance comparison (old vs new)

### 17.2 M1RefreshManager Compatibility Tests

#### Test Suite 12: M1RefreshManager Integration
- **Test 12.1**: Batch refresh coordination
- **Test 12.2**: Refresh scheduling compatibility
- **Test 12.3**: Lazy loading behavior
- **Test 12.4**: Active symbol tracking
- **Test 12.5**: Refresh performance

### 17.3 Cache Synchronization Tests

#### Test Suite 13: Cache Synchronization
- **Test 13.1**: Concurrent cache updates
- **Test 13.2**: Cache invalidation propagation
- **Test 13.3**: Stale data detection
- **Test 13.4**: Cache versioning
- **Test 13.5**: Background refresh coordination

### 17.4 Fallback Mechanism Tests

#### Test Suite 14: Fallback Mechanism
- **Test 14.1**: Automatic fallback activation
- **Test 14.2**: Fallback instance creation
- **Test 14.3**: Fallback data consistency
- **Test 14.4**: Fallback recovery
- **Test 14.5**: Fallback performance

### 17.5 Configuration Update Tests

#### Test Suite 15: Configuration Management
- **Test 15.1**: Runtime configuration updates
- **Test 15.2**: Configuration persistence
- **Test 15.3**: Environment-specific configs
- **Test 15.4**: Configuration validation
- **Test 15.5**: Configuration rollback

---

## 18. Next Steps

1. **Review & Approval**: Review this updated plan with stakeholders
2. **Address Critical Issues**: Ensure all critical issues from review are addressed
3. **Resource Allocation**: Assign developers and testers
4. **Environment Setup**: Set up development and testing environments
5. **Kickoff Meeting**: Align team on plan and timeline
6. **Start Phase 1**: Begin implementation of core service

---

## 19. Plan Updates & Review Status

**Last Updated**: 2025-11-20

**Review Status**: ✅ All issues addressed (First Review + Second Review)

**Changes Made (First Review):**
1. ✅ Fixed singleton initialization pattern (Issue 1)
2. ✅ Fixed fallback logic implementation (Issue 2)
3. ✅ Added M1RefreshManager integration (Issue 3)
4. ✅ Added Desktop Agent integration (Issue 4)
5. ✅ Documented M1MicrostructureAnalyzer dependencies (Issue 5)
6. ✅ Added cache synchronization strategy (Issue 6)
7. ✅ Completed compatibility wrapper API (Issue 7)
8. ✅ Added thread safety details (Issue 8)
9. ✅ Specified error handling parameters (Issue 9)
10. ✅ Defined performance target methodology (Issue 10)
11. ✅ Added configuration management section
12. ✅ Added health check implementation section
13. ✅ Added metrics collection section
14. ✅ Added additional test suites
15. ✅ Updated timeline (added 1 week buffer)

**Changes Made (Second Review):**
16. ✅ Fixed section numbering gap (added sections 13-15)
17. ✅ Fixed phase numbering inconsistency (added Phase 4: Desktop Agent to Section 7)
18. ✅ Added missing API methods (get_cache_age, refresh_symbol, refresh_symbols_batch, check_and_refresh_stale)
19. ✅ Clarified M1RefreshManager initialization logic (internal creation with internal fetcher)
20. ✅ Completed Table of Contents (all sections 1-19)
21. ✅ Aligned timeline consistency (10 weeks total, phases 1-6)

**Changes Made (Third Review):**
22. ✅ Fixed compatibility wrapper method names to match actual M1DataFetcher API:
    - `get_latest_candle()` → `get_latest_m1()` (correct method name)
    - `refresh_data()` → `refresh_symbol()` (correct method name)
    - `get_cache_age()` → `get_data_age()` (correct method name)
23. ✅ Added missing methods to compatibility wrapper:
    - `fetch_m1_data_async()` (async variant)
    - `force_refresh()` (force refresh method)
    - `get_all_symbols()` (get cached symbols list)
    - `is_data_stale()` (check data staleness)
24. ✅ Clarified `get_cache_stats()` return format (should include 'symbols' list)

**Changes Made (Fourth Review):**
25. ✅ Fixed async method signature: Added `use_cache` parameter to `get_m1_data_async()` in primary API to match compatibility wrapper
26. ✅ Clarified IndicatorBridge integration: Documented that `get_multi_indicators()` maps to `IndicatorBridge.get_multi()`

**Status**: ✅ All Issues Fixed - Ready for Implementation

---

*Plan Created: 2025-11-20*  
*Last Updated: 2025-11-20*  
*Status: ✅ Updated - All Review Issues Addressed*

