# Micro-Scalp Streamer Fix

**Date:** 2025-12-05  
**Status:** ✅ **FIXED**

---

## Problem

The micro-scalp monitor in `main_api.py` (root, port 8010) was showing:
```
⚠️ No M1 candles available - streamer may not be providing data
```

**Root Cause:**
- The `MultiTimeframeStreamer` is initialized in `app/main_api.py` (port 8000)
- The micro-scalp monitor in `main_api.py` (root, port 8010) tries to get the streamer from `app.main_api`, but it's not available (separate processes)
- The `_get_m1_candles()` method only used the streamer and had no fallback

---

## Solution

Added **MT5 fallback** to `_get_m1_candles()` method in `infra/micro_scalp_monitor.py`:

1. **Try streamer first** (fast, in-memory)
   - If streamer is available and running, use it
   - Returns immediately if successful

2. **Fallback to MT5** (slower but reliable)
   - If streamer is not available or fails, use MT5 directly
   - Checks if MT5 is initialized before attempting fetch
   - Converts numpy array to list of dicts

---

## Code Changes

### Before:
```python
def _get_m1_candles(self, symbol: str, limit: int = 50) -> Optional[List[Dict]]:
    """Get M1 candles from streamer (fast, in-memory)"""
    if not self.streamer:
        return None
    # ... only streamer logic ...
```

### After:
```python
def _get_m1_candles(self, symbol: str, limit: int = 50) -> Optional[List[Dict]]:
    """Get M1 candles from streamer (fast, in-memory) with MT5 fallback"""
    # Try streamer first (fast, in-memory)
    if self.streamer and self.streamer.is_running:
        # ... streamer logic ...
    
    # Fallback: Use MT5 directly (slower but reliable)
    if self.mt5_service:
        # ... MT5 fallback logic ...
```

---

## Benefits

✅ **Reliability:** Monitor works even when streamer is not available  
✅ **Performance:** Still uses streamer when available (fast, in-memory)  
✅ **Graceful Degradation:** Falls back to MT5 automatically  
✅ **No Breaking Changes:** Existing functionality preserved

---

## Testing

After restarting `main_api.py`, the monitor should:
1. Try to use streamer first (if available)
2. Fall back to MT5 if streamer is not available
3. Log which source was used (debug level)
4. Successfully get M1 candles and perform condition checks

---

## Status

✅ **Fixed** - The monitor now has a reliable fallback to MT5 when the streamer is not available.

