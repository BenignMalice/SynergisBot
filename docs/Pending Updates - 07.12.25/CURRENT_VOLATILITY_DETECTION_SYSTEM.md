# Current Volatility Detection/Classification System

**Date**: 2025-12-07  
**Purpose**: Document how the system currently detects and classifies volatility regimes

---

## 📊 SYSTEM OVERVIEW

The system uses **two separate volatility classification systems**:

1. **`infra/volatility_regime_detector.py`** - Primary volatility regime detector (STABLE/TRANSITIONAL/VOLATILE)
2. **`app/engine/regime_classifier.py`** - Market regime classifier (TREND/RANGE/VOLATILE)

Both systems are used in different contexts but serve complementary purposes.

---

## 🔍 PRIMARY SYSTEM: Volatility Regime Detector

**File**: `infra/volatility_regime_detector.py`  
**Class**: `RegimeDetector`  
**Enum**: `VolatilityRegime` (STABLE, TRANSITIONAL, VOLATILE)

### Detection Method

**Multi-Timeframe Analysis**:
- **M5**: 20% weight
- **M15**: 30% weight  
- **H1**: 50% weight (highest weight)

**Primary Indicators**:

1. **ATR Ratio** (ATR(14) / ATR(50))
   - **STABLE**: ≤ 1.2
   - **TRANSITIONAL**: 1.2 - 1.4
   - **VOLATILE**: ≥ 1.4

2. **Bollinger Band Width Ratio** (vs 20-day median)
   - **STABLE**: ≤ 1.5x median
   - **TRANSITIONAL**: 1.5 - 1.8x median
   - **VOLATILE**: ≥ 1.8x median

3. **ADX** (Average Directional Index)
   - **Weak Trend**: < 20
   - **Strong Trend**: ≥ 25
   - Used as supporting signal (not primary)

4. **Volume Confirmation**
   - For VOLATILE regime: Requires volume spike ≥ 1.5x average
   - Volume must confirm ATR increase

### Classification Logic

**Signal Counting System**:
- Counts signals for VOLATILE vs STABLE
- **VOLATILE**: Requires ≥2 signals + volume confirmation
- **STABLE**: Requires ≥2 signals
- **TRANSITIONAL**: Default when neither threshold met

**Composite Calculation**:
- Calculates indicators per timeframe (M5, M15, H1)
- Weighted average across timeframes
- Final classification based on composite values

### Filtering Mechanisms

**1. Persistence Filter**:
- Requires **3 consecutive candles** showing same regime
- Prevents false signals from single-candle spikes

**2. Regime Inertia**:
- Minimum **5 candles** a regime must hold before changing
- Prevents rapid flips in choppy markets

**3. Auto-Cooldown**:
- Ignores reversals within **2 candles**
- Prevents whipsaw detection

**4. Volume Confirmation**:
- For VOLATILE: Requires 150% volume spike
- Validates that volatility increase is real (not just price noise)

### Confidence Scoring

**Confidence Calculation** (0-100%):
- ATR ratio strength (0-100)
- BB width strength (0-100)
- ADX strength (0-100)
- Volume confirmation bonus (+10 or 0)
- Multi-timeframe alignment bonus (+10 or 0)

**Threshold**: <70% confidence = WAIT state (Regime Confidence Low)

### Integration Points

**Used in**:
- `desktop_agent.py` → `tool_analyse_symbol_full()`
- Called during analysis pipeline
- Returns regime data in analysis response

**Returns**:
```python
{
    "regime": VolatilityRegime.STABLE/TRANSITIONAL/VOLATILE,
    "confidence": 0-100,
    "atr_ratio": float,
    "bb_width_ratio": float,
    "adx_composite": float,
    "volume_confirmed": bool,
    "indicators": {per timeframe data},
    "reasoning": str
}
```

---

## 🔍 SECONDARY SYSTEM: Market Regime Classifier

**File**: `app/engine/regime_classifier.py`  
**Function**: `classify_regime()`  
**Output**: TREND, RANGE, VOLATILE

### Detection Method

**Multi-Timeframe Analysis**:
- **M5**: 20% weight
- **M15**: 50% weight
- **H1**: 30% weight

**Primary Indicators**:

1. **ADX Blend** (normalized across timeframes)
   - Trend score component (60%)
   - EMA200 alignment (15%)
   - Slope agreement (25%)

2. **Bollinger Band Width**
   - Range score: Low ADX + squeeze
   - Volatile score: Wide bands + mid ADX (20-30)

3. **Timeframe Conflict Detection**
   - Penalizes trend score if timeframes disagree
   - Conflict penalty: -0.3

### Classification Logic

**Score-Based System**:
- **Trend Score**: ADX blend + alignment + slope - conflict penalty
- **Range Score**: Low ADX component (60%) + squeeze component (40%)
- **Volatile Score**: Wide BB (60%) + mid ADX (25%) + disagreement bonus (20%)

**Decision Thresholds**:
- **Confident Gate**: ≥0.48 (48%) → Classify as highest score
- **Below Gate**: Returns "UNKNOWN"

**Hysteresis**:
- Adds +0.05 bonus to previous regime
- Prevents rapid regime flips

**Session Nudges**:
- Configurable adjustments per session
- News proximity boost to volatile score

---

## 📈 CURRENT CAPABILITIES

### ✅ What the System CAN Detect

1. **Basic Volatility States**:
   - STABLE (low ATR, narrow BB)
   - TRANSITIONAL (moderate ATR, moderate BB)
   - VOLATILE (high ATR, wide BB)

2. **Multi-Timeframe Analysis**:
   - Weighted analysis across M5, M15, H1
   - Composite indicators

3. **Filtering**:
   - Persistence (3 candles)
   - Inertia (5 candles minimum hold)
   - Cooldown (2 candles)
   - Volume confirmation

4. **Confidence Scoring**:
   - 0-100% confidence
   - WAIT state when <70%

### ❌ What the System CANNOT Detect (Yet)

1. **PRE_BREAKOUT_TENSION**:
   - ❌ No wick-length variance tracking
   - ❌ No intra-bar volatility measurement
   - ❌ No BB width trend analysis (only current width)

2. **POST_BREAKOUT_DECAY**:
   - ❌ No ATR slope/trend tracking
   - ❌ No "time since breakout" detection
   - ❌ No ATR decline rate measurement

3. **FRAGMENTED/CHOP_VOLATILITY**:
   - ❌ No whipsaw detection
   - ❌ No mean reversion pattern recognition
   - ❌ No directional momentum analysis

4. **SESSION_SWITCH_VOLATILITY_FLARE**:
   - ❌ No session transition detection
   - ❌ No volatility spike during transition windows
   - ❌ No distinction between flare vs genuine expansion

---

## 🔧 DATA SOURCES

### Input Data Required

**Per Timeframe (M5, M15, H1)**:
- `rates`: OHLCV data (numpy array or DataFrame)
- `atr_14`: ATR(14) value (optional - calculated if missing)
- `atr_50`: ATR(50) value (optional - calculated if missing)
- `bb_upper`: Bollinger Band upper
- `bb_lower`: Bollinger Band lower
- `bb_middle`: Bollinger Band middle (SMA)
- `adx`: ADX(14) value
- `volume`: Volume array

### Calculation Methods

**ATR Calculation**:
- True Range = max(high-low, |high-prev_close|, |low-prev_close|)
- ATR = SMA of True Range over period

**BB Width Calculation**:
- BB Width = (upper - lower) / middle
- BB Width Ratio = current width / 20-day median width
- Fallback: Uses 2% as default median if history unavailable

**Volume Confirmation**:
- Current volume / average volume
- Threshold: ≥1.5x for VOLATILE regime

---

## 📊 INTEGRATION WITH ANALYSIS PIPELINE

### Flow in `tool_analyse_symbol_full()`

1. **Fetch Market Data**:
   - Gets OHLCV data for M5, M15, H1
   - Calculates technical indicators

2. **Prepare Timeframe Data**:
   ```python
   timeframe_data_for_regime = {
       "M5": {"rates": ..., "atr_14": ..., "bb_upper": ..., ...},
       "M15": {...},
       "H1": {...}
   }
   ```

3. **Call Regime Detector**:
   ```python
   volatility_regime_data = regime_detector.detect_regime(
       symbol=symbol_normalized,
       timeframe_data=timeframe_data_for_regime,
       current_time=datetime.now()
   )
   ```

4. **Extract Results**:
   - Regime: STABLE/TRANSITIONAL/VOLATILE
   - Confidence: 0-100%
   - ATR ratio, BB width ratio, ADX composite

5. **Check WAIT Reasons**:
   - If confidence < 70% → Add WAIT reason code

6. **Include in Response**:
   - Added to analysis response
   - Used for strategy selection
   - Used for risk management

---

## 🎯 STRATEGY SELECTION INTEGRATION

**Current Usage**:
- VOLATILE regime → Selects volatility-aware strategies
- STABLE regime → Standard strategies
- TRANSITIONAL → Cautious approach

**Strategy Mapping** (from `openai.yaml`):
- VOLATILE → Breakout-Continuation, Volatility Reversion Scalp, Post-News Reaction Trade, Inside Bar Volatility Trap

---

## ⚙️ CONFIGURATION

**File**: `config/volatility_regime_config.py`

**Key Parameters**:
- `ATR_RATIO_STABLE = 1.2`
- `ATR_RATIO_VOLATILE = 1.4`
- `BOLLINGER_WIDTH_MULTIPLIER_STABLE = 1.5`
- `BOLLINGER_WIDTH_MULTIPLIER_VOLATILE = 1.8`
- `PERSISTENCE_REQUIRED = 3`
- `INERTIA_MIN_HOLD = 5`
- `COOLDOWN_WINDOW = 2`
- `VOLUME_SPIKE_THRESHOLD = 1.5`
- `CONFIDENCE_THRESHOLD_WAIT = 70`

---

## 📝 SUMMARY

**Current System Strengths**:
- ✅ Multi-timeframe weighted analysis
- ✅ Multiple filtering mechanisms (persistence, inertia, cooldown)
- ✅ Volume confirmation for volatile regimes
- ✅ Confidence scoring
- ✅ Integration with analysis pipeline

**Current System Limitations**:
- ❌ Only 3 basic states (STABLE/TRANSITIONAL/VOLATILE)
- ❌ No wick analysis
- ❌ No ATR trend tracking
- ❌ No whipsaw detection
- ❌ No session transition awareness
- ❌ No pre-breakout tension detection
- ❌ No post-breakout decay detection

**To Add New Volatility States**:
1. Extend `VolatilityRegime` enum
2. Add detection logic in `_classify_regime()` or new method
3. Add new indicators (wick variance, ATR slope, etc.)
4. Update filtering mechanisms
5. Update strategy selection mappings
6. Update knowledge documents

---

## 🚀 REQUIRED FUNCTIONALITY FOR NEW VOLATILITY STATES

### PRE_BREAKOUT_TENSION Detection Requirements

**Indicators Needed**:
1. **BB Width Trend Tracking**:
   - Calculate BB width over rolling window (10 candles)
   - Determine if width is in bottom 20th percentile (narrow threshold)
   - Track BB width slope (expanding/contracting)
   - Current: Only calculates current BB width ratio vs median

2. **Wick Variance Calculation**:
   - Calculate wick-to-body ratio for each candle
   - Compute rolling variance of wick ratios (10-candle window)
   - Track variance change percentage
   - Current: Only calculates single-candle wick ratios

3. **Intra-Bar Volatility**:
   - Calculate candle range / body ratio
   - Track trend of this ratio over time
   - Detect if ratio is increasing (rising intra-bar volatility)
   - Current: Not calculated

**Detection Logic**:
- BB width < narrow threshold (bottom 20th percentile)
- Wick variance increasing (30%+ increase)
- Intra-bar volatility rising (20%+ increase)
- ATR ratio still low/stable (< 1.2)

**Integration Points**:
- Add to `_calculate_timeframe_indicators()` method
- New method: `_detect_pre_breakout_tension()`
- Update `detect_regime()` to check this state

---

### POST_BREAKOUT_DECAY Detection Requirements

**Indicators Needed**:
1. **ATR Trend Analysis**:
   - Calculate ATR slope (rate of change over 5 candles)
   - Track ATR vs baseline (ATR(50) or historical average)
   - Detect declining ATR trend (negative slope)
   - Current: Only calculates ATR ratio, no slope tracking

2. **Breakout Timing**:
   - Track "time since breakout" (optional - requires breakout detection)
   - Identify post-breakout phase (< 30 minutes since breakout)
   - Current: Not tracked

3. **BB Width Expansion Rate**:
   - Track BB width expansion rate (slowing = decay signal)
   - Current: Only current width, no rate tracking

**Detection Logic**:
- ATR slope declining (negative, -5%+ per period)
- ATR still above baseline (> 1.2x)
- Time since breakout < 30 minutes (if available)
- BB width expanding but rate slowing

**Integration Points**:
- New method: `_calculate_atr_trend()`
- New method: `_detect_post_breakout_decay()`
- Update `detect_regime()` to check this state

---

### FRAGMENTED_CHOP Detection Requirements

**Indicators Needed**:
1. **Whipsaw Detection**:
   - Track direction changes over 5-candle window
   - Count alternating up/down movements
   - Detect 3+ direction changes = whipsaw
   - Current: Not calculated

2. **Mean Reversion Pattern**:
   - Calculate price distance from VWAP/EMA
   - Detect oscillation within 0.5 ATR of mean
   - Current: VWAP/EMA calculated but not used for chop detection

3. **Directional Momentum**:
   - Use ADX < 15 as low momentum indicator
   - Current: ADX calculated but not used for chop detection

4. **Session Context**:
   - Identify lunch hours, dead zones
   - Current: Session detection exists but not used for chop

**Detection Logic**:
- Whipsaw detected (3+ direction changes in 5 candles)
- Price oscillating around VWAP/EMA (within 0.5 ATR)
- Low directional momentum (ADX < 15)
- Session context (lunch hours, dead zones)

**Integration Points**:
- New method: `_detect_whipsaw()`
- New method: `_detect_fragmented_chop()`
- Update `detect_regime()` to check this state

---

### SESSION_SWITCH_FLARE Detection Requirements

**Indicators Needed**:
1. **Session Transition Detection**:
   - Identify transition windows:
     - Asia→London: 07:00-08:00 UTC (±15 minutes)
     - London→NY: 13:00-14:00 UTC (±15 minutes)
     - NY→Asia: 21:00-22:00 UTC (±15 minutes)
   - Current: Session detection exists but no transition window tracking

2. **Volatility Spike Detection**:
   - Compare current volatility to "normal" volatility
   - Detect 1.5x+ spike during transition window
   - Current: Volatility calculated but not compared to baseline during transitions

3. **Flare Duration Tracking**:
   - Track time since transition start
   - Flare should resolve within 30 minutes
   - Distinguish from genuine expansion (flare is temporary)
   - Current: Not tracked

**Detection Logic**:
- In session transition window (±15 minutes)
- Volatility spike during transition (1.5x normal)
- Flare duration < 30 minutes
- Distinguish from genuine expansion (flare is temporary, expansion is sustained)

**Integration Points**:
- New method: `_detect_session_transition()`
- New method: `_detect_session_switch_flare()`
- Update `detect_regime()` to check this state FIRST (highest priority)

---

## 📋 IMPLEMENTATION CHECKLIST

### Phase 1: Core Detection (Priority: CRITICAL)
- [ ] Extend `VolatilityRegime` enum with 4 new states
- [ ] Add configuration parameters to `config/volatility_regime_config.py`
- [ ] Implement `_calculate_bb_width_trend()` method
- [ ] Implement `_calculate_wick_variance()` method
- [ ] Implement `_calculate_intrabar_volatility()` method
- [ ] Implement `_calculate_atr_trend()` method
- [ ] Implement `_detect_whipsaw()` method
- [ ] Implement `_detect_session_transition()` method
- [ ] Implement `_detect_pre_breakout_tension()` method
- [ ] Implement `_detect_post_breakout_decay()` method
- [ ] Implement `_detect_fragmented_chop()` method
- [ ] Implement `_detect_session_switch_flare()` method
- [ ] Update `detect_regime()` to integrate new detection methods

### Phase 2: Strategy Selection (Priority: HIGH)
- [ ] Create `infra/volatility_strategy_mapper.py`
- [ ] Define strategy mappings for each new volatility state
- [ ] Update `tool_analyse_symbol_full()` to use new mappings
- [ ] Add strategy recommendations to analysis response

### Phase 3: Auto-Execution Validation (Priority: CRITICAL)
- [ ] Create/update `handlers/auto_execution_validator.py`
- [ ] Add `validate_volatility_state()` method
- [ ] Integrate validation into plan creation flow
- [ ] Add rejection reasons for each volatility state

### Phase 4: Analysis Tools (Priority: HIGH)
- [ ] Update `tool_analyse_symbol_full()` to return new volatility metrics
- [ ] Add detailed volatility state information to response
- [ ] Include detection metrics (BB width trend, wick variance, etc.)

### Phase 5: Knowledge Documents (Priority: HIGH)
- [ ] Update `AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`
- [ ] Update `AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md`
- [ ] Update `SMC_MASTER_EMBEDDING.md`
- [ ] Update symbol-specific guides (GOLD, FOREX, BTCUSD)

### Phase 6: Risk Management (Priority: MEDIUM)
- [ ] Create/update `infra/volatility_risk_manager.py`
- [ ] Add volatility-aware position sizing
- [ ] Update `infra/universal_sl_tp_manager.py` for volatility-aware SL

### Phase 7: Monitoring (Priority: LOW)
- [ ] Enhance `_log_regime_change()` for new states
- [ ] Add Discord alerts for new volatility states
- [ ] Enhance `get_regime_history()` with detailed metrics

### Phase 8: Testing (Priority: HIGH)
- [ ] Create unit tests for each detection method
- [ ] Create integration tests for end-to-end flow
- [ ] Test strategy mapping logic
- [ ] Test auto-execution validation

---

## 🔗 RELATED DOCUMENTS

- **Implementation Plan**: `docs/Pending Updates - 07.12.25/VOLATILITY_STATES_IMPLEMENTATION_PLAN.md`
- **Current System Review**: This document
- **Knowledge Documents**: `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/`

---

# END_OF_DOCUMENT

