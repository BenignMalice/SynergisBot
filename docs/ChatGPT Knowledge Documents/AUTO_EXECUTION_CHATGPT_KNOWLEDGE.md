# Auto Execution System - ChatGPT Knowledge Guide

## Overview
The Auto Execution System allows ChatGPT to create conditional trade plans that automatically execute when specific market conditions are met. This system monitors MT5 market data and executes trades without manual intervention.

## Hierarchical Trend Analysis

### Primary Trend Determination
- **Primary Trend** = H4 + H1 analysis only (locked)
- Lower timeframes (M30/M15/M5) cannot override primary trend
- Primary trend determines "Market Bias"
- **Trend Stability**: STABLE (3 bars confirmed), UNSTABLE (mixed signals), INSUFFICIENT_DATA (< 3 bars)
- Check `primary_trend`, `trend_strength`, and `trend_stability` fields in market data

### Dynamic Volatility Weighting
- **Volatility Regime**: LOW (range), MEDIUM (normal), HIGH (expansion/FOMC/BTC spikes)
- **Weight Adjustments**:
  - HIGH volatility: H4=50%, H1=30%, M15=6%, M5=2% (reduces lower TF noise)
  - MEDIUM volatility: H4=40%, H1=25%, M15=12%, M5=8% (balanced)
  - LOW volatility: H4=30%, H1=25%, M15=20%, M5=20% (more balanced for range markets)
- System automatically adjusts weights based on volatility state
- Check `volatility_regime` and `volatility_weights` fields in market data

### Trend Memory Buffer
- Maintains 3-bar rolling memory per timeframe
- Prevents rapid bias flipping in choppy markets (especially BTC)
- Only shifts bias when 3 consecutive bars confirm change
- Stability status indicates confidence in trend direction

### Trade Opportunities
- Lower timeframe signals are "Trade Opportunities" (not market bias)
- Counter-trend opportunities must be labeled with risk warnings
- Counter-trend trades have confidence capped at 60%
- Check `trade_opportunity_type` and `risk_level` fields in market data

### Counter-Trend Risk Adjustments
- **STRONG trend** (counter-trend):
  - SL multiplier: 1.25x (widen by 25%)
  - TP multiplier: 0.50x (halve TP distance)
  - Max R:R: 0.5:1
  - Risk Level: HIGH
- **MODERATE trend** (counter-trend):
  - SL multiplier: 1.15x (widen by 15%)
  - TP multiplier: 0.75x (reduce by 25%)
  - Max R:R: 0.75:1
  - Risk Level: MEDIUM
- **WEAK trend** (counter-trend):
  - No adjustments
  - Max R:R: 1:1
  - Risk Level: LOW
- Check `risk_adjustments` field for specific multipliers when creating plans
- Check `counter_trend_warning` field (True = counter-trend trade)

### Enhanced Plan Validation
- Auto-execution system automatically rejects counter-trend plans if:
  - Confluence score < 60%
  - Liquidity state contradicts plan direction in strong trends
  - Risk adjustments not properly applied
  - R:R ratio exceeds `max_risk_rr` limit
- Always validate plan direction against primary trend before creating auto-execution plans
- When creating counter-trend auto-execution plans:
  - Check `risk_adjustments` field for required SL/TP multipliers
  - Apply multipliers to stop_loss and take_profit values
  - Ensure R:R ratio doesn't exceed `max_risk_rr` limit
  - Add note explaining it's a counter-trend trade with HIGH RISK

### Terminology Rules
- ❌ NEVER: "Moderate Bullish" when H4/H1 are bearish
- ✅ CORRECT: "Counter-Trend BUY Setup (within Downtrend)"
- Always include primary trend context in labels
- Mention volatility regime if HIGH: "High volatility - reduced lower TF weight"
- Mention stability if UNSTABLE: "Trend UNSTABLE - mixed signals, wait for confirmation"

**🚨 CRITICAL REQUIREMENT: You MUST include appropriate conditions in trade plans that match the strategy type!**

**🚨 CRITICAL FOR BTC TRADES: Order flow conditions can now be used in ALL BTC plans!**

- For BTCUSD analysis, recommendations, and auto-execution plans: ALWAYS use `moneybot.btc_order_flow_metrics` to check Delta Volume, CVD, CVD Divergence, Absorption Zones, and Buy/Sell Pressure
- BTC order flow metrics are AUTOMATICALLY included in `moneybot.analyse_symbol_full` for BTCUSD - check the "BTC ORDER FLOW METRICS" section in the analysis summary
- When creating BTC auto-execution plans, you can now use order flow conditions:
  - **`delta_positive: true`** - Wait for positive delta volume (buying pressure)
  - **`delta_negative: true`** - Wait for negative delta volume (selling pressure)
  - **`cvd_rising: true`** - Wait for CVD (Cumulative Volume Delta) to be rising
  - **`cvd_falling: true`** - Wait for CVD to be falling
  - **`cvd_div_bear: true`** or **`Cvd Div Bear: true`** - Wait for bearish CVD divergence (price making higher highs, CVD making lower highs - selling pressure increasing)
  - **`cvd_div_bull: true`** or **`Cvd Div Bull: true`** - Wait for bullish CVD divergence (price making lower lows, CVD making higher lows - buying pressure increasing)
  - **`delta_divergence_bull: true`** or **`Delta Divergence Bull: true`** - Wait for bullish delta divergence (price down, delta up - buying pressure increasing despite price drop)
  - **`delta_divergence_bear: true`** or **`Delta Divergence Bear: true`** - Wait for bearish delta divergence (price up, delta down - selling pressure increasing despite price rise)
  - **`avoid_absorption_zones: true`** - Block execution if entry price is in an absorption zone (use when you want to avoid zones)
  - **`absorption_zone_detected: true`** or **`Absorption Zone Detected: true`** - Wait for absorption zone to be detected at entry price (use when you WANT to enter at an absorption zone)
- These conditions work for **ANY BTC plan type** (not just order_block plans)
- **Example 1 (Basic):** `{"delta_positive": true, "cvd_rising": true, "price_near": 100000, "tolerance": 200}` - Wait for buying pressure AND rising CVD before entry
- **Example 2 (Divergence):** `{"cvd_div_bear": true, "price_near": 100000, "tolerance": 200}` - Wait for bearish CVD divergence (reversal signal)
- **Example 3 (Absorption):** `{"absorption_zone_detected": true, "delta_positive": true, "price_near": 100000, "tolerance": 200}` - Enter at absorption zone with buying pressure
- When creating BTC auto-execution plans, consider order flow signals:
  * Strong buy pressure (Delta > 0, CVD rising) → Use `delta_positive: true` and `cvd_rising: true`
  * Strong sell pressure (Delta < 0, CVD falling) → Use `delta_negative: true` and `cvd_falling: true`
  * CVD Divergence detected → Use `cvd_div_bear: true` or `cvd_div_bull: true` to wait for divergence confirmation
  * Delta Divergence detected → Use `delta_divergence_bull: true` or `delta_divergence_bear: true` to catch early reversals
  * Absorption zones near entry → Use `avoid_absorption_zones: true` to block execution in zones, OR `absorption_zone_detected: true` to enter at zones

**📊 MTF Alignment Conditions (NEW):**

- **`mtf_alignment_score: 60`** - Minimum multi-timeframe alignment score (0-100, default 60)
  - Higher scores = better alignment across timeframes
  - Use for trend continuation strategies
  - Example: `{"mtf_alignment_score": 70, "price_near": 100000, "tolerance": 200}`

- **`h4_bias: "BULLISH"`** or **`h4_bias: "BEARISH"`** - Require specific H4 bias
  - Use when H4 trend is critical for strategy
  - Example: `{"h4_bias": "BULLISH", "price_near": 100000, "tolerance": 200}`

- **`h1_bias: "BULLISH"`** or **`h1_bias: "BEARISH"`** - Require specific H1 bias
  - Use when H1 trend is critical for strategy
  - Example: `{"h1_bias": "BEARISH", "price_near": 100000, "tolerance": 200}`

- **When to use:** Trend continuation strategies, breakout strategies, structure-based trades
- **Note:** These conditions use cached MTF analysis (no API call during execution)

**🚨 CRITICAL: Always check Enhanced Data Fields before creating auto-execution plans!**
- Enhanced Data Fields are AUTOMATICALLY included in `moneybot.analyse_symbol_full` - check the "📊 ENHANCED DATA FIELDS ⭐ NEW" section in the analysis summary
- **Symbol Constraints:** ALWAYS check `symbol_constraints` before creating plans:
  * Check `max_concurrent_trades_for_symbol` - Don't create plan if already at limit
  * Check `banned_strategies` - Don't use banned strategies
  * Check `allowed_strategies` - Only use allowed strategies (if list not empty)
  * Check `max_total_risk_on_symbol_pct` - Ensure total risk doesn't exceed limit
- **Session Risk:** Check `session_risk` before creating plans:
  * If `in_rollover_window: true` → Wait until after rollover
  * If `in_news_lock: true` → DO NOT create plan, wait for news to pass
  * If `event_proximity_hours < 2` → Reduce position size or wait
  * If `risk_level: "high"` or `"critical"` → Avoid creating new plans
- **Execution Context:** Check `execution_context` for entry timing:
  * If `execution_quality_score < 60` → Wait for better execution conditions
  * If `spread_quality: "poor"` → Wait for spread to tighten
- **HTF Levels:** Use `htf_levels` for entry/stop placement:
  * Use `previous_week_high/low` or `previous_day_high/low` as key levels
  * If price in `premium_zone` → Favor SELL setups, if in `discount_zone` → Favor BUY setups
- **Structure Summary:** Use `structure_summary` for strategy selection:
  * "balanced_range" → Use range trading strategies
  * "trend_channel" → Use trend-following strategies
  * "breakout" → Use breakout strategies
  * If `has_liquidity_sweep: true` → Consider reversal strategies
- **Strategy Stats:** Check `strategy_stats` to validate strategy:
  * If `win_rate_pct < 50%` → Consider alternative strategy
  * If `avg_rr_ratio < 1.0` → Strategy may not be profitable
  * If `confidence_level: "low"` → Use with caution
- **Correlation Context:** Use `correlation_context` to validate bias:
  * If `conflict_detected: true` → Reduced confidence, mention mixed signals
  * Check `dominant_driver` to understand what's driving price action

### ⚠️ CRITICAL: Enhanced Data Fields Integration Examples

**MANDATORY:** You MUST integrate enhanced data fields into your analysis and recommendations, NOT just display them.

#### Example: Proper Enhanced Data Fields Integration

**BEFORE (Incorrect - Just Displaying):**
```
📊 ENHANCED DATA FIELDS ⭐ NEW
🚫 Execution Quality: POOR - Spread elevated
🏗️ Structure: Accumulation, Near Range High
⚙️ Constraints: Max trades: 1, Max risk: 2.0%

🎯 CONFLUENCE VERDICT
⚠️ CONFLICTING SIGNALS
Risk Level: HIGH

📈 LAYERED RECOMMENDATIONS
SCALP: ⚪ WAIT
```

**AFTER (Correct - Integrated):**
```
📊 ENHANCED DATA FIELDS ⭐ NEW
🚫 Execution Quality: POOR - Spread elevated
🏗️ Structure: Accumulation, Near Range High
⚙️ Constraints: Max trades: 1, Max risk: 2.0%

⚠️ ENHANCED DATA FIELDS INTEGRATION:
- Execution Quality: POOR with elevated spread → Wider stops required (add 20% to SL), reduce position size
- Structure: Accumulation near range high → Range scalp strategy appropriate, expect breakout or reversal
- Constraints: Max 1 concurrent trade, max 2% risk → Position size limited to 0.01 lots (1% risk)
- Correlation Context: Unavailable → Cannot validate macro bias with intermarket analysis
- HTF Levels: Unavailable → Cannot assess premium/discount zones
- Session Risk: Unavailable → Cannot assess rollover/news lock status

🎯 CONFLUENCE VERDICT
⚠️ CONFLICTING SIGNALS
Risk Level: HIGH

📈 LAYERED RECOMMENDATIONS
SCALP: ⚪ WAIT
  - Execution quality POOR → Avoid entries until spread normalizes
  - Structure shows accumulation → Wait for breakout confirmation
  - Max 1 concurrent trade constraint → Cannot create new plan if existing plan active
```

**Key Integration Rules:**
1. ✅ Execution quality affects risk guidance (wider stops, reduced position size)
2. ✅ Structure summary informs strategy selection (range scalp, breakout, etc.)
3. ✅ Constraints are applied to position sizing (max trades, max risk)
4. ✅ Missing data is acknowledged (correlation, HTF, session risk)
5. ✅ All enhanced fields influence recommendations, not just displayed

**Common Mistakes:**
- ❌ Creating plans with only `price_near` when strategy requires `order_block`, `choch_bull`, or `price_above`
- ❌ Not matching conditions to the strategy described in reasoning/notes
- ❌ Plans execute prematurely because conditions don't match the intended strategy
- ❌ **Liquidity Sweep plans missing `liquidity_sweep: true`** - Will only check price, not detect sweeps
- ❌ **VWAP Bounce plans missing `vwap_deviation_direction`, `price_near`, or `tolerance`** - Will NOT trigger

**✅ Always match conditions to strategy:**

**🔍 Detection Signals for ChatGPT - How to Identify SMC Patterns:**

When analyzing market structure, look for these keywords/signals to identify SMC patterns:

**Order Block Detection:**
- Keywords: "strong support/resistance zone", "institutional level", "order block", "OB zone"
- Signals: Price rejecting from a zone, volume spike at zone, last candle before displacement
- Tech Dict Fields: `order_block_bull`, `order_block_bear`, `ob_strength`
- When detected: Price is near or retesting an institutional order block zone
- Conditions: `{"order_block": true, "order_block_type": "auto", "price_near": entry, "tolerance": X}`

**Breaker Block Detection:**
- Keywords: "failed order block", "flipped zone", "support became resistance", "resistance became support", "broken order block"
- Signals: Price broke through an order block, then returned to test the flipped zone
- Tech Dict Fields: `breaker_block_bull`, `breaker_block_bear`, `ob_broken`, `price_retesting_breaker`
- When detected: Order block was broken and price is retesting the flipped level
- Conditions: `{"breaker_block": true, "price_near": entry, "tolerance": X}`
- **⚠️ IMPORTANT:** `ob_broken` and `price_retesting_breaker` are detection results from `DetectionSystemManager().get_breaker_block()` - they are checked dynamically by the system, NOT stored in conditions. Only `breaker_block: true` is required in conditions.

**Fair Value Gap (FVG) Detection:**
- Keywords: "imbalance", "fair value gap", "inefficiency", "FVG", "gap in price action"
- Signals: Three-candle pattern with gap, price filling the gap, continuation after gap
- Tech Dict Fields: `fvg_bull`, `fvg_bear`, `fvg_filled_pct`, `fvg_strength`
- When detected: Price is filling or has filled 50-75% of a fair value gap zone
- Conditions: `{"fvg_bull": true, "fvg_filled_pct": 0.5-0.75, "choch_bull": true, "price_near": entry, "tolerance": X}`

**Market Structure Shift (MSS) Detection:**
- Keywords: "market structure shift", "trend reversal confirmed", "structure break", "MSS", "break of structure with pullback"
- Signals: Break of swing high/low, followed by pullback to break level, stronger than CHOCH
- Tech Dict Fields: `mss_bull`, `mss_bear`, `mss_level`, `pullback_to_mss`
- When detected: Market structure has shifted and price is pulling back to confirm the shift
- Conditions: `{"mss_bull": true, "pullback_to_mss": true, "price_near": entry, "tolerance": X}` or `{"mss_bear": true, ...}`

**Mitigation Block Detection:**
- Keywords: "last candle before break", "mitigation block", "smart money exit zone", "structure break zone"
- Signals: Last bullish/bearish candle before structure break, often with FVG nearby
- Tech Dict Fields: `mitigation_block_bull`, `mitigation_block_bear`, `structure_broken`, `fvg_present`
- When detected: Last candle before structure break, often combined with FVG
- Conditions: `{"mitigation_block_bull": true, "structure_broken": true, "price_near": entry, "tolerance": X}`

**Inducement Reversal Detection:**
- Keywords: "liquidity grab", "stop hunt", "liquidity sweep", "rejection from liquidity zone", "inducement"
- Signals: Price sweeps liquidity above/below key level, then rejects back into structure
- Tech Dict Fields: `liquidity_grab_bull`, `liquidity_grab_bear`, `rejection_detected`, `order_block_present`, `fvg_present`
- When detected: Liquidity was grabbed and price rejected, with OB/FVG confluence
- Conditions: `{"liquidity_grab_bull": true, "rejection_detected": true, "order_block": true, "price_near": entry, "tolerance": X}`

**Premium/Discount Array Detection:**
- Keywords: "premium zone", "discount zone", "Fibonacci retracement", "value zone", "0.618 fib", "0.786 fib"
- Signals: Price in discount zone (0.62-0.79 fib) for longs, premium zone (0.21-0.38 fib) for shorts
- Tech Dict Fields: `fib_levels`, `price_in_discount`, `price_in_premium`
- When detected: Price is in optimal value zone based on Fibonacci retracement
- Conditions: `{"price_in_discount": true, "price_near": entry, "tolerance": X}` or `{"price_in_premium": true, ...}`

**Session Liquidity Run Detection:**
- Keywords: "Asian session high/low", "session liquidity", "London sweeps Asian levels", "session breakout"
- Signals: Asian session high/low being swept during London session, followed by reversal
- Tech Dict Fields: `asian_session_high`, `asian_session_low`, `london_session_active`, `sweep_detected`, `reversal_structure`
- When detected: London session is targeting Asian session liquidity levels
- Conditions: `{"asian_session_high": true, "london_session_active": true, "sweep_detected": true, "reversal_structure": true, "price_near": entry, "tolerance": X}`

**Kill Zone Detection:**
- Keywords: "London open", "NY open", "high volatility window", "kill zone", "session open volatility"
- Signals: London Open (02:00-05:00 EST) or NY Open (08:00-11:00 EST) with volatility spike
- Tech Dict Fields: `session`, `kill_zone_active`, `volatility_spike`
- When detected: High volatility window during session opens
- Conditions: `{"kill_zone_active": true, "volatility_spike": true, "price_near": entry, "tolerance": X}`

**Other Strategies:**
- **CHOCH/BOS strategies → `{"choch_bull": true, "timeframe": "M5", "price_near": entry, "tolerance": value}` or `{"choch_bear": true, "timeframe": "M5", "price_near": entry, "tolerance": value}`** ⚠️ **CRITICAL: Always include price_near + tolerance for CHOCH plans!**
- **Breakout strategies → `{"price_above": entry, "price_near": entry, "tolerance": value}` or `{"price_below": entry, "price_near": entry, "tolerance": value}`** ⚠️ **CRITICAL: For breakout strategies, ALWAYS include price_near + tolerance ALONGSIDE price_above/price_below for tighter execution control!**
- Rejection Wick strategies → `{"rejection_wick": true, "timeframe": "M5", "price_near": entry, "tolerance": value}`
- **Liquidity Sweep strategies → `{"liquidity_sweep": true, "price_below": entry, "timeframe": "M5"}`**
- **VWAP Bounce/Fade strategies → `{"vwap_deviation": true, "vwap_deviation_direction": "below", "price_near": entry, "tolerance": value}`**

## System Architecture
- **Database**: `data/auto_execution.db` (SQLite)
- **Monitoring**: Runs every 30 seconds via background thread
- **Integration**: Started automatically with `chatgpt_bot.py`
- **Notifications**: Discord webhook notifications on execution
- **Web Interface**: View plans at `http://localhost:8010/auto-execution/view`
- **M1 Microstructure Integration** ⭐ NEW - Enhanced condition validation with M1 microstructure analysis
- **Plan Updates** ⭐ NEW - Update existing pending plans when market conditions change

## M1 Microstructure Enhancement ⭐ NEW

### Overview

M1 microstructure analysis enhances all auto-execution plans with:
- **3-candle CHOCH/BOS confirmation** - Reduces false triggers by 50%+
- **Dynamic threshold adaptation** - Adjusts confluence requirements based on symbol, session, and ATR ratio (sensitivity reduced by 10% for smoother adjustments)
- **Session-aware parameters** - Adapts to market volatility by session
- **Asset personality validation** - Symbol-specific behavior patterns
- **Real-time signal learning** - System learns from trade outcomes

**Recent Updates (November 2025):**
- M1 confidence threshold: **60%** (reduced from 70% for more permissive execution)
- Dynamic threshold sensitivity: **Reduced by 10%** (vol_weight and sess_weight values reduced)

### CHOCH Plans

M1 microstructure enhances CHOCH plan triggering:

- **3-candle confirmation** reduces false triggers by 50%+
- **CHOCH + BOS combo** requirement for high-confidence signals
- **Confidence weighting** (threshold: 60%) prevents premature execution
- **Dynamic threshold** adapts to market conditions (symbol, session, ATR ratio)
- **Expected improvement:** 50%+ reduction in false CHOCH triggers

### Rejection Wick Plans

M1 microstructure validates rejection wicks:

- **Authenticity validation** filters out fake dojis
- **Wick ratio analysis** confirms genuine rejection signals
- **Order block confirmation** enhances entry precision
- **Expected improvement:** Elimination of fake engulfing triggers

### Order Block Plans ⭐ NEW

M1 microstructure provides comprehensive order block detection and validation:

- **10-parameter validation checklist** ensures only high-quality institutional OBs trigger execution
- **M1-M5 cross-timeframe validation** confirms HTF alignment
- **Anchor candle identification** confirms correct OB origin
- **Displacement/structure shift** (mandatory) ensures genuine institutional activity
- **FVG detection** confirms imbalance after displacement
- **Volume spike confirmation** validates institutional participation
- **Liquidity grab detection** enhances OB reliability
- **Session context validation** prioritizes OBs during high-volatility sessions
- **Freshness check** prevents duplicate alerts for same OB
- **VWAP + liquidity confluence** confirms zone quality
- **Expected improvement:** 70%+ reduction in false OB triggers, precise entry zones

### Range Scalp Plans

M1 microstructure improves range scalping:

- **Order blocks** provide precise entry zones
- **FVGs** enhance entry confirmation
- **Liquidity zones** improve stop-loss placement (1.5-2 ATR sharper)
- **Dynamic threshold** adapts confluence requirements
- **Expected improvement:** 25% improvement in scalp accuracy

### Micro-Scalp Plans ⭐ NEW

Micro-scalp plans are ultra-short-term trades targeting small, quick moves:

- **4-Layer Validation System:**
  1. **Pre-Trade Filters** (hard blocks): Volatility (ATR(1), M1 range), Spread limits
  2. **Location Filter**: Must be at "EDGE" (VWAP band, session high/low, OB zone, liquidity cluster)
  3. **Candle Signal Checklist**: Primary trigger (≥1) + Secondary confluence (≥1)
  4. **Confluence Score**: Numeric filter (≥5 to trade, ≥7 for A+ setup)

- **Symbol-Specific Rules (BROKER-AWARE VALIDATION):**
  - **Base Ranges** (used when broker allows):
    - **XAUUSD**: SL distance $0.50-$1.20, TP distance $1.00-$2.50
    - **BTCUSD**: SL distance $5-$10, TP distance $10-$25
  - **Broker-Aware Adjustment**: The system automatically checks broker minimum stop distance requirements. If broker requires larger minimums (e.g., $100 for BTCUSD), limits are adjusted to broker-compatible ranges (e.g., $100-$300) while keeping micro-scalps relatively tight (up to 3x broker minimum).
  - **Symbols**: Only BTCUSDc and XAUUSDc supported
  - **⚠️ CRITICAL**: Calculate SL/TP distances: SL distance = |entry_price - stop_loss|, TP distance = |take_profit - entry_price|
  - **⚠️ CRITICAL: R:R Ratio Requirements:**
    - **Minimum R:R:** 1.5:1 (system will REJECT plans with lower R:R)
    - **Backwards R:R:** System will REJECT plans where TP < SL
    - **ChatGPT MUST ensure:** TP distance >= 1.5x SL distance
    - **Example:** 
      - Entry: 4500, SL: 4480 (20 points), TP: 4540 (40 points) ✅ R:R = 2.0:1
      - Entry: 4500, SL: 4480 (20 points), TP: 4510 (10 points) ❌ R:R = 0.5:1 (REJECTED)
    - **Configurable:** Can specify `"min_rr_ratio": 2.0` in conditions for stricter requirements
    - **Cost Consideration:** System also checks that spread+slippage < 20% of R:R
  - **Validation**: Plans with SL/TP outside broker-aware ranges will be REJECTED with error messages indicating broker requirements
  - **Example Rejection**: "Micro-scalp SL distance 115.60 exceeds maximum 300.00 for BTCUSDc. Broker minimum: 100.00. Micro-scalps require tight SL/TP."

- **Primary Triggers:**
  - Long wick trap
  - Micro liquidity sweep
  - VWAP tap + rejection
  - Strong engulfing candle

- **Secondary Confluence:**
  - OB retest
  - Fresh micro-CHOCH
  - Strong session momentum
  - Increasing volume

- **Monitoring**: Every 10-15 seconds for fast execution
- **Instant Exit**: Adverse candle detection (micro-interrupt)
- **Trailing Stop**: Optional, activates after +0.5R
- **Cool-Off Lock**: 30-second cooldown after exit
- **Expected improvement:** Ultra-fast execution with high precision for small moves

### General Auto-Execution

M1 microstructure improves all auto-execution plans:

- **Structure validation** confirms setup quality
- **Volatility state** prevents entry during dead zones
- **Momentum quality** filters out choppy conditions
- **Trend alignment** confirms higher timeframe bias
- **Session context** adapts aggressiveness to market hours
- **Asset personality** validates symbol-specific behavior
- **Dynamic thresholds** prevent over-triggering in choppy markets

## Available Tools

### 1. `moneybot.create_auto_trade_plan`
Creates a general conditional trade plan.

**Parameters:**
- `symbol` (string): Trading symbol (e.g., "BTCUSD", "EURUSD")
- `direction` (string): "BUY" or "SELL"
- `entry` (number): Entry price
- `stop_loss` (number): Stop loss price
- `take_profit` (number): Take profit price
- `volume` (number, optional): Position size (default: 0.01)
- `conditions` (object, **REQUIRED**): Market conditions to monitor (see Condition Types below). **⚠️ IMPORTANT: If you mention validation thresholds (min_confluence, min_validation_score, risk_filters) in your reasoning, you MUST include them in the conditions dict so they are saved and displayed.**
- `strategy_type` (string, **RECOMMENDED**): Strategy type for Universal Dynamic SL/TP Manager. Options: `"breakout_ib_volatility_trap"`, `"trend_continuation_pullback"`, `"liquidity_sweep_reversal"`, `"order_block_rejection"`, `"mean_reversion_range_scalp"`, `"breaker_block"`, `"market_structure_shift"`, `"fvg_retracement"`, `"mitigation_block"`, `"inducement_reversal"`, `"premium_discount_array"`, `"session_liquidity_run"`, `"kill_zone"`. If provided, enables advanced dynamic stop loss and take profit management based on strategy, symbol, and session. If omitted, trade uses Intelligent Exit Manager instead.
- `expires_hours` (number, optional): Plan expiry in hours (default: 24)
- `reasoning` (string, optional): Plan description

**🚨 CRITICAL: You MUST include appropriate conditions based on the strategy type!**

**Condition Mapping by Strategy Type:**
- **Order Block strategies** (OB Reversal, OB Continuation, OB Trap, Order Block Rejection) → MUST include `"order_block": true, "price_near": entry, "tolerance": X`
- **CHOCH/BOS strategies** (Breakout, Structure Break, Trend Continuation) → MUST include `"choch_bull": true, "price_near": entry, "tolerance": X` or `"choch_bear": true, "price_near": entry, "tolerance": X` or `"price_above": entry, "price_near": entry, "tolerance": X` or `"price_below": entry, "price_near": entry, "tolerance": X`
- **Rejection Wick strategies** (Wick Rejection, Pin Bar, Reversal) → MUST include `"rejection_wick": true, "price_near": entry, "tolerance": X`
- **Breakout strategies** (Inside Bar Breakout, Volatility Trap, Range Breakout) → MUST include `"price_above": entry, "price_near": entry, "tolerance": X` or `"price_below": entry, "price_near": entry, "tolerance": X` ⚠️ **CRITICAL: For breakout strategies, ALWAYS include price_near + tolerance ALONGSIDE price_above/price_below for tighter execution control!**
- **Combined strategies** → Include ALL relevant conditions (e.g., `{"order_block": true, "choch_bull": true, "price_near": entry, "tolerance": X}`)

**⚠️ CRITICAL RULES FOR price_above/price_below AND price_near:**
1. **NEVER include both price_above AND price_below in the same plan** - they are contradictory and will prevent execution!
2. **price_near MUST always match the entry_price** (NOT midpoint, NOT a different level):
   - For plans with `price_above`: `price_near = entry_price` (same value)
   - For plans with `price_below`: `price_near = entry_price` (same value)
   - For independent BUY/SELL plans: BUY plan uses `price_near = entry_price`, SELL plan uses `price_near = entry_price`
3. **Always include price_near + tolerance** alongside price_above/price_below for tighter execution control

**⚠️ If you don't include proper conditions, the plan will only execute when price reaches entry (price_near), which may not match the intended strategy!**
**⚠️ ALWAYS include `price_near` with `tolerance` alongside directional conditions (`price_above`/`price_below`) to ensure execution happens at the correct price level!**

**⭐ RECOMMENDED: Include `strategy_type` parameter for Universal Dynamic SL/TP Manager:**

**⚠️ CRITICAL: Strategy selection must match market conditions - DO NOT default to breakouts!**

## 🎯 Session & Symbol Strategy Guide

**⚠️ CRITICAL: Strategies adapt automatically based on symbol type and trading session. Understanding these adaptations helps you select the best strategy for current market conditions.**

### 📊 Session Restrictions

Some strategies are **only available** in specific sessions:

| Strategy | Allowed Sessions | Notes |
|----------|-----------------|-------|
| **kill_zone** | LONDON, NEWYORK only | Requires high volatility during session opens |
| **session_liquidity_run** | LONDON, NEWYORK only | Targets Asian session levels during London/NY |
| **All other SMC strategies** | ASIA, LONDON, NEWYORK, WEEKEND, CRYPTO | Available in all sessions |

**🚨 Important:** If you try to create a plan for `kill_zone` or `session_liquidity_run` during ASIA session, the system will reject it. Always check the current session before selecting these strategies.

### 💰 Symbol-Specific SL/TP Adjustments

The system automatically adjusts Stop Loss and Take Profit multipliers based on symbol characteristics:

#### **BTCUSD Adjustments:**
- **Wider Stop Losses:** 1.0-1.3x ATR (vs 0.8-1.0x for other symbols)
- **Higher Take Profits:** 1.8-2.7x ATR (vs 1.5-2.0x for other symbols)
- **Reason:** Higher volatility requires wider stops, but also allows larger targets

#### **XAUUSD Adjustments:**
- **Tighter Stop Losses:** 0.8-1.0x ATR (standard)
- **Moderate Take Profits:** 1.6-2.5x ATR (standard)
- **Reason:** More predictable price action allows tighter risk management

#### **Example Strategy Adjustments:**

**Order Block Rejection:**
- **BTCUSD:** SL 1.2x ATR, TP 1.8x ATR
- **XAUUSD:** SL 1.0x ATR, TP 1.6x ATR

**Breaker Block:**
- **BTCUSD:** SL 1.2x ATR, TP 2.2x ATR
- **XAUUSD:** SL 1.0x ATR, TP 2.0x ATR

**Market Structure Shift:**
- **BTCUSD:** SL 1.3x ATR, TP 2.7x ATR
- **XAUUSD:** SL 1.2x ATR, TP 2.5x ATR

**💡 Tip:** When creating plans, the system automatically applies these adjustments. You don't need to manually calculate them, but be aware that BTCUSD plans will have wider stops and higher targets.

### ⏰ Session-Specific R:R Floors

Each session has different minimum Risk:Reward requirements:

| Session | R:R Floor | Strategy Example |
|---------|-----------|-------------------|
| **ASIA** | 1.25 (lowest) | `order_block_rejection`: R:R 1.25 |
| **LONDON** | 1.4 (moderate) | `order_block_rejection`: R:R 1.4 |
| **NEWYORK** | 1.45 (highest) | `order_block_rejection`: R:R 1.45 |

**Why Different R:R Floors?**
- **ASIA:** Lower volatility, tighter ranges → Lower R:R acceptable
- **LONDON:** High liquidity, clean trends → Moderate R:R required
- **NEWYORK:** Highest volatility, reversals common → Higher R:R required for safety

**🚨 Important:** Plans with R:R below the session floor will be **rejected**. Always ensure your calculated R:R meets the session requirement.

### 🎯 Session Preferences (Strategy Selection Guidance)

While all strategies can work in any allowed session, some sessions favor certain strategies:

#### **LONDON Session (08:00-16:00 UTC):**
- ✅ **Preferred:** Trend continuation, breakouts, order blocks
- ⚠️ **Discouraged:** Range fade (low probability in trending markets)
- **Characteristics:** High liquidity, clean trends, strong breakouts
- **Best Strategies:** `order_block_rejection`, `breaker_block`, `market_structure_shift`, `fvg_retracement`

#### **NEWYORK Session (13:00-21:00 UTC):**
- ✅ **Preferred:** Breakouts, range fade (if conditions met)
- ⚠️ **Neutral:** All strategies viable with caution
- **Characteristics:** High volatility, reversals common, institutional flow
- **Best Strategies:** `breaker_block`, `inducement_reversal`, `session_liquidity_run`, `kill_zone`

#### **ASIA Session (00:00-08:00 UTC):**
- ✅ **Preferred:** Range fade, mean reversion
- ⚠️ **Discouraged:** Breakouts, trend continuation (low probability)
- **Characteristics:** Thin liquidity, defined ranges, mean reversion
- **Best Strategies:** `fvg_retracement`, `premium_discount_array`, `order_block_rejection` (at range edges)

**💡 Tip:** These are preferences, not hard rules. If market structure strongly supports a "discouraged" strategy, it can still work. But prefer "preferred" strategies when multiple options are available.

### 📈 Regime-Specific Adjustments

Strategies adapt their TP multipliers based on market regime:

| Regime | TP Multiplier Adjustment | Example |
|--------|-------------------------|---------|
| **TREND** | Higher TP (1.8-2.7x ATR) | `order_block_rejection`: TP 2.0x ATR in TREND |
| **RANGE** | Lower TP (1.2-1.8x ATR) | `order_block_rejection`: TP 1.2x ATR in RANGE |
| **VOLATILE** | Varies by strategy | `market_structure_shift`: TP 2.3x ATR in VOLATILE |

**Why Different TP Multipliers?**
- **TREND:** Price can run further → Higher TP targets
- **RANGE:** Price bounces between boundaries → Lower TP targets
- **VOLATILE:** Depends on strategy type and volatility characteristics

### 🔄 Strategy-Specific Session Adaptations

#### **Order Block Rejection:**
- **Sessions:** All (ASIA, LONDON, NEWYORK, WEEKEND, CRYPTO)
- **R:R Floors:** ASIA 1.25, LONDON 1.4, NEWYORK 1.45
- **Best For:** LONDON/NY (high liquidity, clean structure)
- **Symbol Adjustments:** BTCUSD wider stops, XAUUSD tighter stops

#### **Breaker Block:**
- **Sessions:** All (ASIA, LONDON, NEWYORK, WEEKEND, CRYPTO)
- **R:R Floor:** 1.3 (base), no session overrides
- **Best For:** LONDON/NY (failed OB retests more reliable)
- **Symbol Adjustments:** BTCUSD 1.2x SL / 2.2x TP, XAUUSD 1.0x SL / 2.0x TP

#### **Market Structure Shift (MSS):**
- **Sessions:** All (ASIA, LONDON, NEWYORK, WEEKEND, CRYPTO)
- **Regimes:** TREND, VOLATILE only (not RANGE)
- **R:R Floor:** 1.5 (highest base requirement)
- **Best For:** LONDON/NY (structure breaks more reliable)
- **Symbol Adjustments:** BTCUSD 1.3x SL / 2.7x TP, XAUUSD 1.2x SL / 2.5x TP

#### **FVG Retracement:**
- **Sessions:** All (ASIA, LONDON, NEWYORK, WEEKEND, CRYPTO)
- **Regimes:** All (TREND, RANGE, VOLATILE)
- **R:R Floor:** 1.3 (base)
- **Best For:** All sessions (works in any market condition)
- **Symbol Adjustments:** BTCUSD 1.0x SL / 1.8x TP, XAUUSD 0.8x SL / 1.6x TP

#### **Mitigation Block:**
- **Sessions:** All (ASIA, LONDON, NEWYORK, WEEKEND, CRYPTO)
- **Regimes:** All (TREND, RANGE, VOLATILE)
- **R:R Floor:** 1.3 (base)
- **Best For:** LONDON/NY (structure breaks more common)
- **Symbol Adjustments:** BTCUSD 1.2x SL / 2.0x TP, XAUUSD 1.0x SL / 1.8x TP

#### **Inducement Reversal:**
- **Sessions:** All (ASIA, LONDON, NEWYORK, WEEKEND, CRYPTO)
- **Regimes:** All (TREND, RANGE, VOLATILE)
- **R:R Floor:** 1.3 (base)
- **Best For:** LONDON/NY (liquidity sweeps more reliable)
- **Symbol Adjustments:** BTCUSD 1.2x SL / 2.0x TP, XAUUSD 1.0x SL / 1.8x TP

#### **Premium/Discount Array:**
- **Sessions:** All (ASIA, LONDON, NEWYORK, WEEKEND, CRYPTO)
- **Regimes:** RANGE only (requires defined range)
- **R:R Floor:** 1.3 (base)
- **Best For:** ASIA (range-bound markets)
- **Symbol Adjustments:** BTCUSD 1.0x SL / 2.0x TP, XAUUSD 0.9x SL / 1.8x TP

#### **Kill Zone:**
- **Sessions:** LONDON, NEWYORK only ⚠️
- **Regimes:** TREND, VOLATILE only
- **R:R Floors:** LONDON 1.4, NEWYORK 1.45
- **Best For:** Session opens (first 2-3 hours)
- **Symbol Adjustments:** BTCUSD 1.0x SL / 2.0x TP, XAUUSD 0.9x SL / 1.8x TP

#### **Session Liquidity Run:**
- **Sessions:** LONDON, NEWYORK only ⚠️
- **Regimes:** All (TREND, RANGE, VOLATILE)
- **R:R Floors:** LONDON 1.4, NEWYORK 1.45
- **Best For:** London/NY targeting Asian session levels
- **Symbol Adjustments:** BTCUSD 1.2x SL / 2.0x TP, XAUUSD 1.0x SL / 1.8x TP

### 📋 Quick Reference: Strategy Selection by Context

**When analyzing a symbol, consider:**

1. **Current Session?**
   - ASIA → Prefer range/mean reversion strategies
   - LONDON → Prefer trend/breakout strategies
   - NEWYORK → All strategies viable, prefer breakouts/reversals

2. **Current Regime?**
   - TREND → Higher TP targets, prefer continuation strategies
   - RANGE → Lower TP targets, prefer reversal strategies
   - VOLATILE → Strategy-specific adjustments

3. **Symbol Type?**
   - BTCUSD → Expect wider stops (1.2-1.3x ATR), higher targets (1.8-2.7x ATR)
   - XAUUSD → Expect tighter stops (0.8-1.0x ATR), moderate targets (1.6-2.5x ATR)

4. **Session Restrictions?**
   - `kill_zone` and `session_liquidity_run` → Only LONDON/NY
   - All others → Available in all sessions

**💡 Best Practice:** When creating auto-execution plans, mention in your reasoning which session/regime/symbol adaptations you're considering. This helps users understand why you selected a specific strategy.

---

**Complete SMC Strategy Priority Hierarchy (Auto-Selection):**

🥇 **TIER 1: Highest Confluence (Institutional Footprints)**

1. **Order Block Rejection** → `strategy_type: "order_block_rejection"`
   - **Use when:** Institutional order blocks detected (order_block_bull/order_block_bear in analysis)
   - **Priority:** HIGHEST - Always select when OB detected
   - **Best for:** High-probability reversal trades with institutional support
   - **Conditions:** `{"order_block": true, "order_block_type": "auto", "price_near": entry, "tolerance": X}`

2. **Breaker Block** → `strategy_type: "breaker_block"`
   - **Use when:** Price breaks through OB, returns to flip zone (failed order block)
   - **Priority:** HIGHEST - Higher probability than regular OB
   - **Best for:** Reversal trades at flipped support/resistance
   - **Conditions:** `{"breaker_block": true, "price_near": entry, "tolerance": X}`
   - **⚠️ IMPORTANT:** `ob_broken` and `price_retesting_breaker` are detection results from `DetectionSystemManager().get_breaker_block()` - they are checked dynamically by the system, NOT stored in conditions. Only `breaker_block: true` is required in conditions.

3. **Market Structure Shift (MSS)** → `strategy_type: "market_structure_shift"`
   - **Use when:** Break of high/low + pullback confirmation
   - **Priority:** HIGHEST - Stronger than CHOCH, confirms trend change
   - **Best for:** Trend change trades with structure confirmation
   - **Conditions:** `{"mss_bull": true, "pullback_to_mss": true, "price_near": entry, "tolerance": X}` or `{"mss_bear": true, ...}`

🥈 **TIER 2: High Confluence (Smart Money Patterns)**

4. **Fair Value Gap (FVG) Retracement** → `strategy_type: "fvg_retracement"`
   - **Use when:** Price fills 50-75% of FVG zone, best after CHOCH/BOS
   - **Priority:** HIGH - Strong institutional footprint
   - **Best for:** Continuation trades after structure break
   - **Conditions:** `{"fvg_bull": true, "fvg_filled_pct": 0.5-0.75, "choch_bull": true, "price_near": entry, "tolerance": X}`

5. **Mitigation Block** → `strategy_type: "mitigation_block"`
   - **Use when:** Last bullish/bearish candle before structure break, often with FVG
   - **Priority:** HIGH - Smart money exit/entry zone
   - **Best for:** Reversal trades at structure break zones
   - **Conditions:** `{"mitigation_block_bull": true, "structure_broken": true, "price_near": entry, "tolerance": X}`

6. **Inducement + Reversal** → `strategy_type: "inducement_reversal"`
   - **Use when:** Liquidity grab above/below key level + rejection + OB/FVG confluence
   - **Priority:** HIGH - Combine with OB/FVG for maximum confluence
   - **Best for:** Reversal trades after liquidity grab
   - **Conditions:** `{"liquidity_grab_bull": true, "rejection_detected": true, "order_block": true, "price_near": entry, "tolerance": X}`

🥉 **TIER 3: Medium-High Confluence**

7. **Liquidity Sweep Reversal** → `strategy_type: "liquidity_sweep_reversal"`
   - **Use when:** Price sweeps liquidity zones (PDH/PDL, equal highs/lows), stop hunt detected, reversal signals present
   - **Priority:** MEDIUM-HIGH - Select when sweep detected (if no Tier 1/2)
   - **Best for:** Reversal trades after liquidity grab, mean reversion setups
   - **Conditions:** `{"liquidity_sweep": true, "price_near": entry, "tolerance": X}`

8. **Session Liquidity Run** → `strategy_type: "session_liquidity_run"`
   - **Use when:** Asian session highs/lows during London, after sweep + reversal
   - **Priority:** MEDIUM-HIGH - Session-specific high-probability setups
   - **Best for:** Reversal trades targeting session liquidity
   - **Conditions:** `{"asian_session_high": true, "london_session_active": true, "sweep_detected": true, "reversal_structure": true, "price_near": entry, "tolerance": X}`

🏅 **TIER 4: Medium Confluence**

9. **Trend Continuation Pullback** → `strategy_type: "trend_continuation_pullback"`
   - **Use when:** Strong trend in place, pullback to support/resistance, CHOCH/BOS continuation signals
   - **Priority:** MEDIUM - Select when trend confirmed (if no Tier 1-3)
   - **Best for:** Trend-following trades, riding established momentum
   - **Conditions:** `{"choch_bull": true, "price_near": entry, "tolerance": X}` or `{"choch_bear": true, ...}`

10. **Premium/Discount Array** → `strategy_type: "premium_discount_array"`
    - **Use when:** Price in discount zone (0.62-0.79 fib) for longs, premium zone (0.21-0.38 fib) for shorts
    - **Priority:** MEDIUM - Value zone entries
    - **Best for:** Mean reversion trades at optimal value zones
    - **Conditions:** `{"price_in_discount": true, "price_near": entry, "tolerance": X}` or `{"price_in_premium": true, ...}`

⚪ **TIER 5: Lower Priority**

11. **Kill Zone Strategy** → `strategy_type: "kill_zone"`
    - **Use when:** London Open (02:00-05:00 EST) or NY Open (08:00-11:00 EST) with volatility
    - **Priority:** LOW - Time-based (lower than structure-based)
    - **Best for:** High volatility window trades
    - **Conditions:** `{"kill_zone_active": true, "volatility_spike": true, "price_near": entry, "tolerance": X}`

12. **Range Scalp/Mean Reversion** → `strategy_type: "mean_reversion_range_scalp"`
    - **Use when:** Price in range, bouncing between support/resistance, VWAP mean reversion signals
    - **Priority:** LOW - Select when range-bound (if no structure)
    - **Best for:** Range trading, scalping between levels
    - **Conditions:** `{"vwap_deviation": true, "vwap_deviation_direction": "below" or "above", "price_near": entry, "tolerance": X}`

13. **Breakout/Inside Bar/Volatility Trap** → `strategy_type: "breakout_ib_volatility_trap"`
    - **Use when:** Volatility compression confirmed (inside bars, Bollinger squeeze), range breakout imminent
    - **Priority:** LOWEST - Only use when NO structure detected (fallback only)
    - **Best for:** Range breakouts, volatility expansion trades
    - **⚠️ WARNING: Only use when volatility compression is confirmed - NOT a default choice!**
    - **⚠️ TIMING ISSUE: For BB_SQUEEZE alerts, by the time plan is created, squeeze may be over. Better to use `bb_expansion` or just `price_above`/`price_below` to wait for breakout!**
    - **Conditions:** `{"bb_squeeze": true, "price_above": entry, "price_near": entry, "tolerance": X}` or `{"inside_bar": true, ...}`

**Selection Rules (Priority Order):**
1. ✅ **TIER 1 FIRST** - Check for Order Blocks, Breaker Blocks, MSS
2. ✅ **TIER 2 SECOND** - Check for FVG, Mitigation Blocks, Inducement
3. ✅ **TIER 3 THIRD** - Check for Liquidity Sweeps, Session Runs
4. ✅ **TIER 4 FOURTH** - Check for Trend Pullbacks, Premium/Discount
5. ✅ **TIER 5 LAST** - Check for Kill Zone, Range Scalp
6. ⚠️ **IBVT AS LAST RESORT** - Only when NO structure detected (no OB, no sweep, no CHOCH/BOS, no FVG, no MSS, etc.)
- **Why include strategy_type?** Enables Universal Dynamic SL/TP Manager to automatically adjust stop loss and take profit based on:
  - Strategy-specific rules (breakouts trail differently than reversals)
  - Symbol-specific behavior (BTC vs XAU have different trailing logic)
  - Session-specific adjustments (London/NY vs Asia have different volatility)
- **If omitted:** Trade will use Intelligent Exit Manager instead (still functional, but less advanced SL/TP management)

**Alternative Parameters (Auto-Converted):**
- `trigger_type` (string, optional): Type of trigger - "structure", "rejection_wick", or "price"
- `trigger_value` (string, optional): Specific trigger value:
  - For `trigger_type: "structure"`: `"CHOCH_BULL"`, `"CHOCH_BEAR"`, `"BOS_BULL"`, `"BOS_BEAR"`
  - For `trigger_type: "rejection_wick"`: Any value (sets rejection_wick: true)
  - For `trigger_type: "price"`: `"ABOVE"`, `"BELOW"`, or any value (defaults to price_near)
- `timeframe` (string, optional): Timeframe for structure conditions (default: "M5")

**Note**: If both `conditions` and `trigger_type`/`trigger_value` are provided, `conditions` takes precedence.

### 2. `moneybot.create_choch_plan`
Creates a CHOCH (Change of Character) based trade plan.

**Parameters:**
- `symbol` (string): Trading symbol
- `direction` (string): "BUY" or "SELL"
- `entry` (number): Entry price
- `stop_loss` (number): Stop loss price
- `take_profit` (number): Take profit price
- `volume` (number, optional): Position size (default: 0.01)
- `choch_type` (string, optional): "bear" or "bull" (default: "bear")
- `price_tolerance` (number, optional): Price tolerance - **Auto-calculated if not provided**: BTCUSD=100.0, ETHUSD=10.0, XAUUSD=5.0, Forex=0.001
- `expires_hours` (number, optional): Plan expiry in hours (default: 24)
- `reasoning` (string, optional): Plan description

### 3. `moneybot.create_rejection_wick_plan`
Creates a rejection wick based trade plan.

**Parameters:**
- `symbol` (string): Trading symbol
- `direction` (string): "BUY" or "SELL"
- `entry` (number): Entry price
- `stop_loss` (number): Stop loss price
- `take_profit` (number): Take profit price
- `volume` (number, optional): Position size (default: 0.01)
- `price_tolerance` (number, optional): Price tolerance - **Auto-calculated if not provided**: BTCUSD=100.0, ETHUSD=10.0, XAUUSD=5.0, Forex=0.001
- `expires_hours` (number, optional): Plan expiry in hours (default: 24)
- `reasoning` (string, optional): Plan description

### 4. `moneybot.create_order_block_plan` ⭐ NEW
Creates an order block-based trade plan with comprehensive 10-parameter validation.

### 5. Batch Operations ⭐ NEW - Create/Update/Cancel Multiple Plans at Once

**⚠️ Bracket Trades Deprecated:**
Bracket trades are no longer supported. Instead, create two independent plans (one BUY, one SELL) with different conditions. Each plan monitors independently - if one executes, the other can still execute later if its conditions are met. This is more flexible than OCO (One Cancels Other) bracket trades.

#### 5.1 `moneybot.create_multiple_auto_plans`
Creates multiple auto-execution trade plans in a single operation.

**Parameters:**
- `plans` (array): Array of plan objects (maximum 20 plans per batch)
  - Each plan must specify `plan_type`: 'auto_trade', 'choch', 'rejection_wick', 'order_block', 'range_scalp', or 'micro_scalp'
  - Each plan includes standard parameters for its type (symbol, direction, entry_price, stop_loss, take_profit, volume, conditions, etc.)

**How It Works:**
- Creates multiple plans in a single operation
- Supports partial success - valid plans are created even if some fail validation
- Returns detailed results per plan with success/failure status
- Reduces permission prompts and improves efficiency

**Use Cases:**
- User requests multiple plans (e.g., "create 3 buy plans", "give me plans for different strategies")
- User wants both BUY and SELL plans (replaces bracket trades)
- Creating multiple plans with different conditions or strategies

**Example:**
```json
{
  "plans": [
    {
      "plan_type": "auto_trade",
      "symbol": "BTCUSDc",
      "direction": "BUY",
      "entry_price": 50000.0,
      "stop_loss": 49500.0,
      "take_profit": 51000.0,
      "volume": 0.01,
      "conditions": {
        "price_near": 50000.0,
        "tolerance": 100.0,
        "choch_bull": true,
        "timeframe": "M5"
      },
      "expires_hours": 24,
      "notes": "First plan"
    },
    {
      "plan_type": "choch",
      "symbol": "XAUUSDc",
      "direction": "SELL",
      "entry_price": 2000.0,
      "stop_loss": 2010.0,
      "take_profit": 1980.0,
      "volume": 0.01,
      "choch_type": "bear",
      "expires_hours": 24,
      "notes": "Second plan"
    }
  ]
}
```

**Response Format:**
```json
{
  "summary": "Created 2 of 2 plans successfully",
  "data": {
    "total": 2,
    "successful": 2,
    "failed": 0,
    "results": [
      {
        "index": 0,
        "plan_id": "chatgpt_abc123",
        "plan_type": "auto_trade",
        "symbol": "BTCUSDc",
        "status": "success",
        "message": "Plan created successfully"
      },
      {
        "index": 1,
        "plan_id": "chatgpt_def456",
        "plan_type": "choch",
        "symbol": "XAUUSDc",
        "status": "success",
        "message": "Plan created successfully"
      }
    ]
  }
}
```

#### 5.2 `moneybot.update_multiple_auto_plans`
Updates multiple auto-execution trade plans in a single operation.

**Parameters:**
- `updates` (array): Array of update objects
  - Each update must include `plan_id` (required)
  - Each update can include any combination of: `entry_price`, `stop_loss`, `take_profit`, `volume`, `conditions`, `expires_hours`, `notes`

**How It Works:**
- Updates multiple plans in a single operation
- Supports partial success - valid updates are processed even if some fail
- Duplicate plan_ids are automatically deduplicated (keeps last update)
- Returns detailed results per plan with success/failure status
- Only pending plans can be updated (executed/cancelled/expired cannot be modified)

**Example:**
```json
{
  "updates": [
    {
      "plan_id": "chatgpt_abc123",
      "entry_price": 50100.0,
      "stop_loss": 49600.0
    },
    {
      "plan_id": "chatgpt_def456",
      "expires_hours": 48,
      "notes": "Extended expiration"
    }
  ]
}
```

#### 5.3 `moneybot.cancel_multiple_auto_plans`
Cancels multiple auto-execution trade plans in a single operation.

**Parameters:**
- `plan_ids` (array): Array of plan_id strings

**How It Works:**
- Cancels multiple plans in a single operation
- Provides idempotent behavior - cancelling already-cancelled or non-existent plans returns success (no error)
- Duplicate plan_ids are automatically deduplicated
- Returns detailed results per plan with success/failure status

**Example:**
```json
{
  "plan_ids": [
    "chatgpt_abc123",
    "chatgpt_def456",
    "chatgpt_ghi789"
  ]
}
```

**💡 Creating Two Independent Plans (Replaces Bracket Trades):**

Instead of bracket trades, create two independent plans using batch operations:

**Example - Creating BUY and SELL plans:**
```json
{
  "plans": [
    {
      "plan_type": "auto_trade",
      "symbol": "BTCUSDc",
      "direction": "BUY",
      "entry_price": 88000.0,
      "stop_loss": 87500.0,
      "take_profit": 89000.0,
      "volume": 0.01,
      "conditions": {
        "price_above": 88000.0,
        "price_near": 88000.0,
        "tolerance": 100.0,
        "choch_bull": true
      },
      "expires_hours": 24,
      "notes": "BUY plan for range breakout"
    },
    {
      "plan_type": "auto_trade",
      "symbol": "BTCUSDc",
      "direction": "SELL",
      "entry_price": 86400.0,
      "stop_loss": 87000.0,
      "take_profit": 85200.0,
      "volume": 0.01,
      "conditions": {
        "price_below": 86400.0,
        "price_near": 86400.0,
        "tolerance": 100.0,
        "choch_bear": true
      },
      "expires_hours": 24,
      "notes": "SELL plan for range breakout"
    }
  ]
}
```

**Benefits:**
- Each plan monitors independently
- If one executes, the other can still execute later if conditions are met
- More flexible than OCO bracket trades
- Can use batch operations to create both plans at once

### 6. `moneybot.create_order_block_plan`
Creates an order block-based trade plan with comprehensive 10-parameter validation.

**Parameters:**
- `symbol` (string): Trading symbol
- `direction` (string): "BUY" or "SELL"
- `entry` (number): Entry price (typically near expected OB zone)
- `stop_loss` (number): Stop loss price
- `take_profit` (number): Take profit price
- `volume` (number, optional): Position size (default: 0.01)
- `order_block_type` (string, optional): "bull" (bullish OB only), "bear" (bearish OB only), or "auto" (auto-detect based on plan direction). Default: "auto"
- `min_validation_score` (integer, optional): Minimum validation score (0-100). Default: 60. Only OBs with score >= this threshold will trigger execution.
- `price_tolerance` (number, optional): Price tolerance - **Auto-calculated if not provided**: BTCUSD=100.0, ETHUSD=10.0, XAUUSD=5.0, Forex=0.001
- `expires_hours` (number, optional): Plan expiry in hours (default: 24)
- `reasoning` (string, optional): Plan description

**10-Parameter Validation Checklist:**
The system validates order blocks using a comprehensive checklist:
1. **Anchor Candle Identification** - Confirms the correct candle (last down/up candle before displacement)
2. **Displacement/Structure Shift (Mandatory)** - Requires clear BOS/CHOCH after OB candle
3. **Imbalance/FVG Presence** - Checks for clear Fair Value Gap after displacement
4. **Volume Spike** - Volume on displacement > 1.2x recent average
5. **Liquidity Grab** - Optional but strong: sweep of swing high/low, stop run
6. **Session Context** - OBs strongest during London/NY Open or major news volatility
7. **Higher-Timeframe Alignment** - Checks if OB aligns with M5 trend and M5 BOS/CHOCH
8. **Structural Context** - Avoids OBs in wide consolidations/choppy ranges
9. **Order Block Freshness** - Fresh OBs are higher quality (price hasn't returned to zone)
10. **VWAP + Liquidity Confluence** - Checks if OB zone is near VWAP or significant liquidity zones

**⚠️ CRITICAL PRE-CREATION CHECKS:**
## Creating Auto-Execution Plans with Hierarchical Trend Analysis

### Pre-Plan Validation Checklist

Before creating any auto-execution plan, check:

1. **Primary Trend Alignment:**
   - Check `primary_trend` field in market data (BEARISH/BULLISH/NEUTRAL)
   - Check `trend_strength` field (STRONG/MODERATE/WEAK)
   - If plan direction contradicts primary trend → It's a counter-trend trade
   - Counter-trend trades require special risk adjustments (see below)

2. **Volatility Regime:**
   - Check `volatility_regime` field (LOW/MEDIUM/HIGH)
   - HIGH volatility: Lower timeframes have reduced weight, focus on H4/H1
   - LOW volatility: More balanced weights, range trading strategies work better

3. **Trend Stability:**
   - Check `trend_stability` field (STABLE/UNSTABLE/INSUFFICIENT_DATA)
   - UNSTABLE: Wait for 3-bar confirmation before creating trend-following plans
   - STABLE: Safe to create plans aligned with primary trend

4. **Trade Opportunity Type:**
   - Check `trade_opportunity_type` field (COUNTER_TREND_BUY/COUNTER_TREND_SELL/TREND_CONTINUATION_BUY/TREND_CONTINUATION_SELL/NONE)
   - If COUNTER_TREND: Apply risk adjustments (see below)
   - If TREND_CONTINUATION: Standard risk parameters apply

5. **Risk Adjustments (for Counter-Trend Trades):**
   - Check `risk_adjustments` field for required multipliers:
     - `sl_multiplier`: Multiply original SL distance by this (e.g., 1.25 = widen by 25%)
     - `tp_multiplier`: Multiply original TP distance by this (e.g., 0.50 = halve TP)
     - `max_risk_rr`: Maximum allowed R:R ratio (e.g., 0.5 = max 0.5:1 R:R)
   - Apply these adjustments when calculating stop_loss and take_profit values
   - Example: If original SL distance = 100 points, and sl_multiplier = 1.25:
     - For BUY: adjusted_sl = entry - (100 * 1.25) = entry - 125 points
     - For SELL: adjusted_sl = entry + (100 * 1.25) = entry + 125 points

### Counter-Trend Plan Creation Example

```python
# Market data shows:
# primary_trend = "BEARISH"
# trend_strength = "STRONG"
# trade_opportunity_type = "COUNTER_TREND_BUY"
# risk_adjustments = {"sl_multiplier": 1.25, "tp_multiplier": 0.50, "max_risk_rr": 0.5}

# Original plan:
entry = 85000
original_sl = 84500  # 500 points below
original_tp = 86000  # 1000 points above

# Calculate distances
sl_distance = abs(entry - original_sl)  # 500
tp_distance = abs(original_tp - entry)  # 1000

# Apply risk adjustments
adjusted_sl = entry - (sl_distance * 1.25)  # 85000 - 625 = 84375
adjusted_tp = entry + (tp_distance * 0.50)  # 85000 + 500 = 85500

# Verify R:R
new_sl_distance = abs(entry - adjusted_sl)  # 625
new_tp_distance = abs(adjusted_tp - entry)  # 500
rr_ratio = new_tp_distance / new_sl_distance  # 500/625 = 0.8:1

# Check if exceeds max R:R (0.5:1)
if rr_ratio > 0.5:
    # Adjust TP to meet max R:R requirement
    adjusted_tp = entry + (new_sl_distance * 0.5)  # 85000 + 312.5 = 85312.5

# Create plan with note
notes = "Counter-trend BUY in STRONG bearish trend (HIGH RISK). Risk adjustments applied: SL×1.25, TP×0.50, Max R:R=0.5:1"
```

### Plan Rejection Reasons

Plans will be automatically rejected if:
- Counter-trend with confluence < 60%
- Counter-trend with R:R > max_risk_rr
- Liquidity state contradicts plan in STRONG trends
- Missing required risk adjustments for counter-trend trades

Before creating OB plans, you MUST check:
1. **VWAP Deviation Check:**
   - Use `moneybot.analyse_symbol_full` to check current VWAP deviation
   - **If VWAP > 2.0σ extended** → **DO NOT create bullish OB plans** (system will block them anyway)
   - **If VWAP < -2.0σ extended** → **DO NOT create bearish OB plans** (system will block them anyway)
   - OB plans in overextended markets are likely to fail - wait for mean reversion first

2. **Session Timing Check:**
   - **DO NOT create plans within 30 minutes of session close** (London 13:00 UTC, NY 21:00 UTC, Overlap 16:00 UTC)
   - System will block execution near session end, but better to avoid creating low-probability plans
   - Prefer London/NY open periods (first 2-3 hours) for OB plans

3. **Order Flow Check (BTCUSD only):**
   - **ALWAYS use `moneybot.btc_order_flow_metrics` before creating BTCUSD OB plans**
   - **For BUY plans:** Only create if `delta > 0.25` AND `CVD rising` (buying pressure confirmed)
   - **For SELL plans:** Only create if `delta < -0.25` AND `CVD falling` (selling pressure confirmed)
   - System will validate order flow, but checking beforehand prevents wasted plan creation
   - Check absorption zones - avoid creating OB plans if entry is in an absorption zone

**Execution Flow:**
1. System monitors every 30 seconds
2. Fetches M1 data (200 candles) and analyzes microstructure
3. Detects order blocks matching the specified direction
4. Validates each OB using the 10-parameter checklist
5. Checks if validation score >= min_validation_score
6. Verifies entry price is near OB zone (if price_near condition exists)
7. When all conditions met → Trade executes automatically
8. Discord notification sent on execution

### 4. `moneybot.create_range_scalp_plan`
Creates a range scalping auto-execution plan that monitors confluence score and structure confirmation.

**Parameters:**
- `symbol` (string): Trading symbol (e.g., "BTCUSDc", "XAUUSDc")
- `direction` (string): "BUY" or "SELL"
- `entry` (number): Entry price for the range scalp
- `stop_loss` (number): Stop loss price
- `take_profit` (number): Take profit price
- `volume` (number, optional): Position size (default: 0.01)
- `min_confluence` (integer, optional): Minimum confluence score required
  - **Symbol-Specific Defaults**:
    - **BTCUSDc**: 75 (may accept slightly lower due to higher baseline volatility)
    - **XAUUSDc**: 80 (stricter for session-driven markets)
    - **Default**: 80
  - Range: 0-100
  - **Note**: BTC and XAU use different confluence calculation methods (see `ChatGPT_Knowledge_Confluence_Calculation.md`)
- `price_tolerance` (number, optional): Price tolerance for entry zone (auto-calculated if not provided)
  - BTCUSD: 100.0
  - ETHUSD: 10.0
  - XAUUSD: 5.0
  - Forex: 0.001
- `expires_hours` (number, optional): Plan expiry in hours (default: 8 for range scalping)
- `reasoning` (string, optional): Plan description

**What It Monitors:**
1. **Range Scalping Confluence Score** - Must reach >= min_confluence (default: 80)
   - Calculated using `moneybot.analyse_range_scalp_opportunity` internally
   - Structure (40pts) - Requires 3+ range touches
   - Location (35pts) - Price at edge (<0.5 ATR from boundary)
   - Confirmation (25pts) - RSI extreme OR rejection wick OR tape pressure
2. **Structure Confirmation** - CHOCH/BOS on M15 matching trade direction
   - **BUY requires**: M15 CHOCH Bull (reversal) **OR** BOS Bull (continuation)
     - CHOCH Bull: Price breaks above the **second-to-last** swing high (structure shift from bearish to bullish)
     - BOS Bull: Price breaks above the **last** swing high (trend continuation)
   - **SELL requires**: M15 CHOCH Bear (reversal) **OR** BOS Bear (continuation)
     - CHOCH Bear: Price breaks below the **second-to-last** swing low (structure shift from bullish to bearish)
     - BOS Bear: Price breaks below the **last** swing low (trend continuation)
   - **Note**: The system uses separate detection functions (`_detect_choch()` and `_detect_bos()`) to accurately identify both reversal and continuation patterns
3. **Price Near Entry** - Price within tolerance of entry zone

**When to Use:**
- User requests: "set alert for range scalping and make it auto-execute"
- User requests: "create auto-execution for range scalp"
- Range-bound market detected and user wants to wait for high-quality setup
- User wants confluence >= 80 before executing

**Example:**
```json
{
  "symbol": "BTCUSDc",
  "direction": "BUY",
  "entry": 105350.0,
  "stop_loss": 105100.0,
  "take_profit": 106100.0,
  "volume": 0.01,
  "min_confluence": 80,
  "expires_hours": 8,
  "reasoning": "Range scalping BUY at lower boundary - wait for confluence >= 80 and M15 structure confirmation"
}
```

**Execution Flow:**
1. System monitors every 30 seconds
2. Checks if price is within tolerance of entry
3. Runs range scalping analysis to calculate confluence score
4. Checks for M15 structure confirmation (CHOCH/BOS)
5. When all conditions met (confluence >= 80, structure confirmed, price near entry) → Trade executes automatically
6. Discord notification sent on execution

### 6. `moneybot.create_price_breakout_plan`
Creates a price breakout based trade plan.

**Parameters:**
- `symbol` (string): Trading symbol
- `direction` (string): "BUY" or "SELL"
- `entry` (number): Entry price
- `stop_loss` (number): Stop loss price
- `take_profit` (number): Take profit price
- `volume` (number, optional): Position size (default: 0.01)
- `breakout_type` (string, optional): "above" or "below" (default: "above")
- `expires_hours` (number, optional): Plan expiry in hours (default: 24)
- `reasoning` (string, optional): Plan description

### 7. `moneybot.cancel_auto_trade_plan`
Cancels an existing trade plan.

**Parameters:**
- `plan_id` (string): Plan ID to cancel

### 8. `moneybot.update_auto_plan` ⭐ NEW
Updates an existing trade plan. Only pending plans can be updated.

**Parameters:**
- `plan_id` (string, **🚨 REQUIRED**): Plan ID to update - **MANDATORY, must be provided**
- `entry_price` (number, optional): New entry price
- `stop_loss` (number, optional): New stop loss
- `take_profit` (number, optional): New take profit
- `volume` (number, optional): New volume
- `conditions` (object, optional): Conditions to update (merged with existing - new values override old ones)
- `expires_hours` (number, optional): New expiration time in hours
- `notes` (string, optional): Updated notes

**🚨 CRITICAL: plan_id is MANDATORY**
- **plan_id is REQUIRED** - you MUST include the plan_id (e.g., 'chatgpt_0ea79233') when calling this tool
- If you don't have the plan_id, first use `moneybot.get_auto_plan_status` to list all plans and find the correct plan_id
- The tool will return an error if plan_id is missing

**Important Notes:**
- Only **pending** plans can be updated (executed, cancelled, or expired plans cannot be modified)
- When updating `conditions`, new conditions are **merged** with existing ones (new values override old ones)
- You can update any combination of fields - only provide the fields you want to change
- Use this when market conditions change and you need to adjust plans for new prices, conditions, or expiration

**Example:**
```json
{
  "plan_id": "chatgpt_0ea79233",
  "entry_price": 84000.0,
  "conditions": {
    "price_near": 84000.0,
    "tolerance": 100.0
  },
  "notes": "Updated based on new market analysis"
}
```

### 9. `moneybot.get_auto_plan_status`
Gets status of trade plans. Can query by plan_id OR ticket number.

**Parameters:**
- `plan_id` (string, optional): Specific plan ID (e.g., "chatgpt_abc123")
- `ticket` (number, optional): MT5 position ticket number (e.g., 169674998)
- **Note**: Provide either `plan_id` OR `ticket`, not both. Omit both to get all plans.

**When User Provides Ticket Numbers:**
- If user gives you MT5 ticket numbers (e.g., "review ticket 169674998", "what plan created ticket 169674999"), use the `ticket` parameter
- The system automatically looks up the plan_id from the ticket number in the database
- Returns full plan details including:
  - Plan ID, symbol, direction, entry_price, stop_loss, take_profit
  - Status (pending/executed/cancelled/expired)
  - Conditions that triggered execution
  - Execution timestamp and ticket number
  - Notes and reasoning

**Example - Query by Ticket:**
```json
{
  "ticket": 169674998
}
```

**Example - Query by Plan ID:**
```json
{
  "plan_id": "chatgpt_abc123"
}
```

**Example - Get All Plans:**
```json
{}
```

**How Ticket-to-Plan Linking Works:**
1. When an auto-execution plan executes, the MT5 ticket number is stored in the database
2. The database links: `plan_id` ←→ `ticket` ←→ MT5 Position
3. Querying by ticket looks up the plan_id in the database and returns the full plan details

### 10. `moneybot.get_auto_execution_system_status`
Gets overall system status.

## Condition Types

**⚠️ CRITICAL: Plans MUST have at least one condition to execute automatically. Plans without conditions will be skipped.**

**🚨 MANDATORY: You MUST match conditions to the strategy described in reasoning/notes!**

**Strategy-to-Condition Mapping Guide:**

| Strategy Type | Required Conditions | Example |
|--------------|-------------------|---------|
| **Order Block** (OB Reversal, OB Continuation, OB Trap) | `"order_block": true` + `"order_block_type"` | `{"order_block": true, "order_block_type": "auto"}` |
| **CHOCH/BOS** (Breakout, Structure Break) | `"choch_bull"` or `"choch_bear"` + `"timeframe"` + `"price_near"` + `"tolerance"` | `{"choch_bull": true, "timeframe": "M5", "price_near": 83800, "tolerance": 100}` |
| **Rejection Wick** (Wick Rejection, Pin Bar) | `"rejection_wick": true` + `"timeframe"` + `"price_near"` + `"tolerance"` | `{"rejection_wick": true, "timeframe": "M5", "price_near": 83920, "tolerance": 100}` |
| **Liquidity Sweep** (Stop Hunt, Sweep Reversal) | `"liquidity_sweep": true` + `"price_below"` or `"price_above"` + `"timeframe"` | `{"liquidity_sweep": true, "price_below": 83890, "timeframe": "M5"}` |
| **VWAP Bounce/Fade** (Mean Reversion) | `"vwap_deviation": true` + `"vwap_deviation_direction"` + `"price_near"` + `"tolerance"` | `{"vwap_deviation": true, "vwap_deviation_direction": "below", "price_near": 83910, "tolerance": 100}` |
| **Breakout** (Inside Bar, Volatility Trap, Range Breakout) | `"price_above"` or `"price_below"` | `{"price_above": 91712}` |
| **Order Flow (BTC Only)** | `"delta_positive": true` OR `"delta_negative": true` OR `"cvd_rising": true` OR `"cvd_falling": true` | `{"delta_positive": true, "price_near": 100000, "tolerance": 200}` |
| **Absorption Zones (BTC Only)** | `"avoid_absorption_zones": true` | `{"avoid_absorption_zones": true, "price_near": 100000, "tolerance": 200}` |
| **MTF Alignment** | `"mtf_alignment_score": 60` (minimum score) | `{"mtf_alignment_score": 70, "price_near": 100000, "tolerance": 200}` |
| **H4/H1 Bias** | `"h4_bias": "BULLISH"` or `"h1_bias": "BEARISH"` | `{"h4_bias": "BULLISH", "price_near": 100000, "tolerance": 200}` |
| **Session Filtering (XAU)** | `"require_active_session": true` | `{"require_active_session": true, "price_near": 4500, "tolerance": 5}` |

**📋 Optional Validation Thresholds - Include in Conditions Dict When Specified:**

**⚠️ IMPORTANT: If you mention these thresholds in your reasoning/notes, you MUST include them in the `conditions` dict so they are saved and displayed correctly.**

These are optional validation thresholds that make plans more selective. If you specify them in your analysis, include them in the conditions dict:

1. **`min_validation_score`** (number, 0-100):
   - **Purpose**: Minimum validation score required for order block plans (default: 60 if not specified)
   - **When to include**: When you want stricter order block validation (e.g., "requires validation score ≥ 70")
   - **Example**: `{"order_block": true, "min_validation_score": 70, "price_near": entry, "tolerance": X}`
   - **Note**: System uses default 60 if not provided, but including it makes your plan requirements explicit

2. **`min_confluence`** or **`range_scalp_confluence`** (number, 0-100):
   - **Purpose**: Minimum confluence score required for range scalping plans (default: 80 if not specified)
   - **When to include**: When you specify a minimum confluence requirement (e.g., "requires confluence ≥ 75")
   - **Example**: `{"range_scalp_confluence": 75, "price_near": entry, "tolerance": X}`
   - **Note**: Use `range_scalp_confluence` for range scalping plans, or `min_confluence` for general plans

3. **`risk_filters`** (boolean):
   - **Purpose**: Indicates that risk filters are enabled (default: always enabled by system)
   - **When to include**: When you explicitly mention "risk filters enabled" in your analysis
   - **Example**: `{"price_above": entry, "risk_filters": true, "price_near": entry, "tolerance": X}`
   - **Note**: System always applies risk filters, but including this makes it explicit in the plan

**🚨 CRITICAL RULE: If you describe these thresholds in your reasoning/notes (e.g., "min_confluence ≥ 75", "validation score ≥ 70", "risk filters enabled"), you MUST include them in the `conditions` dict. Otherwise, they won't be saved to the database and won't appear on the webpage.**

## System-Wide Validations (Automatic - ChatGPT Should Ensure Plans Meet These)

**⚠️ CRITICAL: The system automatically validates these for ALL plans. ChatGPT should ensure plans meet these requirements to avoid rejection.**

### 1. R:R Ratio Validation (MANDATORY)
- **Minimum R:R:** 1.5:1 (default, configurable via `min_rr_ratio` in conditions)
- **Backwards R:R:** System will REJECT plans where TP < SL
- **ChatGPT Action:** Always ensure TP distance >= 1.5x SL distance
- **Example:** If SL = 20 points, TP must be >= 30 points away from entry
- **Condition:** Can specify `"min_rr_ratio": 2.0` for stricter requirements (default 1.5)
- **Calculation:** R:R = (TP distance) / (SL distance)
  - Entry: 4500, SL: 4480 (20 points), TP: 4540 (40 points) ✅ R:R = 2.0:1
  - Entry: 4500, SL: 4480 (20 points), TP: 4510 (10 points) ❌ R:R = 0.5:1 (REJECTED)

### 2. Session-Based Blocking (XAU Default, Strategy-Aware)
- **XAU Plans:** Default `require_active_session: true` (blocks Asian session 00:00-08:00 UTC)
- **BTC Plans:** Can optionally set `require_active_session: true` (blocks Asian session)
- **Asian Session Exception:** Certain strategies ARE allowed during Asian session:
  - ✅ `range_scalp`, `range_fade`, `mean_reversion` - Appropriate for range-bound Asian markets
  - ✅ `fvg_retracement`, `premium_discount_array` - Work well in low-liquidity sessions
  - ✅ `order_block_rejection` - At range edges
  - ❌ `breakout`, `trend_continuation`, `trend_pullback` - Blocked (low probability in Asian session)
- **ChatGPT Action:** 
  - For XAU plans: System automatically blocks Asian session for most strategies (low liquidity, high slippage)
  - **Exception:** Range/mean reversion strategies are automatically allowed in Asian session
  - To allow ALL strategies in Asian session: Explicitly set `"require_active_session": false`
  - For BTC plans: Include `"require_active_session": true` if you want to block Asian session (with same exceptions)

### 3. News Blackout Check (Automatic)
- **System Behavior:** Automatically blocks trades during high-impact news events
- **ChatGPT Action:** No action needed - system handles automatically
- **Note:** Plans will be blocked during news blackout windows (system checks `NewsService.is_blackout("macro")`)

### 4. Execution Quality Check (Automatic)
- **System Behavior:** Blocks trades if spread > 3x normal (XAU: 0.15%, BTC: 0.09%)
- **ChatGPT Action:** No action needed - system handles automatically
- **Note:** Wide spreads indicate poor execution quality - system will reject

### 5. Plan Staleness Validation (Warning Only)
- **System Behavior:** Logs warning if entry price moved > 2x tolerance from current price
- **ChatGPT Action:** Ensure entry prices are still valid when creating plans
- **Note:** Non-blocking (warning only), but indicates plan may need updating

### 6. Spread/Slippage Cost Validation (Automatic)
- **System Behavior:** Blocks trades if execution costs (spread + slippage) > 20% of R:R
- **ChatGPT Action:** Ensure R:R is sufficient to account for execution costs
- **Example:** If TP = 30 points, costs must be < 6 points (20% of 30)

### 7. ATR-Based Stop Validation (Optional)
- **System Behavior:** Validates SL/TP distances against ATR if `"atr_based_stops": true` in conditions
- **Requirements:**
  - BTC: SL >= 1.5 ATR, TP >= 3.0 ATR
  - XAU: SL >= 1.2 ATR, TP >= 2.5 ATR
- **ChatGPT Action:** Include `"atr_based_stops": true` when you want ATR-based validation
- **Note:** System will reject if SL < 0.5x ATR (immediate stop-out risk)

**Example with all thresholds:**
```json
{
  "price_above": 4216.38,
  "price_near": 4216.38,
  "tolerance": 2.0,
  "timeframe": "M15",
  "bb_expansion": true,
  "strategy_type": "breakout_ib_volatility_trap",
  "min_confluence": 75,
  "min_validation_score": 70,
  "risk_filters": true
}
```

## Immediate Execution with Universal SL/TP Manager

### `moneybot.execute_trade`

For immediate trade execution (when user says "place", "execute", "enter now", etc.), you can also enable Universal Dynamic SL/TP Manager by including the `strategy_type` parameter.

**Parameters:**
- `symbol` (string): Trading symbol (e.g., "BTCUSD", "XAUUSD")
- `direction` (string): "BUY" or "SELL"
- `entry` (number): Entry price
- `stop_loss` (number): Stop loss price
- `take_profit` (number): Take profit price
- `volume` (number, optional): Position size (default: auto-calculated)
- `strategy_type` (string, **RECOMMENDED**): Strategy type for Universal Dynamic SL/TP Manager. Options: `"breakout_ib_volatility_trap"`, `"trend_continuation_pullback"`, `"liquidity_sweep_reversal"`, `"order_block_rejection"`, `"mean_reversion_range_scalp"`, `"breaker_block"`, `"market_structure_shift"`, `"fvg_retracement"`, `"mitigation_block"`, `"inducement_reversal"`, `"premium_discount_array"`, `"session_liquidity_run"`, `"kill_zone"`. If provided, enables advanced dynamic stop loss and take profit management based on strategy, symbol, and session. If omitted, trade uses Intelligent Exit Manager instead.

**Example:**
```python
moneybot.execute_trade(
    symbol: "BTCUSDc",
    direction: "BUY",
    entry: 86000.0,
    stop_loss: 85800.0,
    take_profit: 86500.0,
    strategy_type: "breakout_ib_volatility_trap"  # Enables Universal Manager
)
```

**Why include strategy_type?**
- Enables Universal Dynamic SL/TP Manager for advanced stop loss and take profit management
- Strategy-specific trailing rules (breakouts trail differently than reversals)
- Symbol-specific behavior (BTC vs XAU have different trailing logic)
- Session-specific adjustments (London/NY vs Asia have different volatility)
- If omitted, trade will use Intelligent Exit Manager instead (still functional, but less advanced)
| **Combined** (e.g., OB + CHOCH) | Multiple conditions | `{"order_block": true, "choch_bull": true}` |

**⚠️ OPTIONAL Enhancement Conditions - Use ONLY When Market Conditions Warrant:**

**CRITICAL: These conditions are OPTIONAL and should NOT be added by default. They make plans more strict and can prevent execution. Only add them when market conditions specifically warrant stricter validation.**

**When to Use Optional Enhancements:**

1. **`m1_choch_bos_combo: true`** - ONLY for CHOCH plans when:
   - ✅ Market is showing clear M1 structure shifts
   - ✅ You want extra precision validation (adds +20-35% precision but may prevent execution)
   - ❌ DO NOT add if market is choppy or M1 structure is unclear
   - ❌ DO NOT add by default - only when M1 confirmation is critical

2. **`min_volatility: 0.5`** - ONLY when:
   - ✅ Market is in a low-volatility dead zone and you want to wait for expansion
   - ✅ You specifically want to avoid execution during compression
   - ❌ DO NOT add if volatility is already expanding or normal
   - ❌ DO NOT add by default - can prevent execution in normal market conditions

3. **`bb_width_threshold: 2.5`** - ONLY when:
   - ✅ You're specifically waiting for volatility expansion (Bollinger squeeze breakout)
   - ✅ Market is compressed and you want breakout confirmation
   - ❌ DO NOT add for normal breakout or trend continuation trades
   - ❌ DO NOT add by default - can prevent execution if BB width is narrow

**Default Approach (Recommended):**
- Start with SIMPLE conditions: `price_above`/`price_below`, `price_near`, `tolerance`, `choch_bull`/`choch_bear`, `order_block`, etc.
- Only add optional enhancements if market analysis specifically shows they're needed
- Remember: More conditions = Less likely to execute. Simpler is better for most trades.

**🚨 CRITICAL: Discord Alert Workflow - MANDATORY Analysis Before Creating Plans:**

**⚠️ MANDATORY 3-STEP WORKFLOW for Discord Alerts:**

**STEP 1: ANALYZE FIRST (MANDATORY)**
When you receive a Discord alert (e.g., "Analyze BTCUSDc M15 for RSI_DIV_BEAR alert..."), you MUST FIRST:
- ✅ Call `moneybot.analyse_symbol_full` for the symbol in the alert
- ✅ Validate the alert signal is still present/valid in current market data
- ✅ Check current market structure (CHOCH, BOS, trend direction, higher timeframes)
- ✅ Verify price is still near the alert level (may have moved)
- ✅ Assess confluence (macro context, session, volatility state, order flow)
- ✅ Check for conflicting signals (e.g., alert says SELL but structure is bullish)
- ✅ Determine if the setup is still valid for trading based on current conditions

**STEP 2: EVALUATE VALIDITY (MANDATORY)**
Only AFTER analysis, evaluate if the alert represents a valid trading setup:

**🚨 CRITICAL VALIDATION RULES:**
- ❌ **DO NOT create plan if analysis verdict is "AVOID"** → Analysis explicitly says to avoid trading
- ❌ **DO NOT create plan if confluence score is below 50/100 (Grade: F)** → Low confluence means setup is not valid
- ❌ **DO NOT create plan if analysis shows "CHOCH/BOS: ❌ None detected" but alert claims CHOCH/BOS** → Alert condition not confirmed in analysis
- ❌ **DO NOT create plan if alert claims RSI divergence but analysis does NOT detect RSI divergence** → If analysis shows RSI value (e.g., "RSI 56.7") with no divergence detected, but alert claims "RSI_DIV_BEAR", the analysis contradicts the alert - DO NOT create plan
- ❌ **DO NOT create plan if alert condition is NOT detected in analysis** → The analysis must independently confirm the alert condition exists. If the analysis does not detect the condition (e.g., no RSI divergence, no CHOCH/BOS), you MUST explain to the user that the alert condition was not confirmed and therefore you cannot create a plan. Do NOT create a plan "just in case" or "waiting for confirmation" - if the condition isn't present, the plan should not be created.

**✅ "WAIT" Verdict is OK for Auto-Execution Plans:**
- ⚠️ **"WAIT" verdict means "wait for conditions/price"** → This is EXACTLY what auto-execution plans do! They wait for conditions to be met before executing.
- ✅ **If analysis says "WAIT" but alert is valid** → You CAN create an auto-execution plan (the plan will wait for conditions)
- ✅ **If all recommendations say "WAIT" but alert is valid** → You CAN create an auto-execution plan (the plan will wait for conditions)

**❌ "AVOID" Verdict Blocks Plan Creation:**
- ❌ **DO NOT create plan if analysis verdict is "AVOID"** → Analysis explicitly says "AVOID" (don't trade), so do not create plan
- ❌ **DO NOT create plan if confluence score is "AVOID" or Grade: F with explicit "AVOID" message** → Analysis explicitly says to avoid trading

**❌ Other Blockers (Alert Invalid/Expired/Contradictory):**
- ❌ **DO NOT create plan if analysis shows "CHOCH/BOS: ❌ None detected" but alert claims CHOCH/BOS** → Alert condition not confirmed in analysis
- ❌ **DO NOT create plan if alert claims RSI divergence but analysis does NOT detect RSI divergence** → Example: Alert says "RSI_DIV_BEAR" but analysis shows "RSI 56.7" with no divergence detected. The analysis must independently confirm the divergence exists. If it doesn't, explain: "I cannot create a plan because my analysis did not detect RSI bearish divergence. The analysis shows RSI at 56.7 with no divergence pattern detected. The alert condition was not confirmed in my analysis, so I cannot validate this setup."
- ❌ **DO NOT create plan if alert condition is NOT detected in analysis** → The analysis must independently confirm the alert condition exists. Do NOT create a plan "just in case" or "waiting for confirmation" - if the condition isn't present, the plan should not be created.
- ❌ **DO NOT create plan if confluence score is below 50/100 (Grade: F)** → Low confluence means setup is not valid, even if Grade is not explicitly "AVOID"
- ❌ **If price has moved significantly** → DO NOT create plan, explain why (e.g., "Alert was at 91,569 but current price is 91,091 - moved 478 points, CHOCH already occurred")
- ❌ **If market structure contradicts alert direction** → DO NOT create plan, explain why (e.g., "Alert suggests SELL but H4 structure is BULLISH with H1 CONTINUATION")
- ❌ **If alert condition already passed** → DO NOT create plan, explain why (e.g., "RSI divergence already resolved, RSI now at 45", "CHOCH already occurred, price moved 478 points")
- ❌ **If analysis shows alert is invalid/expired** → DO NOT create plan, explain why

**💡 Key Distinction:**
- **"WAIT"** = "Wait for conditions/price" → ✅ OK for auto-execution plans (that's their purpose!)
- **"AVOID"** = "Don't trade" → ❌ Block plan creation

**STEP 3: CREATE PLAN (ONLY IF VALID)**
If analysis confirms the alert is valid:
- ✅ Use entry/SL/TP from analysis (NOT just from alert - prices may have changed)
- ✅ Adjust entry if price has moved (use current price from analysis, not alert price)
- ✅ Include required conditions matching the alert type (see Alert-to-Condition Mapping below)
- ✅ Include reasoning based on analysis findings (not just alert description)
- ✅ Set appropriate strategy_type based on analysis

**❌ WRONG WORKFLOW:**
- Immediately creating auto-execution plan without analysis
- Using alert price/levels without checking current market conditions
- Creating plan even when analysis shows alert is invalid

**✅ CORRECT WORKFLOW:**
1. Receive Discord alert → 2. Analyze symbol with `moneybot.analyse_symbol_full` → 3. Evaluate if alert is still valid → 4. Create plan (if valid) OR explain why not valid

**🚨 CRITICAL: Alert-to-Condition Mapping - REQUIRED Conditions:**
When creating plans from Discord alerts, you MUST include the alert-specific condition to validate the signal.

**⚠️ TIMING CRITICAL: Alert vs Plan Creation Timing:**
- **Alerts fire when conditions are detected** (e.g., BB_SQUEEZE detected at time T)
- **Plans are created AFTER alerts** (user copies alert, pastes to ChatGPT, plan created at T+30s to T+2min)
- **Auto-execution system checks conditions in REAL-TIME** (every 30 seconds)
- **If the alert condition already passed, the plan will wait for it to occur again**
- **⚠️ This is why analysis is MANDATORY - to check if alert is still valid before creating plan**

**🎯 Strategy for Alert-Based Plans:**

1. **BB_SQUEEZE alert** → Use `bb_expansion` OR `price_above`/`price_below` (NOT `bb_squeeze`):
   - **Reason**: By the time plan is created, squeeze may already be over
   - **Better approach**: Wait for breakout (expansion or price break)
   - ✅ **CORRECT**: `{"bb_expansion": true, "price_above": entry, "price_near": entry, "tolerance": X, "timeframe": "M15"}`
   - ✅ **ALTERNATIVE**: `{"price_above": entry, "price_near": entry, "tolerance": X}` (no bb_squeeze - just wait for breakout)
   - ❌ **WRONG**: `{"bb_squeeze": true, ...}` (squeeze may already be over)

2. **BB_EXPANSION alert** → Use `bb_expansion`:
   - ✅ **CORRECT**: `{"bb_expansion": true, "price_above": entry, "price_near": entry, "tolerance": X, "timeframe": "M15"}`
   - Expansion is still active when plan is created

3. **CHOCH/BOS alerts** → Use `choch_bull`/`choch_bear`/`bos_bull`/`bos_bear`:
   - ✅ **CORRECT**: `{"choch_bull": true, "timeframe": "M5", "price_near": entry, "tolerance": X}`
   - Structure changes persist, so condition will still be valid

4. **RSI_DIV alerts** → Use `rsi_div_bull`/`rsi_div_bear`:
   - ✅ **CORRECT**: `{"rsi_div_bull": true, "timeframe": "M15", "price_near": entry, "tolerance": X}`
   - Divergence patterns persist for multiple candles

5. **INSIDE_BAR alert** → Use `inside_bar` OR `price_above`/`price_below`:
   - ⚠️ **Timing issue**: Inside bar may already be broken by the time plan is created
   - ✅ **BETTER**: `{"price_above": entry, "price_near": entry, "tolerance": X}` (wait for breakout)
   - ⚠️ **RISKY**: `{"inside_bar": true, ...}` (inside bar may already be over)
- **BB_EXPANSION alert** → MUST include: `{"bb_expansion": true, "price_above": entry, "price_near": entry, "tolerance": X, "timeframe": "M15"}` 
  - ⚠️ Without `bb_expansion: true`, plan will execute without validating expansion!
- **RSI_DIV_BEAR alert** → MUST include: `{"rsi_div_bear": true, "price_near": entry, "tolerance": X, "timeframe": "M15"}`
  - ⚠️ Without `rsi_div_bear: true`, plan will execute without validating divergence!
- **RSI_DIV_BULL alert** → MUST include: `{"rsi_div_bull": true, "price_near": entry, "tolerance": X, "timeframe": "M15"}`
  - ⚠️ Without `rsi_div_bull: true`, plan will execute without validating divergence!
- **CHOCH_BEAR alert** → MUST include: `{"choch_bear": true, "price_near": entry, "tolerance": X, "timeframe": "M5"}`
  - ⚠️ Without `choch_bear: true`, plan will execute without validating structure shift!
- **CHOCH_BULL alert** → MUST include: `{"choch_bull": true, "price_near": entry, "tolerance": X, "timeframe": "M5"}`
  - ⚠️ Without `choch_bull: true`, plan will execute without validating structure shift!
- **BOS_BEAR alert** → MUST include: `{"bos_bear": true, "price_near": entry, "tolerance": X, "timeframe": "M15"}`
  - ⚠️ Without `bos_bear: true`, plan will execute without validating trend continuation!
- **BOS_BULL alert** → MUST include: `{"bos_bull": true, "price_near": entry, "tolerance": X, "timeframe": "M15"}`
  - ⚠️ Without `bos_bull: true`, plan will execute without validating trend continuation!
- **BULLISH_OB / BEARISH_OB alert** → MUST include: `{"order_block": true, "order_block_type": "auto", "price_near": entry, "tolerance": X}`
  - ⚠️ Without `order_block: true`, plan will execute without validating OB presence!
- **BEAR_SWEEP / BULL_SWEEP alert** → MUST include: `{"liquidity_sweep": true, "price_near": entry, "tolerance": X}`
  - ⚠️ Without `liquidity_sweep: true`, plan will execute without validating sweep occurred!
- **INSIDE_BAR alert** → MUST include: `{"inside_bar": true, "price_above": entry, "price_near": entry, "tolerance": X, "timeframe": "M15"}`
  - ⚠️ Without `inside_bar: true`, plan will execute without validating compression pattern!
- **EQUAL_HIGHS alert** → MUST include: `{"equal_highs": true, "price_near": entry, "tolerance": X, "timeframe": "H1"}`
  - ⚠️ Without `equal_highs: true`, plan will execute without validating liquidity zone!
- **EQUAL_LOWS alert** → MUST include: `{"equal_lows": true, "price_near": entry, "tolerance": X, "timeframe": "H1"}`
  - ⚠️ Without `equal_lows: true`, plan will execute without validating liquidity zone!
- **VWAP_DEV_HIGH / VWAP_DEV_LOW alert** → MUST include: `{"vwap_deviation": true, "vwap_deviation_direction": "above/below", "price_near": entry, "tolerance": X}`
  - ⚠️ Without `vwap_deviation: true`, plan will execute without validating deviation!

**Common Mistakes to Avoid:**
- ❌ "OB Reversal" strategy → Only `price_near` condition (WRONG - missing `order_block`)
- ❌ "Inside Bar Breakout" strategy → Only `price_near` condition (WRONG - missing `price_above`/`price_below`)
- ❌ "CHOCH confirmation" in notes → Only `price_near` condition (WRONG - missing `choch_bull`/`choch_bear`)
- ❌ **"CHOCH Bear" strategy → `{"choch_bear": true, "timeframe": "M15"}` (WRONG - missing `price_near` + `tolerance`)** ⚠️ **Will execute at ANY price when CHOCH confirms!**
- ❌ "Liquidity Sweep" strategy → Only `price_below` condition (WRONG - missing `liquidity_sweep: true`)
- ❌ "VWAP Bounce" strategy → Only `vwap_deviation: true` (WRONG - missing `vwap_deviation_direction`, `price_near`, `tolerance`)
- ❌ **"BB_SQUEEZE alert" → Only `price_above` condition (WRONG - missing `bb_squeeze: true`)** ⚠️ **Will execute on any breakout, not just after squeeze!**
- ❌ **"RSI_DIV_BEAR alert" → Only `price_near` condition (WRONG - missing `rsi_div_bear: true`)** ⚠️ **Will execute without validating divergence!**
- ✅ "OB Reversal" strategy → `{"order_block": true, "order_block_type": "auto", "price_near": entry, "tolerance": X}` (CORRECT)
- ✅ "Inside Bar Breakout" strategy → `{"price_above": entry_price, "price_near": entry_price, "tolerance": X}` (CORRECT)
- ✅ **"BB_SQUEEZE alert" → `{"bb_squeeze": true, "price_above": entry, "price_near": entry, "tolerance": X, "timeframe": "M15"}` (CORRECT)**
- ✅ **"RSI_DIV_BEAR alert" → `{"rsi_div_bear": true, "price_near": entry, "tolerance": X, "timeframe": "M15"}` (CORRECT)**
- ✅ "CHOCH confirmation" in notes → `{"choch_bull": true, "timeframe": "M5", "price_near": 83800, "tolerance": 100}` (CORRECT)
- ✅ "Liquidity Sweep" strategy → `{"liquidity_sweep": true, "price_below": 83890, "timeframe": "M5"}` (CORRECT)
- ✅ "VWAP Bounce" strategy → `{"vwap_deviation": true, "vwap_deviation_direction": "below", "price_near": 83910, "tolerance": 100}` (CORRECT)

### 🚨 **CRITICAL: Why price_near + tolerance is REQUIRED for CHOCH Plans**

**For CHOCH-based plans, a `price_near` condition (with `tolerance`) should ALWAYS be included to anchor execution near the intended entry zone.**

**🔍 Why it matters:**

Without `price_near`, the system will trigger whenever a CHOCH condition is detected on the specified timeframe — **even if the break occurs hundreds of points away from your planned entry**. That could lead to:

- **Slippage** (execution at unexpected prices)
- **R:R distortion** (stop loss and take profit no longer valid)
- **Misaligned execution context** (executed in a different liquidity pocket)

**⚙️ Explanation:**

- **`price_near`**: Anchors monitoring around your planned entry (e.g., ±100 points)
- **`tolerance`**: Defines allowable drift (default BTCUSD ≈ 100 points)

**Example:**
- Plan: `entry_price: 83800`, `stop_loss: 83500`, `take_profit: 82800`
- **WITHOUT `price_near`**: System executes when CHOCH Bear confirms at ANY price (could be 85000, 82000, etc.)
- **WITH `price_near: 83800, tolerance: 100`**: System only executes if CHOCH Bear confirms near 83800 ±100 → keeping structure and R:R intact

**✅ Always include for CHOCH plans:**
```json
{
  "choch_bear": true,
  "timeframe": "M15",
  "price_near": 83800,
  "tolerance": 100
}
```

**Note:** Range scalping plans (`moneybot.create_range_scalp_plan`) use special conditions that are automatically set:
- `range_scalp_confluence`: Minimum confluence score (default: 80)
- `structure_confirmation`: Requires CHOCH/BOS on M15
- `price_near`: Entry price with auto-calculated tolerance
- `plan_type`: "range_scalp" (marks plan as range scalping type)

### Price Conditions

#### `price_above` (number)
Execute when current price goes ABOVE this level.
- Use for: Breakout trades, momentum entries
- Example: `"price_above": 108000` → Executes when BTCUSD price breaks above 108,000

#### `price_below` (number)
Execute when current price goes BELOW this level.
- Use for: Breakdown trades, short entries
- Example: `"price_below": 1.0800` → Executes when EURUSD price breaks below 1.0800

#### `price_near` (number)
Execute when price is within tolerance of target price.
- **Optional parameter**: `tolerance` (number) - Maximum distance from target price
  - **IMPORTANT**: If `tolerance` is not provided, the system automatically calculates it based on symbol type:
    - **BTCUSD**: `100.0` (100 dollars)
    - **ETHUSD**: `10.0` (10 dollars)
    - **XAUUSD/GOLD**: `5.0` (5 dollars)
    - **Forex pairs** (EURUSD, GBPUSD, etc.): `0.001` (0.1 pips)
    - **Other cryptocurrencies**: `10.0`
- Use for: Entry at specific price levels, support/resistance entries
- **Recommended tolerance values** (if manually specifying):
  - **Forex pairs** (EURUSD, GBPUSD): `0.0001` to `0.001` (10-100 pips)
  - **Gold** (XAUUSD): `1.0` to `5.0` (1-5 dollars)
  - **Crypto** (BTCUSD): `50.0` to `100.0` (50-100 dollars)
  - **ETHUSD**: `5.0` to `10.0` (5-10 dollars)
- Example: 
  ```json
  {
    "price_near": 108000
  }
  ```
  → For BTCUSD, automatically uses tolerance of 100.0 (price within 100 points of 108,000)
  
  ```json
  {
    "price_near": 108000,
    "tolerance": 50.0
  }
  ```
  → Manually specified tolerance of 50.0 (price within 50 points of 108,000)

### Structure Conditions (Require Timeframe)

#### `choch_bull` (boolean)
Execute when bullish change of character (CHOCH) detected - structure shift from bearish to bullish.
- **CHOCH (Change of Character)**: Detects reversal by checking if price breaks the **second-to-last** swing high
- **Requires**: `timeframe` or `structure_tf` or `tf` parameter
- **Supported timeframes**: M1, M5, M15, M30, H1, H4, D1
- **Use for**: Trend reversal trades, structure shift entries (when market changes from bearish to bullish)
- **Note**: CHOCH is different from BOS - CHOCH detects reversals (breaks second-to-last swing), while BOS detects continuations (breaks last swing)
- Example:
  ```json
  {
    "choch_bull": true,
    "timeframe": "M15",
    "price_near": 108000,
    "tolerance": 100.0
  }
  ```
  → Executes when M15 CHOCH Bull is confirmed (price breaks above second-to-last swing high) AND price is near 108,000

#### `choch_bear` (boolean)
Execute when bearish change of character (CHOCH) detected - structure shift from bullish to bearish.
- **CHOCH (Change of Character)**: Detects reversal by checking if price breaks the **second-to-last** swing low
- **Requires**: `timeframe` or `structure_tf` or `tf` parameter
- **Supported timeframes**: M1, M5, M15, M30, H1, H4, D1
- **Use for**: Trend reversal trades, structure shift entries (when market changes from bullish to bearish)
- **Note**: CHOCH is different from BOS - CHOCH detects reversals (breaks second-to-last swing), while BOS detects continuations (breaks last swing)
- Example:
  ```json
  {
    "choch_bear": true,
    "timeframe": "M15",
    "price_near": 1.0800,
    "tolerance": 0.001
  }
  ```
  → Executes when M15 CHOCH Bear is confirmed (price breaks below second-to-last swing low) AND price is near 1.0800

#### `rejection_wick` (boolean)
Execute when rejection wick pattern detected (wick-to-body ratio > minimum).
- Analyzes current/last candle for wick rejection
- **Requires**: `timeframe` or `structure_tf` or `tf` parameter (default: M5)
- **Optional**: `min_wick_ratio` (default: 2.0) - Minimum wick-to-body ratio
- Use for: Reversal trades, support/resistance bounces
- Example:
  ```json
  {
    "rejection_wick": true,
    "timeframe": "M5",
    "min_wick_ratio": 2.0,
    "price_near": 4080.0,
    "tolerance": 5.0
  }
  ```
  → Executes when M5 rejection wick detected (wick ratio >= 2.0) AND price is near 4080.0

#### `order_block` (boolean) ⭐ NEW
Execute when institutional order block is detected and validated (M1-M5 validated with 10-parameter checklist).
- **Requires**: M1 microstructure components (automatically available if M1 integration enabled)
- **Optional parameters**:
  - `order_block_type` (string): "bull" (bullish OB only), "bear" (bearish OB only), or "auto" (auto-detect based on plan direction). Default: "auto"
  - `min_validation_score` (integer): Minimum validation score (0-100). Default: 60. Only OBs with score >= this threshold will trigger execution.
  - `timeframe` (string): Always "M1" for order blocks (with M5 cross-timeframe validation)
- **10-Parameter Validation**: Each OB is validated using comprehensive checklist (anchor candle, displacement, FVG, volume, liquidity, session, HTF alignment, structure, freshness, VWAP confluence)
- Use for: High-quality institutional entry zones, precise order block trading
- Example:
  ```json
  {
    "order_block": true,
    "order_block_type": "auto",
    "min_validation_score": 60,
    "price_near": 4080.0,
    "tolerance": 5.0,
    "timeframe": "M1"
  }
  ```
  → Executes when valid order block detected (validation score >= 60) AND entry price is near OB zone

**Note**: You can use `order_block` as a condition in `moneybot.create_auto_trade_plan` OR use the dedicated `moneybot.create_order_block_plan` tool. Both methods work identically - the dedicated tool just sets these conditions automatically.

#### `liquidity_sweep` (boolean) ⭐ NEW
Execute when liquidity sweep (stop hunt) is detected using M1 microstructure analysis.
- **Requires**: M1 analyzer and data fetcher (automatically available if M1 integration enabled)
- **MANDATORY**: You MUST include `liquidity_sweep: true` when creating liquidity sweep plans
- **Also Required**: `price_below` or `price_above` + `timeframe` (M5, M15, etc.)
- **⚠️ CRITICAL: Always include CHOCH confirmation** - The system now requires CHOCH/BOS confirmation before executing liquidity sweep reversals to prevent premature entries
- Detects when price sweeps through liquidity zones (PDH/PDL, equal highs/lows)
- Use for: Reversal trades after stop hunts, high-probability reversal entries
- **Complete Example (SELL after sweep with CHOCH confirmation)**:
  ```json
  {
    "liquidity_sweep": true,
    "choch_bear": true,  // ← REQUIRED: CHOCH confirmation prevents premature entries
    "price_below": 83890,
    "timeframe": "M5"
  }
  ```
  → Executes when liquidity sweep detected AND CHOCH Bear confirmed AND price goes below 83890
- **Complete Example (BUY after sweep with CHOCH confirmation)**:
  ```json
  {
    "liquidity_sweep": true,
    "choch_bull": true,  // ← REQUIRED: CHOCH confirmation prevents premature entries
    "price_above": 84000,
    "timeframe": "M15"
  }
  ```
  → Executes when liquidity sweep detected AND CHOCH Bull confirmed AND price goes above 84000
- **❌ WRONG - Missing liquidity_sweep condition:**
  ```json
  {
    "price_below": 83890,
    "timeframe": "M5"
  }
  ```
  → This will NOT detect liquidity sweeps, only checks price level
- **❌ WRONG - Missing CHOCH confirmation:**
  ```json
  {
    "liquidity_sweep": true,
    "price_below": 83890,
    "timeframe": "M5"
  }
  ```
  → This will be BLOCKED by the system - CHOCH confirmation is now required to prevent false reversals

#### `vwap_deviation` (boolean) ⭐ NEW
Execute when price deviates from VWAP by a specified threshold.
- **Requires**: M1 analyzer and data fetcher
- **MANDATORY**: You MUST include ALL of these when creating VWAP bounce/fade plans:
  - `vwap_deviation: true` - Enables VWAP detection
  - `vwap_deviation_direction` - "above" (for fade), "below" (for bounce), or "any"
  - `price_near` - Entry price for proximity check
  - `tolerance` - Price tolerance (BTCUSD=100, XAUUSD=5, Forex=0.001)
- **Optional parameters**:
  - `vwap_deviation_threshold` (number): Minimum deviation in standard deviations (default: 2.0σ)
- Use for: Mean reversion trades, VWAP bounce/fade strategies
- **Complete Example (VWAP Bounce BUY - price below VWAP)**:
  ```json
  {
    "vwap_deviation": true,
    "vwap_deviation_direction": "below",
    "price_near": 83910,
    "tolerance": 100,
    "timeframe": "M5"
  }
  ```
  → Executes when price is 2.0σ+ below VWAP AND price is near 83910 (±100)
- **Complete Example (VWAP Fade SELL - price above VWAP)**:
  ```json
  {
    "vwap_deviation": true,
    "vwap_deviation_direction": "above",
    "price_near": 84000,
    "tolerance": 100,
    "timeframe": "M15"
  }
  ```
  → Executes when price is 2.0σ+ above VWAP AND price is near 84000 (±100)
- **❌ WRONG - Missing required conditions:**
  ```json
  {
    "vwap_deviation": true,
    "timeframe": "M5"
  }
  ```
  → This will NOT trigger - missing `vwap_deviation_direction`, `price_near`, and `tolerance`

#### `ema_slope` (boolean) ⭐ NEW
Execute when EMA slope aligns with trade direction.
- **Optional parameters**:
  - `ema_period` (integer): EMA period (default: 200 for EMA200)
  - `ema_timeframe` (string): Timeframe for EMA calculation (default: "H1")
  - `ema_slope_direction` (string): "bullish", "bearish", or "any" (default: "any")
  - `min_ema_slope_pct` (number): Minimum slope percentage (default: 0.0)
- Use for: Trend-following trades, momentum continuation
- Example:
  ```json
  {
    "ema_slope": true,
    "ema_period": 200,
    "ema_timeframe": "H1",
    "ema_slope_direction": "bullish",
    "min_ema_slope_pct": 0.1,
    "price_near": 92000.0,
    "tolerance": 100.0
  }
  ```
  → Executes when H1 EMA200 slope is bullish (≥0.1%) AND price is near 92000.0

#### `volatility_state` (string) 🚫 DO NOT USE - BLOCKS EXECUTIONS
**⚠️ CRITICAL: DO NOT ADD THIS CONDITION - IT PREVENTS MOST PLANS FROM EXECUTING**

- **Problem**: Market is usually STABLE, rarely EXPANDING - plans with this condition almost never trigger
- **Values**: "CONTRACTING", "EXPANDING", "STABLE"

**🚫 RULES:**
1. **NEVER add `volatility_state` to any plan by default**
2. **BB_SQUEEZE plans**: Price breakout IS the volatility expansion - do NOT add volatility_state
3. **All breakout/breakdown plans**: Just use `price_above/price_below` + `price_near` + `tolerance`
4. **ONLY add if user EXPLICITLY requests**: "wait for volatility expansion" or "only trade if volatility expands"

- **Example (CORRECT - no volatility_state):**
  ```json
  {
    "price_above": 92000.0,
    "price_near": 92000.0,
    "tolerance": 100.0
  }
  ```
  → Executes when price breaks above 92000.0 - THIS WILL TRIGGER

- **Example (WRONG - blocks execution):**
  ```json
  {
    "volatility_state": "EXPANDING",
    "price_above": 92000.0,
    "price_near": 92000.0,
    "tolerance": 100.0
  }
  ```
  → Almost NEVER executes because market is rarely in EXPANDING state

#### `bb_squeeze` (boolean) ⚠️ TIMING ISSUE - Use with Caution for BB_SQUEEZE alerts
Execute only when Bollinger Band squeeze is detected (BB width below threshold).
- **Requires**: `timeframe` (typically "M15" for BB squeeze alerts)
- **Optional**: `bb_squeeze_threshold` (default: 1.5% for M15)
- **⚠️ CRITICAL TIMING ISSUE**: 
  - **BB_SQUEEZE alerts fire when squeeze is detected** (at time T)
  - **By the time you create the plan (30s-2min later), the squeeze may already be over**
  - **The plan will then wait for the NEXT squeeze, which may never come**
  - **Auto-execution system checks conditions in REAL-TIME every 30 seconds**
- **When to use**: Only if you're creating the plan IMMEDIATELY after the alert (within 30 seconds)
- **When NOT to use**: 
  - **Most BB_SQUEEZE alert-based plans** - Use `bb_expansion` or `price_above`/`price_below` instead
  - Normal breakout plans (use `price_above`/`price_below` without `bb_squeeze`)
- **Better alternative for BB_SQUEEZE alerts**: Use `bb_expansion` to wait for breakout, or just `price_above`/`price_below`:
  ```json
  // ✅ BETTER for BB_SQUEEZE alerts - waits for breakout
  {
    "bb_expansion": true,
    "price_above": 91500.0,
    "price_near": 91500.0,
    "tolerance": 80.0,
    "timeframe": "M15"
  }
  // OR simply:
  {
    "price_above": 91500.0,
    "price_near": 91500.0,
    "tolerance": 80.0
  }
  ```
- **How it works**: Validates that BB width is below threshold (squeeze is active) before allowing execution
- Example (only if plan created immediately):
  ```json
  {
    "bb_squeeze": true,
    "price_above": 91500.0,
    "price_near": 91500.0,
    "tolerance": 80.0,
    "timeframe": "M15"
  }
  ```
  → Executes when BB squeeze is active AND price breaks above 91500.0

#### `rsi_div_bull` (boolean) ⭐ REQUIRED for RSI_DIV_BULL alerts
Execute only when RSI bullish divergence is detected.
- **Requires**: `timeframe` (typically "M15" for RSI divergence alerts)
- **⚠️ CRITICAL**: This condition MUST be included for RSI_DIV_BULL alert-based plans!
- **🚨 CRITICAL VALIDATION**: If your analysis does NOT detect RSI bullish divergence, DO NOT create the plan! The analysis must independently confirm the divergence exists. If analysis shows no divergence detected, the alert is not validated - explain to user why you cannot create the plan.
- **When to use**: Always include when creating plans from RSI_DIV_BULL Discord alerts (ONLY if analysis confirms divergence exists)
- **How it works**: Validates that price is making lower lows while RSI is making higher lows (bullish divergence)
- Example:
  ```json
  {
    "rsi_div_bull": true,
    "price_near": 91000.0,
    "tolerance": 80.0,
    "timeframe": "M15"
  }
  ```
  → Executes when RSI bullish divergence is present AND price is near 91000.0

#### `rsi_div_bear` (boolean) ⭐ REQUIRED for RSI_DIV_BEAR alerts
Execute only when RSI bearish divergence is detected.
- **Requires**: `timeframe` (typically "M15" for RSI divergence alerts)
- **⚠️ CRITICAL**: This condition MUST be included for RSI_DIV_BEAR alert-based plans!
- **🚨 CRITICAL VALIDATION**: If your analysis does NOT detect RSI bearish divergence, DO NOT create the plan! The analysis must independently confirm the divergence exists. If analysis shows "RSI 56.7" with no divergence detected, the alert is not validated - explain to user why you cannot create the plan.
- **When to use**: Always include when creating plans from RSI_DIV_BEAR Discord alerts (ONLY if analysis confirms divergence exists)
- **How it works**: Validates that price is making higher highs while RSI is making lower highs (bearish divergence)
- Example:
  ```json
  {
    "rsi_div_bear": true,
    "price_near": 91498.0,
    "tolerance": 80.0,
    "timeframe": "M15"
  }
  ```
  → Executes when RSI bearish divergence is present AND price is near 91498.0

#### `bos_bull` / `bos_bear` (boolean) ⭐ REQUIRED for BOS_BULL/BOS_BEAR alerts
Execute only when Break of Structure (BOS) is detected - trend continuation pattern.
- **BOS (Break of Structure)**: Detects continuation by checking if price breaks the **last** swing point
  - `bos_bull`: Price breaks above the **last** swing high (uptrend continuation)
  - `bos_bear`: Price breaks below the **last** swing low (downtrend continuation)
- **Requires**: `timeframe` (typically "M15" for BOS alerts)
- **⚠️ CRITICAL**: This condition MUST be included for BOS alert-based plans!
- **When to use**: Always include when creating plans from BOS_BULL/BOS_BEAR Discord alerts
- **How it works**: Validates that structure break confirms trend continuation (higher high in uptrend, lower low in downtrend)
- **Difference from CHOCH**: 
  - **BOS** = trend continuation (breaks **last** swing point)
  - **CHOCH** = trend reversal (breaks **second-to-last** swing point)
- Example:
  ```json
  {
    "bos_bull": true,
    "price_near": 92000.0,
    "tolerance": 100.0,
    "timeframe": "M15"
  }
  ```
  → Executes when bullish BOS is present (price breaks above last swing high on M15) AND price is near 92000.0

#### `bb_expansion` (boolean) ⭐ REQUIRED for BB_EXPANSION alerts
Execute only when Bollinger Band expansion is detected (BB width above threshold).
- **Requires**: `timeframe` (typically "M15" for BB expansion alerts)
- **Optional**: `bb_expansion_threshold` (default: 2.0% for M15)
- **⚠️ CRITICAL**: This condition MUST be included for BB_EXPANSION alert-based plans!
- **When to use**: Always include when creating plans from BB_EXPANSION Discord alerts
- **How it works**: Validates that BB width is above threshold (expansion is active) before allowing execution
- Example:
  ```json
  {
    "bb_expansion": true,
    "price_above": 91500.0,
    "price_near": 91500.0,
    "tolerance": 80.0,
    "timeframe": "M15"
  }
  ```
  → Executes when BB expansion is active AND price breaks above 91500.0

#### `inside_bar` (boolean) ⭐ REQUIRED for INSIDE_BAR alerts
Execute only when inside bar pattern (compression) is detected.
- **Requires**: `timeframe` (typically "M15" for inside bar alerts)
- **⚠️ CRITICAL**: This condition MUST be included for INSIDE_BAR alert-based plans!
- **When to use**: Always include when creating plans from INSIDE_BAR Discord alerts
- **How it works**: Validates that current candle is inside previous candle (compression pattern)
- Example:
  ```json
  {
    "inside_bar": true,
    "price_above": 4173.0,
    "price_near": 4173.0,
    "tolerance": 8.0,
    "timeframe": "M15"
  }
  ```
  → Executes when inside bar pattern is present AND price breaks above 4173.0

#### `equal_highs` / `equal_lows` (boolean) ⭐ REQUIRED for EQUAL_HIGHS/EQUAL_LOWS alerts
Execute only when equal highs/lows (liquidity zones) are detected.
- **Requires**: `timeframe` (typically "H1" for equal highs/lows alerts)
- **Optional**: `equal_tolerance_pct` (default: 0.1%)
- **⚠️ CRITICAL**: This condition MUST be included for EQUAL_HIGHS/EQUAL_LOWS alert-based plans!
- **When to use**: Always include when creating plans from EQUAL_HIGHS/EQUAL_LOWS Discord alerts
- **How it works**: Validates that matching highs/lows exist (liquidity zones where stops cluster)
- Example:
  ```json
  {
    "equal_highs": true,
    "price_near": 92000.0,
    "tolerance": 100.0,
    "timeframe": "H1"
  }
  ```
  → Executes when equal highs liquidity zone is present AND price is near 92000.0

#### `min_volatility` (number) ⚠️ OPTIONAL - Use Only When Needed
Execute only when volatility (ATR) is above minimum threshold.
- **Value**: `0.5` (ATR ratio vs baseline)
- **Benefit**: Reduces false triggers by 20-25% in low-volatility conditions
- **⚠️ WARNING**: Can prevent execution if volatility is below threshold
- **When to use**: Only when market is in a dead zone and you specifically want to wait for volatility expansion
- **When NOT to use**: Normal market conditions, already expanding volatility, trend continuation trades
- **Default**: DO NOT include unless market analysis shows low volatility is a concern
- Example:
  ```json
  {
    "choch_bull": true,
    "timeframe": "M5",
    "min_volatility": 0.5
  }
  ```
  → Executes when CHOCH Bull confirmed AND ATR >= 0.5

#### `bb_width_threshold` (number) ⚠️ OPTIONAL - Use Only When Needed
Execute only when Bollinger Band width is above threshold (ensures breakout conditions).
- **Value**: `2.5` (ensures breakout conditions)
- **Benefit**: Reduces false triggers by 5-10% in compressed markets
- **⚠️ WARNING**: Can prevent execution if BB width is narrow
- **When to use**: Only when specifically waiting for volatility expansion (Bollinger squeeze breakout)
- **When NOT to use**: Normal breakouts, trend continuation, when BB width is already adequate
- **Default**: DO NOT include unless you're specifically trading volatility expansion setups
- Example:
  ```json
  {
    "price_above": 92000.0,
    "bb_width_threshold": 2.5
  }
  ```
  → Executes when price breaks above 92000.0 AND BB width > 2.5

#### `m1_choch_bos_combo` (boolean) ⚠️ OPTIONAL - Use Only When Needed
Require M1 CHOCH + BOS combo confirmation for CHOCH-based plans.
- **Benefit**: Improves entry precision by 20-35% for CHOCH plans
- **⚠️ WARNING**: Very strict condition - requires M1 CHOCH+BOS combo which may not occur frequently
- **When to use**: Only when M1 structure is clear and you want extra precision validation
- **When NOT to use**: Choppy markets, unclear M1 structure, when you want higher execution probability
- **Default**: DO NOT include unless M1 confirmation is critical for the trade setup
- **⚠️ CRITICAL: Multi-Timeframe Validation:**
  - When using `m1_choch_bos_combo`, you MUST also include the higher timeframe condition (`choch_bull` or `choch_bear`)
  - The system checks BOTH timeframes: M5/M15 (from `choch_bull`/`choch_bear`) AND M1 (from `m1_choch_bos_combo`)
  - Both conditions must be met for execution
- **Note**: M1 validation already runs automatically, but this condition requires explicit M1 CHOCH+BOS confirmation
- Example (CORRECT - checks both M5 and M1):
  ```json
  {
    "choch_bull": true,
    "timeframe": "M5",
    "m1_choch_bos_combo": true,
    "price_near": 83800,
    "tolerance": 100
  }
  ```
  → Executes when **BOTH** M5 CHOCH Bull confirmed **AND** M1 CHOCH+BOS combo confirmed
- Example (WRONG - missing higher timeframe):
  ```json
  {
    "m1_choch_bos_combo": true,
    "price_near": 83800,
    "tolerance": 100
  }
  ```
  → ❌ Missing `choch_bull`/`choch_bear` - plan will not validate M5/M15 structure!

### Multi-Timeframe Conditions ⭐ CRITICAL

**🚨 IMPORTANT: The system checks BOTH timeframes when multiple timeframe conditions are specified.**

#### How Multi-Timeframe Validation Works:

1. **Higher Timeframe (M5/M15) checks run first** in `_check_conditions()`
2. **M1 validation runs second** in `_validate_m1_conditions()`
3. **Both must pass** for execution to proceed

#### Conditions That Use Multiple Timeframes:

| Condition | Higher TF | Lower TF | When Both Required |
|-----------|-----------|----------|-------------------|
| `choch_bull` + `m1_choch_bos_combo` | M5/M15 (from `choch_bull`) | M1 (from `m1_choch_bos_combo`) | ✅ **YES** - Must include both |
| `choch_bear` + `m1_choch_bos_combo` | M5/M15 (from `choch_bear`) | M1 (from `m1_choch_bos_combo`) | ✅ **YES** - Must include both |
| `order_block` | M5 (auto-validated) | M1 (detection) | ✅ **AUTO** - System checks both automatically |
| `liquidity_sweep` | M5/M15 (optional context) | M1 (primary detection) | ⚠️ **OPTIONAL** - Can add `choch_bull`/`choch_bear` for structure |
| `structure_confirmation` | M15 (primary) | M5 (optional context) | ⚠️ **OPTIONAL** - Can specify `structure_timeframe` |
| `bb_expansion` | M15 (default) | M5 (optional) | ⚠️ **OPTIONAL** - Use `bb_expansion_check_both: true` |

#### ⚠️ CRITICAL Rules for Multi-Timeframe Plans:

1. **`m1_choch_bos_combo` REQUIRES higher timeframe condition:**
   ```json
   // ✅ CORRECT - Checks both M5 and M1
   {
     "choch_bull": true,
     "timeframe": "M5",
     "m1_choch_bos_combo": true,
     "price_near": 83800,
     "tolerance": 100
   }
   
   // ❌ WRONG - Only checks M1, missing M5 structure
   {
     "m1_choch_bos_combo": true,
     "price_near": 83800,
     "tolerance": 100
   }
   ```

2. **`order_block` automatically uses both M1 and M5:**
   ```json
   // ✅ CORRECT - System automatically checks M1 (detection) + M5 (validation)
   {
     "order_block": true,
     "order_block_type": "auto",
     "price_near": 4080,
     "tolerance": 5
   }
   ```

3. **`liquidity_sweep` can combine with structure:**
   ```json
   // ✅ RECOMMENDED - Checks M5 structure + M1 sweep
   {
     "liquidity_sweep": true,
     "choch_bull": true,
     "timeframe": "M5",
     "price_near": 4080,
     "tolerance": 5
   }
   ```

4. **`bb_expansion` can check both M5 and M15:**
   ```json
   // ✅ Checks both M15 and M5
   {
     "bb_expansion": true,
     "timeframe": "M15",
     "bb_expansion_check_both": true,
     "price_above": 91500,
     "price_near": 91500,
     "tolerance": 80
   }
   ```

### Combined Conditions ⭐ NEW

You can combine multiple conditions for higher-quality setups:

**Example 1: Liquidity Sweep + Order Block**
```json
{
  "liquidity_sweep": true,
  "order_block": true,
  "order_block_type": "auto",
  "price_near": 4080.0,
  "tolerance": 5.0
}
```
→ Executes when both liquidity sweep AND order block are detected

**Example 2: VWAP Deviation + Rejection Wick**
```json
{
  "vwap_deviation": true,
  "vwap_deviation_threshold": 2.0,
  "vwap_deviation_direction": "above",
  "rejection_wick": true,
  "timeframe": "M5",
  "price_near": 4085.0,
  "tolerance": 5.0
}
```
→ Executes when price is 2.0σ+ above VWAP AND rejection wick forms

**Example 3: EMA Slope + Volatility State**
```json
{
  "ema_slope": true,
  "ema_slope_direction": "bullish",
  "volatility_state": "EXPANDING",
  "price_above": 92000.0
}
```
→ Executes when EMA slope is bullish AND volatility is expanding AND price breaks above 92000.0

### Time Conditions

#### `time_after` (ISO 8601 string)
Execute after specified date/time.
- Format: `"2025-10-31T14:00:00"` or `"2025-10-31T14:00:00+00:00"`
- Use for: Session-based entries (e.g., London session start)
- Example: `"time_after": "2025-10-31T08:00:00"` → Executes after 8 AM on Oct 31

#### `time_before` (ISO 8601 string)
Execute before specified date/time.
- Format: Same as `time_after`
- Use for: End-of-day trades, session exits
- Example: `"time_before": "2025-10-31T17:00:00"` → Must execute before 5 PM

### Volatility Conditions

#### `atr_5m_threshold` (number)
Execute when ATR (Average True Range) on M5 timeframe exceeds this value.
- **Calculation**: Uses last 14 M5 candles to compute ATR
- **Use for**: Ensuring candles are expanding enough for rapid price movement
- **Example**: `"atr_5m_threshold": 4.5` → Executes when ATR(5m) > 4.5 USD
- **Recommended values**:
  - Gold (XAUUSD): 3.0 - 5.0
  - Crypto (BTCUSD): 50 - 200
  - Forex: 0.0005 - 0.002

#### `vix_threshold` (number)
Execute when VIX (Volatility Index) exceeds this value.
- **Source**: Fetched from Yahoo Finance (real-time)
- **Use for**: Confirming broad-market volatility is high enough
- **Example**: `"vix_threshold": 16.5` → Executes when VIX > 16.5
- **Recommended values**:
  - Low volatility: < 15
  - Normal: 15 - 20
  - Elevated: 20 - 30
  - High volatility: > 30

#### `bb_width_threshold` (number)
Execute when Bollinger Bands width (in ATR-equivalent units) exceeds this value.
- **Calculation**: BB Width = (Upper Band - Lower Band) / ATR
- **Use for**: Detecting expansion phase following compression
- **Example**: `"bb_width_threshold": 3.5` → Executes when BB Width > 3.5 ATR-equivalent units
- **Recommended values**: 2.0 - 5.0 (depends on symbol volatility)

#### `volatility_trigger_rule` (number)
Number of volatility conditions that must be met (default: 2).
- **Use with**: `atr_5m_threshold`, `vix_threshold`, `bb_width_threshold`
- **Example**: `"volatility_trigger_rule": 2` → Requires 2 of 3 volatility conditions to be met
- **Typical usage**: `2` for 2-of-3 rule, or `3` for all conditions required

#### Legacy Volatility Conditions

- `min_volatility` (number) - Execute when ATR(5m) is above minimum (legacy)
- `max_volatility` (number) - Execute when ATR(5m) is below maximum (legacy)

**Note**: Prefer using `atr_5m_threshold`, `vix_threshold`, and `bb_width_threshold` with `volatility_trigger_rule` for more flexible volatility monitoring.

### Special Conditions

#### `execute_immediately` (boolean)
Execute immediately without waiting for any other conditions.
- Use for: Manual trigger trades, instant execution
- **Use with caution**: Bypasses all safety checks
- Example: `"execute_immediately": true` → Executes as soon as plan is created

### Timeframe Parameter

When using structure conditions (`choch_bull`, `choch_bear`, `rejection_wick`), specify the timeframe using one of:
- `timeframe` (recommended)
- `structure_tf` 
- `tf`

**Supported timeframes**: `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1` (default: `M5`)

#### How Timeframe Monitoring Works

1. **Timeframe in Conditions**: If you include `"timeframe": "M15"` in the conditions object, the system will:
   - Fetch the last 100 M15 candles from MT5 for structure analysis
   - Check for BOS (Break of Structure) patterns on the M15 timeframe
   - Monitor price proximity on M15 candles

2. **Automatic Extraction from Notes**: If you mention a timeframe in the `notes`/`reasoning` field (e.g., "M15 BOS Bull trigger") but don't include it in conditions:
   - The system automatically extracts it from notes using pattern matching
   - Example: Notes "Trigger trade when BOS Bull confirmed on M15" → Extracts `M15` automatically
   - If no timeframe found, defaults to `M5`

3. **MT5 Candle Fetching**: The system uses MT5's `copy_rates_from_pos()` to fetch historical candles:
   - For structure conditions: Fetches last 100 candles of specified timeframe
   - For rejection wick: Fetches last 3 candles of specified timeframe
   - Candles are checked every 30 seconds during monitoring

**Best Practice**: Always include `"timeframe"` explicitly in conditions for clarity and reliability.

## Example Usage

### Basic Conditional Plan (Price Entry)
```json
{
  "symbol": "BTCUSD",
  "direction": "BUY",
  "entry": 108000,
  "stop_loss": 107400,
  "take_profit": 108950,
  "volume": 0.1,
  "conditions": {
    "price_near": 108000,
    "tolerance": 100.0
  },
  "expires_hours": 24,
  "reasoning": "Scalp buy near liquidity support at 108k"
}
```
**Note**: Tolerance of 100.0 is appropriate for BTCUSD (50-100 range)

### Inside Bar / Volatility Trap / Breakout Plan (CORRECT - with price_above condition)
```json
{
  "symbol": "BTCUSDc",
  "direction": "BUY",
  "entry": 91712,
  "stop_loss": 91502,
  "take_profit": 92261,
  "volume": 0.01,
  "conditions": {
    "price_above": 91712,
    "price_near": 91712,
    "tolerance": 100.0
  },
  "expires_hours": 24,
  "reasoning": "Inside Bar Volatility Trap setup - awaiting breakout confirmation above 91712"
}
```
**✅ CORRECT**: Includes `price_above` condition for breakout strategy

### Order Block Plan (CORRECT - with order_block condition)
```json
{
  "symbol": "XAUUSDc",
  "direction": "SELL",
  "entry": 4063,
  "stop_loss": 4066.2,
  "take_profit": 4055.8,
  "volume": 0.01,
  "conditions": {
    "order_block": true,
    "order_block_type": "bear",
    "min_validation_score": 60,
    "price_near": 4063,
    "tolerance": 5.0,
    "timeframe": "M1"
  },
  "expires_hours": 24,
  "reasoning": "OB Reversal: Countertrend scalp from bearish OB (4063-4065). Wait for M1/M5 bearish engulfing confirmation with CHOCH and RSI rollover below 50."
}
```
**✅ CORRECT**: Includes `order_block: true` condition for OB strategy

### Order Block + CHOCH Combined Plan (CORRECT - with multiple conditions)
```json
{
  "symbol": "XAUUSDc",
  "direction": "BUY",
  "entry": 4060,
  "stop_loss": 4056.5,
  "take_profit": 4068.5,
  "volume": 0.01,
  "conditions": {
    "order_block": true,
    "order_block_type": "auto",
    "min_validation_score": 60,
    "choch_bull": true,
    "timeframe": "M5",
    "price_near": 4060,
    "tolerance": 5.0
  },
  "expires_hours": 24,
  "reasoning": "OB Continuation: Bullish trap reversal from bullish OB (4058-4061). Wait for M5 CHOCH confirmation with volume confirmation before entry."
}
```
**✅ CORRECT**: Includes both `order_block` and `choch_bull` conditions for combined strategy

### CHOCH Plan (Structure-Based)
```json
{
  "symbol": "EURUSD",
  "direction": "BUY",
  "entry": 1.0800,
  "stop_loss": 1.0750,
  "take_profit": 1.0850,
  "volume": 0.01,
  "conditions": {
    "choch_bull": true,
    "timeframe": "M15",
    "price_near": 1.0800,
    "tolerance": 0.001
  },
  "expires_hours": 24,
  "reasoning": "CHOCH bull setup on EURUSD - M15 BOS Bull confirmed"
}
```
**Note**: Using `tool_create_choch_plan` automatically sets these conditions. Alternatively, use `tool_create_auto_trade_plan` with conditions object.

### Rejection Wick Plan (Pattern-Based)
```json
{
  "symbol": "XAUUSD",
  "direction": "SELL",
  "entry": 2000,
  "stop_loss": 2010,
  "take_profit": 1980,
  "volume": 0.01,
  "conditions": {
    "rejection_wick": true,
    "min_wick_ratio": 2.0,
    "timeframe": "M5",
    "price_near": 2000,
    "tolerance": 5.0
  },
  "expires_hours": 24,
  "reasoning": "Rejection wick at 2000 resistance - M5 timeframe"
}
```
**Note**: Tolerance of 5.0 is appropriate for XAUUSD (1-5 range). Using `tool_create_rejection_wick_plan` automatically sets these conditions.

### Creating Two Independent Plans (Replaces Bracket Trades) ⭐ NEW

**⚠️ Bracket Trades Deprecated:**
Bracket trades are no longer supported. Instead, create two independent plans (one BUY, one SELL) with different conditions using `moneybot.create_multiple_auto_plans` or individual create tools.

**Method 1: Using batch operations** (Recommended - creates both plans at once)
```json
{
  "plans": [
    {
      "plan_type": "auto_trade",
      "symbol": "BTCUSDc",
      "direction": "BUY",
      "entry_price": 92000.0,
      "stop_loss": 91000.0,
      "take_profit": 93000.0,
      "volume": 0.01,
      "conditions": {
        "price_above": 92000.0,
        "price_near": 92000.0,
        "tolerance": 100.0,
        "order_block": true,
        "order_block_type": "auto"
      },
      "expires_hours": 24,
      "notes": "BUY plan for range breakout with order block validation"
    },
    {
      "plan_type": "auto_trade",
      "symbol": "BTCUSDc",
      "direction": "SELL",
      "entry_price": 90000.0,
      "stop_loss": 91000.0,
      "take_profit": 89000.0,
      "volume": 0.01,
      "conditions": {
        "price_below": 90000.0,
        "price_near": 90000.0,
        "tolerance": 100.0,
        "order_block": true,
        "order_block_type": "auto"
      },
      "expires_hours": 24,
      "notes": "SELL plan for range breakout with order block validation"
    }
  ]
}
```

**Method 2: Using individual tools** (Create each plan separately)
- Create BUY plan using `moneybot.create_auto_trade_plan` with direction="BUY"
- Create SELL plan using `moneybot.create_auto_trade_plan` with direction="SELL"

**Benefits:**
- Each plan monitors independently with its own conditions
- If one executes, the other can still execute later if conditions are met
- More flexible than OCO bracket trades (which cancel the other side)
- Supports all condition types (order_block, choch, price_above/below, liquidity_sweep, etc.)
- Ideal for range breakouts, consolidation patterns, and news events where direction is uncertain

### Order Block Plan (M1-M5 Validated) ⭐ NEW

**Method 1: Using dedicated tool** (`moneybot.create_order_block_plan`)
```json
{
  "symbol": "XAUUSDc",
  "direction": "BUY",
  "entry": 4080.0,
  "stop_loss": 4070.0,
  "take_profit": 4100.0,
  "volume": 0.01,
  "order_block_type": "auto",
  "min_validation_score": 60,
  "expires_hours": 24,
  "reasoning": "Order block BUY plan - wait for bullish OB with validation score >= 60 (M1-M5 validated)"
}
```

**Method 2: Using general tool with conditions** (`moneybot.create_auto_trade_plan`)
```json
{
  "symbol": "XAUUSDc",
  "direction": "BUY",
  "entry": 4080.0,
  "stop_loss": 4070.0,
  "take_profit": 4100.0,
  "volume": 0.01,
  "conditions": {
    "order_block": true,
    "order_block_type": "auto",
    "min_validation_score": 60,
    "price_near": 4080.0,
    "tolerance": 5.0,
    "timeframe": "M1"
  },
  "expires_hours": 24,
  "reasoning": "Order block BUY plan using general tool with order_block condition"
}
```

**Note**: 
- Both methods work identically - `moneybot.create_order_block_plan` is a convenience wrapper that sets the conditions automatically
- `order_block_type: "auto"` automatically matches the plan direction (BUY → bullish OB, SELL → bearish OB)
- `min_validation_score: 60` requires a validation score of at least 60/100 from the 10-parameter checklist
- The system will wait for a valid order block to form and pass all validation checks before executing
- Order blocks are primarily detected on M1 with M5 cross-timeframe validation
- You can combine `order_block` with other conditions (e.g., `choch_bull`, `rejection_wick`) for multi-condition plans

### Immediate Execution Plan
```json
{
  "symbol": "GBPUSD",
  "direction": "BUY",
  "entry": 1.2500,
  "stop_loss": 1.2450,
  "take_profit": 1.2550,
  "conditions": {
    "execute_immediately": true
  },
  "reasoning": "Immediate execution based on current analysis"
}
```

### ❌ WRONG Examples (Missing Required Conditions)

**Example 1: Inside Bar Breakout - Missing price_above condition**
```json
{
  "symbol": "BTCUSDc",
  "direction": "BUY",
  "entry": 91712,
  "conditions": {
    "price_near": 91712,
    "tolerance": 100.0
  },
  "reasoning": "Inside Bar Volatility Trap setup - awaiting breakout confirmation"
}
```
**❌ WRONG**: Missing `price_above` condition - plan will execute when price reaches 91712, not when it breaks above!

**Example 2: Order Block Reversal - Missing order_block condition**
```json
{
  "symbol": "XAUUSDc",
  "direction": "SELL",
  "entry": 4063,
  "conditions": {
    "price_near": 4063,
    "tolerance": 5.0
  },
  "reasoning": "OB Reversal: Countertrend scalp from bearish OB (4063-4065)"
}
```
**❌ WRONG**: Missing `order_block: true` condition - plan will execute when price reaches 4063, not when OB is detected!

**Example 3: Liquidity Sweep - Missing liquidity_sweep condition**
```json
{
  "symbol": "BTCUSDc",
  "direction": "SELL",
  "entry": 83890,
  "conditions": {
    "price_below": 83890,
    "timeframe": "M5"
  },
  "reasoning": "Liquidity Sweep scalp plan: SELL when price sweeps above equal highs and returns below 83890"
}
```
**❌ WRONG**: Missing `liquidity_sweep: true` condition - plan will execute when price goes below 83890, but will NOT detect actual liquidity sweeps using M1 microstructure!

**Example 4: VWAP Bounce - Missing required conditions**
```json
{
  "symbol": "BTCUSDc",
  "direction": "BUY",
  "entry": 83910,
  "conditions": {
    "vwap_deviation": true,
    "timeframe": "M5"
  },
  "reasoning": "VWAP Bounce scalp plan: BUY when price touches VWAP lower deviation zone"
}
```
**❌ WRONG**: Missing `vwap_deviation_direction`, `price_near`, and `tolerance` - plan will NOT trigger because system requires all these conditions for VWAP bounce detection!

**✅ CORRECT VERSIONS:**

**Example 1 (Fixed):**
```json
{
  "symbol": "BTCUSDc",
  "direction": "BUY",
  "entry": 91712,
  "conditions": {
    "price_above": 91712,
    "price_near": 91712,
    "tolerance": 100.0
  },
  "reasoning": "Inside Bar Volatility Trap setup - awaiting breakout confirmation"
}
```

**Example 2 (Fixed):**
```json
{
  "symbol": "XAUUSDc",
  "direction": "SELL",
  "entry": 4063,
  "conditions": {
    "order_block": true,
    "order_block_type": "bear",
    "min_validation_score": 60,
    "price_near": 4063,
    "tolerance": 5.0,
    "timeframe": "M1"
  },
  "reasoning": "OB Reversal: Countertrend scalp from bearish OB (4063-4065)"
}
```

**Example 3 (Fixed - Liquidity Sweep):**
```json
{
  "symbol": "BTCUSDc",
  "direction": "SELL",
  "entry": 83890,
  "conditions": {
    "liquidity_sweep": true,
    "price_below": 83890,
    "timeframe": "M5"
  },
  "reasoning": "Liquidity Sweep scalp plan: SELL when price sweeps above equal highs and returns below 83890"
}
```

**Example 4 (Fixed - VWAP Bounce):**
```json
{
  "symbol": "BTCUSDc",
  "direction": "BUY",
  "entry": 83910,
  "conditions": {
    "vwap_deviation": true,
    "vwap_deviation_direction": "below",
    "price_near": 83910,
    "tolerance": 100,
    "timeframe": "M5"
  },
  "reasoning": "VWAP Bounce scalp plan: BUY when price touches VWAP lower deviation zone"
}
```

## Important Notes

### Safety Features
- Plans without conditions will NOT execute automatically (safety measure)
- Use `execute_immediately: true` for immediate execution
- All plans have expiry times to prevent indefinite monitoring
- Plans are monitored every 30 seconds

### Symbol Format
- Use standard symbols: "BTCUSD", "EURUSD", "XAUUSD", etc.
- System automatically adds 'c' suffix for MT5 compatibility

### Execution Behavior
- Plans execute as market orders when conditions are met
- Stop loss and take profit are set on the order
- Discord notifications are sent on successful execution
- Failed executions are logged with error details

### Plan Status
- `pending`: Waiting for conditions to be met
- `executed`: Successfully executed
- `cancelled`: Manually cancelled
- `expired`: Expired without execution

## ⚠️ Pre-Creation Validation Checklist

**BEFORE creating any auto-execution plan, always check:**

### 1. **Liquidity Sweep Plans - CHOCH Confirmation Required**
- ✅ **ALWAYS include `choch_bear: true` for SELL plans** or `choch_bull: true` for BUY plans
- ✅ System will block execution without CHOCH confirmation (prevents premature entries)
- Example:
  ```json
  {
    "liquidity_sweep": true,
    "choch_bear": true,  // ← REQUIRED
    "price_below": 83890,
    "timeframe": "M5"
  }
  ```

### 2. **Order Block Plans - VWAP Deviation Check**
- ✅ **Check VWAP deviation BEFORE creating OB plans**
- ✅ Use `moneybot.analyse_symbol_full` to see current VWAP deviation
- ✅ **If VWAP > 2.0σ extended** → **DO NOT create bullish OB plans** (system will block)
- ✅ **If VWAP < -2.0σ extended** → **DO NOT create bearish OB plans** (system will block)
- ✅ Wait for mean reversion before creating OB plans in overextended markets

### 3. **Session Timing Check**
- ✅ **DO NOT create plans within 30 minutes of session close**
- ✅ Session end times (UTC): London 13:00, NY 21:00, Overlap 16:00
- ✅ System will block execution near session end, but better to avoid creating low-probability plans
- ✅ Prefer London/NY open periods (first 2-3 hours) for better follow-through

### 4. **Order Flow Check (BTCUSD OB Plans Only)**
- ✅ **ALWAYS use `moneybot.btc_order_flow_metrics` before creating BTCUSD OB plans**
- ✅ **For BUY plans:** Only create if `delta > 0.25` AND `CVD rising`
- ✅ **For SELL plans:** Only create if `delta < -0.25` AND `CVD falling`
- ✅ Check absorption zones - avoid creating OB plans if entry is in an absorption zone
- ✅ System will validate order flow, but checking beforehand prevents wasted plan creation

---

## Best Practices

1. **Always specify conditions** - Plans without conditions will be skipped
   - ✅ GOOD: `{"price_near": 108000, "tolerance": 100.0}`
   - ❌ BAD: `{}` (empty conditions)

2. **🚨 CRITICAL: Match conditions to strategy type** - This is the MOST IMPORTANT rule!
   - ✅ GOOD: Reasoning says "OB Reversal" → `{"order_block": true, "order_block_type": "auto", "price_near": entry, "tolerance": X}`
   - ✅ GOOD: Reasoning says "Inside Bar Breakout" → `{"price_above": entry, "price_near": entry, "tolerance": X}`
   - ✅ GOOD: Reasoning says "CHOCH confirmation" → `{"choch_bull": true, "timeframe": "M5", "price_near": entry, "tolerance": X}`
   - ❌ BAD: Reasoning says "OB Reversal" → Only `{"price_near": entry}` (missing order_block condition!)
   - ❌ BAD: Reasoning says "Inside Bar Breakout" → Only `{"price_near": entry}` (missing price_above condition!)
   - ❌ BAD: Reasoning says "CHOCH confirmation" → Only `{"price_near": entry}` (missing choch_bull condition!)

2. **Use appropriate tolerances** - Set realistic price tolerances for your symbols
   - Forex: 0.0001-0.001 (10-100 pips)
   - Gold: 1.0-5.0 (1-5 dollars)
   - BTC: 50-100 (50-100 dollars)
   - ETH: 5-10 (5-10 dollars)

3. **Combine conditions for better entries**
   - Example: `{"choch_bull": true, "timeframe": "M15", "price_near": 108000, "tolerance": 100.0}`
   - Requires BOS Bull confirmation AND price proximity

4. **Set reasonable expiry times** - Don't let plans run indefinitely
   - Default: 24 hours
   - Session-based: 4-8 hours
   - Scalp: 1-4 hours

5. **Monitor plan status** - Check execution status regularly
   - Web dashboard: `http://localhost:8010/auto-execution/view`
   - Use `get_auto_trade_plan_status` tool

6. **Use descriptive reasoning** - Help with plan tracking and debugging

## Common Condition Patterns

### Pattern 1: Simple Price Entry
```json
{
  "conditions": {
    "price_near": 108000,
    "tolerance": 100.0
  }
}
```
Best for: Simple support/resistance entries

### Pattern 2: Breakout Entry
```json
{
  "conditions": {
    "price_above": 108000
  }
}
```
Best for: Momentum breakouts, trend continuation

### Pattern 3: BOS Bull Entry
```json
{
  "conditions": {
    "choch_bull": true,
    "timeframe": "M15",
    "price_near": 108000,
    "tolerance": 100.0
  }
}
```
Best for: Trend confirmation entries after structure break

### Pattern 4: Rejection Wick Entry
```json
{
  "conditions": {
    "rejection_wick": true,
    "min_wick_ratio": 2.0,
    "timeframe": "M5",
    "price_near": 2000.0,
    "tolerance": 5.0
  }
}
```
Best for: Support/resistance bounce entries

### Pattern 5: Time-Based Entry
```json
{
  "conditions": {
    "time_after": "2025-10-31T08:00:00",
    "price_near": 1.0800,
    "tolerance": 0.001
  }
}
```
Best for: Session-based entries (e.g., London open)

### Pattern 6: Combined Structure + Price + Time
```json
{
  "conditions": {
    "choch_bull": true,
    "timeframe": "M15",
    "price_near": 108000,
    "tolerance": 100.0,
    "time_after": "2025-10-31T08:00:00"
  }
}
```
Best for: High-confidence entries requiring multiple confirmations

### Pattern 7: Volatility Threshold Entry (2-of-3 Rule)
```json
{
  "conditions": {
    "price_near": 4007.15,
    "tolerance": 5.0,
    "atr_5m_threshold": 4.5,
    "vix_threshold": 16.5,
    "bb_width_threshold": 3.5,
    "volatility_trigger_rule": 2
  }
}
```
Best for: Scalping strategies requiring volatility confirmation
- Triggers when price is near entry AND at least 2 of 3 volatility conditions are met
- Prevents execution in quiet, low-volatility ranges

### Pattern 8: Range Scalping Auto-Execution (NEW!)
```json
{
  "symbol": "BTCUSDc",
  "direction": "BUY",
  "entry": 105350.0,
  "stop_loss": 105100.0,
  "take_profit": 106100.0,
  "volume": 0.01,
  "min_confluence": 80,
  "expires_hours": 8,
  "reasoning": "Range scalping BUY - wait for confluence >= 80"
}
```
**Use tool:** `moneybot.create_range_scalp_plan` (automatically sets conditions)

Best for: Range-bound markets where you want to wait for high-quality setups
- Monitors confluence score (Structure + Location + Confirmation)
- Requires structure confirmation (CHOCH/BOS on M15)
- Waits for price near entry zone
- Executes automatically when all conditions met (confluence >= 80, structure confirmed, price near entry)

## Error Handling

- Invalid symbols will be rejected
- Missing required parameters will cause 422 errors
- MT5 connection issues will prevent execution
- Discord notification failures are logged but don't stop execution

## Monitoring and Management

- View all plans at: `http://localhost:8010/auto-execution/view`
- Plans are automatically loaded from database on system startup
- Use the web interface to cancel plans manually
- System logs provide detailed execution information

## Integration with Trading System

- Auto execution runs alongside other monitoring systems
- Uses same MT5 connection as main trading system
- Integrates with Discord notification system
- Plans are stored in SQLite database for persistence
