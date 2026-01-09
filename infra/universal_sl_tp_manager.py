"""
Universal Dynamic SL/TP Manager

Main orchestrator for strategy-aware, symbol-specific, session-aware stop loss
and take profit management.

This system adapts SL/TP behavior based on:
- Strategy Type (breakout, trend continuation, sweep reversal, OB rejection, mean-reversion)
- Symbol (BTC vs XAU - different behaviors)
- Session (Asia, London, NY - volatility and behavior differences)
"""

from enum import Enum
from typing import Dict, Optional, Any, Union, List
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
import sqlite3
import os
import threading

logger = logging.getLogger(__name__)

# Enum Definitions
class Session(Enum):
    """
    Market session enumeration.
    
    Used throughout the system for session-aware adjustments.
    Import this enum in any module that uses session detection:
        from infra.universal_sl_tp_manager import Session
    """
    ASIA = "ASIA"
    LONDON = "LONDON"
    NY = "NY"
    LONDON_NY_OVERLAP = "LONDON_NY_OVERLAP"
    LATE_NY = "LATE_NY"


class StrategyType(Enum):
    """
    Strategy type enumeration.
    
    Used to identify trade types for rule resolution.
    Import this enum in any module that uses strategy types:
        from infra.universal_sl_tp_manager import StrategyType
    """
    BREAKOUT_IB_VOLATILITY_TRAP = "breakout_ib_volatility_trap"
    BREAKOUT_BOS = "breakout_bos"
    TREND_CONTINUATION_PULLBACK = "trend_continuation_pullback"
    TREND_CONTINUATION_BOS = "trend_continuation_bos"
    LIQUIDITY_SWEEP_REVERSAL = "liquidity_sweep_reversal"
    ORDER_BLOCK_REJECTION = "order_block_rejection"
    MEAN_REVERSION_RANGE_SCALP = "mean_reversion_range_scalp"
    MEAN_REVERSION_VWAP_FADE = "mean_reversion_vwap_fade"
    DEFAULT_STANDARD = "default_standard"
    MICRO_SCALP = "micro_scalp"  # Already handled separately
    # Phase 4.5: New SMC Strategies
    BREAKER_BLOCK = "breaker_block"
    MARKET_STRUCTURE_SHIFT = "market_structure_shift"
    FVG_RETRACEMENT = "fvg_retracement"
    MITIGATION_BLOCK = "mitigation_block"
    INDUCEMENT_REVERSAL = "inducement_reversal"
    PREMIUM_DISCOUNT_ARRAY = "premium_discount_array"
    SESSION_LIQUIDITY_RUN = "session_liquidity_run"
    KILL_ZONE = "kill_zone"


# Universal managed strategies
UNIVERSAL_MANAGED_STRATEGIES = [
    StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
    StrategyType.TREND_CONTINUATION_PULLBACK,
    StrategyType.LIQUIDITY_SWEEP_REVERSAL,
    StrategyType.ORDER_BLOCK_REJECTION,
    StrategyType.MEAN_REVERSION_RANGE_SCALP,
    StrategyType.DEFAULT_STANDARD,  # Generic/universal trailing for trades without strategy_type
    # Phase 4.5: New SMC Strategies
    StrategyType.BREAKER_BLOCK,
    StrategyType.MARKET_STRUCTURE_SHIFT,
    StrategyType.FVG_RETRACEMENT,
    StrategyType.MITIGATION_BLOCK,
    StrategyType.INDUCEMENT_REVERSAL,
    StrategyType.PREMIUM_DISCOUNT_ARRAY,
    StrategyType.SESSION_LIQUIDITY_RUN,
    StrategyType.KILL_ZONE,
]


@dataclass
class TradeState:
    """Trade state for universal SL/TP management."""
    # Identity
    ticket: int
    symbol: str
    strategy_type: StrategyType
    direction: str
    
    # Frozen configuration (resolved once at open)
    session: Session  # Frozen at open
    resolved_trailing_rules: Dict[str, Any]  # Fully resolved config
    
    # Ownership
    managed_by: str  # "universal_sl_tp_manager" or "legacy_exit_manager"
    
    # Trade state
    entry_price: float
    initial_sl: float
    initial_tp: float
    breakeven_triggered: bool = False
    partial_taken: bool = False
    
    # Anti-thrash safeguards
    last_sl_modification_time: Optional[datetime] = None
    sl_modification_cooldown_seconds: int = 30
    
    # Runtime fields (NOT saved to DB - recalculated on recovery)
    current_price: float = 0.0  # Updated from position data each check
    current_sl: float = 0.0  # Updated from position data each check
    r_achieved: float = 0.0  # Calculated each check (can be negative if price moved against position)
    trailing_active: bool = False  # Calculated from breakeven_triggered + trailing_enabled
    
    # Structure state (for trailing)
    structure_state: Dict[str, Any] = field(default_factory=dict)
    
    # Volatility tracking (for dynamic adjustments)
    baseline_atr: Optional[float] = None  # ATR at trade open
    initial_volume: float = 0.0  # For detecting manual partial closes
    
    # Timestamps
    registered_at: datetime = field(default_factory=datetime.now)
    last_check_time: Optional[datetime] = None
    
    # Optional plan reference (for recovery)
    plan_id: Optional[str] = None
    
    # Additional fields for trailing
    last_trailing_sl: Optional[float] = None


def detect_session(symbol: str, timestamp: datetime) -> Session:
    """
    Detect market session based on UTC time.
    
    Args:
        symbol: Trading symbol (BTCUSDc, XAUUSDc, EURUSDc, US30c, etc.)
        timestamp: UTC datetime
        
    Returns:
        Session enum value
        
    Note:
        Session boundaries (UTC):
        - Asia: 00:00 - 08:00
        - London: 08:00 - 13:00
        - London-NY Overlap: 13:00 - 16:00
        - NY: 16:00 - 21:00
        - Late NY: 21:00 - 00:00
        
        BTC trades 24/7 but sessions still matter for volatility.
        Other symbols (XAU, EURUSD, US30) use same session times.
    """
    utc_hour = timestamp.hour
    
    # Session boundaries (UTC)
    # Check overlap first (highest priority)
    if 13 <= utc_hour < 16:
        return Session.LONDON_NY_OVERLAP
    elif 8 <= utc_hour < 13:
        return Session.LONDON
    elif 16 <= utc_hour < 21:
        return Session.NY
    elif 21 <= utc_hour or utc_hour < 8:
        if utc_hour >= 21:
            return Session.LATE_NY
        else:
            return Session.ASIA
    
    # Default fallback
    return Session.ASIA


class UniversalDynamicSLTPManager:
    """
    Universal Dynamic SL/TP Manager - Main orchestrator.
    """
    
    def __init__(self, db_path: str = None, mt5_service=None, config_path: str = None):
        """
        Initialize the manager.
        
        Args:
            db_path: Path to SQLite database (default: "data/universal_trades.db")
            mt5_service: MT5Service instance for position modifications
            config_path: Path to config JSON file (default: "config/universal_sl_tp_config.json")
        """
        self.db_path = db_path or "data/universal_sl_tp_trades.db"
        self.config_path = config_path or "config/universal_sl_tp_config.json"
        self.mt5_service = mt5_service
        self.active_trades: Dict[int, TradeState] = {}  # Active trade registry
        self.active_trades_lock = threading.Lock()  # Thread safety for active_trades dictionary
        self.config = self._load_config()  # Load from JSON config
        
        # Initialize database schema
        self._init_database()
        
        # Recover trades on startup
        self.recover_trades_on_startup()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from JSON file.
        
        Returns:
            Configuration dictionary, or default config if file not found
        """
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    logger.info(f"Loaded config from {self.config_path}")
                    return config.get("universal_sl_tp_rules", {})
            else:
                logger.warning(f"Config file not found: {self.config_path}, using defaults")
                return self._get_default_config()
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing config file {self.config_path}: {e}")
            return self._get_default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}", exc_info=True)
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration fallback."""
        return {
            "strategies": {
                "default_standard": {
                    "breakeven_trigger_r": 1.0,
                    "trailing_method": "atr_basic",
                    "trailing_timeframe": "M15",
                    "atr_multiplier": 2.0,
                    "trailing_enabled": True,
                    "min_sl_change_r": 0.1,
                    "sl_modification_cooldown_seconds": 60
                }
            },
            "symbol_adjustments": {}
        }
    
    def _init_database(self):
        """Initialize database schema for persistence."""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS universal_trades (
                        ticket INTEGER PRIMARY KEY,
                        symbol TEXT NOT NULL,
                        strategy_type TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        session TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        initial_sl REAL NOT NULL,
                        initial_tp REAL NOT NULL,
                        resolved_trailing_rules TEXT NOT NULL,
                        managed_by TEXT NOT NULL,
                        baseline_atr REAL,
                        initial_volume REAL,
                        breakeven_triggered INTEGER DEFAULT 0,
                        partial_taken INTEGER DEFAULT 0,
                        last_trailing_sl REAL,
                        last_sl_modification_time TEXT,
                        registered_at TEXT NOT NULL,
                        plan_id TEXT,
                        FOREIGN KEY (plan_id) REFERENCES trade_plans(plan_id)
                    )
                """)
                conn.commit()
                logger.info(f"Database initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}", exc_info=True)
    
    def recover_trades_on_startup(self):
        """
        Recover active trades from database on startup.
        
        Reconstructs TradeState objects for trades that were active before restart.
        """
        try:
            try:
                import MetaTrader5 as mt5
            except ImportError:
                logger.warning("MetaTrader5 not available - skipping trade recovery")
                return
            
            if not mt5.initialize():
                logger.warning("MT5 not initialized - skipping trade recovery")
                return
            
            # Get all open positions from MT5
            positions = mt5.positions_get()
            if not positions:
                positions = []
            
            position_tickets = {pos.ticket for pos in positions} if positions else set()
            
            # Process all open positions
            recovered_count = 0
            from infra.trade_registry import get_trade_state, set_trade_state
            
            for position in positions:
                ticket = position.ticket
                
                # Check if already registered (prevent duplicates)
                existing_state = get_trade_state(ticket)
                if existing_state and existing_state.managed_by == "universal_sl_tp_manager":
                    logger.info(f"Trade {ticket} already registered - skipping recovery")
                    continue
                
                # Try to load from database
                trade_state = self._load_trade_state_from_db(ticket)
                
                if trade_state:
                    # Trade found in DB - verify ownership and recover
                    if trade_state.managed_by == "universal_sl_tp_manager":
                        # Verify position still exists (should be true since we're iterating positions)
                        # Register in active trades and registry
                        with self.active_trades_lock:
                            self.active_trades[ticket] = trade_state
                        set_trade_state(ticket, trade_state)
                        recovered_count += 1
                        logger.info(f"Recovered trade {ticket} ({trade_state.symbol}, {trade_state.strategy_type.value})")
                    else:
                        logger.info(f"Trade {ticket} owned by {trade_state.managed_by} - skipping")
                else:
                    # Trade not in DB - try to infer if it should be managed
                    strategy_type = self._infer_strategy_type(ticket, position)
                    
                    if strategy_type and strategy_type in UNIVERSAL_MANAGED_STRATEGIES:
                        # Reconstruct TradeState for trade that should be managed
                        try:
                            # Use position open time for session detection (not current time)
                            position_open_time = datetime.fromtimestamp(position.time_setup) if hasattr(position, 'time_setup') else datetime.now()
                            session = detect_session(position.symbol, position_open_time)
                            
                            # Resolve rules
                            resolved_rules = self._resolve_trailing_rules(
                                strategy_type, position.symbol, session
                            )
                            
                            # Calculate baseline ATR
                            atr_timeframe = self._get_atr_timeframe_for_strategy(strategy_type, position.symbol)
                            baseline_atr = self._get_current_atr(position.symbol, atr_timeframe)
                            
                            # Extract plan_id from comment if available
                            plan_id = None
                            comment = getattr(position, 'comment', '') or ''
                            if 'plan_id:' in comment:
                                plan_id = comment.split('plan_id:')[1].split()[0]
                            elif comment and len(comment) > 0:
                                plan_id = comment.strip()
                            
                            trade_state = TradeState(
                                ticket=ticket,
                                symbol=position.symbol,
                                strategy_type=strategy_type,
                                direction="BUY" if position.type == 0 else "SELL",
                                session=session,
                                resolved_trailing_rules=resolved_rules,
                                managed_by="universal_sl_tp_manager",
                                entry_price=position.price_open,
                                initial_sl=position.sl if position.sl > 0 else 0.0,
                                initial_tp=position.tp if position.tp > 0 else 0.0,
                                baseline_atr=baseline_atr,
                                initial_volume=position.volume,
                                plan_id=plan_id
                            )
                            
                            # Register and save to DB
                            with self.active_trades_lock:
                                self.active_trades[ticket] = trade_state
                            set_trade_state(ticket, trade_state)
                            self._save_trade_state_to_db(trade_state)
                            recovered_count += 1
                            logger.info(f"Reconstructed trade {ticket} from position data ({strategy_type.value})")
                        except Exception as e:
                            logger.error(f"Error reconstructing trade {ticket}: {e}", exc_info=True)
                            continue
                    else:
                        # Cannot safely reconstruct - leave to legacy managers
                        logger.debug(f"Trade {ticket} cannot be safely recovered - using legacy managers")
            
            # Clean up trades in DB that no longer exist in MT5
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT ticket FROM universal_trades").fetchall()
                for row in rows:
                    ticket = row["ticket"]
                    if ticket not in position_tickets:
                        logger.warning(f"Trade {ticket} in DB but not in MT5 - cleaning up")
                        self._cleanup_trade_from_db(ticket)
            
            logger.info(f"Recovery complete: {recovered_count} trades recovered")
            
        except Exception as e:
            logger.error(f"Error during trade recovery: {e}", exc_info=True)
    
    def _normalize_strategy_type(self, strategy_type: Union[str, StrategyType]) -> StrategyType:
        """
        Convert string to StrategyType enum.
        
        Args:
            strategy_type: String value (e.g., "breakout_ib_volatility_trap") or StrategyType enum
            
        Returns:
            StrategyType enum
            
        Note:
            If string doesn't match any enum value, returns DEFAULT_STANDARD as fallback.
            This ensures the system always has a valid strategy type, even for unknown values.
        """
        if isinstance(strategy_type, StrategyType):
            return strategy_type
        
        # Map string to enum
        strategy_map = {
            "breakout_ib_volatility_trap": StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "breakout_bos": StrategyType.BREAKOUT_BOS,
            "trend_continuation_pullback": StrategyType.TREND_CONTINUATION_PULLBACK,
            "trend_continuation_bos": StrategyType.TREND_CONTINUATION_BOS,
            "liquidity_sweep_reversal": StrategyType.LIQUIDITY_SWEEP_REVERSAL,
            "order_block_rejection": StrategyType.ORDER_BLOCK_REJECTION,
            "mean_reversion_range_scalp": StrategyType.MEAN_REVERSION_RANGE_SCALP,
            "mean_reversion_vwap_fade": StrategyType.MEAN_REVERSION_VWAP_FADE,
            "default_standard": StrategyType.DEFAULT_STANDARD,
            # Phase 4.5: New SMC Strategies
            "breaker_block": StrategyType.BREAKER_BLOCK,
            "market_structure_shift": StrategyType.MARKET_STRUCTURE_SHIFT,
            "fvg_retracement": StrategyType.FVG_RETRACEMENT,
            "mitigation_block": StrategyType.MITIGATION_BLOCK,
            "inducement_reversal": StrategyType.INDUCEMENT_REVERSAL,
            "premium_discount_array": StrategyType.PREMIUM_DISCOUNT_ARRAY,
            "session_liquidity_run": StrategyType.SESSION_LIQUIDITY_RUN,
            "kill_zone": StrategyType.KILL_ZONE,
        }
        
        normalized = strategy_map.get(str(strategy_type).lower())
        if normalized:
            return normalized
        
        # Fallback to default
        logger.warning(
            f"Unknown strategy_type: {strategy_type}, using DEFAULT_STANDARD. "
            f"Valid types: {list(strategy_map.keys())}"
        )
        return StrategyType.DEFAULT_STANDARD
    
    def _get_atr_timeframe_for_strategy(self, strategy_type: StrategyType, symbol: str) -> str:
        """
        Get ATR timeframe for a strategy/symbol combination.
        
        Args:
            strategy_type: Strategy type enum
            symbol: Trading symbol
            
        Returns:
            Timeframe string (e.g., "M5", "M15")
        """
        # Get symbol-specific ATR timeframe
        symbol_config = self.config.get("symbol_adjustments", {}).get(symbol, {})
        atr_timeframe = symbol_config.get("atr_timeframe", "M15")
        
        # Strategy-specific overrides can be added here if needed
        return atr_timeframe
    
    def _get_current_atr(self, symbol: str, timeframe: str, period: int = 14) -> Optional[float]:
        """
        Get current ATR value for a symbol/timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe string (e.g., "M5", "M15")
            period: ATR period (default: 14)
            
        Returns:
            ATR value or None if calculation fails
            
        Note:
            Callers should check for return value > 0 before using.
            Returns 0.0 or None on failure.
        """
        error_details = []
        
        try:
            # Try streamer ATR calculation first (preferred method)
            try:
                from infra.streamer_data_access import StreamerDataAccess
                streamer = StreamerDataAccess()
                atr = streamer.calculate_atr(symbol, timeframe, period=period)
                
                if atr and atr > 0:
                    logger.debug(f"ATR from streamer for {symbol} {timeframe}: {atr:.4f}")
                    return float(atr)
                else:
                    error_details.append(f"Streamer returned invalid ATR: {atr}")
            except ImportError as e:
                error_details.append(f"StreamerDataAccess not available: {e}")
            except Exception as e:
                error_details.append(f"Streamer calculation failed: {e}")
            
            # Fallback to direct MT5 calculation
            import MetaTrader5 as mt5
            
            # Check MT5 initialization
            if not mt5.initialize():
                mt5_error = mt5.last_error()
                error_details.append(f"MT5 not initialized: {mt5_error}")
                logger.warning(
                    f"ATR calculation failed for {symbol} {timeframe}: "
                    f"MT5 not initialized. Errors: {'; '.join(error_details)}"
                )
                return None
            
            # Map timeframe string to MT5 constant
            tf_map = {
                "M1": mt5.TIMEFRAME_M1,
                "M5": mt5.TIMEFRAME_M5,
                "M15": mt5.TIMEFRAME_M15,
                "M30": mt5.TIMEFRAME_M30,
                "H1": mt5.TIMEFRAME_H1,
                "H4": mt5.TIMEFRAME_H4
            }
            
            mt5_tf = tf_map.get(timeframe)
            if not mt5_tf:
                error_details.append(f"Unknown timeframe: {timeframe}")
                logger.warning(
                    f"ATR calculation failed for {symbol} {timeframe}: "
                    f"Unknown timeframe. Errors: {'; '.join(error_details)}"
                )
                return None
            
            # Get bars from MT5
            bars_needed = max(period * 4, 50)
            bars = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, bars_needed)
            
            if bars is None:
                mt5_error = mt5.last_error()
                error_details.append(f"MT5 returned no bars: {mt5_error}")
                logger.warning(
                    f"ATR calculation failed for {symbol} {timeframe}: "
                    f"No bars from MT5. Errors: {'; '.join(error_details)}"
                )
                return None
            
            if len(bars) < period + 2:
                error_details.append(
                    f"Insufficient bars: got {len(bars)}, need {period + 2} "
                    f"(requested {bars_needed})"
                )
                logger.warning(
                    f"ATR calculation failed for {symbol} {timeframe}: "
                    f"Insufficient historical data. Errors: {'; '.join(error_details)}"
                )
                return None
            
            # Calculate ATR manually
            import numpy as np
            
            highs = bars['high']
            lows = bars['low']
            closes = bars['close']
            
            # Calculate True Range
            high_low = highs[1:] - lows[1:]
            high_close = np.abs(highs[1:] - closes[:-1])
            low_close = np.abs(lows[1:] - closes[:-1])
            
            tr = np.maximum(high_low, np.maximum(high_close, low_close))
            
            # Calculate ATR as simple moving average of TR
            if len(tr) >= period:
                atr = np.mean(tr[-period:])
                if atr > 0:
                    logger.debug(f"ATR from MT5 for {symbol} {timeframe}: {atr:.4f} (from {len(bars)} bars)")
                    return float(atr)
                else:
                    error_details.append(f"ATR calculation returned 0 or negative: {atr}")
            else:
                error_details.append(f"Not enough TR values: {len(tr)}, need {period}")
            
            logger.warning(
                f"ATR calculation failed for {symbol} {timeframe}: "
                f"Final calculation error. Errors: {'; '.join(error_details)}"
            )
            return None
            
        except Exception as e:
            logger.error(
                f"ATR calculation exception for {symbol} {timeframe}: {e}. "
                f"Errors: {'; '.join(error_details) if error_details else 'Unknown'}",
                exc_info=True
            )
            return None
    
    def _resolve_trailing_rules(self, strategy_type: StrategyType, symbol: str, session: Session) -> Dict[str, Any]:
        """
        Resolve all rules into a frozen snapshot.
        
        Merges strategy rules + symbol adjustments + session adjustments into a single
        resolved configuration that is stored once at trade open.
        
        Args:
            strategy_type: Strategy type enum
            symbol: Trading symbol
            session: Market session enum
            
        Returns:
            Resolved trailing rules dictionary
        """
        # Start with default strategy rules
        strategy_key = strategy_type.value
        strategies = self.config.get("strategies", {})
        strategy_rules = strategies.get(strategy_key, {})
        
        # If strategy not found, use default_standard
        if not strategy_rules:
            logger.warning(f"Strategy {strategy_key} not found in config, using default_standard")
            strategy_rules = strategies.get("default_standard", {})
        
        # Create a copy to avoid modifying original
        resolved = strategy_rules.copy()
        
        # Apply symbol-specific adjustments
        symbol_adjustments = self.config.get("symbol_adjustments", {}).get(symbol, {})
        
        # Override trailing timeframe if symbol-specific exists
        if "trailing_timeframe" in symbol_adjustments:
            resolved["trailing_timeframe"] = symbol_adjustments["trailing_timeframe"]
        elif symbol == "BTCUSDc" and "trailing_timeframe_btc" in strategy_rules:
            resolved["trailing_timeframe"] = strategy_rules["trailing_timeframe_btc"]
        elif symbol == "XAUUSDc" and "trailing_timeframe_xau" in strategy_rules:
            resolved["trailing_timeframe"] = strategy_rules["trailing_timeframe_xau"]
        
        # Apply symbol-specific base ATR multiplier (if specified)
        # This allows different symbols to have different base trailing distances
        # e.g., BTC needs wider trailing (1.7x), XAU needs tighter (1.3x)
        if "atr_multiplier" in symbol_adjustments:
            resolved["atr_multiplier"] = symbol_adjustments["atr_multiplier"]
            logger.debug(
                f"Symbol-specific ATR multiplier for {symbol}: "
                f"{resolved['atr_multiplier']}"
            )
        
        # Apply session-specific adjustments
        session_adjustments = symbol_adjustments.get("session_adjustments", {}).get(session.value, {})
        
        # Apply session adjustments to TP multiplier and SL tightening
        if "tp_multiplier" in session_adjustments:
            # Store for potential use (not directly in trailing rules, but available)
            resolved["session_tp_multiplier"] = session_adjustments["tp_multiplier"]
        
        if "sl_tightening" in session_adjustments:
            # Adjust ATR multiplier based on session (applied AFTER symbol-specific base)
            current_atr_mult = resolved.get("atr_multiplier", 1.5)
            resolved["atr_multiplier"] = current_atr_mult * session_adjustments["sl_tightening"]
            logger.debug(
                f"Session adjustment for {symbol} {session.value}: "
                f"ATR multiplier {current_atr_mult:.2f} → {resolved['atr_multiplier']:.2f} "
                f"(×{session_adjustments['sl_tightening']:.2f})"
            )
        
        # Apply session-specific breakeven trigger if exists
        session_be_key = f"breakeven_trigger_r_{session.value.lower()}"
        if session_be_key in strategy_rules:
            resolved["breakeven_trigger_r"] = strategy_rules[session_be_key]
        
        # Apply symbol-specific min_sl_change_r (if specified)
        # e.g., BTC needs smaller threshold (0.05R) for frequent adjustments,
        # XAU needs larger threshold (0.12R) for less frequent adjustments
        if "min_sl_change_r" not in resolved:
            resolved["min_sl_change_r"] = symbol_adjustments.get("min_sl_change_r", 0.1)
        elif "min_sl_change_r" in symbol_adjustments:
            # Override with symbol-specific value
            resolved["min_sl_change_r"] = symbol_adjustments["min_sl_change_r"]
            logger.debug(
                f"Symbol-specific min_sl_change_r for {symbol}: "
                f"{resolved['min_sl_change_r']}"
            )
        
        # Apply symbol-specific cooldown period (if specified)
        # e.g., BTC needs faster updates (30s), XAU can be slower (60s)
        if "sl_modification_cooldown_seconds" in symbol_adjustments:
            resolved["sl_modification_cooldown_seconds"] = symbol_adjustments["sl_modification_cooldown_seconds"]
            logger.debug(
                f"Symbol-specific cooldown for {symbol}: "
                f"{resolved['sl_modification_cooldown_seconds']} seconds"
            )
        elif "sl_modification_cooldown_seconds" not in resolved:
            resolved["sl_modification_cooldown_seconds"] = 30
        
        # Set default trailing_enabled if not specified
        if "trailing_enabled" not in resolved:
            resolved["trailing_enabled"] = True
        
        return resolved
    
    def register_trade(self, ticket: int, symbol: str, strategy_type: Union[str, StrategyType, None] = None,
                      entry_price: float = None, initial_sl: float = None, initial_tp: float = None, direction: str = None,
                      plan_id: Optional[str] = None, initial_volume: Optional[float] = None) -> Optional[TradeState]:
        """
        Register a trade with the universal SL/TP manager.
        
        Args:
            ticket: MT5 position ticket
            symbol: Trading symbol (optional if fetching from MT5)
            strategy_type: Strategy type (string or StrategyType enum). If None, uses DEFAULT_STANDARD (generic trailing)
            entry_price: Entry price (optional if fetching from MT5)
            initial_sl: Initial stop loss (optional if fetching from MT5)
            initial_tp: Initial take profit (optional if fetching from MT5)
            direction: "BUY" or "SELL" (optional if fetching from MT5)
            plan_id: Optional plan ID for recovery
            initial_volume: Optional initial volume (fetched from MT5 if not provided)
            
        Returns:
            TradeState if registered, None if registration failed or skipped
        """
        import MetaTrader5 as mt5
        from infra.trade_registry import get_trade_state, set_trade_state
        
        # If strategy_type is None, use DEFAULT_STANDARD (generic/universal trailing)
        if strategy_type is None:
            strategy_type = StrategyType.DEFAULT_STANDARD
            logger.info(f"Trade {ticket} has no strategy_type - using DEFAULT_STANDARD (generic trailing)")
        
        # Normalize strategy_type to enum
        strategy_type_enum = self._normalize_strategy_type(strategy_type)
        
        # Check if this strategy should be managed
        if strategy_type_enum not in UNIVERSAL_MANAGED_STRATEGIES:
            logger.debug(f"Trade {ticket} strategy {strategy_type_enum.value} not in UNIVERSAL_MANAGED_STRATEGIES - skipping")
            return None
        
        # Check if already registered
        existing_state = get_trade_state(ticket)
        if existing_state and existing_state.managed_by == "universal_sl_tp_manager":
            logger.warning(f"Trade {ticket} already registered with Universal Manager - returning existing state")
            return existing_state
        
        # Validate position exists and get data
        try:
            positions = mt5.positions_get(ticket=ticket)
            if not positions or len(positions) == 0:
                logger.error(f"Position {ticket} not found - cannot register")
                return None
            
            position = positions[0]
            
            # Use position data if not provided (allows registration with just ticket)
            if symbol is None:
                symbol = position.symbol
            elif position.symbol != symbol:
                logger.warning(f"Position {ticket} symbol mismatch: {position.symbol} != {symbol}")
                symbol = position.symbol  # Use actual symbol
            
            if direction is None:
                direction = "BUY" if position.type == mt5.ORDER_TYPE_BUY else "SELL"
            
            if initial_volume is None:
                initial_volume = position.volume
            
            if entry_price is None:
                entry_price = position.price_open
            
            if initial_sl is None or initial_sl == 0:
                initial_sl = position.sl if position.sl > 0 else entry_price * 0.99  # Fallback
            
            if initial_tp is None or initial_tp == 0:
                initial_tp = position.tp if position.tp > 0 else entry_price * 1.01  # Fallback
            
        except Exception as e:
            logger.error(f"Error validating position {ticket}: {e}")
            # Use provided data as fallback
            if initial_volume is None:
                initial_volume = 0.0
            if entry_price is None or initial_sl is None or initial_tp is None or direction is None or symbol is None:
                logger.error(f"Missing required position data for {ticket} - cannot register")
                return None
        
        # Detect session ONCE at trade open
        session = detect_session(symbol, datetime.now())
        
        # Calculate baseline ATR for volatility comparison
        atr_timeframe = self._get_atr_timeframe_for_strategy(strategy_type_enum, symbol)
        baseline_atr = self._get_current_atr(symbol, atr_timeframe)
        
        if baseline_atr is None or baseline_atr <= 0:
            logger.warning(f"Could not calculate baseline ATR for {symbol} {atr_timeframe} - using fallback")
            baseline_atr = abs(entry_price - initial_sl) * 0.1  # Rough estimate
        
        # Resolve ALL rules into final snapshot (ONE TIME)
        resolved_rules = self._resolve_trailing_rules(
            strategy_type=strategy_type_enum,
            symbol=symbol,
            session=session
        )
        
        # Create trade state with frozen snapshot
        trade_state = TradeState(
            ticket=ticket,
            symbol=symbol,
            strategy_type=strategy_type_enum,
            direction=direction,
            session=session,  # Frozen at open
            resolved_trailing_rules=resolved_rules,  # Frozen config
            managed_by="universal_sl_tp_manager",
            entry_price=entry_price,
            initial_sl=initial_sl,
            initial_tp=initial_tp,
            baseline_atr=baseline_atr,
            initial_volume=initial_volume,
            plan_id=plan_id,
            sl_modification_cooldown_seconds=resolved_rules.get("sl_modification_cooldown_seconds", 30)
        )
        
        # Store in active trades and global registry
        with self.active_trades_lock:
            self.active_trades[ticket] = trade_state
        set_trade_state(ticket, trade_state)
        
        # Save to database
        self._save_trade_state_to_db(trade_state)
        
        logger.info(
            f"Registered trade {ticket} ({symbol}, {strategy_type_enum.value}, {session.value}) "
            f"with frozen rules snapshot"
        )
        
        return trade_state
    
    def _save_trade_state_to_db(self, trade_state: TradeState):
        """Save trade state to database for persistence."""
        try:
            # Serialize resolved_trailing_rules to JSON
            try:
                rules_json = json.dumps(trade_state.resolved_trailing_rules)
            except Exception as e:
                logger.error(f"Error serializing resolved_trailing_rules: {e}")
                rules_json = "{}"
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO universal_trades (
                        ticket, symbol, strategy_type, direction, session,
                        entry_price, initial_sl, initial_tp, resolved_trailing_rules,
                        managed_by, baseline_atr, initial_volume,
                        breakeven_triggered, partial_taken, last_trailing_sl,
                        last_sl_modification_time, registered_at, plan_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_state.ticket,
                    trade_state.symbol,
                    trade_state.strategy_type.value,
                    trade_state.direction,
                    trade_state.session.value,
                    trade_state.entry_price,
                    trade_state.initial_sl,
                    trade_state.initial_tp,
                    rules_json,
                    trade_state.managed_by,
                    trade_state.baseline_atr,
                    trade_state.initial_volume,
                    1 if trade_state.breakeven_triggered else 0,
                    1 if trade_state.partial_taken else 0,
                    trade_state.last_trailing_sl,
                    trade_state.last_sl_modification_time.isoformat() if trade_state.last_sl_modification_time else None,
                    trade_state.registered_at.isoformat(),
                    trade_state.plan_id
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving trade state to DB: {e}", exc_info=True)
    
    def _calculate_r_achieved(self, entry_price: float, initial_sl: float, 
                              current_price: float, direction: str) -> float:
        """
        Calculate R-multiples achieved.
        
        Args:
            entry_price: Entry price
            initial_sl: Initial stop loss
            current_price: Current price
            direction: "BUY" or "SELL"
            
        Returns:
            R-multiples (can be negative if price moved against position)
        """
        if direction == "BUY":
            one_r = entry_price - initial_sl
            if one_r <= 0:
                return 0.0
            return (current_price - entry_price) / one_r
        else:  # SELL
            one_r = initial_sl - entry_price
            if one_r <= 0:
                return 0.0
            return (entry_price - current_price) / one_r
    
    def _check_cooldown(self, trade_state: TradeState, rules: Dict) -> bool:
        """
        Check if cooldown period has elapsed.
        
        Args:
            trade_state: Trade state object
            rules: Resolved trailing rules
            
        Returns:
            True if cooldown has elapsed (can modify), False otherwise
        """
        if not trade_state.last_sl_modification_time:
            return True  # Never modified, allow
        
        cooldown_seconds = rules.get("sl_modification_cooldown_seconds", 30)
        elapsed = (datetime.now() - trade_state.last_sl_modification_time).total_seconds()
        
        if elapsed < cooldown_seconds:
            logger.debug(
                f"SL modification skipped for {trade_state.ticket}: "
                f"cooldown {elapsed:.1f}s < {cooldown_seconds}s"
            )
            return False
        
        return True
    
    def _should_modify_sl(self, trade_state: TradeState, new_sl: float, 
                         rules: Dict) -> bool:
        """
        Check if SL modification should proceed based on safeguards.
        
        Checks:
        1. Minimum R-distance improvement (min_sl_change_r)
        2. Cooldown period (sl_modification_cooldown_seconds)
        
        Args:
            trade_state: Trade state object
            new_sl: Proposed new SL
            rules: Resolved trailing rules
            
        Returns:
            True if modification should proceed, False otherwise
        """
        # 1. Check minimum R-distance improvement
        min_sl_change_r = rules.get("min_sl_change_r", 0.1)
        try:
            current_sl = float(trade_state.current_sl) if trade_state.current_sl else 0.0
        except (TypeError, ValueError):
            # If current_sl is not a number (e.g., MagicMock in tests), use 0.0
            current_sl = 0.0
        
        # Calculate R improvement
        if trade_state.direction == "BUY":
            # For BUY: new_sl must be higher (better)
            if new_sl <= current_sl:
                return False  # Not an improvement
            
            # Calculate improvement in R-space
            one_r = trade_state.entry_price - trade_state.initial_sl
            if one_r <= 0:
                return False  # Invalid R calculation
            
            current_sl_r = self._calculate_r_achieved(
                trade_state.entry_price,
                trade_state.initial_sl,
                current_sl,
                trade_state.direction
            )
            new_sl_r = self._calculate_r_achieved(
                trade_state.entry_price,
                trade_state.initial_sl,
                new_sl,
                trade_state.direction
            )
            sl_improvement_r = new_sl_r - current_sl_r
        else:  # SELL
            # For SELL: new_sl must be lower (better)
            if new_sl >= current_sl:
                return False  # Not an improvement
            
            # Calculate improvement in R-space
            one_r = trade_state.initial_sl - trade_state.entry_price
            if one_r <= 0:
                return False  # Invalid R calculation
            
            current_sl_r = self._calculate_r_achieved(
                trade_state.entry_price,
                trade_state.initial_sl,
                current_sl,
                trade_state.direction
            )
            new_sl_r = self._calculate_r_achieved(
                trade_state.entry_price,
                trade_state.initial_sl,
                new_sl,
                trade_state.direction
            )
            # For SELL, lower SL is better, so new_sl_r will be less negative (closer to 0)
            # current_sl_r - new_sl_r will be negative when improving
            # We need to use absolute value or flip the sign
            sl_improvement_r = abs(current_sl_r - new_sl_r)  # Use absolute value for SELL
        
        if sl_improvement_r < min_sl_change_r:
            logger.debug(
                f"SL modification skipped for {trade_state.ticket}: "
                f"improvement {sl_improvement_r:.2f}R < minimum {min_sl_change_r}R"
            )
            return False
        
        # 2. Check cooldown period
        if not self._check_cooldown(trade_state, rules):
            return False
        
        # 3. Additional broker validation (points/pips check)
        broker_min_distance = self._get_broker_min_stop_distance(trade_state.symbol)
        if broker_min_distance > 0:
            sl_change_points = abs(new_sl - current_sl)
            if sl_change_points < broker_min_distance:
                logger.debug(
                    f"SL change {sl_change_points:.2f} below broker minimum "
                    f"{broker_min_distance:.2f} for {trade_state.symbol}"
                )
                return False
        
        return True
    
    def _get_broker_min_stop_distance(self, symbol: str) -> float:
        """
        Get broker's minimum stop distance (symbol-specific).
        Used only for final validation, not decision logic.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Minimum stop distance in points/pips, or 0.0 if cannot determine
        """
        try:
            import MetaTrader5 as mt5
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info and hasattr(symbol_info, 'trade_stops_level') and hasattr(symbol_info, 'point'):
                try:
                    stops_level = float(symbol_info.trade_stops_level) if symbol_info.trade_stops_level else 0.0
                    point = float(symbol_info.point) if symbol_info.point else 0.0
                    min_distance = stops_level * point
                    if min_distance > 0:
                        return float(min_distance)
                except (TypeError, ValueError) as e:
                    logger.debug(f"Error calculating min stop distance for {symbol}: {e}")
        except Exception as e:
            logger.error(f"Error getting broker min stop distance for {symbol}: {e}")
        
        # Fallback defaults (points/pips)
        defaults = {
            "BTCUSDc": 5.0,   # 5 points
            "XAUUSDc": 0.5,   # 0.5 pips
            "EURUSDc": 2.0,   # 2 pips
            "US30c": 3.0,     # 3 points
        }
        return defaults.get(symbol, 1.0)
    
    def _log_sl_modification(self, trade_state: TradeState, old_sl: float, 
                            new_sl: float, reason: str):
        """
        Log SL modification with rich format.
        
        Format: ticket symbol strategy_type session old_sl → new_sl r=1.78 reason=structure_trail
        
        Args:
            trade_state: Trade state object
            old_sl: Previous SL
            new_sl: New SL
            reason: Reason for modification (e.g., "breakeven_trigger", "structure_trail")
        """
        try:
            # Ensure values are floats for formatting
            old_sl_float = float(old_sl) if old_sl else 0.0
            new_sl_float = float(new_sl) if new_sl else 0.0
            r_achieved_float = float(trade_state.r_achieved) if trade_state.r_achieved else 0.0
            
            logger.info(
                f"{trade_state.ticket} {trade_state.symbol} "
                f"{trade_state.strategy_type.value} {trade_state.session.value} "
                f"SL {old_sl_float:.2f}→{new_sl_float:.2f} r={r_achieved_float:.2f} reason={reason}"
            )
        except (TypeError, ValueError) as e:
            # Fallback logging if formatting fails
            logger.info(
                f"{trade_state.ticket} {trade_state.symbol} "
                f"{trade_state.strategy_type.value} {trade_state.session.value} "
                f"SL modified reason={reason}"
            )
    
    def _modify_position_sl(self, ticket: int, new_sl: float, trade_state: TradeState) -> bool:
        """
        Modify position SL via MT5Service.
        
        Args:
            ticket: Position ticket
            new_sl: New stop loss price
            trade_state: Trade state object
            
        Returns:
            True if modification successful, False otherwise
        """
        # Verify ownership
        if trade_state.managed_by != "universal_sl_tp_manager":
            logger.warning(
                f"Cannot modify SL for {ticket}: "
                f"owned by {trade_state.managed_by}"
            )
            return False
        
        # Check if DTMS is in defensive mode (can override)
        if self._is_dtms_in_defensive_mode(ticket):
            logger.info(
                f"Skipping SL modification for {ticket}: "
                f"DTMS is in defensive mode (HEDGED/WARNING_L2)"
            )
            return False
        
        # Use MT5Service if available
        if self.mt5_service:
            try:
                result = self.mt5_service.modify_position_sl_tp(
                    ticket=ticket,
                    symbol=trade_state.symbol,
                    sl=new_sl,
                    tp=trade_state.initial_tp  # Keep existing TP
                )
                if result.get("ok"):
                    return True
                else:
                    retcode = result.get("retcode", "unknown")
                    comment = result.get("comment", "Unknown error")
                    logger.warning(
                        f"MT5Service.modify_position_sl_tp failed for {ticket}: "
                        f"retcode={retcode}, comment={comment}, SL={new_sl}"
                    )
            except Exception as e:
                logger.error(f"Error calling MT5Service.modify_position_sl_tp for {ticket}: {e}")
        
        # Fallback to direct MT5 call
        try:
            import MetaTrader5 as mt5
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": new_sl,
                "tp": trade_state.initial_tp,
                "symbol": trade_state.symbol
            }
            result = mt5.order_send(request)
            
            if result and hasattr(result, 'retcode') and result.retcode == mt5.TRADE_RETCODE_DONE:
                return True
            else:
                error_code = result.retcode if result else "unknown"
                logger.warning(
                    f"MT5 order_send failed for {ticket}: "
                    f"retcode={error_code}, SL={new_sl}"
                )
                return False
        except Exception as e:
            logger.error(f"Error modifying position {ticket} SL: {e}", exc_info=True)
            return False
    
    def _is_dtms_in_defensive_mode(self, ticket: int) -> bool:
        """Check if DTMS is in a defensive state that should take priority."""
        try:
            from dtms_integration import get_dtms_trade_status
            status = get_dtms_trade_status(ticket)
            if not status:
                return False
            
            state = status.get('state', '')
            # DTMS defensive states take priority over universal manager
            return state in ['HEDGED', 'WARNING_L2']
        except Exception:
            return False
    
    def _move_to_breakeven(self, ticket: int, trade_state: TradeState):
        """
        Move SL to breakeven (entry price).
        
        Args:
            ticket: Position ticket
            trade_state: Trade state object
        """
        try:
            new_sl = float(trade_state.entry_price)
            try:
                old_sl = float(trade_state.current_sl) if trade_state.current_sl else 0.0
            except (TypeError, ValueError):
                old_sl = 0.0
            
            success = self._modify_position_sl(ticket, new_sl, trade_state)
            if success:
                self._log_sl_modification(trade_state, old_sl, new_sl, "breakeven_trigger")
                trade_state.last_sl_modification_time = datetime.now()
                self._save_trade_state_to_db(trade_state)
        except Exception as e:
            logger.error(f"Error moving to breakeven for ticket {ticket}: {e}", exc_info=True)
    
    def _take_partial_profit(self, ticket: int, trade_state: TradeState, rules: Dict):
        """
        Take partial profit by closing a percentage of the position.
        
        Args:
            ticket: Position ticket
            trade_state: Trade state object
            rules: Resolved trailing rules
        """
        partial_close_pct = rules.get("partial_close_pct", 50)
        
        try:
            import MetaTrader5 as mt5
            positions = mt5.positions_get(ticket=ticket)
            if not positions:
                return
            
            position = positions[0]
            current_volume = position.volume
            close_volume = current_volume * (partial_close_pct / 100.0)
            
            # Round to lot step
            symbol_info = mt5.symbol_info(trade_state.symbol)
            lot_step = 0.01  # Default lot step
            if symbol_info and hasattr(symbol_info, 'volume_step') and symbol_info.volume_step:
                lot_step = float(symbol_info.volume_step)
                close_volume = round(close_volume / lot_step) * lot_step
            
            if close_volume < lot_step:
                logger.warning(f"Partial close volume {close_volume} too small for {ticket}")
                return
            
            # Close partial position
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": trade_state.symbol,
                "volume": close_volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY,
                "position": ticket,
                "deviation": 20,
                "magic": 0,
                "comment": "Universal SL/TP Partial Profit",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(
                    f"Partial profit taken for {ticket}: "
                    f"{close_volume} lots ({partial_close_pct}%)"
                )
                # Update initial_volume for future checks
                trade_state.initial_volume = current_volume - close_volume
                self._save_trade_state_to_db(trade_state)
            else:
                error_code = result.retcode if result else "unknown"
                logger.warning(
                    f"Partial close failed for {ticket}: retcode={error_code}"
                )
        except Exception as e:
            logger.error(f"Error taking partial profit for {ticket}: {e}", exc_info=True)
    
    def _get_dynamic_partial_trigger(self, trade_state: TradeState, 
                                     rules: Dict) -> float:
        """
        Dynamic partial profit trigger based on volatility.
        If volatility expands > 1.2× normal → move partial to 1.2R (earlier).
        
        Args:
            trade_state: Trade state object
            rules: Resolved trailing rules
            
        Returns:
            Partial trigger R-value, or float('inf') if no partial configured
        """
        base_partial_r = rules.get("partial_profit_r")
        if not base_partial_r:
            return float('inf')  # No partial profit configured
        
        # Check volatility expansion
        current_atr = self._get_current_atr(
            trade_state.symbol, 
            rules.get("atr_timeframe", "M15")
        )
        baseline_atr = trade_state.baseline_atr
        
        if baseline_atr and baseline_atr > 0 and current_atr and current_atr > baseline_atr * 1.2:
            # High volatility → take partial earlier
            dynamic_partial_r = base_partial_r * 0.8  # 20% earlier
            logger.info(
                f"Volatility spike detected for {trade_state.ticket}: "
                f"partial trigger adjusted {base_partial_r}R → {dynamic_partial_r}R"
            )
            return dynamic_partial_r
        
        return base_partial_r
    
    def _calculate_trailing_sl(
        self, 
        trade_state: TradeState, 
        rules: Dict,
        atr_multiplier_override: Optional[float] = None
    ) -> Optional[float]:
        """
        Calculate trailing SL based on strategy and rules.
        
        Args:
            trade_state: Trade state object
            rules: Resolved trailing rules
            atr_multiplier_override: Optional override for ATR multiplier (for volatility spikes)
            
        Returns:
            New SL price, or None if trailing not applicable
        """
        trailing_method = rules.get("trailing_method")
        atr_multiplier = atr_multiplier_override or rules.get("atr_multiplier", 1.5)
        trailing_timeframe = rules.get("trailing_timeframe", "M15")
        
        if trailing_method == "structure_atr_hybrid":
            # Get structure-based SL
            structure_sl = self._get_structure_based_sl(trade_state, rules)
            # Get ATR-based SL
            atr_sl = self._get_atr_based_sl(trade_state, rules, atr_multiplier, trailing_timeframe)
            
            # Validate ATR-based SL
            if atr_sl is None:
                logger.warning(f"ATR-based SL calculation failed for {trade_state.ticket}")
                # If structure is available, use it; otherwise return None
                if structure_sl is not None:
                    return structure_sl
                return None  # Can't calculate trailing without ATR or structure
            
            # If structure method not implemented, fallback to ATR-only
            if structure_sl is None:
                logger.debug(f"Structure-based SL not implemented for {trade_state.ticket}, using ATR-only")
                return atr_sl
            
            # Return the better (closer to price) one
            if trade_state.direction == "BUY":
                return max(structure_sl, atr_sl)  # Higher SL is better for BUY
            else:
                return min(structure_sl, atr_sl)  # Lower SL is better for SELL
        
        elif trailing_method == "structure_based":
            structure_sl = self._get_structure_based_sl(trade_state, rules)
            if structure_sl is None:
                # Fallback to ATR if structure not implemented
                logger.warning(f"Structure-based SL not implemented, falling back to ATR for {trade_state.ticket}")
                return self._get_atr_based_sl(trade_state, rules, atr_multiplier, trailing_timeframe)
            return structure_sl
        
        elif trailing_method == "atr_basic":
            atr_sl = self._get_atr_based_sl(trade_state, rules, atr_multiplier, trailing_timeframe)
            if atr_sl is None:
                logger.warning(f"ATR-based SL calculation failed for {trade_state.ticket}")
            return atr_sl
        
        elif trailing_method == "micro_choch":
            micro_choch_sl = self._get_micro_choch_sl(trade_state, rules)
            if micro_choch_sl is None:
                # Fallback to ATR if CHOCH not implemented
                logger.warning(f"Micro CHOCH SL not implemented, falling back to ATR for {trade_state.ticket}")
                return self._get_atr_based_sl(trade_state, rules, atr_multiplier, trailing_timeframe)
            return micro_choch_sl
        
        elif trailing_method == "displacement_or_structure":
            displacement_sl = self._get_displacement_sl(trade_state, rules)
            structure_sl = self._get_structure_based_sl(trade_state, rules)
            
            if displacement_sl:
                return displacement_sl
            if structure_sl:
                return structure_sl
            # Fallback to ATR if both not implemented
            logger.warning(f"Displacement and structure SL not implemented, falling back to ATR for {trade_state.ticket}")
            return self._get_atr_based_sl(trade_state, rules, atr_multiplier, trailing_timeframe)
        
        elif trailing_method == "minimal_be_only":
            # No trailing, just BE protection
            return None
        
        return None
    
    def _get_structure_based_sl(self, trade_state: TradeState, rules: Dict) -> Optional[float]:
        """
        Get structure-based trailing SL (swing lows/highs).
        
        Args:
            trade_state: Trade state object
            rules: Resolved trailing rules
            
        Returns:
            Structure-based SL, or None if calculation fails or not implemented
        """
        lookback = rules.get("structure_lookback", 2)
        timeframe = rules.get("trailing_timeframe", "M15")
        
        try:
            # Get candles for structure analysis
            from infra.streamer_data_access import StreamerDataAccess
            streamer = StreamerDataAccess()
            candles = streamer.get_candles(trade_state.symbol, timeframe, limit=100)
            
            if not candles or len(candles) < (lookback * 2 + 1):
                logger.warning(f"Not enough candles for structure analysis: {len(candles)}")
                return None
            
            # Reverse to chronological order (oldest first) if needed
            if len(candles) > 1:
                first_time = candles[0].get('time') if isinstance(candles[0], dict) else candles[0].time
                last_time = candles[-1].get('time') if isinstance(candles[-1], dict) else candles[-1].time
                if isinstance(first_time, str):
                    from datetime import datetime
                    first_time = datetime.fromisoformat(first_time.replace('Z', '+00:00'))
                    last_time = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
                if first_time > last_time:
                    candles = list(reversed(candles))
            
            # Extract OHLC data
            highs = []
            lows = []
            for candle in candles:
                if isinstance(candle, dict):
                    highs.append(candle['high'])
                    lows.append(candle['low'])
                else:
                    highs.append(candle.high)
                    lows.append(candle.low)
            
            # Find swing points
            swing_highs = []
            swing_lows = []
            
            for i in range(lookback, len(highs) - lookback):
                # Check for swing high
                if highs[i] == max(highs[i-lookback:i+lookback+1]):
                    swing_highs.append(highs[i])
                
                # Check for swing low
                if lows[i] == min(lows[i-lookback:i+lookback+1]):
                    swing_lows.append(lows[i])
            
            # Get ATR for buffer
            atr = self._get_current_atr(trade_state.symbol, timeframe)
            if atr is None or atr <= 0:
                # Fallback: use ATR-based method
                logger.debug(f"ATR unavailable for structure SL, falling back to ATR-based")
                return None
            
            atr_buffer = rules.get("atr_buffer", 0.5)
            
            if trade_state.direction == "BUY":
                if not swing_lows:
                    return None
                # Use most recent swing low
                structure_sl = min(swing_lows[-lookback:]) if len(swing_lows) >= lookback else min(swing_lows)
                # Add ATR buffer below structure
                return structure_sl - (atr * atr_buffer)
            else:  # SELL
                if not swing_highs:
                    return None
                # Use most recent swing high
                structure_sl = max(swing_highs[-lookback:]) if len(swing_highs) >= lookback else max(swing_highs)
                # Add ATR buffer above structure
                return structure_sl + (atr * atr_buffer)
                
        except Exception as e:
            logger.error(f"Error calculating structure-based SL for {trade_state.ticket}: {e}", exc_info=True)
            return None
    
    def _calculate_dynamic_trailing_distance(
        self, 
        trade_state: TradeState, 
        base_atr: float, 
        base_multiplier: float,
        current_sl: Optional[float]
    ) -> float:
        """
        Calculate dynamic trailing distance that adapts to breakeven tightness.
        
        If breakeven is very tight, use a smaller trailing distance so trailing
        can activate sooner. If breakeven is wider, use the full trailing distance.
        
        Args:
            trade_state: Trade state object
            base_atr: Base ATR value
            base_multiplier: Base ATR multiplier
            current_sl: Current stop loss (breakeven level)
            
        Returns:
            Adjusted trailing distance
        """
        if current_sl is None:
            # No current SL - use full trailing distance
            return base_atr * base_multiplier
        
        # Calculate breakeven tightness (distance from entry to breakeven SL)
        if trade_state.direction == "BUY":
            breakeven_distance = abs(current_sl - trade_state.entry_price)
        else:  # SELL
            breakeven_distance = abs(current_sl - trade_state.entry_price)
        
        # Base trailing distance
        base_trailing_distance = base_atr * base_multiplier
        
        # If breakeven is very tight (< 50% of base trailing distance)
        # Reduce trailing distance to allow activation sooner
        if breakeven_distance < base_trailing_distance * 0.5:
            # Tight breakeven: use 60-80% of base trailing distance
            # This ensures trailing can activate when price moves down by ~breakeven_distance
            tightness_ratio = breakeven_distance / base_trailing_distance
            # Scale multiplier: 0.5x to 0.8x based on tightness
            adjusted_multiplier = base_multiplier * (0.5 + 0.3 * tightness_ratio * 2)
            adjusted_distance = base_atr * adjusted_multiplier
            
            logger.debug(
                f"Dynamic trailing for {trade_state.ticket}: "
                f"breakeven={breakeven_distance:.2f} points (tight), "
                f"base_trailing={base_trailing_distance:.2f}, "
                f"adjusted_trailing={adjusted_distance:.2f} "
                f"(multiplier {base_multiplier:.2f} → {adjusted_multiplier:.2f})"
            )
            return adjusted_distance
        else:
            # Normal breakeven: use full trailing distance
            return base_trailing_distance
    
    def _get_fallback_trailing_sl(
        self, 
        trade_state: TradeState, 
        rules: Dict,
        fallback_method: str = "fixed_distance"
    ) -> Optional[float]:
        """
        Get fallback trailing SL when ATR calculation fails.
        
        Fallback methods:
        - fixed_distance: Use fixed distance (e.g., 1.5 points for XAUUSD)
        - percentage: Use percentage of price (e.g., 0.1% of current price)
        
        Args:
            trade_state: Trade state object
            rules: Resolved trailing rules
            fallback_method: "fixed_distance" or "percentage"
            
        Returns:
            Fallback trailing SL, or None if calculation fails
        """
        try:
            import MetaTrader5 as mt5
            tick = mt5.symbol_info_tick(trade_state.symbol)
            if not tick:
                return None
            
            current_price = tick.bid if trade_state.direction == "BUY" else tick.ask
            current_sl = float(trade_state.current_sl) if trade_state.current_sl else None
            
            if fallback_method == "fixed_distance":
                # Symbol-specific fixed distances
                fixed_distances = {
                    "XAUUSDc": 1.5,  # 1.5 points for gold
                    "BTCUSDc": 50.0,  # 50 points for BTC
                    "EURUSDc": 0.0005,  # 5 pips for EUR
                    "GBPUSDc": 0.0005,
                    "USDJPYc": 0.05,
                }
                
                # Get symbol-specific distance or use default
                trailing_distance = fixed_distances.get(
                    trade_state.symbol, 
                    rules.get("fallback_fixed_distance", 1.5)
                )
                
                logger.info(
                    f"Using fixed-distance fallback trailing for {trade_state.ticket} "
                    f"({trade_state.symbol}): {trailing_distance} points"
                )
                
            elif fallback_method == "percentage":
                # Percentage-based trailing (e.g., 0.1% of price)
                trailing_pct = rules.get("fallback_trailing_pct", 0.001)  # 0.1% default
                trailing_distance = current_price * trailing_pct
                
                logger.info(
                    f"Using percentage-based fallback trailing for {trade_state.ticket} "
                    f"({trade_state.symbol}): {trailing_pct*100:.2f}% = {trailing_distance:.2f} points"
                )
            else:
                logger.warning(f"Unknown fallback method: {fallback_method}")
                return None
            
            # Calculate ideal SL
            if trade_state.direction == "BUY":
                ideal_sl = current_price - trailing_distance
                
                # Only move SL UP (tighten), never DOWN (widen)
                if current_sl is not None and ideal_sl < current_sl:
                    logger.debug(
                        f"Fallback trailing SL for {trade_state.ticket} would widen (BUY): "
                        f"ideal={ideal_sl:.2f} < current={current_sl:.2f}, keeping current"
                    )
                    return None
                
                return ideal_sl
            else:  # SELL
                ideal_sl = current_price + trailing_distance
                
                # Only move SL DOWN (tighten), never UP (widen)
                if current_sl is not None and ideal_sl > current_sl:
                    logger.debug(
                        f"Fallback trailing SL for {trade_state.ticket} would widen (SELL): "
                        f"ideal={ideal_sl:.2f} > current={current_sl:.2f}, keeping current"
                    )
                    return None
                
                return ideal_sl
                
        except Exception as e:
            logger.error(f"Error calculating fallback trailing SL for {trade_state.ticket}: {e}", exc_info=True)
            return None
    
    def _get_atr_based_sl(self, trade_state: TradeState, rules: Dict, 
                          atr_multiplier: float, timeframe: str) -> Optional[float]:
        """
        Get ATR-based trailing SL with dynamic trailing distance.
        
        For trailing stops, we only tighten (never widen):
        - BUY: SL only moves UP (higher)
        - SELL: SL only moves DOWN (lower)
        
        The trailing distance adapts to breakeven tightness:
        - Tight breakeven (< 50% of base trailing): Use smaller trailing distance
        - Normal breakeven: Use full trailing distance
        
        If ATR calculation fails, falls back to fixed-distance or percentage-based trailing.
        
        Args:
            trade_state: Trade state object
            rules: Resolved trailing rules
            atr_multiplier: ATR multiplier
            timeframe: Timeframe for ATR calculation
            
        Returns:
            ATR-based SL, or fallback SL if ATR fails, or None if all methods fail
        """
        current_atr = self._get_current_atr(trade_state.symbol, timeframe)
        if current_atr is None or current_atr <= 0:
            # ATR calculation failed - use fallback method
            logger.warning(
                f"ATR calculation failed for {trade_state.ticket} ({trade_state.symbol} {timeframe}) - "
                f"using fallback trailing method"
            )
            
            # Send alert if this is a repeated failure
            if not hasattr(self, '_atr_failure_alerts'):
                self._atr_failure_alerts = {}
            
            alert_key = f"{trade_state.symbol}_{timeframe}"
            failure_count = self._atr_failure_alerts.get(alert_key, 0) + 1
            self._atr_failure_alerts[alert_key] = failure_count
            
            # Alert on first failure and every 10th failure
            if failure_count == 1 or failure_count % 10 == 0:
                try:
                    from discord_notifications import DiscordNotifier
                    discord_notifier = DiscordNotifier()
                    if discord_notifier.enabled:
                        alert_message = f"""⚠️ **ATR Calculation Failed**

📊 **Ticket**: {trade_state.ticket}
💱 **Symbol**: {trade_state.symbol}
📈 **Timeframe**: {timeframe}
🔄 **Failure Count**: {failure_count}

⚠️ **Impact**: Trailing stops using fallback method
💡 **Action**: Check MT5 historical data availability

⏰ **Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                        
                        discord_notifier.send_error_alert(
                            error_message=alert_message,
                            component="Universal Manager - ATR Calculation"
                        )
                        logger.info(f"Discord alert sent for ATR failure (count: {failure_count})")
                except Exception as e:
                    logger.debug(f"Could not send Discord alert for ATR failure: {e}")
            
            # Try fallback methods in order of preference
            fallback_methods = rules.get("fallback_trailing_methods", ["fixed_distance", "percentage"])
            
            for fallback_method in fallback_methods:
                fallback_sl = self._get_fallback_trailing_sl(trade_state, rules, fallback_method)
                if fallback_sl is not None:
                    logger.info(
                        f"Fallback trailing SL calculated for {trade_state.ticket} "
                        f"using {fallback_method}: {fallback_sl:.2f}"
                    )
                    return fallback_sl
            
            # All fallback methods failed
            logger.error(
                f"All trailing methods failed for {trade_state.ticket} "
                f"({trade_state.symbol}): ATR failed, fallbacks failed"
            )
            return None
        
        # Get current price
        try:
            import MetaTrader5 as mt5
            tick = mt5.symbol_info_tick(trade_state.symbol)
            if not tick:
                return None
            
            current_price = tick.bid if trade_state.direction == "BUY" else tick.ask
            
            # Get current SL from trade state
            current_sl = float(trade_state.current_sl) if trade_state.current_sl else None
            
            # Calculate dynamic trailing distance based on breakeven tightness
            trailing_distance = self._calculate_dynamic_trailing_distance(
                trade_state,
                current_atr,
                atr_multiplier,
                current_sl
            )
            
            if trade_state.direction == "BUY":
                # SL below current price
                ideal_sl = current_price - trailing_distance
                
                # For BUY trailing: Only move SL UP (tighten), never DOWN (widen)
                # So ideal_sl must be HIGHER than current_sl
                if current_sl is not None and ideal_sl < current_sl:
                    # Ideal SL would widen the stop - use current SL instead
                    logger.debug(
                        f"Trailing SL for {trade_state.ticket} would widen (BUY): "
                        f"ideal={ideal_sl:.2f} < current={current_sl:.2f}, keeping current"
                    )
                    return None  # Don't modify if it would widen
                
                return ideal_sl
            else:  # SELL
                # SL above current price
                ideal_sl = current_price + trailing_distance
                
                # For SELL trailing: Only move SL DOWN (tighten), never UP (widen)
                # CRITICAL: For SELL trades, when price moves DOWN (profit), we want to lock in MORE profit
                # by moving SL DOWN (closer to current price, but still above it).
                # Moving SL UP would REDUCE profit or cause a loss - this is WRONG.
                if current_sl is not None:
                    entry_price = trade_state.entry_price
                    
                    if ideal_sl > current_sl:
                        # Ideal SL would move UP from current - this is WRONG for SELL
                        # Moving SL UP would reduce profit or cause loss - REJECT
                        logger.debug(
                            f"Trailing SL for {trade_state.ticket} would move UP (SELL): "
                            f"ideal={ideal_sl:.2f} > current={current_sl:.2f} - "
                            f"REJECTED (would reduce profit). "
                            f"Price needs to move down more for trailing to activate. "
                            f"(price={current_price:.2f}, entry={entry_price:.2f}, "
                            f"trailing_distance={trailing_distance:.2f})"
                        )
                        return None  # Don't widen - would reduce profit
                    elif ideal_sl < current_sl:
                        # Ideal SL tightens the stop (moves DOWN) - this is CORRECT
                        # Moving SL DOWN locks in MORE profit as price moves down
                        logger.info(
                            f"Trailing SL for {trade_state.ticket} tightens (SELL): "
                            f"{current_sl:.2f} → {ideal_sl:.2f} "
                            f"(price={current_price:.2f}, entry={entry_price:.2f}, "
                            f"trailing_distance={trailing_distance:.2f}) - "
                            f"locking in more profit"
                        )
                        return ideal_sl
                    else:
                        # Ideal SL equals current SL - no change needed
                        return None
                
                # No current SL - use ideal
                return ideal_sl
        except Exception as e:
            logger.error(f"Error calculating ATR-based SL: {e}", exc_info=True)
            return None
    
    def _get_micro_choch_sl(self, trade_state: TradeState, rules: Dict) -> Optional[float]:
        """
        Get micro CHOCH-based trailing SL.
        
        Uses M1 microstructure analysis to detect CHOCH (Change of Character) and
        uses the most recent swing point as the SL anchor.
        
        Args:
            trade_state: Trade state object
            rules: Resolved trailing rules
            
        Returns:
            CHOCH-based SL, or None if calculation fails
        """
        try:
            # Get M1 candles for microstructure analysis
            from infra.streamer_data_access import StreamerDataAccess
            streamer = StreamerDataAccess()
            m1_candles = streamer.get_candles(trade_state.symbol, "M1", limit=100)
            
            if not m1_candles or len(m1_candles) < 10:
                logger.debug(f"Not enough M1 candles for CHOCH detection: {len(m1_candles) if m1_candles else 0}")
                return None
            
            # Use M1 microstructure analyzer to detect CHOCH and get swing points
            try:
                from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
                analyzer = M1MicrostructureAnalyzer()
                
                # Detect CHOCH/BOS to get swing points
                choch_result = analyzer.detect_choch_bos(m1_candles, require_confirmation=True, symbol=trade_state.symbol)
                
                if not choch_result:
                    logger.debug(f"CHOCH detection failed for {trade_state.ticket}")
                    return None
                
                # Get ATR for buffer calculation
                atr = self._get_current_atr(trade_state.symbol, "M1", period=14)
                if atr is None or atr <= 0:
                    # Fallback: calculate ATR from M1 candles
                    atr = self._calculate_atr_from_candles(m1_candles, period=14)
                    if atr is None or atr <= 0:
                        logger.debug(f"ATR calculation failed for {trade_state.ticket}")
                        return None
                
                # Get ATR buffer multiplier from rules (default 0.5)
                atr_buffer = rules.get("atr_buffer", 0.5)
                
                # Use swing points for SL anchor
                if trade_state.direction == "BUY":
                    # For BUY: use most recent swing low as SL anchor
                    swing_low = choch_result.get("last_swing_low", 0)
                    if swing_low <= 0:
                        logger.debug(f"No valid swing low found for BUY trade {trade_state.ticket}")
                        return None
                    
                    # SL = swing low - ATR buffer
                    choch_sl = swing_low - (atr * atr_buffer)
                    
                    # Ensure SL is below current price (safety check)
                    if choch_sl >= trade_state.current_price:
                        logger.debug(f"CHOCH SL {choch_sl:.2f} above current price {trade_state.current_price:.2f} for {trade_state.ticket}")
                        return None
                    
                    logger.debug(f"CHOCH SL for BUY {trade_state.ticket}: swing_low={swing_low:.2f}, atr={atr:.2f}, sl={choch_sl:.2f}")
                    return choch_sl
                    
                else:  # SELL
                    # For SELL: use most recent swing high as SL anchor
                    swing_high = choch_result.get("last_swing_high", 0)
                    if swing_high <= 0:
                        logger.debug(f"No valid swing high found for SELL trade {trade_state.ticket}")
                        return None
                    
                    # SL = swing high + ATR buffer
                    choch_sl = swing_high + (atr * atr_buffer)
                    
                    # Ensure SL is above current price (safety check)
                    if choch_sl <= trade_state.current_price:
                        logger.debug(f"CHOCH SL {choch_sl:.2f} below current price {trade_state.current_price:.2f} for {trade_state.ticket}")
                        return None
                    
                    logger.debug(f"CHOCH SL for SELL {trade_state.ticket}: swing_high={swing_high:.2f}, atr={atr:.2f}, sl={choch_sl:.2f}")
                    return choch_sl
                    
            except ImportError:
                logger.warning("M1MicrostructureAnalyzer not available - CHOCH SL not implemented")
                return None
            except Exception as e:
                logger.error(f"Error in CHOCH detection for {trade_state.ticket}: {e}", exc_info=True)
                return None
                
        except Exception as e:
            logger.error(f"Error getting micro CHOCH SL for {trade_state.ticket}: {e}", exc_info=True)
            return None
    
    def _calculate_atr_from_candles(self, candles: List[Dict], period: int = 14) -> Optional[float]:
        """
        Calculate ATR from candle data.
        
        Args:
            candles: List of candle dicts with 'high', 'low', 'close'
            period: ATR period (default: 14)
            
        Returns:
            ATR value or None if calculation fails
        """
        try:
            if len(candles) < period + 1:
                return None
            
            import numpy as np
            
            # Extract OHLC data
            highs = [c.get('high', 0) if isinstance(c, dict) else c.high for c in candles]
            lows = [c.get('low', 0) if isinstance(c, dict) else c.low for c in candles]
            closes = [c.get('close', 0) if isinstance(c, dict) else c.close for c in candles]
            
            # Calculate True Range
            tr_values = []
            for i in range(1, len(candles)):
                hl = highs[i] - lows[i]
                hc = abs(highs[i] - closes[i-1])
                lc = abs(lows[i] - closes[i-1])
                tr_values.append(max(hl, hc, lc))
            
            # Calculate ATR as simple moving average of TR
            if len(tr_values) >= period:
                atr = np.mean(tr_values[-period:])
                if atr > 0:
                    return float(atr)
            
            return None
        except Exception as e:
            logger.debug(f"Error calculating ATR from candles: {e}")
            return None
    
    def _get_displacement_sl(self, trade_state: TradeState, rules: Dict) -> Optional[float]:
        """
        Get displacement candle-based trailing SL.
        
        Detects displacement candles (strong move after order block) and uses
        the low/high of the displacement candle as the SL anchor.
        
        Args:
            trade_state: Trade state object
            rules: Resolved trailing rules
            
        Returns:
            Displacement-based SL, or None if calculation fails
        """
        try:
            # Get candles for the appropriate timeframe
            timeframe = rules.get("trailing_timeframe", "M5")
            from infra.streamer_data_access import StreamerDataAccess
            streamer = StreamerDataAccess()
            candles = streamer.get_candles(trade_state.symbol, timeframe, limit=50)
            
            if not candles or len(candles) < 20:
                logger.debug(f"Not enough {timeframe} candles for displacement detection: {len(candles) if candles else 0}")
                return None
            
            # Convert to oldest-first if needed
            if len(candles) > 1:
                first_time = candles[0].get('time') if isinstance(candles[0], dict) else candles[0].time
                last_time = candles[-1].get('time') if isinstance(candles[-1], dict) else candles[-1].time
                if isinstance(first_time, str):
                    from datetime import datetime
                    first_time = datetime.fromisoformat(first_time.replace('Z', '+00:00'))
                    last_time = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
                if first_time > last_time:
                    candles = list(reversed(candles))
            
            # Look for displacement pattern in recent candles
            recent = candles[-15:]  # Check last 15 candles
            
            # Calculate average range for displacement validation
            ranges = []
            for c in recent:
                if isinstance(c, dict):
                    high = c.get('high', 0)
                    low = c.get('low', 0)
                else:
                    high = c.high
                    low = c.low
                ranges.append(high - low)
            
            avg_range = sum(ranges) / len(ranges) if ranges else 0
            if avg_range <= 0:
                logger.debug(f"Cannot calculate displacement: avg_range={avg_range}")
                return None
            
            # Calculate move strength
            if isinstance(recent[0], dict):
                start_price = recent[0].get('open', 0)
                end_price = recent[-1].get('close', 0)
            else:
                start_price = recent[0].open
                end_price = recent[-1].close
            
            move = end_price - start_price
            displacement_strength = abs(move) / avg_range
            
            # Require strong displacement (at least 1.5x average range)
            if displacement_strength < 1.5:
                logger.debug(f"Displacement not strong enough: {displacement_strength:.2f}x < 1.5x")
                return None
            
            # Find the displacement candle (first candle of the strong move)
            displacement_candle = None
            displacement_idx = None
            
            if trade_state.direction == "BUY":
                # For BUY: look for bullish displacement (strong up move)
                if move > 0:
                    # Find the first candle of the bullish move
                    for i in range(len(recent) - 1, -1, -1):
                        c = recent[i]
                        if isinstance(c, dict):
                            open_price = c.get('open', 0)
                            close_price = c.get('close', 0)
                        else:
                            open_price = c.open
                            close_price = c.close
                        
                        # First bullish candle in the sequence
                        if close_price > open_price:
                            displacement_candle = c
                            displacement_idx = i
                            break
            else:  # SELL
                # For SELL: look for bearish displacement (strong down move)
                if move < 0:
                    # Find the first candle of the bearish move
                    for i in range(len(recent) - 1, -1, -1):
                        c = recent[i]
                        if isinstance(c, dict):
                            open_price = c.get('open', 0)
                            close_price = c.get('close', 0)
                        else:
                            open_price = c.open
                            close_price = c.close
                        
                        # First bearish candle in the sequence
                        if close_price < open_price:
                            displacement_candle = c
                            displacement_idx = i
                            break
            
            if not displacement_candle:
                logger.debug(f"No displacement candle found for {trade_state.ticket}")
                return None
            
            # Get ATR for buffer calculation
            atr = self._get_current_atr(trade_state.symbol, timeframe)
            if atr is None or atr <= 0:
                atr = self._calculate_atr_from_candles(candles, period=14)
                if atr is None or atr <= 0:
                    logger.debug(f"ATR calculation failed for displacement SL {trade_state.ticket}")
                    return None
            
            # Get ATR buffer multiplier from rules (default 0.3 for displacement)
            atr_buffer = rules.get("atr_buffer", 0.3)
            
            # Extract high/low from displacement candle
            if isinstance(displacement_candle, dict):
                disp_high = displacement_candle.get('high', 0)
                disp_low = displacement_candle.get('low', 0)
            else:
                disp_high = displacement_candle.high
                disp_low = displacement_candle.low
            
            if trade_state.direction == "BUY":
                # For BUY: use low of displacement candle as SL anchor
                displacement_sl = disp_low - (atr * atr_buffer)
                
                # Ensure SL is below current price
                if displacement_sl >= trade_state.current_price:
                    logger.debug(f"Displacement SL {displacement_sl:.2f} above current price {trade_state.current_price:.2f} for {trade_state.ticket}")
                    return None
                
                logger.debug(f"Displacement SL for BUY {trade_state.ticket}: disp_low={disp_low:.2f}, atr={atr:.2f}, sl={displacement_sl:.2f}")
                return displacement_sl
                
            else:  # SELL
                # For SELL: use high of displacement candle as SL anchor
                displacement_sl = disp_high + (atr * atr_buffer)
                
                # Ensure SL is above current price
                if displacement_sl <= trade_state.current_price:
                    logger.debug(f"Displacement SL {displacement_sl:.2f} below current price {trade_state.current_price:.2f} for {trade_state.ticket}")
                    return None
                
                logger.debug(f"Displacement SL for SELL {trade_state.ticket}: disp_high={disp_high:.2f}, atr={atr:.2f}, sl={displacement_sl:.2f}")
                return displacement_sl
                
        except Exception as e:
            logger.error(f"Error getting displacement SL for {trade_state.ticket}: {e}", exc_info=True)
            return None
    
    def _detect_momentum_exhaustion(self, trade_state: TradeState) -> bool:
        """
        Detect momentum exhaustion (stall detection).
        
        Args:
            trade_state: Trade state object
            
        Returns:
            True if momentum exhaustion detected, False otherwise
        """
        # TODO: Implement momentum exhaustion detection
        # Example: Check for 3+ doji candles on M1
        # Example: Check for CVD divergence
        # Example: Check for volume decline
        return False
    
    def _tighten_sl_aggressively(self, ticket: int, trade_state: TradeState, rules: Dict):
        """
        Aggressively tighten SL when momentum exhaustion detected.
        
        This is a defensive move - locks in profit even if it doesn't meet
        the normal improvement threshold.
        
        Args:
            ticket: Position ticket
            trade_state: Trade state object
            rules: Resolved trailing rules
        """
        # Calculate tighter SL (e.g., lock 0.75R or 1R)
        lock_r = rules.get("stall_lock_r", 0.75)
        
        if trade_state.direction == "BUY":
            one_r = trade_state.entry_price - trade_state.initial_sl
            new_sl = trade_state.entry_price + (one_r * lock_r)
        else:  # SELL
            one_r = trade_state.initial_sl - trade_state.entry_price
            new_sl = trade_state.entry_price - (one_r * lock_r)
        
        # Ensure it's better than current SL
        try:
            current_sl = float(trade_state.current_sl) if trade_state.current_sl else 0.0
        except (TypeError, ValueError):
            current_sl = 0.0
        
        if trade_state.direction == "BUY":
            if new_sl <= current_sl:
                return  # Not an improvement
        else:  # SELL
            if new_sl >= current_sl:
                return  # Not an improvement
        
        old_sl = current_sl
        success = self._modify_position_sl(ticket, new_sl, trade_state)
        
        if success:
            self._log_sl_modification(trade_state, old_sl, new_sl, "stall_tighten")
            trade_state.last_sl_modification_time = datetime.now()
            self._save_trade_state_to_db(trade_state)
    
    def monitor_trade(self, ticket: int):
        """
        Monitor a single trade for SL/TP adjustments.
        
        This method is wrapped in error handling to prevent one failing trade
        from stopping monitoring of other trades.
        """
        # FIX: Thread-safe access to active_trades
        with self.active_trades_lock:
            trade_state = self.active_trades.get(ticket)
            if not trade_state:
                return
        
        # 1. Verify ownership
        if trade_state.managed_by != "universal_sl_tp_manager":
            return  # Not our trade
        
        try:
            # 2. Get current position data
            try:
                import MetaTrader5 as mt5
                positions = mt5.positions_get(ticket=ticket)
                if not positions or len(positions) == 0:
                    logger.info(f"Position {ticket} no longer exists - unregistering")
                    self._unregister_trade(ticket)
                    return
                position = positions[0]  # Get first (should be only one)
            except Exception as e:
                logger.error(f"Error getting position {ticket}: {e}", exc_info=True)
                return
            
            # 2.5. Check for manual partial closes or scale-ins
            try:
                current_volume = float(position.volume)
                if current_volume != trade_state.initial_volume:
                    if current_volume == 0:
                        # Position fully closed
                        logger.info(f"Position {ticket} fully closed - unregistering")
                        self._unregister_trade(ticket)
                        return
                    elif current_volume < trade_state.initial_volume:
                        # Manual partial close detected
                        if current_volume <= 0:
                            logger.error(
                                f"Invalid volume {current_volume} for {ticket} "
                                f"after partial close - unregistering"
                            )
                            self._unregister_trade(ticket)
                            return
                        
                        logger.info(
                            f"Position {ticket} volume reduced: "
                            f"{trade_state.initial_volume} → {current_volume} "
                            "(manual partial close detected)"
                        )
                        trade_state.initial_volume = current_volume  # Update for future checks
                        # Update database
                        self._save_trade_state_to_db(trade_state)
                    elif current_volume > trade_state.initial_volume:
                        # Scale-in (not supported, but log it)
                        logger.warning(
                            f"Position {ticket} volume increased: "
                            f"{trade_state.initial_volume} → {current_volume} "
                            "(scale-in not supported)"
                        )
                        trade_state.initial_volume = current_volume  # Update anyway
                        # Update database
                        self._save_trade_state_to_db(trade_state)
            except Exception as e:
                logger.error(f"Error checking volume change for {ticket}: {e}", exc_info=True)
            
            # 3. Update current metrics
            try:
                trade_state.current_price = float(position.price_current)
                try:
                    trade_state.current_sl = float(position.sl) if position.sl else 0.0
                except (TypeError, ValueError):
                    trade_state.current_sl = 0.0
                trade_state.r_achieved = self._calculate_r_achieved(
                    trade_state.entry_price,
                    trade_state.initial_sl,
                    trade_state.current_price,
                    trade_state.direction
                )
                
                # Log if R is very negative (might indicate calculation error)
                if trade_state.r_achieved < -2.0:
                    logger.warning(
                        f"Very negative R ({trade_state.r_achieved:.2f}) for {ticket} - "
                        f"check calculation. Entry: {trade_state.entry_price}, "
                        f"SL: {trade_state.initial_sl}, Current: {trade_state.current_price}"
                    )
            except Exception as e:
                logger.error(f"Error calculating metrics for {ticket}: {e}", exc_info=True)
                return
            
            # 4. Use FROZEN rules (no recalculation)
            rules = trade_state.resolved_trailing_rules
            
            # Validate rules exist (defensive check)
            if not rules:
                logger.error(f"No resolved rules for {ticket} - skipping monitoring")
                return
            
            # 5. Check breakeven trigger (independent of trailing_enabled)
            # NOTE: Intelligent Exit Manager handles breakeven, Universal Manager only takes over after breakeven
            try:
                if not trade_state.breakeven_triggered:
                    # Check if Intelligent Exit Manager already moved SL to breakeven
                    # (SL at or near entry price indicates breakeven was triggered)
                    entry_price = trade_state.entry_price
                    current_sl = trade_state.current_sl
                    
                    # Check if SL is at breakeven (within 0.1% of entry)
                    sl_at_breakeven = False
                    if current_sl > 0:
                        if trade_state.direction == "BUY":
                            sl_at_breakeven = abs(current_sl - entry_price) / entry_price < 0.001
                        else:  # SELL
                            sl_at_breakeven = abs(current_sl - entry_price) / entry_price < 0.001
                    
                    if sl_at_breakeven:
                        # Intelligent Exit Manager already moved to breakeven
                        logger.info(
                            f"Breakeven already triggered by Intelligent Exit Manager for {ticket} "
                            f"(SL at {current_sl:.2f} near entry {entry_price:.2f}) - Universal Manager takes over"
                        )
                        trade_state.breakeven_triggered = True
                        self._save_trade_state_to_db(trade_state)
                    else:
                        # Breakeven not triggered yet - Intelligent Exit Manager will handle it
                        # Universal Manager skips breakeven logic and waits
                        logger.debug(
                            f"Breakeven not triggered for {ticket} (R={trade_state.r_achieved:.2f}) - "
                            f"Intelligent Exit Manager will handle breakeven"
                        )
                        return  # Skip trailing until breakeven is triggered
            except Exception as e:
                logger.error(f"Error in breakeven check for {ticket}: {e}", exc_info=True)
            
            # 6. Check partial profit trigger (with dynamic scaling)
            try:
                if not trade_state.partial_taken:
                    partial_trigger_r = self._get_dynamic_partial_trigger(
                        trade_state, rules
                    )
                    # Check for None or inf (no partial configured)
                    if partial_trigger_r is not None and partial_trigger_r != float('inf'):
                        if trade_state.r_achieved >= partial_trigger_r:
                            self._take_partial_profit(ticket, trade_state, rules)
                            trade_state.partial_taken = True
                            self._save_trade_state_to_db(trade_state)
            except Exception as e:
                logger.error(f"Error in partial profit check for {ticket}: {e}", exc_info=True)
            
            # 7. Calculate trailing SL (if breakeven triggered AND trailing enabled)
            # Note: Mean-reversion may have trailing_enabled=false, but still uses BE
            try:
                if trade_state.breakeven_triggered and rules.get("trailing_enabled", True):
                    # Check for volatility spike (mid-trade override)
                    current_atr = self._get_current_atr(
                        trade_state.symbol, 
                        rules.get("atr_timeframe", "M15")
                    )
                    baseline_atr = trade_state.baseline_atr
                    
                    atr_multiplier_override = None
                    # Check: baseline_atr could be None if trade registered before fix
                    # Also check that current_atr is not None
                    if (baseline_atr is not None and baseline_atr > 0 and 
                        current_atr is not None and current_atr > 0 and 
                        current_atr > baseline_atr * 1.5):
                        # High-volatility mode: temporarily adjust trailing distance (20% wider)
                        atr_multiplier_override = rules.get("atr_multiplier", 1.5) * 1.2
                        logger.debug(
                            f"Volatility spike detected for {ticket}: "
                            f"ATR {baseline_atr:.2f} → {current_atr:.2f} "
                            f"(×{current_atr/baseline_atr:.2f}), using wider trailing"
                        )
                    elif baseline_atr is None:
                        logger.warning(
                            f"baseline_atr is None for {ticket} - "
                            f"cannot check volatility override"
                        )
                    
                    new_sl = self._calculate_trailing_sl(
                        trade_state, 
                        rules,
                        atr_multiplier_override=atr_multiplier_override
                    )
                    
                    if new_sl is None:
                        # Trailing not applicable or calculation failed
                        # This is normal for some strategies (e.g., mean-reversion with trailing_enabled=false)
                        # or if structure methods not implemented
                        if rules.get("trailing_enabled", True):
                            # Check if ATR failed (would have logged warning)
                            # Try fallback methods directly if ATR failed
                            current_atr = self._get_current_atr(
                                trade_state.symbol, 
                                rules.get("atr_timeframe", "M15")
                            )
                            if current_atr is None or current_atr <= 0:
                                # ATR failed - try fallback
                                logger.warning(
                                    f"Trailing SL calculation failed for {ticket} due to ATR failure - "
                                    f"attempting fallback methods"
                                )
                                fallback_methods = rules.get("fallback_trailing_methods", ["fixed_distance", "percentage"])
                                for fallback_method in fallback_methods:
                                    fallback_sl = self._get_fallback_trailing_sl(trade_state, rules, fallback_method)
                                    if fallback_sl is not None:
                                        new_sl = fallback_sl
                                        logger.info(
                                            f"Fallback trailing SL applied for {ticket} "
                                            f"using {fallback_method}: {fallback_sl:.2f}"
                                        )
                                        break
                            else:
                                logger.debug(
                                    f"Trailing SL calculation returned None for {ticket} "
                                    "(may be expected - structure/other method)"
                                )
                    elif new_sl:
                        # 8. Apply safeguards before modifying
                        # FIX: Re-check trade still exists before modification (race condition fix)
                        with self.active_trades_lock:
                            if ticket not in self.active_trades:
                                logger.debug(f"Trade {ticket} was removed during monitoring - skipping modification")
                                return
                            # Re-get trade_state in case it was updated
                            trade_state = self.active_trades.get(ticket)
                            if not trade_state:
                                return
                        
                        if self._should_modify_sl(trade_state, new_sl, rules):
                            success = self._modify_position_sl(ticket, new_sl, trade_state)
                            if success:
                                trade_state.last_trailing_sl = new_sl
                                trade_state.last_sl_modification_time = datetime.now()
                                self._save_trade_state_to_db(trade_state)
            except Exception as e:
                logger.error(f"Error in trailing SL calculation for {ticket}: {e}", exc_info=True)
            
            # 9. Check momentum/stall detection
            try:
                if rules.get("momentum_exhaustion_detection", False):
                    if self._detect_momentum_exhaustion(trade_state):
                        self._tighten_sl_aggressively(ticket, trade_state, rules)
            except Exception as e:
                logger.error(f"Error in momentum detection for {ticket}: {e}", exc_info=True)
            
            # 10. Update last check time
            trade_state.last_check_time = datetime.now()
            
        except Exception as e:
            logger.error(f"Unexpected error monitoring trade {ticket}: {e}", exc_info=True)
            # Don't unregister - might be temporary issue
    
    def monitor_all_trades(self):
        """Monitor all active trades (called by scheduler)."""
        # Check MT5 connection first
        try:
            import MetaTrader5 as mt5
            if not mt5.initialize():
                logger.error("MT5 not initialized - skipping trade monitoring")
                return
        except Exception as e:
            logger.error(f"Error checking MT5 connection: {e}")
            return
        
        # Get all open positions from MT5
        try:
            positions = mt5.positions_get()
            if positions:
                position_tickets = {pos.ticket for pos in positions}
                
                # Check database for trades registered via API (not in active_trades)
                from infra.trade_registry import get_trade_state, set_trade_state
                for ticket in position_tickets:
                    # If not in active_trades, check database
                    # FIX: Thread-safe check and add
                    with self.active_trades_lock:
                        if ticket not in self.active_trades:
                            trade_state = self._load_trade_state_from_db(ticket)
                            if trade_state and trade_state.managed_by == "universal_sl_tp_manager":
                                # Load into active_trades and registry
                                self.active_trades[ticket] = trade_state
                                set_trade_state(ticket, trade_state)
                                logger.info(f"Loaded trade {ticket} from database into active monitoring")
        except Exception as e:
            logger.debug(f"Error checking database for new trades: {e}")
        
        # Monitor all trades in active_trades
        # FIX: Thread-safe snapshot creation
        with self.active_trades_lock:
            tickets = list(self.active_trades.keys())
        
        for ticket in tickets:
            try:
                # FIX: Defensive check - verify trade still exists before monitoring
                with self.active_trades_lock:
                    if ticket not in self.active_trades:
                        continue  # Trade was removed, skip
                
                self.monitor_trade(ticket)
            except Exception as e:
                logger.error(f"Error monitoring trade {ticket}: {e}", exc_info=True)
    
    def _unregister_trade(self, ticket: int):
        """
        Unregister a trade and clean up all state.
        
        Args:
            ticket: Position ticket
        """
        try:
            # FIX: Thread-safe removal from active trades
            with self.active_trades_lock:
                if ticket in self.active_trades:
                    del self.active_trades[ticket]
            
            # Remove from trade registry
            from infra.trade_registry import remove_trade_state
            remove_trade_state(ticket)
            
            # Clean up from database
            self._cleanup_trade_from_db(ticket)
            
            logger.info(f"Unregistered trade {ticket}")
        except Exception as e:
            logger.error(f"Error unregistering trade {ticket}: {e}", exc_info=True)
    
    def _load_trade_state_from_db(self, ticket: int) -> Optional[TradeState]:
        """
        Load TradeState from database.
        
        Args:
            ticket: Position ticket
            
        Returns:
            TradeState if found, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM universal_trades WHERE ticket = ?",
                    (ticket,)
                ).fetchone()
                
                if not row:
                    return None
                
                # Reconstruct TradeState
                strategy_type = self._normalize_strategy_type(row["strategy_type"])
                session = Session(row["session"])
                
                # Parse resolved_trailing_rules JSON
                try:
                    resolved_rules = json.loads(row["resolved_trailing_rules"])
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Error parsing resolved_trailing_rules for {ticket}: {e}")
                    resolved_rules = {}
                
                trade_state = TradeState(
                    ticket=row["ticket"],
                    symbol=row["symbol"],
                    strategy_type=strategy_type,
                    direction=row["direction"],
                    session=session,
                    resolved_trailing_rules=resolved_rules,
                    managed_by=row["managed_by"],
                    entry_price=row["entry_price"],
                    initial_sl=row["initial_sl"],
                    initial_tp=row["initial_tp"],
                    baseline_atr=row["baseline_atr"],
                    initial_volume=row["initial_volume"],
                    breakeven_triggered=bool(row["breakeven_triggered"]),
                    partial_taken=bool(row["partial_taken"]),
                    last_trailing_sl=row["last_trailing_sl"],
                    last_sl_modification_time=datetime.fromisoformat(row["last_sl_modification_time"]) if row["last_sl_modification_time"] else None,
                    registered_at=datetime.fromisoformat(row["registered_at"]),
                    plan_id=row["plan_id"] if "plan_id" in row.keys() else None
                )
                
                return trade_state
                
        except Exception as e:
            logger.error(f"Error loading trade state for {ticket}: {e}", exc_info=True)
            return None
    
    def _infer_strategy_type(self, ticket: int, position) -> Optional[StrategyType]:
        """
        Infer strategy type from plan_id or position comment.
        
        Args:
            ticket: Position ticket
            position: MT5 position object
            
        Returns:
            StrategyType if inferred, None otherwise
        """
        try:
            # Try to get plan_id from position comment
            comment = getattr(position, 'comment', '') or ''
            
            # Check if comment contains plan_id pattern
            # Format might be: "plan_id:xxx" or just the plan_id
            plan_id = None
            if 'plan_id:' in comment:
                plan_id = comment.split('plan_id:')[1].split()[0]
            elif comment and len(comment) > 0:
                # Try to use comment as plan_id directly
                plan_id = comment.strip()
            
            # If we have a plan_id, try to query the trade_plans table
            if plan_id:
                try:
                    # Try to get strategy_type from trade_plans table
                    # This assumes the trade_plans table exists and has a strategy_type column
                    import sqlite3
                    db_path = "data/trade_plans.db"  # Default path, may need adjustment
                    if os.path.exists(db_path):
                        with sqlite3.connect(db_path) as conn:
                            conn.row_factory = sqlite3.Row
                            row = conn.execute(
                                "SELECT conditions FROM trade_plans WHERE plan_id = ?",
                                (plan_id,)
                            ).fetchone()
                            
                            if row:
                                # Parse conditions JSON to get strategy_type
                                try:
                                    conditions = json.loads(row["conditions"])
                                    strategy_type_str = conditions.get("strategy_type")
                                    if strategy_type_str:
                                        return self._normalize_strategy_type(strategy_type_str)
                                except (json.JSONDecodeError, KeyError):
                                    pass
                except Exception as e:
                    logger.debug(f"Could not query trade_plans for {plan_id}: {e}")
            
            # Fallback: try to infer from position comment patterns
            comment_lower = comment.lower()
            if 'breakout' in comment_lower or 'ib' in comment_lower or 'volatility' in comment_lower:
                return StrategyType.BREAKOUT_IB_VOLATILITY_TRAP
            elif 'trend' in comment_lower or 'continuation' in comment_lower:
                return StrategyType.TREND_CONTINUATION_PULLBACK
            elif 'sweep' in comment_lower or 'reversal' in comment_lower:
                return StrategyType.LIQUIDITY_SWEEP_REVERSAL
            elif 'order' in comment_lower and 'block' in comment_lower:
                return StrategyType.ORDER_BLOCK_REJECTION
            elif 'mean' in comment_lower or 'reversion' in comment_lower or 'range' in comment_lower:
                return StrategyType.MEAN_REVERSION_RANGE_SCALP
            
            return None
            
        except Exception as e:
            logger.debug(f"Error inferring strategy type for {ticket}: {e}")
            return None
    
    def _cleanup_trade_from_db(self, ticket: int):
        """Remove trade from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM universal_trades WHERE ticket = ?", (ticket,))
        except Exception as e:
            logger.error(f"Error cleaning up trade {ticket} from DB: {e}")

