"""
Automatic Signal Detection System
Scans for high-probability trade opportunities and sends notifications
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import json

from infra.mt5_service import MT5Service
from infra.indicator_bridge import IndicatorBridge
from infra.openai_service import OpenAIService
from infra.strategy_selector import select_strategy
from decision_engine import decide_trade
from config import settings

logger = logging.getLogger(__name__)

class SignalScanner:
    """
    IMPROVED: Automatic signal detection system that scans for high-probability trades.
    Only sends notifications for strong signals with high confidence.
    """
    
    def __init__(self, mt5svc: MT5Service, bridge: IndicatorBridge, oai: OpenAIService):
        self.mt5svc = mt5svc
        self.bridge = bridge
        self.oai = oai
        self.last_scan_time = {}
        self.signal_history = {}  # Track recent signals to avoid spam
        
        # Configuration
        self.min_confidence_threshold = 75  # Only high-probability signals
        self.min_rr_ratio = 1.5  # Minimum risk:reward ratio
        self.cooldown_minutes = 30  # Cooldown between signals for same symbol
        self.max_signals_per_hour = 3  # Rate limiting
        
    async def scan_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Scan a single symbol for high-probability trade opportunities.
        Returns signal data if strong signal found, None otherwise.
        """
        try:
            # Check cooldown
            now = time.time()
            if symbol in self.last_scan_time:
                if now - self.last_scan_time[symbol] < (self.cooldown_minutes * 60):
                    return None
            
            # Get market data
            self.mt5svc.ensure_symbol(symbol)
            multi = self.bridge.get_multi(symbol)
            
            if not multi:
                return None
                
            # Build technical context
            tech, _, _ = self._build_tech_context(multi, symbol)
            
            # Extract timeframe data for decision engine
            m5 = tech.get("M5", {})
            m15 = tech.get("M15", {})
            m30 = tech.get("M30", {})
            h1 = tech.get("H1", {})
            
            # Run decision engine with required timeframe arguments
            gate_rec = decide_trade(symbol, m5, m15, m30, h1)
            if not gate_rec:
                return None
                
            # Check if signal is strong enough
            confidence = self._calculate_signal_strength(gate_rec, tech)
            if confidence < self.min_confidence_threshold:
                return None
                
            # Check risk:reward ratio
            rr_ratio = gate_rec.get("rr", 0.0)
            if rr_ratio < self.min_rr_ratio:
                return None
                
            # Check if direction is actionable
            direction = gate_rec.get("direction", "HOLD")
            if direction not in ("BUY", "SELL"):
                return None
                
            # Rate limiting check
            if not self._check_rate_limits(symbol):
                return None
                
            # Update tracking
            self.last_scan_time[symbol] = now
            self._record_signal(symbol, confidence)
            
            return {
                "symbol": symbol,
                "direction": direction,
                "entry": gate_rec.get("entry"),
                "sl": gate_rec.get("sl"),
                "tp": gate_rec.get("tp"),
                "rr": rr_ratio,
                "confidence": confidence,
                "regime": gate_rec.get("regime"),
                "reasoning": gate_rec.get("reasoning", ""),
                "timestamp": now,
                "tech": tech
            }
            
        except Exception as e:
            logger.debug(f"Signal scan failed for {symbol}: {e}")
            return None
    
    def _build_tech_context(self, multi: Dict, symbol: str) -> Tuple[Dict, Dict, Dict]:
        """Build technical context using Feature Builder for enhanced analysis."""
        try:
            # IMPROVED: Use Feature Builder for comprehensive analysis
            from infra.feature_builder import build_features
            feature_data = build_features(symbol, self.mt5svc, self.bridge)
            
            if feature_data and feature_data.get("symbol") == symbol:
                # Use feature builder data
                tech = feature_data
                m5 = feature_data.get("M5", {})
                m15 = feature_data.get("M15", {})
                m30 = feature_data.get("M30", {})
                h1 = feature_data.get("H1", {})
                
                # Ensure tech dict has all timeframes for decision engine
                tech["M5"] = m5
                tech["M15"] = m15
                tech["M30"] = m30
                tech["H1"] = h1
                
                logger.debug(f"Feature builder data used for {symbol}")
            else:
                # Fallback to original method
                m5 = multi.get("M5", {})
                m15 = multi.get("M15", {})
                m30 = multi.get("M30", {})
                h1 = multi.get("H1", {})
                
                tech = {
                    "symbol": symbol,
                    "price": m5.get("close", 0.0),
                    "atr_14": m5.get("atr_14", 0.0),
                    "adx": m5.get("adx_14", 0.0),
                    "rsi_14": m5.get("rsi_14", 50.0),
                    "ema_20": m5.get("ema_20", 0.0),
                    "ema_50": m5.get("ema_50", 0.0),
                    "ema_200": m5.get("ema_200", 0.0),
                    "bb_width": m5.get("bb_width", 0.0),
                    "regime": "VOLATILE",  # Default
                    "_tf_M5": m5,
                    "_tf_M15": m15,
                    "_tf_M30": m30,
                    "_tf_H1": h1
                }
                logger.debug(f"Fallback tech context used for {symbol}")
            
            # Populate detection results (Phase 0.2.2: Tech Dict Integration)
            try:
                from infra.tech_dict_enricher import populate_detection_results
                populate_detection_results(tech, symbol, None, None)
            except Exception as e:
                logger.debug(f"Detection results population failed for {symbol}: {e}")
                # Continue without detection results - graceful degradation
            
            return tech, m5, m15
            
        except Exception as e:
            logger.debug(f"Tech context build failed: {e}")
            return {}, {}, {}
    
    def _calculate_signal_strength(self, gate_rec: Dict, tech: Dict) -> int:
        """
        IMPROVED: Calculate signal strength based on multiple factors.
        Returns confidence score 0-100.
        """
        try:
            base_confidence = 0
            
            # Direction strength
            direction = gate_rec.get("direction", "HOLD")
            if direction in ("BUY", "SELL"):
                base_confidence += 20
            else:
                return 0  # No actionable direction
                
            # Regime alignment
            regime = gate_rec.get("regime", "VOLATILE")
            if regime == "TREND":
                base_confidence += 15
            elif regime == "RANGE":
                base_confidence += 10
            else:  # VOLATILE
                base_confidence += 5
                
            # Technical indicators
            adx = tech.get("adx", 0.0)
            if adx > 30:
                base_confidence += 15
            elif adx > 20:
                base_confidence += 10
            else:
                base_confidence += 5
                
            # RSI confluence
            rsi = tech.get("rsi_14", 50.0)
            if 30 < rsi < 70:  # Not oversold/overbought
                base_confidence += 10
            elif 20 < rsi < 80:  # Reasonable range
                base_confidence += 5
                
            # Risk:Reward ratio
            rr = gate_rec.get("rr", 0.0)
            if rr >= 2.0:
                base_confidence += 20
            elif rr >= 1.5:
                base_confidence += 15
            elif rr >= 1.2:
                base_confidence += 10
            else:
                base_confidence += 5
                
            # Timeframe confluence
            m5_data = tech.get("_tf_M5", {})
            m15_data = tech.get("_tf_M15", {})
            h1_data = tech.get("_tf_H1", {})
            
            # Check ADX alignment across timeframes
            adx_m5 = m5_data.get("adx_14", 0.0)
            adx_m15 = m15_data.get("adx_14", 0.0)
            adx_h1 = h1_data.get("adx_14", 0.0)
            
            strong_tf_count = sum([
                adx_m5 > 25,
                adx_m15 > 25,
                adx_h1 > 25
            ])
            
            if strong_tf_count >= 2:
                base_confidence += 15
            elif strong_tf_count >= 1:
                base_confidence += 10
                
            # RSI alignment across timeframes
            rsi_m5 = m5_data.get("rsi_14", 50.0)
            rsi_m15 = m15_data.get("rsi_14", 50.0)
            rsi_h1 = h1_data.get("rsi_14", 50.0)
            
            # Check for RSI confluence (all pointing same direction)
            rsi_bullish = sum([rsi_m5 > 50, rsi_m15 > 50, rsi_h1 > 50])
            rsi_bearish = sum([rsi_m5 < 50, rsi_m15 < 50, rsi_h1 < 50])
            
            if rsi_bullish >= 2 or rsi_bearish >= 2:
                base_confidence += 10
                
            # Cap at 100
            return min(100, base_confidence)
            
        except Exception as e:
            logger.debug(f"Signal strength calculation failed: {e}")
            return 0
    
    def _check_rate_limits(self, symbol: str) -> bool:
        """Check if we're within rate limits for notifications."""
        try:
            now = time.time()
            hour_ago = now - 3600  # 1 hour ago
            
            # Count signals in last hour
            recent_signals = 0
            for signal_time in self.signal_history.get(symbol, []):
                if signal_time > hour_ago:
                    recent_signals += 1
                    
            return recent_signals < self.max_signals_per_hour
            
        except Exception:
            return True  # Allow if check fails
    
    def _record_signal(self, symbol: str, confidence: int):
        """Record signal for rate limiting."""
        try:
            if symbol not in self.signal_history:
                self.signal_history[symbol] = []
                
            self.signal_history[symbol].append(time.time())
            
            # Keep only last 24 hours
            day_ago = time.time() - 86400
            self.signal_history[symbol] = [
                t for t in self.signal_history[symbol] if t > day_ago
            ]
            
        except Exception:
            pass
    
    def is_market_hours(self) -> bool:
        """
        IMPROVED: Check if we're in active trading hours.
        Returns True if market is likely active.
        """
        try:
            now = datetime.now(timezone.utc)
            hour = now.hour
            weekday = now.weekday()  # 0=Monday, 6=Sunday
            
            # Skip weekends
            if weekday >= 5:  # Saturday, Sunday
                return False
                
            # Major trading sessions (UTC)
            # London: 7-16 UTC
            # New York: 12-21 UTC
            # Tokyo: 23-8 UTC (next day)
            
            # Active hours: 7-21 UTC (London + NY overlap)
            if 7 <= hour <= 21:
                return True
                
            # Tokyo session: 23-8 UTC
            if hour >= 23 or hour <= 8:
                return True
                
            return False
            
        except Exception:
            return True  # Default to active if check fails


async def signal_scanner_job(context):
    """
    IMPROVED: Main signal scanning job.
    Scans configured symbols for high-probability trade opportunities.
    """
    try:
        # Get services from bot data
        mt5svc = context.application.bot_data.get("mt5svc")
        if not mt5svc:
            logger.warning("MT5Service not available for signal scanning")
            return
            
        # Initialize services
        bridge = IndicatorBridge(settings.MT5_FILES_DIR)
        oai = OpenAIService(settings.OPENAI_API_KEY, settings.OPENAI_MODEL)
        scanner = SignalScanner(mt5svc, bridge, oai)
        
        # Check if market is active
        if not scanner.is_market_hours():
            logger.debug("Signal scanner: Market hours check failed")
            return
            
        # Get symbols to scan
        symbols_to_scan = getattr(settings, "SIGNAL_SCANNER_SYMBOLS", ["XAUUSDc", "BTCUSDc", "EURUSDc"])
        
        logger.info(f"Signal scanner: Scanning {len(symbols_to_scan)} symbols")
        
        # Scan each symbol
        for symbol in symbols_to_scan:
            try:
                signal = await scanner.scan_symbol(symbol)
                if signal:
                    await _send_signal_notification(context, signal)
                    
            except Exception as e:
                logger.debug(f"Signal scan failed for {symbol}: {e}")
                
    except Exception as e:
        logger.debug(f"Signal scanner job failed: {e}")


async def _send_signal_notification(context, signal: Dict):
    """
    IMPROVED: Send high-probability signal notification to user.
    """
    try:
        chat_id = getattr(settings, "DEFAULT_NOTIFY_CHAT_ID", 7550446596)
        
        # Format signal message
        symbol = signal["symbol"]
        direction = signal["direction"]
        entry = signal["entry"]
        sl = signal["sl"]
        tp = signal["tp"]
        rr = signal["rr"]
        confidence = signal["confidence"]
        regime = signal["regime"]
        reasoning = signal["reasoning"]
        
        # Create message
        message = (
            f"🚨 **HIGH PROBABILITY SIGNAL DETECTED** 🚨\n\n"
            f"📊 **Symbol:** {symbol}\n"
            f"📈 **Direction:** {direction}\n"
            f"🎯 **Entry:** {entry:.5f}\n"
            f"🛡️ **SL:** {sl:.5f}\n"
            f"🎯 **TP:** {tp:.5f}\n"
            f"📊 **R:R Ratio:** {rr:.2f}\n"
            f"🎯 **Confidence:** {confidence}%\n"
            f"📈 **Regime:** {regime}\n\n"
            f"💡 **Analysis:** {reasoning}\n\n"
            f"⏰ **Detected:** {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"Use /trade {symbol} for full analysis and execution options."
        )
        
        # Send notification
        await context.application.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="Markdown"
        )
        
        logger.info(f"High-probability signal sent: {symbol} {direction} (Confidence: {confidence}%)")
        
    except Exception as e:
        logger.debug(f"Signal notification failed: {e}")


def register_signal_scanner(app, mt5svc):
    """
    IMPROVED: Register signal scanner with the bot.
    """
    try:
        # Store MT5 service in bot data
        app.bot_data["mt5svc"] = mt5svc
        
        # Schedule signal scanner job
        scan_interval = getattr(settings, "SIGNAL_SCANNER_INTERVAL", 300)  # 5 minutes
        app.job_queue.run_repeating(
            signal_scanner_job,
            interval=scan_interval,
            first=60,  # Start after 1 minute
            name="_signal_scanner"
        )
        
        logger.info(f"Signal scanner registered: every {scan_interval}s")
        
    except Exception as e:
        logger.warning(f"Signal scanner registration failed: {e}")
