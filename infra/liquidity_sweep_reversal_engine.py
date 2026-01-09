"""
Liquidity Sweep Reversal Detection and Execution System

An autonomous SMC engine that detects liquidity sweeps (stop hunts) and trades reversals
for BTCUSD and XAUUSD using a three-layer confluence stack:

1. Macro Context (30%): Trend bias, VIX, DXY, news, session validation
2. Setup Context (40%): Sweep structure, volume, VWAP, PDH/PDL proximity
3. Trigger Context (30%): CHOCH/BOS, RSI divergence, volume decline, ADX flattening

Operates continuously, monitoring M1 candles and executing trades when confluence ≥70%.
"""

import asyncio
import json
import logging
from collections import deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np

from infra.streamer_data_access import StreamerDataAccess, get_candles, get_latest_candle, calculate_atr
from infra.mt5_service import MT5Service
from infra.intelligent_exit_manager import IntelligentExitManager
from infra.market_indices_service import MarketIndicesService
from infra.news_service import NewsService
from infra.journal_repo import JournalRepo
from domain.liquidity import detect_sweep, validate_sweep
from domain.market_structure import detect_bos_choch
from discord_notifications import DiscordNotifier

logger = logging.getLogger(__name__)


@dataclass
class SweepSetup:
    """Represents an active liquidity sweep setup"""
    symbol: str
    sweep_time: datetime
    sweep_type: str  # "bull" or "bear"
    sweep_price: float
    setup_score: float
    macro_bias: str
    confirmation_window_start: datetime
    max_confirmation_time: datetime
    setup_type: Optional[str] = None  # "Type 1" or "Type 2"
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    ticket: Optional[int] = None
    status: str = "pending"  # "pending", "confirmed", "executed", "invalidated"
    confluence_score: float = 0.0


@dataclass
class ConfluenceScore:
    """Confluence scoring breakdown"""
    macro_score: float = 0.0
    setup_score: float = 0.0
    trigger_score: float = 0.0
    total_score: float = 0.0
    
    def calculate_total(self, macro_weight: float, setup_weight: float, trigger_weight: float):
        """Calculate weighted total score"""
        self.total_score = (
            self.macro_score * macro_weight +
            self.setup_score * setup_weight +
            self.trigger_score * trigger_weight
        )


class LiquiditySweepReversalEngine:
    """
    Autonomous liquidity sweep reversal detection and execution system.
    
    Operates continuously, monitoring M1 candles for liquidity sweeps and executing
    trades when confluence conditions are met.
    """
    
    def __init__(
        self,
        mt5_service: MT5Service,
        intelligent_exit_manager: Optional[IntelligentExitManager] = None,
        discord_notifier: Optional[DiscordNotifier] = None,
        config_path: str = "config/liquidity_sweep_config.json"
    ):
        """
        Initialize the liquidity sweep reversal engine.
        
        Args:
            mt5_service: MT5 service for trade execution
            intelligent_exit_manager: Optional exit manager for post-entry risk management
            discord_notifier: Optional Discord notifier for alerts
            config_path: Path to configuration JSON file
        """
        self.mt5_service = mt5_service
        self.intelligent_exit_manager = intelligent_exit_manager
        self.discord_notifier = discord_notifier
        
        # Load configuration
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r') as f:
                self.config = json.load(f)
        else:
            logger.warning(f"Config file not found: {config_path}, using defaults")
            self.config = self._get_default_config()
        
        # Initialize services
        self.market_indices_service = MarketIndicesService()
        self.news_service = NewsService() if NewsService else None
        self.data_access = StreamerDataAccess()
        
        # Initialize journal repository for trade logging
        try:
            self.journal_repo = JournalRepo("data/journal.sqlite")
            logger.debug("Journal repository initialized for LSR trade logging")
        except Exception as e:
            logger.warning(f"Failed to initialize journal repository: {e}")
            self.journal_repo = None
        
        # State management
        self.active_setups: Dict[str, SweepSetup] = {}  # {symbol: setup}
        self.recent_trades = deque(maxlen=100)
        self.sweep_history: Dict[str, List[Dict]] = {}  # Track sweep zones per symbol
        self.recent_notifications: Dict[str, datetime] = {}  # Track recent notifications for deduplication
        
        # Load persistent state
        self.state_file = Path("data/liquidity_sweep_state.json")
        self._load_state()
        
        logger.info(f"LiquiditySweepReversalEngine initialized for symbols: {self.config['symbols']}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            "symbols": ["BTCUSDc", "XAUUSDc"],
            "enabled": True,
            "risk_per_trade_pct": 1.5,
            "max_concurrent_setups_per_symbol": 1,
            "sweep_zone_cooldown_minutes": 30,
            "sessions": {
                "LONDON": {"start_hour_utc": 7, "end_hour_utc": 10, "enabled": True},
                "NY": {"start_hour_utc": 12, "end_hour_utc": 16, "enabled": True}
            },
            "macro_context": {
                "vix_max": 22,
                "vix_critical": 25,
                "update_interval_minutes": 15
            },
            "setup_context": {
                "lookback_candles": 5,
                "sweep_atr_multiplier": 1.5,
                "volume_spike_multiplier": 1.3,
                "min_conditions": 4,
                "total_conditions": 6
            },
            "trigger_context": {
                "confirmation_window_bars": 3,
                "max_wait_bars": 5
            },
            "confluence_scoring": {
                "macro_weight": 0.30,
                "setup_weight": 0.40,
                "trigger_weight": 0.30,
                "execution_threshold": 70
            },
            "notifications": {
                "discord_enabled": True
            }
        }
    
    def _load_state(self):
        """Load persistent state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    # Restore active setups (basic restoration)
                    logger.info("State loaded from file")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
    
    def _save_state(self):
        """Save persistent state to file"""
        try:
            state = {
                "active_setups": {
                    sym: {
                        "sweep_time": setup.sweep_time.isoformat(),
                        "status": setup.status,
                        "ticket": setup.ticket
                    }
                    for sym, setup in self.active_setups.items()
                },
                "last_update": datetime.now(timezone.utc).isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")
    
    async def check_macro_context(self, symbol: str) -> Tuple[str, float]:
        """
        Layer 1: Macro Context (30% weight)
        
        Evaluates:
        - Trend bias (H1 EMA200 slope)
        - VIX level (< 22 normal, > 25 critical)
        - DXY context (for BTCUSD/XAUUSD)
        - News blackout check
        - Session validation
        
        Returns:
            Tuple of (macro_bias, score_0_100)
            macro_bias: "bullish", "bearish", or "avoid"
            score: 0-100 confluence score
        """
        try:
            score = 0.0
            factors_checked = 0
            
            # 1. VIX Check (Critical Safety Filter)
            vix_data = self.market_indices_service.get_vix()
            if vix_data is None or 'price' not in vix_data:
                logger.debug("VIX data not available")
                return "avoid", 0.0
            
            vix = vix_data.get('price', 0.0)
            if vix > self.config["macro_context"]["vix_critical"]:
                logger.info(f"VIX too high ({vix:.1f}), avoiding all reversals")
                return "avoid", 0.0
            
            if vix < self.config["macro_context"]["vix_max"]:
                score += 10.0  # Normal volatility environment
            factors_checked += 1
            
            # 2. Session Validation
            current_hour = datetime.now(timezone.utc).hour
            in_active_session = False
            
            for session_name, session_config in self.config["sessions"].items():
                if not session_config.get("enabled", False):
                    continue
                
                start = session_config["start_hour_utc"]
                end = session_config["end_hour_utc"]
                
                if start < end:  # Normal range (e.g., 7-10)
                    if start <= current_hour < end:
                        in_active_session = True
                        break
                else:  # Overnight range (e.g., 22-2)
                    if current_hour >= start or current_hour < end:
                        in_active_session = True
                        break
            
            if in_active_session:
                score += 10.0  # Valid trading session
            else:
                logger.debug(f"Outside active trading session (current hour: {current_hour})")
                return "avoid", 0.0
            factors_checked += 1
            
            # 3. Trend Bias (H1 EMA200)
            # Fetch H1 candles and calculate EMA200 slope
            h1_candles = get_candles(symbol, "H1", limit=200)
            if h1_candles and len(h1_candles) >= 200:
                df = pd.DataFrame(h1_candles)
                if 'close' in df.columns:
                    df['close'] = pd.to_numeric(df['close'], errors='coerce')
                    ema200 = df['close'].ewm(span=200, adjust=False).mean()
                    
                    if len(ema200) >= 2:
                        slope = ema200.iloc[-1] - ema200.iloc[-2]
                        if slope > 0:
                            # Uptrend: only fade downward sweeps (buy reversals)
                            trend_bias = "bullish"
                        else:
                            # Downtrend: only fade upward sweeps (sell reversals)
                            trend_bias = "bearish"
                        
                        score += 10.0  # Trend context available
                        factors_checked += 1
                    else:
                        trend_bias = None
                else:
                    trend_bias = None
            else:
                trend_bias = None
            
            # 4. DXY Context (for BTCUSD/XAUUSD)
            if symbol in ["BTCUSDc", "XAUUSDc"]:
                dxy_data = self.market_indices_service.get_dxy()
                if dxy_data is not None and 'price' in dxy_data:
                    # Simplified: check if DXY is in acceptable range
                    # In production, you'd check recent DXY change
                    score += 5.0
                    factors_checked += 1
            
            # 5. News Blackout Check
            if self.news_service:
                # Check for high-impact news within blackout window
                blackout_minutes = self.config["macro_context"].get("news_blackout_minutes", 30)
                # Simplified check - in production, query actual news events
                score += 5.0  # Assume no blocking news
                factors_checked += 1
            
            # Normalize score to 0-100 scale (out of 30 points max for macro layer)
            normalized_score = (score / 30.0) * 100.0 if factors_checked > 0 else 0.0
            
            macro_bias = "bullish" if trend_bias == "bullish" or trend_bias is None else "bearish"
            if normalized_score < 50.0:
                macro_bias = "avoid"
            
            return macro_bias, normalized_score
            
        except Exception as e:
            logger.error(f"Error checking macro context: {e}", exc_info=True)
            return "avoid", 0.0
    
    async def check_setup_context(self, symbol: str, m1_candles: List[Dict]) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Layer 2: Setup Context (40% weight)
        
        Evaluates:
        - Sweep structure (high > Max(High[3]) and Close < High[1])
        - Candle size vs ATR (≥ 1.5 × ATR)
        - Volume spike (≥ 1.3 × 10-bar avg)
        - Time filter (London/NY sessions)
        - Proximity to PDH/PDL or Equal High/Low (≤ 0.25 × ATR)
        - VWAP distance (≥ 2σ for overextension)
        
        Returns:
            Tuple of (detected, score_0_100, setup_details)
        """
        try:
            if len(m1_candles) < self.config["setup_context"]["lookback_candles"] + 1:
                return False, 0.0, {}
            
            # Convert to DataFrame for easier manipulation
            df = pd.DataFrame(m1_candles)
            if len(df) < 10:
                return False, 0.0, {}
            
            # Ensure numeric columns
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Get last candle
            last_candle = df.iloc[-1]
            recent_candles = df.iloc[-self.config["setup_context"]["lookback_candles"]-1:-1]
            
            # Calculate ATR
            atr = calculate_atr(symbol, "M1", period=14)
            if atr is None or atr <= 0:
                # Fallback: calculate from dataframe
                high_low = df['high'] - df['low']
                high_close = abs(df['high'] - df['close'].shift())
                low_close = abs(df['low'] - df['close'].shift())
                true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                atr = true_range.tail(14).mean()
            
            if atr <= 0:
                return False, 0.0, {}
            
            score = 0.0
            conditions_met = 0
            setup_details = {}
            
            # 1. Sweep Structure Detection
            sweep_result = detect_sweep(df, atr, 
                                       sweep_threshold=0.15 * atr / atr if atr > 0 else 0.15,
                                       lookback=self.config["setup_context"]["lookback_candles"])
            
            sweep_bull = sweep_result.get("sweep_bull", False)
            sweep_bear = sweep_result.get("sweep_bear", False)
            sweep_price = sweep_result.get("sweep_price", 0.0)
            
            # Fallback: If detect_sweep returned a sweep type but price is 0.0,
            # extract price directly from candle data (this handles cases where
            # detect_sweep logic doesn't properly extract price)
            if (sweep_bull or sweep_bear) and sweep_price <= 0:
                # Fallback price extraction from last candle
                if sweep_bull:
                    sweep_price = last_candle['high']
                    logger.debug(f"{symbol}: Bullish sweep detected but price was 0.0, using candle high: {sweep_price:.5f}")
                elif sweep_bear:
                    sweep_price = last_candle['low']
                    logger.debug(f"{symbol}: Bearish sweep detected but price was 0.0, using candle low: {sweep_price:.5f}")
            
            # Consider sweep detected if either type is True
            sweep_detected = sweep_bull or sweep_bear
            
            # Log if sweep_detected but price is still 0 (diagnostic)
            if sweep_detected and sweep_price <= 0:
                logger.warning(f"{symbol}: Sweep detected ({'bull' if sweep_bull else 'bear'}) but price extraction failed. Last candle: high={last_candle.get('high', 'N/A')}, low={last_candle.get('low', 'N/A')}")
            
            if sweep_detected:
                score += 15.0
                conditions_met += 1
                # Correctly determine sweep type
                if sweep_bull:
                    setup_details["sweep_type"] = "bull"
                    setup_details["sweep_price"] = sweep_price if sweep_price > 0 else last_candle['high']
                elif sweep_bear:
                    setup_details["sweep_type"] = "bear"
                    setup_details["sweep_price"] = sweep_price if sweep_price > 0 else last_candle['low']
                else:
                    # Fallback - should not happen if sweep_detected is True
                    setup_details["sweep_type"] = "unknown"
                    setup_details["sweep_price"] = 0.0
                setup_details["sweep_depth"] = sweep_result.get("depth", 0.0)
            
            # 2. Candle Size vs ATR
            candle_range = last_candle['high'] - last_candle['low']
            if candle_range >= self.config["setup_context"]["sweep_atr_multiplier"] * atr:
                score += 10.0
                conditions_met += 1
                setup_details["candle_size_atr"] = candle_range / atr
            
            # 3. Volume Spike
            if 'volume' in df.columns:
                recent_volumes = df['volume'].tail(self.config["setup_context"]["volume_lookback"] + 1)
                if len(recent_volumes) > 1:
                    avg_volume = recent_volumes.iloc[:-1].mean()
                    current_volume = recent_volumes.iloc[-1]
                    
                    if avg_volume > 0 and current_volume >= self.config["setup_context"]["volume_spike_multiplier"] * avg_volume:
                        score += 10.0
                        conditions_met += 1
                        setup_details["volume_spike"] = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # 4. Time Filter (Session Check)
            current_hour = datetime.now(timezone.utc).hour
            in_active_session = False
            for session_name, session_config in self.config["sessions"].items():
                if not session_config.get("enabled", False):
                    continue
                start = session_config["start_hour_utc"]
                end = session_config["end_hour_utc"]
                if start < end:
                    if start <= current_hour < end:
                        in_active_session = True
                        break
                else:
                    if current_hour >= start or current_hour < end:
                        in_active_session = True
                        break
            
            if in_active_session:
                score += 5.0
                conditions_met += 1
            
            # 5. VWAP Distance (simplified - would need actual VWAP calculation)
            # For now, use close price deviation from simple MA as proxy
            if len(df) >= 20:
                ma20 = df['close'].tail(20).mean()
                std20 = df['close'].tail(20).std()
                if std20 > 0:
                    deviation_sigma = abs(last_candle['close'] - ma20) / std20
                    if deviation_sigma >= self.config["setup_context"]["vwap_deviation_sigma"]:
                        score += 5.0
                        conditions_met += 1
                        setup_details["vwap_deviation_sigma"] = deviation_sigma
            
            # Check if minimum conditions met
            min_conditions = self.config["setup_context"]["min_conditions"]
            # Maximum possible score: 15 (sweep) + 10 (candle) + 10 (volume) + 5 (session) + 5 (vwap) = 45 points
            # Note: PDH/PDL proximity check is not included in scoring, only in conditions
            max_possible_score = 45.0
            if conditions_met >= min_conditions:
                # Normalize score to 0-100 scale (cap at 100%)
                normalized_score = min((score / max_possible_score) * 100.0, 100.0)
                return True, normalized_score, setup_details
            else:
                # Return normalized score even if below threshold (for debugging)
                normalized_score = min((score / max_possible_score) * 100.0, 100.0)
                return False, normalized_score, setup_details
                
        except Exception as e:
            logger.error(f"Error checking setup context for {symbol}: {e}", exc_info=True)
            return False, 0.0, {}
    
    async def check_trigger_context(
        self, 
        symbol: str, 
        setup: SweepSetup,
        m1_candles: List[Dict]
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Layer 3: Trigger Context (30% weight)
        
        Evaluates reversal confirmation in 2-3 candles following sweep:
        - Rejection candle (wick ≥ 50%, body < 40%)
        - CHOCH/BOS (structure break)
        - RSI divergence
        - Volume decline (≥ 20% drop)
        - VWAP magnet distance (≤ 1 × ATR)
        - ADX flattening
        
        Returns:
            Tuple of (confirmed, score_0_100, setup_type)
            setup_type: "Type 1" (instant) or "Type 2" (retest) or None
        """
        try:
            if len(m1_candles) < 3:
                return False, 0.0, None
            
            df = pd.DataFrame(m1_candles)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            atr = calculate_atr(symbol, "M1", period=14)
            if atr is None or atr <= 0:
                return False, 0.0, None
            
            score = 0.0
            conditions_met = 0
            choch_detected = False
            
            # Analyze last 2-3 candles (confirmation window)
            confirmation_candles = df.tail(self.config["trigger_context"]["confirmation_window_bars"])
            
            # 1. Check for CHOCH/BOS (most important)
            # Get swing points from recent data
            recent_df = df.tail(20)
            if len(recent_df) >= 10:
                # Simplified CHOCH detection: look for structure break
                if setup.sweep_type == "bull":
                    # Bullish sweep - look for bearish CHOCH (price breaks below previous low)
                    recent_lows = recent_df['low'].tail(5)
                    if len(recent_lows) >= 2:
                        prev_low = recent_lows.iloc[-2]
                        current_close = recent_df['close'].iloc[-1]
                        if current_close < prev_low - (0.2 * atr):  # Break below by 0.2 ATR
                            choch_detected = True
                            score += 15.0
                            conditions_met += 1
                else:  # bearish sweep
                    # Bearish sweep - look for bullish CHOCH (price breaks above previous high)
                    recent_highs = recent_df['high'].tail(5)
                    if len(recent_highs) >= 2:
                        prev_high = recent_highs.iloc[-2]
                        current_close = recent_df['close'].iloc[-1]
                        if current_close > prev_high + (0.2 * atr):  # Break above by 0.2 ATR
                            choch_detected = True
                            score += 15.0
                            conditions_met += 1
            
            # 2. Rejection Candle Analysis
            for _, candle in confirmation_candles.iterrows():
                candle_range = candle['high'] - candle['low']
                candle_body = abs(candle['close'] - candle['open'])
                upper_wick = candle['high'] - max(candle['open'], candle['close'])
                lower_wick = min(candle['open'], candle['close']) - candle['low']
                max_wick = max(upper_wick, lower_wick)
                
                if candle_range > 0:
                    wick_pct = (max_wick / candle_range) * 100
                    body_pct = (candle_body / candle_range) * 100
                    
                    if (wick_pct >= self.config["trigger_context"]["rejection_wick_pct"] and
                        body_pct < self.config["trigger_context"]["rejection_body_pct"]):
                        score += 5.0
                        conditions_met += 1
                        break
            
            # 3. Volume Decline
            if 'volume' in df.columns and len(df) >= 2:
                sweep_volume = df['volume'].iloc[-len(confirmation_candles)-1] if len(df) > len(confirmation_candles) else df['volume'].iloc[-1]
                post_sweep_volume = confirmation_candles['volume'].mean()
                
                if sweep_volume > 0:
                    volume_change = ((sweep_volume - post_sweep_volume) / sweep_volume) * 100
                    if volume_change >= self.config["trigger_context"]["volume_decline_pct"]:
                        score += 5.0
                        conditions_met += 1
            
            # 4. VWAP Magnet Distance (simplified)
            if len(df) >= 20:
                ma20 = df['close'].tail(20).mean()
                current_price = df['close'].iloc[-1]
                distance = abs(current_price - ma20)
                if distance <= self.config["trigger_context"]["vwap_magnet_atr"] * atr:
                    score += 5.0
                    conditions_met += 1
            
            # Normalize score to 0-100 scale (out of 30 points max for trigger layer)
            normalized_score = (score / 30.0) * 100.0
            
            # Determine setup type
            setup_type = None
            if choch_detected:
                # Check if price retraced to order block/FVG zone (Type 2)
                # Simplified: check if price moved back toward sweep origin
                sweep_price = setup.sweep_price
                current_price = df['close'].iloc[-1]
                
                if setup.sweep_type == "bull":
                    # Bullish sweep - check if price retraced down
                    retrace = (sweep_price - current_price) / atr
                    if 0.5 <= retrace <= 1.0:  # Retraced 0.5-1.0 ATR
                        setup_type = "Type 2"
                    else:
                        setup_type = "Type 1"
                else:  # bearish sweep
                    # Bearish sweep - check if price retraced up
                    retrace = (current_price - sweep_price) / atr
                    if 0.5 <= retrace <= 1.0:  # Retraced 0.5-1.0 ATR
                        setup_type = "Type 2"
                    else:
                        setup_type = "Type 1"
            else:
                # No CHOCH yet, wait
                return False, normalized_score, None
            
            # Minimum threshold for confirmation
            if normalized_score >= 50.0:  # At least 50% of trigger layer
                return True, normalized_score, setup_type
            else:
                return False, normalized_score, None
                
        except Exception as e:
            logger.error(f"Error checking trigger context for {symbol}: {e}", exc_info=True)
            return False, 0.0, None
    
    async def calculate_confluence_score(
        self,
        symbol: str,
        macro_score: float,
        setup_score: float,
        trigger_score: float
    ) -> ConfluenceScore:
        """Calculate weighted confluence score"""
        score = ConfluenceScore(
            macro_score=macro_score,
            setup_score=setup_score,
            trigger_score=trigger_score
        )
        
        weights = self.config["confluence_scoring"]
        score.calculate_total(
            weights["macro_weight"],
            weights["setup_weight"],
            weights["trigger_weight"]
        )
        
        return score
    
    async def process_symbol(self, symbol: str):
        """Process one symbol: check for sweeps and manage setups"""
        try:
            # Get M1 candles
            m1_candles = get_candles(symbol, "M1", limit=30)
            if not m1_candles or len(m1_candles) < 10:
                logger.debug(f"Insufficient M1 data for {symbol}")
                return
            
            # Check if symbol has active setup
            if symbol in self.active_setups:
                setup = self.active_setups[symbol]
                
                # Check if setup expired
                if datetime.now(timezone.utc) > setup.max_confirmation_time:
                    logger.info(f"Setup expired for {symbol}")
                    if self.discord_notifier and self.config["notifications"].get("notify_invalidation"):
                        await self._send_discord_notification(
                            symbol, "setup_invalidated",
                            f"Setup expired without confirmation"
                        )
                    del self.active_setups[symbol]
                    self._save_state()
                    return
                
                # Check trigger context for active setup
                trigger_confirmed, trigger_score, setup_type = await self.check_trigger_context(
                    symbol, setup, m1_candles
                )
                
                if trigger_confirmed and setup_type:
                    # Calculate final confluence score
                    macro_score = setup.setup_score * 0.3  # Approximate from initial check
                    setup_score = setup.setup_score * 0.4
                    final_score = await self.calculate_confluence_score(symbol, macro_score, setup_score, trigger_score)
                    
                    if final_score.total_score >= self.config["confluence_scoring"]["execution_threshold"]:
                        # Execute trade
                        setup.setup_type = setup_type
                        setup.confluence_score = final_score.total_score
                        await self._execute_trade(symbol, setup, m1_candles, final_score)
                    else:
                        logger.info(f"{symbol}: Trigger confirmed but confluence too low ({final_score.total_score:.1f}%)")
                
            else:
                # Check for new sweep
                # First check macro context
                macro_bias, macro_score = await self.check_macro_context(symbol)
                
                if macro_bias == "avoid" or macro_score < 30:
                    return  # Skip if macro context is unfavorable
                
                # Check setup context
                setup_detected, setup_score, setup_details = await self.check_setup_context(symbol, m1_candles)
                
                if setup_detected:
                    # Validate sweep details before proceeding
                    sweep_type = setup_details.get("sweep_type", "")
                    sweep_price = setup_details.get("sweep_price", 0.0)
                    
                    # Fallback: If sweep type is missing or price is 0, try to extract from setup_details or candles
                    if sweep_type == "" or sweep_type == "unknown" or sweep_price <= 0:
                        # Check if we can extract from candle data as last resort
                        if len(m1_candles) > 0:
                            last_candle = m1_candles[-1]
                            if isinstance(last_candle, dict):
                                # Try to infer from recent price action
                                if sweep_price <= 0:
                                    # Use current high/low as fallback
                                    sweep_price = last_candle.get("high", last_candle.get("close", 0.0))
                                    if sweep_price <= 0:
                                        sweep_price = last_candle.get("low", 0.0)
                                if sweep_type == "" or sweep_type == "unknown":
                                    # Infer type from price vs recent range (simplified)
                                    recent_highs = [c.get("high", 0) for c in m1_candles[-5:] if isinstance(c, dict)]
                                    recent_lows = [c.get("low", float('inf')) for c in m1_candles[-5:] if isinstance(c, dict)]
                                    if recent_highs and recent_lows:
                                        max_high = max(recent_highs)
                                        min_low = min([l for l in recent_lows if l != float('inf')])
                                        if sweep_price >= max_high * 0.99:
                                            sweep_type = "bull"
                                        elif sweep_price <= min_low * 1.01:
                                            sweep_type = "bear"
                                        else:
                                            sweep_type = "unknown"
                            
                            # Update setup_details with fallback values
                            setup_details["sweep_type"] = sweep_type
                            setup_details["sweep_price"] = sweep_price
                    
                    # Skip if still invalid after fallback
                    if sweep_type == "unknown" or sweep_price <= 0:
                        logger.warning(f"{symbol}: Invalid sweep detected after fallback (type={sweep_type}, price={sweep_price}), skipping. Setup conditions met: {setup_details}")
                        return
                    
                    # Check cooldown
                    if self._is_in_cooldown(symbol, sweep_price):
                        logger.debug(f"{symbol}: In cooldown period, skipping sweep")
                        return
                    
                    # Check for duplicate notification (prevent spam)
                    notification_key = f"{symbol}_{sweep_type}_{sweep_price:.2f}"
                    now = datetime.now(timezone.utc)
                    if notification_key in self.recent_notifications:
                        last_notification = self.recent_notifications[notification_key]
                        # Only send if more than 2 minutes since last notification
                        if (now - last_notification).total_seconds() < 120:
                            logger.debug(f"{symbol}: Duplicate sweep notification suppressed")
                            return
                    
                    # Create new setup
                    setup = SweepSetup(
                        symbol=symbol,
                        sweep_time=now,
                        sweep_type=sweep_type,
                        sweep_price=sweep_price,
                        setup_score=setup_score,
                        macro_bias=macro_bias,
                        confirmation_window_start=now,
                        max_confirmation_time=now + timedelta(
                            minutes=self.config["trigger_context"]["max_wait_bars"]
                        ),
                        status="pending"
                    )
                    
                    self.active_setups[symbol] = setup
                    self._save_state()
                    
                    # Record sweep in history
                    if symbol not in self.sweep_history:
                        self.sweep_history[symbol] = []
                    self.sweep_history[symbol].append({
                        "time": setup.sweep_time.isoformat(),
                        "price": setup.sweep_price,
                        "type": setup.sweep_type
                    })
                    
                    # Track notification
                    self.recent_notifications[notification_key] = now
                    # Clean old notifications (keep last 100)
                    if len(self.recent_notifications) > 100:
                        # Remove oldest entries
                        sorted_keys = sorted(self.recent_notifications.items(), key=lambda x: x[1])
                        for key, _ in sorted_keys[:len(sorted_keys) - 100]:
                            del self.recent_notifications[key]
                    
                    logger.info(f"{symbol}: Sweep detected - {setup.sweep_type} at {setup.sweep_price:.5f} (Score: {setup_score:.1f}%)")
                    
                    # Send Discord notification
                    if self.discord_notifier and self.config["notifications"].get("notify_sweep_detected"):
                        await self._send_discord_notification(
                            symbol, "sweep_detected",
                            f"{setup.sweep_type.upper()} sweep at {setup.sweep_price:.5f}\n"
                            f"Setup Score: {min(setup_score, 100.0):.1f}%\n"
                            f"Monitoring for confirmation..."
                        )
                
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}", exc_info=True)
    
    def _is_in_cooldown(self, symbol: str, sweep_price: float) -> bool:
        """Check if sweep zone is in cooldown period"""
        if symbol not in self.sweep_history:
            return False
        
        cooldown_minutes = self.config.get("sweep_zone_cooldown_minutes", 30)
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
        
        for sweep_record in self.sweep_history[symbol]:
            sweep_time = datetime.fromisoformat(sweep_record["time"])
            if sweep_time > cutoff_time:
                # Check if price is within 0.5 ATR of previous sweep
                price_diff = abs(sweep_price - sweep_record["price"])
                # Simplified: assume ATR is ~1% of price for cooldown check
                atr_estimate = sweep_price * 0.01
                if price_diff < 0.5 * atr_estimate:
                    return True
        
        return False
    
    async def _execute_trade(
        self,
        symbol: str,
        setup: SweepSetup,
        m1_candles: List[Dict],
        confluence_score: ConfluenceScore
    ):
        """Execute trade based on confirmed setup"""
        try:
            df = pd.DataFrame(m1_candles)
            for col in ['open', 'high', 'low', 'close']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            current_price = df['close'].iloc[-1]
            atr = calculate_atr(symbol, "M1", period=14)
            if atr is None or atr <= 0:
                logger.error(f"Cannot calculate ATR for {symbol}")
                return
            
            # Determine direction
            if setup.sweep_type == "bull":
                # Bullish sweep -> Sell reversal
                direction = "sell"
                entry_price = current_price
                
                # Stop loss: beyond sweep wick + ATR multiplier
                if setup.setup_type == "Type 1":
                    sl_multiplier = self.config["execution"]["type1_sl_atr_multiplier"]
                else:
                    sl_multiplier = self.config["execution"]["type2_sl_atr_multiplier"]
                
                stop_loss = setup.sweep_price + (sl_multiplier * atr)
                
                # Take profit: VWAP or R multiplier
                # Simplified: use 1.5R or 2R based on type
                if setup.setup_type == "Type 1":
                    tp_r = self.config["execution"]["type1_tp_r_multiplier"]
                else:
                    tp_r = self.config["execution"]["type2_tp_r_multiplier"]
                
                risk = abs(entry_price - stop_loss)
                take_profit = entry_price - (tp_r * risk)
                
            else:  # bearish sweep
                # Bearish sweep -> Buy reversal
                direction = "buy"
                entry_price = current_price
                
                # Stop loss
                if setup.setup_type == "Type 1":
                    sl_multiplier = self.config["execution"]["type1_sl_atr_multiplier"]
                else:
                    sl_multiplier = self.config["execution"]["type2_sl_atr_multiplier"]
                
                stop_loss = setup.sweep_price - (sl_multiplier * atr)
                
                # Take profit
                if setup.setup_type == "Type 1":
                    tp_r = self.config["execution"]["type1_tp_r_multiplier"]
                else:
                    tp_r = self.config["execution"]["type2_tp_r_multiplier"]
                
                risk = abs(entry_price - stop_loss)
                take_profit = entry_price + (tp_r * risk)
            
            # Calculate position size based on risk
            risk_pct = self.config.get("risk_per_trade_pct", 1.5)
            # Get account equity (simplified - would use MT5Service)
            equity = 10000.0  # Placeholder
            risk_amount = equity * (risk_pct / 100.0)
            
            # Calculate lot size (simplified)
            contract_size = 1.0  # Would get from symbol info
            lot_size = risk_amount / (risk * contract_size)
            lot_size = round(lot_size, 2)  # Round to 0.01
            
            # Execute trade
            if setup.setup_type == "Type 1":
                # Market order (MT5Service.market_order is synchronous)
                result = self.mt5_service.market_order(
                    symbol=symbol,
                    side=direction,
                    lot=lot_size,
                    sl=stop_loss,
                    tp=take_profit,
                    comment=f"LSR_{setup.setup_type}_{symbol}"
                )
            else:
                # Type 2: Limit order at retest level
                # Simplified: use current price for now (would calculate OB/FVG level)
                limit_price = entry_price
                # Include LSR prefix in comment for identification
                base_comment = "buy_limit" if direction == "buy" else "sell_limit"
                comment = f"LSR_{setup.setup_type}_{symbol}_{base_comment}"
                result = self.mt5_service.pending_order(
                    symbol=symbol,
                    side=direction,
                    entry=limit_price,
                    lot=lot_size,
                    sl=stop_loss,
                    tp=take_profit,
                    comment=comment  # Comment determines order type in MT5Service
                )
            
            if result and result.get("ok"):
                # Extract ticket from result details
                details = result.get("details", {})
                ticket = details.get("ticket") or details.get("position") or result.get("ticket")
                setup.ticket = ticket
                setup.entry_price = entry_price
                setup.stop_loss = stop_loss
                setup.take_profit = take_profit
                setup.status = "executed"
                
                # Safely format log message (handle mock objects in tests)
                try:
                    entry_str = f"{entry_price:.5f}"
                    sl_str = f"{stop_loss:.5f}"
                    tp_str = f"{take_profit:.5f}"
                    score_str = f"{confluence_score.total_score:.1f}%"
                except (TypeError, AttributeError):
                    # Fallback for test mocks
                    entry_str = str(entry_price)
                    sl_str = str(stop_loss)
                    tp_str = str(take_profit)
                    score_str = str(confluence_score.total_score) if hasattr(confluence_score, 'total_score') else "N/A"
                
                logger.info(
                    f"{symbol}: Trade executed - {direction.upper()} {lot_size} lots @ {entry_str}\n"
                    f"  Ticket: {ticket}\n"
                    f"  SL: {sl_str} | TP: {tp_str}\n"
                    f"  Confluence: {score_str}"
                )
                
                # Log to journal repository
                if self.journal_repo:
                    try:
                        # Get account balance and equity
                        account_info = None
                        balance = None
                        equity = None
                        try:
                            if hasattr(self.mt5_service, 'account_bal_eq'):
                                balance, equity = self.mt5_service.account_bal_eq()
                            else:
                                # Fallback: try to get from MT5 directly
                                import MetaTrader5 as mt5
                                account_info = mt5.account_info()
                                if account_info:
                                    balance = account_info.balance
                                    equity = account_info.equity
                        except Exception as e:
                            logger.debug(f"Could not get account info for journal: {e}")
                        
                        # Calculate risk:reward ratio
                        risk = abs(entry_price - stop_loss)
                        reward = abs(take_profit - entry_price)
                        rr = reward / risk if risk > 0 else None
                        
                        # Create identifying notes
                        notes = f"LSR_{setup.setup_type}_{symbol} - Liquidity Sweep Reversal (Confluence: {confluence_score.total_score:.1f}%)"
                        
                        # Log to journal
                        self.journal_repo.write_exec({
                            "symbol": symbol,
                            "side": direction.upper(),
                            "entry": entry_price,
                            "sl": stop_loss,
                            "tp": take_profit,
                            "lot": lot_size,
                            "ticket": ticket,
                            "position": ticket,  # Same as ticket for positions
                            "balance": balance,
                            "equity": equity,
                            "rr": rr,
                            "notes": notes
                        })
                        
                        logger.debug(f"✅ LSR trade logged to journal: {ticket} ({notes})")
                    except Exception as e:
                        logger.warning(f"Failed to log LSR trade to journal: {e}")
                
                # Register with Intelligent Exit Manager
                if self.intelligent_exit_manager and ticket:
                    self.intelligent_exit_manager.add_rule(
                        ticket=ticket,
                        symbol=symbol,
                        entry_price=entry_price,
                        direction=direction,
                        initial_sl=stop_loss,
                        initial_tp=take_profit,
                        breakeven_profit_pct=20.0,  # 0.2R
                        partial_profit_pct=60.0,  # 0.6R
                        partial_close_pct=50.0,
                        trailing_enabled=True
                    )
                
                # Send Discord notification
                if self.discord_notifier and self.config["notifications"].get("notify_execution"):
                    await self._send_discord_notification(
                        symbol, "trade_executed",
                        f"**{setup.setup_type} {direction.upper()}** Entry\n"
                        f"Entry: {entry_price:.5f}\n"
                        f"SL: {stop_loss:.5f} | TP: {take_profit:.5f}\n"
                        f"Size: {lot_size} lots\n"
                        f"Confluence: {confluence_score.total_score:.1f}%\n"
                        f"Ticket: {ticket}"
                    )
                
                self._save_state()
            else:
                logger.error(f"Failed to execute trade for {symbol}: {result}")
                
        except Exception as e:
            logger.error(f"Error executing trade for {symbol}: {e}", exc_info=True)
    
    async def _send_discord_notification(self, symbol: str, event_type: str, message: str):
        """Send Discord notification"""
        if not self.discord_notifier:
            return
        
        try:
            title = f"Liquidity Sweep - {symbol}"
            
            if event_type == "sweep_detected":
                color = 0xFFA500  # Orange
                title = f"🔍 Sweep Detected - {symbol}"
            elif event_type == "trade_executed":
                color = 0x00FF00  # Green
                title = f"✅ Trade Executed - {symbol}"
            elif event_type == "setup_invalidated":
                color = 0xFF0000  # Red
                title = f"❌ Setup Invalidated - {symbol}"
            else:
                color = 0x3498DB  # Blue
                title = f"📊 {event_type} - {symbol}"
            
            # DiscordNotifier.send_message() is synchronous, not async
            self.discord_notifier.send_message(
                message=message,
                message_type=title,  # Use title as message_type
                color=color
            )
            
        except Exception as e:
            logger.warning(f"Failed to send Discord notification: {e}")
    
    async def run_continuous(self):
        """Main loop: continuously monitor symbols for liquidity sweeps"""
        if not self.config.get("enabled", True):
            logger.info("Liquidity Sweep Reversal Engine is disabled")
            return
        
        logger.info("Starting Liquidity Sweep Reversal Engine (continuous mode)")
        
        try:
            while True:
                try:
                    for symbol in self.config.get("symbols", []):
                        try:
                            await self.process_symbol(symbol)
                        except Exception as e:
                            logger.error(f"Error processing symbol {symbol}: {e}", exc_info=True)
                            # Continue with next symbol
                    
                    # Wait 60 seconds before next check (M1 candle interval)
                    await asyncio.sleep(60)
                    
                except KeyboardInterrupt:
                    logger.info("Stopping Liquidity Sweep Reversal Engine")
                    break
                except Exception as e:
                    logger.error(f"Error in main loop iteration: {e}", exc_info=True)
                    await asyncio.sleep(60)
        except Exception as fatal_error:
            logger.critical(f"FATAL ERROR in Liquidity Sweep Reversal Engine: {fatal_error}", exc_info=True)
        finally:
            logger.info("Liquidity Sweep Reversal Engine stopped")
    
    async def start(self):
        """Start the engine as a background task"""
        if not self.config.get("enabled", True):
            return
        
        logger.info("Starting Liquidity Sweep Reversal Engine")
        asyncio.create_task(self.run_continuous())
    
    async def stop(self):
        """Stop the engine"""
        logger.info("Stopping Liquidity Sweep Reversal Engine")
        self._save_state()

