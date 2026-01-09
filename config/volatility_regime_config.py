"""
Volatility Regime Detection Configuration - Phase 1

Documents all parameters, thresholds, weights, and filter durations
for the volatility regime detection system.
"""

# ============================================================================
# REGIME CLASSIFICATION THRESHOLDS
# ============================================================================

# ATR Ratio Thresholds (ATR(14) / ATR(50))
ATR_RATIO_STABLE = 1.2  # Below this = STABLE
ATR_RATIO_TRANSITIONAL_LOW = 1.2  # Lower bound for TRANSITIONAL
ATR_RATIO_TRANSITIONAL_HIGH = 1.4  # Upper bound for TRANSITIONAL
ATR_RATIO_VOLATILE = 1.4  # Above this = VOLATILE

# Bollinger Band Width Multipliers (vs 20-day median)
BOLLINGER_WIDTH_MULTIPLIER_STABLE = 1.5  # Below this = STABLE
BOLLINGER_WIDTH_MULTIPLIER_TRANSITIONAL = 1.8  # Threshold for TRANSITIONAL
BOLLINGER_WIDTH_MULTIPLIER_VOLATILE = 1.8  # Above this = VOLATILE

# ADX Thresholds
ADX_THRESHOLD_WEAK = 20  # Below this = weak/no trend
ADX_THRESHOLD_STRONG = 25  # Above this = strong trend

# ============================================================================
# MULTI-TIMEFRAME WEIGHTING
# ============================================================================

TIMEFRAME_WEIGHTS = {
    "M5": 0.20,   # 20% weight
    "M15": 0.30,  # 30% weight
    "H1": 0.50    # 50% weight
}

# ============================================================================
# FILTER PARAMETERS (Prevent False Signals)
# ============================================================================

# Persistence Filter: Require N consecutive candles showing same regime
PERSISTENCE_REQUIRED = 3  # Minimum candles before confirming regime change

# Regime Inertia: Minimum candles a regime must hold before changing
INERTIA_MIN_HOLD = 5  # Prevents rapid flips

# Auto-Cooldown: Ignore reversals within N candles
COOLDOWN_WINDOW = 2  # Candle count for cooldown period

# Volume Confirmation: Require volume spike when ATR increases
VOLUME_SPIKE_THRESHOLD = 1.5  # 150% of average volume

# ============================================================================
# CONFIDENCE SCORING
# ============================================================================

# Confidence calculation factors:
# - ATR ratio strength (0-100)
# - BB width strength (0-100)
# - ADX strength (0-100)
# - Volume confirmation bonus (+10 or -10)
# - Multi-timeframe alignment bonus (+10 or 0)

# Minimum confidence threshold for WAIT state
CONFIDENCE_THRESHOLD_WAIT = 70  # Below this = WAIT (Regime Confidence Low)

# ============================================================================
# REGIME-ADJUSTED RISK MANAGEMENT
# ============================================================================

# Position sizing by regime (Phase 1 - for display only, Phase 3 will implement)
REGIME_POSITION_SIZING = {
    "STABLE": 1.0,        # 1.0% max risk per trade
    "TRANSITIONAL": 0.75, # 0.75% max risk per trade
    "VOLATILE": 0.5      # 0.5% max risk per trade
}

# ============================================================================
# EVENT LOGGING
# ============================================================================

# Database path for regime events
REGIME_EVENTS_DB_PATH = "data/volatility_regime_events.sqlite"

# Session detection (UTC hours)
SESSION_LONDON_START = 7
SESSION_LONDON_END = 16
SESSION_NY_START = 13
SESSION_NY_END = 22

# ============================================================================
# NEW VOLATILITY STATES CONFIGURATION (Phase 1.2)
# ============================================================================

# PRE_BREAKOUT_TENSION thresholds
BB_WIDTH_NARROW_THRESHOLD = 0.015  # 1.5% (bottom 20th percentile)
WICK_VARIANCE_INCREASE_THRESHOLD = 0.3  # 30% increase in rolling variance
INTRABAR_VOLATILITY_RISING_THRESHOLD = 0.2  # 20% increase in candle range/body ratio
BB_WIDTH_TREND_WINDOW = 10  # Candles to analyze for BB width trend

# POST_BREAKOUT_DECAY thresholds
ATR_SLOPE_DECLINE_THRESHOLD = -0.05  # ATR declining at 5% per period
ATR_ABOVE_BASELINE_THRESHOLD = 1.2  # ATR still > 1.2x baseline
POST_BREAKOUT_TIME_WINDOW = 30  # Minutes since breakout to consider "post-breakout"
ATR_SLOPE_WINDOW = 5  # Candles to calculate ATR slope

# FRAGMENTED_CHOP thresholds
WHIPSAW_WINDOW = 5  # Candles to check for whipsaw
WHIPSAW_MIN_DIRECTION_CHANGES = 3  # Minimum direction changes for whipsaw
MEAN_REVERSION_OSCILLATION_THRESHOLD = 0.5  # Price oscillating within 0.5 ATR of VWAP
LOW_MOMENTUM_ADX_THRESHOLD = 15  # ADX < 15 indicates low momentum

# SESSION_SWITCH_FLARE thresholds
SESSION_TRANSITION_WINDOW_MINUTES = 30  # Window before/after session change
VOLATILITY_SPIKE_THRESHOLD = 1.5  # ATR > 1.5x baseline for spike
FLARE_RESOLUTION_DECLINE_THRESHOLD = 0.1  # ATR declining 10% from spike = resolving
BASELINE_ATR_WINDOW = 20  # Candles to calculate baseline ATR

# ============================================================================
# NOTES
# ============================================================================

"""
These parameters use "parameter bands" (ranges) rather than fixed values
to prevent over-optimization. The thresholds are based on:
- ATR ratio: 1.2-1.4 range for transitional states
- Bollinger width: 1.5-1.8 multipliers
- ADX: 20-25 range for trend strength

All filters work together to prevent false regime declarations:
1. Persistence filter: Requires ≥3 candles
2. Inertia coefficient: Requires 5 candles minimum hold
3. Auto-cooldown: Ignores reversals within 2 candles
4. Volume confirmation: Requires 150% volume spike for volatile regimes

Multi-timeframe weighting emphasizes higher timeframes (H1 = 50%)
while still considering lower timeframes (M5 = 20%, M15 = 30%).
"""

