"""
Auto-Alert Generator - Tier 3 Enhancement
Automatically creates alerts for high-confluence trading setups.

Detects high-confidence setups (≥85 confidence) with multiple confluence factors
and creates alerts that can be monitored by the existing alert/execution system.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AutoAlertConfig:
    """Configuration for auto-alert generation"""
    enabled: bool = False
    min_confidence: int = 85
    notification_only: bool = True
    symbols: List[str] = None
    max_alerts_per_day: int = 3
    cooldown_minutes: int = 30
    require_pattern_confirmation: bool = False
    require_volume_expansion: bool = True
    require_mtf_alignment: bool = True
    require_structure_confirmation: bool = True
    discord_notification: bool = True
    
    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ["BTCUSDc", "XAUUSDc"]


class AutoAlertGenerator:
    """
    Generates automatic alerts for high-confluence trading setups.
    
    Features:
    - Strict thresholds (≥85 confidence required)
    - Multiple confluence checks (pattern, volume, MTF alignment, structure)
    - Cooldown periods to prevent duplicate alerts
    - Daily limits per symbol
    - User opt-in only (default disabled)
    """
    
    def __init__(self, config_path: str = "config/auto_alert_config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.alert_history: Dict[str, List[datetime]] = {}  # symbol -> list of alert timestamps
        self.cooldown_cache: Dict[str, datetime] = {}  # (symbol, pattern_type) -> last alert time
        logger.info(f"AutoAlertGenerator initialized (enabled: {self.config.enabled})")
    
    def _load_config(self) -> AutoAlertConfig:
        """Load configuration from JSON file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config_dict = json.load(f)
                    return AutoAlertConfig(**config_dict)
            else:
                # Create default config file
                default_config = AutoAlertConfig()
                self._save_config(default_config)
                logger.info(f"Created default auto-alert config at {self.config_path}")
                return default_config
        except Exception as e:
            logger.error(f"Error loading auto-alert config: {e}")
            return AutoAlertConfig()  # Return defaults on error
    
    def _save_config(self, config: AutoAlertConfig):
        """Save configuration to JSON file"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            config_dict = {
                "enabled": config.enabled,
                "min_confidence": config.min_confidence,
                "notification_only": config.notification_only,
                "symbols": config.symbols,
                "max_alerts_per_day": config.max_alerts_per_day,
                "cooldown_minutes": config.cooldown_minutes,
                "require_pattern_confirmation": config.require_pattern_confirmation,
                "require_volume_expansion": config.require_volume_expansion,
                "require_mtf_alignment": config.require_mtf_alignment,
                "require_structure_confirmation": config.require_structure_confirmation,
                "discord_notification": config.discord_notification
            }
            with open(self.config_path, 'w') as f:
                json.dump(config_dict, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving auto-alert config: {e}")
    
    def should_create_alert(
        self,
        analysis_result: Dict[str, Any],
        symbol: str,
        confidence_score: int,
        features_data: Dict[str, Any],
        m5_data: Dict,
        m15_data: Dict,
        order_flow: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Determine if an alert should be created based on confluence criteria.
        
        Returns:
            True if all conditions are met, False otherwise
        """
        if not self.config.enabled:
            return False
        
        # Check if symbol is enabled
        if symbol not in self.config.symbols:
            return False
        
        # 1. Confidence threshold
        if confidence_score < self.config.min_confidence:
            logger.debug(f"Auto-alert: Confidence {confidence_score} < {self.config.min_confidence}")
            return False
        
        # 2. Pattern confirmation (if required)
        if self.config.require_pattern_confirmation:
            if not self._check_pattern_confirmation(features_data):
                logger.debug("Auto-alert: Pattern not confirmed")
                return False
        
        # 3. Multi-timeframe alignment (if required)
        if self.config.require_mtf_alignment:
            if not self._check_mtf_alignment(features_data):
                logger.debug("Auto-alert: MTF not aligned")
                return False
        
        # 4. Volume expansion (if required)
        if self.config.require_volume_expansion:
            if not self._check_volume_expansion(m5_data, m15_data):
                logger.debug("Auto-alert: Volume not expanding")
                return False
        
        # 5. Structure confirmation (if required)
        if self.config.require_structure_confirmation:
            if not self._check_structure_confirmation(analysis_result):
                logger.debug("Auto-alert: Structure not confirmed")
                return False
        
        # 6. Check cooldown
        pattern_type = self._extract_pattern_type(features_data)
        if not self.check_cooldown(symbol, pattern_type):
            logger.debug(f"Auto-alert: In cooldown for {symbol} {pattern_type}")
            return False
        
        # 7. Check daily limit
        if not self.check_daily_limit(symbol):
            logger.debug(f"Auto-alert: Daily limit reached for {symbol}")
            return False
        
        return True
    
    def _check_pattern_confirmation(self, features_data: Dict[str, Any]) -> bool:
        """Check if a pattern is confirmed"""
        try:
            from infra.pattern_tracker import get_pattern_tracker
            pattern_tracker = get_pattern_tracker()
            
            # Check for confirmed patterns across timeframes
            for tf in ["H1", "M30", "M15", "M5"]:
                tf_features = features_data.get(tf, {})
                pattern_flags = tf_features.get("pattern_flags", {})
                candlestick_flags = tf_features.get("candlestick_flags", {})
                
                # Check for multi-bar patterns
                if pattern_flags.get("morning_star") or pattern_flags.get("evening_star"):
                    pattern_type = "Morning Star" if pattern_flags.get("morning_star") else "Evening Star"
                    # Simplified check - in real implementation, would check tracker
                    pattern_strength = tf_features.get("pattern_strength", 0.0)
                    if pattern_strength > 0.8:
                        return True
                
                # Check pattern strength
                pattern_strength = tf_features.get("pattern_strength", 0.0)
                if pattern_strength > 0.8:
                    return True
            
            return False
        except Exception as e:
            logger.debug(f"Pattern confirmation check failed: {e}")
            return False
    
    def _check_mtf_alignment(self, features_data: Dict[str, Any]) -> bool:
        """Check if multiple timeframes are aligned (all bullish or all bearish)"""
        try:
            h1_features = features_data.get("H1", {})
            m15_features = features_data.get("M15", {})
            m5_features = features_data.get("M5", {})
            
            # Check trend direction (simplified - would use actual SMC structure)
            # For now, check pattern bias direction
            h1_bias = self._extract_timeframe_bias(h1_features)
            m15_bias = self._extract_timeframe_bias(m15_features)
            m5_bias = self._extract_timeframe_bias(m5_features)
            
            # All should be same direction (bullish or bearish, not neutral)
            if h1_bias != "neutral" and m15_bias != "neutral" and m5_bias != "neutral":
                return h1_bias == m15_bias == m5_bias
            
            return False
        except Exception as e:
            logger.debug(f"MTF alignment check failed: {e}")
            return False
    
    def _extract_timeframe_bias(self, tf_features: Dict) -> str:
        """Extract bias direction from timeframe features (bullish/bearish/neutral)"""
        pattern_flags = tf_features.get("pattern_flags", {})
        candlestick_flags = tf_features.get("candlestick_flags", {})
        
        # Bullish patterns
        if (pattern_flags.get("morning_star") or pattern_flags.get("bull_engulfing") or
            candlestick_flags.get("marubozu_bull") or candlestick_flags.get("hammer")):
            return "bullish"
        
        # Bearish patterns
        if (pattern_flags.get("evening_star") or pattern_flags.get("bear_engulfing") or
            candlestick_flags.get("marubozu_bear") or candlestick_flags.get("shooting_star")):
            return "bearish"
        
        return "neutral"
    
    def _check_volume_expansion(self, m5_data: Dict, m15_data: Dict) -> bool:
        """Check if volume is expanding (>1.2x average)"""
        try:
            m5_volume = m5_data.get('volume', 0) or 0
            m5_volume_ma = m5_data.get('volume_ma_20', 0) or 0
            
            if m5_volume_ma > 0:
                volume_ratio = m5_volume / m5_volume_ma
                return volume_ratio > 1.2
            
            return False
        except Exception as e:
            logger.debug(f"Volume expansion check failed: {e}")
            return False
    
    def _check_structure_confirmation(self, analysis_result: Dict[str, Any]) -> bool:
        """Check if structure is confirmed (BOS for trend, CHOCH for reversal)"""
        try:
            # Extract structure information from analysis
            bos_detected = analysis_result.get("bos_detected", False)
            choch_detected = analysis_result.get("choch_detected", False)
            structure_trend = analysis_result.get("structure_trend", "")
            
            # BOS confirms trend continuation
            if bos_detected and structure_trend in ["BULLISH", "BEARISH"]:
                return True
            
            # CHOCH confirms reversal
            if choch_detected:
                return True
            
            return False
        except Exception as e:
            logger.debug(f"Structure confirmation check failed: {e}")
            return False
    
    def _extract_pattern_type(self, features_data: Dict[str, Any]) -> str:
        """Extract the primary pattern type for cooldown tracking"""
        # Check for multi-bar patterns first (higher priority)
        for tf in ["H1", "M30", "M15", "M5"]:
            tf_features = features_data.get(tf, {})
            pattern_flags = tf_features.get("pattern_flags", {})
            
            if pattern_flags.get("morning_star"):
                return "morning_star"
            elif pattern_flags.get("evening_star"):
                return "evening_star"
            elif pattern_flags.get("bull_engulfing"):
                return "bull_engulfing"
            elif pattern_flags.get("bear_engulfing"):
                return "bear_engulfing"
        
        return "general"
    
    def check_cooldown(self, symbol: str, pattern_type: str) -> bool:
        """Check if alert is in cooldown period"""
        cache_key = f"{symbol}_{pattern_type}"
        last_alert_time = self.cooldown_cache.get(cache_key)
        
        if last_alert_time:
            cooldown_end = last_alert_time + timedelta(minutes=self.config.cooldown_minutes)
            if datetime.now(timezone.utc) < cooldown_end:
                return False
        
        return True
    
    def check_daily_limit(self, symbol: str) -> bool:
        """Check if daily alert limit has been reached"""
        today = datetime.now(timezone.utc).date()
        symbol_history = self.alert_history.get(symbol, [])
        
        # Filter to today's alerts
        today_alerts = [
            alert_time for alert_time in symbol_history
            if alert_time.date() == today
        ]
        
        return len(today_alerts) < self.config.max_alerts_per_day
    
    def generate_alert_details(
        self,
        symbol: str,
        analysis_result: Dict[str, Any],
        confidence_score: int,
        features_data: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """Generate alert details from analysis result"""
        pattern_type = self._extract_pattern_type(features_data)
        
        # Extract key information
        confluence_verdict = analysis_result.get("confluence_verdict", "")
        structure_trend = analysis_result.get("structure_trend", "")
        pattern_summary = analysis_result.get("pattern_summary", "")
        
        # Build description
        description = f"🤖 AUTO: High-confluence setup detected"
        if pattern_type != "general":
            description += f" ({pattern_type.replace('_', ' ').title()})"
        
        # Build parameters for alert
        parameters = {
            "auto_detected": True,
            "confidence_score": confidence_score,
            "pattern_type": pattern_type,
            "structure_trend": structure_trend,
            "current_price": current_price,
            "confluence_verdict": confluence_verdict
        }
        
        return {
            "symbol": symbol,
            "alert_type": "structure",
            "condition": "detected",
            "description": description,
            "parameters": parameters
        }
    
    def create_alert(
        self,
        alert_details: Dict[str, Any],
        alert_manager
    ) -> Optional[Any]:
        """
        Create an alert using the alert manager.
        
        Args:
            alert_details: Alert details from generate_alert_details()
            alert_manager: CustomAlertManager instance
        
        Returns:
            Created alert object or None if failed
        """
        try:
            symbol = alert_details["symbol"]
            pattern_type = alert_details["parameters"].get("pattern_type", "general")
            
            # Create alert
            alert = alert_manager.add_alert(
                symbol=symbol,
                alert_type=alert_details["alert_type"],
                condition=alert_details["condition"],
                description=alert_details["description"],
                parameters=alert_details["parameters"],
                expires_hours=24,  # Auto-alerts expire after 24 hours
                one_time=True  # Auto-alerts are one-time
            )
            
            # Update cooldown cache
            cache_key = f"{symbol}_{pattern_type}"
            self.cooldown_cache[cache_key] = datetime.now(timezone.utc)
            
            # Update alert history
            if symbol not in self.alert_history:
                self.alert_history[symbol] = []
            self.alert_history[symbol].append(datetime.now(timezone.utc))
            
            logger.info(f"🤖 Auto-alert created: {alert.description} ({alert.alert_id})")
            
            return alert
            
        except Exception as e:
            logger.error(f"Error creating auto-alert: {e}", exc_info=True)
            return None
    
    async def send_discord_notification(
        self,
        alert: Any,
        symbol: str,
        confidence_score: int,
        confluence_verdict: str
    ):
        """Send Discord notification for auto-alert"""
        if not self.config.discord_notification:
            return
        
        try:
            from discord_notifications import DiscordNotifier
            notifier = DiscordNotifier()
            
            if notifier.enabled:
                message = (
                    f"🤖 **Auto-Alert Created**\n\n"
                    f"**Symbol:** {symbol}\n"
                    f"**Confidence:** {confidence_score}/100\n"
                    f"**Description:** {alert.description}\n"
                    f"**Confluence:** {confluence_verdict}\n\n"
                    f"*This alert was automatically detected. Review before execution.*"
                )
                
                await notifier.send_message(
                    message,
                    message_type="ALERT",
                    channel="private"
                )
                
                logger.info(f"Discord notification sent for auto-alert: {alert.alert_id}")
        except Exception as e:
            logger.debug(f"Discord notification failed for auto-alert: {e}")

