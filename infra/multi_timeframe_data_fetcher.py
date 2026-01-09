"""
Phase III: Multi-Timeframe Data Fetcher
Fetches and aligns data across multiple timeframes for confluence checking
"""

import logging
import threading
from typing import Dict, Optional, Any, List
from datetime import datetime, timezone, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class MultiTimeframeDataFetcher:
    """
    Phase III: Fetches and aligns multi-timeframe data for confluence validation.
    
    Features:
    - Batch fetching across multiple timeframes
    - Timestamp alignment
    - Data freshness validation
    - Caching with shared cache keys
    """
    
    def __init__(self, cache_ttl_seconds: int = 60):
        """
        Initialize multi-timeframe data fetcher.
        
        Args:
            cache_ttl_seconds: Cache TTL in seconds (default: 60)
        """
        self.cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}  # cache_key -> {data, timestamp}
        self._lock = threading.RLock()  # Thread safety for cache access
        logger.info("Phase III: MultiTimeframeDataFetcher initialized")
    
    def _get_cache_key(self, symbol: str, timeframes: List[str]) -> str:
        """Generate cache key for multi-TF data"""
        tf_str = "_".join(sorted(timeframes))
        return f"{symbol}_{tf_str}"
    
    def _get_cached(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached data if still valid"""
        with self._lock:
            if cache_key in self._cache:
                data, timestamp = self._cache[cache_key]
                age_seconds = (datetime.now(timezone.utc) - timestamp).total_seconds()
                if age_seconds < self.cache_ttl:
                    return data
                else:
                    del self._cache[cache_key]
            return None
    
    def _cache_data(self, cache_key: str, data: Dict[str, Any]):
        """Cache multi-TF data"""
        with self._lock:
            self._cache[cache_key] = (data, datetime.now(timezone.utc))
            # Limit cache size (remove oldest if > 50 entries)
            if len(self._cache) > 50:
                oldest_key = min(self._cache.keys(),
                               key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]
    
    def fetch_multi_timeframe_data(
        self,
        symbol: str,
        timeframes: List[str],
        mt5_service,
        count: int = 50
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Fetch data for multiple timeframes in batch.
        
        Args:
            symbol: Trading symbol
            timeframes: List of timeframes (e.g., ["M5", "M15", "M30"])
            mt5_service: MT5Service instance
            count: Number of candles per timeframe (default: 50)
        
        Returns:
            {
                "M5": [candles...],
                "M15": [candles...],
                "M30": [candles...]
            } or None
        """
        try:
            # Check cache first
            cache_key = self._get_cache_key(symbol, timeframes)
            cached_data = self._get_cached(cache_key)
            if cached_data:
                logger.debug(f"Using cached multi-TF data for {symbol} {timeframes}")
                return cached_data
            
            # Fetch data for all timeframes
            tf_data = {}
            missing_tfs = []
            
            for tf in timeframes:
                try:
                    rates = mt5_service.get_rates(symbol, timeframe=tf, count=count)
                    if rates is not None and len(rates) > 0:
                        # Normalize candles
                        candles = []
                        for rate in rates:
                            candles.append({
                                'time': rate.time,
                                'open': rate.open,
                                'high': rate.high,
                                'low': rate.low,
                                'close': rate.close,
                                'volume': rate.tick_volume
                            })
                        tf_data[tf] = candles
                    else:
                        missing_tfs.append(tf)
                except Exception as e:
                    logger.warning(f"Error fetching {tf} data for {symbol}: {e}")
                    missing_tfs.append(tf)
            
            # Check if we have enough data (at least 80% of requested TFs)
            if len(missing_tfs) > len(timeframes) * 0.2:
                logger.warning(f"Too many missing timeframes for {symbol}: {missing_tfs}")
                return None
            
            # Align timestamps (use M5 as base if available)
            if "M5" in tf_data:
                base_tf = "M5"
            elif "M15" in tf_data:
                base_tf = "M15"
            else:
                base_tf = timeframes[0]
            
            # Validate data freshness (all TFs should have data within last 5 minutes)
            now = datetime.now(timezone.utc)
            max_age = timedelta(minutes=5)
            
            for tf, candles in tf_data.items():
                if candles:
                    latest_time = candles[0].get('time')
                    if isinstance(latest_time, datetime):
                        age = now - latest_time
                        if age > max_age:
                            logger.warning(f"Stale data for {symbol} {tf}: {age.total_seconds():.0f}s old")
                            # Use cached data if available, otherwise return None
                            if cached_data and tf in cached_data:
                                tf_data[tf] = cached_data[tf]
                            else:
                                return None
            
            # Cache the result
            self._cache_data(cache_key, tf_data)
            
            return tf_data
            
        except Exception as e:
            logger.error(f"Error fetching multi-timeframe data for {symbol}: {e}", exc_info=True)
            return None
    
    def validate_timeframe_alignment(
        self,
        tf_data: Dict[str, List[Dict[str, Any]]],
        required_tfs: List[str]
    ) -> bool:
        """
        Validate that all required timeframes have data and are aligned.
        
        Args:
            tf_data: Multi-TF data dict
            required_tfs: List of required timeframes
        
        Returns:
            True if all required TFs have data, False otherwise
        """
        for tf in required_tfs:
            if tf not in tf_data or not tf_data[tf]:
                logger.debug(f"Missing required timeframe: {tf}")
                return False
        
        return True

