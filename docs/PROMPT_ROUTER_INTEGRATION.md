# Prompt Router Integration Guide

## Overview

The **Prompt Router** system is now fully integrated into TelegramMoneyBot.v7, providing regime-aware, strategy-specific trade analysis with enhanced validation and analytics.

## What Changed

### 1. **Intelligent Trade Analysis**
- Trade recommendations now route through strategy-specific templates based on market conditions
- Three template families: **Trend Pullback**, **Range Fade**, **Breakout**
- Each template has versioned rules (currently using v2 for all strategies)

### 2. **Enhanced Validation**
- Multi-layer validation: schema → business rules → costs → session/news
- Auto-repair for common issues (missing confidence, invalid RR)
- EV-aware cost gating (20% of planned RR threshold)
- Session-aware routing (Asia prefers range, London/NY prefers breakout)

### 3. **Rich Analytics Metadata**
Every trade decision now includes:
- `router_used`: Boolean flag indicating if router was used
- `template_version`: Which template version generated the trade (e.g., "trend_pullback_v2")
- `session_tag`: Trading session (asia, london, ny, overlap, closed)
- `decision_tags`: Array of tags for dashboard grouping (e.g., `["session=NY", "template=breakout_v2", "regime=VOLATILE"]`)
- `validation_score`: Quality score 0-100 for the recommendation

## Configuration

### Enable/Disable Router

Add to your `.env` file:

```env
# Enable Prompt Router (default: 1/true)
USE_PROMPT_ROUTER=1

# Disable to use original LLM logic
# USE_PROMPT_ROUTER=0
```

The router is **enabled by default**. When disabled, the bot falls back to the original multi-sample LLM approach.

## How It Works

### Trade Flow

1. **User requests trade** (`/trade XAUUSD`)
2. **Feature Builder** gathers multi-timeframe indicators, patterns, structure
3. **Prompt Router**:
   - Classifies market regime (TREND / RANGE / VOLATILE / UNKNOWN)
   - Detects trading session (ASIA / LONDON / NY / OVERLAP / CLOSED)
   - Selects appropriate template (or skips if no match)
   - Validates template health
   - Generates regime-specific prompt with features + guardrails
   - Calls LLM (or simulation in test mode)
   - Validates response (schema, geometry, costs, session rules)
   - Returns `DecisionOutcome` with `TradeSpec` or skip reasons
4. **OpenAI Service** converts `TradeSpec` to bot's recommendation format
5. **Journal** stores metadata for analytics
6. **User** receives recommendation with execute buttons

### Regime Classification

**TREND** (recommended: stop orders)
- ADX > 25 on H1 or M15
- EMA aligned (20 > 50 > 200 or inverse)
- Cross-timeframe consensus

**RANGE** (recommended: limit orders)
- ADX < 20
- Bollinger Band width low (<0.02)
- Flat EMAs, repeated rejections at range edges

**VOLATILE** (recommended: OCO or stop orders with volume confirmation)
- High ATR ratio (>1.3× baseline)
- Breakout bars, volume spikes
- Wide Bollinger Bands

**UNKNOWN** → Skip (avoids bias toward trend in choppy conditions)

### Session-Aware Routing

- **Asia Session**: Prefers range fade (thin liquidity)
- **London/NY Sessions**: Prefers trend pullback and breakout (high volume)
- **Overlap**: Optimal for all strategies
- **Closed**: Still processes but with tighter constraints

### Validation Rules

**Geometry & Structure**
- Stop orders: entry must be beyond current price
- Limit orders: entry must be into pullbacks
- SL floor: ≥0.4×ATR
- Optional: SL beyond nearest swing

**Cost Gating**
- EV threshold: (spread + slippage) / RR ≤ 20%
- Single-source error message (no duplicate cost warnings)

**RR Bounds** (template-specific)
- Trend Pullback: 1.8–3.0
- Range Fade: 1.5–2.5
- Breakout: 2.0–4.0

**Session & News**
- News blackout → skip
- Asia breakout requires volume confirmation
- NY range fade requires wide range

## Analytics & Observability

### Skip Reasons
All skip decisions include structured reasons:
- Template health failures
- Validation errors (geometry, costs, RR)
- Missing data warnings (M5.close, atr_14)
- News blackout, session constraints

### Decision Tags
Every decision includes tags for effortless filtering:
```json
["session=NY", "template=breakout_v2", "regime=VOLATILE"]
```

Use these for:
- Dashboard filtering (show only London trades)
- Performance analysis (win rate by template version)
- Template A/B testing

### Validation Score
0-100 quality score for each recommendation:
- +2 bonus: SL ≥ 0.5×ATR (excellent distance)
- +2 bonus: costs < 10% of RR (excellent efficiency)
- -2 penalty: SL 0.4–0.5×ATR (legal but fragile)
- -5 penalty: RR > 5.0 (unrealistic)

## Testing

### CI Guard Test
Run the comprehensive test suite:

```bash
python test_template_ci_guard.py
```

**Tests**:
1. Template health validation (v2 templates)
2. Router simulation (TREND/RANGE/UNKNOWN regimes)
3. Decision tags presence
4. Skip behavior validation

### Integration Test
```bash
python -c "
from infra.prompt_router import create_prompt_router
router = create_prompt_router()
router.enable_simulation_mode()

outcome = router.route_and_analyze('XAUUSD', {
    'M5': {'close': 2650.0, 'atr_14': 5.0, 'adx': 28.0},
    'H1': {'adx': 30.0},
    'cross_tf': {'trend_consensus': 'up'}
}, {'news_block': False})

print(f'Status: {outcome.status}')
print(f'Template: {outcome.template_name}')
print(f'Tags: {outcome.decision_tags}')
"
```

## Fallback Behavior

The router has multiple safety nets:

1. **Router Disabled** (`USE_PROMPT_ROUTER=0`): Uses original multi-sample LLM logic
2. **Router Fails** (exception): Logs warning, falls back to original logic
3. **Router Skips** (no valid trade): Logged with skip reasons, fallback runs
4. **Validation Fails**: Auto-repair attempted once; else skip with reasons

**Result**: No trade is ever "lost" due to router issues—fallback ensures continuity.

## Troubleshooting

### Router Always Skips
- Check `skip_reasons` in logs or journal
- Common causes:
  - `UNKNOWN` regime (weak indicators, mixed signals)
  - News blackout active
  - Spread too high (>20% of RR)
  - Missing M5 data (close, atr_14)

### Router Not Being Used
- Verify `USE_PROMPT_ROUTER=1` in `.env`
- Check logs for "Prompt router disabled" message
- Ensure `infra/prompt_router.py` exists and compiles

### Validation Score Always Low
- Low scores (<50) indicate quality issues:
  - RR too low or too high
  - SL distance fragile (<0.5×ATR)
  - High costs relative to RR
- Review validation rules in `infra/prompt_validator.py`

## Template Versions

Currently active templates (all v2):
- `trend_pullback_v2`: EMA alignment, pullback to 20/50, stop orders, RR 1.8–3.0
- `range_fade_v2`: Range edges, wick rejections, limit orders, RR 1.5–2.5
- `breakout_v2`: Volume confirmation, Donchian break, stop orders, RR 2.0–4.0

To switch versions, edit `active_versions` in `infra/prompt_templates.py`:
```python
self.active_versions: Dict[str, str] = {
    "trend_pullback": "v2",  # or "v1"
    "range_fade": "v2",
    "breakout": "v2",
}
```

## Next Steps

### Phase 3 (Optional Enhancements)
- Real regime classifier (replace stub)
- Real session detector (replace stub)
- Custom templates for specific symbols (XAUUSD, BTCUSD)
- Template performance dashboard
- A/B testing framework

### Phase 4 (Advanced)
- Multi-symbol portfolio-aware routing
- Dynamic template selection based on journal performance
- Reinforcement learning for template weights

## Support

For issues or questions:
1. Check logs for detailed router messages
2. Run CI guard test to verify template health
3. Enable debug logging: `logging.getLogger("infra.prompt_router").setLevel(logging.DEBUG)`
4. Review `skip_reasons` in journal for specific failure modes

---

**Status**: ✅ Production Ready  
**Version**: Phase 2 Complete  
**Last Updated**: 2025-10-02

