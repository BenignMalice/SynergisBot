"""
Intelligent Exit Manager - Advanced Trade Management
Automatically manages breakeven moves, partial profits, and volatility-based adjustments.

Features:
1. Auto-move SL to breakeven when profit targets are hit
2. Take partial profits at specified levels
3. Adjust SL based on VIX/volatility spikes
4. Per-trade customizable rules
5. Telegram notifications for all actions
"""

import logging
import json
import os
import sys
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

# Import the exit logger
try:
    from infra.intelligent_exit_logger import get_exit_logger
    exit_logger_available = True
except ImportError:
    logger.warning("intelligent_exit_logger not available - database logging disabled")
    exit_logger_available = False


class ExitRule:
    """Represents exit management rules for a single position"""
    
    def __init__(
        self,
        ticket: int,
        symbol: str,
        entry_price: float,
        direction: str,
        initial_sl: float,
        initial_tp: float,
        breakeven_profit_pct: float = 20.0,  # % of potential profit to trigger breakeven (20% = 0.2 R)
        partial_profit_pct: float = 50.0,  # % of potential profit for partial exit (50% = 0.5 R)
        partial_close_pct: float = 50.0,  # % to close at partial level (DISABLED if volume <= 0.01 lots)
        vix_threshold: float = 18.0,  # VIX level to trigger wider stops
        vix_multiplier: float = 1.5,  # SL multiplier when VIX > threshold
        use_hybrid_stops: bool = True,  # Use ATR + VIX hybrid for stop adjustment
        trailing_enabled: bool = True,  # Trailing starts after breakeven
        created_at: Optional[str] = None
    ):
        self.ticket = ticket
        self.symbol = symbol
        self.entry_price = entry_price
        self.direction = direction.lower()
        self.initial_sl = initial_sl
        self.initial_tp = initial_tp
        self.breakeven_profit_pct = breakeven_profit_pct
        self.partial_profit_pct = partial_profit_pct
        self.partial_close_pct = partial_close_pct
        
        # Calculate potential profit (R) for % calculations
        if direction.lower() == "buy":
            self.potential_profit = initial_tp - entry_price
            self.risk = entry_price - initial_sl
        else:  # sell
            self.potential_profit = entry_price - initial_tp
            self.risk = initial_sl - entry_price
        
        self.risk_reward_ratio = self.potential_profit / self.risk if self.risk > 0 else 0
        self.vix_threshold = vix_threshold
        self.vix_multiplier = vix_multiplier
        self.use_hybrid_stops = use_hybrid_stops
        self.trailing_enabled = trailing_enabled
        self.created_at = created_at or datetime.now().isoformat()
        
        # State tracking
        self.breakeven_triggered = False
        self.partial_triggered = False
        self.vix_adjustment_active = False
        self.hybrid_adjustment_active = False
        self.trailing_active = False  # NEW: Trailing starts after breakeven
        self.last_trailing_sl = None  # Track last trailing SL
        self.trailing_multiplier = 1.5  # NEW: Trailing distance multiplier (Phase 2)
        # Snapshot of advanced gating signals captured at rule creation (optional)
        self.advanced_gate: Dict[str, Any] = {}
        self.last_check = None
        self.original_trade_type: Optional[str] = None  # NEW: Store original classification for transition logic
        self.actions_taken = []
        # NEW: Metadata field for storing additional data (e.g., entry_delta for Phase 3.1 order flow flip exit)
        self.metadata: Dict[str, Any] = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage"""
        return {
            "ticket": self.ticket,
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "direction": self.direction,
            "initial_sl": self.initial_sl,
            "initial_tp": self.initial_tp,
            "breakeven_profit_pct": self.breakeven_profit_pct,
            "partial_profit_pct": self.partial_profit_pct,
            "partial_close_pct": self.partial_close_pct,
            "potential_profit": self.potential_profit,
            "risk": self.risk,
            "risk_reward_ratio": self.risk_reward_ratio,
            "vix_threshold": self.vix_threshold,
            "vix_multiplier": self.vix_multiplier,
            "use_hybrid_stops": self.use_hybrid_stops,
            "trailing_enabled": self.trailing_enabled,
            "created_at": self.created_at,
            "original_trade_type": self.original_trade_type,  # NEW: Weekend transition support
            "breakeven_triggered": self.breakeven_triggered,
            "partial_triggered": self.partial_triggered,
            "vix_adjustment_active": self.vix_adjustment_active,
            "hybrid_adjustment_active": self.hybrid_adjustment_active,
            "trailing_active": self.trailing_active,
            "last_trailing_sl": self.last_trailing_sl,
            "last_check": self.last_check,
            "actions_taken": self.actions_taken,
            "advanced_gate": self.advanced_gate,
            "metadata": self.metadata  # NEW: Include metadata in serialization
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExitRule':
        """Create from dictionary"""
        rule = cls(
            ticket=data["ticket"],
            symbol=data["symbol"],
            entry_price=data["entry_price"],
            direction=data["direction"],
            initial_sl=data["initial_sl"],
            initial_tp=data["initial_tp"],
            breakeven_profit_pct=data.get("breakeven_profit_pct", 30.0),
            partial_profit_pct=data.get("partial_profit_pct", 60.0),
            partial_close_pct=data.get("partial_close_pct", 50.0),
            vix_threshold=data.get("vix_threshold", 18.0),
            vix_multiplier=data.get("vix_multiplier", 1.5),
            use_hybrid_stops=data.get("use_hybrid_stops", True),
            trailing_enabled=data.get("trailing_enabled", True),
            created_at=data.get("created_at")
        )
        rule.breakeven_triggered = data.get("breakeven_triggered", False)
        rule.partial_triggered = data.get("partial_triggered", False)
        rule.vix_adjustment_active = data.get("vix_adjustment_active", False)
        rule.hybrid_adjustment_active = data.get("hybrid_adjustment_active", False)
        rule.trailing_active = data.get("trailing_active", False)
        rule.last_trailing_sl = data.get("last_trailing_sl")
        rule.trailing_multiplier = data.get("trailing_multiplier", 1.5)  # NEW: Phase 2, default 1.5 for backward compat
        rule.last_check = data.get("last_check")
        rule.actions_taken = data.get("actions_taken", [])
        rule.advanced_gate = data.get("advanced_gate", {})
        rule.original_trade_type = data.get("original_trade_type", None)  # NEW: Weekend transition support
        rule.metadata = data.get("metadata", {})  # NEW: Restore metadata field (Phase 3.1)
        return rule


class AdvancedProviderWrapper:
    """Wrapper to convert IndicatorBridge.get_multi() to Advanced features format"""
    
    def __init__(self, indicator_bridge, mt5_service=None):
        self.indicator_bridge = indicator_bridge
        self.mt5_service = mt5_service
        self._cache = {}  # Cache Advanced features (refresh every 60 seconds)
        self._cache_timestamps = {}
        self._cache_lock = threading.Lock()  # Thread safety for cache
        self._max_cache_size = 50  # Limit cache size
        self._cache_ttl = 60  # Cache TTL in seconds
    
    def get_advanced_features(self, symbol: str) -> Dict[str, Any]:
        """Get Advanced features for symbol, using cache to avoid excessive calls"""
        import time
        
        # Check cache (thread-safe)
        with self._cache_lock:
            cache_key = symbol
            if cache_key in self._cache:
                cache_age = time.time() - self._cache_timestamps.get(cache_key, 0)
                if cache_age < self._cache_ttl:
                    return self._cache[cache_key]
            
            # Cleanup old entries if cache too large
            if len(self._cache) >= self._max_cache_size:
                self._cleanup_cache()
        
        # Build features (outside lock to avoid blocking)
        try:
            # Use build_features_advanced to get actual Advanced features
            from infra.feature_builder_advanced import build_features_advanced
            
            if not self.mt5_service:
                # Try to get MT5 service from indicator_bridge if available
                if hasattr(self.indicator_bridge, 'mt5_service'):
                    mt5_svc = self.indicator_bridge.mt5_service
                else:
                    logger.warning(f"MT5 service unavailable for Advanced features: {symbol}")
                    return {}
            else:
                mt5_svc = self.mt5_service
            
            # Build Advanced features
            features = build_features_advanced(
                symbol=symbol,
                mt5svc=mt5_svc,
                bridge=self.indicator_bridge,
                timeframes=["M5", "M15", "H1"]
            )
            
            if features and "features" in features:
                # Store in cache (thread-safe)
                with self._cache_lock:
                    self._cache[cache_key] = features
                    self._cache_timestamps[cache_key] = time.time()
                return features
            
            return {}
        except Exception as e:
            logger.warning(f"Failed to get Advanced features for {symbol}: {e}")
            # Return stale cache if available (graceful degradation)
            with self._cache_lock:
                if cache_key in self._cache:
                    cache_age = time.time() - self._cache_timestamps.get(cache_key, 0)
                    if cache_age < self._cache_ttl * 2:  # Allow stale cache up to 2x TTL
                        logger.debug(f"Using stale cache for {symbol} (age: {cache_age:.0f}s)")
                        return self._cache[cache_key]
            return {}
    
    def _cleanup_cache(self):
        """Remove oldest cache entries"""
        import time
        current_time = time.time()
        
        # Remove expired entries first
        expired_keys = [
            k for k, ts in self._cache_timestamps.items()
            if current_time - ts > self._cache_ttl * 2
        ]
        for key in expired_keys:
            self._cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
        
        # If still too large, remove oldest entries
        if len(self._cache) >= self._max_cache_size:
            sorted_keys = sorted(
                self._cache_timestamps.items(),
                key=lambda x: x[1]
            )
            keys_to_remove = [
                k for k, _ in sorted_keys[:len(self._cache) - self._max_cache_size + 10]
            ]
            for key in keys_to_remove:
                self._cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
    
    def get_multi(self, symbol: str) -> Dict[str, Any]:
        """Fallback: return get_multi() result (for compatibility)"""
        if hasattr(self.indicator_bridge, 'get_multi'):
            return self.indicator_bridge.get_multi(symbol)
        return {}


class IntelligentExitManager:
    """
    Manages intelligent exit rules for open positions.
    
    Monitors positions and automatically:
    - Moves SL to breakeven when profit target is hit
    - Takes partial profits at specified levels
    - Adjusts SL when VIX exceeds threshold
    - Advanced-Enhanced: Adapts triggers based on market conditions (stretch, momentum, alignment)
    - Shadow Mode: Run DTMS alongside Intelligent Exits for comparison
    """
    
    def __init__(
        self,
        mt5_service,
        storage_file: str = "data/intelligent_exits.json",
        check_interval: int = 30,  # seconds between checks
        binance_service=None,  # NEW: Binance streaming service
        order_flow_service=None,  # NEW: Order flow service
        shadow_mode_enabled: bool = False,  # NEW: Shadow mode toggle
        shadow_mode_duration_days: int = 14  # NEW: Shadow mode duration
    ):
        # Phase 4: Initialize DTMS state caches for API queries
        self._dtms_state_cache = {}  # 10 second cache for DTMS state queries
        self._dtms_last_known_cache = {}  # 30 second TTL for last known state
        self.mt5 = mt5_service
        self.storage_file = Path(storage_file)
        self.check_interval = check_interval
        self.rules: Dict[int, ExitRule] = {}  # ticket -> ExitRule
        self.rules_lock = threading.Lock()  # NEW: Phase 9 - Protect rules dictionary from race conditions
        
        # Phase 12: Circuit breaker for ATR calculation failures
        self._atr_failure_count: Dict[str, int] = {}  # Track ATR failures per symbol
        self._atr_circuit_breaker_threshold = 5  # Open circuit after 5 failures
        self._atr_circuit_breaker_timeout = 300  # 5 minutes before retry
        self._atr_circuit_breaker_timestamps: Dict[str, float] = {}  # When circuit opened
        self._atr_fallback_values: Dict[str, float] = {}  # Fallback ATR values per symbol
        
        # NEW: Binance and order flow integration
        self.binance_service = binance_service
        self.order_flow_service = order_flow_service
        
        # NEW: Shadow mode configuration
        self.shadow_mode_enabled = shadow_mode_enabled
        self.shadow_mode_duration_days = shadow_mode_duration_days
        self.shadow_mode_start_date = None
        self.shadow_mode_end_date = None
        
        # NEW: Order flow auto-execution configuration
        self.whale_auto_tighten_sl = True  # Auto-tighten SL on whale alerts
        self.whale_auto_partial_exit = True  # Auto-partial exit on CRITICAL whales
        self.whale_critical_tighten_pct = 0.15  # Tighten SL to within 0.15% of current price for CRITICAL
        self.whale_high_tighten_pct = 0.25  # Tighten SL to within 0.25% for HIGH
        self.whale_critical_partial_pct = 50.0  # Close 50% on CRITICAL whale
        self.whale_high_partial_pct = 25.0  # Close 25% on HIGH whale
        
        self.void_auto_partial_exit = True  # Auto-partial exit before liquidity voids
        self.void_partial_exit_pct = 50.0  # Close 50% before void
        self.void_distance_threshold = 0.08  # Auto-close if within 0.08% (very close)
        self.void_close_all_threshold = 0.05  # Close 100% if within 0.05%
        
        # Shadow mode tracking
        if self.shadow_mode_enabled:
            self.shadow_mode_start_date = datetime.now()
            self.shadow_mode_end_date = self.shadow_mode_start_date + timedelta(days=shadow_mode_duration_days)
            logger.info(f"🔍 Shadow Mode ENABLED - Duration: {shadow_mode_duration_days} days")
            logger.info(f"   Start: {self.shadow_mode_start_date.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"   End: {self.shadow_mode_end_date.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            logger.info("📊 Standard Intelligent Exit Mode - Shadow mode disabled")
        
        # Initialize database logger
        self.db_logger = None
        if exit_logger_available:
            try:
                self.db_logger = get_exit_logger()
                logger.info("Database logging enabled for intelligent exits")
            except Exception as e:
                logger.warning(f"Failed to initialize database logger: {e}")
        
        # Ensure data directory exists
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing rules
        self._load_rules()
        
        # Log integration status
        integrations = []
        if binance_service:
            integrations.append("Binance streaming")
        if order_flow_service:
            integrations.append("Order flow")
        
        integration_status = " + ".join(integrations) if integrations else "MT5 only"
        logger.info(f"IntelligentExitManager initialized (storage: {self.storage_file}) - Advanced-Enhanced exits enabled")
        logger.info(f"   Real-time data: {integration_status}")
    
    def add_rule(
        self,
        ticket: int,
        symbol: str,
        entry_price: float,
        direction: str,
        initial_sl: float,
        initial_tp: float,
        breakeven_profit_pct: float = 20.0,
        partial_profit_pct: float = 50.0,
        partial_close_pct: float = 50.0,
        vix_threshold: float = 18.0,
        vix_multiplier: float = 1.5,
        use_hybrid_stops: bool = True,
        trailing_enabled: bool = True,
        is_startup_recovery: bool = False
    ) -> ExitRule:
        """Add exit management rule for a position"""
        rule = ExitRule(
            ticket=ticket,
            symbol=symbol,
            entry_price=entry_price,
            direction=direction,
            initial_sl=initial_sl,
            initial_tp=initial_tp,
            breakeven_profit_pct=breakeven_profit_pct,
            partial_profit_pct=partial_profit_pct,
            partial_close_pct=partial_close_pct,
            vix_threshold=vix_threshold,
            vix_multiplier=vix_multiplier,
            use_hybrid_stops=use_hybrid_stops,
            trailing_enabled=trailing_enabled
        )
        
        self.rules[ticket] = rule

        # Note: Advanced gate capture removed from add_rule() - use add_rule_advanced() instead
        # This prevents NameError when advanced_features is not available
        rule.advanced_gate = {}

        self._save_rules()
        
        # Log rule addition to database
        if self.db_logger:
            try:
                self.db_logger.log_action(
                    ticket=ticket,
                    symbol=symbol,
                    action_type="rule_added",
                    details={
                        "entry_price": entry_price,
                        "direction": direction,
                        "initial_sl": initial_sl,
                        "initial_tp": initial_tp,
                        "breakeven_profit_pct": breakeven_profit_pct,
                        "partial_profit_pct": partial_profit_pct,
                        "partial_close_pct": partial_close_pct,
                        "vix_threshold": vix_threshold,
                        "vix_multiplier": vix_multiplier,
                        "use_hybrid_stops": use_hybrid_stops,
                        "trailing_enabled": trailing_enabled,
                        "potential_profit": rule.potential_profit,
                        "risk": rule.risk,
                        "risk_reward_ratio": rule.risk_reward_ratio
                    },
                    success=True
                )
            except Exception as e:
                logger.warning(f"Failed to log rule addition to database: {e}")
        
        if is_startup_recovery:
            logger.info(f"🔄 Recovered exit rule for ticket {ticket} ({symbol}) - monitoring resumed")
        else:
            logger.info(f"✅ Added exit rule for ticket {ticket} ({symbol})")
            logger.warning(
                f"⚠️ IMPORTANT: Intelligent exit management requires the Telegram bot (chatgpt_bot.py) "
                f"to be running continuously. If the bot is not running, breakeven/partial profit/trailing "
                f"stops will NOT execute automatically! Ensure chatgpt_bot.py is active."
            )
        return rule
    
    def _get_rmag_threshold(self, symbol: str) -> float:
        """Get asset-specific RMAG threshold, handling symbol normalization
        
        Uses same normalization pattern as desktop_agent.py (lines 2129-2131)
        """
        from config.settings import RMAG_STRETCH_THRESHOLDS
        
        # Normalize symbol (same pattern as desktop_agent.py)
        symbol_normalized = symbol.upper()
        if symbol_normalized not in ['DXY', 'VIX', 'US10Y', 'SPX']:
            if not symbol_normalized.endswith('C'):
                symbol_normalized = symbol_normalized + 'C'
            else:
                symbol_normalized = symbol_normalized.rstrip('cC') + 'C'
        
        # Try exact match first
        if symbol_normalized in RMAG_STRETCH_THRESHOLDS:
            return RMAG_STRETCH_THRESHOLDS[symbol_normalized]
        
        # Try without 'c' suffix
        symbol_base = symbol_normalized.rstrip('cC')
        if symbol_base in RMAG_STRETCH_THRESHOLDS:
            return RMAG_STRETCH_THRESHOLDS[symbol_base]
        
        # Default
        return RMAG_STRETCH_THRESHOLDS.get("DEFAULT", 2.0)
    
    def _get_symbol_exit_params(self, symbol: str, session: Optional[str] = None) -> Dict[str, Any]:
        """
        Get symbol-specific exit parameters with session adjustments (Phase 11).
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDc", "XAUUSDc")
            session: Current trading session (e.g., "ASIAN", "LONDON", "NY", "OVERLAP")
        
        Returns:
            Dict with symbol-specific parameters (trailing_atr_multiplier, breakeven_buffer_atr_mult, etc.)
        """
        from config.settings import INTELLIGENT_EXIT_SYMBOL_PARAMS
        
        # Normalize symbol (same pattern as Phase 1)
        symbol_normalized = symbol.upper()
        if symbol_normalized not in ['DXY', 'VIX', 'US10Y', 'SPX']:
            if not symbol_normalized.endswith('C'):
                symbol_normalized = symbol_normalized + 'C'
            else:
                symbol_normalized = symbol_normalized.rstrip('cC') + 'C'
        
        # Get base params
        params = INTELLIGENT_EXIT_SYMBOL_PARAMS.get(symbol_normalized) or \
                 INTELLIGENT_EXIT_SYMBOL_PARAMS.get(symbol_normalized.rstrip('cC')) or \
                 INTELLIGENT_EXIT_SYMBOL_PARAMS.get("DEFAULT", {})
        
        # Apply session adjustments if available
        if session and "session_adjustments" in params:
            session_adj = params["session_adjustments"].get(session, {})
            if session_adj:
                params = params.copy()  # Don't modify original
                if "trailing_mult" in session_adj:
                    params["trailing_atr_multiplier"] = session_adj["trailing_mult"]
                if "buffer_mult" in session_adj:
                    params["breakeven_buffer_atr_mult"] = session_adj["buffer_mult"]
        
        return params
    
    def _calculate_advanced_triggers(
        self, 
        advanced_features: Optional[Dict[str, Any]],
        base_breakeven_pct: float = 30.0,
        base_partial_pct: float = 60.0,
        symbol: Optional[str] = None  # NEW: Add symbol parameter
    ) -> Dict[str, Any]:
        """
        Calculate adaptive trigger levels based on Advanced market conditions.

        Returns dict with:
        - breakeven_pct: Adjusted breakeven trigger percentage
        - partial_pct: Adjusted partial profit trigger percentage
        - reasoning: Human-readable explanation of adjustments
        - advanced_factors: List of Advanced factors that influenced the adjustment
        """
        
        if not advanced_features:
            return {
                "breakeven_pct": base_breakeven_pct,
                "partial_pct": base_partial_pct,
                "reasoning": "No Advanced features available - using standard triggers",
                "advanced_factors": []
            }
        
        # Start with base values
        breakeven_pct = base_breakeven_pct
        partial_pct = base_partial_pct
        adjustments = []
        advanced_factors = []
        
        # Extract Advanced features from nested structure
        # Advanced features come from getMarketData() as v8_insights → timeframes → M5/M15/H1
        # OR from build_features_advanced() as features → M15/M5/H1
        # We'll use M15 as the primary timeframe for exit decisions
        v8_data = None
        
        # Try v8_insights structure (from API)
        if "v8_insights" in advanced_features:
            timeframes = advanced_features["v8_insights"].get("timeframes", {})
            v8_data = timeframes.get("M15") or timeframes.get("M5") or timeframes.get("H1")
        
        # Try features structure (from build_features_advanced)
        if not v8_data and "features" in advanced_features:
            features = advanced_features["features"]
            v8_data = features.get("M15") or features.get("M5") or features.get("H1")
        
        # Try direct access (if Advanced features passed as flat dict)
        if not v8_data:
            v8_data = advanced_features
        
        # 1. RMAG (Price Stretch) - TIGHTEN if stretched
        rmag = v8_data.get("rmag", {})
        ema200_atr = rmag.get("ema200_atr", 0)
        vwap_atr = rmag.get("vwap_atr", 0)
        
        # Get asset-specific threshold
        rmag_threshold = self._get_rmag_threshold(symbol or "UNKNOWN")
        
        if abs(ema200_atr) > rmag_threshold or abs(vwap_atr) > (rmag_threshold * 0.9):
            # Only tighten if EXTREME stretch (above asset-specific threshold)
            breakeven_pct = 20.0
            partial_pct = 40.0
            stretch_direction = "above" if ema200_atr > 0 else "below"
            adjustments.append(f"RMAG stretched ({ema200_atr:.1f}σ {stretch_direction} EMA200, threshold={rmag_threshold}σ) → TIGHTEN to 20%/40%")
            advanced_factors.append("rmag_stretched")
        
        # 2. EMA Slope - WIDEN for quality trends
        ema_slope = v8_data.get("ema_slope", {})
        ema50_slope = ema_slope.get("ema50", 0)
        ema200_slope = ema_slope.get("ema200", 0)
        
        quality_uptrend = ema50_slope > 0.15 and ema200_slope > 0.05
        quality_downtrend = ema50_slope < -0.15 and ema200_slope < -0.05
        
        if (quality_uptrend or quality_downtrend) and abs(ema200_atr) < 1.5:
            # Quality trend + NOT stretched → Let it RUN (40%/70%)
            if "rmag_stretched" not in advanced_factors:  # Don't override stretch tightening
                breakeven_pct = max(breakeven_pct, 40.0)
                partial_pct = max(partial_pct, 70.0)
                adjustments.append("Quality EMA trend + normal range → WIDEN to 40%/70%")
                advanced_factors.append("quality_trend")
        
        # 3. Volatility State - TIGHTEN for squeezes
        vol_state = v8_data.get("vol_trend", {})
        state = vol_state.get("state", "")
        
        if "squeeze" in state:
            # Squeeze state → Breakout imminent, TIGHTEN (20%/40%)
            if "rmag_stretched" not in advanced_factors:
                breakeven_pct = min(breakeven_pct, 25.0)
                partial_pct = min(partial_pct, 50.0)
                adjustments.append(f"Volatility squeeze ({state}) → TIGHTEN to 25%/50%")
                advanced_factors.append("squeeze")
        
        # 4. Momentum Quality - TIGHTEN for fake momentum
        pressure = v8_data.get("pressure", {})
        is_fake = pressure.get("is_fake", False)
        
        if is_fake:
            # Fake momentum (high RSI + weak ADX) → Fade risk HIGH
            breakeven_pct = min(breakeven_pct, 20.0)
            partial_pct = min(partial_pct, 40.0)
            adjustments.append("Fake momentum (high RSI + weak ADX) → TIGHTEN to 20%/40%")
            advanced_factors.append("fake_momentum")
        
        # 5. MTF Alignment - WIDEN for strong alignment
        mtf_score_data = v8_data.get("mtf_score", {})
        mtf_score = mtf_score_data.get("score", 0)
        
        if mtf_score >= 2 and "quality_trend" in advanced_factors:
            # Strong MTF alignment + quality trend → MAXIMIZE (40%/80%)
            breakeven_pct = max(breakeven_pct, 40.0)
            partial_pct = max(partial_pct, 80.0)
            adjustments.append(f"Strong MTF alignment ({mtf_score}/3) + quality trend → WIDEN to 40%/80%")
            advanced_factors.append("mtf_aligned")
        
        # 6. Liquidity Targets - TIGHTEN if near liquidity zone
        liquidity = v8_data.get("liquidity", {})
        pdl_dist = liquidity.get("pdl_dist_atr", 999)
        pdh_dist = liquidity.get("pdh_dist_atr", 999)
        equal_highs = liquidity.get("equal_highs", False)
        equal_lows = liquidity.get("equal_lows", False)
        
        if pdl_dist < 0.5 or pdh_dist < 0.5 or equal_highs or equal_lows:
            # Near liquidity zone → Stop hunt risk, TIGHTEN
            breakeven_pct = min(breakeven_pct, 25.0)
            partial_pct = min(partial_pct, 50.0)
            adjustments.append("Near liquidity zone (PDH/PDL/equal highs-lows) → TIGHTEN to 25%/50%")
            advanced_factors.append("liquidity_risk")
        
        # 7. VWAP Deviation - TIGHTEN for outer zone
        vwap_dev = v8_data.get("vwap_dev", {})
        zone = vwap_dev.get("zone", "inside")
        
        if zone == "outer":
            # Outer VWAP zone → Mean reversion risk HIGH
            breakeven_pct = min(breakeven_pct, 25.0)
            partial_pct = min(partial_pct, 45.0)
            adjustments.append("Outer VWAP zone → Mean reversion risk, TIGHTEN to 25%/45%")
            advanced_factors.append("vwap_outer")
        
        # Build reasoning
        if not adjustments:
            reasoning = "No Advanced adjustments needed - market conditions normal (using standard 30%/60%)"
        else:
            reasoning = " | ".join(adjustments)
        
        return {
            "breakeven_pct": round(breakeven_pct, 1),
            "partial_pct": round(partial_pct, 1),
            "reasoning": reasoning,
            "advanced_factors": advanced_factors,
            "base_breakeven_pct": base_breakeven_pct,
            "base_partial_pct": base_partial_pct
        }
    
    def add_rule_advanced(
        self,
        ticket: int,
        symbol: str,
        entry_price: float,
        direction: str,
        initial_sl: float,
        initial_tp: float,
        advanced_features: Optional[Dict[str, Any]] = None,
        base_breakeven_pct: float = 20.0,
        base_partial_pct: float = 50.0,
        partial_close_pct: float = 50.0,
        vix_threshold: float = 18.0,
        vix_multiplier: float = 1.5,
        use_hybrid_stops: bool = True,
        trailing_enabled: bool = True,
        is_startup_recovery: bool = False,
        trailing_atr_multiplier: Optional[float] = None  # NEW: Weekend support
    ) -> Dict[str, Any]:
        """
        Add Advanced-enhanced exit management rule for a position.
        
        Advanced features automatically adjust breakeven/partial triggers based on:
        - RMAG stretch (tighten if >2σ)
        - EMA slope quality (widen for quality trends)
        - Volatility state (tighten for squeezes)
        - Momentum quality (tighten for fake momentum)
        - MTF alignment (widen for strong confluence)
        - Liquidity proximity (tighten near PDH/PDL)
        - VWAP deviation (tighten in outer zone)
        
        Returns: Dict with rule and Advanced adjustment details
        """

        # Calculate Advanced-adjusted triggers
        advanced_result = self._calculate_advanced_triggers(
            advanced_features=advanced_features,
            base_breakeven_pct=base_breakeven_pct,
            base_partial_pct=base_partial_pct,
            symbol=symbol  # NEW: Pass symbol for asset-specific thresholds
        )
        
        # Create rule with adjusted triggers
        rule = ExitRule(
            ticket=ticket,
            symbol=symbol,
            entry_price=entry_price,
            direction=direction,
            initial_sl=initial_sl,
            initial_tp=initial_tp,
            breakeven_profit_pct=advanced_result["breakeven_pct"],
            partial_profit_pct=advanced_result["partial_pct"],
            partial_close_pct=partial_close_pct,
            vix_threshold=vix_threshold,
            vix_multiplier=vix_multiplier,
            use_hybrid_stops=use_hybrid_stops,
            trailing_enabled=trailing_enabled
        )
        
        # Set trailing multiplier if provided (for weekend trades)
        if trailing_atr_multiplier is not None:
            rule.trailing_multiplier = trailing_atr_multiplier
        
        # Store original trade type for transition logic (if provided in advanced_features)
        if advanced_features and "classification" in advanced_features:
            classification = advanced_features.get("classification", {})
            rule.original_trade_type = classification.get("trade_type")
        
        # Phase 9: Thread-safe dictionary access
        with self.rules_lock:
            self.rules[ticket] = rule
        self._save_rules()  # Save after releasing lock
        
        # Log Advanced-enhanced rule addition to database
        if self.db_logger:
            try:
                self.db_logger.log_action(
                    ticket=ticket,
                    symbol=symbol,
                    action_type="rule_added_v8",
                    details={
                        "entry_price": entry_price,
                        "direction": direction,
                        "initial_sl": initial_sl,
                        "initial_tp": initial_tp,
                        "base_breakeven_pct": base_breakeven_pct,
                        "base_partial_pct": base_partial_pct,
                        "advanced_breakeven_pct": advanced_result["breakeven_pct"],
                        "advanced_partial_pct": advanced_result["partial_pct"],
                        "advanced_reasoning": advanced_result["reasoning"],
                        "advanced_factors": advanced_result["advanced_factors"],
                        "partial_close_pct": partial_close_pct,
                        "vix_threshold": vix_threshold,
                        "use_hybrid_stops": use_hybrid_stops,
                        "trailing_enabled": trailing_enabled,
                        "potential_profit": rule.potential_profit,
                        "risk": rule.risk,
                        "risk_reward_ratio": rule.risk_reward_ratio
                    },
                    success=True
                )
            except Exception as e:
                logger.warning(f"Failed to log Advanced rule addition to database: {e}")
        
        if is_startup_recovery:
            logger.info(f"🔄 Recovered Advanced-enhanced exit rule for ticket {ticket} ({symbol})")
        else:
            logger.info(
                f"✅ Added Advanced-enhanced exit rule for ticket {ticket} ({symbol})\n"
                f"   Base triggers: {base_breakeven_pct}% / {base_partial_pct}%\n"
                f"   Advanced-adjusted: {advanced_result['breakeven_pct']}% / {advanced_result['partial_pct']}%\n"
                f"   Reasoning: {advanced_result['reasoning']}\n"
                f"   Advanced factors: {', '.join(advanced_result['advanced_factors']) if advanced_result['advanced_factors'] else 'None'}"
            )
        
        return {
            "rule": rule,
            "advanced_adjustments": advanced_result,
            "success": True
        }
    
    def _cleanup_stale_rules(self):
        """Remove rules for positions that are no longer open"""
        try:
            # Get all open positions
            if not self.mt5.connect():
                logger.warning("MT5 not connected, skipping stale rule cleanup")
                return
            positions = mt5.positions_get()
            open_tickets = {pos.ticket for pos in positions} if positions else set()
            
            # Phase 9: Thread-safe dictionary access - create snapshot
            with self.rules_lock:
                stale_tickets = [ticket for ticket in self.rules.keys() if ticket not in open_tickets]
            
            if stale_tickets:
                logger.info(f"🧹 Removing {len(stale_tickets)} stale exit rule(s) (positions closed)")
                for ticket in stale_tickets:
                    # Phase 9: Thread-safe access
                    with self.rules_lock:
                        rule = self.rules.get(ticket)
                        if not rule:
                            continue  # Rule already removed
                    
                    logger.info(f"   → Removing rule for ticket {ticket} ({rule.symbol}) - position closed")
                    
                    # Log removal to database (outside lock)
                    if self.db_logger:
                        try:
                            self.db_logger.log_action(
                                ticket=ticket,
                                symbol=rule.symbol,
                                action_type="rule_removed_stale",
                                details={
                                    "reason": "position_closed",
                                    "created_at": rule.created_at,
                                    "actions_taken": rule.actions_taken
                                }
                            )
                        except Exception as e:
                            logger.debug(f"Failed to log stale rule removal: {e}")
                    
                    # Remove from memory (thread-safe)
                    with self.rules_lock:
                        if ticket in self.rules:  # Double-check it still exists
                            del self.rules[ticket]
                
                # Save updated rules (outside lock)
                self._save_rules()
                logger.info(f"✅ Cleanup complete - {len(self.rules)} active rule(s) remaining")
            else:
                logger.debug("No stale rules found - all rules match open positions")
                
        except Exception as e:
            logger.error(f"Error during stale rule cleanup: {e}", exc_info=True)
    
    def remove_rule(self, ticket: int) -> bool:
        """Remove exit rule (called when position closes) - Phase 9: Thread-safe"""
        # Phase 9: Thread-safe access
        with self.rules_lock:
            if ticket not in self.rules:
                return False
            rule = self.rules[ticket]  # Get rule while holding lock
        
        # Log rule removal to database (outside lock to avoid blocking)
        if self.db_logger:
            try:
                self.db_logger.log_action(
                    ticket=ticket,
                    symbol=rule.symbol,
                    action_type="rule_removed",
                    details={
                        "actions_taken": rule.actions_taken,
                        "breakeven_triggered": rule.breakeven_triggered,
                        "partial_triggered": rule.partial_triggered,
                        "hybrid_adjustment_active": rule.hybrid_adjustment_active,
                        "trailing_active": rule.trailing_active,
                        "duration": (datetime.now() - datetime.fromisoformat(rule.created_at)).total_seconds() if rule.created_at else None
                    },
                    success=True
                )
            except Exception as e:
                logger.warning(f"Failed to log rule removal to database: {e}")
        
        # Remove from dictionary (thread-safe)
        with self.rules_lock:
            if ticket in self.rules:  # Double-check it still exists
                del self.rules[ticket]
        
        self._save_rules()  # Save after releasing lock
        logger.info(f"Removed exit rule for ticket {ticket}")
        return True
    
    def get_rule(self, ticket: int) -> Optional[ExitRule]:
        """Get exit rule for a ticket - Phase 9: Thread-safe"""
        with self.rules_lock:
            return self.rules.get(ticket)
    
    def get_all_rules(self) -> List[ExitRule]:
        """Get all active exit rules - Phase 9: Thread-safe"""
        with self.rules_lock:
            return list(self.rules.values())
    
    def check_exits(self, vix_price: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Check all positions with exit rules and execute actions as needed.
        
        Args:
            vix_price: Current VIX price (if None, will fetch from Yahoo Finance)
        
        Returns:
            List of actions taken
        """
        actions = []
        
        if not self.rules:
            return actions
        
        # Connect to MT5
        if not self.mt5.connect():
            logger.warning("MT5 not connected, skipping exit check")
            return actions
        
        # Get VIX if not provided
        if vix_price is None:
            vix_price = self._get_vix_price()
        
        # Get all open positions
        positions = mt5.positions_get()
        if positions is None:
            # MT5 error - do NOT clean up rules
            logger.error(f"MT5 positions_get() returned None - skipping check. Error: {mt5.last_error()}")
            return actions
        elif len(positions) == 0:
            # Truly no positions - clean up ALL rules
            # Phase 9: Thread-safe snapshot
            with self.rules_lock:
                closed_tickets = list(self.rules.keys())
            logger.info(f"No open positions found, cleaning up {len(closed_tickets)} rule(s)")
            for ticket in closed_tickets:
                self.remove_rule(ticket)
            return actions
        
        position_tickets = {pos.ticket for pos in positions}
        
        # Phase 9: Thread-safe snapshot for iteration
        with self.rules_lock:
            tickets = list(self.rules.keys())
        
        # Check each rule (iterate over snapshot)
        for ticket in tickets:
            # Phase 9: Thread-safe access
            with self.rules_lock:
                rule = self.rules.get(ticket)
                if not rule:
                    continue  # Rule removed, skip
            
            # Process rule (outside lock to avoid deadlock)
            # If position is closed, remove rule
            if ticket not in position_tickets:
                # Log enhanced closure information and get closure details
                closure_info = self._log_position_closure(ticket, rule)
                if closure_info:
                    # Add closure as an action for Telegram notification
                    actions.append({
                        "type": "position_closed",
                        "ticket": ticket,
                        **closure_info
                    })
                self.remove_rule(ticket)
                continue
            
            # Get position and verify it still exists (race condition protection)
            position = next((p for p in positions if p.ticket == ticket), None)
            if not position:
                # Position was closed between the check and now - skip it
                logger.debug(f"Position {ticket} no longer found, skipping (likely closed)")
                continue
            
            # Double-check position still exists in MT5 (prevents using stale position data)
            current_position = mt5.positions_get(ticket=ticket)
            if not current_position or len(current_position) == 0:
                logger.debug(f"Position {ticket} verified as closed, removing rule")
                closure_info = self._log_position_closure(ticket, rule)
                if closure_info:
                    actions.append({
                        "type": "position_closed",
                        "ticket": ticket,
                        **closure_info
                    })
                self.remove_rule(ticket)
                continue
            
            # Use the current position data (not stale)
            position = current_position[0]
            
            # Phase 3.1: Check order flow flip exit first (highest priority)
            if self.order_flow_service and hasattr(self.order_flow_service, 'running') and self.order_flow_service.running:
                try:
                    flip_exit = self._check_order_flow_flip(ticket, rule, position)
                    if flip_exit:
                        actions.append({
                            "ticket": ticket,
                            "action": "close",
                            "reason": "order_flow_flip",
                            "details": flip_exit,
                            "priority": "high"
                        })
                        logger.info(
                            f"Phase 3.1: Order flow flip detected for {rule.symbol} ticket {ticket} "
                            f"(entry_delta: {flip_exit.get('entry_delta', 'N/A')}, "
                            f"current_delta: {flip_exit.get('current_delta', 'N/A')}, "
                            f"flip: {flip_exit.get('flip_percentage', 0):.1f}%)"
                        )
                        continue  # Skip other exit checks if flip detected
                except Exception as e:
                    logger.debug(f"Error checking order flow flip for ticket {ticket}: {e}")
            
            # ⚠️ CRITICAL: Check ownership - allow Intelligent Exit Manager to manage until breakeven
            try:
                from infra.trade_registry import get_trade_state
                import sqlite3
                from pathlib import Path
                
                # First check in-memory registry
                trade_state = get_trade_state(ticket)
                
                # If not in memory, check database (for trades registered via API)
                breakeven_triggered = False
                if not trade_state:
                    db_path = Path("data/universal_sl_tp_trades.db")
                    if db_path.exists():
                        try:
                            with sqlite3.connect(str(db_path)) as conn:
                                cursor = conn.execute("""
                                    SELECT managed_by, breakeven_triggered FROM universal_trades 
                                    WHERE ticket = ? AND managed_by = 'universal_sl_tp_manager'
                                """, (ticket,))
                                row = cursor.fetchone()
                                if row:
                                    breakeven_triggered = bool(row[1])
                                    # If breakeven triggered, Universal Manager takes over - skip Intelligent Exit Manager
                                    if breakeven_triggered:
                                        logger.debug(
                                            f"Skipping intelligent exit check for {ticket}: "
                                            f"breakeven triggered - Universal Manager takes over"
                                        )
                                        continue
                                    # If not breakeven yet, Intelligent Exit Manager can manage it
                                    logger.debug(
                                        f"Trade {ticket} registered with Universal Manager but breakeven not triggered - "
                                        f"Intelligent Exit Manager will handle breakeven"
                                    )
                        except Exception as db_error:
                            logger.debug(f"Error checking database for trade {ticket}: {db_error}")
                
                # Check in-memory registry result
                if trade_state:
                    if trade_state.managed_by == "universal_sl_tp_manager":
                        # Check if breakeven already triggered
                        if trade_state.breakeven_triggered:
                            logger.debug(
                                f"Skipping intelligent exit check for {ticket}: "
                                f"breakeven triggered - Universal Manager takes over"
                            )
                            continue
                        # If not breakeven yet, Intelligent Exit Manager can manage it
                        logger.debug(
                            f"Trade {ticket} registered with Universal Manager but breakeven not triggered - "
                            f"Intelligent Exit Manager will handle breakeven"
                        )
                    # DTMS defensive actions take priority, but normal DTMS actions don't block intelligent exits
                    # (Intelligent exits can still run alongside DTMS normal actions)
            except ImportError:
                # Trade registry not available - continue with normal logic
                pass
            except Exception as e:
                logger.debug(f"Error checking trade ownership for {ticket}: {e}")
                # Continue with normal logic on error
            
            # 🔴 CRITICAL: Skip range scalping trades (handled by RangeScalpingExitManager)
            # Check if this ticket is managed by RangeScalpingExitManager
            try:
                # Try to get RangeScalpingExitManager from registry or check position comment
                is_range_scalp = False
                
                # Check position comment for range scalp identifier
                if position.comment:
                    comment_lower = position.comment.lower()
                    if "range_scalp" in comment_lower or "range scalping" in comment_lower:
                        is_range_scalp = True
                
                # Also check if ticket is in RangeScalpingExitManager's active trades
                # (if available via registry or global reference)
                if not is_range_scalp:
                    try:
                        # Attempt to check RangeScalpingExitManager (may not be initialized)
                        from desktop_agent import registry
                        if hasattr(registry, 'range_scalp_exit_manager') and registry.range_scalp_exit_manager:
                            active_range_tickets = registry.range_scalp_exit_manager.get_active_ticket_list()
                            if ticket in active_range_tickets:
                                is_range_scalp = True
                    except (ImportError, AttributeError, Exception):
                        # RangeScalpingExitManager not available or ticket not found - continue normally
                        pass
                
                if is_range_scalp:
                    logger.debug(f"Skipping intelligent exit check for range scalping trade {ticket}")
                    continue  # Skip this position - RangeScalpingExitManager handles it
            except Exception as e:
                logger.debug(f"Error checking if trade {ticket} is range scalp: {e}")
                # Continue with normal processing if check fails
            
            try:
                # Refresh Advanced gates from provider (if available)
                try:
                    self._update_advanced_gate(rule)
                except Exception:
                    pass
                
                # Phase 10: Optional Advanced triggers refresh (only if breakeven not triggered)
                # Refresh every 5 minutes (300 seconds) to adapt to changing market conditions
                try:
                    if not rule.breakeven_triggered:
                        # Check if enough time has passed since last refresh (if tracked)
                        # For now, refresh on every check_exits call (can be optimized later)
                        refresh_result = self.refresh_advanced_triggers(ticket)
                        if refresh_result:
                            logger.debug(f"Advanced triggers refreshed for ticket {ticket}")
                except Exception as e:
                    logger.debug(f"Advanced triggers refresh failed for ticket {ticket}: {e}")
                
                # Check and execute exit actions
                rule_actions = self._check_position_exits(rule, position, vix_price)
                actions.extend(rule_actions)
                
                # Update last check time
                rule.last_check = datetime.now().isoformat()
                
            except Exception as e:
                logger.error(f"Error checking exits for ticket {ticket}: {e}", exc_info=True)
        
        # Save updated rules
        if actions:
            self._save_rules()
        
        return actions

    def _update_advanced_gate(self, rule: ExitRule) -> None:
        """Refresh rule.advanced_gate from an optional advanced provider.
        
        Provider may expose:
          - get_advanced_features(symbol) -> { features: { M5|M15|H1: {...}, mtf_score, vp } }
          - or get_multi(symbol) -> { M5|M15|H1: {...} }
        """
        ap = getattr(self, "advanced_provider", None)
        if not ap:
            return
        features = None
        try:
            if hasattr(ap, "get_advanced_features"):
                out = ap.get_advanced_features(rule.symbol)
                if isinstance(out, dict):
                    features = out.get("features")
            if features is None and hasattr(ap, "get_multi"):
                multi = ap.get_multi(rule.symbol)
                if isinstance(multi, dict):
                    features = {"M5": multi.get("M5", {}), "M15": multi.get("M15", {}), "H1": multi.get("H1", {})}
        except Exception:
            return
        if not features or not isinstance(features, dict):
            return
        v8 = features.get("M15") or features.get("M5") or features.get("H1") or {}
        rmag = (v8.get("rmag") or {})
        ema_slope = (v8.get("ema_slope") or {})
        vol_trend = (v8.get("vol_trend") or {})
        vwap_dev = (v8.get("vwap") or v8.get("vwap_dev") or {})
        mtf = features.get("mtf_score", {}) or v8.get("mtf_score", {})
        vp = features.get("vp", {}) or v8.get("vp", {})
        gate = {
            "ema50_slope": float(ema_slope.get("ema50", 0) or 0),
            "ema200_slope": float(ema_slope.get("ema200", 0) or 0),
            "vol_state": str(vol_trend.get("state", "")),
            "ema200_atr": float(rmag.get("ema200_atr", 0) or 0),
            "vwap_zone": str(vwap_dev.get("zone", "inside")),
            "mtf_total": int(mtf.get("total", mtf.get("score", 0)) or 0),
            "mtf_max": int(mtf.get("max", 3) or 3),
            "hvn_dist_atr": float(vp.get("hvn_dist_atr", 999) or 999),
        }
        rule.advanced_gate = gate
        try:
            logger.debug(
                f"Gates refresh for {rule.symbol} ticket {rule.ticket}: "
                f"vol={gate['vol_state']} mtf={gate['mtf_total']}/{gate['mtf_max']} "
                f"rmag={gate['ema200_atr']:.2f} vwap={gate['vwap_zone']} hvn={gate['hvn_dist_atr']:.2f}"
            )
        except Exception:
            pass
    
    def refresh_advanced_triggers(
        self, 
        ticket: int, 
        advanced_features: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Refresh Advanced triggers mid-trade (Phase 10: Optional Enhancement).
        
        This allows recalculation of Advanced-Enhanced exit triggers during a trade,
        adapting to changing market conditions. Only refreshes if breakeven hasn't
        been triggered yet (conservative approach).
        
        Args:
            ticket: Trade ticket number
            advanced_features: Optional Advanced features dict. If None, will fetch
                             from advanced_provider if available.
        
        Returns:
            Dict with updated triggers and reasoning, or None if refresh not applicable
        """
        # Phase 9: Thread-safe access
        with self.rules_lock:
            rule = self.rules.get(ticket)
            if not rule:
                logger.debug(f"Refresh requested for ticket {ticket} but rule not found")
                return None
        
        # Only refresh if breakeven not yet triggered (conservative)
        if rule.breakeven_triggered:
            logger.debug(f"Refresh skipped for ticket {ticket} - breakeven already triggered")
            return None
        
        # Fetch Advanced features if not provided
        if advanced_features is None:
            ap = getattr(self, "advanced_provider", None)
            if ap:
                try:
                    if hasattr(ap, "get_advanced_features"):
                        features_output = ap.get_advanced_features(rule.symbol)
                        if isinstance(features_output, dict):
                            advanced_features = features_output.get("features") or features_output
                    elif hasattr(ap, "get_multi"):
                        multi = ap.get_multi(rule.symbol)
                        if isinstance(multi, dict):
                            advanced_features = {
                                "M5": multi.get("M5", {}),
                                "M15": multi.get("M15", {}),
                                "H1": multi.get("H1", {})
                            }
                except Exception as e:
                    logger.warning(f"Failed to fetch Advanced features for refresh (ticket {ticket}): {e}")
                    return None
            else:
                logger.debug(f"No advanced_provider available for refresh (ticket {ticket})")
                return None
        
        # Recalculate triggers using current rule values as base
        try:
            advanced_result = self._calculate_advanced_triggers(
                advanced_features=advanced_features,
                base_breakeven_pct=rule.breakeven_profit_pct,  # Use current as base
                base_partial_pct=rule.partial_profit_pct,  # Use current as base
                symbol=rule.symbol  # Pass symbol for asset-specific thresholds
            )
        except Exception as e:
            logger.error(f"Error recalculating Advanced triggers for ticket {ticket}: {e}", exc_info=True)
            return None
        
        # Check if triggers actually changed
        breakeven_changed = abs(advanced_result["breakeven_pct"] - rule.breakeven_profit_pct) > 0.1
        partial_changed = abs(advanced_result["partial_pct"] - rule.partial_profit_pct) > 0.1
        
        if not breakeven_changed and not partial_changed:
            logger.debug(f"Advanced triggers unchanged for ticket {ticket} - no refresh needed")
            return advanced_result  # Return result even if unchanged
        
        # Update rule (thread-safe)
        with self.rules_lock:
            # Re-check rule still exists and breakeven not triggered
            rule = self.rules.get(ticket)
            if not rule:
                logger.debug(f"Rule removed during refresh for ticket {ticket}")
                return None
            
            if rule.breakeven_triggered:
                logger.debug(f"Breakeven triggered during refresh for ticket {ticket} - aborting update")
                return None
            
            # Update triggers
            old_breakeven = rule.breakeven_profit_pct
            old_partial = rule.partial_profit_pct
            
            rule.breakeven_profit_pct = advanced_result["breakeven_pct"]
            rule.partial_profit_pct = advanced_result["partial_pct"]
        
        # Save after releasing lock
        self._save_rules()
        
        logger.info(
            f"🔄 Refreshed Advanced triggers for {rule.symbol} ticket {ticket}: "
            f"BE {old_breakeven:.1f}% → {rule.breakeven_profit_pct:.1f}%, "
            f"Partial {old_partial:.1f}% → {rule.partial_profit_pct:.1f}%"
        )
        logger.debug(f"   Reasoning: {advanced_result.get('reasoning', 'N/A')}")
        
        return advanced_result
    
    def _log_position_closure(self, ticket: int, rule: ExitRule) -> Optional[Dict[str, Any]]:
        """
        Log detailed information about a closed position.
        Determines if closure was manual or automatic, and records final state.
        """
        try:
            # Get historical trade data from MT5 to determine actual exit reason
            import MetaTrader5 as mt5
            from datetime import datetime as dt, timedelta
            
            # Get deal history for this ticket (last 30 days)
            deals = mt5.history_deals_get(
                dt.now() - timedelta(days=30),
                dt.now(),
                position=ticket
            )
            
            closure_reason = "Unknown"
            final_pl = 0.0
            exit_price = 0.0
            
            if deals and len(deals) > 0:
                # Last deal for this position is the exit
                exit_deal = deals[-1]
                final_pl = exit_deal.profit
                exit_price = exit_deal.price
                
                # Determine closure reason from deal comment or type
                if exit_deal.comment:
                    comment_lower = exit_deal.comment.lower()
                    if "sl" in comment_lower or "stop loss" in comment_lower:
                        closure_reason = "Stop Loss Hit"
                    elif "tp" in comment_lower or "take profit" in comment_lower:
                        closure_reason = "Take Profit Hit"
                    elif "close" in comment_lower or "manual" in comment_lower:
                        closure_reason = "Manual Closure"
                    elif "breakeven" in comment_lower:
                        closure_reason = "Intelligent Exit - Breakeven"
                    elif "partial" in comment_lower:
                        closure_reason = "Intelligent Exit - Partial Profit"
                    else:
                        closure_reason = "Manual Closure"  # Default if no specific marker
                else:
                    closure_reason = "Manual Closure"  # No comment usually means manual
            
            # Calculate if any intelligent exit actions were taken
            actions_summary = []
            if rule.breakeven_triggered:
                actions_summary.append("Breakeven SL moved")
            if rule.partial_triggered:
                actions_summary.append("Partial profit taken")
            if rule.hybrid_adjustment_active:
                actions_summary.append("Hybrid ATR+VIX adjustment applied")
            if rule.trailing_active:
                actions_summary.append("ATR trailing active")
            
            actions_executed = ", ".join(actions_summary) if actions_summary else "None"
            
            # Determine if this was a manual closure without intelligent exits
            is_manual_without_protection = (
                closure_reason == "Manual Closure" and 
                rule.last_check is not None and  # Was monitored
                not any([rule.breakeven_triggered, rule.partial_triggered, rule.hybrid_adjustment_active])
            )
            
            # Determine if position closed before monitoring could start
            closed_unmonitored = rule.last_check is None
            
            # Log to database
            if self.db_logger:
                self.db_logger.log_action(
                    ticket=ticket,
                    symbol=rule.symbol,
                    action_type="position_closed",
                    old_sl=rule.initial_sl,
                    new_sl=exit_price,
                    volume=0.0,  # Not applicable for closure
                    profit=final_pl,
                    atr=None,
                    vix=None,
                    success=True,
                    details={
                        "closure_reason": closure_reason,
                        "entry_price": rule.entry_price,
                        "exit_price": exit_price,
                        "direction": rule.direction,
                        "final_pl": final_pl,
                        "intelligent_actions_taken": actions_executed,
                        "breakeven_triggered": rule.breakeven_triggered,
                        "partial_triggered": rule.partial_triggered,
                        "trailing_active": rule.trailing_active,
                        "was_monitored": rule.last_check is not None,
                        "manual_closure": closure_reason == "Manual Closure",
                        "closed_unmonitored": closed_unmonitored
                    }
                )
            
            # Enhanced logging based on closure type
            if closed_unmonitored:
                logger.error(
                    f"⚠️ CRITICAL: Position {ticket} ({rule.symbol}) closed BEFORE intelligent exits could monitor it! "
                    f"Reason: {closure_reason} | Entry: {rule.entry_price} | Exit: {exit_price} | P/L: ${final_pl:.2f} | "
                    f"Possible cause: Bot was offline/restarting when position closed or never checked after creation."
                )
            elif is_manual_without_protection:
                logger.warning(
                    f"🟡 MANUAL CLOSURE: Position {ticket} ({rule.symbol}) closed manually before intelligent exits could execute. "
                    f"Entry: {rule.entry_price} | Exit: {exit_price} | P/L: ${final_pl:.2f} | "
                    f"Actions taken: {actions_executed} | "
                    f"The position was being monitored but no protection actions had triggered yet."
                )
            elif closure_reason in ["Stop Loss Hit", "Take Profit Hit"]:
                logger.info(
                    f"✅ Position {ticket} ({rule.symbol}) closed via {closure_reason}. "
                    f"Entry: {rule.entry_price} | Exit: {exit_price} | P/L: ${final_pl:.2f} | "
                    f"Intelligent actions executed: {actions_executed}"
                )
            else:
                logger.info(
                    f"📊 Position {ticket} ({rule.symbol}) closed. Reason: {closure_reason} | "
                    f"Entry: {rule.entry_price} | Exit: {exit_price} | P/L: ${final_pl:.2f} | "
                    f"Actions: {actions_executed}"
                )
            
            # Return closure info for Telegram notification (will be used by background task)
            return {
                "ticket": ticket,
                "symbol": rule.symbol,
                "closure_reason": closure_reason,
                "manual_closure": closure_reason == "Manual Closure",
                "closed_unmonitored": closed_unmonitored,
                "actions_executed": actions_executed,
                "final_pl": final_pl,
                "exit_price": exit_price,
                "entry_price": rule.entry_price,
                "direction": rule.direction
            }
            
        except Exception as e:
            logger.error(f"Error logging closure for ticket {ticket}: {e}", exc_info=True)
            return None
    
    def _check_position_exits(
        self,
        rule: ExitRule,
        position,
        vix_price: Optional[float]
    ) -> List[Dict[str, Any]]:
        """Check a single position for exit actions"""
        actions = []
        
        current_price = position.price_current
        current_sl = position.sl if position.sl else rule.initial_sl
        current_volume = position.volume
        entry_price = rule.entry_price  # FIX: Store entry price for breakeven detection
        
        # Calculate current profit as % of potential profit (R)
        # This works for any trade size!
        if rule.direction == "buy":
            price_movement = current_price - rule.entry_price
        else:
            price_movement = rule.entry_price - current_price
        
        # Calculate what % of potential profit we've achieved
        # Handle edge case where potential_profit is 0 (invalid TP or SL)
        if rule.potential_profit <= 0:
            logger.warning(f"Invalid potential_profit ({rule.potential_profit}) for ticket {rule.ticket} - skipping profit-based triggers")
            profit_pct = 0
        else:
            profit_pct = (price_movement / rule.potential_profit * 100)
        
        # Also calculate R (risk units) for logging
        # R = profit / risk (e.g., 0.3R = 30% of potential profit for 1:1 R:R trade)
        r_achieved = (price_movement / rule.risk) if rule.risk > 0 else 0
        
        # 0.5. Optional: Use M1 latest candle for early detection (enhanced precision)
        # This provides faster detection than position.price_current alone
        try:
            from infra.streamer_data_access import get_latest_candle
            m1_candle = get_latest_candle(rule.symbol, "M1", max_age_seconds=120)  # Max 2 min old
            
            if m1_candle:
                # Use M1 close price for more precise detection (faster than position price updates)
                m1_price = m1_candle['close']
                if rule.direction == "buy":
                    m1_price_movement = m1_price - rule.entry_price
                else:
                    m1_price_movement = rule.entry_price - m1_price
                
                # Calculate profit % using M1 price (more recent)
                if rule.potential_profit > 0:
                    m1_profit_pct = (m1_price_movement / rule.potential_profit * 100)
                    # Use the higher of the two (M1 or position price) for trigger detection
                    if m1_profit_pct > profit_pct:
                        profit_pct = m1_profit_pct
                        current_price = m1_price  # Update current_price for action execution
                        logger.debug(f"Using M1 price {m1_price} for {rule.symbol} (more recent than position price)")
        except Exception as e:
            # Fallback: continue with position price if M1 unavailable
            logger.debug(f"M1 price check failed for {rule.symbol}: {e}, using position price")
        
        # FIX: Check if SL is already at breakeven (Universal Manager or manually moved)
        # This must be checked BEFORE the profit-based trigger
        # CRITICAL: Must validate that SL is actually at or better than entry (not worse)
        if not rule.breakeven_triggered:
            sl_at_breakeven = False
            if current_sl > 0:
                # CRITICAL FIX: Check if SL is close to entry AND actually at breakeven (not worse)
                # For BUY: SL at breakeven means SL >= entry_price (or very close, accounting for spread)
                # For SELL: SL at breakeven means SL <= entry_price (or very close, accounting for spread)
                tolerance = entry_price * 0.001  # 0.1% tolerance for spread/commission
                if rule.direction == "buy":
                    # For BUY: SL must be >= entry - tolerance (at or above entry)
                    sl_close_to_entry = abs(current_sl - entry_price) / entry_price < 0.001
                    sl_at_or_above_entry = current_sl >= (entry_price - tolerance)
                    sl_at_breakeven = sl_close_to_entry and sl_at_or_above_entry
                else:  # sell
                    # For SELL: SL must be <= entry + tolerance (at or below entry)
                    sl_close_to_entry = abs(current_sl - entry_price) / entry_price < 0.001
                    sl_at_or_below_entry = current_sl <= (entry_price + tolerance)
                    sl_at_breakeven = sl_close_to_entry and sl_at_or_below_entry
            
            if sl_at_breakeven:
                # SL already at breakeven (moved by Universal Manager or manually)
                logger.info(
                    f"Breakeven detected for {rule.ticket} (SL at {current_sl:.5f} at/above entry {entry_price:.5f}) - "
                    f"activating trailing if enabled"
                )
                rule.breakeven_triggered = True
                if rule.trailing_enabled:
                    # CRITICAL FIX: Always activate trailing after breakeven, regardless of gates
                    # Gates only affect the multiplier, not whether trailing is active
                    rule.trailing_active = True
                    logger.info(f"✅ Trailing stops ACTIVATED for ticket {rule.ticket} (breakeven detected)")
                    # Set default multiplier (gates will adjust it if needed)
                    rule.trailing_multiplier = getattr(rule, 'trailing_multiplier', 1.5)
            elif current_sl > 0:
                # SL is close to entry but NOT at breakeven (worse than entry) - log warning
                if rule.direction == "buy" and current_sl < entry_price:
                    logger.warning(
                        f"⚠️ SL {current_sl:.5f} is close to entry {entry_price:.5f} but BELOW entry "
                        f"(diff={entry_price - current_sl:.5f}) - NOT at breakeven! Will trigger modification."
                    )
                elif rule.direction == "sell" and current_sl > entry_price:
                    logger.warning(
                        f"⚠️ SL {current_sl:.5f} is close to entry {entry_price:.5f} but ABOVE entry "
                        f"(diff={current_sl - entry_price:.5f}) - NOT at breakeven! Will trigger modification."
                    )
        
        # 1. Check breakeven trigger (% of potential profit)
        # FIX: Use R achieved for more accurate calculation
        breakeven_r = rule.breakeven_profit_pct / 100.0  # Convert % to decimal (20% = 0.2R)
        if not rule.breakeven_triggered and r_achieved >= breakeven_r:
            action = self._move_to_breakeven(rule, position, current_price)
            if action:
                actions.append(action)
                rule.breakeven_triggered = True
                # Enable trailing after breakeven if enabled
                if rule.trailing_enabled:
                    rule.trailing_active = True
                    rule.last_trailing_sl = action.get("new_sl")
                    logger.info(f"✅ Trailing stops ACTIVATED for ticket {rule.ticket}")
                    # #region agent log
                    import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_be", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:1473", "message": "Breakeven triggered - trailing activated", "data": {"ticket": rule.ticket, "symbol": rule.symbol, "profit_pct": profit_pct, "r_achieved": r_achieved, "trailing_enabled": rule.trailing_enabled, "trailing_active": rule.trailing_active, "partial_triggered": rule.partial_triggered}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
                    # #endregion
                rule.actions_taken.append({
                    "action": "breakeven",
                    "timestamp": datetime.now().isoformat(),
                    "profit_pct": profit_pct,
                    "r_achieved": r_achieved
                })
        
        # 2. Check partial profit trigger (SKIP if volume <= 0.01 - prevent premature closure of small positions!)
        if not rule.partial_triggered and profit_pct >= rule.partial_profit_pct:
            if current_volume > 0.01:  # Only take partial profits on trades > 0.01 lots (prevent premature closure)
                action = self._take_partial_profit(rule, position, current_price, profit_pct, r_achieved)
                if action:
                    actions.append(action)
                    rule.partial_triggered = True
                    rule.actions_taken.append({
                        "action": "partial_profit",
                        "timestamp": datetime.now().isoformat(),
                        "profit_pct": profit_pct,
                        "r_achieved": r_achieved,
                        "closed_pct": rule.partial_close_pct
                    })
            else:
                logger.info(f"Skipping partial profit for ticket {rule.ticket}: volume {current_volume} too small (<= 0.01 lots) - preventing premature closure | At {profit_pct:.1f}% of TP ({r_achieved:.2f}R)")
                rule.partial_triggered = True  # Mark as triggered so we don't keep checking

        # CRITICAL FIX: After breakeven, always activate trailing (gates only affect multiplier)
        # This ensures trailing starts immediately after breakeven, regardless of gate status
        if rule.breakeven_triggered and (not rule.trailing_active) and rule.trailing_enabled:
            # Always activate trailing after breakeven - gates only affect multiplier
            rule.trailing_active = True
            logger.info(f"✅ Trailing stops ACTIVATED (post-breakeven) for ticket {rule.ticket}")
            # Check gates to determine multiplier (but don't block activation)
            try:
                gate_result = self._trailing_gates_pass(rule, profit_pct, r_achieved, return_details=True)
                if isinstance(gate_result, tuple):
                    should_trail, gate_info = gate_result
                    rule.trailing_multiplier = gate_info.get("trailing_multiplier", 1.5)
                    logger.debug(f"Trailing multiplier set to {rule.trailing_multiplier}x for ticket {rule.ticket} based on gates")
            except Exception as e:
                logger.debug(f"Error checking gates for trailing multiplier (non-fatal): {e}")
                rule.trailing_multiplier = 1.5

        # 3. ONE-TIME Hybrid ATR + VIX initial adjustment (for pre-breakeven widening)
        if rule.use_hybrid_stops and not rule.breakeven_triggered:
            # Only apply initial hybrid adjustment BEFORE breakeven
            if not rule.hybrid_adjustment_active:
                action = self._adjust_hybrid_atr_vix(rule, position, current_price, vix_price)
                if action:
                    actions.append(action)
                    rule.hybrid_adjustment_active = True
                    rule.actions_taken.append({
                        "action": "hybrid_adjustment",
                        "timestamp": datetime.now().isoformat(),
                        "vix_price": vix_price,
                        "details": action.get("details", {})
                    })
        
        # 4. CONTINUOUS ATR-based trailing (after breakeven)
        # FIX: Add comprehensive logging for trailing status
        logger.debug(
            f"Trailing check for {rule.ticket}: "
            f"breakeven_triggered={rule.breakeven_triggered}, "
            f"trailing_enabled={rule.trailing_enabled}, "
            f"trailing_active={rule.trailing_active}, "
            f"profit_pct={profit_pct:.1f}%, R={r_achieved:.2f}"
        )
        
        # If gates don't pass yet, keep trailing disabled
        if rule.trailing_active and rule.breakeven_triggered:
            try:
                gate_result = self._trailing_gates_pass(rule, profit_pct, r_achieved, return_details=True)
                if isinstance(gate_result, tuple):
                    should_trail, gate_info = gate_result
                    # #region agent log
                    import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_gate", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:1527", "message": "Trailing gates check", "data": {"ticket": rule.ticket, "symbol": rule.symbol, "should_trail": should_trail, "profit_pct": profit_pct, "r_achieved": r_achieved, "partial_triggered": rule.partial_triggered, "trailing_active_before": rule.trailing_active, "gate_info": gate_info}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "B"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
                    # #endregion
                    if not should_trail:
                        # FIX: Log WHY trailing is disabled, but don't disable permanently
                        failed_gates = gate_info.get('failed_gates', [])
                        logger.info(
                            f"⏳ Trailing gated for ticket {rule.ticket}: "
                            f"gates={failed_gates}, profit_pct={profit_pct:.1f}%, R={r_achieved:.2f} - "
                            f"using wider multiplier (2.0x) as fallback"
                        )
                        # FIX: Don't disable trailing permanently - use wider multiplier instead
                        # rule.trailing_active = False  # REMOVED - don't disable permanently
                        # Use wider multiplier (2.0x) if gates fail
                        rule.trailing_multiplier = 2.0
                        # #region agent log
                        import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_gate_fail", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:1532", "message": "Trailing gates failed - using wider multiplier", "data": {"ticket": rule.ticket, "symbol": rule.symbol, "r_achieved": r_achieved, "partial_triggered": rule.partial_triggered, "trailing_active": rule.trailing_active, "multiplier": 2.0, "failed_gates": failed_gates}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "B"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
                        # #endregion
                    else:
                        # Update multiplier if changed
                        rule.trailing_multiplier = gate_info.get("trailing_multiplier", 1.5)
            except Exception as e:
                # #region agent log
                import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_gate_err", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:1536", "message": "Gate check exception", "data": {"ticket": rule.ticket, "symbol": rule.symbol, "error": str(e)}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "B"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
                # #endregion
                pass
        if rule.trailing_active and rule.breakeven_triggered:
            # #region agent log
            import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_trail_start", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:1538", "message": "About to call _trail_stop_atr", "data": {"ticket": rule.ticket, "symbol": rule.symbol, "current_price": current_price, "current_sl": position.sl, "trailing_active": rule.trailing_active, "breakeven_triggered": rule.breakeven_triggered}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
            # #endregion
            multiplier = getattr(rule, "trailing_multiplier", 1.5)
            action = self._trail_stop_atr(rule, position, current_price, trailing_multiplier=multiplier)
            # #region agent log
            import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_trail_result", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:1540", "message": "_trail_stop_atr result", "data": {"ticket": rule.ticket, "symbol": rule.symbol, "action_returned": action is not None, "action_data": action if action else None}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
            # #endregion
            if action:
                actions.append(action)
                rule.last_trailing_sl = action.get("new_sl")
                rule.actions_taken.append({
                    "action": "trailing_stop",
                    "timestamp": datetime.now().isoformat(),
                    "new_sl": action.get("new_sl"),
                    "atr": action.get("details", {}).get("atr")
                })
        
        # 5. NEW: Binance momentum reversal check
        if self.binance_service and self.binance_service.running:
            binance_actions = self._check_binance_momentum(rule, position, current_price)
            actions.extend(binance_actions)
        
        # 6. NEW: Whale order protection
        if self.order_flow_service and self.order_flow_service.running:
            whale_actions = self._check_whale_orders(rule, position)
            actions.extend(whale_actions)
        
        # 7. NEW: Liquidity void warnings
        if self.order_flow_service and self.order_flow_service.running:
            void_actions = self._check_liquidity_voids(rule, position, current_price)
            actions.extend(void_actions)
        
        return actions

    def _trailing_gates_pass(
        self, 
        rule: ExitRule, 
        profit_pct: float, 
        r_achieved: float,
        return_details: bool = False  # NEW: Optional detailed return
    ):
        """Return True if trailing should be enabled based on Advanced/structure guards.
        
        RELAXED LOGIC (2025-12-17):
        - Trailing starts after breakeven (R >= 0.2 or breakeven triggered)
        - Advisory gates are more lenient (better defaults, relaxed thresholds)
        - Trailing always works, just adjusts multiplier based on conditions
        
        Returns bool (backward compat) or (bool, dict) if return_details=True
        
        Gates (any missing data falls back to safe defaults):
        - CRITICAL: Breakeven triggered OR partial taken OR r_achieved >= 0.2 (relaxed from 0.6)
        - ADVISORY: vol_state not a squeeze (relaxed - defaults to pass)
        - ADVISORY: mtf_total >= 1 (relaxed from 2 - only need 1 timeframe)
        - ADVISORY: abs(ema200_atr) <= asset-specific threshold * 1.5 (relaxed - 50% more room)
        - ADVISORY: vwap_zone != 'outer' (relaxed - advisory only, doesn't count as failure)
        - ADVISORY: hvn_dist_atr >= 0.2 (relaxed from 0.3 - closer to HVN allowed)
        """
        
        g = getattr(rule, "advanced_gate", {}) or {}
        
        # Get asset-specific RMAG threshold and relax it (50% more room)
        rmag_threshold = self._get_rmag_threshold(rule.symbol) * 1.5  # RELAXED: 50% more room
        
        # CRITICAL gates (must pass) - RELAXED: Allow trailing after breakeven
        # Breakeven triggered OR partial taken OR R >= 0.2 (was 0.6)
        breakeven_or_partial_or_r = bool(rule.breakeven_triggered) or bool(rule.partial_triggered) or (r_achieved >= 0.2)
        # #region agent log
        import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_gate_check", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:1663", "message": "Gate check values (relaxed)", "data": {"ticket": rule.ticket, "symbol": rule.symbol, "breakeven_triggered": rule.breakeven_triggered, "partial_triggered": rule.partial_triggered, "r_achieved": r_achieved, "breakeven_or_partial_or_r": breakeven_or_partial_or_r, "r_threshold": 0.2}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
        # #endregion
        
        # ADVISORY gates (warn but allow trailing with wider distance) - RELAXED
        # RELAXED: Better defaults and more lenient thresholds
        vol_ok = str(g.get("vol_state", "")).find("squeeze") == -1  # Default: True (assume not in squeeze)
        mtf_ok = int(g.get("mtf_total", 1)) >= 1  # RELAXED: Only need 1 timeframe (was 2), default to 1
        rmag_ok = abs(float(g.get("ema200_atr", 0))) <= rmag_threshold  # RELAXED: Threshold already increased by 1.5x
        vwap_ok = True  # RELAXED: VWAP zone is advisory only, doesn't block trailing
        hvn_ok = float(g.get("hvn_dist_atr", 999)) >= 0.2  # RELAXED: 0.2 instead of 0.3, default to 999 (pass)
        
        # Count advisory gate failures (vwap_ok always True now, so only count others)
        advisory_failures = sum([not vol_ok, not mtf_ok, not rmag_ok, not hvn_ok])
        
        # Gate status for logging
        gate_status = {
            "breakeven_or_partial_or_r": breakeven_or_partial_or_r,
            "breakeven_triggered": rule.breakeven_triggered,
            "partial_triggered": rule.partial_triggered,
            "r_achieved": r_achieved,
            "vol_ok": vol_ok,
            "mtf_ok": mtf_ok,
            "mtf_total": g.get("mtf_total", 1),  # Default to 1 (relaxed)
            "rmag_ok": rmag_ok,
            "rmag_value": g.get("ema200_atr", 0),
            "rmag_threshold": rmag_threshold,
            "vwap_ok": vwap_ok,
            "vwap_zone": g.get("vwap_zone", "inside"),
            "hvn_ok": hvn_ok,
            "hvn_dist": g.get("hvn_dist_atr", 999),
            "advisory_failures": advisory_failures
        }
        
        # RELAXED: Allow trailing if breakeven triggered OR partial taken OR R >= 0.2
        # This ensures trailing starts after breakeven
        if breakeven_or_partial_or_r:
            # RELAXED: More lenient multiplier selection
            if advisory_failures == 0:  # All gates pass
                multiplier = 1.5
                gate_status_str = "normal"
            elif advisory_failures <= 2:  # 1-2 failures - still use normal
                multiplier = 1.5
                gate_status_str = "normal"
            else:  # 3+ failures - use wider trailing
                multiplier = 2.0
                gate_status_str = "wide"
            
            # Log gate status
            logger.info(
                f"Trailing gates for {rule.symbol} ticket {rule.ticket}: "
                f"breakeven={rule.breakeven_triggered} partial={rule.partial_triggered} R={r_achieved:.2f} "
                f"vol={vol_ok} mtf={mtf_ok}({gate_status['mtf_total']}) "
                f"rmag={rmag_ok}({gate_status['rmag_value']:.2f}σ, threshold={rmag_threshold:.2f}σ) "
                f"hvn={hvn_ok}({gate_status['hvn_dist']:.2f}) "
                f"failures={advisory_failures} → ALLOW trailing (multiplier={multiplier}x, status={gate_status_str})"
            )
            
            if return_details:
                failed_gates = []
                if not vol_ok: failed_gates.append("vol_squeeze")
                if not mtf_ok: failed_gates.append("mtf_alignment")
                if not rmag_ok: failed_gates.append("rmag_stretch")
                if not hvn_ok: failed_gates.append("hvn_proximity")
                return (True, {
                    "trailing_multiplier": multiplier, 
                    "gate_status": gate_status, 
                    "status": gate_status_str,
                    "failed_gates": failed_gates
                })
            else:
                return True
        else:
            logger.info(
                f"Trailing gates for {rule.symbol} ticket {rule.ticket}: "
                f"breakeven={rule.breakeven_triggered} partial={rule.partial_triggered} R={r_achieved:.2f} "
                f"→ BLOCK trailing (need breakeven OR partial OR R>=0.2)"
            )
            if return_details:
                failed_gates = ["critical_gate"]  # Critical gate failed
                if not vol_ok: failed_gates.append("vol_squeeze")
                if not mtf_ok: failed_gates.append("mtf_alignment")
                if not rmag_ok: failed_gates.append("rmag_stretch")
                if not hvn_ok: failed_gates.append("hvn_proximity")
                return (False, {
                    "reason": "critical_gate_failed", 
                    "gate_status": gate_status,
                    "failed_gates": failed_gates
                })
            else:
                return False
    
    def _calculate_atr(self, symbol: str, timeframe: str = "M15", period: int = 14) -> Optional[float]:
        """
        Calculate ATR using existing streamer utility (preferred) with MT5 fallback.
        Phase 12: Includes circuit breaker for repeated failures.
        """
        import time
        
        # Phase 12: Check circuit breaker
        if symbol in self._atr_circuit_breaker_timestamps:
            time_since_open = time.time() - self._atr_circuit_breaker_timestamps[symbol]
            if time_since_open < self._atr_circuit_breaker_timeout:
                # Circuit open - use fallback
                fallback = self._atr_fallback_values.get(symbol)
                if fallback:
                    logger.debug(f"ATR circuit breaker open for {symbol}, using fallback: {fallback:.5f}")
                    return fallback
                return None
            else:
                # Circuit timeout expired - reset
                logger.info(f"ATR circuit breaker reset for {symbol}, retrying")
                self._atr_circuit_breaker_timestamps.pop(symbol, None)
                self._atr_failure_count.pop(symbol, None)
        
        try:
            # Try streamer ATR first (fast, uses cached data)
            from infra.streamer_data_access import calculate_atr as streamer_atr
            atr = streamer_atr(symbol, timeframe, period=period)
            if atr and atr > 0:
                # Success - reset failure count and update fallback
                self._atr_failure_count.pop(symbol, None)
                self._atr_fallback_values[symbol] = atr
                return atr
        except Exception as e:
            logger.debug(f"Streamer ATR failed for {symbol} {timeframe}, using MT5 fallback: {e}")
        
        # Fallback to direct MT5 (same pattern as existing code)
        try:
            if not mt5.initialize():
                # Failure - increment count
                self._atr_failure_count[symbol] = self._atr_failure_count.get(symbol, 0) + 1
                if self._atr_failure_count[symbol] >= self._atr_circuit_breaker_threshold:
                    logger.warning(f"ATR circuit breaker opened for {symbol} after {self._atr_failure_count[symbol]} failures")
                    self._atr_circuit_breaker_timestamps[symbol] = time.time()
                return self._atr_fallback_values.get(symbol)
            
            # Map timeframe string to MT5 enum
            tf_map = {
                "M1": mt5.TIMEFRAME_M1,
                "M5": mt5.TIMEFRAME_M5,
                "M15": mt5.TIMEFRAME_M15,
                "M30": mt5.TIMEFRAME_M30,
                "H1": mt5.TIMEFRAME_H1,
                "H4": mt5.TIMEFRAME_H4
            }
            tf_enum = tf_map.get(timeframe, mt5.TIMEFRAME_M15)
            
            bars = mt5.copy_rates_from_pos(symbol, tf_enum, 0, 50)
            if bars is None or len(bars) < period + 1:
                # Failure - increment count
                self._atr_failure_count[symbol] = self._atr_failure_count.get(symbol, 0) + 1
                if self._atr_failure_count[symbol] >= self._atr_circuit_breaker_threshold:
                    logger.warning(f"ATR circuit breaker opened for {symbol} after {self._atr_failure_count[symbol]} failures")
                    self._atr_circuit_breaker_timestamps[symbol] = time.time()
                return self._atr_fallback_values.get(symbol)
            
            import numpy as np
            high_low = bars['high'][1:] - bars['low'][1:]
            high_close = np.abs(bars['high'][1:] - bars['close'][:-1])
            low_close = np.abs(bars['low'][1:] - bars['close'][:-1])
            tr = np.maximum(high_low, np.maximum(high_close, low_close))
            atr = np.mean(tr[-period:]) if len(tr) >= period else 0
            
            return atr if atr > 0 else None
        except Exception as e:
            logger.debug(f"MT5 ATR calculation failed for {symbol}: {e}")
            return None
    
    def _get_min_stop_distance(self, symbol: str) -> float:
        """
        Get broker's minimum stop distance for a symbol.
        Used to check if SL change is significant enough before modifying.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Minimum stop distance in price units, or fallback default
        """
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info:
                stops_level = getattr(symbol_info, 'trade_stops_level', None) or getattr(symbol_info, 'stops_level', None) or 0
                point = getattr(symbol_info, 'point', 0.0) or 0.0
                
                if stops_level and point:
                    min_distance = float(stops_level) * float(point)
                    if min_distance > 0:
                        return min_distance
        except Exception as e:
            logger.debug(f"Error getting min stop distance for {symbol}: {e}")
        
        # Fallback defaults (in price units)
        defaults = {
            "BTCUSDc": 5.0,   # 5 points
            "XAUUSDc": 0.5,   # 0.5 pips
            "EURUSDc": 2.0,   # 2 pips
            "US30c": 3.0,     # 3 points
        }
        
        # Try to get a reasonable default based on symbol
        for key, value in defaults.items():
            if key in symbol.upper():
                return value
        
        # Generic fallback: 0.1% of typical price (very conservative)
        # This ensures we don't skip modifications unless change is truly insignificant
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info:
                bid = getattr(symbol_info, 'bid', 0.0) or 0.0
                if bid > 0:
                    return bid * 0.001  # 0.1% of current price
        except Exception:
            pass
        
        # Last resort: very small default (1 point for most symbols)
        return 0.00001
    
    def _move_to_breakeven(self, rule: ExitRule, position, current_price: float) -> Optional[Dict[str, Any]]:
        """Move stop loss to breakeven (entry price) with ATR buffer"""
        try:
            # Calculate breakeven SL (entry + small buffer for spread)
            symbol_info = mt5.symbol_info(rule.symbol)
            if not symbol_info:
                logger.error(f"Could not get symbol info for {rule.symbol}")
                return None
            
            spread = symbol_info.spread * symbol_info.point
            
            # Phase 11: Get symbol-specific buffer multiplier
            try:
                from infra.session_helpers import SessionHelpers
                current_session = SessionHelpers.get_current_session()
            except Exception:
                current_session = None
            
            symbol_params = self._get_symbol_exit_params(rule.symbol, current_session)
            buffer_mult = symbol_params.get("breakeven_buffer_atr_mult", 0.3)  # Default 0.3
            atr_timeframe = symbol_params.get("atr_timeframe", "M15")
            
            # Calculate ATR buffer (symbol-specific multiplier × ATR)
            # USE EXISTING UTILITY - streamer_data_access.calculate_atr()
            atr = self._calculate_atr(rule.symbol, atr_timeframe, 14)  # Use symbol-specific timeframe
            if atr and atr > 0:
                atr_buffer = atr * buffer_mult
            else:
                # Fallback: use 0.1% of entry price as buffer if ATR unavailable
                atr_buffer = rule.entry_price * 0.001
                logger.debug(f"ATR unavailable for {rule.symbol}, using 0.1% price buffer")
            
            # Calculate breakeven with buffer
            # BREAKEVEN means "no loss" - SL should be at entry price (or very close for spread)
            # CRITICAL FIX: For BUY trades, SL must be AT or ABOVE entry to prevent loss
            # For BUY: You enter at ASK, exit at BID when SL hit. If SL < entry, you lose money.
            # For SELL: You enter at BID, exit at ASK when SL hit. If SL > entry, you lose money.
            # NOTE: ATR buffer is too large for breakeven - use spread only
            
            if rule.direction == "buy":
                # For BUY: Breakeven SL = entry_price (or slightly above to ensure no loss)
                # When SL is hit, you sell at BID. If SL is below entry, you lose money.
                # Solution: Set SL at entry_price (or entry_price + small_buffer to ensure no loss)
                # Use half the spread as buffer (since you pay full spread on entry, but only need to cover half on exit)
                spread_buffer = spread / 2.0  # Half spread to account for exit spread
                tiny_buffer = rule.entry_price * 0.0001  # 0.01% of entry price (very small safety buffer)
                new_sl = rule.entry_price + spread_buffer + tiny_buffer
                # Ensure SL is at least at entry (never below entry for BUY)
                min_sl = rule.entry_price  # Never below entry for BUY
                new_sl = max(new_sl, min_sl)
            else:
                # For SELL: Breakeven SL = entry_price (or slightly below to ensure no loss)
                # When SL is hit, you buy at ASK. If SL is above entry, you lose money.
                # Solution: Set SL at entry_price (or entry_price - small_buffer to ensure no loss)
                # Use half the spread as buffer (since you pay full spread on entry, but only need to cover half on exit)
                spread_buffer = spread / 2.0  # Half spread to account for exit spread
                tiny_buffer = rule.entry_price * 0.0001  # 0.01% of entry price (very small safety buffer)
                new_sl = rule.entry_price - spread_buffer - tiny_buffer
                # Ensure SL is at most at entry (never above entry for SELL)
                max_sl = rule.entry_price  # Never above entry for SELL
                new_sl = min(new_sl, max_sl)
            
            # CRITICAL: Final safety check FIRST - Ensure breakeven SL is actually at breakeven (not worse)
            # For BUY: SL should be >= entry (at or above entry to prevent loss)
            # For SELL: SL should be <= entry (at or below entry to prevent loss)
            if rule.direction == "buy" and new_sl < rule.entry_price:
                # SL is below entry - this would cause loss when hit! Fix it.
                logger.warning(f"Breakeven SL {new_sl} is below entry {rule.entry_price} for BUY trade - correcting to entry + spread_buffer")
                spread_buffer = spread / 2.0 if spread > 0 else 0.0
                tiny_buffer = rule.entry_price * 0.0001  # 0.01% of entry price
                new_sl = rule.entry_price + spread_buffer + tiny_buffer
                # Ensure it's at least at entry (never below entry for BUY)
                min_sl = rule.entry_price
                new_sl = max(new_sl, min_sl)
            elif rule.direction == "sell" and new_sl > rule.entry_price:
                # SL is above entry - this would cause loss when hit! Fix it.
                logger.warning(f"Breakeven SL {new_sl} is above entry {rule.entry_price} for SELL trade - correcting to entry - spread_buffer")
                spread_buffer = spread / 2.0 if spread > 0 else 0.0
                tiny_buffer = rule.entry_price * 0.0001  # 0.01% of entry price
                new_sl = rule.entry_price - spread_buffer - tiny_buffer
                # Ensure it's at most at entry (never above entry for SELL)
                max_sl = rule.entry_price
                new_sl = min(new_sl, max_sl)
            
            # Get current SL for comparison
            current_sl = position.sl if position.sl else rule.initial_sl
            
            # CRITICAL: Final validation - breakeven SL must NEVER cause a loss
            # For BUY: SL must be >= entry (at or above entry to prevent loss)
            # For SELL: SL must be <= entry (at or below entry to prevent loss)
            if rule.direction == "buy":
                if new_sl < rule.entry_price:
                    # This would cause loss when hit! Force correction
                    logger.error(f"CRITICAL: Breakeven SL {new_sl} is BELOW entry {rule.entry_price} for BUY trade - FORCING correction to entry + spread_buffer")
                    spread_buffer = spread / 2.0
                    tiny_buffer = rule.entry_price * 0.0001  # 0.01% of entry price
                    new_sl = rule.entry_price + spread_buffer + tiny_buffer
                    # Ensure it's at least at entry (never below entry for BUY)
                    min_sl = rule.entry_price
                    new_sl = max(new_sl, min_sl)
            else:  # SELL
                if new_sl > rule.entry_price:
                    # This would cause loss when hit! Force correction
                    logger.error(f"CRITICAL: Breakeven SL {new_sl} is ABOVE entry {rule.entry_price} for SELL trade - FORCING correction to entry - spread_buffer")
                    spread_buffer = spread / 2.0
                    tiny_buffer = rule.entry_price * 0.0001  # 0.01% of entry price
                    new_sl = rule.entry_price - spread_buffer - tiny_buffer
                    # Ensure it's at most at entry (never above entry for SELL)
                    max_sl = rule.entry_price
                    new_sl = min(new_sl, max_sl)
            
            # For breakeven, we want to move SL to entry (or very close), even if it's "worse" than current SL
            # The goal is to eliminate risk, not to improve SL distance
            # Only skip if the new SL would actually increase risk (move SL in wrong direction)
            if rule.direction == "buy":
                # For BUY: New SL should be <= entry, and should not be worse than current SL
                # "Worse" means moving SL up (closer to price) when it should go down
                # But for breakeven, we allow moving to entry even if current SL is already at entry
                if new_sl > current_sl and new_sl > rule.entry_price:
                    logger.warning(f"Breakeven SL {new_sl} would increase risk (above entry {rule.entry_price} and above current {current_sl}) - skipping")
                    return None
                # Allow moving SL to entry even if slightly "worse" than current (for breakeven protection)
            else:  # SELL
                # For SELL: New SL should be >= entry, and should not be worse than current SL
                # "Worse" means moving SL down (closer to price) when it should go up
                # But for breakeven, we allow moving to entry even if current SL is already at entry
                if new_sl < current_sl and new_sl < rule.entry_price:
                    logger.warning(f"Breakeven SL {new_sl} would increase risk (below entry {rule.entry_price} and below current {current_sl}) - skipping")
                    return None
                # Allow moving SL to entry even if slightly "worse" than current (for breakeven protection)
            
            # CRITICAL FIX: Validate that current SL is actually at breakeven before skipping modification
            # For BUY: current_sl must be >= entry_price (at or above entry)
            # For SELL: current_sl must be <= entry_price (at or below entry)
            # If current_sl is worse than entry, we MUST modify it even if the change is small
            current_sl_is_at_breakeven = False
            if rule.direction == "buy":
                # For BUY: SL at breakeven means SL >= entry_price (or very close, accounting for spread)
                # Allow small tolerance (0.1% of entry) to account for spread/commission
                breakeven_tolerance = rule.entry_price * 0.001  # 0.1% tolerance
                current_sl_is_at_breakeven = current_sl >= (rule.entry_price - breakeven_tolerance)
            else:  # SELL
                # For SELL: SL at breakeven means SL <= entry_price (or very close, accounting for spread)
                breakeven_tolerance = rule.entry_price * 0.001  # 0.1% tolerance
                current_sl_is_at_breakeven = current_sl <= (rule.entry_price + breakeven_tolerance)
            
            # Check if change is significant before attempting MT5 modification
            # This prevents "10025 - No changes" error when SL is already at breakeven
            sl_change = abs(new_sl - current_sl)
            min_distance = self._get_min_stop_distance(rule.symbol)
            
            # CRITICAL: Only skip modification if:
            # 1. Change is small (already at breakeven), AND
            # 2. Current SL is actually at breakeven (not worse than entry)
            if sl_change < min_distance and current_sl_is_at_breakeven:
                # Change is too small AND current SL is actually at breakeven - skip modification
                logger.info(
                    f"Breakeven SL already achieved for {rule.symbol} (ticket {rule.ticket}): "
                    f"current_sl={current_sl:.5f}, calculated_breakeven={new_sl:.5f}, "
                    f"difference={sl_change:.5f} < min_distance={min_distance:.5f}, "
                    f"entry_price={rule.entry_price:.5f}, sl_at_breakeven={current_sl_is_at_breakeven}"
                )
                
                # Mark breakeven as triggered
                rule.breakeven_triggered = True
                
                # Enable trailing after breakeven if enabled
                if rule.trailing_enabled:
                    rule.trailing_active = True
                    rule.last_trailing_sl = current_sl
                    logger.info(f"✅ Trailing stops ACTIVATED for ticket {rule.ticket} (breakeven already at target)")
            elif sl_change < min_distance and not current_sl_is_at_breakeven:
                # CRITICAL BUG FIX: Change is small BUT current SL is NOT at breakeven (worse than entry)
                # This means the SL is below entry (for BUY) or above entry (for SELL) = LOSS
                # We MUST modify it even if the change is small, otherwise trade will close at loss
                logger.warning(
                    f"⚠️ CRITICAL: Current SL {current_sl:.5f} is NOT at breakeven (entry={rule.entry_price:.5f}) "
                    f"but calculated breakeven {new_sl:.5f} is close (diff={sl_change:.5f}). "
                    f"FORCING modification to prevent loss!"
                )
                # Continue with modification (don't return None)
                
                # Log to database as successful (breakeven already achieved)
                if self.db_logger:
                    try:
                        price_movement = abs(current_price - rule.entry_price)
                        potential_profit = abs(rule.initial_tp - rule.entry_price)
                        profit_pct = (price_movement / potential_profit * 100) if potential_profit > 0 else 0
                        
                        self.db_logger.log_action(
                            ticket=rule.ticket,
                            symbol=rule.symbol,
                            action_type="breakeven",
                            old_sl=current_sl,
                            new_sl=current_sl,  # No change needed
                            profit_pct=profit_pct,
                            r_achieved=profit_pct / 100.0,
                            details={
                                "entry_price": rule.entry_price,
                                "current_price": current_price,
                                "direction": rule.direction,
                                "already_at_breakeven": True,
                                "sl_change": sl_change,
                                "min_distance": min_distance
                            },
                            success=True
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log breakeven to database: {e}")
                
                # Return success action (breakeven already achieved)
                return {
                    "action": "breakeven",
                    "ticket": rule.ticket,
                    "symbol": rule.symbol,
                    "old_sl": current_sl,
                    "new_sl": current_sl,  # No change
                    "timestamp": datetime.now().isoformat(),
                    "already_at_breakeven": True
                }
            
            # Modify position (change is significant enough)
            success = self._modify_position_sl(rule.ticket, new_sl, position.tp)
            
            if success:
                buffer_info = f" (ATR buffer: {atr_buffer:.5f})" if atr and atr > 0 else " (price buffer: 0.1%)"
                logger.info(f"✅ Moved SL to breakeven for {rule.symbol} (ticket {rule.ticket}): {current_sl:.5f} → {new_sl:.5f}{buffer_info}")
                
                # Log to database
                if self.db_logger:
                    try:
                        # Calculate profit percentage achieved
                        price_movement = abs(current_price - rule.entry_price)
                        potential_profit = abs(rule.initial_tp - rule.entry_price)
                        profit_pct = (price_movement / potential_profit * 100) if potential_profit > 0 else 0
                        
                        self.db_logger.log_action(
                            ticket=rule.ticket,
                            symbol=rule.symbol,
                            action_type="breakeven",
                            old_sl=current_sl,
                            new_sl=new_sl,
                            profit_pct=profit_pct,
                            r_achieved=profit_pct / 100.0,  # R-multiple approximation
                            details={
                                "entry_price": rule.entry_price,
                                "current_price": current_price,
                                "direction": rule.direction
                            },
                            success=True
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log breakeven to database: {e}")
                
                return {
                    "action": "breakeven",
                    "ticket": rule.ticket,
                    "symbol": rule.symbol,
                    "old_sl": current_sl,
                    "new_sl": new_sl,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                logger.error(f"Failed to move SL to breakeven for ticket {rule.ticket}")
                
                # Log failure to database
                if self.db_logger:
                    try:
                        self.db_logger.log_action(
                            ticket=rule.ticket,
                            symbol=rule.symbol,
                            action_type="breakeven",
                            old_sl=current_sl,
                            new_sl=new_sl,
                            success=False,
                            error_message="Failed to modify position in MT5"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log breakeven failure to database: {e}")
                
                return None
                
        except Exception as e:
            logger.error(f"Error moving to breakeven for ticket {rule.ticket}: {e}", exc_info=True)
            return None
    
    def _take_partial_profit(
        self,
        rule: ExitRule,
        position,
        current_price: float,
        profit_pct: float,
        r_achieved: float
    ) -> Optional[Dict[str, Any]]:
        """Take partial profit by closing a percentage of the position"""
        try:
            current_volume = position.volume
            close_volume = current_volume * (rule.partial_close_pct / 100.0)
            
            # Round to broker's volume step (usually 0.01)
            close_volume = round(close_volume, 2)
            
            if close_volume <= 0:
                logger.warning(f"Partial close volume too small for ticket {rule.ticket}")
                return None
            
            # Ensure we don't close more than available
            if close_volume > current_volume:
                close_volume = current_volume
            
            # Prepare close request
            symbol = rule.symbol
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": close_volume,
                "type": mt5.ORDER_TYPE_SELL if rule.direction == "buy" else mt5.ORDER_TYPE_BUY,
                "position": rule.ticket,
                "price": current_price,
                "deviation": 20,
                "magic": 0,
                "comment": f"Partial profit ({rule.partial_close_pct}%)",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"✅ Partial profit taken for {symbol} (ticket {rule.ticket}): Closed {close_volume} lots at {profit_pct:.1f}% of TP ({r_achieved:.2f}R)")
                
                # Update rule's expected volume (position was partially closed)
                # Note: This will be updated on next check_exits() call from actual position volume
                # But we mark partial_triggered here to prevent duplicate actions
                
                # Calculate profit realized
                # Get symbol info for profit calculation
                symbol_info = mt5.symbol_info(symbol)
                contract_size = symbol_info.trade_contract_size if symbol_info else 100000
                
                # Correct profit calculation:
                # profit = price_movement × volume × contract_size
                # For BTCUSD: $840 move × 0.05 lots × 1 contract = $42.00
                # For Gold: $13 move × 0.05 lots × 100 oz = $65.00
                # For Forex: 0.01 move × 0.05 lots × 100,000 units = $50.00
                price_movement = abs(current_price - rule.entry_price)
                profit_realized = price_movement * close_volume * contract_size
                
                # Log to database
                if self.db_logger:
                    try:
                        self.db_logger.log_action(
                            ticket=rule.ticket,
                            symbol=symbol,
                            action_type="partial_profit",
                            volume_closed=close_volume,
                            volume_remaining=current_volume - close_volume,
                            profit_realized=profit_realized,
                            profit_pct=profit_pct,
                            r_achieved=r_achieved,
                            details={
                                "entry_price": rule.entry_price,
                                "exit_price": current_price,
                                "direction": rule.direction,
                                "close_percent": rule.partial_close_pct
                            },
                            success=True
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log partial profit to database: {e}")
                
                return {
                    "action": "partial_profit",
                    "ticket": rule.ticket,
                    "symbol": symbol,
                    "closed_volume": close_volume,
                    "remaining_volume": current_volume - close_volume,
                    "profit_pct": profit_pct,
                    "r_achieved": r_achieved,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                error_code = result.retcode if result else "unknown"
                logger.error(f"Failed to take partial profit for ticket {rule.ticket}: {error_code}")
                
                # Log failure to database
                if self.db_logger:
                    try:
                        self.db_logger.log_action(
                            ticket=rule.ticket,
                            symbol=symbol,
                            action_type="partial_profit",
                            volume_closed=close_volume,
                            success=False,
                            error_message=f"MT5 error: {error_code}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log partial profit failure to database: {e}")
                
                return None
                
        except Exception as e:
            logger.error(f"Error taking partial profit for ticket {rule.ticket}: {e}", exc_info=True)
            return None
    
    def _take_partial_profit_by_pct(
        self,
        rule: ExitRule,
        position,
        current_price: float,
        close_percent: float,
        reason: str = "Manual partial exit"
    ) -> Optional[Dict[str, Any]]:
        """
        Take partial profit by closing a specific percentage of position.
        
        Args:
            rule: ExitRule for this position
            position: MT5 position object
            current_price: Current market price
            close_percent: Percentage to close (e.g., 50.0 = close 50%)
            reason: Reason for partial exit (for logging)
        """
        try:
            current_volume = position.volume
            close_volume = current_volume * (close_percent / 100.0)
            
            # Round to broker's volume step (usually 0.01)
            close_volume = round(close_volume, 2)
            
            if close_volume <= 0:
                logger.warning(f"Partial close volume too small for ticket {rule.ticket}")
                return None
            
            # Ensure we don't close more than available
            if close_volume > current_volume:
                close_volume = current_volume
            
            # Prepare close request
            symbol = rule.symbol
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": close_volume,
                "type": mt5.ORDER_TYPE_SELL if rule.direction == "buy" else mt5.ORDER_TYPE_BUY,
                "position": rule.ticket,
                "price": current_price,
                "deviation": 20,
                "magic": 0,
                "comment": reason,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"✅ Partial exit taken for {symbol} (ticket {rule.ticket}): Closed {close_volume} lots ({close_percent}%) - {reason}")
                
                # Calculate profit realized
                symbol_info = mt5.symbol_info(symbol)
                contract_size = symbol_info.trade_contract_size if symbol_info else 100000
                price_movement = abs(current_price - rule.entry_price)
                profit_realized = price_movement * close_volume * contract_size
                
                # Log to database
                if self.db_logger:
                    try:
                        self.db_logger.log_action(
                            ticket=rule.ticket,
                            symbol=symbol,
                            action_type="partial_profit",
                            volume_closed=close_volume,
                            volume_remaining=current_volume - close_volume,
                            profit_realized=profit_realized,
                            details={"reason": reason, "close_percent": close_percent},
                            success=True
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log partial exit to database: {e}")
                
                return {
                    "action": "partial_profit",
                    "type": "void_partial_exit",
                    "ticket": rule.ticket,
                    "symbol": symbol,
                    "closed_volume": close_volume,
                    "remaining_volume": current_volume - close_volume,
                    "close_percent": close_percent,
                    "reason": reason,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                error_code = result.retcode if result else "unknown"
                logger.error(f"Failed to take partial exit for ticket {rule.ticket}: {error_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error taking partial exit for ticket {rule.ticket}: {e}", exc_info=True)
            return None
    
    def _close_position_fully(
        self,
        rule: ExitRule,
        position,
        current_price: float,
        reason: str = "Manual closure"
    ) -> Optional[Dict[str, Any]]:
        """
        Close entire position.
        
        Args:
            rule: ExitRule for this position
            position: MT5 position object
            current_price: Current market price
            reason: Reason for closure (for logging)
        """
        try:
            close_volume = position.volume
            
            if close_volume <= 0:
                return None
            
            # Prepare close request
            symbol = rule.symbol
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": close_volume,
                "type": mt5.ORDER_TYPE_SELL if rule.direction == "buy" else mt5.ORDER_TYPE_BUY,
                "position": rule.ticket,
                "price": current_price,
                "deviation": 20,
                "magic": 0,
                "comment": reason,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"✅ Position closed for {symbol} (ticket {rule.ticket}): {reason}")
                
                # Log to database
                if self.db_logger:
                    try:
                        self.db_logger.log_action(
                            ticket=rule.ticket,
                            symbol=symbol,
                            action_type="position_closed",
                            volume_closed=close_volume,
                            details={"reason": reason},
                            success=True
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log closure to database: {e}")
                
                return {
                    "action": "position_closed",
                    "type": "void_full_close",
                    "ticket": rule.ticket,
                    "symbol": symbol,
                    "reason": reason,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                error_code = result.retcode if result else "unknown"
                logger.error(f"Failed to close position {rule.ticket}: {error_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error closing position {rule.ticket}: {e}", exc_info=True)
            return None
    
    def _adjust_hybrid_atr_vix(
        self,
        rule: ExitRule,
        position,
        current_price: float,
        vix_price: Optional[float]
    ) -> Optional[Dict[str, Any]]:
        """
        Hybrid ATR + VIX stop adjustment with multi-timeframe analysis.
        
        FIXED LOGIC (2025-12-17):
        - Only widens stops when VIX exceeds threshold
        - Calculates from entry price (not current price) to widen stop
        - Never tightens stops (only widens or keeps same)
        - Skips entirely if VIX is below threshold (no adjustment needed)
        
        Logic:
        - M1 ATR: Micro-volatility (intraday spikes, fast adaptation)
        - M30 ATR: Trend volatility (smoother, less noise)
        - VIX: Market fear/volatility (macro context)
        - Combine all three for intelligent stop adjustment
        
        Formula:
        - Calculate M1 and M30 ATR for the symbol
        - Use weighted average: (M1 * 0.3) + (M30 * 0.7) for stability
        - If VIX > threshold: Use ATR * (1 + (VIX - threshold) / 10)
        - If VIX <= threshold: SKIP adjustment (no change needed)
        - New SL = Entry - (ATR_adjusted * multiplier) for BUY (widen DOWN)
        - New SL = Entry + (ATR_adjusted * multiplier) for SELL (widen UP)
        - Only apply if it widens the stop (never tighten)
        
        Example:
        - M1 ATR = 8.0, M30 ATR = 5.0, VIX = 20, threshold = 18
        - Combined ATR = (8.0 * 0.3) + (5.0 * 0.7) = 5.9
        - ATR_adjusted = 5.9 * (1 + (20 - 18) / 10) = 5.9 * 1.2 = 7.08
        - More volatile markets get wider stops automatically
        """
        try:
            current_sl = position.sl if position.sl else rule.initial_sl
            entry_price = rule.entry_price
            
            # FIX: Early exit if VIX is below threshold (no adjustment needed)
            if not vix_price or vix_price <= rule.vix_threshold:
                logger.debug(
                    f"Hybrid ATR+VIX adjustment skipped for {rule.symbol} (ticket {rule.ticket}): "
                    f"VIX {vix_price} below threshold {rule.vix_threshold} - no adjustment needed"
                )
                return None
            
            # Try to get ATR from streamer (M1 + M30), fallback to direct MT5
            try:
                from infra.streamer_data_access import calculate_atr
                
                # Get M1 ATR for micro-volatility
                m1_atr = calculate_atr(rule.symbol, "M1", period=14)
                
                # Get M30 ATR for trend volatility
                m30_atr = calculate_atr(rule.symbol, "M30", period=14)
                
                # Use weighted average: M1 (30%) + M30 (70%) for stability
                if m1_atr and m30_atr:
                    atr = (m1_atr * 0.3) + (m30_atr * 0.7)
                    logger.debug(f"Hybrid ATR for {rule.symbol}: M1={m1_atr:.2f}, M30={m30_atr:.2f}, Combined={atr:.2f}")
                elif m30_atr:
                    # Fallback: use only M30 if M1 not available
                    atr = m30_atr
                    logger.debug(f"Using M30 ATR only for {rule.symbol}: {atr:.2f}")
                elif m1_atr:
                    # Fallback: use only M1 if M30 not available
                    atr = m1_atr
                    logger.debug(f"Using M1 ATR only for {rule.symbol}: {atr:.2f}")
                else:
                    atr = None
                    
            except Exception as e:
                logger.debug(f"Streamer ATR calculation failed, using direct MT5: {e}")
                atr = None
            
            # Fallback to direct MT5 if streamer failed
            if atr is None or atr == 0:
                import MetaTrader5 as mt5
                # Ensure MT5 is initialized
                if not mt5.initialize():
                    logger.warning(f"MT5 initialization failed, cannot calculate ATR for {rule.symbol}")
                    return None
                
                bars = mt5.copy_rates_from_pos(rule.symbol, mt5.TIMEFRAME_M30, 0, 50)
                
                if bars is None or len(bars) < 14:
                    logger.warning(f"Could not get bars for ATR calculation for {rule.symbol}")
                    return None
                
                # Calculate ATR manually
                import numpy as np
                high_low = bars['high'][1:] - bars['low'][1:]
                high_close = np.abs(bars['high'][1:] - bars['close'][:-1])
                low_close = np.abs(bars['low'][1:] - bars['close'][:-1])
                tr = np.maximum(high_low, np.maximum(high_close, low_close))
                atr = np.mean(tr[-14:]) if len(tr) >= 14 else 0
            
            if atr == 0:
                logger.warning(f"ATR is 0 for {rule.symbol}, skipping hybrid adjustment")
                return None
            
            # Calculate VIX-based ATR multiplier (VIX already confirmed > threshold above)
            # For every 1 point VIX above threshold, increase ATR by 10%
            vix_excess = vix_price - rule.vix_threshold
            vix_multiplier = 1.0 + (vix_excess / 10.0)
            # Cap at 2.0x
            vix_multiplier = min(vix_multiplier, 2.0)
            
            # Calculate adjusted ATR
            atr_adjusted = atr * vix_multiplier
            
            # FIX: Calculate new SL from ENTRY price (not current price) to widen stop
            # Use 1.5x ATR as the stop distance (professional standard)
            stop_distance = atr_adjusted * 1.5
            
            if rule.direction == "buy":
                # Widen stop DOWN from entry (lower SL = wider stop)
                new_sl = entry_price - stop_distance
                # Only apply if it widens the stop (new_sl < current_sl)
                if new_sl >= current_sl:
                    logger.debug(
                        f"Hybrid adjustment would not widen stop (buy): "
                        f"new_sl={new_sl:.5f} >= current_sl={current_sl:.5f}, skipping"
                    )
                    return None
                # Ensure we don't move SL above entry (invalid for BUY)
                if new_sl > entry_price:
                    logger.warning(
                        f"Hybrid adjustment would move SL above entry (buy): "
                        f"new_sl={new_sl:.5f} > entry={entry_price:.5f}, skipping"
                    )
                    return None
            else:  # sell
                # Widen stop UP from entry (higher SL = wider stop)
                new_sl = entry_price + stop_distance
                # Only apply if it widens the stop (new_sl > current_sl)
                if new_sl <= current_sl:
                    logger.debug(
                        f"Hybrid adjustment would not widen stop (sell): "
                        f"new_sl={new_sl:.5f} <= current_sl={current_sl:.5f}, skipping"
                    )
                    return None
                # Ensure we don't move SL below entry (invalid for SELL)
                if new_sl < entry_price:
                    logger.warning(
                        f"Hybrid adjustment would move SL below entry (sell): "
                        f"new_sl={new_sl:.5f} < entry={entry_price:.5f}, skipping"
                    )
                    return None
            
            # Only adjust if the change is significant (> 0.1% of price)
            sl_change = abs(new_sl - current_sl)
            price_threshold = current_price * 0.001  # 0.1% of current price
            if sl_change < price_threshold:
                logger.debug(f"Hybrid adjustment too small ({sl_change:.5f}), skipping")
                return None
            
            # Modify position
            success = self._modify_position_sl(rule.ticket, new_sl, position.tp)
            
            if success:
                logger.info(
                    f"✅ Hybrid ATR+VIX adjustment for {rule.symbol} (ticket {rule.ticket}): "
                    f"{current_sl:.5f} → {new_sl:.5f} | "
                    f"ATR={atr:.3f}, VIX={vix_price if vix_price else 'N/A'}, "
                    f"Multiplier={vix_multiplier:.2f}, Distance={stop_distance:.3f}"
                )
                
                # Log to database
                if self.db_logger:
                    try:
                        self.db_logger.log_action(
                            ticket=rule.ticket,
                            symbol=rule.symbol,
                            action_type="hybrid_adjustment",
                            old_sl=current_sl,
                            new_sl=new_sl,
                            atr_value=atr,
                            vix_value=vix_price,
                            details={
                                "vix_multiplier": vix_multiplier,
                                "atr_adjusted": atr_adjusted,
                                "stop_distance": stop_distance,
                                "current_price": current_price,
                                "direction": rule.direction,
                                "vix_threshold": rule.vix_threshold
                            },
                            success=True
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log hybrid adjustment to database: {e}")
                
                return {
                    "action": "hybrid_adjustment",
                    "ticket": rule.ticket,
                    "symbol": rule.symbol,
                    "old_sl": current_sl,
                    "new_sl": new_sl,
                    "vix_price": vix_price,
                    "timestamp": datetime.now().isoformat(),
                    "details": {
                        "atr": atr,
                        "vix_multiplier": vix_multiplier,
                        "atr_adjusted": atr_adjusted,
                        "stop_distance": stop_distance
                    }
                }
            else:
                logger.error(f"Failed to apply hybrid adjustment for ticket {rule.ticket}")
                
                # Log failure to database
                if self.db_logger:
                    try:
                        self.db_logger.log_action(
                            ticket=rule.ticket,
                            symbol=rule.symbol,
                            action_type="hybrid_adjustment",
                            old_sl=current_sl,
                            new_sl=new_sl,
                            atr_value=atr,
                            vix_value=vix_price,
                            success=False,
                            error_message="Failed to modify position in MT5"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log hybrid adjustment failure to database: {e}")
                
                return None
                
        except Exception as e:
            logger.error(f"Error applying hybrid adjustment for ticket {rule.ticket}: {e}", exc_info=True)
            return None
    
    def _trail_stop_atr(
        self,
        rule: ExitRule,
        position,
        current_price: float,
        trailing_multiplier: Optional[float] = None  # NEW: Optional multiplier
    ) -> Optional[Dict[str, Any]]:
        """
        CONTINUOUS ATR-based trailing stop (runs every check cycle after breakeven).
        
        Logic:
        - Calculate current ATR from M30 bars
        - New SL = Current Price - (multiplier × ATR) for BUY
        - New SL = Current Price + (multiplier × ATR) for SELL
        - Only moves SL in favorable direction (never backwards)
        - Trails price as it moves in your favor
        - Multiplier defaults to 1.5x (normal) or 2.0x (wide when gates fail)
        
        Example (BUY trade):
        - Price at 3950, ATR = 5.0, multiplier = 1.5
        - SL = 3950 - (1.5 × 5.0) = 3942.50
        - Price moves to 3955
        - SL = 3955 - 7.5 = 3947.50 (trailed up!)
        - Price moves to 3960
        - SL = 3960 - 7.5 = 3952.50 (trailed up again!)
        """
        try:
            current_sl = position.sl if position.sl else rule.initial_sl
            
            # Phase 11: Get symbol-specific trailing multiplier
            try:
                from infra.session_helpers import SessionHelpers
                current_session = SessionHelpers.get_current_session()
            except Exception:
                current_session = None
            
            symbol_params = self._get_symbol_exit_params(rule.symbol, current_session)
            default_multiplier = symbol_params.get("trailing_atr_multiplier", 1.5)  # Default 1.5
            
            # Use provided multiplier, stored multiplier, symbol-specific, or default
            multiplier = trailing_multiplier or getattr(rule, "trailing_multiplier", None) or default_multiplier
            
            # Get current ATR
            import MetaTrader5 as mt5
            # Ensure MT5 is initialized
            if not mt5.initialize():
                logger.warning(f"MT5 initialization failed, cannot calculate trailing ATR for {rule.symbol}")
                # #region agent log
                import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_atr_init", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:2391", "message": "MT5 init failed", "data": {"ticket": rule.ticket, "symbol": rule.symbol}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
                # #endregion
                return None
            
            bars = mt5.copy_rates_from_pos(rule.symbol, mt5.TIMEFRAME_M30, 0, 50)
            
            if bars is None or len(bars) < 14:
                logger.debug(f"Could not get bars for trailing ATR calculation for {rule.symbol}")
                # #region agent log
                import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_atr_bars", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:2397", "message": "Bars unavailable", "data": {"ticket": rule.ticket, "symbol": rule.symbol, "bars": bars is None, "bars_len": len(bars) if bars is not None else 0}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
                # #endregion
                return None
            
            # Calculate ATR
            import numpy as np
            high_low = bars['high'][1:] - bars['low'][1:]
            high_close = np.abs(bars['high'][1:] - bars['close'][:-1])
            low_close = np.abs(bars['low'][1:] - bars['close'][:-1])
            tr = np.maximum(high_low, np.maximum(high_close, low_close))
            atr = np.mean(tr[-14:]) if len(tr) >= 14 else 0
            
            if atr == 0:
                logger.debug(f"ATR is 0 for {rule.symbol}, skipping trail")
                # #region agent log
                import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_atr_zero", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:2409", "message": "ATR is zero", "data": {"ticket": rule.ticket, "symbol": rule.symbol}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
                # #endregion
                return None
            
            # Calculate new trailing SL based on current price and ATR
            # Use configurable multiplier (1.5x normal, 2.0x wide)
            trailing_distance = atr * multiplier
            
            if rule.direction == "buy":
                new_sl = current_price - trailing_distance
            else:
                new_sl = current_price + trailing_distance
            
            # #region agent log
            import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_trail_calc", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:2415", "message": "Trailing SL calculated", "data": {"ticket": rule.ticket, "symbol": rule.symbol, "current_price": current_price, "current_sl": current_sl, "new_sl": new_sl, "atr": atr, "multiplier": multiplier, "trailing_distance": trailing_distance, "direction": rule.direction}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
            # #endregion
            
            # CRITICAL: Only move SL in favorable direction (NEVER backwards)
            if rule.direction == "buy":
                if new_sl <= current_sl:
                    # New SL would be lower than current - don't trail backwards!
                    # #region agent log
                    import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_trail_back", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:2424", "message": "Trailing backwards blocked", "data": {"ticket": rule.ticket, "symbol": rule.symbol, "new_sl": new_sl, "current_sl": current_sl, "direction": "buy"}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
                    # #endregion
                    return None
            else:  # sell
                if new_sl >= current_sl:
                    # New SL would be higher than current - don't trail backwards!
                    # #region agent log
                    import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_trail_back", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:2429", "message": "Trailing backwards blocked", "data": {"ticket": rule.ticket, "symbol": rule.symbol, "new_sl": new_sl, "current_sl": current_sl, "direction": "sell"}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
                    # #endregion
                    return None
            
            # Phase 11: Get symbol-specific minimum change threshold
            symbol_params = self._get_symbol_exit_params(rule.symbol, current_session)
            min_change_pct = symbol_params.get("min_sl_change_pct", 0.05)  # Default 0.05%
            
            # Check if movement is significant (symbol-specific threshold to avoid tiny adjustments)
            sl_change = abs(new_sl - current_sl)
            price_threshold = current_price * (min_change_pct / 100.0)
            if sl_change < price_threshold:
                # #region agent log
                import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_trail_min", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:2439", "message": "Trailing change too small", "data": {"ticket": rule.ticket, "symbol": rule.symbol, "sl_change": sl_change, "price_threshold": price_threshold, "min_change_pct": min_change_pct}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "D"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
                # #endregion
                return None
            
            # Modify position
            # #region agent log
            import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_modify_before", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:2443", "message": "Before modify_position_sl", "data": {"ticket": rule.ticket, "symbol": rule.symbol, "new_sl": new_sl, "current_tp": position.tp}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
            # #endregion
            success = self._modify_position_sl(rule.ticket, new_sl, position.tp)
            # #region agent log
            import json; log_data = {"id": f"log_{int(__import__('time').time() * 1000)}_modify_after", "timestamp": int(__import__('time').time() * 1000), "location": "intelligent_exit_manager.py:2443", "message": "After modify_position_sl", "data": {"ticket": rule.ticket, "symbol": rule.symbol, "success": success, "new_sl": new_sl}, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "E"}; __import__('pathlib').Path(r"c:\Coding\MoneyBotv2.7 - 10 Nov 25\.cursor\debug.log").open('a', encoding='utf-8').write(json.dumps(log_data) + '\n')
            # #endregion
            
            if success:
                logger.info(
                    f"📈 ATR Trailing Stop for {rule.symbol} (ticket {rule.ticket}): "
                    f"{current_sl:.5f} → {new_sl:.5f} | "
                    f"ATR={atr:.3f}, Multiplier={multiplier:.1f}x, Distance={trailing_distance:.3f}"
                )
                
                # Log to database
                if self.db_logger:
                    try:
                        self.db_logger.log_action(
                            ticket=rule.ticket,
                            symbol=rule.symbol,
                            action_type="trailing_stop",
                            old_sl=current_sl,
                            new_sl=new_sl,
                            atr_value=atr,
                            details={
                                "trailing_distance": trailing_distance,
                                "current_price": current_price,
                                "direction": rule.direction,
                                "atr_multiplier": 1.5
                            },
                            success=True
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log trailing stop to database: {e}")
                
                return {
                    "action": "trailing_stop",
                    "ticket": rule.ticket,
                    "symbol": rule.symbol,
                    "old_sl": current_sl,
                    "new_sl": new_sl,
                    "timestamp": datetime.now().isoformat(),
                    "details": {
                        "atr": atr,
                        "trailing_distance": trailing_distance,
                        "price": current_price
                    }
                }
            else:
                logger.debug(f"Failed to update trailing SL for ticket {rule.ticket}")
                
                # Log failure to database
                if self.db_logger:
                    try:
                        self.db_logger.log_action(
                            ticket=rule.ticket,
                            symbol=rule.symbol,
                            action_type="trailing_stop",
                            old_sl=current_sl,
                            new_sl=new_sl,
                            atr_value=atr,
                            success=False,
                            error_message="Failed to modify position in MT5"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log trailing stop failure to database: {e}")
                
                return None
                
        except Exception as e:
            logger.error(f"Error trailing stop for ticket {rule.ticket}: {e}", exc_info=True)
            return None
    
    def _adjust_for_vix(
        self,
        rule: ExitRule,
        position,
        current_price: float,
        vix_price: float
    ) -> Optional[Dict[str, Any]]:
        """Widen stop loss when VIX exceeds threshold (LEGACY - use hybrid instead)"""
        try:
            current_sl = position.sl if position.sl else rule.initial_sl
            
            # Calculate distance from entry to current SL
            sl_distance = abs(current_sl - rule.entry_price)
            
            # Widen by multiplier
            new_distance = sl_distance * rule.vix_multiplier
            
            if rule.direction == "buy":
                new_sl = rule.entry_price - new_distance
            else:
                new_sl = rule.entry_price + new_distance
            
            # Don't move SL backwards (only widen)
            if rule.direction == "buy" and new_sl >= current_sl:
                logger.debug(f"VIX adjustment would move SL backwards (buy), skipping")
                return None
            if rule.direction == "sell" and new_sl <= current_sl:
                logger.debug(f"VIX adjustment would move SL backwards (sell), skipping")
                return None
            
            # Modify position
            success = self._modify_position_sl(rule.ticket, new_sl, position.tp)
            
            if success:
                logger.info(f"✅ Widened SL for VIX spike on {rule.symbol} (ticket {rule.ticket}): {current_sl:.5f} → {new_sl:.5f} (VIX={vix_price:.2f})")
                return {
                    "action": "vix_adjustment",
                    "ticket": rule.ticket,
                    "symbol": rule.symbol,
                    "old_sl": current_sl,
                    "new_sl": new_sl,
                    "vix_price": vix_price,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                logger.error(f"Failed to adjust SL for VIX for ticket {rule.ticket}")
                return None
                
        except Exception as e:
            logger.error(f"Error adjusting for VIX for ticket {rule.ticket}: {e}", exc_info=True)
            return None
    
    def _modify_position_sl(self, ticket: int, new_sl: float, current_tp: float, max_retries: int = 3) -> bool:
        """
        Modify position SL in MT5 with conflict prevention and retry logic (Phase 12).
        
        Args:
            ticket: Trade ticket number
            new_sl: New stop loss price
            current_tp: Current take profit price (preserved)
            max_retries: Maximum retry attempts (default: 3)
        
        Returns:
            True if modification successful, False otherwise
        """
        import time
        
        # Phase 12: Check trade registry to prevent conflicts
        try:
            from infra.trade_registry import get_trade_state
            trade_state = get_trade_state(ticket)
            if trade_state:
                managed_by = trade_state.get("managed_by", "")
                # Skip if managed by Universal Manager (unless breakeven not triggered yet)
                if managed_by == "universal_sl_tp_manager":
                    # Check if breakeven already triggered (Universal Manager takes over)
                    breakeven_triggered = trade_state.get("breakeven_triggered", False)
                    if breakeven_triggered:
                        logger.debug(f"Skipping SL modification for {ticket}: managed by Universal Manager (breakeven triggered)")
                        return False
                    # If not breakeven yet, Intelligent Exit Manager can manage it
                    logger.debug(f"Trade {ticket} registered with Universal Manager but breakeven not triggered - proceeding")
                # Skip if managed by DTMS in defensive mode
                elif managed_by == "dtms_manager":
                    if self._is_dtms_in_defensive_mode(ticket):
                        logger.debug(f"Skipping SL modification for {ticket}: DTMS in defensive mode")
                        return False
        except (ImportError, AttributeError, Exception) as e:
            logger.debug(f"Trade registry unavailable: {e}, proceeding with modification")
        
        # Phase 12: Retry logic with exponential backoff
        for attempt in range(max_retries):
            try:
                # Ensure MT5 is connected before attempting modification
                if not self.mt5.connect():
                    logger.error(f"MT5 not connected, cannot modify position {ticket}")
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                        logger.debug(f"Retry {attempt + 1}/{max_retries} for ticket {ticket} in {wait_time}s")
                        time.sleep(wait_time)
                        continue
                    return False
                
                if hasattr(self.mt5, 'modify_position'):
                    success = self.mt5.modify_position(
                        ticket=ticket,
                        new_sl=new_sl,
                        new_tp=current_tp
                    )
                    if success:
                        return True
                else:
                    # Fallback: direct MT5 modification
                    # Verify MT5 is initialized before calling positions_get
                    if not mt5.initialize():
                        logger.error(f"MT5 not initialized, cannot modify position {ticket}")
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) * 0.5
                            time.sleep(wait_time)
                            continue
                        return False
                    
                    # Get position and verify it still exists (race condition protection)
                    position = mt5.positions_get(ticket=ticket)
                    if not position or len(position) == 0:
                        logger.warning(f"Position {ticket} no longer exists, cannot modify")
                        return False
                    
                    position = position[0]
                    
                    # Verify position still exists one more time before sending order (double-check for race condition)
                    verify_pos = mt5.positions_get(ticket=ticket)
                    if not verify_pos or len(verify_pos) == 0:
                        logger.warning(f"Position {ticket} was closed during modification attempt")
                        return False
                    
                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "symbol": position.symbol,
                        "position": ticket,
                        "sl": new_sl,
                        "tp": current_tp if current_tp else position.tp
                    }
                    
                    result = mt5.order_send(request)
                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        return True
                    elif result:
                        logger.warning(f"MT5 modify failed for {ticket}: {result.retcode} - {result.comment}")
                        # Retry on transient errors
                        if attempt < max_retries - 1 and result.retcode in [10004, 10006, 10007]:  # Common transient errors
                            wait_time = (2 ** attempt) * 0.5
                            logger.debug(f"Retry {attempt + 1}/{max_retries} for ticket {ticket} in {wait_time}s (error: {result.retcode})")
                            time.sleep(wait_time)
                            continue
                        return False
                    else:
                        logger.error(f"MT5 modify returned None for {ticket}")
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) * 0.5
                            time.sleep(wait_time)
                            continue
                        return False
                
                # If failed, wait before retry (exponential backoff)
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                    logger.debug(f"Retry {attempt + 1}/{max_retries} for ticket {ticket} in {wait_time}s")
                    time.sleep(wait_time)
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for ticket {ticket}: {e}")
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 0.5
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error modifying position SL for ticket {ticket} after {max_retries} attempts: {e}", exc_info=True)
        
        logger.error(f"Failed to modify position {ticket} after {max_retries} attempts")
        return False
    
    def _is_dtms_in_defensive_mode(self, ticket: int) -> bool:
        """
        Check if DTMS is in defensive mode (HEDGED/WARNING_L2) via API.
        
        Phase 4: Updated to query DTMS API server instead of local engine.
        Includes caching and conservative fallback for API unavailability.
        """
        import time
        import requests
        import logging
        
        logger_local = logging.getLogger(__name__)
        
        # Initialize caches if not exists (lazy initialization)
        if not hasattr(self, '_dtms_state_cache'):
            self._dtms_state_cache = {}  # 10 second cache
        if not hasattr(self, '_dtms_last_known_cache'):
            self._dtms_last_known_cache = {}  # 30 second TTL
        
        try:
            cache_key = f"dtms_state_{ticket}"
            
            # Check cache first (10 second cache)
            cached_state = self._dtms_state_cache.get(cache_key)
            if cached_state is not None:
                cache_time, state = cached_state
                if time.time() - cache_time < 10:  # 10 second cache
                    return state in ['HEDGED', 'WARNING_L2']
            
            # Query API with retry logic (1 retry, 2 second timeout)
            for attempt in range(2):  # 1 initial attempt + 1 retry
                try:
                    response = requests.get(
                        f"http://127.0.0.1:8001/dtms/trade/{ticket}",
                        timeout=2.0
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if data and not data.get('error'):
                            state = data.get('state', '')
                            is_defensive = state in ['HEDGED', 'WARNING_L2']
                            # Cache the result (both caches)
                            self._dtms_state_cache[cache_key] = (time.time(), state)
                            self._dtms_last_known_cache[cache_key] = (time.time(), state)
                            return is_defensive
                    elif response.status_code == 404:
                        # Trade not found in DTMS - not in defensive mode
                        logger_local.debug(f"Trade {ticket} not found in DTMS - not in defensive mode")
                        return False
                except requests.exceptions.Timeout:
                    logger_local.warning(f"⚠️ DTMS API query timeout for ticket {ticket} (attempt {attempt + 1}/2)")
                    if attempt < 1:  # Only retry once
                        time.sleep(0.5)  # Small delay before retry
                        continue
                except requests.exceptions.RequestException as e:
                    logger_local.warning(f"⚠️ DTMS API query failed for ticket {ticket} (attempt {attempt + 1}/2): {e}")
                    if attempt < 1:  # Only retry once
                        time.sleep(0.5)  # Small delay before retry
                        continue
                except Exception as e:
                    logger_local.error(f"❌ Unexpected error querying DTMS state for {ticket}: {e}", exc_info=True)
                    break  # Don't retry for unexpected errors
            
            # API unavailable - use last known state cache (30 second TTL)
            last_known = self._dtms_last_known_cache.get(cache_key)
            if last_known:
                cache_time, state = last_known
                if time.time() - cache_time < 30:  # 30 second TTL
                    logger_local.debug(f"Using cached DTMS state for {ticket}: {state}")
                    return state in ['HEDGED', 'WARNING_L2']
            
            # No cache available - assume not in defensive mode (conservative)
            logger_local.warning(f"⚠️ DTMS API unavailable for ticket {ticket}, assuming not in defensive mode (conservative)")
            return False
            
        except Exception as e:
            logger_local.error(f"❌ Error in _is_dtms_in_defensive_mode for {ticket}: {e}", exc_info=True)
            # Use last known state if available
            cache_key = f"dtms_state_{ticket}"
            last_known = self._dtms_last_known_cache.get(cache_key)
            if last_known:
                cache_time, state = last_known
                if time.time() - cache_time < 30:
                    return state in ['HEDGED', 'WARNING_L2']
            return False  # Assume not in defensive mode if API unavailable
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get system health status (Phase 12: Health Check).
        
        Returns:
            Dict with health status, active rules count, circuit breaker status, cache status, and errors
        """
        import time
        
        status = {
            "status": "healthy",
            "active_rules": len(self.rules),
            "atr_circuit_breakers": {},
            "cache_status": {},
            "errors": []
        }
        
        # Check ATR circuit breakers
        for symbol, timestamp in self._atr_circuit_breaker_timestamps.items():
            time_since_open = time.time() - timestamp
            status["atr_circuit_breakers"][symbol] = {
                "open": True,
                "time_since_open": round(time_since_open, 1),
                "will_reset_in": max(0, round(self._atr_circuit_breaker_timeout - time_since_open, 1)),
                "failure_count": self._atr_failure_count.get(symbol, 0),
                "fallback_value": self._atr_fallback_values.get(symbol)
            }
        
        # Check Advanced provider cache
        if hasattr(self, 'advanced_provider') and self.advanced_provider:
            if hasattr(self.advanced_provider, '_cache') and hasattr(self.advanced_provider, '_cache_lock'):
                with self.advanced_provider._cache_lock:
                    status["cache_status"] = {
                        "size": len(self.advanced_provider._cache),
                        "max_size": getattr(self.advanced_provider, '_max_cache_size', 50),
                        "usage_pct": round((len(self.advanced_provider._cache) / getattr(self.advanced_provider, '_max_cache_size', 50)) * 100, 1)
                    }
        
        # Check for errors (degraded takes priority over idle)
        if status["atr_circuit_breakers"]:
            status["status"] = "degraded"
            status["errors"].append(f"ATR circuit breakers open for {len(status['atr_circuit_breakers'])} symbol(s)")
        elif status["active_rules"] == 0:
            status["status"] = "idle"
        
        return status
    
    def _get_vix_price(self) -> Optional[float]:
        """Fetch current VIX price from Yahoo Finance"""
        try:
            from infra.market_indices_service import create_market_indices_service
            indices = create_market_indices_service()
            vix_data = indices.get_vix()
            return vix_data.get('price')
        except Exception as e:
            logger.warning(f"Could not fetch VIX price: {e}")
            return None
    
    def _load_rules(self):
        """Load rules from JSON file with validation and cleanup stale rules (Phase 12: JSON validation)"""
        if not self.storage_file.exists():
            logger.info("No existing exit rules file found, starting fresh")
            return
        
        try:
            with open(self.storage_file, 'r') as f:
                data = json.load(f)
            
            # Phase 12: Validate structure
            if not isinstance(data, dict):
                logger.error(f"Invalid rules file structure: expected dict, got {type(data)}")
                # Backup corrupted file
                backup_file = self.storage_file.with_suffix('.corrupted')
                try:
                    self.storage_file.rename(backup_file)
                    logger.warning(f"Backed up corrupted file to {backup_file}")
                except Exception as e:
                    logger.error(f"Failed to backup corrupted file: {e}")
                return
            
            # Phase 9: Thread-safe loading with validation
            loaded_count = 0
            with self.rules_lock:
                for ticket_str, rule_data in data.items():
                    try:
                        ticket = int(ticket_str)
                        # Phase 12: Validate rule data structure
                        if not isinstance(rule_data, dict):
                            logger.warning(f"Invalid rule data for ticket {ticket_str}, skipping")
                            continue
                        
                        # Phase 12: Validate required fields
                        required_fields = ["ticket", "symbol", "entry_price", "direction", "initial_sl", "initial_tp"]
                        if not all(field in rule_data for field in required_fields):
                            logger.warning(f"Missing required fields for ticket {ticket_str}, skipping")
                            continue
                        
                        rule = ExitRule.from_dict(rule_data)
                        self.rules[ticket] = rule
                        loaded_count += 1
                    except (ValueError, KeyError, TypeError) as e:
                        logger.warning(f"Error loading rule for ticket {ticket_str}: {e}, skipping")
                        continue
            
            # Phase 9: Thread-safe access for logging
            with self.rules_lock:
                rules_count = len(self.rules)
            
            if rules_count > 0:
                logger.info(f"✅ Loaded {rules_count} exit rules from storage")
                
                # Auto-cleanup stale rules (positions no longer open)
                self._cleanup_stale_rules()
                
                # Log remaining valid rules (thread-safe snapshot)
                with self.rules_lock:
                    rules_snapshot = list(self.rules.items())
                
                if rules_snapshot:
                    logger.info(f"📊 Monitoring {len(rules_snapshot)} active position(s) with intelligent exits")
                    for ticket, rule in rules_snapshot:
                        logger.info(
                            f"   → Ticket {ticket} ({rule.symbol}): "
                            f"Breakeven={'✅' if rule.breakeven_triggered else '⏳'}, "
                            f"Partial={'✅' if rule.partial_triggered else '⏳'}, "
                            f"LastCheck={rule.last_check or 'Never'}"
                        )
                else:
                    logger.info("🧹 All loaded rules were stale - starting fresh")
            else:
                logger.info("No exit rules to resume - starting fresh")
            
        except Exception as e:
            logger.error(f"Error loading exit rules: {e}", exc_info=True)
    
    def _save_rules(self):
        """Save rules to JSON file (thread-safe with atomic write) - Phase 9: Thread-safe snapshot"""
        try:
            # Phase 9: Create snapshot while holding lock
            with self.rules_lock:
                data = {str(ticket): rule.to_dict() for ticket, rule in self.rules.items()}
            
            # Write to file (outside lock to avoid blocking)
            
            # Use atomic write: write to temp file, then rename (prevents corruption)
            temp_file = self.storage_file.with_suffix('.tmp')
            
            # Write to temp file first
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
                f.flush()
                try:
                    os.fsync(f.fileno())  # Force write to disk
                except AttributeError:
                    pass  # Windows may not have fsync
            
            # Atomic rename (atomic on most filesystems, prevents corruption on crashes)
            try:
                temp_file.replace(self.storage_file)
            except OSError:
                # Fallback: copy on Windows if replace fails
                import shutil
                shutil.move(str(temp_file), str(self.storage_file))
            
            logger.debug(f"Saved {len(self.rules)} exit rules to storage")
            
        except Exception as e:
            logger.error(f"Error saving exit rules: {e}", exc_info=True)
            # Try to clean up temp file if it exists
            try:
                temp_file = self.storage_file.with_suffix('.tmp')
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass
    
    def _check_binance_momentum(self, rule: ExitRule, position, current_price: float) -> List[Dict[str, Any]]:
        """
        Check Binance real-time momentum for reversal signals.
        
        Early exit if momentum reverses sharply against position.
        """
        actions = []
        
        try:
            # Get recent price history (last 10 ticks = ~10 seconds)
            history = self.binance_service.get_history(rule.symbol, count=10)
            if len(history) < 10:
                return actions
            
            # Calculate momentum
            prices = [t['price'] for t in history]
            momentum = self._calculate_momentum(prices)
            
            # Check for momentum reversal
            if rule.direction == "buy":
                # BUY position but momentum turning sharply negative
                if momentum < -0.20:  # -0.20% sharp reversal
                    logger.warning(f"🔴 Momentum reversal detected for {rule.symbol} (ticket {rule.ticket}): {momentum:.2f}%")
                    actions.append({
                        "type": "momentum_warning",
                        "ticket": rule.ticket,
                        "symbol": rule.symbol,
                        "reason": f"Binance momentum reversal ({momentum:.2f}%)",
                        "momentum": momentum,
                        "recommendation": "Consider tightening stop or partial exit"
                    })
            
            elif rule.direction == "sell":
                # SELL position but momentum turning sharply positive
                if momentum > +0.20:  # +0.20% sharp reversal
                    logger.warning(f"🟢 Momentum reversal detected for {rule.symbol} (ticket {rule.ticket}): {momentum:+.2f}%")
                    actions.append({
                        "type": "momentum_warning",
                        "ticket": rule.ticket,
                        "symbol": rule.symbol,
                        "reason": f"Binance momentum reversal ({momentum:+.2f}%)",
                        "momentum": momentum,
                        "recommendation": "Consider tightening stop or partial exit"
                    })
            
        except Exception as e:
            logger.debug(f"Binance momentum check failed for {rule.symbol}: {e}")
        
        return actions
    
    def _calculate_momentum(self, prices: list) -> float:
        """Calculate momentum as % change with linear regression"""
        if len(prices) < 2:
            return 0.0
        
        # Simple momentum: % change from first to last
        first_price = prices[0]
        last_price = prices[-1]
        
        momentum_pct = ((last_price - first_price) / first_price) * 100
        return momentum_pct
    
    def _convert_to_binance_symbol(self, mt5_symbol: str) -> str:
        """
        Convert MT5 symbol (e.g., "BTCUSDc") to Binance symbol format (e.g., "BTCUSDT").
        
        OrderFlowService stores symbols in UPPERCASE format from stream callbacks.
        """
        symbol = mt5_symbol.upper()
        
        # Remove 'c' suffix
        if symbol.endswith("C"):
            symbol = symbol[:-1]
        
        # Add USDT for crypto pairs
        if symbol.startswith(("BTC", "ETH", "LTC", "XRP", "ADA")):
            if not symbol.endswith("USDT"):
                symbol = symbol.replace("USD", "USDT")
        
        return symbol  # Return UPPERCASE (matching OrderFlowService internal format)
    
    def _check_whale_orders(self, rule: ExitRule, position) -> List[Dict[str, Any]]:
        """
        Check for large whale orders that might impact position.
        
        Automatically tightens SL and/or takes partial exit if enabled.
        """
        actions = []
        
        try:
            # Convert MT5 symbol to Binance format for order flow service
            binance_symbol = self._convert_to_binance_symbol(rule.symbol)
            
            # Get recent whale orders (last 60 seconds)
            recent_whales = self.order_flow_service.get_recent_whales(
                binance_symbol,
                min_size="large"  # $500k+ orders
            )
            
            for whale in recent_whales:
                # Check if whale order is against our position
                if rule.direction == "buy" and whale["side"] == "SELL":
                    # Large SELL whale while we're BUY
                    if whale["usd_value"] >= 500000:  # $500k+
                        severity = "CRITICAL" if whale["usd_value"] >= 1000000 else "HIGH"
                        logger.warning(
                            f"🐋 {severity}: Large SELL whale detected for {rule.symbol} "
                            f"(ticket {rule.ticket}): ${whale['usd_value']:,.0f} @ {whale['price']}"
                        )
                        
                        # Get current price for auto-execution
                        current_price = position.price_current
                        current_sl = position.sl
                        
                        executed_actions = []
                        
                        # ⭐ AUTO-EXECUTE: Tighten Stop Loss
                        if self.whale_auto_tighten_sl:
                            tighten_pct = self.whale_critical_tighten_pct if severity == "CRITICAL" else self.whale_high_tighten_pct
                            # Calculate new SL: within X% of current price (tight protection)
                            if rule.direction == "buy":
                                # For BUY: SL below current price
                                new_sl = current_price * (1 - tighten_pct / 100)
                            else:
                                # For SELL: SL above current price
                                new_sl = current_price * (1 + tighten_pct / 100)
                            
                            # Only tighten if new SL is better than current (closer to price)
                            if rule.direction == "buy" and (current_sl == 0 or new_sl > current_sl):
                                if self._modify_position_sl(rule.ticket, new_sl, position.tp):
                                    logger.info(f"✅ Auto-tightened SL to {new_sl:.5f} due to {severity} whale")
                                    executed_actions.append("sl_tightened")
                                    actions.append({
                                        "type": "whale_sl_tightened",
                                        "ticket": rule.ticket,
                                        "symbol": rule.symbol,
                                        "old_sl": current_sl,
                                        "new_sl": new_sl,
                                        "severity": severity,
                                        "reason": f"Auto-tightened due to ${whale['usd_value']:,.0f} SELL whale"
                                    })
                            elif rule.direction == "sell" and (current_sl == 0 or new_sl < current_sl):
                                if self._modify_position_sl(rule.ticket, new_sl, position.tp):
                                    logger.info(f"✅ Auto-tightened SL to {new_sl:.5f} due to {severity} whale")
                                    executed_actions.append("sl_tightened")
                                    actions.append({
                                        "type": "whale_sl_tightened",
                                        "ticket": rule.ticket,
                                        "symbol": rule.symbol,
                                        "old_sl": current_sl,
                                        "new_sl": new_sl,
                                        "severity": severity,
                                        "reason": f"Auto-tightened due to ${whale['usd_value']:,.0f} BUY whale"
                                    })
                        
                        # ⭐ AUTO-EXECUTE: Partial Exit
                        if self.whale_auto_partial_exit and position.volume > 0.01:
                            partial_pct = self.whale_critical_partial_pct if severity == "CRITICAL" else self.whale_high_partial_pct
                            
                            # Check if we haven't already taken partial for this whale alert (prevent duplicates)
                            whale_action_key = f"whale_partial_{severity}_{whale['usd_value']:.0f}"
                            if whale_action_key not in rule.actions_taken:
                                partial_result = self._take_partial_profit_by_pct(
                                    rule, position, current_price, partial_pct,
                                    reason=f"{severity} whale protection"
                                )
                                if partial_result:
                                    rule.actions_taken.append(whale_action_key)
                                    executed_actions.append("partial_exit")
                                    actions.append(partial_result)
                        
                        # Always send alert notification (even if auto-executed)
                        actions.append({
                            "type": "whale_alert",
                            "ticket": rule.ticket,
                            "symbol": rule.symbol,
                            "reason": f"${whale['usd_value']:,.0f} SELL whale @ {whale['price']}",
                            "whale_size": whale["whale_size"],
                            "whale_side": "SELL",
                            "severity": severity,
                            "executed_actions": executed_actions,
                            "recommendation": "SL tightened & partial exit taken" if executed_actions else "Monitor closely"
                        })
                
                elif rule.direction == "sell" and whale["side"] == "BUY":
                    # Large BUY whale while we're SELL
                    if whale["usd_value"] >= 500000:
                        severity = "CRITICAL" if whale["usd_value"] >= 1000000 else "HIGH"
                        logger.warning(
                            f"🐋 {severity}: Large BUY whale detected for {rule.symbol} "
                            f"(ticket {rule.ticket}): ${whale['usd_value']:,.0f} @ {whale['price']}"
                        )
                        
                        # Get current price for auto-execution
                        current_price = position.price_current
                        current_sl = position.sl
                        
                        executed_actions = []
                        
                        # ⭐ AUTO-EXECUTE: Tighten Stop Loss
                        if self.whale_auto_tighten_sl:
                            tighten_pct = self.whale_critical_tighten_pct if severity == "CRITICAL" else self.whale_high_tighten_pct
                            # Calculate new SL: within X% of current price
                            new_sl = current_price * (1 + tighten_pct / 100)  # SELL: SL above price
                            
                            # Only tighten if new SL is better than current
                            if current_sl == 0 or new_sl < current_sl:
                                if self._modify_position_sl(rule.ticket, new_sl, position.tp):
                                    logger.info(f"✅ Auto-tightened SL to {new_sl:.5f} due to {severity} whale")
                                    executed_actions.append("sl_tightened")
                                    actions.append({
                                        "type": "whale_sl_tightened",
                                        "ticket": rule.ticket,
                                        "symbol": rule.symbol,
                                        "old_sl": current_sl,
                                        "new_sl": new_sl,
                                        "severity": severity,
                                        "reason": f"Auto-tightened due to ${whale['usd_value']:,.0f} BUY whale"
                                    })
                        
                        # ⭐ AUTO-EXECUTE: Partial Exit
                        if self.whale_auto_partial_exit and position.volume > 0.01:
                            partial_pct = self.whale_critical_partial_pct if severity == "CRITICAL" else self.whale_high_partial_pct
                            
                            whale_action_key = f"whale_partial_{severity}_{whale['usd_value']:.0f}"
                            if whale_action_key not in rule.actions_taken:
                                partial_result = self._take_partial_profit_by_pct(
                                    rule, position, current_price, partial_pct,
                                    reason=f"{severity} whale protection"
                                )
                                if partial_result:
                                    rule.actions_taken.append(whale_action_key)
                                    executed_actions.append("partial_exit")
                                    actions.append(partial_result)
                        
                        # Always send alert notification
                        actions.append({
                            "type": "whale_alert",
                            "ticket": rule.ticket,
                            "symbol": rule.symbol,
                            "reason": f"${whale['usd_value']:,.0f} BUY whale @ {whale['price']}",
                            "whale_size": whale["whale_size"],
                            "whale_side": "BUY",
                            "severity": severity,
                            "executed_actions": executed_actions,
                            "recommendation": "SL tightened & partial exit taken" if executed_actions else "Monitor closely"
                        })
            
        except Exception as e:
            logger.debug(f"Whale order check failed for {rule.symbol}: {e}")
        
        return actions
    
    def _check_liquidity_voids(self, rule: ExitRule, position, current_price: float) -> List[Dict[str, Any]]:
        """
        Check if price is approaching liquidity voids.
        
        Automatically executes partial or full exit if enabled.
        """
        actions = []
        
        try:
            # Convert MT5 symbol to Binance format for order flow service
            binance_symbol = self._convert_to_binance_symbol(rule.symbol)
            
            # Get liquidity voids
            voids = self.order_flow_service.get_liquidity_voids(binance_symbol)
            
            for void in voids:
                # Calculate distance to void
                if rule.direction == "buy":
                    # Check for ASK voids above current price (where we'd exit)
                    if void["side"] == "ask" and current_price < void["price_from"]:
                        distance = void["price_from"] - current_price
                        distance_pct = (distance / current_price) * 100
                        
                        # Alert if within 0.1% of void
                        if distance_pct < 0.1:
                            logger.warning(
                                f"⚠️ Liquidity void ahead for {rule.symbol} (ticket {rule.ticket}): "
                                f"{void['price_from']:.2f} → {void['price_to']:.2f} (severity: {void['severity']:.1f}x, distance: {distance_pct:.3f}%)"
                            )
                            
                            executed_actions = []
                            
                            # ⭐ AUTO-EXECUTE: Close 100% if very close to void
                            if distance_pct <= self.void_close_all_threshold and position.volume > 0.01:
                                # Close entire position to avoid slippage
                                close_result = self._close_position_fully(
                                    rule, position, current_price,
                                    reason=f"Very close to liquidity void ({distance_pct:.3f}%)"
                                )
                                if close_result:
                                    executed_actions.append("full_close")
                                    actions.append(close_result)
                            
                            # ⭐ AUTO-EXECUTE: Partial exit before void
                            elif distance_pct <= self.void_distance_threshold and self.void_auto_partial_exit and position.volume > 0.01:
                                void_action_key = f"void_partial_{void['price_from']:.2f}"
                                if void_action_key not in rule.actions_taken:
                                    partial_result = self._take_partial_profit_by_pct(
                                        rule, position, current_price, self.void_partial_exit_pct,
                                        reason=f"Liquidity void protection ({distance_pct:.3f}% away)"
                                    )
                                    if partial_result:
                                        rule.actions_taken.append(void_action_key)
                                        executed_actions.append("partial_exit")
                                        actions.append(partial_result)
                            
                            # Always send warning notification
                            actions.append({
                                "type": "void_warning",
                                "ticket": rule.ticket,
                                "symbol": rule.symbol,
                                "reason": f"Approaching liquidity void at {void['price_from']:.2f}",
                                "void_side": "ask",
                                "void_range": f"{void['price_from']:.2f} → {void['price_to']:.2f}",
                                "severity": void["severity"],
                                "distance_pct": distance_pct,
                                "executed_actions": executed_actions,
                                "recommendation": "Position closed" if "full_close" in executed_actions else \
                                                 "Partial exit taken" if "partial_exit" in executed_actions else \
                                                 "Consider partial exit before void"
                            })
                
                elif rule.direction == "sell":
                    # Check for BID voids below current price (where we'd exit)
                    if void["side"] == "bid" and current_price > void["price_to"]:
                        distance = current_price - void["price_to"]
                        distance_pct = (distance / current_price) * 100
                        
                        # Alert if within 0.1% of void
                        if distance_pct < 0.1:
                            logger.warning(
                                f"⚠️ Liquidity void ahead for {rule.symbol} (ticket {rule.ticket}): "
                                f"{void['price_from']:.2f} → {void['price_to']:.2f} (severity: {void['severity']:.1f}x, distance: {distance_pct:.3f}%)"
                            )
                            
                            executed_actions = []
                            
                            # ⭐ AUTO-EXECUTE: Close 100% if very close to void
                            if distance_pct <= self.void_close_all_threshold and position.volume > 0.01:
                                close_result = self._close_position_fully(
                                    rule, position, current_price,
                                    reason=f"Very close to liquidity void ({distance_pct:.3f}%)"
                                )
                                if close_result:
                                    executed_actions.append("full_close")
                                    actions.append(close_result)
                            
                            # ⭐ AUTO-EXECUTE: Partial exit before void
                            elif distance_pct <= self.void_distance_threshold and self.void_auto_partial_exit and position.volume > 0.01:
                                void_action_key = f"void_partial_{void['price_to']:.2f}"
                                if void_action_key not in rule.actions_taken:
                                    partial_result = self._take_partial_profit_by_pct(
                                        rule, position, current_price, self.void_partial_exit_pct,
                                        reason=f"Liquidity void protection ({distance_pct:.3f}% away)"
                                    )
                                    if partial_result:
                                        rule.actions_taken.append(void_action_key)
                                        executed_actions.append("partial_exit")
                                        actions.append(partial_result)
                            
                            # Always send warning notification
                            actions.append({
                                "type": "void_warning",
                                "ticket": rule.ticket,
                                "symbol": rule.symbol,
                                "reason": f"Approaching liquidity void at {void['price_to']:.2f}",
                                "void_side": "bid",
                                "void_range": f"{void['price_from']:.2f} → {void['price_to']:.2f}",
                                "severity": void["severity"],
                                "distance_pct": distance_pct,
                                "executed_actions": executed_actions,
                                "recommendation": "Position closed" if "full_close" in executed_actions else \
                                                 "Partial exit taken" if "partial_exit" in executed_actions else \
                                                 "Consider partial exit before void"
                            })
            
        except Exception as e:
            logger.debug(f"Liquidity void check failed for {rule.symbol}: {e}")
        
        return actions
    
    def is_shadow_mode_active(self) -> bool:
        """Check if shadow mode is currently active"""
        if not self.shadow_mode_enabled:
            return False
        
        if self.shadow_mode_end_date is None:
            return False
        
        return datetime.now() < self.shadow_mode_end_date
    
    def get_shadow_mode_status(self) -> Dict[str, Any]:
        """Get current shadow mode status and statistics"""
        if not self.shadow_mode_enabled:
            return {
                "enabled": False,
                "message": "Shadow mode is disabled"
            }
        
        if not self.is_shadow_mode_active():
            return {
                "enabled": True,
                "active": False,
                "message": f"Shadow mode period ended on {self.shadow_mode_end_date.strftime('%Y-%m-%d %H:%M:%S')}"
            }
        
        remaining_days = (self.shadow_mode_end_date - datetime.now()).days
        return {
            "enabled": True,
            "active": True,
            "start_date": self.shadow_mode_start_date.isoformat() if self.shadow_mode_start_date else None,
            "end_date": self.shadow_mode_end_date.isoformat() if self.shadow_mode_end_date else None,
            "remaining_days": remaining_days,
            "message": f"Shadow mode active - {remaining_days} days remaining"
        }
    
    def enable_shadow_mode(self, duration_days: int = 14) -> bool:
        """Enable shadow mode for specified duration"""
        try:
            self.shadow_mode_enabled = True
            self.shadow_mode_duration_days = duration_days
            self.shadow_mode_start_date = datetime.now()
            self.shadow_mode_end_date = self.shadow_mode_start_date + timedelta(days=duration_days)
            
            logger.info(f"🔍 Shadow Mode ENABLED - Duration: {duration_days} days")
            logger.info(f"   Start: {self.shadow_mode_start_date.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"   End: {self.shadow_mode_end_date.strftime('%Y-%m-%d %H:%M:%S')}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to enable shadow mode: {e}")
            return False
    
    def disable_shadow_mode(self) -> bool:
        """Disable shadow mode immediately"""
        try:
            self.shadow_mode_enabled = False
            self.shadow_mode_start_date = None
            self.shadow_mode_end_date = None
            
            logger.info("📊 Shadow Mode DISABLED - Returning to standard intelligent exit mode")
            return True
        except Exception as e:
            logger.error(f"Failed to disable shadow mode: {e}")
            return False
    
    def log_decision_trace(
        self,
        ticket: int,
        symbol: str,
        decision_type: str,
        feature_vector: Dict[str, Any],
        decision_result: Dict[str, Any],
        reasoning: str = ""
    ) -> None:
        """
        Log full decision traces with feature vector hashes for error analysis.
        
        This provides comprehensive logging for debugging and performance analysis.
        """
        try:
            import hashlib
            import json
            
            # Create feature vector hash for quick lookup
            feature_json = json.dumps(feature_vector, sort_keys=True, default=str)
            feature_hash = hashlib.sha256(feature_json.encode()).hexdigest()[:16]
            
            # Create decision trace
            decision_trace = {
                "timestamp": datetime.now().isoformat(),
                "ticket": ticket,
                "symbol": symbol,
                "decision_type": decision_type,
                "feature_vector": feature_vector,
                "feature_hash": feature_hash,
                "decision_result": decision_result,
                "reasoning": reasoning,
                "shadow_mode_active": self.is_shadow_mode_active()
            }
            
            # Log to database if available
            if self.db_logger:
                try:
                    self.db_logger.log_action(
                        ticket=ticket,
                        symbol=symbol,
                        action_type="decision_trace",
                        details=decision_trace,
                        success=True
                    )
                except Exception as e:
                    logger.warning(f"Failed to log decision trace to database: {e}")
            
            # Log to console with hash for quick reference
            logger.debug(
                f"Decision Trace [{feature_hash}]: {decision_type} for {symbol} (ticket {ticket}) - "
                f"Result: {decision_result.get('action', 'none')} | Reasoning: {reasoning}"
            )
            
        except Exception as e:
            logger.error(f"Failed to log decision trace: {e}")
    
    def transition_weekend_trades_to_weekday(self):
        """
        Transition open weekend trades to weekday exit parameters.
        Called when weekend ends (Mon 03:00 UTC).
        """
        from infra.weekend_profile_manager import WeekendProfileManager
        from datetime import timezone
        
        weekend_manager = WeekendProfileManager()
        
        # Check if weekend just ended (not just "is ended")
        # Track last transition check to avoid re-transitioning
        current_time = datetime.now(timezone.utc)
        last_check = getattr(self, '_last_weekend_transition_check', None)
        
        # Only transition if:
        # 1. Weekend is not active now
        # 2. Last check was during weekend (or never checked)
        # 3. At least 1 hour has passed since last check (avoid multiple transitions)
        should_transition = False
        if not weekend_manager.is_weekend_active():
            if last_check is None:
                # First check - if weekend not active, check if we just started (not transition needed)
                should_transition = False  # Don't transition on first startup if not weekend
            else:
                # Check if last check was during weekend
                if hasattr(weekend_manager, 'is_weekend_active_at_time'):
                    was_weekend = weekend_manager.is_weekend_active_at_time(last_check)
                else:
                    # Fallback: assume weekend if last check was Fri 23:00+ or Sat/Sun
                    last_check_weekday = last_check.weekday()
                    last_check_hour = last_check.hour
                    was_weekend = (
                        (last_check_weekday == 4 and last_check_hour >= 23) or  # Fri 23:00+
                        last_check_weekday == 5 or  # Saturday
                        last_check_weekday == 6 or  # Sunday
                        (last_check_weekday == 0 and last_check_hour < 3)  # Mon < 03:00
                    )
                
                if was_weekend:
                    # Last check was during weekend, now it's not - weekend just ended
                    time_since_check = (current_time - last_check).total_seconds()
                    if time_since_check >= 3600:  # At least 1 hour since last check
                        should_transition = True
        
        if should_transition:
            # Weekend just ended - transition trades
            transitioned_count = 0
            with self.rules_lock:
                for ticket, rule in list(self.rules.items()):
                    # Check if trade was classified as WEEKEND
                    original_type = getattr(rule, 'original_trade_type', None)
                    if original_type == "WEEKEND":
                        # Reclassify as SCALP or INTRADAY based on current conditions
                        from infra.trade_type_classifier import TradeTypeClassifier
                        classifier = TradeTypeClassifier(self.mt5)
                        
                        # Get current position info
                        try:
                            positions = mt5.positions_get(ticket=ticket)
                            if positions and len(positions) > 0:
                                position = positions[0]
                                classification = classifier.classify(
                                    symbol=rule.symbol,
                                    entry_price=rule.entry_price,
                                    stop_loss=position.sl,
                                    comment=getattr(rule, 'comment', ''),
                                    is_weekend=False  # Now weekday
                                )
                                
                                # Update exit parameters based on new classification
                                if classification["trade_type"] == "SCALP":
                                    rule.breakeven_profit_pct = 25.0
                                    rule.partial_profit_pct = 40.0
                                    rule.partial_close_pct = 70.0
                                    rule.trailing_multiplier = 0.7
                                    rule.vix_threshold = 18.0
                                else:  # INTRADAY
                                    rule.breakeven_profit_pct = 30.0
                                    rule.partial_profit_pct = 60.0
                                    rule.partial_close_pct = 50.0
                                    rule.trailing_multiplier = 1.0
                                    rule.vix_threshold = 18.0
                                
                                # Update original_trade_type to new classification
                                rule.original_trade_type = classification["trade_type"]
                                
                                transitioned_count += 1
                                logger.info(
                                    f"🔄 Transitioned weekend trade {ticket} ({rule.symbol}) to {classification['trade_type']} "
                                    f"parameters: BE={rule.breakeven_profit_pct}%, Partial={rule.partial_profit_pct}%"
                                )
                        except Exception as e:
                            logger.warning(f"Error transitioning weekend trade {ticket}: {e}")
            
            # Save updated rules
            if transitioned_count > 0:
                self._save_rules()
                logger.info(f"✅ Transitioned {transitioned_count} weekend trade(s) to weekday parameters")
        
        # Update last check time
        self._last_weekend_transition_check = current_time
    
    # Phase 3.1: Order Flow Flip Exit Methods
    def _check_order_flow_flip(
        self, 
        ticket: int, 
        rule: ExitRule, 
        position: Any
    ) -> Optional[Dict]:
        """
        Check if order flow has flipped (≥80% reversal).
        
        Phase 3.1: Detects when order flow has reversed significantly from entry,
        indicating potential trend reversal and exit signal.
        
        Args:
            ticket: Position ticket
            rule: ExitRule for position
            position: MT5 position object
        
        Returns:
            Dict with flip details or None if no flip
        """
        try:
            # Get entry delta (stored when position opened)
            entry_delta = rule.metadata.get("entry_delta") if hasattr(rule, 'metadata') else None
            
            # Fallback: Use advanced_gate field if metadata not available
            if entry_delta is None:
                entry_delta = rule.advanced_gate.get("entry_delta") if hasattr(rule, 'advanced_gate') else None
            
            if entry_delta is None:
                return None  # No entry delta stored
            
            # Get current delta
            symbol = position.symbol if hasattr(position, 'symbol') else rule.symbol
            binance_symbol = self._convert_to_binance_symbol(symbol)
            
            if not binance_symbol:
                return None
            
            # Get current order flow pressure
            if not self.order_flow_service or not hasattr(self.order_flow_service, 'get_buy_sell_pressure'):
                return None
            
            pressure_data = self.order_flow_service.get_buy_sell_pressure(
                binance_symbol, window=30
            )
            if not pressure_data:
                return None
            
            current_delta = pressure_data.get("net_volume", 0)
            
            # Calculate flip percentage
            direction = position.type if hasattr(position, 'type') else (0 if rule.direction.lower() == "buy" else 1)
            
            if direction == 0:  # BUY position
                # Exit if delta flips negative ≥80% of entry delta
                if entry_delta > 0:
                    flip_threshold = -0.8 * entry_delta
                    if current_delta <= flip_threshold:
                        flip_pct = abs((current_delta - entry_delta) / entry_delta) * 100
                        return {
                            "flip_detected": True,
                            "entry_delta": entry_delta,
                            "current_delta": current_delta,
                            "flip_percentage": flip_pct,
                            "threshold": 80.0,
                            "direction": "BUY"
                        }
            else:  # SELL position
                # Exit if delta flips positive ≥80% of entry delta
                if entry_delta < 0:
                    flip_threshold = 0.8 * abs(entry_delta)
                    if current_delta >= flip_threshold:
                        flip_pct = abs((current_delta - entry_delta) / abs(entry_delta)) * 100
                        return {
                            "flip_detected": True,
                            "entry_delta": entry_delta,
                            "current_delta": current_delta,
                            "flip_percentage": flip_pct,
                            "threshold": 80.0,
                            "direction": "SELL"
                        }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error checking order flow flip for ticket {ticket}: {e}")
            return None
    
    def _convert_to_binance_symbol(self, mt5_symbol: str) -> Optional[str]:
        """
        Convert MT5 symbol to Binance symbol.
        
        Phase 3.1: Converts MT5 symbol format to Binance format for order flow queries.
        
        Args:
            mt5_symbol: MT5 symbol (e.g., "BTCUSDc")
        
        Returns:
            Binance symbol (e.g., "BTCUSDT") or None if not available
        """
        symbol_map = {
            "BTCUSDc": "BTCUSDT",
            "BTCUSDC": "BTCUSDT",  # Uppercase variant
            "XAUUSDc": None,  # Not available on Binance
            "XAUUSDC": None,  # Not available on Binance
            "EURUSDc": None,  # Not available on Binance
            "EURUSDC": None  # Not available on Binance
        }
        
        # Try exact match first
        if mt5_symbol in symbol_map:
            return symbol_map[mt5_symbol]
        
        # Try case-insensitive match
        symbol_upper = mt5_symbol.upper()
        if symbol_upper in symbol_map:
            return symbol_map[symbol_upper]
        
        # Try pattern matching for BTC
        if symbol_upper.startswith("BTC") and "USD" in symbol_upper:
            return "BTCUSDT"
        
        return None


def create_exit_manager(
    mt5_service,
    binance_service=None,
    order_flow_service=None,
    storage_file: str = "data/intelligent_exits.json",
    check_interval: int = 30,
    advanced_provider=None,
    shadow_mode_enabled: bool = False,
    shadow_mode_duration_days: int = 14,
    db_logger=None
) -> IntelligentExitManager:
    """Factory: IntelligentExitManager with optional integrations.

    Parameters:
      - advanced_provider: object exposing either get_advanced_features(symbol)
        or get_multi(symbol) to refresh Advanced gates live each cycle.
    """
    mgr = IntelligentExitManager(
        mt5_service,
        storage_file=storage_file,
        check_interval=check_interval,
        binance_service=binance_service,
        order_flow_service=order_flow_service,
        shadow_mode_enabled=shadow_mode_enabled,
        shadow_mode_duration_days=shadow_mode_duration_days
    )
    
    # Set db_logger manually if provided
    if db_logger is not None:
        mgr.db_logger = db_logger
    if advanced_provider is not None:
        try:
            setattr(mgr, "advanced_provider", advanced_provider)
        except Exception:
            pass
    return mgr
    
    # Phase 3.1: Order Flow Flip Exit Methods
    def _check_order_flow_flip(
        self, 
        ticket: int, 
        rule: ExitRule, 
        position: Any
    ) -> Optional[Dict]:
        """
        Check if order flow has flipped (≥80% reversal).
        
        Phase 3.1: Detects when order flow has reversed significantly from entry,
        indicating potential trend reversal and exit signal.
        
        Args:
            ticket: Position ticket
            rule: ExitRule for position
            position: MT5 position object
        
        Returns:
            Dict with flip details or None if no flip
        """
        try:
            # Get entry delta (stored when position opened)
            entry_delta = rule.metadata.get("entry_delta") if hasattr(rule, 'metadata') else None
            
            # Fallback: Use advanced_gate field if metadata not available
            if entry_delta is None:
                entry_delta = rule.advanced_gate.get("entry_delta") if hasattr(rule, 'advanced_gate') else None
            
            if entry_delta is None:
                return None  # No entry delta stored
            
            # Get current delta
            symbol = position.symbol if hasattr(position, 'symbol') else rule.symbol
            binance_symbol = self._convert_to_binance_symbol(symbol)
            
            if not binance_symbol:
                return None
            
            # Get current order flow pressure
            if not self.order_flow_service or not hasattr(self.order_flow_service, 'get_buy_sell_pressure'):
                return None
            
            pressure_data = self.order_flow_service.get_buy_sell_pressure(
                binance_symbol, window=30
            )
            if not pressure_data:
                return None
            
            current_delta = pressure_data.get("net_volume", 0)
            
            # Calculate flip percentage
            direction = position.type if hasattr(position, 'type') else (0 if rule.direction.lower() == "buy" else 1)
            
            if direction == 0:  # BUY position
                # Exit if delta flips negative ≥80% of entry delta
                if entry_delta > 0:
                    flip_threshold = -0.8 * entry_delta
                    if current_delta <= flip_threshold:
                        flip_pct = abs((current_delta - entry_delta) / entry_delta) * 100
                        return {
                            "flip_detected": True,
                            "entry_delta": entry_delta,
                            "current_delta": current_delta,
                            "flip_percentage": flip_pct,
                            "threshold": 80.0,
                            "direction": "BUY"
                        }
            else:  # SELL position
                # Exit if delta flips positive ≥80% of entry delta
                if entry_delta < 0:
                    flip_threshold = 0.8 * abs(entry_delta)
                    if current_delta >= flip_threshold:
                        flip_pct = abs((current_delta - entry_delta) / abs(entry_delta)) * 100
                        return {
                            "flip_detected": True,
                            "entry_delta": entry_delta,
                            "current_delta": current_delta,
                            "flip_percentage": flip_pct,
                            "threshold": 80.0,
                            "direction": "SELL"
                        }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error checking order flow flip for ticket {ticket}: {e}")
            return None
    
    def _convert_to_binance_symbol(self, mt5_symbol: str) -> Optional[str]:
        """
        Convert MT5 symbol to Binance symbol.
        
        Phase 3.1: Converts MT5 symbol format to Binance format for order flow queries.
        
        Args:
            mt5_symbol: MT5 symbol (e.g., "BTCUSDc")
        
        Returns:
            Binance symbol (e.g., "BTCUSDT") or None if not available
        """
        symbol_map = {
            "BTCUSDc": "BTCUSDT",
            "BTCUSDC": "BTCUSDT",  # Uppercase variant
            "XAUUSDc": None,  # Not available on Binance
            "XAUUSDC": None,  # Not available on Binance
            "EURUSDc": None,  # Not available on Binance
            "EURUSDC": None  # Not available on Binance
        }
        
        # Try exact match first
        if mt5_symbol in symbol_map:
            return symbol_map[mt5_symbol]
        
        # Try case-insensitive match
        symbol_upper = mt5_symbol.upper()
        if symbol_upper in symbol_map:
            return symbol_map[symbol_upper]
        
        # Try pattern matching for BTC
        if symbol_upper.startswith("BTC") and "USD" in symbol_upper:
            return "BTCUSDT"
        
        return None

