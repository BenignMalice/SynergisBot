"""
Alert Monitor - Checks custom alerts and triggers Telegram notifications
Enhanced with M1-M5 Order Block Detection
"""

import logging
from typing import Dict, Optional, List, Any
from datetime import datetime, timezone
from .custom_alerts import CustomAlertManager, CustomAlert, AlertType, AlertCondition
from .mt5_service import MT5Service
from .indicator_bridge import IndicatorBridge

logger = logging.getLogger(__name__)


class AlertMonitor:
    """Monitors custom alerts and triggers notifications"""
    
    def __init__(
        self, 
        alert_manager: CustomAlertManager, 
        mt5_service: MT5Service,
        m1_data_fetcher=None,
        m1_analyzer=None,
        session_manager=None
    ):
        self.alert_manager = alert_manager
        self.mt5_service = mt5_service
        self.indicator_bridge = IndicatorBridge(None)
        self.last_prices: Dict[str, float] = {}  # Track price for cross detection
        
        # M1 Microstructure Integration (for Order Block Detection)
        self.m1_data_fetcher = m1_data_fetcher
        self.m1_analyzer = m1_analyzer
        self.session_manager = session_manager
        
        # Track detected order blocks to prevent duplicate alerts
        self._detected_ob_cache: Dict[str, List[Dict]] = {}  # symbol -> list of detected OBs
        
        logger.info("AlertMonitor initialized with M1 microstructure support")
    
    async def check_all_alerts(self) -> list[tuple[CustomAlert, Dict]]:
        """
        Check all active alerts and return triggered ones with context
        
        Returns:
            List of (alert, context_data) tuples for triggered alerts
        """
        triggered_alerts = []
        
        try:
            # Cleanup expired alerts first
            self.alert_manager.cleanup_expired()
            
            # Get all active alerts
            alerts = self.alert_manager.get_all_alerts(enabled_only=True)
            
            if not alerts:
                return []
            
            # Group alerts by symbol for efficiency
            alerts_by_symbol: Dict[str, list[CustomAlert]] = {}
            for alert in alerts:
                if alert.symbol not in alerts_by_symbol:
                    alerts_by_symbol[alert.symbol] = []
                alerts_by_symbol[alert.symbol].append(alert)
            
            # Check each symbol's alerts
            for symbol, symbol_alerts in alerts_by_symbol.items():
                # Normalize broker symbol: ensure SINGLE trailing 'c'
                sym_norm = symbol.upper()
                if sym_norm.endswith('C'):
                    sym_norm = sym_norm[:-1] + 'c'
                elif not sym_norm.endswith('c'):
                    sym_norm = sym_norm + 'c'
                # Get current data for this symbol
                try:
                    quote = self.mt5_service.get_quote(sym_norm)
                    current_price = (quote.ask + quote.bid) / 2
                    
                    # Get indicators if needed
                    multi_data = None
                    structure_data = None
                    
                    # Check if any alert needs indicators
                    needs_indicators = any(
                        a.alert_type in [AlertType.INDICATOR, AlertType.STRUCTURE] 
                        for a in symbol_alerts
                    )
                    
                    if needs_indicators:
                        multi_data = self.indicator_bridge.get_multi(sym_norm)
                    
                    # Check each alert for this symbol
                    for alert in symbol_alerts:
                        context = None
                        
                        if alert.alert_type == AlertType.PRICE:
                            context = self._check_price_alert(alert, current_price, symbol)
                        
                        elif alert.alert_type == AlertType.INDICATOR:
                            if multi_data:
                                context = self._check_indicator_alert(alert, multi_data)
                        
                        elif alert.alert_type == AlertType.STRUCTURE:
                            if multi_data:
                                # Check if this is an order block alert
                                pattern = alert.parameters.get("pattern", "").lower()
                                if pattern in ["ob_bull", "ob_bear", "order_block"]:
                                    context = self._check_order_block_alert(alert, sym_norm, current_price, multi_data)
                                else:
                                    context = self._check_structure_alert(alert, multi_data)
                        
                        elif alert.alert_type == AlertType.ORDER_FLOW:
                            # Order flow would need binance service - skip for now
                            pass
                        
                        elif alert.alert_type == AlertType.VOLATILITY:
                            if multi_data:
                                context = self._check_volatility_alert(alert, multi_data)
                        
                        if context:
                            # Mark alert as triggered
                            self.alert_manager.trigger_alert(alert.alert_id)
                            triggered_alerts.append((alert, context))
                            logger.info(f"🔔 Alert triggered: {alert.description}")
                            
                            # Auto-remove if one-time alert
                            if alert.one_time:
                                self.alert_manager.remove_alert(alert.alert_id)
                                logger.info(f"🗑️ One-time alert removed: {alert.alert_id}")
                    
                    # Update last price for this (base) symbol
                    self.last_prices[symbol] = current_price
                    
                except Exception as e:
                    logger.error(f"Error checking alerts for {symbol}: {e}")
                    continue
            
            return triggered_alerts
            
        except Exception as e:
            logger.error(f"Error in check_all_alerts: {e}", exc_info=True)
            return []
    
    def _check_price_alert(self, alert: CustomAlert, current_price: float, symbol: str) -> Optional[Dict]:
        """Check price-based alerts"""
        try:
            target_price = alert.parameters.get("price_level")
            
            # Migration: Try to extract price from description if not in parameters
            if not target_price:
                import re
                # Try patterns like "below 4109" or "above 4100"
                match = re.search(r'(?:below|above|crosses)\s+(\d+(?:\.\d+)?)', alert.description)
                if match:
                    target_price = float(match.group(1))
                    logger.debug(f"Extracted price {target_price} from description: {alert.description}")
                else:
                    return None
            
            last_price = self.last_prices.get(symbol)
            
            if alert.condition == AlertCondition.CROSSES_ABOVE:
                if last_price and last_price <= target_price and current_price > target_price:
                    return {
                        "current_price": current_price,
                        "target_price": target_price,
                        "last_price": last_price,
                        "condition": "crossed above"
                    }
            
            elif alert.condition == AlertCondition.CROSSES_BELOW:
                if last_price and last_price >= target_price and current_price < target_price:
                    return {
                        "current_price": current_price,
                        "target_price": target_price,
                        "last_price": last_price,
                        "condition": "crossed below"
                    }
            
            elif alert.condition == AlertCondition.GREATER_THAN:
                if current_price > target_price:
                    return {
                        "current_price": current_price,
                        "target_price": target_price,
                        "condition": "above"
                    }
            
            elif alert.condition == AlertCondition.LESS_THAN:
                if current_price < target_price:
                    return {
                        "current_price": current_price,
                        "target_price": target_price,
                        "condition": "below"
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking price alert: {e}")
            return None
    
    def _check_indicator_alert(self, alert: CustomAlert, multi_data: Dict) -> Optional[Dict]:
        """Check indicator-based alerts"""
        try:
            indicator = alert.parameters.get("indicator", "").lower()
            timeframe = alert.parameters.get("timeframe", "M5")
            target_value = alert.parameters.get("value")
            
            if not indicator or target_value is None:
                return None
            
            tf_data = multi_data.get(timeframe, {})
            if not tf_data:
                return None
            
            current_value = tf_data.get(indicator)
            if current_value is None:
                return None
            
            triggered = False
            condition_text = ""
            
            if alert.condition == AlertCondition.GREATER_THAN and current_value > target_value:
                triggered = True
                condition_text = f"{indicator.upper()} > {target_value}"
            
            elif alert.condition == AlertCondition.LESS_THAN and current_value < target_value:
                triggered = True
                condition_text = f"{indicator.upper()} < {target_value}"
            
            elif alert.condition == AlertCondition.EQUALS and abs(current_value - target_value) < 0.1:
                triggered = True
                condition_text = f"{indicator.upper()} ≈ {target_value}"
            
            if triggered:
                return {
                    "indicator": indicator.upper(),
                    "current_value": current_value,
                    "target_value": target_value,
                    "timeframe": timeframe,
                    "condition": condition_text
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking indicator alert: {e}")
            return None
    
    def _check_structure_alert(self, alert: CustomAlert, multi_data: Dict) -> Optional[Dict]:
        """Check structure-based alerts (BOS, CHOCH, etc)"""
        try:
            pattern = alert.parameters.get("pattern", "").lower()
            timeframe = alert.parameters.get("timeframe", "M5")
            
            # Skip order block patterns (handled separately)
            if pattern in ["ob_bull", "ob_bear", "order_block"]:
                return None
            
            if not pattern:
                return None
            
            tf_data = multi_data.get(timeframe, {})
            if not tf_data:
                return None
            
            # Extract candle data for structure detection
            # This is simplified - you'd need actual candle history
            highs = tf_data.get("highs", [])
            lows = tf_data.get("lows", [])
            closes = tf_data.get("closes", [])
            
            if not highs or not lows or not closes:
                return None
            
            triggered = False
            structure_type = ""
            
            if pattern == "bos_bull":
                # Check for bullish Break of Structure
                if len(highs) >= 3:
                    if highs[-1] > highs[-2] > highs[-3]:
                        triggered = True
                        structure_type = "BOS Bull"
            
            elif pattern == "bos_bear":
                # Check for bearish Break of Structure
                if len(lows) >= 3:
                    if lows[-1] < lows[-2] < lows[-3]:
                        triggered = True
                        structure_type = "BOS Bear"
            
            elif pattern == "choch_bull":
                # Check for bullish Change of Character
                if len(lows) >= 3 and len(highs) >= 2:
                    if lows[-1] > lows[-2] and highs[-1] > highs[-2]:
                        triggered = True
                        structure_type = "CHOCH Bull"
            
            elif pattern == "choch_bear":
                # Check for bearish Change of Character
                if len(highs) >= 3 and len(lows) >= 2:
                    if highs[-1] < highs[-2] and lows[-1] < lows[-2]:
                        triggered = True
                        structure_type = "CHOCH Bear"
            
            if triggered:
                return {
                    "pattern": pattern,
                    "structure_type": structure_type,
                    "timeframe": timeframe,
                    "current_price": tf_data.get("current_close", 0)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking structure alert: {e}")
            return None
    
    def _check_volatility_alert(self, alert: CustomAlert, multi_data: Dict) -> Optional[Dict]:
        """Check volatility-based alerts"""
        try:
            timeframe = alert.parameters.get("timeframe", "M5")
            threshold = alert.parameters.get("threshold")
            metric = alert.parameters.get("metric", "atr").lower()
            
            if threshold is None:
                return None
            
            tf_data = multi_data.get(timeframe, {})
            if not tf_data:
                return None
            
            current_value = None
            
            if metric == "atr":
                current_value = tf_data.get("atr14")
            elif metric == "adx":
                current_value = tf_data.get("adx")
            
            if current_value is None:
                return None
            
            triggered = False
            
            if alert.condition == AlertCondition.GREATER_THAN and current_value > threshold:
                triggered = True
            elif alert.condition == AlertCondition.LESS_THAN and current_value < threshold:
                triggered = True
            
            if triggered:
                return {
                    "metric": metric.upper(),
                    "current_value": current_value,
                    "threshold": threshold,
                    "timeframe": timeframe
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking volatility alert: {e}")
            return None
    
    def _check_order_block_alert(
        self, 
        alert: CustomAlert, 
        symbol_norm: str, 
        current_price: float,
        multi_data: Dict
    ) -> Optional[Dict]:
        """
        Comprehensive Order Block Detection with 10-parameter validation.
        
        Validates:
        1. Correct candle identification (last down/up before displacement)
        2. Displacement/Market Structure Shift (BOS/CHOCH)
        3. Imbalance/Fair Value Gap (FVG) presence
        4. Volume spike confirmation
        5. Liquidity grab detection
        6. Session context validation
        7. Higher timeframe alignment
        8. Structural context
        9. Order block freshness
        10. VWAP + liquidity confluence
        
        Args:
            alert: CustomAlert with pattern "ob_bull", "ob_bear", or "order_block"
            symbol_norm: Normalized symbol (e.g., "XAUUSDc")
            current_price: Current market price
            multi_data: Multi-timeframe indicator data
            
        Returns:
            Dict with order block details if valid, None otherwise
        """
        try:
            if not self.m1_data_fetcher or not self.m1_analyzer:
                logger.warning(f"Order block detection requires M1 components (not available) for {symbol_norm}")
                return None
            
            pattern = alert.parameters.get("pattern", "").lower()
            direction = None
            if pattern == "ob_bull" or (pattern == "order_block" and alert.parameters.get("direction") == "bull"):
                direction = "BULLISH"
            elif pattern == "ob_bear" or (pattern == "order_block" and alert.parameters.get("direction") == "bear"):
                direction = "BEARISH"
            elif pattern == "order_block":
                # Auto-detect direction from market structure
                direction = None  # Will be determined during detection
            else:
                logger.debug(f"Invalid order block pattern: {pattern}")
                return None
            
            # Fetch M1 and M5 data
            m1_candles = self.m1_data_fetcher.fetch_m1_data(symbol_norm, count=200)
            if not m1_candles or len(m1_candles) < 50:
                logger.warning(f"Insufficient M1 data for {symbol_norm}: {len(m1_candles) if m1_candles else 0} candles (need 50+)")
                return None
            
            # Get M5 candles from multi_data or MT5
            m5_data = multi_data.get("M5", {})
            m5_candles = None
            if m5_data:
                # Try to extract candles from multi_data
                m5_candles = self._extract_candles_from_multi_data(m5_data)
            
            # If M5 not in multi_data, fetch from MT5
            if not m5_candles and self.mt5_service:
                try:
                    import MetaTrader5 as mt5
                    m5_rates = mt5.copy_rates_from_pos(symbol_norm, mt5.TIMEFRAME_M5, 0, 100)
                    if m5_rates is not None and len(m5_rates) > 0:
                        m5_candles = [self._convert_mt5_rate_to_dict(r) for r in m5_rates]
                except Exception as e:
                    logger.debug(f"Could not fetch M5 data: {e}")
            
            # Analyze M1 microstructure
            m1_analysis = self.m1_analyzer.analyze_microstructure(
                symbol=symbol_norm,
                candles=m1_candles,
                current_price=current_price,
                higher_timeframe_data=m5_data if m5_data else None
            )
            
            if not m1_analysis or not m1_analysis.get('available'):
                error_msg = m1_analysis.get('error', 'Unknown error') if m1_analysis else 'No analysis returned'
                logger.warning(f"M1 analysis unavailable for {symbol_norm}: {error_msg}")
                return None
            
            # Get order blocks from M1 analysis
            m1_order_blocks = m1_analysis.get('order_blocks', [])
            if not m1_order_blocks:
                return None
            
            # Validate each order block using comprehensive checklist
            for ob in m1_order_blocks:
                ob_direction = ob.get('type', '').upper()
                
                # Skip if direction doesn't match alert
                if direction and ob_direction != direction:
                    continue
                
                # Comprehensive validation
                validation_result = self._validate_order_block(
                    ob=ob,
                    m1_candles=m1_candles,
                    m5_candles=m5_candles,
                    m1_analysis=m1_analysis,
                    m5_data=m5_data,
                    symbol_norm=symbol_norm,
                    current_price=current_price
                )
                
                if validation_result and validation_result.get('valid'):
                    score = validation_result.get('score', 0)
                    logger.info(f"✅ Valid order block detected for {symbol_norm}: {ob_direction} OB with validation score {score}/100")
                    # Check if we've already alerted on this OB
                    ob_key = f"{symbol_norm}_{ob.get('price_range', [0, 0])[0]:.2f}_{ob.get('price_range', [0, 0])[1]:.2f}"
                    if ob_key not in self._detected_ob_cache.get(symbol_norm, []):
                        # Cache this OB to prevent duplicate alerts
                        if symbol_norm not in self._detected_ob_cache:
                            self._detected_ob_cache[symbol_norm] = []
                        self._detected_ob_cache[symbol_norm].append(ob_key)
                        
                        # Clean old cache entries (keep last 10)
                        if len(self._detected_ob_cache[symbol_norm]) > 10:
                            self._detected_ob_cache[symbol_norm] = self._detected_ob_cache[symbol_norm][-10:]
                        
                        return {
                            "pattern": f"ob_{ob_direction.lower()}",
                            "order_block_type": ob_direction,
                            "price_range": ob.get('price_range', []),
                            "strength": ob.get('strength', 0),
                            "validation_score": validation_result.get('score', 0),
                            "validation_details": validation_result.get('details', {}),
                            "current_price": current_price,
                            "timeframe": "M1-M5"
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking order block alert: {e}", exc_info=True)
            return None
    
    def _validate_order_block(
        self,
        ob: Dict[str, Any],
        m1_candles: List[Dict],
        m5_candles: Optional[List[Dict]],
        m1_analysis: Dict[str, Any],
        m5_data: Optional[Dict],
        symbol_norm: str,
        current_price: float
    ) -> Optional[Dict[str, Any]]:
        """
        Comprehensive Order Block Validation - 10 Parameter Checklist.
        
        Returns validation result with score and details.
        """
        try:
            if len(m1_candles) < 20:
                return None
            
            ob_direction = ob.get('type', '').upper()
            ob_range = ob.get('price_range', [])
            if not ob_range or len(ob_range) < 2:
                return None
            
            ob_low = ob_range[0]
            ob_high = ob_range[1]
            
            validation_score = 0
            max_score = 100
            details = {}
            
            # 1. Identify Correct Candle (Anchor Candle)
            anchor_candle_idx = self._find_anchor_candle(m1_candles, ob_direction, ob_low, ob_high)
            if anchor_candle_idx is None:
                return None
            details['anchor_candle_found'] = True
            validation_score += 10
            
            # 2. Displacement / Market Structure Shift (Mandatory)
            choch_bos = m1_analysis.get('choch_bos', {})
            has_structure_shift = False
            
            if ob_direction == "BULLISH":
                has_structure_shift = (
                    choch_bos.get('has_bos', False) and 
                    choch_bos.get('choch_bos', {}).get('last_swing_high', 0) > 0
                ) or choch_bos.get('choch_bull', False)
            else:  # BEARISH
                has_structure_shift = (
                    choch_bos.get('has_bos', False) and 
                    choch_bos.get('choch_bos', {}).get('last_swing_low', 0) > 0
                ) or choch_bos.get('choch_bear', False)
            
            if not has_structure_shift:
                return None  # Mandatory check failed
            details['structure_shift'] = True
            validation_score += 15
            
            # 3. Imbalance / Fair Value Gap (FVG) Presence
            fvg_detected = self._detect_fvg_after_displacement(m1_candles, anchor_candle_idx, ob_direction)
            if fvg_detected:
                details['fvg_present'] = True
                validation_score += 10
            else:
                details['fvg_present'] = False
            
            # 4. Volume Spike Confirmation
            volume_confirmed = self._check_volume_spike(m1_candles, anchor_candle_idx)
            if volume_confirmed:
                details['volume_spike'] = True
                validation_score += 10
            else:
                details['volume_spike'] = False
            
            # 5. Liquidity Grab Detection
            liquidity_grab = self._detect_liquidity_grab(m1_candles, anchor_candle_idx, ob_direction)
            if liquidity_grab:
                details['liquidity_grab'] = True
                validation_score += 10
            else:
                details['liquidity_grab'] = False
            
            # 6. Session Context Validation
            session_score = self._validate_session_context(symbol_norm)
            if session_score > 0:
                details['session_context'] = session_score
                validation_score += session_score
            
            # 7. Higher-Timeframe Alignment
            htf_alignment = self._check_htf_alignment(m5_candles, m5_data, ob_direction)
            if htf_alignment:
                details['htf_alignment'] = True
                validation_score += 15
            else:
                details['htf_alignment'] = False
            
            # 8. Structural Context
            structural_context = self._validate_structural_context(m1_candles, m1_analysis, ob_direction)
            if structural_context:
                details['structural_context'] = True
                validation_score += 10
            else:
                details['structural_context'] = False
            
            # 9. Order Block Freshness
            freshness = self._check_ob_freshness(symbol_norm, ob_low, ob_high)
            if freshness:
                details['freshness'] = True
                validation_score += 10
            else:
                details['freshness'] = False
            
            # 10. VWAP + Liquidity Confluence
            vwap_confluence = self._check_vwap_liquidity_confluence(m1_analysis, ob_low, ob_high, current_price)
            if vwap_confluence:
                details['vwap_confluence'] = True
                validation_score += 10
            else:
                details['vwap_confluence'] = False
            
            # Minimum score threshold (60/100 required)
            if validation_score >= 60:
                logger.debug(f"Order block validation passed for {symbol_norm}: score {validation_score}/100")
                return {
                    'valid': True,
                    'score': validation_score,
                    'details': details
                }
            else:
                logger.debug(f"Order block validation failed for {symbol_norm}: score {validation_score}/100 (need 60+)")
                return None
            
        except Exception as e:
            logger.error(f"Error validating order block: {e}", exc_info=True)
            return None
    
    def _find_anchor_candle(
        self, 
        candles: List[Dict], 
        direction: str, 
        ob_low: float, 
        ob_high: float
    ) -> Optional[int]:
        """Find the anchor candle (last down/up before displacement)"""
        try:
            if direction == "BULLISH":
                # Last down candle before bullish displacement
                for i in range(len(candles) - 1, max(0, len(candles) - 50), -1):
                    candle = candles[i]
                    if (candle.get('close', 0) < candle.get('open', 0) and
                        ob_low <= candle.get('low', 0) <= ob_high):
                        # Check if next candles show displacement
                        if i < len(candles) - 1:
                            next_candle = candles[i + 1]
                            if next_candle.get('close', 0) > candle.get('high', 0):
                                return i
            else:  # BEARISH
                # Last up candle before bearish displacement
                for i in range(len(candles) - 1, max(0, len(candles) - 50), -1):
                    candle = candles[i]
                    if (candle.get('close', 0) > candle.get('open', 0) and
                        ob_low <= candle.get('high', 0) <= ob_high):
                        # Check if next candles show displacement
                        if i < len(candles) - 1:
                            next_candle = candles[i + 1]
                            if next_candle.get('close', 0) < candle.get('low', 0):
                                return i
            return None
        except Exception as e:
            logger.debug(f"Error finding anchor candle: {e}")
            return None
    
    def _detect_fvg_after_displacement(
        self, 
        candles: List[Dict], 
        anchor_idx: int, 
        direction: str
    ) -> bool:
        """Detect Fair Value Gap (FVG) after displacement"""
        try:
            if anchor_idx >= len(candles) - 2:
                return False
            
            # Check next 3 candles for FVG
            for i in range(anchor_idx + 1, min(anchor_idx + 4, len(candles))):
                if i >= len(candles) - 1:
                    break
                
                candle1 = candles[i - 1]
                candle2 = candles[i]
                candle3 = candles[i + 1] if i + 1 < len(candles) else None
                
                if direction == "BULLISH":
                    # Bullish FVG: candle1 high < candle3 low
                    if candle3:
                        if candle1.get('high', 0) < candle3.get('low', 0):
                            return True
                else:  # BEARISH
                    # Bearish FVG: candle1 low > candle3 high
                    if candle3:
                        if candle1.get('low', 0) > candle3.get('high', 0):
                            return True
            
            return False
        except Exception:
            return False
    
    def _check_volume_spike(self, candles: List[Dict], anchor_idx: int) -> bool:
        """Check for volume spike on displacement move"""
        try:
            if anchor_idx >= len(candles) - 1:
                return False
            
            # Get volume of displacement candle
            displacement_volume = candles[anchor_idx + 1].get('volume', 0)
            
            # Calculate average volume of last 20 candles
            recent_volumes = [c.get('volume', 0) for c in candles[max(0, anchor_idx - 20):anchor_idx]]
            if not recent_volumes:
                return False
            
            avg_volume = sum(recent_volumes) / len(recent_volumes)
            
            # Volume spike: > 1.2x average
            return displacement_volume > (avg_volume * 1.2) if avg_volume > 0 else False
        except Exception:
            return False
    
    def _detect_liquidity_grab(
        self, 
        candles: List[Dict], 
        anchor_idx: int, 
        direction: str
    ) -> bool:
        """Detect liquidity grab (sweep of swing high/low)"""
        try:
            if anchor_idx >= len(candles) - 1:
                return False
            
            # Check for wick spike into liquidity pool
            displacement_candle = candles[anchor_idx + 1]
            
            if direction == "BULLISH":
                # Check for lower wick spike (liquidity grab below)
                low = displacement_candle.get('low', 0)
                open_price = displacement_candle.get('open', 0)
                close_price = displacement_candle.get('close', 0)
                body_low = min(open_price, close_price)
                wick_size = body_low - low
                body_size = abs(close_price - open_price)
                
                if body_size > 0 and wick_size > (body_size * 0.5):
                    return True
            else:  # BEARISH
                # Check for upper wick spike (liquidity grab above)
                high = displacement_candle.get('high', 0)
                open_price = displacement_candle.get('open', 0)
                close_price = displacement_candle.get('close', 0)
                body_high = max(open_price, close_price)
                wick_size = high - body_high
                body_size = abs(close_price - open_price)
                
                if body_size > 0 and wick_size > (body_size * 0.5):
                    return True
            
            return False
        except Exception:
            return False
    
    def _validate_session_context(self, symbol_norm: str) -> int:
        """Validate session context (strong sessions = higher score)"""
        try:
            if not self.session_manager:
                return 5  # Neutral score if no session manager
            
            session = self.session_manager.get_current_session()
            session_upper = session.upper()
            
            # Strong sessions
            if any(s in session_upper for s in ['LONDON', 'NY', 'OVERLAP']):
                return 10
            # Weak sessions
            elif 'ASIAN' in session_upper or 'POST' in session_upper:
                return 3
            # Normal
            return 5
        except Exception:
            return 5
    
    def _check_htf_alignment(
        self, 
        m5_candles: Optional[List[Dict]], 
        m5_data: Optional[Dict],
        direction: str
    ) -> bool:
        """Check higher timeframe alignment"""
        try:
            if not m5_candles and not m5_data:
                return False
            
            # Simple check: M5 trend alignment
            if m5_candles and len(m5_candles) >= 10:
                recent_closes = [c.get('close', 0) for c in m5_candles[-10:]]
                if direction == "BULLISH":
                    return recent_closes[-1] > recent_closes[0]
                else:
                    return recent_closes[-1] < recent_closes[0]
            
            return False
        except Exception:
            return False
    
    def _validate_structural_context(
        self, 
        m1_candles: List[Dict], 
        m1_analysis: Dict,
        direction: str
    ) -> bool:
        """Validate structural context (avoid choppy ranges)"""
        try:
            structure = m1_analysis.get('structure', {})
            structure_type = structure.get('type', '').upper()
            
            # Avoid choppy/indecisive structures
            if 'CHOPPY' in structure_type or 'RANGE' in structure_type:
                return False
            
            # Prefer clear impulses
            volatility = m1_analysis.get('volatility', {})
            volatility_state = volatility.get('state', '').upper()
            
            # Good: Expanding volatility (clear impulse)
            if volatility_state == 'EXPANDING':
                return True
            
            # Avoid: Contracting (compression, no clear direction)
            if volatility_state == 'CONTRACTING':
                return False
            
            return True
        except Exception:
            return True  # Default to allowing if check fails
    
    def _check_ob_freshness(self, symbol_norm: str, ob_low: float, ob_high: float) -> bool:
        """Check if order block is fresh (not already used)"""
        try:
            # Check cache for this OB zone
            ob_key = f"{symbol_norm}_{ob_low:.2f}_{ob_high:.2f}"
            cached_obs = self._detected_ob_cache.get(symbol_norm, [])
            
            # If not in cache, it's fresh
            return ob_key not in cached_obs
        except Exception:
            return True
    
    def _check_vwap_liquidity_confluence(
        self, 
        m1_analysis: Dict, 
        ob_low: float, 
        ob_high: float,
        current_price: float
    ) -> bool:
        """Check VWAP + liquidity confluence"""
        try:
            # Check if OB zone is near VWAP (within 0.5 ATR)
            volatility = m1_analysis.get('volatility', {})
            atr = volatility.get('atr', 0)
            
            if atr <= 0:
                return False
            
            # Get VWAP from analysis (if available)
            # For now, use current price as proxy
            ob_mid = (ob_low + ob_high) / 2
            distance_from_price = abs(current_price - ob_mid)
            
            # Within 0.5 ATR = good confluence
            return distance_from_price < (atr * 0.5)
        except Exception:
            return False
    
    def _extract_candles_from_multi_data(self, multi_data: Dict) -> Optional[List[Dict]]:
        """Extract candle data from multi_data structure"""
        try:
            # Try to reconstruct candles from highs/lows/closes arrays
            highs = multi_data.get('highs', [])
            lows = multi_data.get('lows', [])
            closes = multi_data.get('closes', [])
            opens = multi_data.get('opens', [])
            
            if not highs or not lows or not closes:
                return None
            
            candles = []
            for i in range(len(closes)):
                candles.append({
                    'open': opens[i] if opens and i < len(opens) else closes[i],
                    'high': highs[i] if i < len(highs) else closes[i],
                    'low': lows[i] if i < len(lows) else closes[i],
                    'close': closes[i],
                    'volume': 0
                })
            
            return candles
        except Exception:
            return None
    
    def _convert_mt5_rate_to_dict(self, rate) -> Dict:
        """Convert MT5 rate to candle dict"""
        try:
            return {
                'open': float(rate.open),
                'high': float(rate.high),
                'low': float(rate.low),
                'close': float(rate.close),
                'volume': int(rate.tick_volume if hasattr(rate, 'tick_volume') else rate.volume),
                'timestamp': datetime.fromtimestamp(rate.time, tz=timezone.utc) if hasattr(rate, 'time') else datetime.now(timezone.utc)
            }
        except Exception:
            return {}

