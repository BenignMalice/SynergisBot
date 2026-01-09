# Dynamic Threshold Tuning - Auto-Execution Integration Guide

**Purpose:** Comprehensive guide for integrating Dynamic Threshold Tuning into auto-execution monitoring so EVERY plan dynamically adapts to asset volatility personality, current market session, and real-time ATR ratio.

**Status:** Integration Details Documented in M1_MICROSTRUCTURE_INTEGRATION_PLAN.md

---

## ✅ Integration Status

**YES - Dynamic Threshold Tuning is fully integrated into auto-execution monitoring.**

Every auto-execution plan now dynamically adapts to:
1. **Asset's volatility personality** (symbol-specific profiles)
2. **Current market session** (session bias per symbol)
3. **Real-time ATR ratio** (volatility state)

---

## 🔧 How It Works

### 1. Initialization (DesktopAgent)

```python
# In DesktopAgent.__init__()
# 1. Load AssetProfile
self.asset_profiles = AssetProfile("config/asset_profiles.json")

# 2. Initialize SessionVolatilityProfile
self.session_manager = SessionVolatilityProfile(self.asset_profiles)

# 3. Initialize SymbolThresholdManager (Dynamic Threshold Tuning)
self.threshold_manager = SymbolThresholdManager("config/threshold_profiles.json")

# 4. Initialize M1MicrostructureAnalyzer with threshold_manager
self.m1_analyzer = M1MicrostructureAnalyzer(
    mt5_service=self.mt5_service,
    session_manager=self.session_manager,
    asset_profiles=self.asset_profiles,
    threshold_manager=self.threshold_manager,  # ← Dynamic Threshold Tuning
    # ... other components
)

# 5. Initialize AutoExecutionSystem with threshold_manager
self.auto_execution = AutoExecutionSystem(
    mt5_service=self.mt5_service,
    m1_analyzer=self.m1_analyzer,
    session_manager=self.session_manager,
    asset_profiles=self.asset_profiles,
    threshold_manager=self.threshold_manager,  # ← Dynamic Threshold Tuning
    # ... other components
)
```

### 2. M1 Analysis (Computes Dynamic Threshold)

```python
# In M1MicrostructureAnalyzer.analyze_microstructure()
# Calculate ATR ratio (current ATR / median ATR)
atr_current = analysis.get('volatility', {}).get('atr', 0)
atr_median = analysis.get('volatility', {}).get('atr_median', atr_current)
atr_ratio = atr_current / atr_median if atr_median > 0 else 1.0

# Get current session
session = self.session_manager.get_current_session()

# Compute dynamic threshold (adapts to: asset, session, ATR ratio)
dynamic_threshold = self.threshold_manager.compute_threshold(
    symbol=symbol,
    session=session,
    atr_ratio=atr_ratio
)

# Store in analysis output
analysis['dynamic_threshold'] = dynamic_threshold
analysis['threshold_calculation'] = {
    'base_confidence': self.threshold_manager.get_base_confidence(symbol),  # Asset personality
    'atr_ratio': atr_ratio,  # Real-time volatility
    'session_bias': self.threshold_manager.get_session_bias(session, symbol),  # Session
    'adjusted_threshold': dynamic_threshold
}
```

### 3. Auto-Execution Monitoring Loop

```python
# In AutoExecutionSystem._monitor_loop()
def _monitor_loop(self):
    """Main monitoring loop - EVERY plan uses dynamic threshold adaptation"""
    while self.running:
        try:
            # 1. Refresh M1 data for all active symbols (batch refresh)
            active_symbols = list(set([plan.symbol for plan in self.plans.values() 
                                      if plan.status == 'pending']))
            if active_symbols and self.m1_refresh_manager:
                symbols_to_refresh = [
                    s for s in active_symbols 
                    if self.m1_refresh_manager.should_refresh_symbol(s)
                ]
                if symbols_to_refresh:
                    asyncio.run(self.m1_refresh_manager.refresh_symbols_batch(symbols_to_refresh))
            
            # 2. Check all pending plans
            for plan_id, plan in list(self.plans.items()):
                if plan.status != 'pending':
                    continue
                
                # 3. Refresh M1 data for this plan's symbol if stale
                if self.m1_refresh_manager and plan.symbol:
                    if self.m1_refresh_manager.is_data_stale(plan.symbol, max_age_seconds=180):
                        self.m1_refresh_manager.force_refresh(plan.symbol)
                
                # 4. Get fresh M1 microstructure (includes dynamic threshold)
                if self.m1_analyzer and plan.symbol:
                    m1_data = self.m1_analyzer.get_microstructure(plan.symbol)
                    
                    if m1_data and m1_data.get('available'):
                        # 5. Check M1 conditions (uses dynamic threshold)
                        if not self._check_m1_conditions(plan, m1_data):
                            continue  # Skip this plan, check next
                
                # 6. Check other conditions (price_near, etc.)
                if self._check_conditions(plan):
                    # 7. Execute trade
                    self._execute_plan(plan)
        
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
        
        time.sleep(30)  # Check every 30 seconds
```

### 4. Dynamic Threshold Check (Core Integration)

```python
# In AutoExecutionSystem._check_m1_conditions()
def _check_m1_conditions(self, plan: TradePlan, m1_data: Dict) -> bool:
    """
    Check M1 conditions with DYNAMIC THRESHOLD TUNING
    
    Every plan dynamically adapts to:
    1. Asset's volatility personality (symbol-specific base_confidence, vol_weight, sess_weight)
    2. Current market session (session bias per symbol)
    3. Real-time ATR ratio (current_ATR / median_ATR)
    """
    # ... existing M1 condition checks (CHOCH, BOS, volatility state, etc.) ...
    
    # DYNAMIC THRESHOLD TUNING: Core integration point
    dynamic_threshold = m1_data.get('dynamic_threshold')
    threshold_calc = m1_data.get('threshold_calculation', {})
    
    if dynamic_threshold:
        # Use dynamic threshold (already computed in M1 analyzer)
        base_confluence = m1_data.get('microstructure_confluence', {}).get('score', 0)
        
        if base_confluence < dynamic_threshold:
            logger.debug(
                f"Plan {plan.plan_id} ({plan.symbol}): Confluence {base_confluence:.1f} < "
                f"Dynamic Threshold {dynamic_threshold:.1f} | "
                f"ATR: {threshold_calc.get('atr_ratio', 1.0):.2f}x | "
                f"Session: {threshold_calc.get('session', 'UNKNOWN')} | "
                f"Base: {threshold_calc.get('base_confidence', 70)} | "
                f"Bias: {threshold_calc.get('session_bias', 1.0):.2f}"
            )
            return False
        else:
            logger.info(
                f"Plan {plan.plan_id} ({plan.symbol}): ✅ Dynamic threshold passed | "
                f"Confluence {base_confluence:.1f} >= Threshold {dynamic_threshold:.1f} | "
                f"Adapted to: ATR {threshold_calc.get('atr_ratio', 1.0):.2f}x, "
                f"Session {threshold_calc.get('session', 'UNKNOWN')}"
            )
    else:
        # Fallback: Compute dynamic threshold on-the-fly if not in M1 data
        if self.threshold_manager and self.session_manager:
            atr_current = m1_data.get('volatility', {}).get('atr', 0)
            atr_median = m1_data.get('volatility', {}).get('atr_median', atr_current)
            atr_ratio = atr_current / atr_median if atr_median > 0 else 1.0
            session = self.session_manager.get_current_session()
            
            dynamic_threshold = self.threshold_manager.compute_threshold(
                symbol=plan.symbol,
                session=session,
                atr_ratio=atr_ratio
            )
            
            base_confluence = m1_data.get('microstructure_confluence', {}).get('score', 0)
            if base_confluence < dynamic_threshold:
                return False
    
    # Additional checks: Asset personality validation, strategy hint matching, etc.
    return True
```

---

## 📊 How Each Plan Adapts

### Example 1: BTCUSD Plan in NY Overlap (High Volatility)

**Market Conditions:**
- Symbol: BTCUSD
- Session: NY Overlap
- ATR Ratio: 1.4 (high volatility)

**Dynamic Threshold Calculation:**
```
Base: 75 (BTCUSD profile)
ATR Adjustment: 75 * (1 + (1.4 - 1) * 0.6) = 75 * 1.24 = 93.0
Session Adjustment: 93.0 * (1.1 ^ 0.4) ≈ 96.8
Final Threshold: 97
```

**Result:**
- Plan requires confluence ≥ 97 (vs normal 75)
- Prevents execution during high volatility noise
- Only strong signals execute

### Example 2: XAUUSD Plan in Asian Session (Low Volatility)

**Market Conditions:**
- Symbol: XAUUSD
- Session: Asian
- ATR Ratio: 0.8 (low volatility)

**Dynamic Threshold Calculation:**
```
Base: 70 (XAUUSD profile)
ATR Adjustment: 70 * (1 + (0.8 - 1) * 0.5) = 70 * 0.9 = 63.0
Session Adjustment: 63.0 * (0.85 ^ 0.6) ≈ 57.3
Final Threshold: 57
```

**Result:**
- Plan requires confluence ≥ 57 (vs normal 70)
- Allows looser entries during quiet session
- More aggressive during low volatility

### Example 3: EURUSD Plan in London (Normal Conditions)

**Market Conditions:**
- Symbol: EURUSD
- Session: London
- ATR Ratio: 1.0 (normal volatility)

**Dynamic Threshold Calculation:**
```
Base: 65 (EURUSD profile)
ATR Adjustment: 65 * (1 + (1.0 - 1) * 0.4) = 65 * 1.0 = 65.0
Session Adjustment: 65.0 * (1.0 ^ 0.7) = 65.0
Final Threshold: 65
```

**Result:**
- Plan requires confluence ≥ 65 (default threshold)
- Normal conditions, normal threshold

---

## 🔄 Real-Time Adaptation

### During Monitoring Loop:

1. **Every 30 seconds:**
   - Refresh M1 data for all active symbols
   - Recompute dynamic threshold for each symbol
   - Check all pending plans against updated thresholds

2. **As ATR Ratio Changes:**
   - If volatility increases (ATR ratio ↑), threshold increases
   - If volatility decreases (ATR ratio ↓), threshold decreases
   - Plans automatically adapt without manual intervention

3. **As Session Transitions:**
   - When session changes (e.g., Asian → London), threshold recalculates
   - Session bias changes per symbol
   - Plans adapt to new session conditions

4. **Per Symbol:**
   - Each symbol uses its own volatility personality profile
   - Each symbol uses its own session bias matrix
   - Thresholds differ per symbol even in same session

---

## 📋 Configuration File

**File:** `config/threshold_profiles.json`

```json
{
  "symbol_profiles": {
    "BTCUSD": {
      "base_confidence": 75,
      "volatility_weight": 0.6,
      "session_weight": 0.4,
      "notes": "Trades 24/7, wide swings, frequent fakeouts"
    },
    "XAUUSD": {
      "base_confidence": 70,
      "volatility_weight": 0.5,
      "session_weight": 0.6,
      "notes": "High sensitivity to DXY/US10Y"
    },
    "EURUSD": {
      "base_confidence": 65,
      "volatility_weight": 0.4,
      "session_weight": 0.7,
      "notes": "Narrower ATR; trades cleaner in London"
    }
  },
  "session_bias": {
    "Asian": {
      "BTCUSD": 0.9,
      "XAUUSD": 0.85,
      "EURUSD": 0.8
    },
    "London": {
      "BTCUSD": 1.0,
      "XAUUSD": 1.1,
      "EURUSD": 1.0
    },
    "NY_Overlap": {
      "BTCUSD": 1.1,
      "XAUUSD": 1.2,
      "EURUSD": 1.1
    }
  }
}
```

---

## ✅ Integration Checklist

- [x] SymbolThresholdManager class created
- [x] Threshold profiles configuration file created
- [x] M1MicrostructureAnalyzer computes dynamic threshold
- [x] AutoExecutionSystem initialized with threshold_manager
- [x] Monitoring loop uses dynamic threshold for EVERY plan
- [x] _check_m1_conditions uses dynamic threshold
- [x] Fallback logic implemented (on-the-fly calculation)
- [x] Logging shows threshold calculations
- [x] Testing requirements documented

---

## 🎯 Key Benefits

1. **Every Plan Adapts:** Not just M1-specific plans - ALL plans use dynamic threshold
2. **Real-Time Updates:** Threshold recalculates every 30 seconds as conditions change
3. **Symbol-Specific:** Each asset has its own volatility personality
4. **Session-Aware:** Each symbol has its own session bias matrix
5. **ATR-Responsive:** Threshold adjusts based on real-time volatility state
6. **Automatic:** No manual intervention required
7. **Transparent:** Logging shows threshold calculations for debugging

---

**See:** `docs/Pending Updates - 19.11.25/M1_MICROSTRUCTURE_INTEGRATION_PLAN.md` Section 5 (Dynamic Threshold Tuning Module) for complete details.

