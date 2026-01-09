# Phase 4.2 - Session-Aware Playbooks

## Overview
Transform generic strategy logic into session-specific trading playbooks with concrete rules, filters, and confidence adjustments based on London, New York, and Asia market characteristics.

## Objectives
1. **Session Detection**: Accurate session identification with overlap handling
2. **Session-Specific Rules**: Different entry criteria per session
3. **Confidence Modulation**: Adjust confidence based on session characteristics
4. **Time-of-Day Filters**: Avoid common traps (pre-London chop, NY reversals, Asia thin liquidity)

## Session Characteristics

### London Session (08:00-16:00 GMT)
**Strengths:**
- Highest liquidity for FX pairs
- Clean trend continuation
- Breakouts tend to hold
- Best for EURUSD, GBPUSD, XAUUSD

**Rules:**
- ✅ Prefer trend-pullback and breakout strategies
- ✅ Require ADX ≥ 20 for trend trades
- ✅ Volume confirmation (volume_z ≥ 0)
- ✅ Spread must be < 20% ATR
- ✅ +10 confidence bonus if BOS detected on M15/M30
- ❌ Avoid first 30 minutes (chop/false breakouts)
- ❌ Reduce range-fade confidence by 20 unless strong S/R

### New York Session (13:00-21:00 GMT)
**Strengths:**
- High volatility
- Strong reversals possible
- Institutional money flow
- Good for XAUUSD, BTCUSD, US indices

**Challenges:**
- Mid-session reversals common
- Fakeouts at London close overlap (16:00 GMT)

**Rules:**
- ✅ Range-fade allowed IF bb_width ≥ threshold (e.g., 0.03) AND no red news ±45m
- ✅ Breakout requires volume_z ≥ 1.0 OR confirmed BOS
- ✅ Confluence with DXY/10Y yields adds +10 confidence
- ❌ −10 confidence if spread spike detected (>30% ATR)
- ❌ −10 confidence if price is mid-range (no edge)
- ❌ Avoid trend continuation near 16:00 GMT (London close overlap)

### Asia Session (22:00-08:00 GMT)
**Strengths:**
- Defined ranges
- Mean reversion works well
- Good for range-bound strategies

**Challenges:**
- Thin liquidity
- Prone to stop hunts
- Breakouts often fail

**Rules:**
- ✅ Range-fade PREFERRED strategy
- ✅ Require well-defined range edges + wick rejections
- ✅ Pending orders with short expiries (30-60m)
- ❌ −15 confidence for breakouts without volume_z ≥ 1.5
- ❌ −20 confidence for trend continuation unless Donchian breach + high volume
- ❌ Avoid BTCUSD unless clear range with volume

## Implementation Components

### 1. Session Detector (`infra/session_detector.py`)
```python
class SessionDetector:
    """
    Detect current trading session with overlap handling.
    """
    def detect_session(current_time_utc: datetime) -> SessionInfo
    def get_session_profile(session: str, symbol: str) -> SessionProfile
    def is_session_transition(current_time_utc: datetime) -> bool
```

**SessionInfo:**
- Primary session (London/NY/Asia)
- Overlap status (London-NY, Asia-open)
- Minutes into session
- Session strength (0.0-1.0, lower during transitions)

**SessionProfile:**
- Preferred strategies
- Required filters
- Confidence adjustments
- Risk multipliers

### 2. Session Rules Engine (`infra/session_rules.py`)
```python
class SessionRules:
    """
    Apply session-specific rules to trade recommendations.
    """
    def apply_session_filters(trade_spec, session_info, features) -> FilterResult
    def adjust_confidence(confidence, session_info, features, strategy) -> float
    def get_session_guardrails(session_info, symbol) -> Dict
```

**Filter Results:**
- Pass/Fail
- Skip reasons (e.g., "Asia breakout without volume")
- Confidence adjustment
- Risk size multiplier

### 3. Integration Points

#### A. Prompt Router
Enhance template selection with session bias:
```python
# In prompt_router.py _select_template()
if context.session == TradingSession.ASIA:
    if context.regime == MarketRegime.RANGE:
        priority_boost = 0.2  # Prefer range templates in Asia
    elif strategy == "breakout":
        confidence_penalty = 0.15  # Discourage breakouts
```

#### B. Prompt Templates
Add session-specific instructions to v2 templates:
```
Enhanced Analysis Rules:
...
- SESSION GUIDANCE:
  * London: Prefer trend continuation, require ADX≥20, volume confirmation
  * NY: Careful of reversals, require volume≥1.0 for breakouts, check DXY confluence
  * Asia: Range-fade preferred, discourage breakouts without volume≥1.5
  * Reduce confidence by [X] if conditions not met
```

#### C. Validator
Add session checks to business rules:
```python
# In prompt_validator.py _validate_session_news()
session = context.session
strategy = trade_spec.strategy

if session == "ASIA" and strategy == "breakout":
    if not (volume_z >= 1.5 and donchian_breach):
        errors.append("Asia breakouts require volume≥1.5 and Donchian breach")
```

## Confidence Adjustment Table

| Scenario | Session | Strategy | Adjustment |
|----------|---------|----------|------------|
| Strong trend, ADX≥25 | London | Trend-pullback | +10 |
| BOS detected M15+ | London | Trend-continuation | +10 |
| Range width < 0.03 | NY | Range-fade | −20 |
| Mid-range entry | NY | Any | −10 |
| Spread spike >30% ATR | NY | Any | −10 |
| Breakout, volume<1.5 | Asia | Breakout | −20 |
| Range edges + wicks | Asia | Range-fade | +10 |
| Trend without Donchian | Asia | Trend | −15 |

## Deliverables

1. **Code:**
   - `infra/session_detector.py` - Session detection & profiles
   - `infra/session_rules.py` - Rule engine
   - Enhanced `infra/prompt_router.py` - Session-aware template selection
   - Enhanced `infra/prompt_templates.py` - Session guidance in templates
   - Enhanced `infra/prompt_validator.py` - Session rule validation

2. **Tests:**
   - `tests/test_session_detector.py` - Session detection accuracy
   - `tests/test_session_rules.py` - Rule application
   - `tests/test_session_integration.py` - End-to-end session filtering

3. **Documentation:**
   - Session playbook reference
   - Integration guide
   - Performance benchmarks by session

## Success Metrics
- Session detection 100% accurate
- Confidence adjustments applied consistently
- Skip rate increases for low-probability session scenarios
- Win rate improvement per session (vs. baseline)

## Next Steps After Phase 4.2
- Phase 4.3: Cross-Asset Confluence
- Phase 4.4: Execution Upgrades (OCO, Adaptive TP)
- Phase 4.5: Portfolio Discipline

