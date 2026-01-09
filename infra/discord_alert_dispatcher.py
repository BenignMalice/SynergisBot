"""
Discord Alert Dispatcher - Multi-Timeframe Trading Alerts

Monitors M5/M15/H1 candles from streamer and sends formatted alerts to Discord.
Designed for copy-paste into ChatGPT for analysis and auto-execution plan creation.
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# ALERT THROTTLER
# =============================================================================

class AlertThrottler:
    """
    Prevents alert spam - max 1 alert per symbol/type per cooldown period.
    
    Uses in-memory cache: {(symbol, alert_type): last_alert_time}
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cache: Dict[Tuple[str, str], datetime] = {}
        self.default_cooldown = 5  # minutes
    
    def can_send(self, symbol: str, alert_type: str) -> bool:
        """Check if alert can be sent (not in cooldown)."""
        key = (symbol, alert_type)
        now = datetime.now(timezone.utc)
        
        if key not in self.cache:
            return True
        
        last_sent = self.cache[key]
        cooldown_minutes = self._get_cooldown(alert_type)
        
        return (now - last_sent) >= timedelta(minutes=cooldown_minutes)
    
    def record_sent(self, symbol: str, alert_type: str):
        """Record that an alert was sent."""
        key = (symbol, alert_type)
        self.cache[key] = datetime.now(timezone.utc)
    
    def _get_cooldown(self, alert_type: str) -> int:
        """Get cooldown minutes for alert type."""
        # Map alert type codes to config keys
        type_map = {
            'BEAR_SWEEP': 'liquidity_sweep',
            'BULL_SWEEP': 'liquidity_sweep',
            'CHOCH_BULL': 'choch',
            'CHOCH_BEAR': 'choch',
            'BOS_BULL': 'bos',
            'BOS_BEAR': 'bos',
            'BULLISH_OB': 'order_block',
            'BEARISH_OB': 'order_block',
            'VWAP_DEV_HIGH': 'vwap_deviation',
            'VWAP_DEV_LOW': 'vwap_deviation',
            'BB_SQUEEZE': 'bb_squeeze',
            'BB_EXPANSION': 'bb_expansion',
            'INSIDE_BAR': 'inside_bar',
            'RSI_DIV_BULL': 'rsi_divergence',
            'RSI_DIV_BEAR': 'rsi_divergence',
            'EQUAL_HIGHS': 'equal_highs_lows',
            'EQUAL_LOWS': 'equal_highs_lows',
        }
        
        config_key = type_map.get(alert_type, 'default')
        alerts_config = self.config.get('alerts', {})
        
        if config_key in alerts_config:
            return alerts_config[config_key].get('cooldown_minutes', self.default_cooldown)
        
        return self.default_cooldown
    
    def cleanup_old_entries(self):
        """Remove entries older than max cooldown (30 min)."""
        now = datetime.now(timezone.utc)
        max_age = timedelta(minutes=30)
        
        self.cache = {
            k: v for k, v in self.cache.items()
            if (now - v) < max_age
        }


# =============================================================================
# CONFIDENCE DECAY TRACKER
# =============================================================================

class ConfidenceDecayTracker:
    """
    Tracks alerts that fired at 70-79% confidence and monitors price movement.
    If price doesn't move in expected direction within 5 minutes, raises threshold by +5% for 30 minutes.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        decay_config = self.config.get('confidence_decay', {})
        self.enabled = decay_config.get('enabled', True)
        self.validation_window = timedelta(minutes=decay_config.get('validation_window_minutes', 5))
        self.decay_duration = timedelta(minutes=decay_config.get('decay_duration_minutes', 30))
        self.threshold_adjustment = decay_config.get('threshold_adjustment', 5)
        self.min_movement_atr = decay_config.get('min_movement_atr', 0.1)
        
        # Tracked alerts: {(symbol, alert_type): alert_data}
        self.tracked_alerts: Dict[Tuple[str, str], Dict[str, Any]] = {}
        
        # Active decays: {(symbol, alert_type): decay_data}
        self.active_decays: Dict[Tuple[str, str], Dict[str, Any]] = {}
    
    def register_alert(self, symbol: str, alert_type: str, price: float, direction: str, confidence: int):
        """Register an alert for price movement tracking (only 70-79% confidence)."""
        if not self.enabled:
            return
        
        if 70 <= confidence < 80:
            key = (symbol, alert_type)
            self.tracked_alerts[key] = {
                "price": price,
                "timestamp": datetime.now(timezone.utc),
                "direction": direction,
                "expected_movement_atr": self.min_movement_atr,
                "confidence": confidence
            }
            logger.debug(f"Registered alert for decay tracking: {symbol} {alert_type} at {price} ({direction})")
    
    def check_price_movement(self, symbol: str, alert_type: str, current_price: float, atr: float, streamer: Any = None):
        """Check if price moved in expected direction for tracked alerts."""
        if not self.enabled:
            return
        
        key = (symbol, alert_type)
        if key not in self.tracked_alerts:
            return
        
        alert_data = self.tracked_alerts[key]
        alert_time = alert_data["timestamp"]
        now = datetime.now(timezone.utc)
        
        # Check if validation window has passed
        if (now - alert_time) < self.validation_window:
            return  # Too early to check
        
        # Check price movement
        alert_price = alert_data["price"]
        direction = alert_data["direction"]
        expected_movement = alert_data["expected_movement_atr"] * atr
        
        movement_occurred = False
        if direction == "buy":
            # For buy signals, price should have moved up
            price_change = current_price - alert_price
            movement_occurred = price_change >= expected_movement
        elif direction == "sell":
            # For sell signals, price should have moved down
            price_change = alert_price - current_price
            movement_occurred = price_change >= expected_movement
        
        if not movement_occurred:
            # Price didn't move as expected - activate decay
            self.active_decays[key] = {
                "activated_at": now,
                "expires_at": now + self.decay_duration,
                "threshold_adjustment": self.threshold_adjustment
            }
            logger.info(
                f"Confidence decay activated for {symbol} {alert_type}: "
                f"price didn't move {direction} within {self.validation_window.total_seconds()/60:.0f} min "
                f"(threshold +{self.threshold_adjustment}% for {self.decay_duration.total_seconds()/60:.0f} min)"
            )
        
        # Remove from tracked alerts (checked once)
        del self.tracked_alerts[key]
    
    def get_threshold_adjustment(self, symbol: str, alert_type: str) -> int:
        """Get threshold adjustment for symbol/alert_type if decay is active."""
        if not self.enabled:
            return 0
        
        key = (symbol, alert_type)
        if key not in self.active_decays:
            return 0
        
        decay_data = self.active_decays[key]
        now = datetime.now(timezone.utc)
        
        # Check if decay expired
        if now >= decay_data["expires_at"]:
            del self.active_decays[key]
            logger.debug(f"Confidence decay expired for {symbol} {alert_type}")
            return 0
        
        return decay_data["threshold_adjustment"]
    
    def cleanup_expired(self):
        """Remove expired decay entries."""
        now = datetime.now(timezone.utc)
        expired_keys = [
            key for key, decay_data in self.active_decays.items()
            if now >= decay_data["expires_at"]
        ]
        for key in expired_keys:
            del self.active_decays[key]
        
        # Also cleanup old tracked alerts (older than validation window + buffer)
        max_age = self.validation_window + timedelta(minutes=1)
        old_keys = [
            key for key, alert_data in self.tracked_alerts.items()
            if (now - alert_data["timestamp"]) > max_age
        ]
        for key in old_keys:
            del self.tracked_alerts[key]


# =============================================================================
# ALERT FORMATTER
# =============================================================================

@dataclass
class AlertData:
    """Data structure for a single alert."""
    symbol: str
    alert_type: str
    timeframe: str
    price: float
    confidence: int
    session: str
    trend: str
    volatility: str
    timestamp: datetime
    notes: str
    cross_tf_status: str = "N/A"  # PASSED, FAILED, N/A
    confirmation_tf: str = ""  # For copy-paste prompt


class AlertFormatter:
    """
    Formats alerts for Discord with ChatGPT-ready copy-paste block.
    """
    
    # Severity thresholds
    INFO_THRESHOLD = 60
    ACTION_THRESHOLD = 80
    ACTIONABLE_CONFIDENCE_THRESHOLD = 80  # Alerts >= 80% sent to Discord, 70-79% logged only
    
    # Discord embed colors (hex)
    COLOR_INFO = 0xffff00      # Yellow
    COLOR_ACTION = 0xff9900    # Orange
    COLOR_CRITICAL = 0xff0000  # Red
    
    # Severity emojis
    EMOJI_INFO = "🔸"
    EMOJI_ACTION = "🔶"
    EMOJI_CRITICAL = "🔴"
    
    # Confirmation timeframes by alert type
    CONFIRMATION_TF_MAP = {
        'BEAR_SWEEP': 'M1/M5 CHOCH',
        'BULL_SWEEP': 'M1/M5 CHOCH',
        'CHOCH_BULL': 'M15 trend',
        'CHOCH_BEAR': 'M15 trend',
        'BOS_BULL': 'M5 pullback',
        'BOS_BEAR': 'M5 pullback',
        'BULLISH_OB': 'M5 CHOCH at OB retest',
        'BEARISH_OB': 'M5 CHOCH at OB retest',
        'VWAP_DEV_HIGH': 'mean reversion SELL',
        'VWAP_DEV_LOW': 'mean reversion BUY',
        'BB_SQUEEZE': 'breakout expansion',
        'BB_EXPANSION': 'trend continuation',
        'INSIDE_BAR': 'London/NY breakout',
        'RSI_DIV_BULL': 'reversal BUY',
        'RSI_DIV_BEAR': 'reversal SELL',
        'EQUAL_HIGHS': 'sweep trigger',
        'EQUAL_LOWS': 'sweep trigger',
    }
    
    def format_alert(self, alert: AlertData) -> Tuple[str, int, str]:
        """
        Format alert for Discord.
        
        Returns:
            Tuple of (message, color, title)
        """
        severity_emoji, color = self._get_severity(alert.confidence)
        alert_id = self._generate_alert_id(alert)
        confirmation_tf = self.CONFIRMATION_TF_MAP.get(alert.alert_type, 'confirmation')
        
        # Main alert block
        message = f"""{severity_emoji} **{alert.alert_type}** | {alert.symbol} | {alert.timeframe}

[ALERT]
Symbol: {alert.symbol}
Type: {alert.alert_type}
Timeframe: {alert.timeframe}
Price: {self._format_price(alert.price, alert.symbol)}
Confidence: {alert.confidence}
Session: {alert.session}
Trend: {alert.trend}
Volatility: {alert.volatility}
Time: {alert.timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')}
Alert_ID: {alert_id}
Cross_TF: {alert.cross_tf_status}
Notes: {alert.notes}

**📋 Copy to ChatGPT:**
```
Analyze {alert.symbol} {alert.timeframe} for {alert.alert_type} alert.
Detection: {alert.notes}
Price: {self._format_price(alert.price, alert.symbol)} | Time: {alert.timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')}
Confidence: {alert.confidence}% | Session: {alert.session}
Context: {alert.trend} trend, {alert.volatility} volatility.
If valid setup, create auto-execution plan for {confirmation_tf} confirmation.
```"""
        
        title = f"{alert.alert_type} Alert"
        return message, color, title
    
    def _get_severity(self, confidence: int) -> Tuple[str, int]:
        """Get severity emoji and color based on confidence."""
        if confidence >= self.ACTION_THRESHOLD:
            return self.EMOJI_CRITICAL, self.COLOR_CRITICAL
        elif confidence >= self.INFO_THRESHOLD:
            return self.EMOJI_ACTION, self.COLOR_ACTION
        else:
            return self.EMOJI_INFO, self.COLOR_INFO
    
    def _generate_alert_id(self, alert: AlertData) -> str:
        """Generate 6-char hash for traceability."""
        data = f"{alert.symbol}{alert.alert_type}{alert.timestamp.isoformat()}"
        return hashlib.md5(data.encode()).hexdigest()[:6]
    
    def _format_price(self, price: float, symbol: str) -> str:
        """Format price based on symbol type."""
        symbol_upper = symbol.upper()
        
        if 'JPY' in symbol_upper:
            return f"{price:.3f}"
        elif 'XAU' in symbol_upper or 'GOLD' in symbol_upper:
            return f"{price:.2f}"
        elif 'BTC' in symbol_upper:
            return f"{price:,.0f}"
        elif 'ETH' in symbol_upper:
            return f"{price:.2f}"
        else:
            # Forex pairs
            return f"{price:.5f}"


# =============================================================================
# DETECTION FUNCTIONS
# =============================================================================

def detect_choch_bos(candles: List[Any], timeframe: str) -> Optional[Dict[str, Any]]:
    """
    Detect Change of Character (CHOCH) or Break of Structure (BOS).
    
    CHOCH: Structure shift (trend reversal)
    BOS: Trend continuation (higher high in uptrend, lower low in downtrend)
    
    Args:
        candles: List of Candle objects (newest first)
        timeframe: M5 or M15
    
    Returns:
        Dict with type, direction, price or None
    """
    if len(candles) < 20:
        return None
    
    try:
        # Convert to oldest-first for analysis
        candles = list(reversed(candles[:50]))
        
        # Find swing highs and lows (simplified)
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(candles) - 2):
            # Swing high: higher than 2 candles before and after
            if (candles[i].high > candles[i-1].high and 
                candles[i].high > candles[i-2].high and
                candles[i].high > candles[i+1].high and 
                candles[i].high > candles[i+2].high):
                swing_highs.append((i, candles[i].high))
            
            # Swing low: lower than 2 candles before and after
            if (candles[i].low < candles[i-1].low and 
                candles[i].low < candles[i-2].low and
                candles[i].low < candles[i+1].low and 
                candles[i].low < candles[i+2].low):
                swing_lows.append((i, candles[i].low))
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return None
        
        # Get last 2 swing points
        last_highs = swing_highs[-2:]
        last_lows = swing_lows[-2:]
        
        # Determine previous trend
        prev_trend = None
        if last_highs[-1][1] > last_highs[-2][1] and last_lows[-1][1] > last_lows[-2][1]:
            prev_trend = 'bullish'
        elif last_highs[-1][1] < last_highs[-2][1] and last_lows[-1][1] < last_lows[-2][1]:
            prev_trend = 'bearish'
        
        if prev_trend is None:
            return None
        
        # Calculate ATR for normalization (14-period ATR)
        atr_period = 14
        if len(candles) >= atr_period:
            true_ranges = []
            for i in range(len(candles) - atr_period, len(candles) - 1):
                if i + 1 < len(candles):
                    tr = max(
                        candles[i+1].high - candles[i+1].low,
                        abs(candles[i+1].high - candles[i].close),
                        abs(candles[i+1].low - candles[i].close)
                    )
                    true_ranges.append(tr)
            atr = sum(true_ranges) / len(true_ranges) if true_ranges else None
        else:
            atr = None
        
        # Check current candle for structure break
        current = candles[-1]
        
        # CHOCH detection (trend reversal)
        # CHOCH = Change of Character = Structure shift (reversal)
        if prev_trend == 'bullish':
            # Bearish CHOCH: In uptrend, break below previous swing low (structure shift to bearish)
            # Check if breaking below the second-to-last swing low (previous structure point)
            if len(last_lows) >= 2 and current.close < last_lows[-2][1]:
                break_distance = last_lows[-2][1] - current.close
                # ATR normalization: break should be at least 0.3 ATR to be significant
                if atr and break_distance < atr * 0.3:
                    return None  # Break too small relative to volatility
                
                atr_note = f" ({break_distance/atr:.2f} ATR)" if atr else ""
                return {
                    'type': 'CHOCH_BEAR',
                    'direction': 'sell',
                    'price': current.close,
                    'notes': f"Structure shifted bearish - broke below previous swing low{atr_note}"
                }
        else:  # prev_trend == 'bearish'
            # Bullish CHOCH: In downtrend, break above previous swing high (structure shift to bullish)
            # Check if breaking above the second-to-last swing high (previous structure point)
            if len(last_highs) >= 2 and current.close > last_highs[-2][1]:
                break_distance = current.close - last_highs[-2][1]
                # ATR normalization: break should be at least 0.3 ATR to be significant
                if atr and break_distance < atr * 0.3:
                    return None  # Break too small relative to volatility
                
                atr_note = f" ({break_distance/atr:.2f} ATR)" if atr else ""
                return {
                    'type': 'CHOCH_BULL',
                    'direction': 'buy',
                    'price': current.close,
                    'notes': f"Structure shifted bullish - broke above previous swing high{atr_note}"
                }
        
        # BOS detection (trend continuation)
        if prev_trend == 'bullish':
            if current.close > last_highs[-1][1]:
                break_distance = current.close - last_highs[-1][1]
                # ATR normalization: break should be at least 0.3 ATR to be significant
                if atr and break_distance < atr * 0.3:
                    return None  # Break too small relative to volatility
                
                atr_note = f" ({break_distance/atr:.2f} ATR)" if atr else ""
                return {
                    'type': 'BOS_BULL',
                    'direction': 'buy',
                    'price': current.close,
                    'notes': f"Break of structure bullish, new higher high{atr_note}"
                }
        else:
            if current.close < last_lows[-1][1]:
                break_distance = last_lows[-1][1] - current.close
                # ATR normalization: break should be at least 0.3 ATR to be significant
                if atr and break_distance < atr * 0.3:
                    return None  # Break too small relative to volatility
                
                atr_note = f" ({break_distance/atr:.2f} ATR)" if atr else ""
                return {
                    'type': 'BOS_BEAR',
                    'direction': 'sell',
                    'price': current.close,
                    'notes': f"Break of structure bearish, new lower low{atr_note}"
                }
        
        return None
    except (AttributeError, IndexError, TypeError) as e:
        # Handle missing candle attributes or malformed data
        logger.debug(f"Error detecting CHOCH/BOS: {e}")
        return None


def detect_liquidity_sweep(candles: List[Any]) -> Optional[Dict[str, Any]]:
    """
    Detect liquidity sweep (stop hunt) with rejection.
    
    Bull sweep: Wick below recent lows then close above
    Bear sweep: Wick above recent highs then close below
    
    Enhanced with volume confirmation.
    """
    if len(candles) < 20:
        return None
    
    try:
        # Convert to oldest-first
        candles = list(reversed(candles[:30]))
        
        # Find recent swing high/low (last 20 candles excluding last 3)
        lookback = candles[:-3]
        recent_high = max(c.high for c in lookback[-15:])
        recent_low = min(c.low for c in lookback[-15:])
        
        current = candles[-1]
        prev = candles[-2]
        
        # Calculate average volume for comparison
        volumes = []
        for c in lookback[-15:]:
            vol = getattr(c, 'volume', getattr(c, 'tick_volume', 0))
            if vol > 0:
                volumes.append(vol)
        avg_volume = sum(volumes) / len(volumes) if volumes else 1
        
        # Get current candle volume
        current_volume = getattr(current, 'volume', getattr(current, 'tick_volume', 0))
        if current_volume <= 0:
            current_volume = avg_volume  # Fallback if volume missing
        
        # Bear sweep: wick above recent high, close below
        if current.high > recent_high and current.close < current.open:
            wick_size = current.high - max(current.open, current.close)
            body_size = abs(current.close - current.open)
            
            if wick_size > body_size * 0.5:  # Significant rejection wick
                # Volume confirmation: sweep candle should have elevated volume
                if current_volume >= avg_volume * 1.1:  # At least 10% above average
                    return {
                        'type': 'BEAR_SWEEP',
                        'direction': 'sell',
                        'price': current.close,
                        'notes': f"Stops above {recent_high:.2f} cleared, price rejected (volume confirmed)"
                    }
        
        # Bull sweep: wick below recent low, close above
        if current.low < recent_low and current.close > current.open:
            wick_size = min(current.open, current.close) - current.low
            body_size = abs(current.close - current.open)
            
            if wick_size > body_size * 0.5:
                # Volume confirmation: sweep candle should have elevated volume
                if current_volume >= avg_volume * 1.1:  # At least 10% above average
                    return {
                        'type': 'BULL_SWEEP',
                        'direction': 'buy',
                        'price': current.close,
                        'notes': f"Stops below {recent_low:.2f} cleared, price rejected (volume confirmed)"
                    }
        
        return None
    except (AttributeError, IndexError, TypeError, ZeroDivisionError) as e:
        # Handle missing candle attributes or malformed data
        logger.debug(f"Error detecting liquidity sweep: {e}")
        return None


def detect_order_block(candles: List[Any]) -> Optional[Dict[str, Any]]:
    """
    Detect order block (last impulse candle before reversal).
    
    Bullish OB: Last bearish candle before bullish move
    Bearish OB: Last bullish candle before bearish move
    
    Enhanced with basic validation:
    - Displacement check: Validates strong move after OB candle
    - Volume check: Confirms volume spike on displacement
    
    Note: This is enhanced detection for alerts. Comprehensive validation
    (10-parameter checklist) is performed by the auto-execution system.
    """
    if len(candles) < 20:
        return None
    
    try:
        # Convert to oldest-first
        candles = list(reversed(candles[:30]))
        
        # Look for impulse move in last 8 candles (need more for validation)
        recent = candles[-8:]
        
        # Calculate move strength
        move = recent[-1].close - recent[0].open
        avg_range = sum(c.high - c.low for c in recent) / len(recent)
        
        if avg_range == 0:
            return None  # Cannot calculate move strength without range
        
        if abs(move) < avg_range * 2:
            return None  # Not a strong enough move
        
        # Calculate average volume for comparison
        volumes = []
        for c in recent:
            vol = getattr(c, 'volume', getattr(c, 'tick_volume', 0))
            if vol > 0:
                volumes.append(vol)
        avg_volume = sum(volumes) / len(volumes) if volumes else 1
        
        # Bullish OB: strong up move, find last bearish candle
        if move > 0:
            ob_candle_idx = None
            for i in range(len(recent) - 1, -1, -1):
                if recent[i].close < recent[i].open:  # Bearish candle
                    ob_candle_idx = i
                    break
            
            if ob_candle_idx is None:
                return None
            
            # Check displacement: candles after OB should show strong bullish move
            displacement_candles = recent[ob_candle_idx + 1:]
            if len(displacement_candles) < 2:
                return None  # Need at least 2 candles after OB for displacement
            
            # Calculate displacement strength
            displacement_move = displacement_candles[-1].close - displacement_candles[0].open
            if avg_range == 0:
                return None  # Cannot calculate displacement strength without range
            
            displacement_strength = abs(displacement_move) / avg_range
            
            if displacement_strength < 1.5:
                return None  # Displacement not strong enough
            
            # Check volume on displacement candles
            displacement_volumes = []
            for c in displacement_candles:
                vol = getattr(c, 'volume', getattr(c, 'tick_volume', 0))
                if vol > 0:
                    displacement_volumes.append(vol)
            
            # Require volume confirmation if volume data is available
            # If no volume data at all, skip volume check (for symbols without volume)
            if displacement_volumes:
                max_displacement_volume = max(displacement_volumes)
                if max_displacement_volume < avg_volume * 1.2:
                    return None  # No volume spike on displacement
            elif volumes:  # If we had volume data in recent candles but not in displacement
                # This means volume data exists but displacement candles have no volume
                # This is suspicious - might indicate bad data, so be conservative
                return None  # Missing volume on displacement candles when volume data exists
            
            ob_high = recent[ob_candle_idx].high
            ob_low = recent[ob_candle_idx].low
            return {
                'type': 'BULLISH_OB',
                'direction': 'buy',
                'price': candles[-1].close,
                'notes': f"Institutional buy zone at {ob_low:.0f}-{ob_high:.0f} (displacement + volume confirmed)",
                'ob_zone': (ob_low, ob_high)
            }
        
        # Bearish OB: strong down move, find last bullish candle
        if move < 0:
            ob_candle_idx = None
            for i in range(len(recent) - 1, -1, -1):
                if recent[i].close > recent[i].open:  # Bullish candle
                    ob_candle_idx = i
                    break
            
            if ob_candle_idx is None:
                return None
            
            # Check displacement: candles after OB should show strong bearish move
            displacement_candles = recent[ob_candle_idx + 1:]
            if len(displacement_candles) < 2:
                return None  # Need at least 2 candles after OB for displacement
            
            # Calculate displacement strength
            displacement_move = displacement_candles[-1].close - displacement_candles[0].open
            if avg_range == 0:
                return None  # Cannot calculate displacement strength without range
            
            displacement_strength = abs(displacement_move) / avg_range
            
            if displacement_strength < 1.5:
                return None  # Displacement not strong enough
            
            # Check volume on displacement candles
            displacement_volumes = []
            for c in displacement_candles:
                vol = getattr(c, 'volume', getattr(c, 'tick_volume', 0))
                if vol > 0:
                    displacement_volumes.append(vol)
            
            # Require volume confirmation if volume data is available
            # If no volume data at all, skip volume check (for symbols without volume)
            if displacement_volumes:
                max_displacement_volume = max(displacement_volumes)
                if max_displacement_volume < avg_volume * 1.2:
                    return None  # No volume spike on displacement
            elif volumes:  # If we had volume data in recent candles but not in displacement
                # This means volume data exists but displacement candles have no volume
                # This is suspicious - might indicate bad data, so be conservative
                return None  # Missing volume on displacement candles when volume data exists
            
            ob_high = recent[ob_candle_idx].high
            ob_low = recent[ob_candle_idx].low
            return {
                'type': 'BEARISH_OB',
                'direction': 'sell',
                'price': candles[-1].close,
                'notes': f"Institutional sell zone at {ob_low:.0f}-{ob_high:.0f} (displacement + volume confirmed)",
                'ob_zone': (ob_low, ob_high)
            }
        
        return None
    except (AttributeError, IndexError, TypeError, ZeroDivisionError) as e:
        # Handle missing candle attributes or malformed data
        logger.debug(f"Error detecting order block: {e}")
        return None


def detect_vwap_deviation(candles: List[Any], threshold_sigma: float = 2.0) -> Optional[Dict[str, Any]]:
    """
    Detect VWAP deviation beyond threshold.
    """
    if len(candles) < 20:
        return None
    
    try:
        # Calculate VWAP
        total_pv = 0
        total_volume = 0
        
        for c in candles[:50]:
            # Handle missing volume (use tick_volume or default to 1)
            volume = getattr(c, 'volume', getattr(c, 'tick_volume', 1))
            if volume <= 0:
                volume = 1  # Default to 1 if volume is missing or zero
            
            typical_price = (c.high + c.low + c.close) / 3
            total_pv += typical_price * volume
            total_volume += volume
        
        if total_volume == 0:
            return None
        
        vwap = total_pv / total_volume
        
        # Calculate standard deviation (use sample std dev: N-1)
        deviations = []
        for c in candles[:50]:
            typical_price = (c.high + c.low + c.close) / 3
            deviations.append((typical_price - vwap) ** 2)
        
        if not deviations or len(deviations) < 2:
            return None
        
        # Sample standard deviation (divide by N-1 for better accuracy)
        std_dev = (sum(deviations) / (len(deviations) - 1)) ** 0.5
        
        if std_dev == 0:
            return None
        
        current_price = candles[0].close
        deviation_sigma = (current_price - vwap) / std_dev
    
        if deviation_sigma > threshold_sigma:
            return {
                'type': 'VWAP_DEV_HIGH',
                'direction': 'sell',
                'price': current_price,
                'notes': f"Price +{deviation_sigma:.1f}σ above VWAP ({vwap:.0f}), ${abs(current_price - vwap):.0f} deviation"
            }
        elif deviation_sigma < -threshold_sigma:
            return {
                'type': 'VWAP_DEV_LOW',
                'direction': 'buy',
                'price': current_price,
                'notes': f"Price {deviation_sigma:.1f}σ below VWAP ({vwap:.0f}), ${abs(current_price - vwap):.0f} deviation"
            }
        
        return None
    except (AttributeError, IndexError, TypeError, ZeroDivisionError) as e:
        # Handle missing candle attributes, malformed data, or division errors
        logger.debug(f"Error detecting VWAP deviation: {e}")
        return None


def detect_bb_state(candles: List[Any], squeeze_threshold: float = 1.5, expansion_threshold: float = 2.0) -> Optional[Dict[str, Any]]:
    """
    Detect Bollinger Band squeeze or expansion.
    
    Uses proper Bollinger Bands calculation: BB width = (upper - lower) / middle
    where upper = middle + 2*std, lower = middle - 2*std
    So width = 4*std / middle
    """
    if len(candles) < 20:
        return None
    
    try:
        # Calculate BB width using proper Bollinger Bands formula
        closes = [c.close for c in candles[:20]]
        sma = sum(closes) / len(closes)
        std_dev = (sum((c - sma) ** 2 for c in closes) / len(closes)) ** 0.5
        
        if sma == 0:
            return None
        
        # Proper BB width: (upper - lower) / middle = (4 * std_dev) / middle
        # Upper = middle + 2*std, Lower = middle - 2*std
        # Width = (upper - lower) / middle = 4*std / middle
        bb_width = (std_dev * 4) / sma * 100  # As percentage (corrected from 2*std to 4*std)
        
        if bb_width < squeeze_threshold:
            return {
                'type': 'BB_SQUEEZE',
                'direction': 'neutral',
                'price': candles[0].close,
                'notes': f"BB Width {bb_width:.2f}% (squeeze) - breakout imminent"
            }
        elif bb_width > expansion_threshold:
            # Determine direction based on price vs SMA
            if candles[0].close > sma:
                return {
                    'type': 'BB_EXPANSION',
                    'direction': 'buy',
                    'price': candles[0].close,
                    'notes': f"BB Width {bb_width:.2f}% (expansion) - bullish breakout"
                }
            else:
                return {
                    'type': 'BB_EXPANSION',
                    'direction': 'sell',
                    'price': candles[0].close,
                    'notes': f"BB Width {bb_width:.2f}% (expansion) - bearish breakout"
                }
        
        return None
    except (AttributeError, IndexError, TypeError, ZeroDivisionError) as e:
        # Handle missing candle attributes, malformed data, or division errors
        logger.debug(f"Error detecting BB state: {e}")
        return None


def detect_inside_bar(candles: List[Any]) -> Optional[Dict[str, Any]]:
    """
    Detect inside bar pattern (compression).
    
    Enhanced with direction hint based on price position within mother bar.
    """
    if len(candles) < 3:
        return None
    
    try:
        current = candles[0]
        mother = candles[1]
        
        # Inside bar: current high/low within mother bar
        if current.high < mother.high and current.low > mother.low:
            range_size = mother.high - mother.low
            mother_range = mother.high - mother.low
            
            # Determine price position within mother bar (0.0 = at low, 1.0 = at high)
            if mother_range > 0:
                price_position = (current.close - mother.low) / mother_range
                
                # Direction hint based on position
                if price_position > 0.65:
                    direction_hint = "Watch for bullish breakout"
                elif price_position < 0.35:
                    direction_hint = "Watch for bearish breakout"
                else:
                    direction_hint = "Neutral - watch both directions"
                
                return {
                    'type': 'INSIDE_BAR',
                    'direction': 'neutral',
                    'price': current.close,
                    'notes': f"Compression forming, range {mother.low:.0f}-{mother.high:.0f} ({range_size:.0f}pts). {direction_hint}"
                }
        
        return None
    except (AttributeError, IndexError, TypeError, ZeroDivisionError) as e:
        # Handle missing candle attributes or malformed data
        logger.debug(f"Error detecting inside bar: {e}")
        return None


def detect_rsi_divergence(candles: List[Any]) -> Optional[Dict[str, Any]]:
    """
    Detect RSI divergence using proper divergence detection.
    
    Properly checks if price and RSI are moving in opposite directions,
    not just if RSI is in a certain range.
    """
    if len(candles) < 30:  # Need more candles for proper RSI calculation
        return None
    
    try:
        # Calculate RSI for multiple periods to detect divergence
        # Use standard 14-period RSI
        period = 14
        rsi_values = []
        prices = []
        
        # Calculate RSI for last 20 candles (need enough for trend comparison)
        for start_idx in range(max(0, len(candles) - 20), len(candles) - period + 1):
            if start_idx + period > len(candles):
                break
                
            # Calculate RSI for this window
            gains = []
            losses = []
            
            for i in range(start_idx + 1, start_idx + period):
                if i >= len(candles):
                    break
                change = candles[i-1].close - candles[i].close  # Newest first
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            if not gains or not losses or sum(losses) == 0:
                continue
            
            avg_gain = sum(gains) / len(gains)
            avg_loss = sum(losses) / len(losses)
            
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            rsi_values.append(rsi)
            prices.append(candles[start_idx].close)
        
        if len(rsi_values) < 5 or len(prices) < 5:
            return None
        
        # Get current RSI
        current_rsi = rsi_values[-1]
        current_price = candles[0].close
        
        # Check for divergence by comparing price trend vs RSI trend
        # Use recent 5-7 periods for trend comparison
        lookback = min(7, len(rsi_values) - 1)
        if lookback < 3:
            return None
        
        # Price trend: compare recent price vs earlier price
        price_trend = prices[0] - prices[lookback]  # Newest - older
        # RSI trend: compare recent RSI vs earlier RSI
        rsi_trend = rsi_values[0] - rsi_values[lookback]  # Newest - older
        
        # Bearish divergence: price making higher highs, RSI making lower highs
        # Price going up but RSI going down
        if price_trend > 0 and rsi_trend < 0 and current_rsi > 50 and current_rsi < 75:
            return {
                'type': 'RSI_DIV_BEAR',
                'direction': 'sell',
                'price': current_price,
                'notes': f"RSI bearish divergence detected, RSI at {current_rsi:.0f}"
            }
        
        # Bullish divergence: price making lower lows, RSI making higher lows
        # Price going down but RSI going up
        if price_trend < 0 and rsi_trend > 0 and current_rsi < 50 and current_rsi > 25:
            return {
                'type': 'RSI_DIV_BULL',
                'direction': 'buy',
                'price': current_price,
                'notes': f"RSI bullish divergence detected, RSI at {current_rsi:.0f}"
            }
        
        return None
    except (AttributeError, IndexError, TypeError, ZeroDivisionError) as e:
        # Handle missing candle attributes, malformed data, or division errors
        logger.debug(f"Error detecting RSI divergence: {e}")
        return None


def detect_equal_highs_lows(candles: List[Any], tolerance_pct: float = 0.1) -> Optional[Dict[str, Any]]:
    """
    Detect equal highs or equal lows (liquidity zones).
    
    Looks for clusters of 2+ similar price levels (highs or lows) that are
    at least 3 candles apart, indicating liquidity zones.
    """
    if len(candles) < 20:
        return None
    
    try:
        # Get highs and lows with their indices
        highs = [(i, c.high) for i, c in enumerate(candles[:30])]
        lows = [(i, c.low) for i, c in enumerate(candles[:30])]
        
        # Find clusters of similar highs (at least 2 levels within tolerance)
        for i, (idx1, h1) in enumerate(highs):
            # Check for other highs that are similar and at least 3 candles apart
            for idx2, h2 in highs[i+3:]:  # At least 3 candles apart
                if h1 == 0:
                    continue  # Skip if price is zero (invalid data)
                tolerance = h1 * tolerance_pct / 100
                if abs(h1 - h2) < tolerance:
                    # Found a pair of equal highs - check if there are more (cluster of 3+)
                    cluster_count = 2
                    for idx3, h3 in highs:
                        if idx3 != idx1 and idx3 != idx2 and abs(h1 - h3) < tolerance:
                            cluster_count += 1
                    
                    cluster_note = f"{cluster_count} equal highs" if cluster_count > 2 else "Equal highs"
                    return {
                        'type': 'EQUAL_HIGHS',
                        'direction': 'neutral',
                        'price': candles[0].close,
                        'notes': f"{cluster_note} at {h1:.0f} - liquidity resting above"
                    }
        
        # Find clusters of similar lows (at least 2 levels within tolerance)
        for i, (idx1, l1) in enumerate(lows):
            # Check for other lows that are similar and at least 3 candles apart
            for idx2, l2 in lows[i+3:]:  # At least 3 candles apart
                if l1 == 0:
                    continue  # Skip if price is zero (invalid data)
                tolerance = l1 * tolerance_pct / 100
                if abs(l1 - l2) < tolerance:
                    # Found a pair of equal lows - check if there are more (cluster of 3+)
                    cluster_count = 2
                    for idx3, l3 in lows:
                        if idx3 != idx1 and idx3 != idx2 and abs(l1 - l3) < tolerance:
                            cluster_count += 1
                    
                    cluster_note = f"{cluster_count} equal lows" if cluster_count > 2 else "Equal lows"
                    return {
                        'type': 'EQUAL_LOWS',
                        'direction': 'neutral',
                        'price': candles[0].close,
                        'notes': f"{cluster_note} at {l1:.0f} - liquidity resting below"
                    }
        
        return None
    except (AttributeError, IndexError, TypeError) as e:
        # Handle missing candle attributes or malformed data
        logger.debug(f"Error detecting equal highs/lows: {e}")
        return None


def get_h1_trend(candles: List[Any]) -> str:
    """
    Get H1 trend direction from candles.
    
    Returns: "Bullish", "Bearish", or "Neutral"
    """
    if len(candles) < 5:
        return "Neutral"
    
    # Compare close of last 5 candles
    closes = [c.close for c in candles[:5]]
    
    # Simple trend: compare first and last
    change = closes[0] - closes[-1]
    avg_range = sum(abs(candles[i].close - candles[i+1].close) for i in range(4)) / 4
    
    if avg_range == 0:
        return "Neutral"  # Cannot determine trend without price movement
    
    if change > avg_range * 2:
        return "Bullish"
    elif change < -avg_range * 2:
        return "Bearish"
    else:
        return "Neutral"


# =============================================================================
# CROSS-TIMEFRAME CONFIRMATION
# =============================================================================

class CrossTFConfirmation:
    """
    Validates alerts with cross-timeframe confirmation.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get('cross_tf_confirmation', {})
        self.enabled = self.config.get('enabled', False)
        self.required_for_critical = self.config.get('required_for_critical', True)
        self.rules = self.config.get('rules', {})
    
    def check(self, alert_type: str, m5_candles: List[Any], m15_candles: List[Any]) -> str:
        """
        Check cross-TF confirmation.
        
        Returns: "PASSED", "FAILED", or "N/A"
        """
        if not self.enabled:
            return "N/A"
        
        # Get rule for this alert type
        alert_category = self._get_category(alert_type)
        rule = self.rules.get(alert_category, {})
        
        if not rule:
            return "N/A"
        
        direction_must_match = rule.get('direction_must_match', True)
        lookback = rule.get('lookback_candles', 5)
        require = rule.get('require', '')
        
        # Validate candle data
        if not m5_candles or len(m5_candles) == 0:
            return "N/A"
        if not m15_candles or len(m15_candles) == 0:
            return "N/A"
        
        # Ensure lookback doesn't exceed available candles
        m5_lookback = min(lookback, len(m5_candles))
        m15_lookback = min(lookback, len(m15_candles))
        
        # CHOCH alerts: check M15 for OB or sweep
        if alert_category == 'choch':
            ob = detect_order_block(m15_candles[:m15_lookback])
            sweep = detect_liquidity_sweep(m15_candles[:m15_lookback])
            
            if ob or sweep:
                if direction_must_match:
                    alert_dir = 'buy' if 'BULL' in alert_type else 'sell'
                    confirm_dir = (ob or sweep).get('direction', '')
                    if confirm_dir == alert_dir or confirm_dir == 'neutral':
                        return "PASSED"
                    return "FAILED"
                return "PASSED"
            return "FAILED"
        
        # Sweep alerts: check M5 for CHOCH
        if alert_category == 'sweep':
            choch = detect_choch_bos(m5_candles[:m5_lookback], 'M5')
            
            if choch and 'CHOCH' in choch.get('type', ''):
                if direction_must_match:
                    alert_dir = 'buy' if 'BULL' in alert_type else 'sell'
                    if choch.get('direction', '') == alert_dir:
                        return "PASSED"
                    return "FAILED"
                return "PASSED"
            return "FAILED"
        
        # Order block alerts: check M5 for structure alignment
        if alert_category == 'order_block':
            structure = detect_choch_bos(m5_candles[:m5_lookback], 'M5')
            
            if structure:
                if direction_must_match:
                    alert_dir = 'buy' if 'BULLISH' in alert_type else 'sell'
                    if structure.get('direction', '') == alert_dir:
                        return "PASSED"
                    return "FAILED"
                return "PASSED"
            return "FAILED"
        
        return "N/A"
    
    def _get_category(self, alert_type: str) -> str:
        """Map alert type to category."""
        if 'CHOCH' in alert_type:
            return 'choch'
        if 'SWEEP' in alert_type:
            return 'sweep'
        if 'OB' in alert_type:
            return 'order_block'
        return ''


# =============================================================================
# CONFLUENCE SCORING
# =============================================================================

def calculate_confluence(
    alert_type: str,
    direction: str,
    h1_trend: str,
    session: str,
    volatility: str,
    cross_tf_passed: bool
) -> int:
    """
    Calculate confluence score (0-100).
    """
    # Base scores by alert type
    base_scores = {
        'BEAR_SWEEP': 60,
        'BULL_SWEEP': 60,
        'CHOCH_BULL': 55,
        'CHOCH_BEAR': 55,
        'BOS_BULL': 50,
        'BOS_BEAR': 50,
        'BULLISH_OB': 50,
        'BEARISH_OB': 50,
        'VWAP_DEV_HIGH': 55,
        'VWAP_DEV_LOW': 55,
        'BB_SQUEEZE': 45,
        'BB_EXPANSION': 50,
        'INSIDE_BAR': 40,
        'RSI_DIV_BULL': 50,
        'RSI_DIV_BEAR': 50,
        'EQUAL_HIGHS': 35,
        'EQUAL_LOWS': 35,
    }
    
    score = base_scores.get(alert_type, 50)
    
    # +10 if H1 trend aligns
    if direction == 'buy' and h1_trend == 'Bullish':
        score += 10
    elif direction == 'sell' and h1_trend == 'Bearish':
        score += 10
    
    # +10 if active session
    active_sessions = ['London', 'New_York', 'NY', 'London_NY_Overlap']
    if any(s in session for s in active_sessions):
        score += 10
    
    # +10 if volatility matches strategy
    if alert_type in ['BB_EXPANSION', 'BEAR_SWEEP', 'BULL_SWEEP', 'BOS_BULL', 'BOS_BEAR']:
        if volatility == 'EXPANDING':
            score += 10
    elif alert_type in ['BB_SQUEEZE', 'INSIDE_BAR']:
        if volatility == 'CONTRACTING':
            score += 10
    elif alert_type in ['VWAP_DEV_HIGH', 'VWAP_DEV_LOW']:
        if volatility == 'EXPANDING':
            score += 10
    
    # +10 if cross-TF confirmation passed
    if cross_tf_passed:
        score += 10
    
    return min(score, 100)


# =============================================================================
# MAIN DISPATCHER
# =============================================================================

class DiscordAlertDispatcher:
    """
    Main dispatcher - monitors candles and sends alerts to Discord.
    """
    
    def __init__(self, config_path: str = "config/discord_alerts_config.json"):
        self.config = self._load_config(config_path)
        self.throttler = AlertThrottler(self.config)
        self.formatter = AlertFormatter()
        self.cross_tf = CrossTFConfirmation(self.config)
        self.decay_tracker = ConfidenceDecayTracker(self.config)
        
        self.streamer = None
        self.discord_notifier = None
        self.channel_webhooks: Dict[str, str] = {}
        self.is_running = False
        
        # Symbols to monitor
        self.symbols = self.config.get('symbols', ['BTCUSDc', 'XAUUSDc'])
        
        # Create informational alerts directory
        self.info_alerts_dir = Path("data/alerts_informational")
        self.info_alerts_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Discord Alert Dispatcher initialized for {len(self.symbols)} symbols")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        path = Path(config_path)
        
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
        
        logger.warning(f"Config not found at {config_path}, using defaults")
        return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "enabled": True,
            "min_confidence": 70,
            "actionable_threshold": 80,
            "symbols": ["BTCUSDc", "XAUUSDc"],
            "symbol_overrides": {
                "XAUUSDc": {"min_confidence": 80, "actionable_threshold": 80},
                "BTCUSDc": {"min_confidence": 75, "actionable_threshold": 80},
                "GBPUSDc": {"min_confidence": 75, "actionable_threshold": 80},
                "EURUSDc": {"min_confidence": 70, "actionable_threshold": 80}
            },
            "confidence_decay": {
                "enabled": True,
                "validation_window_minutes": 5,
                "decay_duration_minutes": 30,
                "threshold_adjustment": 5,
                "min_movement_atr": 0.1
            },
            "alerts": {
                "liquidity_sweep": {"enabled": True, "timeframes": ["M5"], "cooldown_minutes": 5},
                "order_block": {"enabled": True, "timeframes": ["M15"], "cooldown_minutes": 10},
                "choch": {"enabled": True, "timeframes": ["M5"], "cooldown_minutes": 5},
                "bos": {"enabled": True, "timeframes": ["M15"], "cooldown_minutes": 10},
                "vwap_deviation": {"enabled": True, "timeframes": ["M15"], "min_sigma": 2.0, "cooldown_minutes": 15},
                "inside_bar": {"enabled": True, "timeframes": ["M15"], "cooldown_minutes": 30},
                "bb_squeeze": {"enabled": True, "timeframes": ["M15"], "max_bb_width": 1.5, "cooldown_minutes": 15},
                "bb_expansion": {"enabled": True, "timeframes": ["M5", "M15"], "min_bb_width": 2.0, "cooldown_minutes": 15},
            },
            "quiet_hours": {"enabled": True, "start_utc": 22, "end_utc": 6}
        }
    
    async def start(self):
        """Start the dispatcher (initialize streamer and notifier)."""
        if self.is_running:
            logger.warning("Dispatcher already running")
            return
        
        try:
            # Import here to avoid circular imports
            from infra.multi_timeframe_streamer import MultiTimeframeStreamer, StreamerConfig
            from discord_notifications import DiscordNotifier
            
            # Create streamer config
            streamer_config = StreamerConfig(symbols=self.symbols)
            self.streamer = MultiTimeframeStreamer(streamer_config)
            await self.streamer.start()
            
            # Create Discord notifier
            self.discord_notifier = DiscordNotifier()
            
            # Load channel webhooks from environment
            self.channel_webhooks = self._load_channel_webhooks()
            
            if not self.discord_notifier.enabled:
                logger.warning("Discord notifier not enabled - alerts will be logged only")
            
            self.is_running = True
            logger.info("Discord Alert Dispatcher started")
            if self.channel_webhooks:
                logger.info(f"   → Channel routing enabled: {list(self.channel_webhooks.keys())}")
            else:
                logger.warning("   → No channel webhooks configured - using default DiscordNotifier")
                if self.discord_notifier:
                    logger.info(f"   → Default notifier enabled: {self.discord_notifier.enabled}")
                else:
                    logger.error("   → Default notifier is None - alerts will NOT be sent!")
            
        except Exception as e:
            logger.error(f"Failed to start dispatcher: {e}")
            raise
    
    def _load_channel_webhooks(self) -> Dict[str, str]:
        """Load channel-specific webhooks from environment."""
        import os
        
        # Ensure .env is loaded
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            # Manual .env loading fallback
            env_path = '.env'
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()
        
        webhooks = {}
        
        # Check for channel-specific webhooks
        channel_env_map = {
            'crypto': 'DISCORD_WEBHOOK_CRYPTO',
            'gold': 'DISCORD_WEBHOOK_GOLD',
            'forex': 'DISCORD_WEBHOOK_FOREX',
            'indices': 'DISCORD_WEBHOOK_INDICES',
        }
        
        for channel, env_var in channel_env_map.items():
            webhook_url = os.getenv(env_var)
            if webhook_url:
                webhooks[channel] = webhook_url
                logger.info(f"✅ Loaded webhook for channel '{channel}' from {env_var} (URL: {webhook_url[:50]}...)")
            else:
                logger.debug(f"   No webhook found for channel '{channel}' (env var: {env_var})")
        
        if not webhooks:
            logger.warning("No channel webhooks found - all alerts will go to default channel")
        
        return webhooks
    
    def _get_channel_for_symbol(self, symbol: str) -> str:
        """Get Discord channel for a symbol based on routing config."""
        routing = self.config.get('channel_routing', {})
        return routing.get(symbol, routing.get('default', 'private'))
    
    def _is_weekend(self) -> bool:
        """
        Check if current time is weekend (Friday 21:00 UTC to Sunday 22:00 UTC).
        
        Returns:
            True if weekend, False otherwise
        """
        now = datetime.now(timezone.utc)
        weekday = now.weekday()  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
        hour = now.hour
        
        # Friday after 21:00 UTC
        if weekday == 4 and hour >= 21:
            return True
        
        # Saturday (all day)
        if weekday == 5:
            return True
        
        # Sunday before 22:00 UTC
        if weekday == 6 and hour < 22:
            return True
        
        return False
    
    def _should_monitor_on_weekend(self, symbol: str) -> bool:
        """
        Check if symbol should be monitored on weekends.
        
        Args:
            symbol: Symbol name
            
        Returns:
            True if should monitor on weekend, False otherwise
        """
        # BTCUSD trades 24/7
        if 'BTC' in symbol.upper():
            return True
        
        # Gold (XAUUSD, XAGUSD) and Forex pairs: skip weekend (limited trading)
        return False
    
    async def stop(self):
        """Stop the dispatcher."""
        self.is_running = False
        if self.streamer:
            await self.streamer.stop()
        logger.info("Discord Alert Dispatcher stopped")
    
    async def run_detection_cycle(self):
        """Run one detection cycle for all symbols."""
        if not self.is_running:
            logger.debug("Discord Alert Dispatcher: Not running, skipping cycle")
            return
        
        if not self.config.get('enabled', True):
            logger.debug("Discord Alert Dispatcher: Disabled in config, skipping cycle")
            return
        
        # Check quiet hours
        if self._in_quiet_hours():
            logger.debug("Discord Alert Dispatcher: In quiet hours, skipping cycle")
            return
        
        # Get current session
        session = self._get_current_session()
        logger.debug(f"Discord Alert Dispatcher: Running detection cycle for session {session}")
        
        alerts_sent = 0
        for symbol in self.symbols:
            try:
                result = await self._process_symbol(symbol, session)
                if result:
                    alerts_sent += result
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}", exc_info=True)
        
        if alerts_sent > 0:
            logger.info(f"Discord Alert Dispatcher: Sent {alerts_sent} alert(s) in this cycle")
        else:
            logger.debug(f"Discord Alert Dispatcher: No alerts sent in this cycle (session: {session})")
        
        # Cleanup old throttle entries
        self.throttler.cleanup_old_entries()
        
        # Check price movement for tracked alerts and cleanup expired decays
        if self.decay_tracker.enabled and self.streamer:
            for symbol in self.symbols:
                try:
                    # Get current price and ATR for movement validation
                    m5_candles = self.streamer.get_candles(symbol, 'M5', 20)
                    m15_candles = self.streamer.get_candles(symbol, 'M15', 20)
                    
                    if m5_candles and len(m5_candles) > 0:
                        current_price = m5_candles[0].close
                        m5_atr = self._calculate_atr_approximation(m5_candles)
                        
                        # Check CHOCH alerts (M5 timeframe)
                        self.decay_tracker.check_price_movement(symbol, 'CHOCH_BULL', current_price, m5_atr, self.streamer)
                        self.decay_tracker.check_price_movement(symbol, 'CHOCH_BEAR', current_price, m5_atr, self.streamer)
                    
                    if m15_candles and len(m15_candles) > 0:
                        if not m5_candles or len(m5_candles) == 0:
                            # Fallback to M15 price if M5 not available
                            current_price = m15_candles[0].close
                        m15_atr = self._calculate_atr_approximation(m15_candles)
                        
                        # Check BOS alerts (M15 timeframe)
                        self.decay_tracker.check_price_movement(symbol, 'BOS_BULL', current_price, m15_atr, self.streamer)
                        self.decay_tracker.check_price_movement(symbol, 'BOS_BEAR', current_price, m15_atr, self.streamer)
                except Exception as e:
                    logger.debug(f"Error checking price movement for {symbol}: {e}")
            
            self.decay_tracker.cleanup_expired()
    
    async def _process_symbol(self, symbol: str, session: str) -> int:
        """Process alerts for a single symbol. Returns number of alerts sent."""
        # Skip gold/forex symbols on weekends
        if self._is_weekend() and not self._should_monitor_on_weekend(symbol):
            logger.debug(f"Skipping {symbol} - weekend filtering")
            return 0
        
        # Validate streamer is available
        if not self.streamer:
            logger.warning(f"Streamer not available for {symbol} - alerts cannot be processed")
            return 0
        
        # Get candles from streamer
        m5_candles = self.streamer.get_candles(symbol, 'M5', 50)
        m15_candles = self.streamer.get_candles(symbol, 'M15', 50)
        h1_candles = self.streamer.get_candles(symbol, 'H1', 20)
        
        # Validate candle data exists and is not empty
        if not m5_candles or len(m5_candles) == 0:
            logger.warning(f"No M5 candles available for {symbol} - alerts cannot be processed")
            return 0
        if not m15_candles or len(m15_candles) == 0:
            logger.warning(f"No M15 candles available for {symbol} - alerts cannot be processed")
            return 0
        
        # Get context
        h1_trend = get_h1_trend(h1_candles) if h1_candles else "Neutral"
        volatility = self._get_volatility_state(m15_candles)
        
        # Run detections
        alerts = []
        
        # M5 detections
        if self._alert_enabled('choch'):
            result = detect_choch_bos(m5_candles, 'M5')
            if result and 'CHOCH' in result.get('type', ''):
                alerts.append(('M5', result))
        
        if self._alert_enabled('liquidity_sweep'):
            result = detect_liquidity_sweep(m5_candles)
            if result:
                alerts.append(('M5', result))
        
        # M15 detections
        if self._alert_enabled('bos'):
            result = detect_choch_bos(m15_candles, 'M15')
            if result and 'BOS' in result.get('type', ''):
                alerts.append(('M15', result))
        
        if self._alert_enabled('order_block'):
            result = detect_order_block(m15_candles)
            if result:
                alerts.append(('M15', result))
        
        if self._alert_enabled('vwap_deviation'):
            min_sigma = self.config.get('alerts', {}).get('vwap_deviation', {}).get('min_sigma', 2.0)
            result = detect_vwap_deviation(m15_candles, min_sigma)
            if result:
                alerts.append(('M15', result))
        
        # BB Squeeze/Expansion - check M15 (primary)
        if self._alert_enabled('bb_squeeze') or self._alert_enabled('bb_expansion'):
            result = detect_bb_state(m15_candles)
            if result:
                if 'SQUEEZE' in result['type'] and self._alert_enabled('bb_squeeze'):
                    alerts.append(('M15', result))
                elif 'EXPANSION' in result['type'] and self._alert_enabled('bb_expansion'):
                    alerts.append(('M15', result))
        
        # BB Expansion - also check M5 if enabled (config allows M5/M15)
        if self._alert_enabled('bb_expansion'):
            result = detect_bb_state(m5_candles)
            if result and 'EXPANSION' in result.get('type', ''):
                # Only add if not already detected on M15 (avoid duplicates)
                existing_m15 = any(tf == 'M15' and d.get('type') == 'BB_EXPANSION' 
                                   for tf, d in alerts)
                if not existing_m15:
                    alerts.append(('M5', result))
        
        if self._alert_enabled('inside_bar'):
            result = detect_inside_bar(m15_candles)
            if result:
                alerts.append(('M15', result))
        
        if self._alert_enabled('rsi_divergence'):
            result = detect_rsi_divergence(m15_candles)
            if result:
                alerts.append(('M15', result))
        
        # H1 detections
        if self._alert_enabled('equal_highs_lows') and h1_candles:
            result = detect_equal_highs_lows(h1_candles)
            if result:
                alerts.append(('H1', result))
        
        # Process and send alerts
        alerts_detected = len(alerts)
        alerts_sent_successfully = 0
        alerts_failed = 0
        
        logger.info(f"🔍 Processing {alerts_detected} detected alert(s) for {symbol}")
        
        for idx, (timeframe, detection) in enumerate(alerts, 1):
            alert_type = detection.get('type', 'UNKNOWN')
            try:
                logger.debug(f"   [{idx}/{alerts_detected}] Processing: {alert_type} {symbol} {timeframe}")
                send_success = await self._send_alert(
                    symbol=symbol,
                    timeframe=timeframe,
                    detection=detection,
                    session=session,
                    h1_trend=h1_trend,
                    volatility=volatility,
                    m5_candles=m5_candles,
                    m15_candles=m15_candles
                )
                if send_success:
                    alerts_sent_successfully += 1
                    logger.info(f"   ✅ [{idx}/{alerts_detected}] {alert_type} {timeframe} sent successfully")
                else:
                    alerts_failed += 1
                    logger.warning(f"   ⚠️ [{idx}/{alerts_detected}] {alert_type} {timeframe} filtered or failed")
            except Exception as e:
                logger.error(f"   ❌ [{idx}/{alerts_detected}] Exception processing {alert_type} {symbol} {timeframe}: {e}", exc_info=True)
                alerts_failed += 1
        
        # Log summary
        if alerts_sent_successfully > 0:
            logger.info(f"✅ Successfully sent {alerts_sent_successfully} alert(s) to Discord for {symbol}")
        if alerts_failed > 0:
            # Only log as error if there were actual webhook failures, not just filtered alerts
            logger.info(f"ℹ️ {alerts_failed} alert(s) for {symbol} were filtered (low confidence, throttled, etc.)")
            logger.debug(f"   → Channel: {self._get_channel_for_symbol(symbol)}")
            logger.debug(f"   → Webhook configured: {'crypto' in self.channel_webhooks}")
        if alerts_detected > 0 and alerts_sent_successfully == 0 and alerts_failed == 0:
            logger.debug(f"Detected {alerts_detected} alert(s) for {symbol} but none were sent (throttled or filtered)")
        
        return alerts_sent_successfully
    
    async def _send_alert(
        self,
        symbol: str,
        timeframe: str,
        detection: Dict[str, Any],
        session: str,
        h1_trend: str,
        volatility: str,
        m5_candles: List[Any],
        m15_candles: List[Any]
    ) -> bool:
        """
        Send an alert to Discord.
        
        Returns:
            True if sent successfully, False otherwise
        """
        """Format and send an alert."""
        alert_type = detection['type']
        
        # Check throttle
        if not self.throttler.can_send(symbol, alert_type):
            logger.debug(f"   ⏸️ Alert throttled (cooldown): {alert_type} {symbol} {timeframe}")
            return False
        
        # Check cross-TF confirmation
        cross_tf_status = self.cross_tf.check(alert_type, m5_candles, m15_candles)
        cross_tf_passed = cross_tf_status == "PASSED"
        
        # Calculate confluence
        direction = detection.get('direction', 'neutral')
        confidence = calculate_confluence(
            alert_type=alert_type,
            direction=direction,
            h1_trend=h1_trend,
            session=session,
            volatility=volatility,
            cross_tf_passed=cross_tf_passed
        )
        
        # Downgrade if cross-TF failed for critical alerts
        if confidence >= 80 and cross_tf_status == "FAILED":
            confidence = 75  # Downgrade to ACTION level
        
        # Get symbol-specific thresholds and apply decay adjustment
        min_confidence = self._get_symbol_threshold(symbol, 'min_confidence')
        actionable_threshold = self._get_symbol_threshold(symbol, 'actionable_threshold')
        
        # Apply confidence decay adjustment if active
        decay_adjustment = self.decay_tracker.get_threshold_adjustment(symbol, alert_type)
        effective_min_confidence = min_confidence + decay_adjustment
        effective_actionable_threshold = actionable_threshold + decay_adjustment
        
        if decay_adjustment > 0:
            logger.debug(
                f"   🔧 Confidence decay active for {symbol} {alert_type}: "
                f"thresholds raised by +{decay_adjustment}% "
                f"(min: {effective_min_confidence}%, actionable: {effective_actionable_threshold}%)"
            )
        
        # Check minimum confidence threshold
        if confidence < effective_min_confidence:
            logger.debug(
                f"   ⏸️ Alert filtered (low confidence): {alert_type} {symbol} {timeframe} "
                f"(confidence: {confidence}% < {effective_min_confidence}%)"
            )
            return False
        
        # Validate detection data
        if 'price' not in detection:
            logger.warning(f"Detection missing 'price' field: {detection}")
            return False
        
        # Create alert data
        alert = AlertData(
            symbol=symbol,
            alert_type=alert_type,
            timeframe=timeframe,
            price=detection.get('price', 0.0),
            confidence=confidence,
            session=session,
            trend=h1_trend,
            volatility=volatility,
            timestamp=datetime.now(timezone.utc),
            notes=detection.get('notes', ''),
            cross_tf_status=cross_tf_status
        )
        
        # Tiered alert handling: 70-79% log only, 80%+ send to Discord
        if 70 <= confidence < effective_actionable_threshold:
            # Informational alert (70-79%) - log only, don't send to Discord
            self._log_informational_alert(alert)
            
            # Register with decay tracker for price movement validation
            self.decay_tracker.register_alert(
                symbol=symbol,
                alert_type=alert_type,
                price=detection.get('price', 0.0),
                direction=direction,
                confidence=confidence
            )
            
            logger.info(
                f"   📝 Informational alert logged (not sent to Discord): {alert_type} {symbol} {timeframe} "
                f"(confidence: {confidence}% < {effective_actionable_threshold}%)"
            )
            return False  # Don't send to Discord
        
        # Actionable alert (80%+) - send to Discord
        # Format message
        message, color, title = self.formatter.format_alert(alert)
        
        # Send to Discord (with channel routing)
        send_success = False
        if self.discord_notifier and self.discord_notifier.enabled:
            channel = self._get_channel_for_symbol(symbol)
            webhook_url = self.channel_webhooks.get(channel)
            
            logger.error(f"📤 Attempting to send {alert_type} alert for {symbol} {timeframe} to channel '{channel}'")
            
            try:
                if webhook_url:
                    # Send to channel-specific webhook
                    logger.error(f"   → Using channel webhook for '{channel}' (URL: {webhook_url[:50]}...)")
                    send_success = await asyncio.to_thread(
                        self._send_to_webhook,
                        webhook_url,
                        message,
                        color,
                        title
                    )
                    if send_success:
                        logger.info(f"   ✅ Webhook send successful")
                    else:
                        logger.error(f"   ❌ Webhook send failed - check logs above for HTTP error details")
                else:
                    # Fallback to default notifier
                    logger.warning(f"   ⚠️ No channel webhook for '{channel}', using default notifier")
                    await asyncio.to_thread(
                        self.discord_notifier.send_message,
                        message,
                        "ALERT",
                        color,
                        "private",
                        title
                    )
                    send_success = True  # Assume success if no exception
                    logger.info(f"   ✅ Default notifier send completed")
            except Exception as e:
                logger.error(f"   ❌ Exception sending alert to Discord: {e}", exc_info=True)
                send_success = False
        else:
            if not self.discord_notifier:
                logger.error(f"❌ Discord notifier is None - alert NOT sent: {alert_type} {symbol} {timeframe}")
            else:
                logger.warning(f"⚠️ Discord notifier disabled - alert NOT sent: {alert_type} {symbol} {timeframe}")
        
        # Record in throttler only if actually sent
        if send_success:
            self.throttler.record_sent(symbol, alert_type)
        
        return send_success
    
    def _get_symbol_threshold(self, symbol: str, threshold_type: str) -> int:
        """Get symbol-specific threshold, falling back to global config."""
        symbol_overrides = self.config.get('symbol_overrides', {})
        symbol_config = symbol_overrides.get(symbol, {})
        
        if threshold_type in symbol_config:
            return symbol_config[threshold_type]
        
        # Fall back to global config
        if threshold_type == 'min_confidence':
            return self.config.get('min_confidence', 70)
        elif threshold_type == 'actionable_threshold':
            return self.config.get('actionable_threshold', self.formatter.ACTIONABLE_CONFIDENCE_THRESHOLD)
        
        # Default fallback
        return 70
    
    def _log_informational_alert(self, alert: AlertData):
        """Log informational alert (70-79% confidence) to file."""
        try:
            # Create daily log file
            date_str = alert.timestamp.strftime('%Y-%m-%d')
            log_file = self.info_alerts_dir / f"{date_str}.jsonl"
            
            # Format alert as JSON line
            alert_dict = {
                "timestamp": alert.timestamp.isoformat(),
                "symbol": alert.symbol,
                "alert_type": alert.alert_type,
                "timeframe": alert.timeframe,
                "confidence": alert.confidence,
                "price": alert.price,
                "session": alert.session,
                "trend": alert.trend,
                "volatility": alert.volatility,
                "cross_tf_status": alert.cross_tf_status,
                "notes": alert.notes
            }
            
            # Append to log file (JSONL format - one JSON object per line)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(alert_dict) + '\n')
            
            logger.debug(f"Logged informational alert to {log_file}")
        except Exception as e:
            logger.error(f"Error logging informational alert: {e}", exc_info=True)
    
    def _calculate_atr_approximation(self, candles: List[Any]) -> float:
        """Calculate ATR approximation from candles."""
        if not candles or len(candles) < 14:
            return 1.0  # Default fallback
        
        try:
            # Calculate True Range for last 14 candles
            true_ranges = []
            for i in range(max(0, len(candles) - 14), len(candles) - 1):
                if i + 1 < len(candles):
                    tr = max(
                        candles[i+1].high - candles[i+1].low,
                        abs(candles[i+1].high - candles[i].close),
                        abs(candles[i+1].low - candles[i].close)
                    )
                    true_ranges.append(tr)
            
            if true_ranges:
                return sum(true_ranges) / len(true_ranges)
            else:
                return 1.0
        except Exception:
            return 1.0
    
    def _alert_enabled(self, alert_category: str) -> bool:
        """Check if alert category is enabled."""
        alerts_config = self.config.get('alerts', {})
        return alerts_config.get(alert_category, {}).get('enabled', True)
    
    def _in_quiet_hours(self) -> bool:
        """Check if current time is in quiet hours."""
        quiet_config = self.config.get('quiet_hours', {})
        
        if not quiet_config.get('enabled', False):
            return False
        
        current_hour = datetime.now(timezone.utc).hour
        start = quiet_config.get('start_utc', 22)
        end = quiet_config.get('end_utc', 6)
        
        if start > end:  # Crosses midnight
            return current_hour >= start or current_hour < end
        else:
            return start <= current_hour < end
    
    def _get_current_session(self) -> str:
        """Get current trading session."""
        try:
            from infra.session_helpers import SessionHelper
            return SessionHelper.get_current_session()
        except ImportError:
            # Fallback
            hour = datetime.now(timezone.utc).hour
            if 0 <= hour < 7:
                return "Asian"
            elif 7 <= hour < 12:
                return "London"
            elif 12 <= hour < 16:
                return "London_NY_Overlap"
            elif 16 <= hour < 21:
                return "New_York"
            else:
                return "Post_NY"
    
    def _get_volatility_state(self, candles: List[Any]) -> str:
        """Get volatility state from candles."""
        if len(candles) < 10:
            return "STABLE"
        
        # Calculate ATR-like measure
        ranges = [c.high - c.low for c in candles[:10]]
        current_range = ranges[0]
        avg_range = sum(ranges) / len(ranges)
        
        if avg_range == 0:
            return "STABLE"  # Cannot determine volatility without range
        
        if current_range > avg_range * 1.5:
            return "EXPANDING"
        elif current_range < avg_range * 0.7:
            return "CONTRACTING"
        else:
            return "STABLE"
    
    def _send_to_webhook(self, webhook_url: str, message: str, color: int, title: str) -> bool:
        """
        Send message to a specific Discord webhook.
        
        Returns:
            True if sent successfully, False otherwise
        """
        import requests
        
        # Validate webhook URL format
        if not webhook_url or not isinstance(webhook_url, str):
            logger.warning(f"Invalid webhook URL: {webhook_url}")
            return False
        
        if not webhook_url.startswith('https://discord.com/api/webhooks/'):
            logger.warning(f"Webhook URL does not match Discord format: {webhook_url[:50]}...")
            return False
        
        data = {
            "embeds": [{
                "title": title,
                "description": message,
                "color": color
            }]
        }
        
        try:
            logger.error(f"   → Sending POST request to webhook...")
            response = requests.post(webhook_url, json=data, timeout=10)
            logger.error(f"   → Webhook response: Status {response.status_code}")
            
            if response.status_code == 204:
                logger.info(f"   ✅ Alert sent to custom webhook successfully (204 No Content)")
                return True
            else:
                error_msg = response.text[:500] if response.text else 'No response body'
                logger.error(
                    f"   ❌ Webhook HTTP error {response.status_code}: {error_msg}"
                )
                logger.error(f"   ❌ Webhook URL (first 80 chars): {webhook_url[:80]}...")
                logger.error(f"   ❌ Request payload size: {len(json.dumps(data))} bytes")
                logger.error(f"   ❌ Common causes: Invalid webhook URL, webhook deleted, rate limit, or message too large")
                return False
        except requests.exceptions.Timeout:
            logger.error(f"   ❌ Webhook request timed out after 10 seconds")
            logger.error(f"   ❌ Webhook URL (first 80 chars): {webhook_url[:80]}...")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"   ❌ Webhook connection error: {e}")
            logger.error(f"   ❌ Webhook URL (first 80 chars): {webhook_url[:80]}...")
            logger.error(f"   ❌ Check internet connection and Discord service status")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"   ❌ Webhook request failed: {e}")
            logger.error(f"   ❌ Webhook URL (first 80 chars): {webhook_url[:80]}...")
            return False
        except Exception as e:
            logger.error(f"   ❌ Unexpected error sending to webhook: {e}", exc_info=True)
            logger.error(f"   ❌ Webhook URL (first 80 chars): {webhook_url[:80]}...")
            return False

