# Binance Disconnect Fix - Implementation Guide

## 🎯 **Problem Summary**
Binance WebSocket feeds disconnect when ChatGPT is used due to cross-thread MT5 API access causing event loop stalls.

## 🚀 **Solution Overview**
1. **Remove MT5 calls from Binance tick callback** - Prevent cross-thread access
2. **Create MT5 proxy service** - Single-thread executor for all MT5 calls
3. **Implement quote cache** - Thread-safe cache updated by main thread
4. **Add periodic calibration** - Offset updates on main thread timer
5. **Tune WebSocket parameters** - More forgiving ping/timeout settings

## 📋 **Implementation Steps**

### **Step 1: Immediate Fix (Test Solution)**
```bash
# Apply quick fix to test the solution
python apply_binance_fix_immediate.py

# This removes MT5 calls from Binance tick callback
# Test with ChatGPT to verify disconnects stop
```

### **Step 2: Full Implementation**

#### **2.1 Update Binance Service**
Replace `infra/binance_service.py` with `infra/binance_service_fixed.py`:
- No MT5 calls in tick callback
- Lightweight processing for stability
- Thread-safe price caching

#### **2.2 Integrate MT5 Proxy Service**
Add to `chatgpt_bot.py`:
```python
from infra.mt5_proxy_service import initialize_mt5_proxy, start_mt5_proxy

# Initialize MT5 proxy
mt5_proxy = initialize_mt5_proxy(mt5_service, update_interval=0.5)
await start_mt5_proxy()
```

#### **2.3 Add Periodic Calibration**
Add to `chatgpt_bot.py`:
```python
from infra.binance_service_fixed import PeriodicOffsetCalibrator

# Start periodic calibration
calibrator = PeriodicOffsetCalibrator(binance_service, mt5_proxy, interval=1.0)
await calibrator.start()
```

#### **2.4 Update API Endpoints**
Route all MT5 calls through proxy in `app/main_api.py`:
```python
from infra.mt5_proxy_service import get_mt5_proxy

# Replace direct MT5 calls with proxy calls
mt5_proxy = get_mt5_proxy()
if mt5_proxy:
    quote = await mt5_proxy.get_quote_async(symbol)
```

### **Step 3: WebSocket Tuning**
Update `infra/binance_stream.py`:
```python
# Add explicit ping parameters
websockets.connect(
    url,
    ping_interval=10,
    ping_timeout=10,
    close_timeout=5
)
```

## 🧪 **Testing Plan**

### **Test 1: Immediate Fix**
1. Apply immediate fix
2. Restart system
3. Ask ChatGPT questions
4. Verify no Binance disconnects

### **Test 2: Full Implementation**
1. Implement MT5 proxy service
2. Update Binance service
3. Add periodic calibration
4. Test with high ChatGPT load

### **Test 3: Performance Validation**
1. Monitor tick processing times
2. Check MT5 call latency
3. Verify price synchronization
4. Test under load

## 📊 **Expected Results**

### **Before Fix**
- ❌ Binance disconnects when ChatGPT is used
- ❌ Cross-thread MT5 access
- ❌ WebSocket stalls and timeouts
- ❌ Unstable streaming

### **After Fix**
- ✅ No Binance disconnects
- ✅ Single-thread MT5 access
- ✅ Fast tick processing (< 1ms)
- ✅ Stable streaming under load
- ✅ Maintained price synchronization

## 🔧 **Files Modified**

### **New Files**
- `infra/mt5_proxy_service.py` - MT5 proxy service
- `infra/binance_service_fixed.py` - Fixed Binance service
- `infra/binance_stream_fixed.py` - WebSocket tuning
- `test_binance_fix.py` - Test script

### **Modified Files**
- `chatgpt_bot.py` - Integrate proxy service
- `app/main_api.py` - Route MT5 calls through proxy
- `desktop_agent.py` - Update MT5 access

## 🚨 **Rollback Plan**

If issues occur:
```bash
# Restore original Binance service
python apply_binance_fix_immediate.py restore

# Or manually restore from backup
cp infra/binance_service.py.backup infra/binance_service.py
```

## 📈 **Performance Monitoring**

### **Key Metrics**
- Tick processing time (should be < 1ms)
- MT5 call latency (through proxy)
- WebSocket connection stability
- Price synchronization accuracy

### **Monitoring Commands**
```python
# Get performance stats
binance_service.get_performance_stats()

# Get MT5 proxy stats
mt5_proxy.get_cache_stats()

# Check connection health
binance_service.get_connection_health()
```

## ✅ **Success Criteria**
- [ ] No Binance disconnects during ChatGPT usage
- [ ] Tick processing < 1ms consistently
- [ ] MT5 calls only from main thread
- [ ] Price synchronization maintained
- [ ] System stable under high load
- [ ] WebSocket connections stable

## 🎯 **Next Steps**
1. Apply immediate fix and test
2. Implement full solution if test passes
3. Monitor performance metrics
4. Validate under load
5. Document results
