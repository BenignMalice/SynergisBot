"""
Confluence Calculator - Calculate multi-timeframe confluence scores
"""
import logging
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import numpy as np

logger = logging.getLogger(__name__)


class ConfluenceCalculator:
    """
    Calculate confluence scores across multiple timeframes
    
    Fix 18: Singleton Pattern - Only one instance shared across requests
    """
    _instance = None
    _lock = threading.RLock()  # Reentrant lock for nested calls
    
    def __new__(cls, indicator_bridge, cache_ttl: int = 30):
        """
        Fix 18: Singleton pattern - ensure only one instance exists
        
        Args:
            indicator_bridge: Indicator bridge instance for data access
            cache_ttl: Cache time-to-live in seconds (default: 30)
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, indicator_bridge, cache_ttl: int = 30):
        """
        Initialize ConfluenceCalculator (only called once due to singleton)
        
        Args:
            indicator_bridge: Indicator bridge instance for data access
            cache_ttl: Cache time-to-live in seconds (default: 30)
        """
        # Fix 18: Only initialize once (singleton pattern)
        if self._initialized:
            # Update indicator_bridge if it changed (e.g., on restart)
            if indicator_bridge is not None and indicator_bridge != self.indicator_bridge:
                logger.debug("Updating indicator_bridge in existing ConfluenceCalculator instance")
                self.indicator_bridge = indicator_bridge
            return
        
        if indicator_bridge is None:
            raise ValueError("indicator_bridge cannot be None")
        
        if cache_ttl <= 0:
            logger.warning(f"Invalid cache_ttl {cache_ttl}, using default 30")
            cache_ttl = 30
        
        self.indicator_bridge = indicator_bridge
        # Cache for per-timeframe calculations
        self._cache = {}  # {symbol: (data, timestamp)}
        # Fix 6: Unified cache for regime data (for API consistency)
        self._regime_cache = {}  # {symbol: (regime, timestamp)}
        self._cache_ttl = cache_ttl
        # Thread lock for cache operations
        self._cache_lock = threading.Lock()
        # Fix 6: Thread lock for regime cache operations
        self._regime_cache_lock = threading.Lock()
        self._initialized = True
        logger.debug("ConfluenceCalculator initialized (singleton instance)")
    
    def calculate_confluence(self, symbol: str) -> Dict:
        """
        Calculate confluence score for a symbol across all timeframes
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDc', 'XAUUSDc')
        
        Returns:
            dict with score (0-100), grade (A/B/C/D/F), and factor breakdown
        """
        # Input validation
        if not symbol or not isinstance(symbol, str):
            logger.error(f"Invalid symbol parameter: {symbol}")
            return self._empty_result()
        
        symbol = symbol.strip().upper()
        if not symbol:
            logger.error("Symbol cannot be empty")
            return self._empty_result()
        
        try:
            # Check indicator bridge is available
            if not self.indicator_bridge:
                logger.error(f"Indicator bridge not available for {symbol}")
                return self._empty_result()
            
            # Get multi-timeframe data
            multi_data = self.indicator_bridge.get_multi(symbol)
            
            if not multi_data:
                logger.warning(f"No data available for {symbol}")
                return self._empty_result()
            
            # Calculate individual factors
            trend_score = self._calculate_trend_alignment(multi_data)
            momentum_score = self._calculate_momentum_alignment(multi_data)
            support_resistance_score = self._calculate_sr_confluence(multi_data)
            volume_score = self._calculate_volume_confirmation(multi_data)
            volatility_score = self._calculate_volatility_health(multi_data, symbol=symbol)
            
            # Weighted average
            weights = {
                "trend": 0.30,
                "momentum": 0.25,
                "support_resistance": 0.25,
                "volume": 0.10,
                "volatility": 0.10
            }
            
            total_score = (
                trend_score * weights["trend"] +
                momentum_score * weights["momentum"] +
                support_resistance_score * weights["support_resistance"] +
                volume_score * weights["volume"] +
                volatility_score * weights["volatility"]
            )
            
            # Determine grade
            grade = self._score_to_grade(total_score)
            
            # Determine recommendation
            recommendation = self._get_recommendation(total_score, grade)
            
            return {
                "symbol": symbol,
                "confluence_score": round(total_score, 2),
                "grade": grade,
                "recommendation": recommendation,
                "factors": {
                    "trend_alignment": round(trend_score, 2),
                    "momentum_alignment": round(momentum_score, 2),
                    "support_resistance": round(support_resistance_score, 2),
                    "volume_confirmation": round(volume_score, 2),
                    "volatility_health": round(volatility_score, 2)
                },
                "weights": weights,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating confluence for {symbol}: {e}", exc_info=True)
            return self._empty_result()
    
    def _calculate_trend_alignment(self, multi_data: Dict) -> float:
        """
        Calculate trend alignment score (0-100)
        Checks if EMAs are aligned across timeframes
        """
        timeframes = ["M5", "M15", "M30", "H1", "H4"]
        scores = []
        
        for tf in timeframes:
            tf_data = multi_data.get(tf, {})
            if not tf_data:
                continue
            
            ema20 = float(tf_data.get("ema20", 0))
            ema50 = float(tf_data.get("ema50", 0))
            ema200 = float(tf_data.get("ema200", 0))
            
            # Get current close
            close_data = tf_data.get("close", 0)
            if isinstance(close_data, list):
                close = float(close_data[-1]) if close_data else 0.0
            else:
                close = float(close_data) if close_data else 0.0
            close = float(tf_data.get("current_close", close))
            
            if ema20 == 0 or ema50 == 0 or ema200 == 0 or close == 0:
                continue
            
            # Check alignment
            tf_score = 0
            
            # Bullish alignment: Price > EMA20 > EMA50 > EMA200
            if close > ema20 > ema50 > ema200:
                tf_score = 100
            # Bearish alignment: Price < EMA20 < EMA50 < EMA200
            elif close < ema20 < ema50 < ema200:
                tf_score = 100
            # Partial alignment
            elif (close > ema20 > ema50) or (close < ema20 < ema50):
                tf_score = 70
            elif (close > ema20) or (close < ema20):
                tf_score = 40
            else:
                tf_score = 0
            
            scores.append(tf_score)
        
        return sum(scores) / len(scores) if scores else 0
    
    def _calculate_momentum_alignment(self, multi_data: Dict) -> float:
        """
        Calculate momentum alignment score (0-100)
        Checks if RSI and MACD align across timeframes
        """
        timeframes = ["M5", "M15", "M30", "H1", "H4"]
        scores = []
        
        for tf in timeframes:
            tf_data = multi_data.get(tf, {})
            if not tf_data:
                continue
            
            rsi = float(tf_data.get("rsi", 50))
            macd = float(tf_data.get("macd", 0))
            macd_signal = float(tf_data.get("macd_signal", 0))
            
            tf_score = 0
            
            # Strong bullish momentum
            if rsi > 60 and macd > macd_signal and macd > 0:
                tf_score = 100
            # Strong bearish momentum
            elif rsi < 40 and macd < macd_signal and macd < 0:
                tf_score = 100
            # Moderate bullish
            elif rsi > 50 and macd > macd_signal:
                tf_score = 70
            # Moderate bearish
            elif rsi < 50 and macd < macd_signal:
                tf_score = 70
            # Neutral
            elif 45 <= rsi <= 55:
                tf_score = 50
            else:
                tf_score = 30
            
            scores.append(tf_score)
        
        return sum(scores) / len(scores) if scores else 50
    
    def _calculate_sr_confluence(self, multi_data: Dict) -> float:
        """
        Calculate support/resistance confluence score (0-100)
        Checks if price is near key levels across timeframes
        """
        timeframes = ["M5", "M15", "M30", "H1", "H4"]
        scores = []
        
        for tf in timeframes:
            tf_data = multi_data.get(tf, {})
            if not tf_data:
                continue
            
            # Get current close
            close_data = tf_data.get("close", 0)
            if isinstance(close_data, list):
                close = float(close_data[-1]) if close_data else 0.0
            else:
                close = float(close_data) if close_data else 0.0
            close = float(tf_data.get("current_close", close))
            
            ema20 = float(tf_data.get("ema20", 0))
            ema50 = float(tf_data.get("ema50", 0))
            ema200 = float(tf_data.get("ema200", 0))
            
            bb_upper = float(tf_data.get("bb_upper", 0))
            bb_lower = float(tf_data.get("bb_lower", 0))
            
            if close == 0:
                continue
            
            tf_score = 50  # Default neutral
            
            # Check if price is near key levels (within 0.5%)
            tolerance = close * 0.005
            
            near_ema20 = abs(close - ema20) < tolerance if ema20 > 0 else False
            near_ema50 = abs(close - ema50) < tolerance if ema50 > 0 else False
            near_ema200 = abs(close - ema200) < tolerance if ema200 > 0 else False
            near_bb_upper = abs(close - bb_upper) < tolerance if bb_upper > 0 else False
            near_bb_lower = abs(close - bb_lower) < tolerance if bb_lower > 0 else False
            
            # Score based on proximity to key levels
            if near_ema200:
                tf_score = 100  # EMA200 is most significant
            elif near_ema50:
                tf_score = 85
            elif near_ema20:
                tf_score = 70
            elif near_bb_upper or near_bb_lower:
                tf_score = 75
            else:
                tf_score = 50
            
            scores.append(tf_score)
        
        return sum(scores) / len(scores) if scores else 50
    
    def _calculate_volume_confirmation(self, multi_data: Dict) -> float:
        """
        Calculate volume confirmation score (0-100)
        Checks if volume supports the move
        """
        # For now, return neutral score as volume data may not be available
        # This can be enhanced when volume data is integrated
        return 60
    
    def _calculate_volatility_health(self, multi_data: Dict, symbol: str = None) -> float:
        """
        Calculate volatility health score (0-100)
        Checks if volatility is in healthy range (not too high, not too low)
        Uses symbol-specific thresholds for BTC and XAU
        """
        timeframes = ["M15", "M30", "H1"]
        scores = []
        
        for tf in timeframes:
            tf_data = multi_data.get(tf, {})
            if not tf_data:
                continue
            
            # Use the per-timeframe method which handles symbol-specific thresholds
            tf_score = self._calculate_volatility_health_for_timeframe(tf_data, symbol=symbol)
            scores.append(tf_score)
        
        return sum(scores) / len(scores) if scores else 60
    
    def _score_to_grade(self, score: float) -> str:
        """Convert score to letter grade"""
        if score >= 85:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 55:
            return "C"
        elif score >= 40:
            return "D"
        else:
            return "F"
    
    def _get_recommendation(self, score: float, grade: str) -> str:
        """Get recommendation based on score"""
        if grade == "A":
            return "Excellent setup - High confidence recommended"
        elif grade == "B":
            return "Good setup - Moderate to high confidence"
        elif grade == "C":
            return "Fair setup - Moderate confidence, manage risk carefully"
        elif grade == "D":
            return "Weak setup - Low confidence, consider skipping"
        else:
            return "Poor setup - Not recommended"
    
    def _empty_result(self) -> Dict:
        """Return empty result when data is unavailable"""
        return {
            "symbol": "",
            "confluence_score": 0,
            "grade": "F",
            "recommendation": "No data available",
            "factors": {
                "trend_alignment": 0,
                "momentum_alignment": 0,
                "support_resistance": 0,
                "volume_confirmation": 0,
                "volatility_health": 0
            },
            "weights": {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_confluence_for_multiple(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get confluence scores for multiple symbols"""
        results = {}
        for symbol in symbols:
            results[symbol] = self.calculate_confluence(symbol)
        return results
    
    def calculate_confluence_per_timeframe(self, symbol: str, m1_analyzer=None, m1_data_fetcher=None) -> Dict[str, Dict]:
        """
        Calculate confluence score for each timeframe separately
        
        Args:
            symbol: Symbol to calculate confluence for
            m1_analyzer: Optional M1MicrostructureAnalyzer instance for M1 calculation
            m1_data_fetcher: Optional M1DataFetcher instance for M1 data
        
        Returns:
            {
                "M1": {"score": 75, "grade": "B", "factors": {...}, "available": True},
                "M5": {"score": 82, "grade": "A", "factors": {...}, "available": True},
                "M15": {"score": 78, "grade": "B", "factors": {...}, "available": True},
                "H1": {"score": 85, "grade": "A", "factors": {...}, "available": True}
            }
        """
        # Input validation
        if not symbol or not isinstance(symbol, str):
            logger.error(f"Invalid symbol parameter: {symbol}")
            return self._empty_per_timeframe_result("")
        
        symbol = symbol.strip().upper()
        if not symbol:
            logger.error("Symbol cannot be empty")
            return self._empty_per_timeframe_result("")
        
        # Normalize symbol for cache key (ensure consistent format)
        cache_key = self._normalize_cache_key(symbol)
        
        # Normalize symbol for MT5 (ensure 'c' suffix for broker symbols)
        # Remove all trailing 'c' or 'C' and add single 'c'
        normalized_symbol = symbol
        while normalized_symbol.endswith('c') or normalized_symbol.endswith('C'):
            normalized_symbol = normalized_symbol[:-1]
        normalized_symbol = normalized_symbol + 'c'
        
        try:
            # Check cache first (thread-safe)
            now = datetime.now(timezone.utc)
            with self._cache_lock:
                if cache_key in self._cache:
                    data, timestamp = self._cache[cache_key]
                    cache_age = (now - timestamp).total_seconds()
                    if cache_age < self._cache_ttl:
                        logger.debug(f"Using cached confluence data for {symbol} (age: {cache_age:.1f}s)")
                        return data
            
            # Check indicator bridge is available
            if not self.indicator_bridge:
                logger.error(f"Indicator bridge not available for {symbol}")
                return self._empty_per_timeframe_result(symbol)
            
            # Get multi-timeframe data (use normalized symbol for MT5)
            multi_data = self.indicator_bridge.get_multi(normalized_symbol)
            
            if not multi_data:
                logger.warning(f"No data available for {symbol} - indicator_bridge.get_multi() returned empty dict")
                return self._empty_per_timeframe_result(symbol)
            
            # Debug: Log what timeframes we got
            available_tfs = list(multi_data.keys())
            logger.debug(f"Got multi-timeframe data for {symbol}: {available_tfs}")
            
            results = {}
            
            # Fix 6 & 7: Pre-calculate and cache regime for BTC (for API consistency)
            # This ensures regime is cached even if M1 components are not available
            # Use normalized_symbol (already normalized above with 'c' suffix)
            is_btc = normalized_symbol and normalized_symbol.startswith('BTC')
            if is_btc and self.indicator_bridge:
                try:
                    # Fix 5: Try RegimeDetector first (more accurate), fallback to lightweight
                    regime = None
                    try:
                        # Prepare data for RegimeDetector
                        timeframe_data = self._prepare_regime_detector_data(symbol, multi_data)
                        
                        if timeframe_data:
                            from infra.volatility_regime_detector import RegimeDetector
                            
                            regime_detector = RegimeDetector()
                            regime_result = regime_detector.detect_regime(
                                symbol=normalized_symbol,
                                timeframe_data=timeframe_data
                            )
                            
                            if regime_result and 'regime' in regime_result:
                                regime_enum = regime_result['regime']
                                # Convert VolatilityRegime enum to string
                                if hasattr(regime_enum, 'value'):
                                    regime = regime_enum.value
                                elif hasattr(regime_enum, 'name'):
                                    regime = regime_enum.name
                                else:
                                    regime = str(regime_enum)
                                
                                logger.debug(f"Pre-cached regime (RegimeDetector) for {symbol}: {regime}")
                    except (ImportError, Exception) as e:
                        # Fallback to lightweight method
                        logger.debug(f"RegimeDetector unavailable for pre-cache, using lightweight: {e}")
                        regime = self._calculate_volatility_regime_lightweight(multi_data, normalized_symbol)
                    
                    if regime:
                        # Cache the regime (Fix 6 & 7)
                        cache_key = self._normalize_cache_key(normalized_symbol)
                        now = datetime.now(timezone.utc)
                        with self._regime_cache_lock:
                            self._regime_cache[cache_key] = (regime, now)
                        logger.debug(f"Pre-cached regime for {normalized_symbol}: {regime}")
                except (KeyError, AttributeError) as e:
                    logger.debug(f"Missing data for regime calculation for {symbol}: {e}")
                except (ValueError, TypeError) as e:
                    logger.debug(f"Invalid data type for regime calculation for {symbol}: {e}")
                except Exception as e:
                    logger.debug(f"Unexpected error pre-caching regime for {symbol}: {e}", exc_info=True)
            
            # Calculate M1 confluence (special handling)
            m1_result = self._calculate_m1_confluence(symbol, m1_analyzer, m1_data_fetcher)
            results["M1"] = m1_result
            
            # Calculate M5, M15, H1 using existing methods per timeframe
            for tf in ["M5", "M15", "H1"]:
                try:
                    tf_data = multi_data.get(tf, {})
                    if not tf_data:
                        logger.debug(f"No {tf} data in multi_data for {symbol}")
                        results[tf] = {
                            "score": 0,
                            "grade": "F",
                            "available": False,
                            "factors": {}
                        }
                        continue
                    
                    # Fix 9: Validate timeframe data before calculation
                    # Debug: Log what keys are available
                    available_keys = list(tf_data.keys())
                    logger.debug(f"{tf} data for {symbol} has keys: {available_keys[:10]}...")  # Log first 10 keys
                    
                    if not self._validate_timeframe_data(tf_data, ['atr14', 'current_close']):
                        missing_keys = [k for k in ['atr14', 'current_close'] if k not in tf_data or tf_data[k] is None]
                        logger.warning(f"Invalid data for {tf} timeframe for {symbol}: missing or invalid keys: {missing_keys}")
                        results[tf] = {
                            "score": 0,
                            "grade": "F",
                            "available": False,
                            "factors": {}
                        }
                        continue
                    
                    # Calculate factors for this timeframe only
                    try:
                        trend_score = self._calculate_trend_alignment_for_timeframe(tf_data)
                        momentum_score = self._calculate_momentum_alignment_for_timeframe(tf_data)
                        sr_score = self._calculate_sr_confluence_for_timeframe(tf_data)
                        volume_score = self._calculate_volume_confirmation_for_timeframe(tf_data)
                        volatility_score = self._calculate_volatility_health_for_timeframe(tf_data, symbol=symbol)
                    except Exception as calc_error:
                        logger.error(f"Error calculating factors for {tf} timeframe for {symbol}: {calc_error}", exc_info=True)
                        results[tf] = {
                            "score": 0,
                            "grade": "F",
                            "available": False,
                            "factors": {},
                            "error": str(calc_error)
                        }
                        continue
                    
                    # Fix 13: Score bounds validation (clamp scores to 0-100)
                    trend_score = max(0, min(100, trend_score))
                    momentum_score = max(0, min(100, momentum_score))
                    sr_score = max(0, min(100, sr_score))
                    volume_score = max(0, min(100, volume_score))
                    volatility_score = max(0, min(100, volatility_score))
                    
                    # Weighted average (same weights as composite)
                    weights = {
                        "trend": 0.30,
                        "momentum": 0.25,
                        "support_resistance": 0.25,
                        "volume": 0.10,
                        "volatility": 0.10
                    }
                    
                    total_score = (
                        trend_score * weights["trend"] +
                        momentum_score * weights["momentum"] +
                        sr_score * weights["support_resistance"] +
                        volume_score * weights["volume"] +
                        volatility_score * weights["volatility"]
                    )
                    
                    # Fix 13: Clamp total score to 0-100
                    total_score = max(0, min(100, total_score))
                    
                    grade = self._score_to_grade(total_score)
                    
                    results[tf] = {
                        "score": round(total_score, 2),
                        "grade": grade,
                        "available": True,
                        "factors": {
                            "trend_alignment": round(trend_score, 2),
                            "momentum_alignment": round(momentum_score, 2),
                            "support_resistance": round(sr_score, 2),
                            "volume_confirmation": round(volume_score, 2),
                            "volatility_health": round(volatility_score, 2)
                        }
                    }
                except Exception as tf_error:
                    # Individual timeframe error - don't fail entire calculation
                    logger.error(f"Error processing {tf} timeframe for {symbol}: {tf_error}", exc_info=True)
                    results[tf] = {
                        "score": 0,
                        "grade": "F",
                        "available": False,
                        "factors": {},
                        "error": str(tf_error)
                    }
                    continue
            
            # Cache result
            # Store in cache (thread-safe)
            with self._cache_lock:
                self._cache[cache_key] = (results, now)
            
            return results
            
        except (KeyError, AttributeError) as e:
            logger.error(f"Missing data or attribute error calculating per-timeframe confluence for {symbol}: {e}")
            return self._empty_per_timeframe_result(symbol)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid data type error calculating per-timeframe confluence for {symbol}: {e}")
            return self._empty_per_timeframe_result(symbol)
        except Exception as e:
            logger.error(f"Unexpected error calculating per-timeframe confluence for {symbol}: {e}", exc_info=True)
            return self._empty_per_timeframe_result(symbol)
    
    def _calculate_m1_confluence(self, symbol: str, m1_analyzer=None, m1_data_fetcher=None) -> Dict:
        """
        Calculate M1 confluence using microstructure analysis
        
        Returns:
            {"score": 75, "grade": "B", "available": True, "factors": {...}}
        """
        try:
            # If M1 analyzer not provided, return unavailable
            if not m1_analyzer or not m1_data_fetcher:
                logger.debug(f"M1 analyzer not available for {symbol}")
                return {
                    "score": 0,
                    "grade": "F",
                    "available": False,
                    "factors": {}
                }
            
            # Fetch M1 data
            m1_candles = m1_data_fetcher.fetch_m1_data(symbol, count=200)
            if not m1_candles or len(m1_candles) < 50:
                # Fix 4: Fallback Logging - More detailed logging
                candle_count = len(m1_candles) if m1_candles else 0
                logger.debug(f"Insufficient M1 data for {symbol}: got {candle_count} candles, need at least 50")
                return {
                    "score": 0,
                    "grade": "F",
                    "available": False,
                    "factors": {}
                }
            
            # Get current price
            try:
                from infra.mt5_service import MT5Service
                mt5 = MT5Service()
                if mt5.connect():
                    quote = mt5.get_quote(symbol)
                    current_price = quote.ask if quote else None
                else:
                    current_price = None
            except (AttributeError, ImportError) as e:
                logger.debug(f"MT5 service unavailable for {symbol}: {e}")
                current_price = None
            except Exception as e:
                logger.debug(f"Error getting current price from MT5 for {symbol}: {e}")
                current_price = None
            
            if not current_price and m1_candles:
                # Fallback: use last candle close
                last_candle = m1_candles[-1] if isinstance(m1_candles[-1], dict) else m1_candles[-1]
                current_price = last_candle.get('close') if isinstance(last_candle, dict) else getattr(last_candle, 'close', None)
            
            if not current_price:
                # Fix 4: Fallback Logging - More detailed logging
                logger.debug(f"Could not determine current price for {symbol}: MT5 connection failed or quote unavailable")
                return {
                    "score": 0,
                    "grade": "F",
                    "available": False,
                    "factors": {}
                }
            
            # Analyze microstructure
            analysis = m1_analyzer.analyze_microstructure(
                symbol=symbol,
                candles=m1_candles,
                current_price=current_price
            )
            
            if not analysis or not analysis.get('available'):
                # Fix 4: Fallback Logging - More detailed logging
                analysis_status = "None" if not analysis else f"available={analysis.get('available', False)}"
                logger.debug(f"M1 analysis not available for {symbol}: analysis={analysis_status}")
                return {
                    "score": 0,
                    "grade": "F",
                    "available": False,
                    "factors": {}
                }
            
            # For BTC: Get volatility regime instead of using session-based volatility
            volatility_regime = None
            # Use normalized symbol for BTC detection (Fix 2: Symbol Normalization)
            normalized_symbol = self._normalize_symbol_for_check(symbol)
            is_btc = normalized_symbol and normalized_symbol.startswith('BTC')
            if is_btc and self.indicator_bridge:
                try:
                    # Get multi-timeframe data for regime detection
                    multi_data = self.indicator_bridge.get_multi(symbol)
                    if multi_data:
                        # Fix 5: Try RegimeDetector first (more accurate), fallback to lightweight
                        try:
                            # Prepare data for RegimeDetector
                            timeframe_data = self._prepare_regime_detector_data(symbol, multi_data)
                            
                            if timeframe_data:
                                from infra.volatility_regime_detector import RegimeDetector
                                
                                regime_detector = RegimeDetector()
                                regime_result = regime_detector.detect_regime(
                                    symbol=symbol,
                                    timeframe_data=timeframe_data
                                )
                                
                                if regime_result and 'regime' in regime_result:
                                    regime = regime_result['regime']
                                    # Convert VolatilityRegime enum to string
                                    if hasattr(regime, 'value'):
                                        volatility_regime = regime.value
                                    elif hasattr(regime, 'name'):
                                        volatility_regime = regime.name
                                    else:
                                        volatility_regime = str(regime)
                                    
                                    # Cache the regime (Fix 6 & 7)
                                    cache_key = self._normalize_cache_key(symbol)
                                    now = datetime.now(timezone.utc)
                                    with self._regime_cache_lock:
                                        if not hasattr(self, '_regime_cache'):
                                            self._regime_cache = {}
                                        self._regime_cache[cache_key] = (volatility_regime, now)
                                    
                                    confidence = regime_result.get('confidence', 0)
                                    logger.debug(f"BTC volatility regime (RegimeDetector) for {symbol}: {volatility_regime} (confidence: {confidence:.1f}%)")
                                else:
                                    # RegimeDetector returned no result, fallback to lightweight
                                    logger.debug(f"RegimeDetector returned no result for {symbol}, using lightweight method")
                                    volatility_regime = self._calculate_volatility_regime_lightweight(multi_data, symbol)
                            else:
                                # Cannot prepare data for RegimeDetector, fallback to lightweight
                                logger.debug(f"Cannot prepare RegimeDetector data for {symbol}, using lightweight method")
                                volatility_regime = self._calculate_volatility_regime_lightweight(multi_data, symbol)
                        except ImportError:
                            # RegimeDetector not available, fallback to lightweight
                            logger.debug(f"RegimeDetector not available for {symbol}, using lightweight method")
                            volatility_regime = self._calculate_volatility_regime_lightweight(multi_data, symbol)
                        except Exception as e:
                            # RegimeDetector failed, fallback to lightweight
                            logger.debug(f"RegimeDetector failed for {symbol}: {e}, using lightweight method")
                            volatility_regime = self._calculate_volatility_regime_lightweight(multi_data, symbol)
                        
                        if volatility_regime:
                            logger.debug(f"BTC volatility regime for {symbol}: {volatility_regime}")
                except (KeyError, AttributeError) as e:
                    logger.debug(f"Missing data for volatility regime detection for {symbol}: {e}")
                    volatility_regime = None
                except (ValueError, TypeError) as e:
                    logger.debug(f"Invalid data type for volatility regime detection for {symbol}: {e}")
                    volatility_regime = None
                except Exception as e:
                    logger.debug(f"Unexpected error detecting volatility regime for {symbol}: {e}", exc_info=True)
                    volatility_regime = None
            
            # Calculate microstructure confluence
            confluence_result = m1_analyzer.calculate_microstructure_confluence(
                analysis=analysis,
                symbol=symbol,
                volatility_regime=volatility_regime
            )
            
            if not confluence_result:
                return {
                    "score": 0,
                    "grade": "F",
                    "available": False,
                    "factors": {}
                }
            
            # Extract score and grade
            score = confluence_result.get('score', 0)
            grade = confluence_result.get('grade', 'F')
            components = confluence_result.get('components', {})
            
            # Map components to standard factor names
            factors = {
                "trend_alignment": components.get('strategy_fit', 0),
                "momentum_alignment": components.get('momentum_quality', 0),
                "support_resistance": components.get('liquidity_proximity', 0),
                "volume_confirmation": components.get('m1_signal_confidence', 0),
                "volatility_health": components.get('session_volatility_suitability', 0)
            }
            
            return {
                "score": round(score, 2),
                "grade": grade,
                "available": True,
                "factors": factors
            }
            
        except (AttributeError, TypeError) as e:
            logger.warning(f"Data structure error calculating M1 confluence for {symbol}: {e}")
            return {
                "score": 0,
                "grade": "F",
                "available": False,
                "factors": {}
            }
        except (KeyError, IndexError) as e:
            logger.warning(f"Missing data error calculating M1 confluence for {symbol}: {e}")
            return {
                "score": 0,
                "grade": "F",
                "available": False,
                "factors": {}
            }
        except Exception as e:
            logger.warning(f"Unexpected error calculating M1 confluence for {symbol}: {e}", exc_info=True)
            return {
                "score": 0,
                "grade": "F",
                "available": False,
                "factors": {}
            }
    
    def _calculate_trend_alignment_for_timeframe(self, tf_data: Dict) -> float:
        """Calculate trend alignment score for a single timeframe"""
        ema20 = float(tf_data.get("ema20", 0))
        ema50 = float(tf_data.get("ema50", 0))
        ema200 = float(tf_data.get("ema200", 0))
        
        close_data = tf_data.get("close", 0)
        if isinstance(close_data, list):
            close = float(close_data[-1]) if close_data else 0.0
        else:
            close = float(close_data) if close_data else 0.0
        close = float(tf_data.get("current_close", close))
        
        if ema20 == 0 or ema50 == 0 or ema200 == 0 or close == 0:
            return 0
        
        # Bullish alignment: Price > EMA20 > EMA50 > EMA200
        if close > ema20 > ema50 > ema200:
            return 100
        # Bearish alignment: Price < EMA20 < EMA50 < EMA200
        elif close < ema20 < ema50 < ema200:
            return 100
        # Partial alignment
        elif (close > ema20 > ema50) or (close < ema20 < ema50):
            return 70
        elif (close > ema20) or (close < ema20):
            return 40
        else:
            return 0
    
    def _calculate_momentum_alignment_for_timeframe(self, tf_data: Dict) -> float:
        """Calculate momentum alignment score for a single timeframe"""
        rsi = float(tf_data.get("rsi", 50))
        macd = float(tf_data.get("macd", 0))
        macd_signal = float(tf_data.get("macd_signal", 0))
        
        # Strong bullish momentum
        if rsi > 60 and macd > macd_signal and macd > 0:
            return 100
        # Strong bearish momentum
        elif rsi < 40 and macd < macd_signal and macd < 0:
            return 100
        # Moderate bullish
        elif rsi > 50 and macd > macd_signal:
            return 70
        # Moderate bearish
        elif rsi < 50 and macd < macd_signal:
            return 70
        # Neutral
        elif 45 <= rsi <= 55:
            return 50
        else:
            return 30
    
    def _calculate_sr_confluence_for_timeframe(self, tf_data: Dict) -> float:
        """Calculate support/resistance confluence score for a single timeframe"""
        close_data = tf_data.get("close", 0)
        if isinstance(close_data, list):
            close = float(close_data[-1]) if close_data else 0.0
        else:
            close = float(close_data) if close_data else 0.0
        close = float(tf_data.get("current_close", close))
        
        if close == 0:
            return 50
        
        ema20 = float(tf_data.get("ema20", 0))
        ema50 = float(tf_data.get("ema50", 0))
        ema200 = float(tf_data.get("ema200", 0))
        bb_upper = float(tf_data.get("bb_upper", 0))
        bb_lower = float(tf_data.get("bb_lower", 0))
        
        tf_score = 50  # Default neutral
        
        # Check if price is near key levels (within 0.5%)
        tolerance = close * 0.005
        
        near_ema200 = abs(close - ema200) < tolerance if ema200 > 0 else False
        near_ema50 = abs(close - ema50) < tolerance if ema50 > 0 else False
        near_ema20 = abs(close - ema20) < tolerance if ema20 > 0 else False
        near_bb_upper = abs(close - bb_upper) < tolerance if bb_upper > 0 else False
        near_bb_lower = abs(close - bb_lower) < tolerance if bb_lower > 0 else False
        
        # Score based on proximity to key levels
        if near_ema200:
            tf_score = 100  # EMA200 is most significant
        elif near_ema50:
            tf_score = 85
        elif near_ema20:
            tf_score = 70
        elif near_bb_upper or near_bb_lower:
            tf_score = 75
        
        return tf_score
    
    def _calculate_volume_confirmation_for_timeframe(self, tf_data: Dict) -> float:
        """Calculate volume confirmation score for a single timeframe"""
        # For now, return neutral score as volume data may not be available
        return 60
    
    def _calculate_volatility_health_for_timeframe(self, tf_data: Dict, symbol: str = None) -> float:
        """
        Calculate volatility health score for a single timeframe
        Uses symbol-specific ATR% thresholds for BTC and XAU
        """
        atr = float(tf_data.get("atr14", 0))
        
        close_data = tf_data.get("close", 0)
        if isinstance(close_data, list):
            close = float(close_data[-1]) if close_data else 0.0
        else:
            close = float(close_data) if close_data else 0.0
        close = float(tf_data.get("current_close", close))
        
        if atr == 0 or close == 0:
            return 60
        
        # Calculate ATR as percentage of price
        atr_pct = (atr / close) * 100
        
        # Get symbol-specific thresholds
        thresholds = self._get_volatility_thresholds(symbol)
        
        # Score based on thresholds
        if thresholds['optimal_low'] <= atr_pct <= thresholds['optimal_high']:
            return 100
        elif thresholds['low_min'] <= atr_pct < thresholds['optimal_low']:
            return 70  # Too low (choppy)
        elif thresholds['optimal_high'] < atr_pct <= thresholds['high_max']:
            return 70  # Slightly high
        elif atr_pct > thresholds['high_max']:
            return 40  # Too high (risky)
        else:
            return 50
    
    def _get_volatility_thresholds(self, symbol: str = None) -> Dict:
        """
        Get symbol-specific volatility thresholds for ATR% scoring
        
        Returns:
            dict with 'optimal_low', 'optimal_high', 'low_min', 'high_max' thresholds
        """
        symbol_upper = (symbol or "").upper()
        
        if symbol_upper.startswith('BTC'):
            # BTC: Higher volatility is normal and acceptable
            return {
                'optimal_low': 1.0,
                'optimal_high': 4.0,
                'low_min': 0.8,
                'high_max': 5.0
            }
        elif symbol_upper.startswith('XAU') or symbol_upper.startswith('GOLD'):
            # XAU/Gold: Lower volatility range
            return {
                'optimal_low': 0.4,
                'optimal_high': 1.5,
                'low_min': 0.3,
                'high_max': 2.0
            }
        else:
            # Default (FX pairs and others)
            return {
                'optimal_low': 0.5,
                'optimal_high': 2.0,
                'low_min': 0.3,
                'high_max': 3.0
            }
    
    def _calculate_volatility_regime_lightweight(self, multi_data: Dict, symbol: str) -> Optional[str]:
        """
        Fix 1: ATR Ratio Consistency - Lightweight multi-timeframe regime detection
        
        Uses ATR ratio from multiple timeframes for better accuracy than single timeframe.
        More accurate than current single-H1 approach, faster than full RegimeDetector.
        
        Fix 6 & 7: Cache regime result for API consistency
        
        Args:
            multi_data: Multi-timeframe data from indicator_bridge
            symbol: Trading symbol
        
        Returns:
            'STABLE', 'TRANSITIONAL', 'VOLATILE', or None if cannot determine
        """
        cache_key = self._normalize_cache_key(symbol)
        
        # Fix 6 & 7: Check cache for regime first
        now = datetime.now(timezone.utc)
        with self._cache_lock:
            # Check if we have cached regime data
            if hasattr(self, '_regime_cache') and cache_key in self._regime_cache:
                regime, timestamp = self._regime_cache[cache_key]
                cache_age = (now - timestamp).total_seconds()
                if cache_age < self._cache_ttl:
                    logger.debug(f"Using cached regime for {symbol}: {regime} (age: {cache_age:.1f}s)")
                    return regime
        
        try:
            # Collect ATR ratios from multiple timeframes (weighted by reliability)
            timeframe_weights = {
                'H1': 0.5,   # Most reliable for regime
                'M15': 0.3,  # Secondary confirmation
                'M5': 0.2    # Tertiary confirmation
            }
            
            ratios = []
            weights = []
            
            for tf, weight in timeframe_weights.items():
                tf_data = multi_data.get(tf, {})
                if not tf_data:
                    continue
                
                atr_14 = float(tf_data.get('atr14', 0))
                atr_50 = float(tf_data.get('atr50', 0))
                
                # Fix 9: Validate ATR values
                if atr_14 <= 0:
                    logger.debug(f"Invalid ATR14 for {tf}: {atr_14}")
                    continue
                
                # If ATR50 not available, try to calculate from longer timeframe or estimate
                if atr_50 == 0:
                    # Try to get from higher timeframe
                    if tf == 'M5' and 'M15' in multi_data:
                        m15_data = multi_data['M15']
                        atr_50 = float(m15_data.get('atr50', 0))
                    elif tf == 'M15' and 'H1' in multi_data:
                        h1_data = multi_data['H1']
                        atr_50 = float(h1_data.get('atr50', 0))
                    
                    # If still not available, estimate (Fix 1: Better estimation)
                    if atr_50 == 0:
                        # Use more accurate estimation: ATR50 typically 85-95% of ATR14 in stable markets
                        # But can be much lower in volatile markets, so use conservative estimate
                        atr_50 = atr_14 * 0.9 if atr_14 > 0 else 0
                        logger.debug(f"Estimated ATR50 for {tf} as 90% of ATR14: {atr_50:.2f}")
                
                if atr_50 > 0:
                    atr_ratio = atr_14 / atr_50
                    ratios.append(atr_ratio)
                    weights.append(weight)
                    logger.debug(f"{tf} ATR ratio: {atr_ratio:.2f} (ATR14: {atr_14:.2f}, ATR50: {atr_50:.2f})")
            
            if not ratios:
                logger.debug(f"Could not calculate ATR ratios for {symbol}")
                return None
            
            # Calculate weighted average ATR ratio
            weighted_ratio = sum(r * w for r, w in zip(ratios, weights)) / sum(weights)
            
            # Regime classification based on weighted ATR ratio
            # STABLE: ≤1.2, TRANSITIONAL: 1.2-1.4, VOLATILE: ≥1.4
            if weighted_ratio >= 1.4:
                regime = 'VOLATILE'
            elif weighted_ratio <= 1.2:
                regime = 'STABLE'
            else:
                regime = 'TRANSITIONAL'
            
            # Fix 6 & 7: Cache regime result for API consistency
            with self._cache_lock:
                if not hasattr(self, '_regime_cache'):
                    self._regime_cache = {}
                self._regime_cache[cache_key] = (regime, now)
            
            return regime
                
        except (KeyError, AttributeError) as e:
            logger.debug(f"Missing data for volatility regime calculation for {symbol}: {e}")
            return None
        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.debug(f"Invalid data or calculation error for volatility regime for {symbol}: {e}")
            return None
        except Exception as e:
            logger.debug(f"Unexpected error calculating volatility regime for {symbol}: {e}", exc_info=True)
            return None
    
    def _prepare_regime_detector_data(
        self, symbol: str, multi_data: Dict
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Fix 5: Prepare data for RegimeDetector from indicator_bridge format
        
        Converts indicator_bridge.get_multi() format to RegimeDetector.detect_regime() format.
        
        Args:
            symbol: Trading symbol
            multi_data: Multi-timeframe data from indicator_bridge.get_multi()
        
        Returns:
            Dict with keys 'M5', 'M15', 'H1' containing RegimeDetector format data,
            or None if data cannot be prepared
        """
        if not multi_data:
            return None
        
        timeframe_data = {}
        
        for tf in ['M5', 'M15', 'H1']:
            tf_data = multi_data.get(tf, {})
            if not tf_data:
                continue
            
            # Reconstruct rates array from OHLCV lists
            rates_array = None
            if all(key in tf_data for key in ['opens', 'highs', 'lows', 'closes']):
                opens = tf_data['opens']
                highs = tf_data['highs']
                lows = tf_data['lows']
                closes = tf_data['closes']
                volumes = tf_data.get('volumes', [0] * len(opens))
                
                # Take last 100 bars (RegimeDetector needs sufficient history)
                n_bars = min(100, len(opens))
                if n_bars < 50:
                    logger.debug(f"Insufficient data for {tf}: {n_bars} bars (need at least 50)")
                    continue
                
                # Create rates array: [time, open, high, low, close, tick_volume, spread, real_volume]
                # RegimeDetector expects numpy array with OHLCV data
                rates_list = []
                times = tf_data.get('times', [])
                for i in range(-n_bars, 0):
                    idx = len(opens) + i
                    if idx < 0:
                        continue
                    # Use timestamp if available, otherwise use index
                    # Times can be string format ('YYYY-MM-DD HH:MM:SS') or datetime objects
                    if times and idx < len(times):
                        time_obj = times[idx]
                        if isinstance(time_obj, str):
                            # Parse string format
                            try:
                                from datetime import datetime as dt
                                time_val = int(dt.strptime(time_obj, '%Y-%m-%d %H:%M:%S').timestamp())
                            except:
                                time_val = idx
                        elif hasattr(time_obj, 'timestamp'):
                            time_val = int(time_obj.timestamp())
                        else:
                            time_val = idx
                    else:
                        time_val = idx
                    rates_list.append((
                        time_val,
                        float(opens[idx]),
                        float(highs[idx]),
                        float(lows[idx]),
                        float(closes[idx]),
                        int(volumes[idx]) if idx < len(volumes) else 0,
                        0,  # spread (not available)
                        0   # real_volume (not available)
                    ))
                
                # Convert to numpy structured array (same format as MT5)
                dtype = [('time', 'i8'), ('open', 'f8'), ('high', 'f8'), ('low', 'f8'), 
                        ('close', 'f8'), ('tick_volume', 'i8'), ('spread', 'i4'), ('real_volume', 'i8')]
                rates_array = np.array(rates_list, dtype=dtype)
            else:
                logger.debug(f"Cannot reconstruct rates for {tf}: missing OHLC data")
                continue
            
            # Get indicators
            atr_14 = float(tf_data.get('atr14', 0))
            atr_50 = float(tf_data.get('atr50', 0))
            
            # Calculate ATR50 if not available (estimate)
            if atr_50 == 0 and atr_14 > 0:
                # Estimate ATR50 as ~90% of ATR14 (typical in stable conditions)
                atr_50 = atr_14 * 0.9
                logger.debug(f"Estimated ATR50 for {tf} as 90% of ATR14: {atr_50:.2f}")
            
            # Get Bollinger Bands
            bb_upper = float(tf_data.get('bb_upper', 0))
            bb_lower = float(tf_data.get('bb_lower', 0))
            bb_middle = float(tf_data.get('bb_middle', 0))
            
            # Calculate bb_middle if not available (average of upper and lower)
            if bb_middle == 0 and bb_upper > 0 and bb_lower > 0:
                bb_middle = (bb_upper + bb_lower) / 2.0
                logger.debug(f"Calculated bb_middle for {tf} as average of upper and lower: {bb_middle:.2f}")
            
            # Get ADX
            adx = float(tf_data.get('adx', 0))
            
            # Get volume array
            volumes = tf_data.get('volumes', [])
            volume_array = np.array(volumes[-n_bars:]) if volumes and len(volumes) >= n_bars else np.array([0] * n_bars)
            
            # Prepare timeframe data for RegimeDetector
            timeframe_data[tf] = {
                'rates': rates_array,
                'atr_14': atr_14,
                'atr_50': atr_50,
                'bb_upper': bb_upper,
                'bb_lower': bb_lower,
                'bb_middle': bb_middle,
                'adx': adx,
                'volume': volume_array
            }
        
        return timeframe_data if timeframe_data else None
    
    def get_cached_regime(self, symbol: str) -> Optional[str]:
        """
        Fix 7: Get cached regime for API consistency
        
        Allows other endpoints to access the same regime value calculated by confluence
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Cached regime string or None if not cached
        """
        cache_key = self._normalize_cache_key(symbol)
        
        with self._cache_lock:
            if hasattr(self, '_regime_cache') and cache_key in self._regime_cache:
                regime, timestamp = self._regime_cache[cache_key]
                now = datetime.now(timezone.utc)
                cache_age = (now - timestamp).total_seconds()
                if cache_age < self._cache_ttl:
                    return regime
        return None
    
    def _normalize_symbol_for_check(self, symbol: str) -> str:
        """
        Normalize symbol for symbol checks (BTC detection, etc.)
        Uses same logic as normalize_symbol() in main_api.py
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Normalized symbol string (uppercase, consistent format)
        """
        if not symbol:
            return ""
        # Normalize: uppercase, strip whitespace, ensure 'c' suffix
        symbol = symbol.strip().upper()
        # Remove ALL trailing 'c' or 'C' characters
        while symbol.endswith('c') or symbol.endswith('C'):
            symbol = symbol[:-1]
        # Add single 'c' suffix
        return symbol + 'c'
    
    def _normalize_cache_key(self, symbol: str) -> str:
        """
        Normalize symbol for cache key to prevent collisions
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Normalized symbol string (uppercase, consistent format)
        """
        if not symbol:
            return ""
        # Normalize: uppercase, strip whitespace, ensure 'c' suffix
        symbol = symbol.strip().upper()
        # Remove ALL trailing 'c' or 'C' characters
        while symbol.endswith('c') or symbol.endswith('C'):
            symbol = symbol[:-1]
        # Add single 'c' suffix
        return symbol + 'c'
    
    def get_cache_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get cache information for a symbol (public method)
        
        Args:
            symbol: Trading symbol
        
        Returns:
            dict with cache info or None if not cached
        """
        if not symbol or not isinstance(symbol, str):
            return None
        
        cache_key = self._normalize_cache_key(symbol)
        
        with self._cache_lock:
            if cache_key not in self._cache:
                return None
            
            data, timestamp = self._cache[cache_key]
            now = datetime.now(timezone.utc)
            cache_age = (now - timestamp).total_seconds()
            
            return {
                "cached": True,
                "cache_age_seconds": cache_age,
                "cache_timestamp": timestamp.isoformat(),
                "is_fresh": cache_age < self._cache_ttl
            }
    
    def _empty_per_timeframe_result(self, symbol: str) -> Dict[str, Dict]:
        """Return empty per-timeframe result when data is unavailable"""
        return {
            "M1": {"score": 0, "grade": "F", "available": False, "factors": {}},
            "M5": {"score": 0, "grade": "F", "available": False, "factors": {}},
            "M15": {"score": 0, "grade": "F", "available": False, "factors": {}},
            "H1": {"score": 0, "grade": "F", "available": False, "factors": {}}
        }
    
    def _validate_timeframe_data(self, tf_data: Dict, required_keys: List[str]) -> bool:
        """
        Fix 9: Validate timeframe data has required keys and valid values
        
        Args:
            tf_data: Timeframe data dictionary
            required_keys: List of required keys
        
        Returns:
            True if valid, False otherwise
        """
        if not tf_data:
            return False
        
        for key in required_keys:
            if key not in tf_data or tf_data[key] is None:
                return False
            
            # Check numeric values are valid
            if key in ['atr14', 'atr50', 'current_close', 'close']:
                try:
                    value = float(tf_data[key])
                    if value <= 0:
                        return False
                except (ValueError, TypeError):
                    return False
        
        return True
    
    def _prepare_regime_detector_data(
        self, symbol: str, multi_data: Dict
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Fix 5: Prepare data for RegimeDetector from indicator_bridge format
        
        Converts indicator_bridge.get_multi() format to RegimeDetector.detect_regime() format.
        
        Args:
            symbol: Trading symbol
            multi_data: Multi-timeframe data from indicator_bridge.get_multi()
        
        Returns:
            Dict with keys 'M5', 'M15', 'H1' containing RegimeDetector format data,
            or None if data cannot be prepared
        """
        if not multi_data:
            return None
        
        timeframe_data = {}
        
        for tf in ['M5', 'M15', 'H1']:
            tf_data = multi_data.get(tf, {})
            if not tf_data:
                continue
            
            # Reconstruct rates array from OHLCV lists
            rates_array = None
            if all(key in tf_data for key in ['opens', 'highs', 'lows', 'closes']):
                opens = tf_data['opens']
                highs = tf_data['highs']
                lows = tf_data['lows']
                closes = tf_data['closes']
                volumes = tf_data.get('volumes', [0] * len(opens))
                
                # Take last 100 bars (RegimeDetector needs sufficient history)
                n_bars = min(100, len(opens))
                if n_bars < 50:
                    logger.debug(f"Insufficient data for {tf}: {n_bars} bars (need at least 50)")
                    continue
                
                # Create rates array: [time, open, high, low, close, tick_volume, spread, real_volume]
                # RegimeDetector expects numpy array with OHLCV data
                rates_list = []
                times = tf_data.get('times', [])
                for i in range(-n_bars, 0):
                    idx = len(opens) + i
                    if idx < 0:
                        continue
                    # Use timestamp if available, otherwise use index
                    # Times can be string format ('YYYY-MM-DD HH:MM:SS') or datetime objects
                    if times and idx < len(times):
                        time_obj = times[idx]
                        if isinstance(time_obj, str):
                            # Parse string format
                            try:
                                from datetime import datetime as dt
                                time_val = int(dt.strptime(time_obj, '%Y-%m-%d %H:%M:%S').timestamp())
                            except:
                                time_val = idx
                        elif hasattr(time_obj, 'timestamp'):
                            time_val = int(time_obj.timestamp())
                        else:
                            time_val = idx
                    else:
                        time_val = idx
                    
                    rates_list.append((
                        time_val,
                        float(opens[idx]),
                        float(highs[idx]),
                        float(lows[idx]),
                        float(closes[idx]),
                        int(volumes[idx]) if idx < len(volumes) else 0,
                        0,  # spread (not available)
                        0   # real_volume (not available)
                    ))
                
                # Convert to numpy structured array (same format as MT5)
                dtype = [('time', 'i8'), ('open', 'f8'), ('high', 'f8'), ('low', 'f8'), 
                        ('close', 'f8'), ('tick_volume', 'i8'), ('spread', 'i4'), ('real_volume', 'i8')]
                rates_array = np.array(rates_list, dtype=dtype)
            else:
                logger.debug(f"Cannot reconstruct rates for {tf}: missing OHLC data")
                continue
            
            # Get indicators
            atr_14 = float(tf_data.get('atr14', 0))
            atr_50 = float(tf_data.get('atr50', 0))
            
            # Calculate ATR50 if not available (estimate)
            if atr_50 == 0 and atr_14 > 0:
                # Estimate ATR50 as ~90% of ATR14 (typical in stable conditions)
                atr_50 = atr_14 * 0.9
                logger.debug(f"Estimated ATR50 for {tf} as 90% of ATR14: {atr_50:.2f}")
            
            # Get Bollinger Bands
            bb_upper = float(tf_data.get('bb_upper', 0))
            bb_lower = float(tf_data.get('bb_lower', 0))
            bb_middle = float(tf_data.get('bb_middle', 0))
            
            # Calculate bb_middle if not available (average of upper and lower)
            if bb_middle == 0 and bb_upper > 0 and bb_lower > 0:
                bb_middle = (bb_upper + bb_lower) / 2.0
                logger.debug(f"Calculated bb_middle for {tf} as average of upper and lower: {bb_middle:.2f}")
            
            # Get ADX
            adx = float(tf_data.get('adx', 0))
            
            # Get volume array
            volumes = tf_data.get('volumes', [])
            volume_array = np.array(volumes[-n_bars:]) if volumes and len(volumes) >= n_bars else np.array([0] * n_bars)
            
            # Prepare timeframe data for RegimeDetector
            timeframe_data[tf] = {
                'rates': rates_array,
                'atr_14': atr_14,
                'atr_50': atr_50,
                'bb_upper': bb_upper,
                'bb_lower': bb_lower,
                'bb_middle': bb_middle,
                'adx': adx,
                'volume': volume_array
            }
        
        return timeframe_data if timeframe_data else None
    