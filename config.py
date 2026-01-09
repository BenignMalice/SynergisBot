# =====================================
# config.py
# =====================================
from __future__ import annotations
import os
import logging
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv, find_dotenv

ROOT = Path(__file__).parent

# Load .env reliably even if the CWD isn't the project root
env_path = find_dotenv(usecwd=True)
if env_path:
    print(f"[CONFIG] Loading .env from: {env_path}")
    load_dotenv(env_path, override=True)
else:
    # Fallback: try to load .env from the project root
    project_root = Path(__file__).parent
    env_file = project_root / ".env"
    if env_file.exists():
        print(f"[CONFIG] Loading .env from project root: {env_file}")
        load_dotenv(env_file, override=True)
    else:
        print("[CONFIG] No .env file found")

# Force reload environment variables after loading .env
# This ensures all environment variables are available when Settings is instantiated
import os
os.environ.update(os.environ)

# Helpful: confirm whether the key was seen (masking the value)
logger = logging.getLogger(__name__)
_raw_key = os.getenv("OPENAI_API_KEY", "")
_telegram_token = os.getenv("TELEGRAM_TOKEN", "")
print(f"[CONFIG] OPENAI key loaded: {'yes' if _raw_key else 'NO'}")
print(f"[CONFIG] TELEGRAM_TOKEN loaded: {'yes' if _telegram_token else 'NO'}")
if _raw_key:
    print(f"[CONFIG] OPENAI key length: {len(_raw_key)}")
if _telegram_token:
    print(f"[CONFIG] TELEGRAM_TOKEN length: {len(_telegram_token)}")
logger.info(
    "OPENAI key loaded: %s", ("yes (len=%d)" % len(_raw_key)) if _raw_key else "NO"
)

NEWS_EVENTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "news_events.json"
)


def _as_bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}


def _expand_path(p: str) -> str:
    # Expand %VAR% and ~ on Windows/Unix
    return os.path.expanduser(os.path.expandvars(p))


class Settings:
    def __init__(self):
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        # SPEED: Use gpt-4o-mini for fast analysis (~1-2s) or gpt-4o for balanced speed/quality
        # Available models: "gpt-4o-mini" (fastest), "gpt-4o", "gpt-4-turbo", "gpt-5-thinking" (slowest)
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        # Twelve Data API key for DXY/indices (correlation filter) - OPTIONAL (using Yahoo Finance)
        self.TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")
        
        # Alpha Vantage API key for economic indicators and news sentiment
        self.ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
        
        # FRED API key for economic data (breakeven rate, Fed funds rate, 2Y yield)
        self.FRED_API_KEY = os.getenv("FRED_API_KEY", "")
        
        # IMPROVED: Prompt Router configuration
        self.USE_PROMPT_ROUTER = _as_bool(os.getenv("USE_PROMPT_ROUTER", "1"))  # Enable router by default
        
        # IMPROVED Phase 4.2: Session-aware decision making
        self.SESSION_RULES_ENABLED = _as_bool(os.getenv("SESSION_RULES_ENABLED", "1"))  # Enable session rules by default
        
        # Add all the remaining class variables as instance variables
        # This ensures all environment variables are loaded at instantiation time
        self.USE_STRUCTURE_SL = _as_bool(os.getenv("USE_STRUCTURE_SL", "1"))
        self.USE_ADAPTIVE_TP = _as_bool(os.getenv("USE_ADAPTIVE_TP", "1"))
        self.USE_TRAILING_STOPS = _as_bool(os.getenv("USE_TRAILING_STOPS", "1"))
        self.USE_OCO_BRACKETS = _as_bool(os.getenv("USE_OCO_BRACKETS", "1"))
        self.TRAILING_CHECK_INTERVAL = int(os.getenv("TRAILING_CHECK_INTERVAL", "15"))
        self.USE_PARALLEL_ANALYSIS = _as_bool(os.getenv("USE_PARALLEL_ANALYSIS", "0"))
        self.USE_FAST_FEATURES = _as_bool(os.getenv("USE_FAST_FEATURES", "0"))
        self.PARALLEL_TIMEOUT = float(os.getenv("PARALLEL_TIMEOUT", "15.0"))
        self.MT5_WINDOW_TITLE = os.getenv("MT5_WINDOW_TITLE", "Exness")
        self.AHK_EXE = _expand_path(os.getenv("AHK_EXE", r"C:\Program Files\AutoHotkey\AutoHotkey.exe"))
        self.AHK_SCRIPT = _expand_path(os.getenv("AHK_SCRIPT", str(ROOT / "arrange_charts.ahk")))
        self.AUTO_ARRANGE = _as_bool(os.getenv("AUTO_ARRANGE", "1"))
        self.MT5_FILES_DIR = Path(_expand_path(os.getenv("MT5_FILES_DIR", r"C:\Users\Public\Documents\MetaQuotes\Terminal\Common\Files")))
        self.DEFAULT_LOT_SIZE = float(os.getenv("DEFAULT_LOT_SIZE", "0.01"))
        self.SLIPPAGE_POINTS = int(os.getenv("SLIPPAGE_POINTS", "50"))
        self.MAGIC_NUMBER = int(os.getenv("MAGIC_NUMBER", "202510"))
        self.RISK_PCT = float(os.getenv("RISK_PCT", "0"))
        self.ALWAYS_SHOW_EXEC = _as_bool(os.getenv("ALWAYS_SHOW_EXEC", "0"))
        self.JOURNAL_ENABLE = _as_bool(os.getenv("JOURNAL_ENABLE", "1"))
        self.JOURNAL_DIR = Path(_expand_path(os.getenv("JOURNAL_DIR", str(ROOT / "journal"))))
        self.JOURNAL_CSV = Path(_expand_path(os.getenv("JOURNAL_CSV", str(ROOT / "journal" / "trades.csv"))))
        self.JOURNAL_DB = Path(_expand_path(os.getenv("JOURNAL_DB", str(ROOT / "journal" / "trades.sqlite"))))
        
        # TRADE TYPE CLASSIFICATION (AIES Phase 1 MVP) - Set as instance variable
        self.ENABLE_TRADE_TYPE_CLASSIFICATION = _as_bool(os.getenv("ENABLE_TRADE_TYPE_CLASSIFICATION", "0"))  # Default: OFF for safety
    
    # IMPROVED Phase 4.4: Execution Upgrades
    USE_STRUCTURE_SL: bool = _as_bool(os.getenv("USE_STRUCTURE_SL", "1"))  # Enable structure-aware SL
    USE_ADAPTIVE_TP: bool = _as_bool(os.getenv("USE_ADAPTIVE_TP", "1"))  # Enable adaptive TP
    USE_TRAILING_STOPS: bool = _as_bool(os.getenv("USE_TRAILING_STOPS", "1"))  # Enable trailing stops
    USE_OCO_BRACKETS: bool = _as_bool(os.getenv("USE_OCO_BRACKETS", "1"))  # FIXED: OCO bracket SL/TP calculation corrected
    TRAILING_CHECK_INTERVAL: int = int(os.getenv("TRAILING_CHECK_INTERVAL", "15"))  # Trailing stop check interval (seconds)
    
    # SPEED OPTIMIZATION: Advanced performance options
    USE_PARALLEL_ANALYSIS: bool = _as_bool(os.getenv("USE_PARALLEL_ANALYSIS", "0"))  # Run Router + Fallback in parallel (experimental)
    USE_FAST_FEATURES: bool = _as_bool(os.getenv("USE_FAST_FEATURES", "0"))  # Use lightweight feature computation
    PARALLEL_TIMEOUT: float = float(os.getenv("PARALLEL_TIMEOUT", "15.0"))  # Timeout for parallel analysis (seconds)

    MT5_WINDOW_TITLE: str = os.getenv("MT5_WINDOW_TITLE", "Exness")
    AHK_EXE: str = _expand_path(
        os.getenv("AHK_EXE", r"C:\Program Files\AutoHotkey\AutoHotkey.exe")
    )
    AHK_SCRIPT: str = _expand_path(
        os.getenv("AHK_SCRIPT", str(ROOT / "arrange_charts.ahk"))
    )
    AUTO_ARRANGE: bool = _as_bool(os.getenv("AUTO_ARRANGE", "1"))

    MT5_FILES_DIR: Path = Path(
        _expand_path(
            os.getenv(
                "MT5_FILES_DIR",
                r"C:\Users\Public\Documents\MetaQuotes\Terminal\Common\Files",
            )
        )
    )

    DEFAULT_LOT_SIZE: float = float(os.getenv("DEFAULT_LOT_SIZE", "0.01"))
    SLIPPAGE_POINTS: int = int(os.getenv("SLIPPAGE_POINTS", "50"))
    MAGIC_NUMBER: int = int(os.getenv("MAGIC_NUMBER", "202510"))
    RISK_PCT: float = float(os.getenv("RISK_PCT", "0"))

    # Show Execute button even on HOLD (useful while testing LLM)
    ALWAYS_SHOW_EXEC: bool = _as_bool(os.getenv("ALWAYS_SHOW_EXEC", "0"))

    JOURNAL_ENABLE: bool = _as_bool(os.getenv("JOURNAL_ENABLE", "1"))
    JOURNAL_DIR: Path = Path(
        _expand_path(os.getenv("JOURNAL_DIR", str(ROOT / "journal")))
    )
    JOURNAL_CSV: Path = Path(
        _expand_path(os.getenv("JOURNAL_CSV", str(ROOT / "journal" / "trades.csv")))
    )
    JOURNAL_DB: Path = Path(
        _expand_path(os.getenv("JOURNAL_DB", str(ROOT / "journal" / "trades.sqlite")))
    )
    NEWS_EVENTS_PATH: str = os.path.join(
        os.path.dirname(__file__), "..", "data", "news_events.json"
    )

    # Seconds between management loop iterations (your manager uses this)
    CLOSE_WATCH_INTERVAL: int = int(os.getenv("CLOSE_WATCH_INTERVAL", "30"))

    # Path to your fundamentals doc (if you use it)
    FUND_DOCX_PATH: Path = Path(
        _expand_path(
            os.getenv(
                "FUND_DOCX_PATH", str(ROOT / "Daily_Analysis_XAUUSD_BTCUSD_ETHUSD.docx")
            )
        )
    )
    
    # AUTOMATED LOSS-CUTTING CONFIGURATION
    # Early exit thresholds (IMPROVED: More aggressive to prevent losses like -15 pips)
    POS_EARLY_EXIT_R: float = float(os.getenv("POS_EARLY_EXIT_R", "-0.5"))  # R-multiple threshold for early exit (was -0.8)
    POS_EARLY_EXIT_SCORE: float = float(os.getenv("POS_EARLY_EXIT_SCORE", "0.55"))  # Confluence risk score threshold (was 0.65)
    
    # INTELLIGENT EXIT MANAGEMENT - AUTO-ENABLE
    INTELLIGENT_EXITS_AUTO_ENABLE: bool = _as_bool(os.getenv("INTELLIGENT_EXITS_AUTO_ENABLE", "1"))  # Auto-enable for all trades
    INTELLIGENT_EXITS_BREAKEVEN_PCT: float = float(os.getenv("INTELLIGENT_EXITS_BREAKEVEN_PCT", "30.0"))  # 30% of potential profit
    INTELLIGENT_EXITS_PARTIAL_PCT: float = float(os.getenv("INTELLIGENT_EXITS_PARTIAL_PCT", "60.0"))  # 60% of potential profit
    INTELLIGENT_EXITS_PARTIAL_CLOSE_PCT: float = float(os.getenv("INTELLIGENT_EXITS_PARTIAL_CLOSE_PCT", "50.0"))  # Close 50%
    INTELLIGENT_EXITS_VIX_THRESHOLD: float = float(os.getenv("INTELLIGENT_EXITS_VIX_THRESHOLD", "18.0"))  # VIX spike level
    INTELLIGENT_EXITS_USE_HYBRID_STOPS: bool = _as_bool(os.getenv("INTELLIGENT_EXITS_USE_HYBRID_STOPS", "1"))  # Hybrid ATR+VIX
    INTELLIGENT_EXITS_TRAILING_ENABLED: bool = _as_bool(os.getenv("INTELLIGENT_EXITS_TRAILING_ENABLED", "1"))  # Continuous trailing
    
    # TRADE TYPE CLASSIFICATION (AIES Phase 1 MVP)
    # Feature flag for Adaptive Intelligent Exit System - classifies trades as SCALP vs INTRADAY
    # When enabled: SCALP trades use 25%/40%/70% parameters, INTRADAY uses 30%/60%/50%
    # When disabled: All trades use standard INTRADAY parameters (30%/60%/50%)
    # Default: False (disabled) for safe rollout - enable after testing
    ENABLE_TRADE_TYPE_CLASSIFICATION: bool = _as_bool(os.getenv("ENABLE_TRADE_TYPE_CLASSIFICATION", "0"))  # Default: OFF for safety
    
    # CLASSIFICATION METRICS & REPORTING
    # Enable metrics collection and reporting for trade classification system
    CLASSIFICATION_METRICS_ENABLED: bool = _as_bool(os.getenv("CLASSIFICATION_METRICS_ENABLED", "1"))  # Enable metrics by default
    CLASSIFICATION_METRICS_DISCORD_DAILY: bool = _as_bool(os.getenv("CLASSIFICATION_METRICS_DISCORD_DAILY", "1"))  # Daily Discord summary at 17:00 UTC
    CLASSIFICATION_METRICS_DISCORD_WEEKLY: bool = _as_bool(os.getenv("CLASSIFICATION_METRICS_DISCORD_WEEKLY", "1"))  # Weekly Discord summary (Sunday 17:00 UTC)
    CLASSIFICATION_METRICS_LOG_SUMMARY: bool = _as_bool(os.getenv("CLASSIFICATION_METRICS_LOG_SUMMARY", "1"))  # Daily log summary (after 100 trades)
    CLASSIFICATION_METRICS_WINDOW_SIZE: int = int(os.getenv("CLASSIFICATION_METRICS_WINDOW_SIZE", "100"))  # Rolling window size for log summary
    CLASSIFICATION_METRICS_DISCORD_DAILY_SCHEDULE: str = os.getenv("CLASSIFICATION_METRICS_DISCORD_DAILY_SCHEDULE", "0 17 * * *")  # Daily at 17:00 UTC (cron format)
    CLASSIFICATION_METRICS_DISCORD_WEEKLY_SCHEDULE: str = os.getenv("CLASSIFICATION_METRICS_DISCORD_WEEKLY_SCHEDULE", "0 17 * * 0")  # Sunday at 17:00 UTC (cron format)
    
    # Time-based backstop
    POS_TIME_BACKSTOP_ENABLE: bool = _as_bool(os.getenv("POS_TIME_BACKSTOP_ENABLE", "1"))
    POS_TIME_BACKSTOP_BARS: int = int(os.getenv("POS_TIME_BACKSTOP_BARS", "10"))  # Bars to wait before time decay
    
    # Multi-timeframe invalidation
    POS_INVALIDATION_EXIT_ENABLE: bool = _as_bool(os.getenv("POS_INVALIDATION_EXIT_ENABLE", "1"))
    
    # Spread/ATR gating
    POS_SPREAD_ATR_CLOSE_CAP: float = float(os.getenv("POS_SPREAD_ATR_CLOSE_CAP", "0.40"))  # Max spread/ATR ratio for closing
    
    # Closing reliability
    POS_CLOSE_RETRY_MAX: int = int(os.getenv("POS_CLOSE_RETRY_MAX", "3"))  # Max retry attempts
    POS_CLOSE_BACKOFF_MS: str = os.getenv("POS_CLOSE_BACKOFF_MS", "300,600,900")  # Exponential backoff delays
    
    # TRADE SETUP WATCHER CONFIGURATION
    # Setup monitoring
    SETUP_WATCHER_ENABLE: bool = _as_bool(os.getenv("SETUP_WATCHER_ENABLE", "1"))  # Enable setup watcher
    SETUP_WATCHER_INTERVAL: int = int(os.getenv("SETUP_WATCHER_INTERVAL", "30"))  # Check interval in seconds
    SETUP_WATCHER_MIN_CONFIDENCE: int = int(os.getenv("SETUP_WATCHER_MIN_CONFIDENCE", "70"))  # Min confidence for alerts
    
    # Setup conditions
    SETUP_BUY_RSI_MIN: int = int(os.getenv("SETUP_BUY_RSI_MIN", "50"))  # Min RSI for BUY setups
    SETUP_SELL_RSI_MAX: int = int(os.getenv("SETUP_SELL_RSI_MAX", "50"))  # Max RSI for SELL setups
    SETUP_ADX_MIN: int = int(os.getenv("SETUP_ADX_MIN", "25"))  # Min ADX for trend strength
    SETUP_ATR_MIN: float = float(os.getenv("SETUP_ATR_MIN", "5.0"))  # Min ATR for volatility
    
    # IMPROVED: Entry confirmation requirements (prevent bad entries)
    SETUP_REQUIRE_PULLBACK: bool = _as_bool(os.getenv("SETUP_REQUIRE_PULLBACK", "1"))  # Wait for pullback to EMA
    SETUP_MIN_CANDLES_FROM_EXTREME: int = int(os.getenv("SETUP_MIN_CANDLES_FROM_EXTREME", "3"))  # Bars since high/low
    SETUP_MAX_RSI_FOR_BUY: int = int(os.getenv("SETUP_MAX_RSI_FOR_BUY", "70"))  # Don't buy when overbought
    SETUP_MIN_RSI_FOR_SELL: int = int(os.getenv("SETUP_MIN_RSI_FOR_SELL", "30"))  # Don't sell when oversold
    
    # Risk management
    SETUP_STOP_ATR_MULT: float = float(os.getenv("SETUP_STOP_ATR_MULT", "2.0"))  # Stop loss ATR multiplier
    SETUP_TP_ATR_MULT: float = float(os.getenv("SETUP_TP_ATR_MULT", "3.0"))  # Take profit ATR multiplier


# Create settings instance after environment is loaded
settings = Settings()

# --- expose wick helpers from config/settings.py so callsites can use settings.get_* ---

import importlib.util


# Module-level defaults; these will be overwritten if we load config/settings.py
def get_wick_geometry_for(symbol: str, tf: str):
    return (
        float(os.getenv("CANDLE_WICK_UP_EXH_FRAC", "0.60")),
        float(os.getenv("CANDLE_BODY_MAX_PIN_FRAC", "0.35")),
        float(os.getenv("CANDLE_EDGE_BB_PROX_FRAC", "0.15")),
    )


def get_wick_symbol_overrides(symbol: str):
    return (
        float(os.getenv("CANDLE_SPIKE_ATR_MULT", "1.8")),
        float(os.getenv("WICK_EXIT_PARTIAL_PCT", "0.5")),
    )


try:
    _settings_path = ROOT / "config" / "settings.py"
    if _settings_path.exists():
        _spec = importlib.util.spec_from_file_location(
            "bot_settings", str(_settings_path)
        )
        if _spec and _spec.loader:
            _mod = importlib.util.module_from_spec(_spec)  # type: ignore
            _spec.loader.exec_module(_mod)  # type: ignore

            if hasattr(_mod, "get_wick_geometry_for"):
                get_wick_geometry_for = _mod.get_wick_geometry_for  # type: ignore[attr-defined]
            if hasattr(_mod, "get_wick_symbol_overrides"):
                get_wick_symbol_overrides = _mod.get_wick_symbol_overrides  # type: ignore[attr-defined]

            # attach to the Settings instance so existing code works:
            setattr(settings, "get_wick_geometry_for", get_wick_geometry_for)
            setattr(settings, "get_wick_symbol_overrides", get_wick_symbol_overrides)
        else:
            logger.warning(
                "config/settings.py found but could not load spec/loader; using env defaults."
            )
    else:
        logger.info(
            "config/settings.py not present; using env defaults for wick helpers."
        )
except Exception as e:
    logger.exception(
        "Failed to expose wick helpers from config/settings.py; using env defaults. %s",
        e,
    )
    setattr(settings, "get_wick_geometry_for", get_wick_geometry_for)
    setattr(settings, "get_wick_symbol_overrides", get_wick_symbol_overrides)
