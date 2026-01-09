# Verification Guide: Dynamic Threshold Tuning Implementation

**Purpose:** How to verify that Dynamic Threshold Tuning has been successfully implemented and is working correctly in the auto-execution system.

**Status:** Verification Methods Documented

---

## ✅ Verification Checklist

### 1. Code Verification (Static Checks)

**Check if files exist:**
- [ ] `infra/m1_threshold_calibrator.py` exists (or `infra/m1_threshold_manager.py`)
- [ ] `config/threshold_profiles.json` exists
- [ ] `SymbolThresholdManager` class is defined
- [ ] `compute_threshold()` method exists

**Check initialization:**
- [ ] `DesktopAgent.__init__()` initializes `SymbolThresholdManager`
- [ ] `M1MicrostructureAnalyzer.__init__()` receives `threshold_manager` parameter
- [ ] `AutoExecutionSystem.__init__()` receives `threshold_manager` parameter
- [ ] `M1MicrostructureAnalyzer.analyze_microstructure()` computes dynamic threshold
- [ ] `AutoExecutionSystem._check_m1_conditions()` uses dynamic threshold

**Check integration points:**
- [ ] `M1MicrostructureAnalyzer` stores `dynamic_threshold` in analysis output
- [ ] `M1MicrostructureAnalyzer` stores `threshold_calculation` in analysis output
- [ ] `AutoExecutionSystem._check_m1_conditions()` reads `dynamic_threshold` from M1 data
- [ ] `AutoExecutionSystem._monitor_loop()` refreshes M1 data before checking plans

---

### 2. Runtime Verification (Logging Checks)

**What to look for in logs:**

#### A. Initialization Logs

```
✅ Expected log messages:
- "Initializing SymbolThresholdManager..."
- "Loaded threshold profiles from config/threshold_profiles.json"
- "SymbolThresholdManager initialized with X symbols"
```

#### B. M1 Analysis Logs (Dynamic Threshold Computation)

```
✅ Expected log messages during analysis:
- "Computing dynamic threshold for {symbol}"
- "ATR ratio: {ratio:.2f} (current: {atr}, median: {median})"
- "Session: {session}, Bias: {bias:.2f}"
- "Dynamic threshold: {threshold:.1f} (Base: {base}, ATR: {atr_ratio:.2f}x, Session: {session})"
```

#### C. Auto-Execution Monitoring Logs

```
✅ Expected log messages during plan checks:

SUCCESS CASE:
- "Plan {plan_id} ({symbol}): ✅ Dynamic threshold passed | Confluence {score:.1f} >= Threshold {threshold:.1f} | Adapted to: ATR {ratio:.2f}x, Session {session}"

FAILURE CASE:
- "Plan {plan_id} ({symbol}): Confluence {score:.1f} < Dynamic Threshold {threshold:.1f} | ATR: {ratio:.2f}x | Session: {session} | Base: {base} | Bias: {bias:.2f}"
```

#### D. Threshold Calculation Details

```
✅ Expected log format showing all three adaptations:
- Symbol: {symbol} (asset volatility personality)
- Session: {session} (current market session)
- ATR Ratio: {ratio:.2f} (real-time volatility state)
- Base Confidence: {base} (from symbol profile)
- Session Bias: {bias:.2f} (from session bias matrix)
- Final Threshold: {threshold:.1f} (calculated)
```

---

### 3. Functional Verification (Behavior Checks)

#### A. Test Different Symbols

**Test BTCUSD:**
1. Create a test plan for BTCUSD
2. Check logs for threshold calculation
3. Verify threshold uses BTCUSD profile (base: 75, vol_weight: 0.6, sess_weight: 0.4)
4. Verify threshold differs from other symbols

**Test XAUUSD:**
1. Create a test plan for XAUUSD
2. Check logs for threshold calculation
3. Verify threshold uses XAUUSD profile (base: 70, vol_weight: 0.5, sess_weight: 0.6)
4. Verify threshold differs from BTCUSD

**Test EURUSD:**
1. Create a test plan for EURUSD
2. Check logs for threshold calculation
3. Verify threshold uses EURUSD profile (base: 65, vol_weight: 0.4, sess_weight: 0.7)
4. Verify threshold differs from BTCUSD and XAUUSD

#### B. Test Different Sessions

**Test Asian Session:**
1. Set system time to Asian session hours
2. Create test plans for multiple symbols
3. Verify thresholds are LOWER (more aggressive) for Asian session
4. Check logs show session bias < 1.0 (e.g., 0.85 for XAUUSD, 0.9 for BTCUSD)

**Test NY Overlap Session:**
1. Set system time to NY Overlap hours
2. Create test plans for multiple symbols
3. Verify thresholds are HIGHER (stricter) for Overlap session
4. Check logs show session bias > 1.0 (e.g., 1.1 for BTCUSD, 1.2 for XAUUSD)

**Test Session Transition:**
1. Monitor logs during session transition (e.g., Asian → London)
2. Verify threshold recalculates automatically
3. Verify threshold changes match session bias changes

#### C. Test ATR Ratio Changes

**Test High Volatility (ATR Ratio > 1.2):**
1. Wait for or simulate high volatility period
2. Check logs show ATR ratio > 1.2
3. Verify threshold is HIGHER than normal
4. Verify plans require higher confluence to execute

**Test Low Volatility (ATR Ratio < 0.9):**
1. Wait for or simulate low volatility period
2. Check logs show ATR ratio < 0.9
3. Verify threshold is LOWER than normal
4. Verify plans can execute with lower confluence

**Test ATR Ratio Change:**
1. Monitor logs as volatility changes
2. Verify threshold recalculates automatically
3. Verify threshold changes match ATR ratio changes

---

### 4. Data Verification (Output Checks)

#### A. Check M1 Analysis Output

**Verify `m1_data` contains:**
```python
m1_data = {
    'dynamic_threshold': 83.4,  # ← Must exist
    'threshold_calculation': {   # ← Must exist
        'base_confidence': 70,   # Asset personality
        'atr_ratio': 1.4,        # Real-time volatility
        'session_bias': 1.1,     # Session
        'adjusted_threshold': 83.4
    },
    'microstructure_confluence': {
        'score': 85,  # Compare this to dynamic_threshold
        # ...
    }
}
```

**Verification method:**
```python
# In Python console or test script
m1_data = m1_analyzer.get_microstructure("XAUUSD")
assert 'dynamic_threshold' in m1_data, "Dynamic threshold missing!"
assert 'threshold_calculation' in m1_data, "Threshold calculation missing!"
assert m1_data['threshold_calculation']['atr_ratio'] > 0, "ATR ratio invalid!"
assert m1_data['threshold_calculation']['session_bias'] > 0, "Session bias invalid!"
```

#### B. Check Plan Execution Behavior

**Verify plans are filtered by dynamic threshold:**
1. Create plan with confluence score BELOW dynamic threshold
2. Verify plan does NOT execute (logs show threshold rejection)
3. Create plan with confluence score ABOVE dynamic threshold
4. Verify plan DOES execute (logs show threshold passed)

**Verify threshold changes affect execution:**
1. Create plan that's just below threshold
2. Wait for ATR ratio to decrease (or simulate)
3. Verify threshold decreases
4. Verify plan now executes (if confluence now above threshold)

---

### 5. Monitoring Verification (Real-Time Checks)

#### A. Monitor Logs During Active Trading

**What to watch for:**
- Threshold calculations appear in logs every 30 seconds (monitoring loop)
- Threshold values change as ATR ratio changes
- Threshold values change as session transitions
- Different symbols show different thresholds (even in same session)
- Plans are correctly filtered by dynamic threshold

#### B. Monitor Plan Status

**Check plan database/status:**
- Plans with confluence < dynamic threshold: Status = "pending" (not executing)
- Plans with confluence >= dynamic threshold: Status = "executed" (if other conditions met)
- Plans show threshold calculation in execution logs

#### C. Monitor Performance Metrics

**Track over time:**
- Average threshold per symbol per session
- Threshold distribution (should vary by symbol and session)
- Execution rate vs threshold (should correlate)
- False positive rate (should decrease with dynamic threshold)

---

### 6. Test Script Verification

**Create test script:**
```python
# test_dynamic_threshold.py
import asyncio
from infra.m1_threshold_calibrator import SymbolThresholdManager
from infra.m1_session_volatility_profile import SessionVolatilityProfile
from infra.m1_asset_profiles import AssetProfile

async def test_dynamic_threshold():
    # 1. Initialize components
    asset_profiles = AssetProfile("config/asset_profiles.json")
    session_manager = SessionVolatilityProfile(asset_profiles)
    threshold_manager = SymbolThresholdManager("config/threshold_profiles.json")
    
    # 2. Test BTCUSD in NY Overlap (high volatility)
    threshold_btc_overlap = threshold_manager.compute_threshold(
        symbol="BTCUSD",
        session="NY_Overlap",
        atr_ratio=1.4
    )
    print(f"BTCUSD NY Overlap (ATR 1.4×): Threshold = {threshold_btc_overlap}")
    assert threshold_btc_overlap > 90, f"Expected threshold > 90, got {threshold_btc_overlap}"
    
    # 3. Test XAUUSD in Asian (low volatility)
    threshold_xau_asian = threshold_manager.compute_threshold(
        symbol="XAUUSD",
        session="Asian",
        atr_ratio=0.8
    )
    print(f"XAUUSD Asian (ATR 0.8×): Threshold = {threshold_xau_asian}")
    assert threshold_xau_asian < 70, f"Expected threshold < 70, got {threshold_xau_asian}"
    
    # 4. Test EURUSD in London (normal)
    threshold_eur_london = threshold_manager.compute_threshold(
        symbol="EURUSD",
        session="London",
        atr_ratio=1.0
    )
    print(f"EURUSD London (ATR 1.0×): Threshold = {threshold_eur_london}")
    assert 60 < threshold_eur_london < 70, f"Expected threshold 60-70, got {threshold_eur_london}"
    
    # 5. Test threshold changes with ATR ratio
    threshold_low = threshold_manager.compute_threshold("BTCUSD", "London", 0.8)
    threshold_high = threshold_manager.compute_threshold("BTCUSD", "London", 1.4)
    assert threshold_high > threshold_low, "High volatility should have higher threshold"
    
    print("✅ All dynamic threshold tests passed!")

if __name__ == "__main__":
    asyncio.run(test_dynamic_threshold())
```

**Run test:**
```bash
python test_dynamic_threshold.py
```

**Expected output:**
```
BTCUSD NY Overlap (ATR 1.4×): Threshold = 96.8
XAUUSD Asian (ATR 0.8×): Threshold = 57.3
EURUSD London (ATR 1.0×): Threshold = 65.0
✅ All dynamic threshold tests passed!
```

---

### 7. Integration Test Verification

**Test auto-execution integration:**
```python
# test_auto_execution_dynamic_threshold.py
def test_auto_execution_uses_dynamic_threshold():
    # 1. Create auto-execution system with threshold_manager
    auto_exec = AutoExecutionSystem(
        mt5_service=mt5_service,
        m1_analyzer=m1_analyzer,
        threshold_manager=threshold_manager,
        # ... other components
    )
    
    # 2. Create test plan
    plan = TradePlan(
        plan_id="test_001",
        symbol="XAUUSD",
        status="pending",
        conditions={}
    )
    
    # 3. Get M1 data (should include dynamic threshold)
    m1_data = m1_analyzer.get_microstructure("XAUUSD")
    assert 'dynamic_threshold' in m1_data, "M1 data missing dynamic threshold!"
    
    # 4. Check conditions (should use dynamic threshold)
    result = auto_exec._check_m1_conditions(plan, m1_data)
    
    # 5. Verify threshold was used
    # (Check logs or add assertion)
    print(f"Plan check result: {result}")
    print(f"Dynamic threshold used: {m1_data['dynamic_threshold']}")
    print(f"Confluence score: {m1_data['microstructure_confluence']['score']}")
    
    assert isinstance(result, bool), "Check should return boolean"
```

---

### 8. Visual Verification (Console Output)

**What you should see in console/logs:**

```
[INFO] Computing dynamic threshold for XAUUSD
[INFO] ATR ratio: 0.85 (current: 12.5, median: 14.7)
[INFO] Session: Asian, Bias: 0.85
[INFO] Dynamic threshold: 57.3 (Base: 70, ATR: 0.85x, Session: Asian)

[INFO] Plan test_001 (XAUUSD): ✅ Dynamic threshold passed | Confluence 68.5 >= Threshold 57.3 | Adapted to: ATR 0.85x, Session Asian

[INFO] Computing dynamic threshold for BTCUSD
[INFO] ATR ratio: 1.42 (current: 850, median: 600)
[INFO] Session: NY_Overlap, Bias: 1.1
[INFO] Dynamic threshold: 96.8 (Base: 75, ATR: 1.42x, Session: NY_Overlap)

[DEBUG] Plan test_002 (BTCUSD): Confluence 85.2 < Dynamic Threshold 96.8 | ATR: 1.42x | Session: NY_Overlap | Base: 75 | Bias: 1.10
```

---

### 9. Database/State Verification

**Check plan execution history:**
- Plans that executed should show threshold calculation in logs
- Plans that didn't execute should show threshold rejection reason
- Threshold values should be stored/logged for each plan check

**Check M1 analysis cache:**
- M1 data should include `dynamic_threshold` field
- M1 data should include `threshold_calculation` breakdown
- Threshold should update when M1 data refreshes

---

### 10. Comparison Verification (Before/After)

**Before Dynamic Threshold:**
- All plans use fixed threshold (e.g., 70)
- Same threshold for all symbols
- Same threshold for all sessions
- No ATR ratio consideration

**After Dynamic Threshold:**
- Plans use variable threshold (e.g., 57-97)
- Different threshold per symbol
- Different threshold per session
- Threshold adjusts with ATR ratio

**Verification:**
1. Compare threshold values across symbols (should differ)
2. Compare threshold values across sessions (should differ)
3. Compare threshold values across ATR ratios (should differ)
4. Verify execution behavior changes (fewer false positives, better timing)

---

## 🎯 Quick Verification Checklist

**5-Minute Verification:**

1. **Check logs for threshold calculations:**
   ```bash
   grep -i "dynamic threshold" logs/app.log | tail -20
   ```

2. **Check M1 data output:**
   ```python
   m1_data = m1_analyzer.get_microstructure("XAUUSD")
   print(f"Dynamic Threshold: {m1_data.get('dynamic_threshold')}")
   print(f"Threshold Calc: {m1_data.get('threshold_calculation')}")
   ```

3. **Check plan execution logs:**
   ```bash
   grep -i "threshold passed\|threshold.*failed" logs/app.log | tail -10
   ```

4. **Verify different symbols show different thresholds:**
   ```python
   for symbol in ["BTCUSD", "XAUUSD", "EURUSD"]:
       m1 = m1_analyzer.get_microstructure(symbol)
       print(f"{symbol}: Threshold = {m1.get('dynamic_threshold')}")
   ```

5. **Verify threshold changes with session:**
   - Check logs during different sessions
   - Verify threshold values change
   - Verify session bias is applied

---

## ⚠️ Common Issues to Check

### Issue 1: Threshold Always Same Value
**Symptom:** All symbols show same threshold (e.g., always 70)
**Cause:** SymbolThresholdManager not initialized or not using symbol profiles
**Fix:** Check initialization, verify `config/threshold_profiles.json` is loaded

### Issue 2: Threshold Doesn't Change with Session
**Symptom:** Threshold same in Asian and Overlap sessions
**Cause:** Session bias not applied or session detection not working
**Fix:** Check session detection, verify session_bias matrix is loaded

### Issue 3: Threshold Doesn't Change with ATR Ratio
**Symptom:** Threshold same regardless of volatility
**Cause:** ATR ratio not calculated or not passed to compute_threshold
**Fix:** Check ATR calculation in M1MicrostructureAnalyzer, verify atr_ratio is computed

### Issue 4: Plans Not Using Dynamic Threshold
**Symptom:** Plans execute with fixed threshold, logs don't show dynamic threshold
**Cause:** Auto-execution not reading dynamic_threshold from M1 data
**Fix:** Check `_check_m1_conditions()` method, verify it reads `m1_data.get('dynamic_threshold')`

### Issue 5: Threshold Calculation Errors
**Symptom:** Errors in logs about threshold calculation
**Cause:** Missing symbol profile, invalid ATR ratio, or session not found
**Fix:** Check error messages, verify all symbols have profiles, verify ATR ratio is valid

---

## 📊 Expected Behavior Summary

**When Working Correctly:**

1. **Different symbols = Different thresholds**
   - BTCUSD: ~75-97 (depending on session/ATR)
   - XAUUSD: ~57-85 (depending on session/ATR)
   - EURUSD: ~52-72 (depending on session/ATR)

2. **Different sessions = Different thresholds**
   - Asian: Lower thresholds (more aggressive)
   - Overlap: Higher thresholds (stricter)
   - London/NY: Normal thresholds

3. **Different ATR ratios = Different thresholds**
   - ATR 0.8×: Lower threshold
   - ATR 1.0×: Normal threshold
   - ATR 1.4×: Higher threshold

4. **Real-time updates**
   - Threshold recalculates every 30 seconds
   - Threshold changes as ATR ratio changes
   - Threshold changes as session transitions

5. **Logging shows all three adaptations**
   - Asset personality (base_confidence from symbol profile)
   - Session (session_bias from session bias matrix)
   - ATR ratio (real-time volatility state)

---

## 🔍 Debugging Commands

**Check if threshold_manager is initialized:**
```python
# In Python console
from desktop_agent import DesktopAgent
agent = DesktopAgent()
print(f"Threshold Manager: {agent.threshold_manager}")
print(f"Has threshold_manager: {hasattr(agent, 'threshold_manager')}")
```

**Check if M1 analyzer computes threshold:**
```python
m1_data = agent.m1_analyzer.get_microstructure("XAUUSD")
print(f"Has dynamic_threshold: {'dynamic_threshold' in m1_data}")
print(f"Dynamic threshold: {m1_data.get('dynamic_threshold')}")
```

**Check if auto-execution uses threshold:**
```python
# Check auto-execution has threshold_manager
print(f"Auto-execution has threshold_manager: {hasattr(agent.auto_execution, 'threshold_manager')}")

# Check a plan's threshold check
plan = agent.auto_execution.plans.get("some_plan_id")
if plan:
    m1_data = agent.m1_analyzer.get_microstructure(plan.symbol)
    result = agent.auto_execution._check_m1_conditions(plan, m1_data)
    print(f"Check result: {result}")
    print(f"Threshold used: {m1_data.get('dynamic_threshold')}")
```

---

**See:** `docs/Pending Updates - 19.11.25/M1_MICROSTRUCTURE_INTEGRATION_PLAN.md` for complete implementation details.

