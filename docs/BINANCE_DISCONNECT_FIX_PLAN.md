# Binance Disconnect Fix Plan

## 🎯 **Problem Summary**
Binance WebSocket feeds disconnect when ChatGPT is used due to cross-thread MT5 API access causing event loop stalls.

## 🔍 **Root Cause Analysis**
- **Binance runs in separate thread** with its own event loop
- **MT5 API is not thread-safe** and should only be called from main thread
- **Binance tick callback** calls MT5 directly (`get_quote()`) causing cross-thread access
- **ChatGPT requests** increase MT5 load on main thread, creating contention
- **WebSocket stalls** → ping timeout → disconnect

## 🚀 **Solution Strategy**

### **Phase 1: Immediate Mitigation (Quick Fix)**
1. **Disable MT5 calls in Binance callback** - Remove `get_quote()` from `_on_tick()`
2. **Add timing logs** - Monitor `_on_tick()` execution time
3. **Test disconnects stop** - Verify ChatGPT no longer causes disconnects

### **Phase 2: Proper Architecture Fix**
1. **Create MT5 Proxy Service** - Single-thread executor for all MT5 calls
2. **Implement Quote Cache** - Thread-safe cache updated by main thread
3. **Add Periodic Calibration** - Offset updates on main thread timer
4. **Tune WebSocket Parameters** - More forgiving ping/timeout settings

### **Phase 3: Monitoring & Validation**
1. **Add Health Monitoring** - Track connection stability and performance
2. **Load Testing** - Simulate high ChatGPT usage with Binance streaming
3. **Performance Metrics** - Monitor tick processing times and MT5 call latency

## 📋 **Implementation Plan**

### **Step 1: Create MT5 Proxy Service**
- Create `MT5ProxyService` class with single-thread executor
- Route all MT5 calls through proxy
- Maintain thread-safe interface for other components

### **Step 2: Implement Quote Cache**
- Create `MT5QuoteCache` with thread-safe read/write
- Update cache on main thread timer (250-500ms)
- Provide latest quotes to Binance thread without MT5 calls

### **Step 3: Decouple Binance from MT5**
- Remove direct MT5 calls from `_on_tick()` callback
- Use quote cache for price data
- Keep Binance thread lightweight and non-blocking

### **Step 4: Add Periodic Calibration**
- Create periodic task on main thread
- Read Binance prices from cache
- Update offset/sync manager
- Maintain price synchronization without blocking Binance

### **Step 5: WebSocket Resilience**
- Configure explicit ping intervals and timeouts
- Add connection health monitoring
- Improve reconnection logic

## 🎯 **Expected Results**
- **No more disconnects** when using ChatGPT
- **Binance thread remains fast** (sub-millisecond tick processing)
- **MT5 calls serialized** on main thread only
- **Maintained price synchronization** through periodic calibration
- **Improved system stability** under high load

## 🔧 **Files to Modify**
- `infra/binance_service.py` - Remove MT5 calls from callback
- `infra/mt5_service.py` - Add proxy service
- `infra/mt5_proxy_service.py` - New proxy service
- `infra/mt5_quote_cache.py` - New quote cache
- `chatgpt_bot.py` - Update Binance service initialization
- `app/main_api.py` - Route MT5 calls through proxy

## 📊 **Success Criteria**
- ✅ No Binance disconnects during ChatGPT usage
- ✅ Binance tick processing < 1ms
- ✅ MT5 calls only from main thread
- ✅ Price synchronization maintained
- ✅ System stable under load
