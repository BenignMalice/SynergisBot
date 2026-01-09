# Phase 4 — Edge Multipliers (Deep Dive)
## Implementation Plan

---

## 🎯 Objectives

1. **Market Structure Awareness**: Add liquidity sweeps, BOS/CHOCH, fair value gaps
2. **Session-Specific Logic**: London/NY/Asia playbooks with explicit rules
3. **Cross-Asset Confluence**: DXY → USD pairs; yields → Gold; risk indices → BTC
4. **Execution Upgrades**: OCO brackets, adaptive TP, momentum-aware trailing
5. **Portfolio Discipline**: Correlation/basket risk management; EV gating
6. **Selectivity**: Increase expectancy without materially increasing risk

**Success Metrics**: Higher win rate, better RR realization, reduced correlated losses, measurable EV improvement per decision.

---

## 📋 Phase 4 Structure (5 Sub-Phases)

### **Phase 4.1: Market Structure Toolkit** (2-3 days)
Build deterministic structure detectors on top of Phase-0 features.

### **Phase 4.2: Session Playbooks** (1-2 days)
Codify session-specific rules into templates and validators.

### **Phase 4.3: Cross-Asset Confluence** (2-3 days)
Lightweight correlation/confluence scoring system.

### **Phase 4.4: Execution & Exit Upgrades** (2-3 days)
OCO brackets, adaptive TP/trailing, pending order hygiene.

### **Phase 4.5: Portfolio Discipline & EV Gate** (2-3 days)
Correlation matrix, basket risk, EV threshold enforcement.

**Total Estimated Time**: 9-14 days (depending on testing depth)

---

## 🛠️ Phase 4.1: Market Structure Toolkit

### **Goal**
Add deterministic detectors for structure-based edge indicators.

### **Components**

#### **A) Equal Highs/Lows Detector**
**File**: `domain/liquidity.py` (enhance existing or create new)

```python
def detect_equal_highs(
    highs: np.ndarray, 
    atr: float, 
    lookback: int = 50, 
    tolerance_mult: float = 0.1
) -> Dict[str, Any]:
    """
    Detect clusters of equal highs (resting liquidity).
    
    Returns:
        {
            "eq_high_cluster": bool,
            "cluster_price": float,
            "cluster_count": int,
            "bars_ago": int
        }
    """
```

**Parameters**:
- `pips_tol = 0.1 × ATR(14)`
- `lookbackN = 50 bars`

**Usage**: Flag areas where price repeatedly failed to break (resting orders).

#### **B) Sweep / Liquidity Grab Detector**
**File**: `domain/liquidity.py`

```python
def detect_sweep(
    bars: pd.DataFrame,  # OHLC
    atr: float,
    sweep_threshold: float = 0.15
) -> Dict[str, Any]:
    """
    Detect liquidity sweeps (stop hunts).
    
    Bullish sweep: High breaks prior swing high by ≥0.15×ATR 
                   but closes back below prior high.
    
    Returns:
        {
            "sweep_bull": bool,
            "sweep_bear": bool,
            "depth": float,  # break distance / ATR
            "bars_ago": int
        }
    """
```

**Signals**: Used for reversal setups or pullback triggers in trends.

#### **C) BOS / CHOCH Detector**
**File**: `domain/market_structure.py` (enhance existing)

```python
def detect_bos_choch(
    swings: List[Dict],  # swing highs/lows
    close: float,
    atr: float,
    bos_threshold: float = 0.2
) -> Dict[str, Any]:
    """
    Detect Break of Structure (BOS) and Change of Character (CHOCH).
    
    BOS: Close beyond last swing by ≥0.2×ATR, sustained ≥1 bar
    CHOCH: BOS that reverses prior swing sequence (LL → HH)
    
    Returns:
        {
            "bos_bull": bool,
            "bos_bear": bool,
            "choch_bull": bool,
            "choch_bear": bool,
            "bars_since_bos": int
        }
    """
```

**Usage**: Promote trend-continuation after BOS; allow "first pullback after CHOCH" entries.

#### **D) FVG (Fair Value Gap) Detector**
**File**: `domain/patterns.py` or `domain/market_structure.py`

```python
def detect_fvg(
    bars: pd.DataFrame,  # OHLC
    atr: float,
    min_width_mult: float = 0.1
) -> Dict[str, Any]:
    """
    Detect Fair Value Gaps.
    
    Bearish FVG: high(n-1) < low(n+1), width ≥ 0.1×ATR
    Bullish FVG: low(n-1) > high(n+1), width ≥ 0.1×ATR
    
    Returns:
        {
            "fvg_bull": bool,
            "fvg_bear": bool,
            "fvg_zone": (upper, lower),
            "width_atr": float,
            "bars_ago": int
        }
    """
```

**Filters**: Reject FVGs overlapping session gaps or news spikes unless vol regime is "volatile-trending".

#### **E) Wick Asymmetry Detector**
**File**: `domain/candle_stats.py` (enhance existing)

```python
def calculate_wick_asymmetry(bar: Dict) -> float:
    """
    Calculate wick asymmetry: (upper_wick - lower_wick) / range
    
    Returns: float in range [-1, 1]
        > 0.5: Strong upper rejection
        < -0.5: Strong lower rejection
    """
```

**Usage**: Strengthen sweep/rejection logic; penalize trend trades with repeated counter-trend wick dominance at HTF.

### **Integration Points**
1. **Feature Builder**: Add new structure module
   ```python
   # infra/feature_structure.py
   def compute_structure_features(bars_dict, atr_dict):
       return {
           "equal_highs": detect_equal_highs(...),
           "sweep": detect_sweep(...),
           "bos_choch": detect_bos_choch(...),
           "fvg": detect_fvg(...),
           "wick_asymmetry": calculate_wick_asymmetry(...)
       }
   ```

2. **Prompt Templates**: Add structure tokens
   ```
   Structure Context:
   - BOS/CHOCH: {bos_bull}, {choch_bull}
   - Sweep: {sweep_bull} (depth: {sweep_depth})
   - FVG: {fvg_bull} at {fvg_zone}
   - Equal highs: {eq_high_cluster} at {cluster_price}
   ```

3. **Validator**: Add structure-aware rules
   ```python
   # infra/prompt_validator.py
   def _validate_structure_alignment(response, context):
       # Penalize mid-range entries
       # Reward BOS + pullback setups
       # Validate sweep rejection logic
   ```

### **Testing**
```python
# test_structure_toolkit.py
def test_equal_highs_detection():
    # Test with known equal highs scenario
    
def test_sweep_detection():
    # Test bullish/bearish sweep scenarios
    
def test_bos_choch():
    # Test trend break scenarios
```

---

## 🕐 Phase 4.2: Session Playbooks

### **Goal**
Codify session-specific rules into templates and validators for explicit enforcement.

### **Components**

#### **A) Session-Specific Template Variants**
**File**: `infra/prompt_templates.py`

Add session-specific variants:
```python
"trend_pullback_london_v1": {
    "name": "Trend Pullback (London)",
    "session_preference": "london",
    "min_rr": 1.8,
    "required_conditions": {
        "adx": 20,
        "volume_z": 0.0,
        "spread_atr_pct": 0.20
    },
    "confidence_bonus": {
        "bos_recent": 10  # +10 if BOS within 10 bars
    }
}

"range_fade_asia_v1": {
    "name": "Range Fade (Asia)",
    "session_preference": "asia",
    "min_rr": 1.5,
    "required_conditions": {
        "bb_width": 0.02,  # Minimum range width
        "wick_rejection": True
    },
    "confidence_penalty": {
        "breakout_attempt": -15  # -15 for breakouts without volume
    }
}

"breakout_ny_v1": {
    "name": "Breakout (New York)",
    "session_preference": "ny",
    "min_rr": 2.0,
    "required_conditions": {
        "volume_z": 1.0,  # Minimum volume confirmation
        "news_clear": True  # No red news ±45m
    },
    "confidence_penalty": {
        "spread_spike": -10,  # -10 if spread spikes at open
        "mid_range": -10      # -10 if price mid-range
    }
}
```

#### **B) Session-Aware Router Logic**
**File**: `infra/prompt_router.py`

Enhance `_select_template()`:
```python
def _select_template(self, context: RouterContext) -> Optional[PromptTemplate]:
    """Select template with session preference."""
    regime = context.regime
    session = context.session
    
    # Try session-specific template first
    template_key = f"{regime.value}_{session.value}"
    template = self.template_manager.get_session_template(template_key)
    
    if template and self._validate_session_requirements(template, context):
        return template
    
    # Fall back to generic template
    return self.template_manager.get_active_template(regime.value)
```

#### **C) Session Validator Rules**
**File**: `infra/prompt_validator.py`

Add `_validate_session_requirements()`:
```python
def _validate_session_requirements(
    self, 
    response: Dict, 
    context: Dict,
    template_config: Dict
) -> List[str]:
    """Validate session-specific requirements."""
    errors = []
    session = context.get("session", "unknown")
    
    # London: Require ADX, volume, spread limits
    if session == "london":
        adx = context.get("M5", {}).get("adx", 0)
        if adx < 20:
            errors.append("London breakout requires ADX ≥ 20")
            
        spread_atr = context.get("M5", {}).get("spread_atr_pct", 0)
        if spread_atr > 0.20:
            errors.append("London spread too high (>20% ATR)")
    
    # New York: Check for mid-range, news, spread spike
    elif session == "ny":
        bb_width = context.get("M5", {}).get("bb_width", 0)
        news_block = context.get("M5", {}).get("news_blackout", False)
        
        if response.get("strategy") == "range_fade" and bb_width < 0.03:
            errors.append("NY range-fade requires bb_width ≥ 0.03")
            
        if news_block:
            errors.append("NY trade blocked: red news within 45 minutes")
    
    # Asia: Restrict breakouts, require volume for trends
    elif session == "asia":
        if response.get("strategy") == "breakout":
            volume_z = context.get("M5", {}).get("volume_zscore", 0)
            if volume_z < 1.5:
                errors.append("Asia breakout requires volume_zscore ≥ 1.5")
    
    return errors
```

### **Integration**
1. Update `PromptTemplateManager` to support session variants
2. Enhance `RouterContext` with session-specific features
3. Add session requirement checks to validator
4. Update confidence blending to include session penalties

### **Testing**
```python
# test_session_playbooks.py
def test_london_breakout_requirements():
    # Test ADX, volume, spread requirements
    
def test_ny_range_fade_restrictions():
    # Test bb_width, news block scenarios
    
def test_asia_breakout_volume_requirement():
    # Test volume_z threshold enforcement
```

---

## 🌐 Phase 4.3: Cross-Asset Confluence

### **Goal**
Add lightweight cross-asset correlation/confluence scoring for USD pairs, Gold, and BTC.

### **Components**

#### **A) Confluence Data Provider**
**File**: `infra/confluence_provider.py` (new)

```python
class ConfluenceProvider:
    """Provides cross-asset confluence scores."""
    
    def __init__(self, mt5svc: MT5Service):
        self.mt5svc = mt5svc
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    def get_confluence_score(self, symbol: str) -> Dict[str, Any]:
        """
        Calculate confluence score (-20 to +20) for symbol.
        
        Returns:
            {
                "score": float (-20 to +20),
                "dxy_alignment": float (-10 to +10),
                "yield_alignment": float (-10 to +10),
                "risk_index_alignment": float (-10 to +10),
                "components": {...}
            }
        """
        
    def _get_dxy_slope(self) -> float:
        """Get DXY slope (EMA20 - EMA50) / price."""
        
    def _get_yield_slope(self) -> float:
        """Get US 10Y yield slope proxy."""
        
    def _get_risk_index_slope(self) -> float:
        """Get risk-on/off index slope (e.g., Nasdaq proxy)."""
```

**Confluence Rules**:

**USD Pairs ↔ DXY**:
```python
def _calculate_usd_pair_confluence(self, symbol: str, direction: str) -> float:
    """
    Long EURUSD needs DXY slope ≤ 0 (flat to down).
    If DXY diverges (up), return -10 penalty.
    """
    dxy_slope = self._get_dxy_slope()
    
    if symbol in ["EURUSD", "GBPUSD", "AUDUSD"]:
        if direction == "BUY" and dxy_slope > 0.1:  # DXY rising
            return -10
        elif direction == "SELL" and dxy_slope < -0.1:  # DXY falling
            return -10
    
    return 0  # Neutral or aligned
```

**XAUUSD ↔ Yields**:
```python
def _calculate_gold_confluence(self, direction: str) -> float:
    """
    Long XAUUSD stronger when yields flat/down.
    Penalty if yields rising into entry.
    """
    yield_slope = self._get_yield_slope()
    
    if direction == "BUY" and yield_slope > 0.2:  # Yields rising
        return -10
    
    return 0
```

**BTCUSD ↔ Risk Indices**:
```python
def _calculate_btc_confluence(self, direction: str) -> float:
    """
    Trend trades get +10 if risk index aligns.
    """
    risk_slope = self._get_risk_index_slope()
    
    if direction == "BUY" and risk_slope > 0.1:  # Risk-on
        return +10
    elif direction == "SELL" and risk_slope < -0.1:  # Risk-off
        return +10
    
    return 0
```

#### **B) Integration into Feature Builder**
**File**: `infra/feature_builder.py`

```python
def build_features(symbol: str, mt5svc: MT5Service, bridge: IndicatorBridge) -> Dict:
    # ... existing feature building ...
    
    # Add confluence scoring
    confluence_provider = ConfluenceProvider(mt5svc)
    confluence_data = confluence_provider.get_confluence_score(symbol)
    
    features["confluence"] = confluence_data
    
    return features
```

#### **C) Validator Confluence Check**
**File**: `infra/prompt_validator.py`

```python
def _validate_confluence(self, response: Dict, context: Dict) -> List[str]:
    """Validate cross-asset confluence."""
    errors = []
    warnings = []
    
    confluence = context.get("confluence", {})
    confluence_score = confluence.get("score", 0)
    
    # Hard gate: confluence < -10 requires higher RR
    if confluence_score < -10:
        min_rr = context.get("template_config", {}).get("min_rr", 1.5)
        required_rr = min_rr + 0.3
        
        if response.get("rr", 0) < required_rr:
            errors.append(f"Confluence too low ({confluence_score:.1f}): requires RR ≥ {required_rr:.1f}")
    
    # Warning for moderate divergence
    elif confluence_score < -5:
        warnings.append(f"Moderate confluence divergence ({confluence_score:.1f})")
    
    return errors
```

#### **D) Confidence Blending**
**File**: `infra/prompt_router.py` or validator

```python
def _blend_confluence_into_confidence(
    base_confidence: Dict[str, int],
    confluence_score: float
) -> Dict[str, int]:
    """
    Adjust confidence based on confluence.
    Confluence: -20 to +20 scale
    """
    # Map confluence to confidence adjustment (-10 to +10)
    confluence_adjustment = int(confluence_score * 0.5)
    
    base_confidence["overall"] = max(0, min(100, 
        base_confidence["overall"] + confluence_adjustment
    ))
    
    base_confidence["confluence"] = max(0, min(100, 50 + confluence_score * 2.5))
    
    return base_confidence
```

### **Testing**
```python
# test_confluence.py
def test_dxy_usd_pair_alignment():
    # Test DXY up → EURUSD long penalty
    
def test_gold_yield_alignment():
    # Test yields rising → XAUUSD long penalty
    
def test_btc_risk_alignment():
    # Test risk-on → BTCUSD long bonus
```

---

## 🎯 Phase 4.4: Execution & Exit Upgrades

### **Goal**
Enhance order execution with OCO brackets, adaptive TP, and momentum-aware trailing.

### **Components**

#### **A) OCO Bracket Orders**
**File**: `trade_manager.py` (enhance existing)

```python
def place_oco_bracket(
    symbol: str,
    consolidation_high: float,
    consolidation_low: float,
    atr: float,
    sl_buffer: float = 0.5,
    expiry_minutes: int = 60
) -> Dict[str, Any]:
    """
    Place OCO bracket orders for breakouts.
    
    Setup:
        - Buy stop above consolidation_high + 0.2×ATR
        - Sell stop below consolidation_low - 0.2×ATR
        - Cancel opposite on fill
        - Auto-cancel at session end or red news
    
    Returns:
        {
            "buy_ticket": int,
            "sell_ticket": int,
            "expiry_ts": int,
            "status": "pending"
        }
    """
```

**Integration**: Add OCO option to `/execute` handler:
```python
# handlers/trading.py
if order_recommendation == "OCO":
    result = place_oco_bracket(...)
```

#### **B) Pending Order Hygiene**
**File**: `infra/pseudo_pendings.py` or `trade_manager.py`

```python
class PendingOrderManager:
    """Manages pending order lifecycle."""
    
    def __init__(self):
        self.pending_orders = {}
        self.cooldowns = {}
    
    def create_pending(
        self,
        symbol: str,
        order_type: str,
        price: float,
        sl: float,
        tp: float,
        expiry_minutes: int = 60,
        max_rearms: int = 1
    ) -> str:
        """
        Create pending order with expiry and re-arm limits.
        
        Expiry: 30-90 minutes depending on session/volatility
        Re-arm: Only once if structure persists; otherwise cooldown
        """
    
    def check_expiry(self, order_id: str) -> bool:
        """Check if order has expired."""
    
    def rearm_order(self, order_id: str) -> bool:
        """Re-arm expired order if conditions allow."""
```

#### **C) Adaptive TP / Trailing**
**File**: `infra/position_watcher.py` (enhance existing)

```python
def calculate_adaptive_tp(
    position: Dict,
    tech: Dict,
    original_tp: float
) -> float:
    """
    Adjust TP based on momentum and volatility.
    
    Momentum extension:
        If MACD hist slope > threshold or range expansion > 1.2× median:
            Extend TP by +0.5R
    
    Vol contraction:
        If BB bandwidth shrinks rapidly:
            Scale-out at TP1, move SL to breakeven
    """
    
def calculate_trailing_stop(
    position: Dict,
    tech: Dict,
    current_sl: float
) -> float:
    """
    Trail stop using SuperTrend or Keltner upper/lower.
    
    Only trail if momentum persists (MACD hist > 0 for longs).
    """
```

**Integration**: Add to position watcher loop:
```python
# infra/position_watcher.py
async def _check_position_management():
    for position in positions:
        # Check for adaptive TP adjustment
        new_tp = calculate_adaptive_tp(position, tech, position["tp"])
        if new_tp != position["tp"]:
            modify_position_tp(position["ticket"], new_tp)
        
        # Check for trailing stop
        new_sl = calculate_trailing_stop(position, tech, position["sl"])
        if new_sl != position["sl"]:
            modify_position_sl(position["ticket"], new_sl)
```

#### **D) SL Anchoring Enhancement**
**File**: `infra/prompt_validator.py`

```python
def _validate_sl_anchoring(self, response: Dict, context: Dict) -> List[str]:
    """
    Validate SL is anchored to structure with buffer.
    
    Rules:
        - SL must be beyond nearest swing or FVG edge by buffer = 0.1×ATR
        - If geometry increases SL and RR < min_rr: skip or switch order type
    """
    errors = []
    
    entry = response.get("entry", 0)
    sl = response.get("sl", 0)
    
    # Get structure reference (swing, FVG edge)
    structure = context.get("structure", {})
    nearest_swing = structure.get("nearest_swing_low" if response.get("direction") == "BUY" else "nearest_swing_high", 0)
    
    atr = context.get("M5", {}).get("atr_14", 0)
    buffer = 0.1 * atr
    
    # Validate SL beyond structure + buffer
    if response.get("direction") == "BUY":
        required_sl = nearest_swing - buffer
        if sl > required_sl:
            errors.append(f"SL too tight: must be below {required_sl:.5f} (swing + buffer)")
    else:
        required_sl = nearest_swing + buffer
        if sl < required_sl:
            errors.append(f"SL too tight: must be above {required_sl:.5f} (swing + buffer)")
    
    return errors
```

### **Testing**
```python
# test_execution_upgrades.py
def test_oco_bracket_placement():
    # Test bracket distance, expiry, cancellation
    
def test_pending_expiry_and_rearm():
    # Test expiry timing, re-arm limits
    
def test_adaptive_tp_extension():
    # Test momentum-based TP extension
    
def test_trailing_stop_logic():
    # Test SuperTrend/Keltner trailing
```

---

## 🛡️ Phase 4.5: Portfolio Discipline & EV Gate

### **Goal**
Enforce portfolio-level risk management with correlation, basket risk, and EV thresholds.

### **Components**

#### **A) Correlation Matrix Builder**
**File**: `infra/portfolio_risk.py` (new)

```python
class PortfolioRiskManager:
    """Manages portfolio-level risk and correlation."""
    
    def __init__(self, mt5svc: MT5Service):
        self.mt5svc = mt5svc
        self.correlation_matrix = {}
        self.last_update = None
        self.update_interval = 3600  # 1 hour
    
    def update_correlation_matrix(self):
        """
        Build rolling correlation matrix using last 500-1000 bars on M15.
        Uses daily updated coefficients for efficiency.
        """
        symbols = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "XAUUSD", "BTCUSD"]
        
        # Get M15 data for last 1000 bars
        data = {}
        for symbol in symbols:
            bars = self.mt5svc.get_bars(symbol, "M15", 1000)
            data[symbol] = bars["close"].pct_change()
        
        # Calculate correlation matrix
        import pandas as pd
        df = pd.DataFrame(data)
        self.correlation_matrix = df.corr().to_dict()
    
    def get_correlation(self, sym1: str, sym2: str) -> float:
        """Get correlation coefficient between two symbols."""
        if not self.correlation_matrix:
            self.update_correlation_matrix()
        
        return self.correlation_matrix.get(sym1, {}).get(sym2, 0.0)
```

#### **B) Basket Risk Calculator**
**File**: `infra/portfolio_risk.py`

```python
def calculate_basket_risk(
    open_positions: List[Dict],
    new_position: Dict,
    correlation_matrix: Dict,
    max_basket_risk_pct: float = 2.0
) -> Dict[str, Any]:
    """
    Calculate total correlated risk across portfolio.
    
    Rules:
        - Max concurrent USD-long exposure: 2 positions
        - Do not open EURUSD long if already long GBPUSD + AUDUSD (ρ > 0.7)
        - Basket risk cap: sum of position risks ≤ 2% (configurable)
    
    Returns:
        {
            "total_risk_pct": float,
            "correlated_risk_pct": float,
            "usd_exposure_count": int,
            "violations": List[str]
        }
    """
```

**Integration**: Add to validator:
```python
# infra/prompt_validator.py
def _validate_portfolio_risk(self, response: Dict, context: Dict) -> List[str]:
    """Validate portfolio-level risk constraints."""
    errors = []
    
    # Get current positions
    open_positions = context.get("open_positions", [])
    
    # Calculate basket risk
    portfolio_mgr = PortfolioRiskManager(mt5svc)
    risk_analysis = portfolio_mgr.calculate_basket_risk(
        open_positions,
        response,
        portfolio_mgr.correlation_matrix
    )
    
    # Check violations
    if risk_analysis["total_risk_pct"] > 2.0:
        errors.append(f"Basket risk too high: {risk_analysis['total_risk_pct']:.1f}% > 2.0%")
    
    for violation in risk_analysis["violations"]:
        errors.append(f"Portfolio constraint: {violation}")
    
    return errors
```

#### **C) EV Gate**
**File**: `infra/prompt_validator.py`

```python
def _validate_expected_value(
    self,
    response: Dict,
    context: Dict,
    ev_min: float = 0.10
) -> List[str]:
    """
    Validate Expected Value (EV) meets minimum threshold.
    
    EV ≈ (confidence/100) × planned_RR - cost_penalty
    
    Rule: Require EV ≥ EV_min (e.g., 0.10R) after cost adjustment
    If EV marginal (< EV_min), allow only if:
        - Cross-TF confluence high (> 0.8)
        - Cross-asset confluence high (> 10)
        - Session favorable (London/NY for trends)
    """
    errors = []
    
    confidence = response.get("confidence", {}).get("overall", 50)
    rr = response.get("rr", 0)
    
    # Calculate costs
    spread_atr = context.get("M5", {}).get("spread_atr_pct", 0.05)
    slip_atr = context.get("M5", {}).get("expected_slippage_atr_pct", 0.05)
    cost_penalty = (spread_atr + slip_atr) / rr if rr > 0 else 1.0
    
    # Calculate EV
    ev = (confidence / 100.0) * rr - cost_penalty
    
    # Check minimum threshold
    if ev < ev_min:
        # Check for override conditions
        cross_tf_score = context.get("cross_tf", {}).get("trend_consensus_score", 0)
        confluence_score = context.get("confluence", {}).get("score", 0)
        session = context.get("session", "unknown")
        
        override_allowed = (
            cross_tf_score > 0.8 and
            confluence_score > 10 and
            session in ["london", "ny"]
        )
        
        if not override_allowed:
            errors.append(
                f"EV too low: {ev:.2f}R < {ev_min:.2f}R "
                f"(conf={confidence}, rr={rr:.1f}, cost={cost_penalty:.2f})"
            )
    
    return errors
```

#### **D) Confidence Blending with All Components**
**File**: `infra/prompt_router.py` or validator

```python
def blend_confidence_score(
    base_scores: Dict[str, int],
    structure_score: int,
    confluence_score: float,
    session_penalty: int,
    weights: Dict[str, float] = None
) -> int:
    """
    Blend all confidence components with weights.
    
    Components:
        - trend_score: Trend alignment
        - pattern_score: Pattern quality
        - volume_score: Volume confirmation
        - regime_fit: Regime classification fit
        - structure_score: Market structure alignment
        - confluence_score: Cross-asset confluence
        - session_penalty: Session-specific adjustment
    
    Defaults:
        w_trend=0.2, w_pattern=0.15, w_volume=0.15,
        w_regime=0.15, w_structure=0.2, w_confluence=0.15
    """
    if weights is None:
        weights = {
            "trend": 0.20,
            "pattern": 0.15,
            "volume": 0.15,
            "regime": 0.15,
            "structure": 0.20,
            "confluence": 0.15
        }
    
    overall = (
        weights["trend"] * base_scores.get("trend", 50) +
        weights["pattern"] * base_scores.get("pattern", 50) +
        weights["volume"] * base_scores.get("volume", 50) +
        weights["regime"] * base_scores.get("regime_fit", 50) +
        weights["structure"] * structure_score +
        weights["confluence"] * (50 + confluence_score * 2.5) +  # Map -20..+20 to 0..100
        session_penalty
    )
    
    # Cap overall at 60 if any sub-score < 40 (unless A+ override)
    min_sub_score = min(base_scores.values())
    has_a_plus_override = (
        base_scores.get("bos_recent", False) and
        base_scores.get("fvg_aligned", False) and
        base_scores.get("donchian_breach", False)
    )
    
    if min_sub_score < 40 and not has_a_plus_override:
        overall = min(overall, 60)
    
    return int(max(0, min(100, overall)))
```

### **Testing**
```python
# test_portfolio_discipline.py
def test_correlation_matrix_build():
    # Test matrix calculation and caching
    
def test_basket_risk_calculation():
    # Test risk aggregation with correlations
    
def test_usd_exposure_limits():
    # Test max concurrent USD positions
    
def test_ev_gate_threshold():
    # Test EV calculation and threshold enforcement
    
def test_confidence_blending():
    # Test weighted confidence calculation
```

---

## 📊 Phase 4.6: Symbol Personality Presets

### **Goal**
Apply symbol-specific parameter overrides for XAUUSD, BTCUSD, FX pairs.

### **Components**

#### **A) Symbol Config System**
**File**: `config/symbol_presets.py` (new)

```python
SYMBOL_PRESETS = {
    "XAUUSD": {
        "sl_buffer_mult": 0.5,  # SL ≥ 0.5×ATR (wider than default 0.4)
        "order_preference": "stop",  # Prefer stop orders
        "session_bias": ["london", "ny"],  # Strong session preference
        "confluence_penalty": {
            "yields_rising": -10  # Penalty on rising yields
        },
        "min_rr": 1.8,
        "structure_required": True  # Require structure confirmation
    },
    
    "BTCUSD": {
        "sl_buffer_mult": 0.4,
        "rr_range": (2.0, 3.0),  # Allow larger RR targets
        "momentum_required": True,  # Only on momentum bursts
        "volume_threshold": 1.5,  # Require strong volume
        "session_bias": ["london", "ny"],  # Avoid Asia unless volume spikes
        "min_rr": 2.0
    },
    
    "EURUSD": {
        "sl_buffer_mult": 0.4,  # Normal SL
        "session_balanced": True,  # No strong session bias
        "confluence_required": {
            "dxy": True  # Strong DXY confluence gating
        },
        "min_rr": 1.5
    },
    
    "GBPUSD": {
        "sl_buffer_mult": 0.45,  # Slightly wider (more volatile)
        "session_bias": ["london"],  # London preference
        "confluence_required": {
            "dxy": True
        },
        "min_rr": 1.6
    }
}

def get_symbol_preset(symbol: str) -> Dict[str, Any]:
    """Get symbol-specific configuration."""
    return SYMBOL_PRESETS.get(symbol, {
        "sl_buffer_mult": 0.4,
        "min_rr": 1.5,
        "session_balanced": True
    })
```

#### **B) Integration into Validator**
**File**: `infra/prompt_validator.py`

```python
def _apply_symbol_preset(self, symbol: str, response: Dict, context: Dict) -> List[str]:
    """Apply symbol-specific validation rules."""
    from config.symbol_presets import get_symbol_preset
    
    preset = get_symbol_preset(symbol)
    errors = []
    
    # Apply SL buffer
    sl_buffer_mult = preset.get("sl_buffer_mult", 0.4)
    atr = context.get("M5", {}).get("atr_14", 0)
    entry = response.get("entry", 0)
    sl = response.get("sl", 0)
    sl_distance = abs(entry - sl)
    
    if sl_distance < (sl_buffer_mult * atr):
        errors.append(f"SL too tight for {symbol}: requires ≥{sl_buffer_mult}×ATR")
    
    # Apply RR requirements
    min_rr = preset.get("min_rr", 1.5)
    if response.get("rr", 0) < min_rr:
        errors.append(f"{symbol} requires RR ≥ {min_rr}")
    
    # Apply momentum requirements (BTCUSD)
    if preset.get("momentum_required"):
        macd_hist = context.get("M5", {}).get("macd_hist", 0)
        if abs(macd_hist) < 0.5:
            errors.append(f"{symbol} requires momentum burst (MACD hist)")
    
    # Apply volume requirements (BTCUSD)
    volume_threshold = preset.get("volume_threshold")
    if volume_threshold:
        volume_z = context.get("M5", {}).get("volume_zscore", 0)
        if volume_z < volume_threshold:
            errors.append(f"{symbol} requires volume_zscore ≥ {volume_threshold}")
    
    # Apply confluence requirements
    confluence_required = preset.get("confluence_required", {})
    if confluence_required.get("dxy"):
        confluence_score = context.get("confluence", {}).get("dxy_alignment", 0)
        if confluence_score < -5:
            errors.append(f"{symbol} DXY confluence too low")
    
    return errors
```

### **Testing**
```python
# test_symbol_presets.py
def test_xauusd_wider_sl():
    # Test XAUUSD requires SL ≥ 0.5×ATR
    
def test_btcusd_momentum_requirement():
    # Test BTCUSD requires momentum burst
    
def test_eurusd_dxy_confluence():
    # Test EURUSD DXY confluence gating
```

---

## 📈 Phase 4.7: Telemetry & Analytics

### **Goal**
Enhanced logging and analytics for Phase 4 features.

### **Components**

#### **A) Extended Journal Schema**
**File**: `infra/journal_repo.py`

Add new columns to `events` table:
```python
_EVENTS_PHASE4_COLS = [
    "structure_flags",  # JSON: sweep, BOS, CHOCH, FVG
    "confluence_score",  # float: -20 to +20
    "ev_score",  # float: expected value
    "basket_risk_pct",  # float: portfolio risk
    "session",  # str: asia/london/ny
    "structure_score",  # int: 0-100
]
```

#### **B) Decision Logging Enhancement**
**File**: `infra/prompt_router.py`

```python
def route_and_analyze(...) -> DecisionOutcome:
    # ... existing logic ...
    
    # IMPROVED: Log Phase 4 telemetry
    telemetry = {
        "structure": {
            "sweep_bull": features.get("sweep", {}).get("sweep_bull"),
            "bos_bull": features.get("bos_choch", {}).get("bos_bull"),
            "fvg_bull": features.get("fvg", {}).get("fvg_bull")
        },
        "confluence_score": features.get("confluence", {}).get("score", 0),
        "ev_score": self._calculate_ev(trade_spec, features),
        "session": context.session.value,
        "structure_score": self._calculate_structure_score(features)
    }
    
    outcome.telemetry = telemetry
    logger.info(f"Phase 4 telemetry: {telemetry}")
```

#### **C) Analytics Queries**
**File**: `infra/analytics.py` (new)

```python
class Phase4Analytics:
    """Analytics for Phase 4 features."""
    
    def win_rate_by_structure_tag(self, structure_flag: str) -> float:
        """Calculate win rate for specific structure flag (BOS, sweep, FVG)."""
    
    def win_rate_by_session(self, session: str) -> float:
        """Calculate win rate by trading session."""
    
    def win_rate_by_confluence_bucket(self) -> Dict[str, float]:
        """Win rate by confluence score buckets (< -10, -10..0, 0..10, > 10)."""
    
    def avg_rr_by_structure_tag(self, structure_flag: str) -> float:
        """Average realized RR for structure flag."""
    
    def top_skip_reasons(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Most common skip reasons."""
    
    def ev_vs_realized_pnl(self) -> Dict[str, Any]:
        """Compare predicted EV vs actual PnL."""
```

### **Dashboard Queries**
```sql
-- Win rate by structure flag
SELECT 
    structure_flags,
    COUNT(*) as trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
    AVG(r_multiple) as avg_r
FROM events
WHERE event = 'trade_close'
  AND structure_flags IS NOT NULL
GROUP BY structure_flags;

-- Win rate by session
SELECT 
    session,
    COUNT(*) as trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
    AVG(ev_score) as avg_ev
FROM events
WHERE event = 'trade_close'
GROUP BY session;

-- Confluence effectiveness
SELECT 
    CASE 
        WHEN confluence_score < -10 THEN 'very_negative'
        WHEN confluence_score < 0 THEN 'negative'
        WHEN confluence_score < 10 THEN 'positive'
        ELSE 'very_positive'
    END as confluence_bucket,
    COUNT(*) as trades,
    AVG(r_multiple) as avg_r,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
FROM events
WHERE event = 'trade_close'
GROUP BY confluence_bucket;
```

---

## 🧪 Testing Strategy

### **Unit Tests**
- Each detector/calculator has isolated tests
- Mock MT5 data for reproducible scenarios
- Test edge cases (missing data, extreme values)

### **Integration Tests**
- End-to-end flow: feature → router → validator → journal
- Test all Phase 4 components together
- Verify telemetry logging

### **Validation Tests**
- Historical replay with known market conditions
- Compare Phase 3 vs Phase 4 skip rates
- Measure EV improvement

### **Performance Tests**
- Benchmark structure detectors (<10ms per symbol)
- Correlation matrix update time (<1s for 6 symbols)
- End-to-end latency (<500ms for full analysis)

---

## 📅 Implementation Timeline

### **Week 1: Foundation**
- Days 1-2: Structure toolkit (Phase 4.1)
- Days 3-4: Session playbooks (Phase 4.2)
- Day 5: Testing & integration

### **Week 2: Confluence & Execution**
- Days 1-2: Cross-asset confluence (Phase 4.3)
- Days 3-4: Execution upgrades (Phase 4.4)
- Day 5: Testing & integration

### **Week 3: Portfolio & Analytics**
- Days 1-2: Portfolio discipline (Phase 4.5)
- Days 3-4: Symbol presets & telemetry (Phase 4.6-4.7)
- Day 5: End-to-end testing, documentation

**Total: ~15 working days (3 weeks)**

---

## 🎯 Success Criteria

### **Functional**
- ✅ All structure detectors working correctly
- ✅ Session playbooks enforced in validator
- ✅ Confluence scoring integrated
- ✅ OCO brackets functional
- ✅ Portfolio risk checks active
- ✅ EV gate enforcing thresholds

### **Performance**
- ✅ Win rate improves by ≥5% vs Phase 3
- ✅ Average RR realized improves by ≥10%
- ✅ Skip rate increases by 10-20% (better selectivity)
- ✅ Correlated loss events reduced by ≥30%
- ✅ EV prediction accuracy within 20% of realized

### **Observability**
- ✅ All telemetry logged correctly
- ✅ Dashboard queries functional
- ✅ Top skip reasons trackable
- ✅ Structure/session/confluence analytics available

---

## 🚨 Risks & Mitigations

### **Risk 1: Over-Optimization**
**Mitigation**: Use simple, robust thresholds; validate on out-of-sample data; avoid curve-fitting.

### **Risk 2: Increased Complexity**
**Mitigation**: Maintain Phase 3 fallback; allow gradual rollout; comprehensive testing.

### **Risk 3: Performance Degradation**
**Mitigation**: Benchmark all components; cache correlation matrix; optimize hot paths.

### **Risk 4: False Positives in Structure Detection**
**Mitigation**: Require multiple confirmations; use ATR-normalized thresholds; validate against manual review.

---

## 📚 Documentation

### **User Guide**
- `docs/PHASE4_USER_GUIDE.md`: How to use new features
- `docs/STRUCTURE_PATTERNS.md`: Visual guide to BOS/CHOCH/FVG/sweeps
- `docs/SESSION_STRATEGIES.md`: London/NY/Asia playbook details

### **Developer Guide**
- `docs/PHASE4_ARCHITECTURE.md`: System design and integration
- `docs/TELEMETRY_SCHEMA.md`: Analytics schema and queries
- `docs/SYMBOL_PRESETS.md`: How to configure symbol-specific rules

---

## ✅ Next Steps

1. **Review & Approve** this plan
2. **Set up Git branch**: `feature/phase4-edge-multipliers`
3. **Start with Phase 4.1**: Structure toolkit (low-hanging fruit)
4. **Iterate with feedback**: Test each phase before moving to next
5. **Document as you go**: Keep docs updated with learnings

---

**Ready to proceed with Phase 4.1 (Structure Toolkit)?** 🚀

