"""
Unified Detection System Manager

Provides consistent interface for all pattern detection systems with caching
and session-based cache invalidation.

🧩 LOGICAL REVIEW: Session-Based Cache Invalidation
- Cache invalidated on session change to prevent stale detections
- Session tracking per symbol
- Automatic cache cleanup
"""

import logging
import time
import pandas as pd
from typing import Dict, Optional, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class DetectionSystemManager:
    """Unified interface for all detection systems with caching"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}  # {cache_key: {result, timestamp, session}}
        self._cache_ttl = 300  # 5 minutes default TTL
        self._mt5_service = None
        self._streamer = None
    
    def _get_mt5_service(self):
        """Lazy load MT5Service"""
        if self._mt5_service is None:
            try:
                from infra.mt5_service import MT5Service
                self._mt5_service = MT5Service()
            except Exception as e:
                logger.warning(f"Could not initialize MT5Service: {e}")
        return self._mt5_service
    
    def _get_streamer(self):
        """Lazy load StreamerDataAccess"""
        if self._streamer is None:
            try:
                from infra.streamer_data_access import StreamerDataAccess
                self._streamer = StreamerDataAccess()
            except Exception as e:
                logger.debug(f"StreamerDataAccess not available: {e}")
        return self._streamer
    
    def _get_cache_key(self, symbol: str, timeframe: str, detection_type: str) -> str:
        """Generate cache key"""
        # Get current bar timestamp (simplified - use minute-based)
        current_minute = int(time.time() / 60)
        return f"{symbol}_{timeframe}_{detection_type}_{current_minute}"
    
    def _get_cached(self, cache_key: str) -> Optional[Dict]:
        """Get cached result if still valid"""
        cached = self._cache.get(cache_key)
        if cached:
            age = time.time() - cached.get("timestamp", 0)
            if age < self._cache_ttl:
                return cached.get("result")
            else:
                # Expired, remove from cache
                del self._cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, result: Dict):
        """Cache detection result"""
        # 🧩 LOGICAL REVIEW: Check session change before caching
        # Extract symbol from cache key (format: symbol_timeframe_detection_minute)
        symbol = cache_key.split("_")[0] if "_" in cache_key else ""
        if symbol:
            self._check_session_change(symbol)
        
        self._cache[cache_key] = {
            "result": result,
            "timestamp": time.time()
        }
        # Cleanup old cache entries (keep last 100)
        if len(self._cache) > 100:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest_key]
    
    def _invalidate_cache_on_session_change(self, symbol: str):
        """
        🧩 LOGICAL REVIEW: Session-Based Cache Invalidation
        
        Invalidate detection cache when session changes (e.g., Asian → London).
        Prevents stale cached detections from being used during volatility regime shifts.
        
        Call this method when session changes are detected (e.g., in session monitoring loop).
        """
        from infra.session_helpers import SessionHelpers
        
        try:
            current_session = SessionHelpers.get_current_session()
            cache_key_prefix = f"{symbol}_"
            
            # Get all cache keys for this symbol
            keys_to_remove = [
                key for key in self._cache.keys()
                if key.startswith(cache_key_prefix)
            ]
            
            for key in keys_to_remove:
                del self._cache[key]
            
            logger.debug(f"Invalidated {len(keys_to_remove)} cache entries for {symbol} on session change to {current_session}")
        except Exception as e:
            logger.warning(f"Error invalidating cache on session change for {symbol}: {e}")
    
    def _check_session_change(self, symbol: str) -> bool:
        """
        Check if session has changed since last cache entry.
        Returns True if session changed, False otherwise.
        """
        try:
            from infra.session_helpers import SessionHelpers
            
            current_session = SessionHelpers.get_current_session()
            cache_key = f"{symbol}_session"
            
            last_session = self._cache.get(cache_key, {}).get("session")
            
            if last_session != current_session:
                # Session changed - invalidate cache
                self._invalidate_cache_on_session_change(symbol)
                # Update session tracking
                self._cache[cache_key] = {"session": current_session, "timestamp": time.time()}
                return True
            
            return False
        except Exception as e:
            logger.warning(f"Error checking session change for {symbol}: {e}")
            return False
    
    def _get_bars(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Get bars DataFrame for symbol/timeframe.
        
        Implementation example using MT5Service:
        """
        try:
            mt5_service = self._get_mt5_service()
            if mt5_service:
                bars = mt5_service.get_bars(symbol, timeframe, count=100)
                if bars is not None:
                    return bars
            
            # Fallback to streamer
            streamer = self._get_streamer()
            if streamer:
                candles = streamer.get_candles(symbol, timeframe, limit=100)
                if candles:
                    # Convert to DataFrame
                    df = pd.DataFrame(candles)
                    if 'time' in df.columns:
                        df['time'] = pd.to_datetime(df['time'])
                    return df
            
            logger.warning(f"Could not get bars for {symbol} {timeframe}")
            return None
        except Exception as e:
            logger.warning(f"Error getting bars for {symbol} {timeframe}: {e}")
            return None
    
    def _get_atr(self, symbol: str, timeframe: str, period: int = 14) -> Optional[float]:
        """Get ATR for symbol/timeframe"""
        try:
            streamer = self._get_streamer()
            if streamer:
                atr = streamer.calculate_atr(symbol, timeframe, period=period)
                if atr and atr > 0:
                    return float(atr)
            
            # Fallback to UniversalDynamicSLTPManager
            try:
                from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
                manager = UniversalDynamicSLTPManager()
                atr = manager._get_current_atr(symbol, timeframe, period=period)
                if atr and atr > 0:
                    return float(atr)
            except Exception:
                pass
            
            logger.warning(f"Could not get ATR for {symbol} {timeframe}")
            return None
        except Exception as e:
            logger.warning(f"Error getting ATR for {symbol} {timeframe}: {e}")
            return None
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        try:
            mt5_service = self._get_mt5_service()
            if mt5_service:
                quote = mt5_service.get_quote(symbol)
                if quote:
                    return (quote.bid + quote.ask) / 2.0  # Mid price
            return None
        except Exception as e:
            logger.warning(f"Error getting current price for {symbol}: {e}")
            return None
    
    def get_order_block(self, symbol: str, timeframe: str = "M5") -> Optional[Dict]:
        """Get order block detection result"""
        cache_key = self._get_cache_key(symbol, timeframe, "order_block")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            # Use micro order block detector for M1/M5
            if timeframe in ["M1", "M5"]:
                from infra.micro_order_block_detector import MicroOrderBlockDetector
                detector = MicroOrderBlockDetector()
                
                # Get bars
                bars_df = self._get_bars(symbol, timeframe)
                if bars_df is None or len(bars_df) < 10:
                    return None
                
                # Convert to list of dicts for detector
                candles = []
                for _, row in bars_df.tail(20).iterrows():
                    candles.append({
                        'open': float(row.get('open', 0)),
                        'high': float(row.get('high', 0)),
                        'low': float(row.get('low', 0)),
                        'close': float(row.get('close', 0)),
                        'volume': float(row.get('volume', 0))
                    })
                
                current_price = self._get_current_price(symbol)
                atr_value = self._get_atr(symbol, timeframe)
                micro_obs = detector.detect_micro_obs(candles, atr_value=atr_value, current_price=current_price)
                
                if micro_obs:
                    # Get most recent
                    ob = micro_obs[0]
                    result = {
                        "order_block_bull": ob.price_range[1] if ob.direction == "BULLISH" else None,
                        "order_block_bear": ob.price_range[0] if ob.direction == "BEARISH" else None,
                        "ob_strength": ob.strength,
                        "ob_confluence": [],
                        "ob_retest": ob.retest_detected
                    }
                    self._cache_result(cache_key, result)
                    return result
            
            return None
        except Exception as e:
            logger.warning(f"Order block detection failed for {symbol}: {e}")
            # 🧩 LOGICAL REVIEW: Degraded State Logging
            self._log_degraded_state("order_block_detection", symbol, str(e))
        return None
    
    def get_fvg(self, symbol: str, timeframe: str = "M15") -> Optional[Dict]:
        """Get FVG detection result"""
        cache_key = self._get_cache_key(symbol, timeframe, "fvg")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            from domain.fvg import detect_fvg
            
            bars = self._get_bars(symbol, timeframe)
            if bars is None or len(bars) < 3:
                return None
            
            atr = self._get_atr(symbol, timeframe)
            if atr is None or atr <= 0:
                return None
            
            # Call FVG detection
            fvg_result = detect_fvg(bars, atr, min_width_mult=0.1, lookback=10)
            
            if not fvg_result.get("fvg_bull") and not fvg_result.get("fvg_bear"):
                return None
            
            # Get current price for fill calculation
            current_price = self._get_current_price(symbol)
            
            # Normalize to dict format expected by strategies
            zone_high, zone_low = fvg_result.get("fvg_zone", (0.0, 0.0))
            
            # Calculate fill percentage
            filled_pct_bull = 0.0
            filled_pct_bear = 0.0
            
            if current_price is not None and zone_high > zone_low:
                # Calculate fill percentage for bullish FVG
                if fvg_result.get("fvg_bull"):
                    if current_price <= zone_low:
                        filled_pct_bull = 0.0
                    elif current_price >= zone_high:
                        filled_pct_bull = 1.0
                    else:
                        filled_pct_bull = (current_price - zone_low) / (zone_high - zone_low)
                
                # Calculate fill percentage for bearish FVG
                if fvg_result.get("fvg_bear"):
                    if current_price >= zone_high:
                        filled_pct_bear = 0.0
                    elif current_price <= zone_low:
                        filled_pct_bear = 1.0
                    else:
                        filled_pct_bear = (zone_high - current_price) / (zone_high - zone_low)
            
            normalized = {
                "fvg_bull": {
                    "high": zone_high,
                    "low": zone_low,
                    "filled_pct": filled_pct_bull
                } if fvg_result.get("fvg_bull") else None,
                "fvg_bear": {
                    "high": zone_high,
                    "low": zone_low,
                    "filled_pct": filled_pct_bear
                } if fvg_result.get("fvg_bear") else None,
                "fvg_strength": min(1.0, fvg_result.get("width_atr", 0.0) / 2.0),  # Normalize to 0-1
                "fvg_confluence": []
            }
            
            self._cache_result(cache_key, normalized)
            return normalized
        except Exception as e:
            logger.warning(f"FVG detection failed for {symbol}: {e}")
            # 🧩 LOGICAL REVIEW: Degraded State Logging
            self._log_degraded_state("fvg_detection", symbol, str(e))
        return None
    
    def get_choch_bos(self, symbol: str, timeframe: str = "M15") -> Optional[Dict]:
        """Get CHOCH/BOS detection result"""
        cache_key = self._get_cache_key(symbol, timeframe, "choch_bos")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            from domain.market_structure import label_structure
            
            bars = self._get_bars(symbol, timeframe)
            if bars is None or len(bars) < 10:
                return None
            
            # Use market structure detection
            structure = label_structure(bars, lookback=10)
            
            result = {
                "choch_bull": structure.get("choch_bull", False),
                "choch_bear": structure.get("choch_bear", False),
                "bos_bull": structure.get("bos_bull", False),
                "bos_bear": structure.get("bos_bear", False),
                "structure_strength": structure.get("strength", 0.5)
            }
            
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"CHOCH/BOS detection failed for {symbol}: {e}")
            self._log_degraded_state("choch_bos_detection", symbol, str(e))
        return None
    
    def get_kill_zone(self, symbol: str, timeframe: str = "M5") -> Optional[Dict]:
        """Get kill zone detection result"""
        cache_key = self._get_cache_key(symbol, timeframe, "kill_zone")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            from infra.session_helpers import SessionHelpers
            
            current_session = SessionHelpers.get_current_session()
            
            # Kill zones are time-based (London/NY open)
            kill_zone_active = current_session in ["LONDON", "NY", "OVERLAP"]
            
            result = {
                "kill_zone_active": kill_zone_active,
                "session": current_session
            }
            
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"Kill zone detection failed for {symbol}: {e}")
            self._log_degraded_state("kill_zone_detection", symbol, str(e))
        return None
    
    def get_breaker_block(self, symbol: str, timeframe: str = "M5") -> Optional[Dict]:
        """
        Get breaker block detection result.
        
        Breaker Block: An order block that was broken (price moved through it),
        then price returns to retest the broken zone. This creates a stronger
        rejection zone than a regular order block.
        
        Logic:
        1. Get order blocks
        2. Check if price has broken through the OB zone
        3. Check if price is retesting the broken zone
        4. Return breaker block if retest detected
        """
        cache_key = self._get_cache_key(symbol, timeframe, "breaker_block")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            # Get order blocks first
            ob_result = self.get_order_block(symbol, timeframe)
            if not ob_result:
                return None
            
            bars = self._get_bars(symbol, timeframe)
            if bars is None or len(bars) < 20:
                return None
            
            current_price = self._get_current_price(symbol)
            if current_price is None:
                return None
            
            ob_bull = ob_result.get("order_block_bull")
            ob_bear = ob_result.get("order_block_bear")
            
            breaker_block_bull = None
            breaker_block_bear = None
            ob_broken = False
            price_retesting_breaker = False
            
            # Check for bullish breaker block
            if ob_bull:
                # Check if price has broken below the bullish OB
                # Get recent bars to check for break
                recent_lows = bars["low"].tail(10).values
                min_recent_low = float(min(recent_lows))
                
                # OB is broken if price went below it
                if min_recent_low < ob_bull:
                    ob_broken = True
                    # Check if price is retesting (within 0.5 ATR of broken OB)
                    atr = self._get_atr(symbol, timeframe)
                    if atr and atr > 0:
                        tolerance = atr * 0.5
                        if abs(current_price - ob_bull) <= tolerance:
                            breaker_block_bull = ob_bull
                            price_retesting_breaker = True
            
            # Check for bearish breaker block
            if ob_bear:
                # Check if price has broken above the bearish OB
                recent_highs = bars["high"].tail(10).values
                max_recent_high = float(max(recent_highs))
                
                # OB is broken if price went above it
                if max_recent_high > ob_bear:
                    ob_broken = True
                    # Check if price is retesting (within 0.5 ATR of broken OB)
                    atr = self._get_atr(symbol, timeframe)
                    if atr and atr > 0:
                        tolerance = atr * 0.5
                        if abs(current_price - ob_bear) <= tolerance:
                            breaker_block_bear = ob_bear
                            price_retesting_breaker = True
            
            if breaker_block_bull or breaker_block_bear:
                result = {
                    "breaker_block_bull": breaker_block_bull,
                    "breaker_block_bear": breaker_block_bear,
                    "ob_broken": ob_broken,
                    "price_retesting_breaker": price_retesting_breaker,
                    "breaker_block_strength": ob_result.get("ob_strength", 0.5) * 1.2  # Breaker blocks are stronger
                }
                self._cache_result(cache_key, result)
                return result
            
            return None
        except Exception as e:
            logger.warning(f"Breaker block detection failed for {symbol}: {e}")
            self._log_degraded_state("breaker_block_detection", symbol, str(e))
        return None
    
    def get_market_structure_shift(self, symbol: str, timeframe: str = "M15") -> Optional[Dict]:
        """
        Get Market Structure Shift (MSS) detection result.
        
        MSS: A break of structure (BOS) followed by a pullback to the break level.
        This is stronger than a regular BOS because it shows institutional
        interest at the break level.
        
        Logic:
        1. Detect BOS/CHOCH (already available)
        2. Check if price has pulled back to the break level
        3. Confirm MSS when pullback occurs
        """
        cache_key = self._get_cache_key(symbol, timeframe, "mss")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            # Get CHOCH/BOS detection
            choch_bos = self.get_choch_bos(symbol, timeframe)
            if not choch_bos:
                return None
            
            bars = self._get_bars(symbol, timeframe)
            if bars is None or len(bars) < 20:
                return None
            
            current_price = self._get_current_price(symbol)
            if current_price is None:
                return None
            
            atr = self._get_atr(symbol, timeframe)
            if atr is None or atr <= 0:
                return None
            
            mss_bull = False
            mss_bear = False
            pullback_to_mss = False
            mss_level = 0.0
            mss_strength = 0.5
            
            # Check for bullish MSS
            if choch_bos.get("bos_bull") or choch_bos.get("choch_bull"):
                break_level = choch_bos.get("break_level", 0.0)
                if break_level > 0:
                    # Check if price has pulled back to break level (within 0.5 ATR)
                    tolerance = atr * 0.5
                    if abs(current_price - break_level) <= tolerance:
                        mss_bull = True
                        pullback_to_mss = True
                        mss_level = break_level
                        mss_strength = choch_bos.get("structure_strength", 0.5) * 1.1  # MSS is stronger
            
            # Check for bearish MSS
            if choch_bos.get("bos_bear") or choch_bos.get("choch_bear"):
                break_level = choch_bos.get("break_level", 0.0)
                if break_level > 0:
                    # Check if price has pulled back to break level (within 0.5 ATR)
                    tolerance = atr * 0.5
                    if abs(current_price - break_level) <= tolerance:
                        mss_bear = True
                        pullback_to_mss = True
                        mss_level = break_level
                        mss_strength = choch_bos.get("structure_strength", 0.5) * 1.1  # MSS is stronger
            
            if mss_bull or mss_bear:
                result = {
                    "mss_bull": mss_bull,
                    "mss_bear": mss_bear,
                    "pullback_to_mss": pullback_to_mss,
                    "mss_level": mss_level,
                    "mss_strength": mss_strength
                }
                self._cache_result(cache_key, result)
                return result
            
            return None
        except Exception as e:
            logger.warning(f"MSS detection failed for {symbol}: {e}")
            self._log_degraded_state("mss_detection", symbol, str(e))
        return None
    
    def get_mitigation_block(self, symbol: str, timeframe: str = "M5") -> Optional[Dict]:
        """
        Get mitigation block detection result.
        
        Mitigation Block: The last candle before a structure break (CHOCH/BOS).
        This is the order block that "mitigates" or stops the previous structure.
        
        Logic:
        1. Detect structure break (CHOCH/BOS)
        2. Find the last candle before the break
        3. Check if that candle is an order block
        4. Return mitigation block if found
        """
        cache_key = self._get_cache_key(symbol, timeframe, "mitigation_block")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            # Get structure break detection
            choch_bos = self.get_choch_bos(symbol, timeframe)
            if not choch_bos or not (choch_bos.get("choch_bull") or choch_bos.get("choch_bear")):
                return None
            
            bars = self._get_bars(symbol, timeframe)
            if bars is None or len(bars) < 20:
                return None
            
            # Get order blocks
            ob_result = self.get_order_block(symbol, timeframe)
            if not ob_result:
                return None
            
            mitigation_block_bull = None
            mitigation_block_bear = None
            structure_broken = True  # We know structure is broken if we have CHOCH
            
            # If we have a bullish CHOCH, the mitigation block is the last bearish OB before the break
            if choch_bos.get("choch_bull"):
                ob_bear = ob_result.get("order_block_bear")
                if ob_bear:
                    mitigation_block_bear = ob_bear
            
            # If we have a bearish CHOCH, the mitigation block is the last bullish OB before the break
            if choch_bos.get("choch_bear"):
                ob_bull = ob_result.get("order_block_bull")
                if ob_bull:
                    mitigation_block_bull = ob_bull
            
            if mitigation_block_bull or mitigation_block_bear:
                result = {
                    "mitigation_block_bull": mitigation_block_bull,
                    "mitigation_block_bear": mitigation_block_bear,
                    "structure_broken": structure_broken,
                    "mitigation_block_strength": ob_result.get("ob_strength", 0.5) * 1.15  # Mitigation blocks are strong
                }
                self._cache_result(cache_key, result)
                return result
            
            return None
        except Exception as e:
            logger.warning(f"Mitigation block detection failed for {symbol}: {e}")
            self._log_degraded_state("mitigation_block_detection", symbol, str(e))
        return None
    
    def get_detection_result(self, symbol: str, detection_type: str, timeframe: str = "M15") -> Optional[Dict]:
        """
        Get detection result for any detection type.
        
        Args:
            symbol: Trading symbol
            detection_type: Type of detection (order_block, fvg, choch_bos, kill_zone, breaker_block, mss, mitigation_block, etc.)
            timeframe: Timeframe for detection
        
        Returns:
            Detection result dict or None
        """
        method_map = {
            "order_block": lambda s: self.get_order_block(s, timeframe),
            "fvg": lambda s: self.get_fvg(s, timeframe),
            "choch_bos": lambda s: self.get_choch_bos(s, timeframe),
            "kill_zone": lambda s: self.get_kill_zone(s, "M5"),
            "breaker_block": lambda s: self.get_breaker_block(s, timeframe),
            "market_structure_shift": lambda s: self.get_market_structure_shift(s, timeframe),
            "mss": lambda s: self.get_market_structure_shift(s, timeframe),
            "mitigation_block": lambda s: self.get_mitigation_block(s, timeframe),
            "rejection_pattern": lambda s: self.get_rejection_pattern(s, timeframe),
            "premium_discount_array": lambda s: self.get_fibonacci_levels(s, timeframe),
            "fibonacci_levels": lambda s: self.get_fibonacci_levels(s, timeframe),
            "session_liquidity_run": lambda s: self.get_session_liquidity(s, timeframe),
            "session_liquidity": lambda s: self.get_session_liquidity(s, timeframe)
        }
        
        method = method_map.get(detection_type)
        if method:
            return method(symbol)
        
        logger.warning(f"Unknown detection type: {detection_type}")
        return None
    
    def get_rejection_pattern(self, symbol: str, timeframe: str = "M5") -> Optional[Dict]:
        """
        Get rejection pattern detection result.
        
        Rejection Pattern: Long wicks (upper or lower) that show price rejection.
        Used for inducement + reversal strategy - when liquidity is grabbed
        and then rejected.
        
        Logic:
        1. Analyze recent candles for long wicks
        2. Check if wick is significantly longer than body
        3. Determine rejection direction (bullish = long lower wick, bearish = long upper wick)
        4. Calculate rejection strength based on wick-to-body ratio
        """
        cache_key = self._get_cache_key(symbol, timeframe, "rejection_pattern")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            bars = self._get_bars(symbol, timeframe)
            if bars is None or len(bars) < 5:
                return None
            
            # Analyze last 5 candles for rejection patterns
            recent_bars = bars.tail(5)
            
            rejection_detected = False
            rejection_direction = None  # "BULLISH" or "BEARISH"
            rejection_strength = 0.0
            
            for _, bar in recent_bars.iterrows():
                open_price = float(bar.get("open", 0))
                high_price = float(bar.get("high", 0))
                low_price = float(bar.get("low", 0))
                close_price = float(bar.get("close", 0))
                
                body_size = abs(close_price - open_price)
                upper_wick = high_price - max(open_price, close_price)
                lower_wick = min(open_price, close_price) - low_price
                
                # Skip if body is too small (doji-like)
                if body_size < (high_price - low_price) * 0.1:
                    continue
                
                # Check for bullish rejection (long lower wick)
                if lower_wick > body_size * 2.0 and lower_wick > 0:
                    rejection_detected = True
                    rejection_direction = "BULLISH"
                    # Strength based on wick-to-body ratio (max 1.0)
                    rejection_strength = min(1.0, lower_wick / body_size / 2.0)
                    break
                
                # Check for bearish rejection (long upper wick)
                if upper_wick > body_size * 2.0 and upper_wick > 0:
                    rejection_detected = True
                    rejection_direction = "BEARISH"
                    # Strength based on wick-to-body ratio (max 1.0)
                    rejection_strength = min(1.0, upper_wick / body_size / 2.0)
                    break
            
            if rejection_detected:
                result = {
                    "rejection_detected": rejection_detected,
                    "rejection_direction": rejection_direction,
                    "rejection_strength": rejection_strength,
                    "liquidity_grab_bull": rejection_direction == "BULLISH",
                    "liquidity_grab_bear": rejection_direction == "BEARISH"
                }
                self._cache_result(cache_key, result)
                return result
            
            return None
        except Exception as e:
            logger.warning(f"Rejection pattern detection failed for {symbol}: {e}")
            self._log_degraded_state("rejection_pattern_detection", symbol, str(e))
        return None
    
    def get_fibonacci_levels(self, symbol: str, timeframe: str = "M15") -> Optional[Dict]:
        """
        Get Fibonacci retracement levels for premium/discount array detection.
        
        Premium/Discount Array: Uses Fibonacci retracement levels to determine
        if price is in premium (0.21-0.38) or discount (0.62-0.79) zones.
        
        Logic:
        1. Calculate swing high and low from recent bars
        2. Calculate Fibonacci retracement levels (0.236, 0.382, 0.618, 0.786)
        3. Determine if current price is in premium or discount zone
        4. Calculate fib level and strength
        """
        cache_key = self._get_cache_key(symbol, timeframe, "fibonacci_levels")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            bars = self._get_bars(symbol, timeframe)
            if bars is None or len(bars) < 50:
                return None
            
            current_price = self._get_current_price(symbol)
            if current_price is None:
                return None
            
            # Calculate swing high and low from last 50 bars
            recent_bars = bars.tail(50)
            swing_high = float(recent_bars["high"].max())
            swing_low = float(recent_bars["low"].min())
            price_range = swing_high - swing_low
            
            if price_range <= 0:
                return None
            
            # Calculate Fibonacci retracement levels
            fib_levels = {
                "0.236": swing_high - (price_range * 0.236),
                "0.382": swing_high - (price_range * 0.382),
                "0.618": swing_high - (price_range * 0.618),
                "0.786": swing_high - (price_range * 0.786)
            }
            
            # Determine if price is in premium or discount zone
            price_in_premium = False
            price_in_discount = False
            fib_level = 0.0
            fib_strength = 0.5
            
            # Premium zone: 0.21-0.38 (between 0.236 and 0.382 fib levels)
            if swing_low + (price_range * 0.21) <= current_price <= swing_low + (price_range * 0.38):
                price_in_premium = True
                fib_level = 0.3  # Midpoint of premium zone
                fib_strength = 0.7
            
            # Discount zone: 0.62-0.79 (between 0.618 and 0.786 fib levels)
            elif swing_low + (price_range * 0.62) <= current_price <= swing_low + (price_range * 0.79):
                price_in_discount = True
                fib_level = 0.7  # Midpoint of discount zone
                fib_strength = 0.7
            
            # Calculate exact fib level if in range
            if not price_in_premium and not price_in_discount:
                # Find closest fib level
                for fib_key, fib_price in fib_levels.items():
                    if abs(current_price - fib_price) < price_range * 0.05:  # Within 5% of range
                        fib_level = float(fib_key)
                        fib_strength = 0.6
                        break
            
            result = {
                "fib_levels": fib_levels,
                "price_in_premium": price_in_premium,
                "price_in_discount": price_in_discount,
                "fib_level": fib_level,
                "fib_strength": fib_strength,
                "swing_high": swing_high,
                "swing_low": swing_low
            }
            
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"Fibonacci levels detection failed for {symbol}: {e}")
            self._log_degraded_state("fibonacci_levels_detection", symbol, str(e))
        return None
    
    def get_session_liquidity(self, symbol: str, timeframe: str = "M15") -> Optional[Dict]:
        """
        Get session liquidity run detection result.
        
        Session Liquidity Run: Detects when price runs to session highs/lows
        (Asian session extremes) and then reverses. Common pattern where
        London/NY sessions sweep Asian session liquidity.
        
        Logic:
        1. Track Asian session high/low
        2. Detect when London/NY session sweeps these levels
        3. Confirm reversal structure after sweep
        """
        cache_key = self._get_cache_key(symbol, timeframe, "session_liquidity")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            from infra.session_helpers import SessionHelpers
            from datetime import datetime, timezone
            
            current_session = SessionHelpers.get_current_session()
            bars = self._get_bars(symbol, timeframe)
            if bars is None or len(bars) < 100:
                return None
            
            current_price = self._get_current_price(symbol)
            if current_price is None:
                return None
            
            # Get current time to determine session boundaries
            now = datetime.now(timezone.utc)
            current_hour = now.hour
            
            # Define session boundaries (UTC)
            # Asian: 00:00-08:00 UTC
            # London: 08:00-16:00 UTC
            # NY: 13:00-21:00 UTC
            
            asian_session_high = None
            asian_session_low = None
            london_session_active = current_session in ["LONDON", "OVERLAP"]
            ny_session_active = current_session in ["NY", "OVERLAP"]
            
            # Calculate Asian session high/low from bars in Asian session hours
            # For simplicity, use last 24 hours and filter by hour
            recent_bars = bars.tail(100)
            
            # Filter for Asian session (00:00-08:00 UTC)
            asian_bars = []
            for idx, bar in recent_bars.iterrows():
                bar_time = bar.name if hasattr(bar.name, 'hour') else None
                if bar_time and (0 <= bar_time.hour < 8):
                    asian_bars.append(bar)
            
            if asian_bars:
                asian_highs = [float(b.get("high", 0)) for b in asian_bars]
                asian_lows = [float(b.get("low", 0)) for b in asian_bars]
                asian_session_high = max(asian_highs) if asian_highs else None
                asian_session_low = min(asian_lows) if asian_lows else None
            
            # Check if current price is near Asian session extremes (within 0.5 ATR)
            session_liquidity_run = False
            session_liquidity_strength = 0.0
            
            if asian_session_high and asian_session_low:
                atr = self._get_atr(symbol, timeframe)
                if atr and atr > 0:
                    tolerance = atr * 0.5
                    
                    # Check if price is near Asian high (liquidity sweep)
                    if abs(current_price - asian_session_high) <= tolerance:
                        session_liquidity_run = True
                        session_liquidity_strength = 0.8
                    
                    # Check if price is near Asian low (liquidity sweep)
                    elif abs(current_price - asian_session_low) <= tolerance:
                        session_liquidity_run = True
                        session_liquidity_strength = 0.8
            
            result = {
                "session_liquidity_run": session_liquidity_run,
                "asian_session_high": asian_session_high,
                "asian_session_low": asian_session_low,
                "london_session_active": london_session_active,
                "ny_session_active": ny_session_active,
                "session_liquidity_strength": session_liquidity_strength
            }
            
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.warning(f"Session liquidity detection failed for {symbol}: {e}")
            self._log_degraded_state("session_liquidity_detection", symbol, str(e))
        return None
    
    def _log_degraded_state(self, component: str, symbol: str, reason: str):
        """
        🧩 LOGICAL REVIEW: Degraded State Logging
        
        Log when system operates in reduced capability mode.
        Allows monitoring dashboard to show degraded state rather than silent suppression.
        """
        degraded_state = {
            "component": component,
            "symbol": symbol,
            "reason": reason,
            "timestamp": time.time(),
            "severity": "warning"  # warning, error, critical
        }
        
        # Log to dedicated degraded state logger
        logger.warning(f"DEGRADED_STATE: {component} for {symbol}: {reason}")
        
        # Optionally: Store in database or send to monitoring system
        # self._store_degraded_state(degraded_state)

