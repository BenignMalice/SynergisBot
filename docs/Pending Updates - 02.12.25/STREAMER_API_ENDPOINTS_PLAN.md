# MultiTimeframeStreamer HTTP API Endpoints - Implementation Plan

**Date:** 2025-12-05  
**Status:** 📋 Planning  
**Priority:** High

---

## Objective

Expose HTTP API endpoints in `app/main_api.py` to allow the micro-scalp monitor (running in `main_api.py`) to access MultiTimeframeStreamer data efficiently.

---

## Architecture Overview

```
┌─────────────────────────────────┐
│  app/main_api.py (port 8000)    │
│  ┌───────────────────────────┐  │
│  │ MultiTimeframeStreamer     │  │
│  │ (in-memory buffers)        │  │
│  └───────────────────────────┘  │
│           │                       │
│           │ HTTP API              │
│           ▼                       │
│  ┌───────────────────────────┐  │
│  │ /streamer/* endpoints     │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
           │
           │ HTTP GET (localhost)
           │
┌─────────────────────────────────┐
│  main_api.py (port 8010)        │
│  ┌───────────────────────────┐  │
│  │ MicroScalpMonitor         │  │
│  │ _get_m1_candles()          │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

---

## API Endpoints Design

### 1. Get Candles for Symbol/Timeframe

**Endpoint:** `GET /streamer/candles/{symbol}/{timeframe}`

**Query Parameters:**
- `limit` (optional, default: 50): Number of candles to return
- `format` (optional, default: 'dict'): Response format ('dict' or 'raw')

**Example:**
```
GET /streamer/candles/BTCUSDc/M1?limit=50
GET /streamer/candles/XAUUSDc/M5?limit=100
```

**Response Format:**
```json
{
  "success": true,
  "symbol": "BTCUSDc",
  "timeframe": "M1",
  "count": 50,
  "candles": [
    {
      "time": 1701234567,
      "open": 42000.0,
      "high": 42050.0,
      "low": 41950.0,
      "close": 42025.0,
      "volume": 1234
    },
    ...
  ],
  "timestamp": "2025-12-05T08:00:00Z",
  "source": "streamer_buffer"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Symbol not found in streamer",
  "symbol": "BTCUSDc",
  "timeframe": "M1"
}
```

---

### 2. Get Streamer Status

**Endpoint:** `GET /streamer/status`

**Response:**
```json
{
  "success": true,
  "running": true,
  "symbols": ["BTCUSDc", "XAUUSDc"],
  "timeframes": ["M1", "M5", "M15"],
  "metrics": {
    "total_candles_buffered": 1500,
    "last_update": "2025-12-05T08:00:00Z",
    "uptime_seconds": 3600
  }
}
```

---

### 3. Get Available Symbols/Timeframes

**Endpoint:** `GET /streamer/available`

**Response:**
```json
{
  "success": true,
  "symbols": {
    "BTCUSDc": ["M1", "M5", "M15"],
    "XAUUSDc": ["M1", "M5", "M15"]
  }
}
```

---

### 4. Health Check

**Endpoint:** `GET /streamer/health`

**Response:**
```json
{
  "status": "healthy",
  "streamer_running": true,
  "buffer_status": "ok",
  "last_check": "2025-12-05T08:00:00Z"
}
```

---

## Implementation Details

### 1. Endpoint Location

**File:** `app/main_api.py`

**Integration:**
- Add endpoints after streamer initialization in `startup_event()`
- Use FastAPI router or direct app routes
- Access `multi_tf_streamer` global variable

---

### 2. Endpoint Implementation

**Key Functions:**

```python
@router.get("/streamer/candles/{symbol}/{timeframe}")
async def get_streamer_candles(
    symbol: str,
    timeframe: str,
    limit: int = 50,
    format: str = "dict"
):
    """
    Get candles from MultiTimeframeStreamer buffer.
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDc')
        timeframe: Timeframe ('M1', 'M5', 'M15')
        limit: Number of candles to return (default: 50)
        format: Response format ('dict' or 'raw')
    
    Returns:
        JSON response with candles or error
    """
    # 1. Check if streamer is available
    # 2. Check if streamer is running
    # 3. Get candles from streamer buffer
    # 4. Convert to dict format if needed
    # 5. Return JSON response
```

---

### 3. Data Conversion

**Streamer returns:** `List[Candle]` objects (from `multi_timeframe_streamer.py`)

**Need to convert to:** List of dictionaries for JSON serialization

**Conversion Logic:**
- Check if `Candle` has `to_dict()` method (preferred)
- Fallback: Manual conversion using object attributes
- Handle both `Candle` objects and already-dict formats

---

### 4. Error Handling

**Scenarios to Handle:**
1. Streamer not initialized → Return error
2. Streamer not running → Return error with status
3. Symbol not in streamer → Return error
4. Timeframe not available → Return error
5. Insufficient candles → Return available candles with warning
6. Invalid parameters → Return validation error

**Error Response Format:**
```json
{
  "success": false,
  "error": "Error message",
  "error_code": "STREAMER_NOT_RUNNING",
  "details": {}
}
```

---

### 5. Performance Considerations

**Caching:**
- No caching needed (streamer buffer is already in-memory)
- Response time should be < 10ms for localhost

**Rate Limiting:**
- Optional: Add rate limiting if needed
- Default: No rate limiting (internal API)

**Response Size:**
- Limit max `limit` parameter (e.g., max 500 candles)
- Prevent excessive data transfer

---

### 6. Security

**Since this is localhost-only:**
- No authentication required (internal API)
- Optional: Add simple API key if needed
- Validate input parameters (symbol, timeframe, limit)

**Input Validation:**
- Validate symbol format
- Validate timeframe (only allow M1, M5, M15, etc.)
- Validate limit (1-500 range)

---

## Micro-Scalp Monitor Integration

### 1. Update `_get_m1_candles()` Method

**File:** `infra/micro_scalp_monitor.py`

**New Priority Order:**
1. **Try HTTP API** (streamer via API) - Fastest, in-memory
2. **Try direct streamer** (if available) - Fallback
3. **Try MT5** (last resort) - Slowest

**Implementation:**
```python
def _get_m1_candles(self, symbol: str, limit: int = 50) -> Optional[List[Dict]]:
    # 1. Try HTTP API first (streamer via API)
    candles = self._get_candles_from_api(symbol, 'M1', limit)
    if candles:
        return candles
    
    # 2. Try direct streamer (if available)
    if self.streamer and self.streamer.is_running:
        candles = self._get_candles_from_streamer(symbol, 'M1', limit)
        if candles:
            return candles
    
    # 3. Fallback to MT5
    return self._get_candles_from_mt5(symbol, 'M1', limit)
```

---

### 2. HTTP Client Method

**Add to `MicroScalpMonitor`:**
```python
def _get_candles_from_api(self, symbol: str, timeframe: str, limit: int) -> Optional[List[Dict]]:
    """
    Get candles from streamer via HTTP API.
    
    Args:
        symbol: Trading symbol
        timeframe: Timeframe ('M1', 'M5', 'M15')
        limit: Number of candles
    
    Returns:
        List of candle dicts or None
    """
    try:
        import httpx
        url = f"http://localhost:8000/streamer/candles/{symbol}/{timeframe}"
        params = {"limit": limit}
        
        response = httpx.get(url, params=params, timeout=1.0)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("candles"):
                return data["candles"]
    except Exception as e:
        logger.debug(f"[{symbol}] API call failed: {e}")
    
    return None
```

---

### 3. Configuration

**Add to `MicroScalpMonitor.__init__()`:**
```python
# Streamer API configuration
self.streamer_api_url = os.getenv(
    "STREAMER_API_URL",
    "http://localhost:8000"
)
self.streamer_api_timeout = 1.0  # 1 second timeout
```

---

## Testing Strategy

### 1. Unit Tests

**Test Cases:**
- Endpoint returns candles for valid symbol/timeframe
- Endpoint returns error for invalid symbol
- Endpoint returns error for invalid timeframe
- Endpoint handles missing streamer gracefully
- Endpoint validates limit parameter
- Response format is correct JSON

---

### 2. Integration Tests

**Test Cases:**
- Monitor can fetch candles via API
- Monitor falls back correctly when API unavailable
- API performance is acceptable (< 10ms)
- Multiple concurrent requests work correctly

---

### 3. Manual Testing

**Steps:**
1. Start `app/main_api.py` (streamer running)
2. Start `main_api.py` (monitor running)
3. Check logs for API calls
4. Verify monitor gets candles successfully
5. Stop `app/main_api.py`, verify fallback works

---

## Implementation Checklist

### Phase 1: API Endpoints
- [ ] Add `/streamer/candles/{symbol}/{timeframe}` endpoint
- [ ] Add `/streamer/status` endpoint
- [ ] Add `/streamer/available` endpoint
- [ ] Add `/streamer/health` endpoint
- [ ] Implement error handling
- [ ] Add input validation
- [ ] Test endpoints manually

### Phase 2: Monitor Integration
- [ ] Add `_get_candles_from_api()` method
- [ ] Update `_get_m1_candles()` priority order
- [ ] Add HTTP client (httpx or requests)
- [ ] Add configuration for API URL
- [ ] Add error handling and logging
- [ ] Test monitor integration

### Phase 3: Testing & Optimization
- [ ] Write unit tests for endpoints
- [ ] Write integration tests
- [ ] Performance testing (response time)
- [ ] Load testing (concurrent requests)
- [ ] Update documentation

### Phase 4: Deployment
- [ ] Verify endpoints work in production
- [ ] Monitor API usage in logs
- [ ] Verify fallback works correctly
- [ ] Document API usage

---

## Performance Expectations

**Response Time:**
- API endpoint: < 10ms (localhost)
- Monitor API call: < 15ms (including network)
- Total overhead: < 20ms vs direct streamer access

**Throughput:**
- Should handle 100+ requests/second
- No rate limiting needed for internal use

**Memory:**
- No additional memory overhead (using existing buffer)
- HTTP responses are small (JSON serialization)

---

## Rollback Plan

If issues occur:
1. Monitor will automatically fall back to MT5
2. No breaking changes to existing functionality
3. Can disable API endpoints if needed
4. Direct streamer access still works

---

## Future Enhancements

**Potential Improvements:**
1. **WebSocket Support:** Real-time candle updates
2. **Caching Layer:** Redis cache for frequently accessed candles
3. **Metrics Endpoint:** Detailed streamer metrics
4. **Batch Requests:** Get multiple symbols/timeframes in one call
5. **Compression:** Gzip compression for large responses

---

## Dependencies

**Required:**
- `httpx` or `requests` (for HTTP client in monitor)
- FastAPI (already in use)
- `multi_tf_streamer` (already initialized)

**Optional:**
- `pydantic` (for request/response validation)
- `cachetools` (for response caching if needed)

---

## Documentation

**API Documentation:**
- Add to FastAPI auto-generated docs (`/docs`)
- Document all endpoints
- Include example requests/responses
- Document error codes

**Code Documentation:**
- Add docstrings to all endpoints
- Document integration with monitor
- Update README if needed

---

## Success Criteria

✅ Monitor successfully gets candles via API  
✅ Response time < 20ms total  
✅ Fallback to MT5 works when API unavailable  
✅ No breaking changes to existing functionality  
✅ All tests pass  
✅ Documentation complete  

---

## Timeline Estimate

- **Phase 1 (API Endpoints):** 2-3 hours
- **Phase 2 (Monitor Integration):** 1-2 hours
- **Phase 3 (Testing):** 1-2 hours
- **Phase 4 (Deployment):** 30 minutes

**Total:** ~5-8 hours

---

## Notes

- This is an internal API (localhost only)
- No authentication required
- Performance is critical (used every 5 seconds)
- Must be reliable (fallback to MT5 if fails)
- Keep it simple (no over-engineering)

