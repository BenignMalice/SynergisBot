# Manual Testing Guide - Volume Confirmation Implementation

**Date**: 2025-12-11  
**Status**: Ready for Testing

---

## Prerequisites Checklist

Before starting manual testing, verify:

- [ ] MT5 connection is active and working
- [ ] Auto-execution system is running (check `http://localhost:8000/auto-execution/view`)
- [ ] Monitoring status shows "Active" with pending plans count
- [ ] Test symbols available in MT5: BTCUSDc, XAUUSDc
- [ ] Binance API accessible (for BTCUSD volume confirmation)
- [ ] ChatGPT has access to updated knowledge documents

---

## Test 1: Volume Above Condition (Basic)

**Objective**: Verify `volume_above` condition works correctly

**Steps**:
1. Open ChatGPT interface
2. Ask ChatGPT to create an auto-execution plan:
   ```
   "Create a BUY plan for BTCUSDc at entry 100000, SL 99900, TP 100200. 
   Add volume_above condition: 1000. Use M5 timeframe."
   ```
3. Verify plan created:
   - Check `http://localhost:8000/auto-execution/view`
   - Plan should appear in pending list
   - Conditions column should show `volume_above: 1000`
4. Monitor execution:
   - Wait for current volume to exceed 1000
   - Plan should execute when volume condition met AND price condition met
   - If volume < 1000, plan should NOT execute (even if price matches)

**Expected Result**: ✅ Plan executes only when volume > 1000 AND price conditions met

**Verification**:
- [ ] Plan created successfully
- [ ] Plan appears in pending list
- [ ] Conditions displayed correctly
- [ ] Plan executes when volume > 1000
- [ ] Plan does NOT execute when volume < 1000

---

## Test 2: Volume Ratio Condition

**Objective**: Verify `volume_ratio` condition works correctly

**Steps**:
1. Ask ChatGPT:
   ```
   "Create a SELL plan for XAUUSDc at entry 4200, SL 4210, TP 4190. 
   Add volume_ratio condition: 1.5. Use M15 timeframe."
   ```
2. Verify plan created with `volume_ratio: 1.5`
3. Monitor execution:
   - System calculates average volume over last 4 M15 candles (1 hour)
   - Plan should execute when current volume >= 1.5 × average
   - Check logs for volume ratio calculations

**Expected Result**: ✅ Plan executes when volume is 1.5× average or higher

**Verification**:
- [ ] Plan created with volume_ratio condition
- [ ] Plan monitors correctly
- [ ] Plan executes when ratio met
- [ ] Plan does NOT execute when ratio not met

---

## Test 3: Volume Spike Condition

**Objective**: Verify `volume_spike` condition detects Z-score > 2.0

**Steps**:
1. Ask ChatGPT:
   ```
   "Create a BUY plan for BTCUSDc at entry 100000, SL 99900, TP 100200. 
   Add volume_spike condition. Use M5 timeframe."
   ```
2. Verify plan created with `volume_spike: true`
3. Monitor execution:
   - System calculates Z-score (current volume vs 20-candle average)
   - Plan should execute when |Z-score| > 2.0
   - Check logs for Z-score calculations

**Expected Result**: ✅ Plan executes on significant volume spike (Z-score > 2.0)

**Verification**:
- [ ] Plan created with volume_spike condition
- [ ] Plan monitors correctly
- [ ] Plan executes on spike
- [ ] Plan does NOT execute without spike

---

## Test 4: Volume Confirmation - BTCUSD (Binance Buy/Sell Volume)

**Objective**: Verify BTCUSD uses Binance buy/sell volume separation

**Steps**:
1. **BUY Plan Test**:
   - Ask ChatGPT:
     ```
     "Create a BUY plan for BTCUSDc at entry 100000, SL 99900, TP 100200. 
     Add volume_confirmation condition."
     ```
   - Verify plan created with `volume_confirmation: true`
   - Monitor execution:
     - System should check Binance buy_volume vs sell_volume
     - Plan should execute when buy_volume > sell_volume
     - Check logs for Binance API calls and cache hits

2. **SELL Plan Test**:
   - Ask ChatGPT:
     ```
     "Create a SELL plan for BTCUSDc at entry 100000, SL 100100, TP 99900. 
     Add volume_confirmation condition."
     ```
   - Monitor execution:
     - Plan should execute when sell_volume > buy_volume

**Expected Result**: ✅ BTCUSD plans use Binance buy/sell volume, not volume spike

**Verification**:
- [ ] BUY plan created
- [ ] BUY plan executes when buy_volume > sell_volume
- [ ] SELL plan created
- [ ] SELL plan executes when sell_volume > buy_volume
- [ ] Binance cache working (check logs for cache hits)

---

## Test 5: Volume Confirmation - Non-BTCUSD (Volume Spike)

**Objective**: Verify non-BTCUSD symbols use volume spike

**Steps**:
1. Ask ChatGPT:
   ```
   "Create a BUY plan for XAUUSDc at entry 4200, SL 4190, TP 4210. 
   Add volume_confirmation condition. Use M5 timeframe."
   ```
2. Verify plan created with `volume_confirmation: true`
3. Monitor execution:
   - System should use volume spike (Z-score > 2.0)
   - Should NOT call Binance API
   - Plan executes on volume spike

**Expected Result**: ✅ Non-BTCUSD uses volume spike, not Binance data

**Verification**:
- [ ] Plan created
- [ ] Plan uses volume spike (not Binance)
- [ ] Plan executes on spike
- [ ] No Binance API calls in logs

---

## Test 6: Volume-Only Plan (Fail-Closed)

**Objective**: Verify volume-only plans fail closed when data unavailable

**Steps**:
1. Create a plan with ONLY volume condition (no price conditions):
   ```
   "Create a BUY plan for BTCUSDc at entry 100000, SL 99900, TP 100200. 
   Add ONLY volume_confirmation condition (no price_near or other conditions)."
   ```
   **Note**: ChatGPT validation should prevent this, but if it doesn't:
2. Simulate volume data unavailable:
   - Temporarily disconnect MT5 (or use invalid symbol)
   - Or wait for volume calculation to fail
3. Verify behavior:
   - Plan should NOT execute
   - Error should be logged: "Volume-only plan cannot proceed without volume data"
   - Plan status should remain "pending"

**Expected Result**: ✅ Volume-only plan fails closed (blocks execution)

**Verification**:
- [ ] Plan created (or validation prevents it)
- [ ] If created, plan does NOT execute without volume data
- [ ] Error logged correctly
- [ ] Fail-closed behavior confirmed

---

## Test 7: Hybrid Plan (Fail-Open)

**Objective**: Verify hybrid plans fail open when volume data unavailable

**Steps**:
1. Create a plan with multiple conditions:
   ```
   "Create a BUY plan for BTCUSDc at entry 100000, SL 99900, TP 100200. 
   Add price_near: 100000, tolerance: 100, choch_bull: true, volume_confirmation: true."
   ```
2. Verify plan has both volume AND other conditions
3. Simulate volume data unavailable:
   - Temporarily disconnect MT5
   - Or wait for volume calculation to fail
4. Verify behavior:
   - Plan should continue checking OTHER conditions (price, CHOCH)
   - If other conditions met, plan should execute (even without volume)
   - Warning should be logged: "Volume check failed for hybrid plan, continuing with other conditions"

**Expected Result**: ✅ Hybrid plan fails open (continues with other conditions)

**Verification**:
- [ ] Plan created with multiple conditions
- [ ] Plan continues checking other conditions when volume unavailable
- [ ] Plan executes if other conditions met
- [ ] Warning logged correctly
- [ ] Fail-open behavior confirmed

---

## Test 8: Multiple Volume Conditions

**Objective**: Verify all volume conditions must pass when multiple specified

**Steps**:
1. Create a plan with multiple volume conditions:
   ```
   "Create a BUY plan for BTCUSDc at entry 100000, SL 99900, TP 100200. 
   Add volume_above: 1000, volume_ratio: 1.5, volume_spike: true."
   ```
2. Verify ChatGPT warns about multiple conditions
3. Monitor execution:
   - ALL three conditions must pass:
     - volume_current > 1000
     - volume_current >= 1.5 × volume_avg
     - |Z-score| > 2.0
   - Plan should execute only when ALL conditions met
   - If only 2/3 conditions met, plan should NOT execute

**Expected Result**: ✅ All volume conditions must pass for execution

**Verification**:
- [ ] Plan created with multiple volume conditions
- [ ] ChatGPT warning logged (if applicable)
- [ ] Plan executes only when ALL conditions met
- [ ] Plan does NOT execute when any condition fails

---

## Test 9: Cache Performance

**Objective**: Verify caching reduces redundant MT5 calls

**Steps**:
1. Create 5 plans checking same symbol/timeframe:
   ```
   "Create 5 BUY plans for BTCUSDc M5, all with volume_above: 1000, 
   different entry prices (100000, 100010, 100020, 100030, 100040)."
   ```
2. Monitor logs for MT5 calls:
   - First plan: Should fetch candles (cache miss)
   - Subsequent plans: Should use cache (cache hit)
   - After 30 seconds: Cache expires, new fetch
3. Check cache statistics:
   - Look for "Volume cache hit" messages in logs
   - Verify only 1 MT5 call per 30 seconds for same symbol/timeframe

**Expected Result**: ✅ Cache reduces redundant fetches by ~80%

**Verification**:
- [ ] 5 plans created
- [ ] Cache hits logged for plans 2-5
- [ ] Only 1 MT5 call per 30 seconds
- [ ] Cache expires after 30 seconds

---

## Test 10: Binance Cache Performance

**Objective**: Verify Binance cache reduces API rate limiting

**Steps**:
1. Create 3 BTCUSD plans with volume_confirmation:
   ```
   "Create 3 BUY plans for BTCUSDc with volume_confirmation: true, 
   different entry prices."
   ```
2. Monitor logs for Binance API calls:
   - First plan: Should call Binance API (cache miss)
   - Plans 2-3: Should use cache (cache hit)
   - After 10 seconds: Cache expires, new call
3. Check for cache hit messages:
   - Look for "Binance pressure cache hit" in logs
   - Verify only 1 Binance call per 10 seconds

**Expected Result**: ✅ Binance cache reduces API calls by ~66%

**Verification**:
- [ ] 3 plans created
- [ ] Cache hits logged for plans 2-3
- [ ] Only 1 Binance call per 10 seconds
- [ ] Cache expires after 10 seconds

---

## Test 11: Timeframe Validation

**Objective**: Verify invalid timeframes default to M5

**Steps**:
1. Try to create plan with invalid timeframe:
   ```
   "Create a BUY plan for BTCUSDc with volume_above: 1000, timeframe: M3."
   ```
   **Note**: ChatGPT may prevent this, but if it doesn't:
2. Check system behavior:
   - System should default to M5
   - Warning should be logged: "Unsupported timeframe 'M3' for volume check, defaulting to M5"
   - Plan should use M5 volume calculations

**Expected Result**: ✅ Invalid timeframes default to M5 with warning

**Verification**:
- [ ] Plan created (or validation prevents invalid timeframe)
- [ ] If invalid timeframe used, system defaults to M5
- [ ] Warning logged
- [ ] Plan uses M5 calculations

---

## Test 12: Type Validation

**Objective**: Verify validation rejects invalid types

**Steps**:
1. Try to create plan with invalid volume_above:
   ```
   "Create a BUY plan for BTCUSDc with volume_above: 'invalid' (string)."
   ```
2. Verify ChatGPT validation:
   - Should reject with error: "volume_above must be a non-negative number"
   - Plan should NOT be created

3. Try to create plan with negative volume_ratio:
   ```
   "Create a BUY plan for BTCUSDc with volume_ratio: -1."
   ```
4. Verify ChatGPT validation:
   - Should reject with error: "volume_ratio must be a positive number"
   - Plan should NOT be created

**Expected Result**: ✅ Validation prevents invalid types/values

**Verification**:
- [ ] Invalid string rejected
- [ ] Negative value rejected
- [ ] Error messages clear
- [ ] Plans not created with invalid values

---

## Test 13: Integration with Other Conditions

**Objective**: Verify volume conditions work with other conditions

**Steps**:
1. Create plan with multiple condition types:
   ```
   "Create a BUY plan for BTCUSDc at entry 100000, SL 99900, TP 100200. 
   Add price_near: 100000, tolerance: 100, choch_bull: true, 
   volume_confirmation: true, bb_expansion: true."
   ```
2. Verify all conditions checked:
   - Price condition (price_near)
   - Structure condition (choch_bull)
   - Volume condition (volume_confirmation)
   - Volatility condition (bb_expansion)
3. Monitor execution:
   - Plan should execute only when ALL conditions met
   - If any condition fails, plan should NOT execute

**Expected Result**: ✅ All conditions must pass for execution

**Verification**:
- [ ] Plan created with multiple condition types
- [ ] All conditions displayed correctly
- [ ] Plan executes only when ALL conditions met
- [ ] Plan does NOT execute when any condition fails

---

## Test 14: Error Recovery

**Objective**: Verify graceful error handling and recovery

**Steps**:
1. Create plan with volume condition
2. Disconnect MT5 temporarily:
   - Stop MT5 or disconnect network
   - Wait for condition check cycle
3. Verify error handling:
   - System should log error gracefully
   - Plan should remain in pending state
   - No crashes or exceptions
4. Reconnect MT5:
   - Restore MT5 connection
   - Wait for next check cycle
5. Verify recovery:
   - System should resume monitoring
   - Plan should continue checking conditions

**Expected Result**: ✅ System handles errors gracefully and recovers

**Verification**:
- [ ] Plan created
- [ ] Error handled gracefully (no crash)
- [ ] Plan remains pending
- [ ] System recovers after reconnection
- [ ] Monitoring resumes

---

## Test 15: ChatGPT Plan Creation

**Objective**: Verify ChatGPT creates valid plans with volume conditions

**Steps**:
1. Ask ChatGPT to analyze and create plan:
   ```
   "Analyze BTCUSDc and create a BUY plan with volume confirmation 
   if conditions are good. Entry around 100000, use proper SL/TP."
   ```
2. Verify ChatGPT behavior:
   - Should call `moneybot.analyse_symbol_full` first
   - Should create plan with appropriate volume conditions
   - Should include price conditions (price_near)
   - Should use correct timeframe
3. Verify plan in database:
   - Check `http://localhost:8000/auto-execution/view`
   - Plan should appear with all conditions
   - Conditions should be displayed correctly

**Expected Result**: ✅ ChatGPT creates valid, monitorable plans

**Verification**:
- [ ] ChatGPT analyzes symbol first
- [ ] Plan created with volume conditions
- [ ] Plan includes price conditions
- [ ] Plan saved to database
- [ ] Plan appears in web UI
- [ ] Conditions displayed correctly

---

## Testing Checklist Summary

**Quick Verification**:
- [ ] All 15 test cases executed
- [ ] All expected results confirmed
- [ ] No crashes or exceptions
- [ ] Logs show correct behavior
- [ ] Web UI displays plans correctly
- [ ] ChatGPT creates valid plans

**Issues Found**:
- [ ] List any bugs or unexpected behavior here
- [ ] Note any performance issues
- [ ] Document any edge cases discovered

---

## Next Steps After Testing

1. **If All Tests Pass**: ✅ Feature ready for production
2. **If Issues Found**: 
   - Document issues in plan
   - Fix bugs
   - Re-test affected cases
3. **Performance Monitoring**:
   - Monitor cache hit rates
   - Monitor API call frequency
   - Check system resource usage

---

**END OF MANUAL TESTING GUIDE**

