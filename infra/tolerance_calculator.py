"""
Dynamic Tolerance Calculator

Calculates price tolerance dynamically based on ATR and symbol characteristics.
Replaces static tolerance values with adaptive tolerances that adjust to market volatility.

🧩 LOGICAL REVIEW: Tolerance Calculator Integration
- Works with existing tolerance_helper.py system
- Uses ATR from StreamerDataAccess or UniversalDynamicSLTPManager
- Includes cache TTL (60 seconds)
- Symbol-specific and timeframe-specific adjustments
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Any
from config import settings

logger = logging.getLogger(__name__)


class ToleranceCalculator:
    """Calculate dynamic tolerance based on ATR and symbol characteristics"""
    
    def __init__(self, config_path: str = "config/tolerance_settings.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._cache: Dict[str, Dict[str, Any]] = {}  # {cache_key: {tolerance, timestamp}}
        self._cache_ttl = 60  # 60 seconds cache TTL
    
    def _load_config(self) -> Dict:
        """Load tolerance configuration"""
        default_config = {
            "tolerance_settings": {
                "enabled": True,
                "base_atr_mult": 0.5,
                "min_tolerance": 2.0,
                "max_tolerance": 50.0,
                "symbol_overrides": {
                    "BTCUSDc": {
                        "base_atr_mult": 0.6,
                        "min_tolerance": 10.0,
                        "max_tolerance": 100.0
                    },
                    "XAUUSDc": {
                        "base_atr_mult": 0.4,
                        "min_tolerance": 3.0,
                        "max_tolerance": 20.0
                    }
                },
                "timeframe_overrides": {
                    "M5": {
                        "base_atr_mult": 0.3
                    },
                    "H1": {
                        "base_atr_mult": 0.7
                    }
                }
            }
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    file_config = json.load(f)
                return {**default_config, **file_config}
            except Exception as e:
                logger.warning(f"Failed to load tolerance config: {e}, using defaults")
        
        return default_config
    
    def calculate_tolerance(
        self,
        symbol: str,
        timeframe: str = "M15",
        base_atr_mult: Optional[float] = None,
        min_tolerance: Optional[float] = None,
        max_tolerance: Optional[float] = None
    ) -> float:
        """
        Calculate dynamic tolerance for symbol/timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (M5, M15, H1, etc.)
            base_atr_mult: Override base ATR multiplier
            min_tolerance: Override min tolerance
            max_tolerance: Override max tolerance
        
        Returns:
            Tolerance value in price units
        """
        if not self.config.get("tolerance_settings", {}).get("enabled", True):
            # Fallback to static tolerance if disabled
            return self._get_static_tolerance(symbol)
        
        # Check cache
        cache_key = f"{symbol}_{timeframe}_{base_atr_mult}_{min_tolerance}_{max_tolerance}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        # Get settings
        settings = self.config.get("tolerance_settings", {})
        
        # Get base multiplier (use override or config)
        if base_atr_mult is None:
            base_atr_mult = settings.get("base_atr_mult", 0.5)
        
        # Get ATR
        atr = self._get_atr(symbol, timeframe)
        if atr is None or atr <= 0:
            logger.warning(f"Could not get ATR for {symbol} {timeframe}, using static tolerance")
            tolerance = self._get_static_tolerance(symbol)
            self._cache_result(cache_key, tolerance)
            return tolerance
        
        # Calculate base tolerance
        tolerance = atr * base_atr_mult
        
        # Apply symbol-specific adjustments
        symbol_upper = symbol.upper()
        symbol_overrides = settings.get("symbol_overrides", {}).get(symbol_upper, {})
        if symbol_overrides:
            if "base_atr_mult" in symbol_overrides:
                tolerance = atr * symbol_overrides["base_atr_mult"]
            if "min_tolerance" in symbol_overrides:
                min_tolerance = symbol_overrides["min_tolerance"]
            if "max_tolerance" in symbol_overrides:
                max_tolerance = symbol_overrides["max_tolerance"]
        
        # Apply timeframe-specific adjustments
        timeframe_overrides = settings.get("timeframe_overrides", {}).get(timeframe, {})
        if timeframe_overrides and "base_atr_mult" in timeframe_overrides:
            tolerance = atr * timeframe_overrides["base_atr_mult"]
        
        # Apply min/max bounds
        if min_tolerance is None:
            min_tolerance = settings.get("min_tolerance", 2.0)
        if max_tolerance is None:
            max_tolerance = settings.get("max_tolerance", 50.0)
        
        tolerance = max(min_tolerance, min(tolerance, max_tolerance))
        
        # Cache result
        self._cache_result(cache_key, tolerance)
        return tolerance
    
    def get_tolerance_for_condition(
        self,
        symbol: str,
        condition: Dict[str, Any],
        timeframe: str = "M15"
    ) -> float:
        """
        Get tolerance for a specific condition.
        
        If condition specifies tolerance, use it (but validate against ATR-based max).
        If condition doesn't specify tolerance, calculate dynamically.
        
        Args:
            symbol: Trading symbol
            condition: Condition dictionary (may contain 'tolerance' key)
            timeframe: Timeframe (extracted from condition or default)
        
        Returns:
            Tolerance value
        """
        # Extract timeframe from condition if available
        if "timeframe" in condition:
            timeframe = condition.get("timeframe", timeframe)
        
        # If tolerance specified in condition, validate it
        if "tolerance" in condition:
            specified_tolerance = float(condition["tolerance"])
            
            # Calculate max reasonable tolerance based on ATR
            max_tolerance = self.calculate_tolerance(
                symbol,
                timeframe,
                base_atr_mult=1.0,  # 100% of ATR as max
                max_tolerance=100.0
            )
            
            # If specified tolerance exceeds 2x max, use calculated tolerance
            if specified_tolerance > max_tolerance * 2:
                logger.warning(
                    f"Specified tolerance {specified_tolerance} exceeds reasonable max {max_tolerance}, "
                    f"using calculated tolerance for {symbol}"
                )
                return self.calculate_tolerance(symbol, timeframe)
            
            return specified_tolerance
        
        # Calculate dynamic tolerance
        return self.calculate_tolerance(symbol, timeframe)
    
    def _get_atr(self, symbol: str, timeframe: str, period: int = 14) -> Optional[float]:
        """Get ATR for symbol/timeframe"""
        try:
            # Try StreamerDataAccess first
            from infra.streamer_data_access import StreamerDataAccess
            streamer = StreamerDataAccess()
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
            
            return None
        except Exception as e:
            logger.debug(f"Error getting ATR for {symbol} {timeframe}: {e}")
            return None
    
    def _get_static_tolerance(self, symbol: str) -> float:
        """Get static tolerance fallback"""
        # Use existing tolerance_helper if available
        try:
            from infra.tolerance_helper import get_tolerance
            return get_tolerance(symbol)
        except Exception:
            # Default fallback
            symbol_upper = symbol.upper()
            if "BTC" in symbol_upper:
                return 20.0
            elif "XAU" in symbol_upper or "GOLD" in symbol_upper:
                return 5.0
            else:
                return 2.0
    
    def _get_cached(self, cache_key: str) -> Optional[float]:
        """Get cached tolerance if still valid"""
        cached = self._cache.get(cache_key)
        if cached:
            age = time.time() - cached.get("timestamp", 0)
            if age < self._cache_ttl:
                return cached.get("tolerance")
            else:
                # Expired, remove from cache
                del self._cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, tolerance: float):
        """Cache tolerance result"""
        self._cache[cache_key] = {
            "tolerance": tolerance,
            "timestamp": time.time()
        }
        # Cleanup old cache entries (keep last 50)
        if len(self._cache) > 50:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest_key]

