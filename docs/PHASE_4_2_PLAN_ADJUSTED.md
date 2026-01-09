# Phase 4.2 - Session-Aware Playbooks (Adjusted Plan)

## Current State Analysis

### ✅ What Already Exists:
1. **Session Detection** (2 implementations):
   - `config/settings.py::get_trading_session()` - Uses Africa/Johannesburg timezone (UTC+2)
     - ASIA: 00:00-08:00 local
     - LONDON: 08:00-16:00 local  
     - NY: 16:00-24:00 local
   - `infra/feature_session_news.py::SessionNewsFeatures._get_current_session()` - Uses UTC
     - tokyo: 00:00-09:00 UTC
     - london: 07:00-16:00 UTC
     - new_york: 12:00-21:00 UTC

2. **Session Context**:
   - `decision_engine.py` already uses session for S/R geometry thresholds
   - Feature builder includes `session` and `session_minutes` in features
   - `POS_TRAIL_ATR_MULT_BY_SESSION` config exists (but empty)

### ⚠️ Issues to Address:
1. **Inconsistent session definitions**:
   - Two different implementations with different times
   - One uses local (UTC+2), one uses UTC
   - Need to standardize on **GMT/UTC for clarity**

2. **No overlap detection**:
   - London-NY overlap (12:00-16:00 UTC) is crucial
   - Asia-London overlap (07:00-09:00 UTC) matters
   - Currently treats sessions as exclusive

3. **No session-specific rules**:
   - Session is detected but not actively used for filtering
   - No confidence adjustments per session
   - No strategy preferences per session

4. **Naming inconsistency**:
   - "tokyo" vs "ASIA"
   - "london" vs "LONDON"
   - "new_york" vs "NY"

## Adjusted Implementation Plan

### 1. Standardize Session Detection ✨

**Decision**: Use **UTC-based times** for consistency with FX market standard.

**Standard Session Times (UTC):**
```python
ASIA_SESSION:    22:00-08:00 UTC  # Tokyo/Sydney
LONDON_SESSION:  08:00-16:00 UTC  # London/Frankfurt
NY_SESSION:      13:00-21:00 UTC  # New York

OVERLAPS:
- LONDON_ASIA_OVERLAP:  08:00-09:00 UTC (thin, transitional)
- LONDON_NY_OVERLAP:    13:00-16:00 UTC (peak liquidity)
- NY_ASIA_OVERLAP:      21:00-22:00 UTC (thin, transitional)
```

**Action**: 
- Enhance `infra/feature_session_news.py` to be the single source of truth
- Add overlap detection
- Deprecate `config/settings.py::get_trading_session()` or make it a wrapper

### 2. Session Profile System (NEW)

Create `infra/session_profiles.py`:

```python
@dataclass
class SessionProfile:
    """Session-specific trading characteristics and rules."""
    name: str
    preferred_strategies: List[str]  # ["trend_pullback", "breakout"]
    discouraged_strategies: List[str]  # ["range_fade"]
    
    # Filters
    min_adx: Optional[float] = None
    min_volume_z: Optional[float] = None
    max_spread_atr_pct: Optional[float] = None
    min_bb_width: Optional[float] = None
    
    # Confidence adjustments
    base_confidence_adj: int = 0  # +10 for favorable, -10 for unfavorable
    strategy_confidence_adj: Dict[str, int] = field(default_factory=dict)
    
    # Time-based filters
    avoid_first_minutes: int = 0  # Skip first X minutes
    avoid_last_minutes: int = 0   # Skip last X minutes
    
    # Symbol-specific adjustments
    symbol_multipliers: Dict[str, float] = field(default_factory=dict)
```

**Profiles**:
- `LONDON_PROFILE` - High liquidity, favor trends/breakouts
- `NY_PROFILE` - High volatility, cautious on reversals
- `ASIA_PROFILE` - Ranges preferred, breakouts discouraged
- `LONDON_NY_OVERLAP_PROFILE` - Peak liquidity, all strategies viable
- `TRANSITION_PROFILE` - Reduced confidence, avoid trades

### 3. Session Rules Engine (NEW)

Create `infra/session_rules.py`:

```python
class SessionRules:
    """Apply session-specific filtering and confidence adjustment."""
    
    def __init__(self):
        self.profiles = self._load_profiles()
    
    def get_active_profile(
        self, 
        session: str, 
        session_minutes: int,
        is_overlap: bool
    ) -> SessionProfile:
        """Get appropriate profile based on session and timing."""
        
    def apply_filters(
        self,
        trade_spec: Dict,
        session_info: Dict,
        features: Dict
    ) -> Tuple[bool, List[str]]:
        """
        Apply session-specific filters.
        Returns: (pass: bool, skip_reasons: List[str])
        """
        
    def adjust_confidence(
        self,
        confidence: float,
        strategy: str,
        session_info: Dict,
        features: Dict,
        symbol: str
    ) -> Tuple[float, List[str]]:
        """
        Adjust confidence based on session characteristics.
        Returns: (adjusted_confidence: float, reasons: List[str])
        """
```

**Key Features**:
- Filter trades that don't meet session requirements
- Adjust confidence based on session favorability
- Track and log adjustment reasons for analytics
- Symbol-specific session rules (e.g., BTCUSD in Asia)

### 4. Enhanced Session Detection (IMPROVE)

Enhance `infra/feature_session_news.py`:

```python
@dataclass
class SessionInfo:
    """Complete session context."""
    primary_session: str  # "ASIA", "LONDON", "NY"
    is_overlap: bool
    overlap_type: Optional[str]  # "LONDON_NY", "ASIA_LONDON", etc.
    minutes_into_session: int
    session_strength: float  # 0.0-1.0, reduced during transitions
    is_transition_period: bool  # First/last 30 minutes
    is_weekend: bool

class SessionNewsFeatures:
    def get_session_info(self, current_time: datetime) -> SessionInfo:
        """Get complete session context with overlap detection."""
        
    def _detect_overlap(self, utc_time: time) -> Tuple[bool, Optional[str]]:
        """Detect if current time is in a session overlap period."""
        
    def _calculate_session_strength(
        self, 
        session: str, 
        minutes_into: int,
        is_overlap: bool
    ) -> float:
        """
        Calculate session strength (0.0-1.0).
        Reduced during first/last 30 min and overlaps.
        """
```

### 5. Integration Points (ENHANCE)

#### A. Prompt Router Integration
File: `infra/prompt_router.py`

```python
# In _create_context():
session_info = self._get_session_info(features)  # NEW
context.session_info = session_info  # NEW

# In _select_template():
# Apply session bias to template selection
if session_info.primary_session == "ASIA":
    if strategy == "range_fade":
        priority += 0.2  # Prefer range strategies
    elif strategy == "breakout":
        priority -= 0.2  # Discourage breakouts

# In route_and_analyze():
# Apply session rules BEFORE returning
session_rules = SessionRules()
pass_filters, skip_reasons = session_rules.apply_filters(
    trade_spec, session_info, features
)
if not pass_filters:
    return DecisionOutcome(status="skip", skip_reasons=skip_reasons, ...)

# Adjust confidence
adjusted_conf, adj_reasons = session_rules.adjust_confidence(
    trade_spec.confidence, 
    trade_spec.strategy,
    session_info,
    features,
    symbol
)
trade_spec.confidence = adjusted_conf
```

#### B. Prompt Templates Enhancement
File: `infra/prompt_templates.py`

Add session-specific guidance to v2 templates:

```python
"trend_pullback_v2": {
    "template": """
    ...
    Enhanced Analysis Rules:
    ...
    
    SESSION-SPECIFIC GUIDANCE:
    {SESSION_GUIDANCE}
    
    - If SESSION=LONDON and trend_strength≥0.7:
      * Confidence bonus: +10
      * Require: ADX≥20, volume_z≥0, spread<20% ATR
      * Avoid first 30 minutes (chop/false breakouts)
      
    - If SESSION=NY and mid-range entry:
      * Confidence penalty: -10
      * Require: volume_z≥1.0 OR confirmed BOS
      * Check for reversal risk near 16:00 UTC (London close)
      
    - If SESSION=ASIA:
      * Confidence penalty: -15
      * Require: Donchian breach AND volume_z≥1.5
      * Prefer range-fade over trend continuation
    
    Adjust confidence accordingly and explain reasoning.
    """
}
```

#### C. Prompt Validator Enhancement  
File: `infra/prompt_validator.py`

```python
def _validate_session_rules(
    self, 
    trade_spec: Dict, 
    context: Dict
) -> Tuple[List[str], List[str]]:
    """
    Validate trade meets session-specific requirements.
    Returns: (errors, warnings)
    """
    errors = []
    warnings = []
    
    session = context.get("session", "UNKNOWN")
    strategy = trade_spec.get("strategy", "")
    features = context.get("features", {})
    
    # Asia breakout rules
    if session == "ASIA" and strategy == "breakout":
        volume_z = features.get("volume_zscore", 0)
        donchian_breakout = features.get("donchian_breakout", False)
        
        if volume_z < 1.5 or not donchian_breakout:
            errors.append(
                "Asia breakouts require volume_z≥1.5 AND Donchian breach"
            )
    
    # London first 30 minutes
    if session == "LONDON":
        session_minutes = features.get("session_minutes", 0)
        if session_minutes < 30:
            warnings.append(
                "London first 30min: higher false breakout risk"
            )
    
    # NY mid-range entries
    if session == "NY" and strategy in ["trend_pullback", "trend_continuation"]:
        range_position = features.get("range_position", 0.5)
        if 0.4 < range_position < 0.6:  # Mid-range
            warnings.append(
                "NY mid-range entry: reduced edge, reversal risk"
            )
    
    return errors, warnings
```

### 6. Configuration (NEW)

Add to `config.py`:

```python
# Session-specific settings
SESSION_RULES_ENABLED = _as_bool(os.getenv("SESSION_RULES_ENABLED", "1"))

# Session profile overrides (JSON string)
SESSION_PROFILE_OVERRIDES = os.getenv("SESSION_PROFILE_OVERRIDES", "{}")

# Symbol-session blacklist (e.g., "BTCUSD:ASIA,EURUSD:WEEKEND")
SYMBOL_SESSION_BLACKLIST = os.getenv("SYMBOL_SESSION_BLACKLIST", "")
```

## Testing Strategy

### 1. Unit Tests
- `tests/test_session_detector.py` - Session detection accuracy
- `tests/test_session_profiles.py` - Profile loading and access
- `tests/test_session_rules.py` - Filter and confidence adjustment logic

### 2. Integration Tests
- `tests/test_session_router_integration.py` - Router + session rules
- `tests/test_session_validator_integration.py` - Validator + session rules

### 3. Historical Validation
- `tests/validate_session_performance.py` - Backtest with/without session rules
- Compare win rates per session
- Measure skip rate improvements

## Migration Path

### Phase 1: Foundation (Non-breaking)
1. ✅ Create `infra/session_profiles.py`
2. ✅ Create `infra/session_rules.py`
3. ✅ Enhance `infra/feature_session_news.py` with overlap detection
4. ✅ Add configuration flags (default OFF)

### Phase 2: Integration (Gradual rollout)
1. ✅ Integrate into Prompt Router (behind flag)
2. ✅ Add session guidance to templates
3. ✅ Enhance validator with session checks
4. ✅ Test with synthetic data

### Phase 3: Validation (Controlled testing)
1. ✅ Enable for single symbol (e.g., XAUUSD)
2. ✅ Monitor skip rates and confidence adjustments
3. ✅ Validate against historical trades
4. ✅ Tune thresholds based on results

### Phase 4: Production (Full rollout)
1. ✅ Enable globally with `SESSION_RULES_ENABLED=1`
2. ✅ Monitor performance metrics
3. ✅ Iterate on profiles based on data

## Success Metrics

### Quantitative:
- **Skip rate increase**: 15-25% for unfavorable session scenarios
- **Confidence accuracy**: Adjusted confidence correlates with win rate
- **Win rate by session**: 5-10% improvement vs. baseline
- **Drawdown reduction**: 10-15% during thin liquidity periods

### Qualitative:
- Clear, actionable skip reasons
- Consistent session handling across components
- Easy to tune and customize per symbol

## Key Differences from Original Plan

### Changes:
1. ✅ **Build on existing** `feature_session_news.py` instead of new `session_detector.py`
2. ✅ **Standardize on UTC** instead of local timezone
3. ✅ **Overlap detection** as first-class feature
4. ✅ **Gradual rollout** with feature flags
5. ✅ **Deprecate** inconsistent `config/settings.py::get_trading_session()`

### Additions:
1. ✅ **Session strength** metric (0.0-1.0)
2. ✅ **Transition period** detection
3. ✅ **Symbol-session blacklist** configuration
4. ✅ **Historical validation** tooling

### Removed:
1. ❌ Separate `SessionDetector` class (use enhanced SessionNewsFeatures)
2. ❌ Complex timezone handling (standardize on UTC)

## Next Steps

**Recommend starting with**:
1. Create `infra/session_profiles.py` with profile definitions
2. Create `infra/session_rules.py` with filtering logic
3. Enhance `infra/feature_session_news.py` with overlap detection
4. Write comprehensive tests
5. Integrate into router (behind flag)

**Then proceed to**:
- Phase 4.3: Cross-Asset Confluence
- Phase 4.4: Execution Upgrades
- Phase 4.5: Portfolio Discipline

