# File: config/settings.py
# ---------------------------------------------
# Position Watcher & Pending Config
# ---------------------------------------------
import os

LOG_LEVEL = "DEBUG"

DEFAULT_NOTIFY_CHAT_ID = 7550446596

# MT5 Files Directory
MT5_FILES_DIR = "./data/mt5_files"

# === ANCHOR: AUTO_WATCH_SETTINGS_START ===
# Symbols you want auto-watch to keep re-analysing for actionable entries
AUTO_WATCH_SYMBOLS = ["XAUUSDc", "BTCUSDc"]

# When a /trade finishes (any symbol), also bootstrap auto-watch for all above symbols
AUTO_WATCH_BOOTSTRAP_ON_TRADE = True

# When you arm a pending (any symbol), also bootstrap auto-watch for all above symbols
AUTO_WATCH_BOOTSTRAP_ON_PENDING = True
# === ANCHOR: AUTO_WATCH_SETTINGS_END ===

# === ANCHOR: SIGNAL_SCANNER_SETTINGS_START ===
# IMPROVED: Automatic signal detection settings
SIGNAL_SCANNER_ENABLED = True
SIGNAL_SCANNER_SYMBOLS = ["XAUUSDc", "BTCUSDc", "EURUSDc", "USDJPYc"]
SIGNAL_SCANNER_INTERVAL = 300  # Scan every 5 minutes
SIGNAL_SCANNER_MIN_CONFIDENCE = 75  # Only high-probability signals
SIGNAL_SCANNER_MIN_RR = 1.5  # Minimum risk:reward ratio
SIGNAL_SCANNER_COOLDOWN = 30  # Minutes between signals for same symbol
SIGNAL_SCANNER_MAX_PER_HOUR = 3  # Rate limiting
# === ANCHOR: SIGNAL_SCANNER_SETTINGS_END ===

# === Trade Setup Watcher Settings ===
SETUP_WATCHER_ENABLE = False  # Disabled by default (use signal scanner instead)
SETUP_WATCHER_MIN_CONFIDENCE = 75  # Minimum confidence for setup alerts

# -------------------- Pending orders --------------------
PENDINGS_PATH = "./data/pendings.json"
PENDING_DEFAULT_EXPIRY_MIN = 360  # 6 hours
MIN_RR_FOR_PENDINGS = 1.5  # auto-reject plans below this (unless low-RR allowed)

# === ANCHOR: PA20_FLAGS_START ===
# Master switch for price-action 2.0 context
PA20_ENABLED = True

# Retest entry when breakout quality is "weak"
PENDING_BQ_RETEST_ENABLED: bool = True

# Offer fakeout OCO (fade+protect) when breakout is "weak"/"failure" near boundary
PENDING_ENABLE_FAKEOUT_OCO: bool = True
# How close to a zone counts as "near" (in zone spans)
PENDING_FAKEOUT_MAX_SPANS = 1.2
# === ANCHOR: PA20_FLAGS_END ===

# Re-anchor parameters for LIMIT orders
PENDING_LIMIT_ENTRY_OFFSET_SPANS = 0.20
PENDING_LIMIT_SL_BEYOND_SPANS = 0.40

# === ANCHOR: PA20_STOP_FLAGS_START ===
# Re-anchoring and conversion knobs for STOP plans
PENDING_STOP_ENTRY_OFFSET_SPANS: float = (
    0.20  # how far beyond zone the stop trigger sits
)
PENDING_STOP_SL_BEYOND_SPANS: float = 0.40  # structure stop beyond the opposite side
PENDING_STOP_ATR_FLOOR_MULT: float = 0.80  # minimum risk as ATR multiple

# If RR still < floor, allow automatic conversion to retest stop
PENDING_STOP_ALLOW_RETEST_CONVERSION: bool = True

# Optional: enable measured-move TP nudge
PENDING_STOP_USE_MEASURED_MOVE: bool = False
PENDING_STOP_MEASURED_MOVE_MULT: float = 1.00
# === ANCHOR: PA20_STOP_FLAGS_END ===

# Allow saving and watching pending plans even if their calculated risk-to-reward ratio
# is below the floor specified above.
ALLOW_LOW_RR_PENDINGS = True
MAX_SPREAD_PCT_ATR = 0.35
# Prevent micro-ATR explosions in quiet hours (pending checks use M15 ATR with this floor)
ATR_FLOOR_TICKS = 3.0  # minimum ATR is N ticks (point * N)
# Cool-off to avoid one-tick spikes for *_STOP triggers
PENDING_COOLDOWN_M1_CLOSES = (
    1  # set 0 to disable; >0 requires N closed M1 bars beyond trigger
)
PENDING_COOLDOWN_BUFFER_PCT = 0.0  # extra buffer beyond trigger (e.g., 0.0005 = 5 bps)

# Volatility spike handling (on M1)
PENDING_SPIKE_TR_MULT = 1.8  # last M1 TR vs median threshold
PENDING_SPIKE_EXTRA_CLOSES = 1  # extra closed M1s when spike detected
PENDING_SPIKE_WIDEN_SL_FACTOR = 1.10  # widen SL distance by this factor when spike

# Risk & execution
RISK_ACCOUNT_SCALE = 0.01  # scale equity for cent accounts (USC etc.)
RISK_DEFAULT_PCT = 1.0  # default per-trade risk %
RISK_Lot_HARD_CAP = 0.05  # hard cap on computed lots (0 disables)
SPLIT_MAX_ORDERS = 3  # split large sizes across <= 3 orders
DEFAULT_DEVIATION = 10  # slippage tolerance (points in broker digits)

# === ANCHOR: INTELLIGENT_EXIT_RMAG_THRESHOLDS_START ===
# RMAG Stretch Thresholds (asset-specific)
# Thresholds determine when price is "stretched" enough to tighten exits
# Values are in standard deviations (σ) from EMA200/VWAP
RMAG_STRETCH_THRESHOLDS = {
    "BTCUSDc": 4.0,   # BTCUSD can stretch to 4σ normally (high volatility)
    "BTCUSD": 4.0,    # Handle both with/without 'c' suffix
    "XAUUSDc": 2.0,   # Gold more sensitive to stretch
    "XAUUSD": 2.0,
    "DEFAULT": 2.0    # Default for other assets
}
# === ANCHOR: INTELLIGENT_EXIT_RMAG_THRESHOLDS_END ===

# Dynamic deviation (market sends)
DEVIATION_POINTS_BASE = 10
DEVIATION_POINTS_PER_SPREAD = 0.5
DEVIATION_POINTS_MAX = 50

# Spread/vol filters
SPREAD_MAX_ATR_PCT = 0.25  # block if spread >= 25% of M5 ATR
SPREAD_MAX_POINTS = 0  # absolute cap in points (0 disables)

# -------------------- RAG memory & strategy selector paths --------------------
# Directory used to store stateful data (memory store, strategy selector thresholds,
# confidence calibrator).  Defaults to the data directory alongside this file.
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MEMORY_STORE_PATH = os.path.join(DATA_DIR, "memory_store.json")
STRATEGY_SELECTOR_PATH = os.path.join(DATA_DIR, "strategy_selector.json")
CALIBRATOR_PATH = os.path.join(DATA_DIR, "confidence_calibrator.json")

# Spread ratio used by guardrails.slippage_ok.  If not set, SPREAD_MAX_ATR_PCT is used.
MAX_SPREAD_PCT_ATR = SPREAD_MAX_ATR_PCT

# Risk-size pendings at trigger time (recommended)
PENDINGS_USE_RISK_SIZING = True

# -------------------- Pyramiding (optional) --------------------
POS_PYR_ENABLE = False  # turn on to allow adds
POS_PYR_STEPS_CSV = "1.0,2.0"  # add at +1R and +2R
POS_PYR_RISK_PCT = 0.5  # base risk % per add (pre-DD scaling)
POS_PYR_MAX_ADDS = 2  # cap per position
POS_PYR_USE_CURRENT_SL = True  # use current SL (safer) for adds

# -------------------- News integration --------------------
NEWS_EVENTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "news_events.json"
)
NEWS_HIGH_IMPACT_BEFORE_MIN = 30
NEWS_HIGH_IMPACT_AFTER_MIN = 30
NEWS_ULTRA_HIGH_BEFORE_MIN = 60
NEWS_ULTRA_HIGH_AFTER_MIN = 90
NEWS_CRYPTO_BEFORE_MIN = 15
NEWS_CRYPTO_AFTER_MIN = 30

# -------------------- Position Watcher (TP1/BE/Trailing/Backstop/Adaptive TP) --------------------
POS_WATCH_ENABLE = True
POS_WATCH_INTERVAL = 20  # seconds

# TP1 / BE
POS_TP1_R = 1.0  # trigger TP1/BE at +1R
POS_TP1_PART_CLOSE = 0.50  # close 50% at TP1 (0..1)
POS_BE_ENABLE = True
POS_BE_BUFFER_PCT = 0.0  # e.g., 0.0001

# Trailing mode
# "AUTO" (regime-aware), or force "R", "ATR", "CHAND", "HYBRID_MAX", "HYBRID_MIN"
POS_TRAIL_MODE = "AUTO"
POS_AUTO_TRAIL_TREND = "HYBRID_MAX"  # when AUTO and regime == TREND
POS_AUTO_TRAIL_RANGE = "R"  # when AUTO and regime == RANGE
POS_AUTO_TRAIL_VOL = "HYBRID_MAX"  # when AUTO and regime == VOLATILE

# Trailing params
POS_TRAIL_ATR_TF = "M5"
POS_TRAIL_ATR_PERIOD = 14
POS_TRAIL_ATR_MULT = 1.5
POS_CHAND_PERIOD = 22
POS_CHAND_MULT = 3.0
POS_TRAIL_DIST_R = 0.75
POS_TRAIL_THROTTLE_SEC = 5

# Regime re-evaluation (mid-trade) with hysteresis
POS_REGIME_REEVAL_ENABLE = True
POS_REGIME_REEVAL_TF = "M15"
POS_REGIME_REEVAL_EVERY_SEC = 120
POS_REGIME_CONFIRM_BARS = 2  # require N consecutive detections
POS_REGIME_MIN_SWITCH_MIN = 10  # min minutes between trail mode flips

# Fallback regime thresholds (used if utils.market_regime is unavailable)
POS_REGIME_ADX_PERIOD = 14
POS_REGIME_BB_PERIOD = 20
POS_REGIME_EMA_PERIOD = 50
POS_REGIME_EMA_SLOPE_BARS = 10
POS_REGIME_ADX_TREND = 25.0
POS_REGIME_ADX_RANGE = 20.0
POS_REGIME_EMA_SLOPE_THR = 0.0015  # ~0.15%
POS_REGIME_BB_RANGE_THR = 0.0040  # 0.4%

# Time-based exit backstop
POS_TIME_BACKSTOP_ENABLE = True
POS_TIME_BACKSTOP_TF = "M15"  # M1/M5/M15/M30/H1/H4
POS_TIME_BACKSTOP_BARS = 8  # e.g., 8 × M15 bars

# Adaptive TP by regime
POS_ADAPTIVE_TP_ENABLE = True
POS_TP_ONLY_EXTEND = True  # never lower TP in TREND/VOL regimes
POS_TP_ALLOW_TIGHTEN_IN_RANGE = True  # allow tighter TP in RANGE regime

# Trend regime TP targets
POS_TP_TREND_R = 2.0
POS_TP_TREND_ATR_MULT = 2.0

# Volatile/breakout regime TP targets
POS_TP_VOL_R = 2.5
POS_TP_VOL_ATR_MULT = 2.5

# Range regime TP targets (pick closer of BB inner offset vs ~1R)
POS_TP_RANGE_R = 1.0
POS_TP_RANGE_BB_PERIOD = 20
POS_TP_RANGE_BB_OFFSET = 0.15  # pull TP inside band by 15% of band width

# -------------------- Journal / risk --------------------
JOURNAL_DB_PATH = "./data/journal.sqlite"
JOURNAL_CSV_PATH = "./data/journal_events.csv"
JOURNAL_CSV_ENABLE = True
BOT_DB_PATH = "./data/bot.sqlite"

# Backwards compatibility: some modules still reference JOURNAL_DB and JOURNAL_CSV.
# Define these aliases as Path objects so handlers/journal.py can locate the files.
try:
    from pathlib import Path as _Path

    if "JOURNAL_DB" not in globals():
        JOURNAL_DB = _Path(JOURNAL_DB_PATH)
    if "JOURNAL_CSV" not in globals():
        JOURNAL_CSV = _Path(JOURNAL_CSV_PATH)
except Exception:
    # Ignore any errors during alias setup
    pass

# Correlation / Exposure guard
EXPO_CORR_THRESHOLD = 0.80  # treat |r| >= 0.80 as "strongly correlated"
EXPO_MAX_CORRELATED_SAME_DIR = (
    1  # block if already >=1 strong-correlated open in same direction
)
EXPO_CORR_RISK_REDUCE_FACTOR = 0.50  # if not blocked, trim risk by this factor
EXPO_CORR_TF = "M15"
EXPO_CORR_LOOKBACK_BARS = 300

EXPO_CCY_CAP_ENABLE = True  # cap open positions that touch same base/quote ccy
EXPO_MAX_OPEN_PER_CCY = 3  # e.g., max three positions involving USD (base or quote)

# Circuit breaker / Daily risk guard
CB_ENABLE = True
CB_MAX_DAILY_LOSS_R = 3.0  # trip if net daily R <= -3R
CB_MAX_CONSEC_LOSSES = 3
CB_MAX_DAILY_LOSS_PCT = 0.0  # 0 disables % guard
CB_COOL_OFF_MIN = 90  # minutes; 0 = hold until midnight (Africa/Johannesburg)
CB_STORE_PATH = "./data/circuit.json"

# Risk scaling by drawdown (compatible with journal_repo._parse_dd_tiers)
RISK_DD_LOOKBACK_DAYS = 180
# List of (drawdown_fraction, factor) sorted by threshold ascending.
# e.g., 0.05 = 5% DD → scale to 0.75×; 0.10 = 10% → 0.50×; 0.20 = 20% → 0.33×
RISK_DD_TIERS = [(0.05, 0.75), (0.10, 0.50), (0.15, 0.33), (0.20, 0.25)]
RISK_DD_MIN_FACTOR = 0.20
RISK_DD_MAX_FACTOR = 1.00
DD_BASE_EQUITY = 1000.0  # seed if no equity snapshots were recorded yet

# ---------------------------------------------
# Candlestick Geometry & Spike Management
# ---------------------------------------------

# General candle geometry
CANDLE_BODY_MIN_TREND_FRAC = 0.35  # prefer solid bodies for trend entries
CANDLE_BODY_MAX_PIN_FRAC = 0.35  # classify as pin/exhaustion if body below this
CANDLE_WICK_UP_EXH_FRAC = 0.60  # large upper wick (exhaustion candidate)
CANDLE_WICK_LO_EXH_FRAC = 0.60  # large lower wick (exhaustion candidate)
CANDLE_EDGE_BB_PROX_FRAC = 0.15  # “near” BB window (±15% of band distance)

# Spike detection (global defaults; can be overridden per symbol)
CANDLE_SPIKE_ATR_MULT = 1.8  # rng > 1.8×ATR14 => spike
CANDLE_SPIKE_Z = 2.0  # optional TR z-score alternative
CANDLE_SPIKE_LOOKBACK = 50  # z-score window

# Live management: wick-based exits/tightening
WICK_EXIT_ENABLE = True
WICK_EXIT_TFS = ["M5", "M15"]
WICK_STACK_CONFIRM_BARS = 2  # consecutive bars required for exit
WICK_EXIT_MODE = "tighten_then_exit"  # "tighten_then_exit" | "immediate_exit"
WICK_EXIT_PARTIAL_PCT = 0.5  # partial close % on first signal when tighten_then_exit
WICK_TIGHTEN_TO = "BE_OR_ATR"  # "BE_OR_ATR" | "ATR_ONLY" | "R_TRAIL"
WICK_BE_BUFFER_PCT = 0.05  # +5% of R buffer when tightening to BE

# Spike management modifiers (kept simple for now)
SPIKE_WITH_TREND_EXTEND_TP = True
SPIKE_AGAINST_TIGHTEN_SL = True
SPIKE_CONFIRM_BARS = 1

# --- Per-symbol/timeframe geometry overrides (from your tuner, 2025-08-12) ---
# Structure: WICK_GEOMETRY_OVERRIDES[symbol][tf] = dict(wick_exh_frac=..., body_max_frac=..., bb_near_frac=...)
WICK_GEOMETRY_OVERRIDES = {
    "XAUUSDc": {
        "M5": {"wick_exh_frac": 0.55, "body_max_frac": 0.35, "bb_near_frac": 0.20},
        "M15": {"wick_exh_frac": 0.65, "body_max_frac": 0.40, "bb_near_frac": 0.10},
    },
    "BTCUSDc": {
        "M5": {"wick_exh_frac": 0.55, "body_max_frac": 0.40, "bb_near_frac": 0.10},
        "M15": {"wick_exh_frac": 0.55, "body_max_frac": 0.40, "bb_near_frac": 0.20},
    },
}

# --- Per-session overrides for candle geometry ---
# Extend wick/spike thresholds by trading session.  The keys should
# follow the structure {symbol: {tf: {session: {wick_exh_frac, body_max_frac,
# bb_near_frac}}}}.  A "session" is one of 'ASIA', 'LONDON', 'NY'.
# You can tune these per instrument/timeframe to reflect higher
# volatility during London/NY sessions and quieter Asian trading.
# If a session override is missing, fall back to the per‑symbol/timeframe
# override and then the global default defined above.
WICK_SESSION_OVERRIDES = {
    # Example:
    # "XAUUSDc": {
    #     "M5": {
    #         "ASIA": {"wick_exh_frac": 0.50, "body_max_frac": 0.35, "bb_near_frac": 0.25},
    #         "LONDON": {"wick_exh_frac": 0.60, "body_max_frac": 0.40, "bb_near_frac": 0.20},
    #         "NY": {"wick_exh_frac": 0.65, "body_max_frac": 0.45, "bb_near_frac": 0.15},
    #     },
    # },
}

# Trailing and BE buffers by session.  Use these to adjust the
# aggressiveness of break‑even moves and ATR multipliers during different
# sessions.  Format: {session: value}.  If a session is missing, the
# global POS_BE_BUFFER_PCT or POS_TRAIL_ATR_MULT is used.
POS_BE_BUFFER_PCT_BY_SESSION = {
    # e.g., "ASIA": 0.0010, "LONDON": 0.0005, "NY": 0.0000
}
POS_TRAIL_ATR_MULT_BY_SESSION = {
    # e.g., "ASIA": 1.2, "LONDON": 1.5, "NY": 1.8
}


def get_trading_session(ts, tz: str = "Africa/Johannesburg") -> str:
    """
    Return the trading session ('ASIA', 'LONDON', 'NY') for a given
    timestamp.  The timestamp may be a naive or timezone‑aware
    datetime or pandas Timestamp.  Sessions are determined based on
    local time in the provided timezone (default: Africa/Johannesburg,
    UTC+2).  Approximate boundaries:
      - ASIA: 00:00–08:00 local
      - LONDON: 08:00–16:00 local
      - NY: 16:00–24:00 local
    """
    try:
        import pandas as pd  # type: ignore
        import pytz  # type: ignore

        if ts is None:
            return "UNKNOWN"
        # Convert to pandas Timestamp for convenience
        if not isinstance(ts, pd.Timestamp):
            try:
                ts = pd.Timestamp(ts)
            except Exception:
                return "UNKNOWN"
        # Localise/convert to timezone
        try:
            tzinfo = pytz.timezone(tz)
            if ts.tzinfo is None:
                ts_local = ts.tz_localize(tzinfo)
            else:
                ts_local = ts.tz_convert(tzinfo)
        except Exception:
            ts_local = ts
        hour = int(ts_local.hour)
        if 0 <= hour < 8:
            return "ASIA"
        if 8 <= hour < 16:
            return "LONDON"
        return "NY"
    except Exception:
        return "UNKNOWN"


def get_wick_geometry_for_session(symbol: str, tf: str, session: str | None = None):
    """
    Return tuned (wick_exh_frac, body_max_frac, bb_near_frac) for a
    given (symbol, timeframe, session).  Layering precedence:
      1. Session‑specific override (WICK_SESSION_OVERRIDES)
      2. Per‑symbol/timeframe override (WICK_GEOMETRY_OVERRIDES)
      3. Global defaults (CANDLE_WICK_UP_EXH_FRAC, CANDLE_BODY_MAX_PIN_FRAC, CANDLE_EDGE_BB_PROX_FRAC)

    If session is None or no override exists, falls back to the next layer.
    """
    tf = (tf or "").upper()
    sess = (session or "").upper() if session else None
    # Session override
    if sess:
        try:
            sym_map = (WICK_SESSION_OVERRIDES or {}).get(symbol, {}) or {}
            tf_map = sym_map.get(tf) or {}
            sess_map = tf_map.get(sess) or {}
            if sess_map:
                return (
                    float(sess_map.get("wick_exh_frac", CANDLE_WICK_UP_EXH_FRAC)),
                    float(sess_map.get("body_max_frac", CANDLE_BODY_MAX_PIN_FRAC)),
                    float(sess_map.get("bb_near_frac", CANDLE_EDGE_BB_PROX_FRAC)),
                )
        except Exception:
            pass
    # Symbol/timeframe override
    try:
        sym_map = (WICK_GEOMETRY_OVERRIDES or {}).get(symbol, {}) or {}
        m = sym_map.get(tf)
        if m:
            return (
                float(m.get("wick_exh_frac", CANDLE_WICK_UP_EXH_FRAC)),
                float(m.get("body_max_frac", CANDLE_BODY_MAX_PIN_FRAC)),
                float(m.get("bb_near_frac", CANDLE_EDGE_BB_PROX_FRAC)),
            )
    except Exception:
        pass
    # Global defaults
    return (
        float(CANDLE_WICK_UP_EXH_FRAC),
        float(CANDLE_BODY_MAX_PIN_FRAC),
        float(CANDLE_EDGE_BB_PROX_FRAC),
    )


def get_wick_geometry_for(symbol: str, tf: str):
    """
    Return tuned (wick_exh_frac, body_max_frac, bb_near_frac) for (symbol, tf),
    or global defaults if not present.
    """
    tf = (tf or "").upper()
    sym_map = (WICK_GEOMETRY_OVERRIDES or {}).get(symbol, {})
    m = sym_map.get(tf)
    if m:
        return (
            float(m.get("wick_exh_frac", CANDLE_WICK_UP_EXH_FRAC)),
            float(m.get("body_max_frac", CANDLE_BODY_MAX_PIN_FRAC)),
            float(m.get("bb_near_frac", CANDLE_EDGE_BB_PROX_FRAC)),
        )
    return (
        float(CANDLE_WICK_UP_EXH_FRAC),
        float(CANDLE_BODY_MAX_PIN_FRAC),
        float(CANDLE_EDGE_BB_PROX_FRAC),
    )


# --- Per-symbol spike & partial overrides ---
# Example (uncomment and adjust):
# WICK_SYMBOL_OVERRIDES = {
#     "BTCUSDc": {"spike_mult": 2.2, "partial_pct": 0.40},
#     "XAUUSDc": {"spike_mult": 1.9, "partial_pct": 0.50},
# }
WICK_SYMBOL_OVERRIDES = {}


def get_wick_symbol_overrides(symbol: str):
    """Return (spike_mult, partial_pct) for a symbol; fall back to global defaults."""
    d = (WICK_SYMBOL_OVERRIDES or {}).get(symbol, {}) or {}
    spike = float(d.get("spike_mult", CANDLE_SPIKE_ATR_MULT))
    part = float(d.get("partial_pct", WICK_EXIT_PARTIAL_PCT))
    return spike, part


# === ANCHOR: POSWATCH_NOTIFY_SETTINGS_START ===
# Turn on/off live-trade notifications
POS_WATCH_NOTIFY = True

# Which events to notify about
POS_WATCH_NOTIFY_EVENTS = {
    "sl_adjust",
    "tp_adjust",
    "breakeven_set",
    "trail_update",
    "partial_tp",
    "close_by_rule",
}

# Minimum seconds between notifications for the same position id (anti-spam)
POS_WATCH_NOTIFY_THROTTLE_SEC = 30

# Fallback chat to notify if a position doesn’t carry a chat id (optional)
DEFAULT_NOTIFY_CHAT_ID = None  # e.g., 123456789
# === ANCHOR: POSWATCH_NOTIFY_SETTINGS_END ===

TIME_STOP_BARS   = {"M5": 10, "M15": 8, "M30": 6, "H1": 4, "H4": 3}
TIME_STOP_ACTION = "tighten"       # "tighten" | "close"

PARTIAL_TP = {
    "enabled": True,
    "fraction": 0.5,
    "rr_first": 1.0,               # start of window
    "rr_max": 1.2,                 # end of window (hysteresis guards repeats)
}

TRAIL = {
    "atr_period": 14,
    "atr_mult": 3.0,
    "atr_mult_tight": 2.0,         # after +1.5R
}

EARLY_EXIT = {
    "enabled": True,
    "min_rr": 0.5,
    "action": "tighten",           # or "close"
}

SESSION_DECAY = {
    "enabled": True,
    "dead_sessions": ["ASIA_LATE", "NY_LATE"],
    "stall_bars": 2,
    "halve_tp": True,              # else close on stall
}

DEFAULT_TF = "M5"                  # used if we can’t infer TF from position comment
REQUIRE_SWING_BE = True            # allow 2 favorable swings → BE
JOURNAL_ACTIONS = True             # log actions to JournalRepo if available

USE_TRAILING_STOPS = False  # DISABLED - Use only intelligent exits
TRAILING_CHECK_INTERVAL = 60  # seconds

# === ANCHOR: INTELLIGENT_EXITS_SETTINGS_START ===
# Intelligent Exit Management - Auto-enable for all positions
INTELLIGENT_EXITS_AUTO_ENABLE = True  # Auto-enable for all new positions (including triggered pending orders)
INTELLIGENT_EXITS_BREAKEVEN_PCT = 30.0  # Move SL to breakeven at 30% of potential profit (0.3R)
INTELLIGENT_EXITS_PARTIAL_PCT = 60.0  # Take partial profit at 60% of potential profit (0.6R)
INTELLIGENT_EXITS_PARTIAL_CLOSE_PCT = 50.0  # Close 50% of position at partial level
INTELLIGENT_EXITS_VIX_THRESHOLD = 18.0  # VIX level above which to widen stops
INTELLIGENT_EXITS_USE_HYBRID_STOPS = True  # Use hybrid ATR+VIX for stop adjustment
INTELLIGENT_EXITS_TRAILING_ENABLED = True  # Enable ATR trailing stops after breakeven
# === ANCHOR: INTELLIGENT_EXITS_SETTINGS_END ===

# === ANCHOR: INTELLIGENT_EXIT_SYMBOL_PARAMS_START ===
# Symbol-Specific Intelligent Exit Parameters (Phase 11)
# Optimized for each asset's volatility profile
INTELLIGENT_EXIT_SYMBOL_PARAMS = {
    "BTCUSDc": {
        "trailing_atr_multiplier": 2.0,      # Wider trailing (high volatility)
        "breakeven_buffer_atr_mult": 0.5,     # Larger buffer (0.5x ATR)
        "atr_timeframe": "M15",               # M15 ATR for BTC
        "trailing_timeframe": "M5",           # M5 for trailing updates
        "min_sl_change_pct": 0.1,             # 0.1% minimum change
        "session_adjustments": {
            "ASIAN": {"trailing_mult": 2.2, "buffer_mult": 0.6},  # Wider in Asia
            "LONDON": {"trailing_mult": 2.0, "buffer_mult": 0.5},
            "NY": {"trailing_mult": 2.0, "buffer_mult": 0.5},
            "OVERLAP": {"trailing_mult": 1.8, "buffer_mult": 0.4}  # Tighter in overlap
        }
    },
    "BTCUSD": {  # Handle without 'c' suffix
        "trailing_atr_multiplier": 2.0,
        "breakeven_buffer_atr_mult": 0.5,
        "atr_timeframe": "M15",
        "trailing_timeframe": "M5",
        "min_sl_change_pct": 0.1
    },
    "XAUUSDc": {
        "trailing_atr_multiplier": 1.5,      # Standard trailing
        "breakeven_buffer_atr_mult": 0.3,    # Standard buffer
        "atr_timeframe": "M15",               # M15 ATR for XAU
        "trailing_timeframe": "M5",
        "min_sl_change_pct": 0.08,            # 0.08% minimum (tighter)
        "session_adjustments": {
            "ASIAN": {"trailing_mult": 1.8, "buffer_mult": 0.4},  # Wider in Asia
            "LONDON": {"trailing_mult": 1.5, "buffer_mult": 0.3},
            "NY": {"trailing_mult": 1.5, "buffer_mult": 0.3},
            "OVERLAP": {"trailing_mult": 1.3, "buffer_mult": 0.25}  # Tighter in overlap
        }
    },
    "XAUUSD": {
        "trailing_atr_multiplier": 1.5,
        "breakeven_buffer_atr_mult": 0.3,
        "atr_timeframe": "M15",
        "trailing_timeframe": "M5",
        "min_sl_change_pct": 0.08
    },
    "EURUSDc": {
        "trailing_atr_multiplier": 1.2,      # Tighter trailing (lower volatility)
        "breakeven_buffer_atr_mult": 0.2,     # Smaller buffer (0.2x ATR)
        "atr_timeframe": "M15",
        "trailing_timeframe": "M5",
        "min_sl_change_pct": 0.05,            # 0.05% minimum (very tight)
        "session_adjustments": {
            "ASIAN": {"trailing_mult": 1.4, "buffer_mult": 0.25},
            "LONDON": {"trailing_mult": 1.2, "buffer_mult": 0.2},
            "NY": {"trailing_mult": 1.2, "buffer_mult": 0.2},
            "OVERLAP": {"trailing_mult": 1.1, "buffer_mult": 0.15}
        }
    },
    "EURUSD": {
        "trailing_atr_multiplier": 1.2,
        "breakeven_buffer_atr_mult": 0.2,
        "atr_timeframe": "M15",
        "trailing_timeframe": "M5",
        "min_sl_change_pct": 0.05
    },
    "GBPUSDc": {
        "trailing_atr_multiplier": 1.3,      # Slightly wider than EURUSD
        "breakeven_buffer_atr_mult": 0.25,    # Slightly larger buffer
        "atr_timeframe": "M15",
        "trailing_timeframe": "M5",
        "min_sl_change_pct": 0.06,
        "session_adjustments": {
            "ASIAN": {"trailing_mult": 1.5, "buffer_mult": 0.3},
            "LONDON": {"trailing_mult": 1.3, "buffer_mult": 0.25},
            "NY": {"trailing_mult": 1.3, "buffer_mult": 0.25},
            "OVERLAP": {"trailing_mult": 1.2, "buffer_mult": 0.2}
        }
    },
    "GBPUSD": {
        "trailing_atr_multiplier": 1.3,
        "breakeven_buffer_atr_mult": 0.25,
        "atr_timeframe": "M15",
        "trailing_timeframe": "M5",
        "min_sl_change_pct": 0.06
    },
    "USDJPYc": {
        "trailing_atr_multiplier": 1.2,
        "breakeven_buffer_atr_mult": 0.2,
        "atr_timeframe": "M15",
        "trailing_timeframe": "M5",
        "min_sl_change_pct": 0.05,
        "session_adjustments": {
            "ASIAN": {"trailing_mult": 1.4, "buffer_mult": 0.25},
            "LONDON": {"trailing_mult": 1.2, "buffer_mult": 0.2},
            "NY": {"trailing_mult": 1.2, "buffer_mult": 0.2},
            "OVERLAP": {"trailing_mult": 1.1, "buffer_mult": 0.15}
        }
    },
    "USDJPY": {
        "trailing_atr_multiplier": 1.2,
        "breakeven_buffer_atr_mult": 0.2,
        "atr_timeframe": "M15",
        "trailing_timeframe": "M5",
        "min_sl_change_pct": 0.05
    },
    "DEFAULT": {
        "trailing_atr_multiplier": 1.5,      # Default for unknown symbols
        "breakeven_buffer_atr_mult": 0.3,    # Default buffer
        "atr_timeframe": "M15",
        "trailing_timeframe": "M5",
        "min_sl_change_pct": 0.05
    }
}
# === ANCHOR: INTELLIGENT_EXIT_SYMBOL_PARAMS_END ===

# ===== LOSS CUTTER SETTINGS =====
# Early exit thresholds
POS_EARLY_EXIT_R = -0.8  # R-multiple threshold for early exit
POS_EARLY_EXIT_SCORE = 0.65  # Risk score threshold (0-1)

# Time-based backstop
POS_TIME_BACKSTOP_ENABLE = True  # Enable time backstop
POS_TIME_BACKSTOP_BARS = 10  # Bars before time decay triggers

# Multi-timeframe invalidation
POS_INVALIDATION_EXIT_ENABLE = True  # Enable invalidation exits

# Spread/ATR gating
POS_SPREAD_ATR_CLOSE_CAP = 0.40  # Max spread/ATR ratio for closing (0.40 = 40%)

# Closing reliability
POS_CLOSE_RETRY_MAX = 3  # Maximum retry attempts
POS_CLOSE_BACKOFF_MS = "300,600,900"  # Backoff delays in milliseconds (comma-separated)



# ===== OCO BRACKET SETTINGS =====
# Enable/disable OCO (One-Cancels-Other) bracket orders
USE_OCO_BRACKETS = False  # Disabled by default (experimental feature)
