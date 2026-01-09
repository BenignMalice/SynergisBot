"""
FRED (Federal Reserve Economic Data) Service
Fetches economic data from FRED API (free, requires API key from email signup)

Provides:
- Breakeven Inflation Rate (T10YIE) - 10-Year Breakeven Inflation Rate
- Fed Funds Rate (FEDFUNDS) - Effective Federal Funds Rate
- 2-Year Treasury Yield (DGS2) - 2-Year Treasury Constant Maturity Rate
- Generic series fetching for other FRED data
"""

import logging
import os
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class FREDService:
    """
    FRED API wrapper for fetching economic data
    
    API Key: Free registration at https://fred.stlouisfed.org/docs/api/api_key.html
    Rate Limits: 120 requests/minute (free tier)
    """
    
    BASE_URL = "https://api.stlouisfed.org/fred"
    CACHE_FILE = Path("data/fred_cache.json")
    CACHE_DURATION_MINUTES = {
        'daily': 60,      # Daily data cached for 1 hour
        'monthly': 24 * 60  # Monthly data cached for 24 hours
    }
    
    # FRED Series IDs
    SERIES_BREAKEVEN = "T10YIE"      # 10-Year Breakeven Inflation Rate
    SERIES_FEDFUNDS = "FEDFUNDS"     # Effective Federal Funds Rate
    SERIES_2Y_YIELD = "DGS2"         # 2-Year Treasury Constant Maturity Rate
    SERIES_2Y10Y_SPREAD = "T10Y2Y"   # 2Y-10Y Treasury Spread
    SERIES_CPI = "CPIAUCSL"          # Consumer Price Index (Monthly)
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize FRED Service
        
        Args:
            api_key: FRED API key (or reads from FRED_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("FRED_API_KEY", "")
        if not self.api_key:
            logger.warning("FRED_API_KEY not found. Real yield and Fed expectations will be unavailable.")
        
        self.cache = self._load_cache()
        self.logger = logging.getLogger(__name__)
        
        if self.api_key:
            self.logger.info("FREDService initialized with API key")
        else:
            self.logger.warning("FREDService initialized without API key (data will be unavailable)")
    
    def _load_cache(self) -> Dict:
        """Load cache from disk"""
        if self.CACHE_FILE.exists():
            try:
                with open(self.CACHE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load FRED cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save cache to disk"""
        try:
            self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            self.logger.warning(f"Failed to save FRED cache: {e}")
    
    def _is_cache_valid(self, key: str, update_frequency: str = 'daily') -> bool:
        """
        Check if cached data is still valid
        
        Args:
            key: Cache key
            update_frequency: 'daily' or 'monthly' (affects cache duration)
        """
        if key not in self.cache or 'timestamp' not in self.cache[key]:
            return False
        
        cached_time = datetime.fromisoformat(self.cache[key]['timestamp'])
        age_minutes = (datetime.now() - cached_time).total_seconds() / 60
        max_age = self.CACHE_DURATION_MINUTES.get(update_frequency, 60)
        
        return age_minutes < max_age
    
    def get_series(self, series_id: str, limit: int = 1, update_frequency: str = 'daily') -> Optional[float]:
        """
        Get latest value from FRED series
        
        Args:
            series_id: FRED series ID (e.g., 'T10YIE', 'FEDFUNDS')
            limit: Number of recent observations to return (default: 1 for latest)
            update_frequency: 'daily' or 'monthly' (for cache duration)
        
        Returns:
            Latest value (float) or None if unavailable
        """
        if not self.api_key:
            self.logger.warning(f"Cannot fetch FRED series {series_id}: No API key")
            return None
        
        cache_key = f"series_{series_id}"
        
        # Check cache first
        if self._is_cache_valid(cache_key, update_frequency):
            self.logger.debug(f"Using cached FRED data for {series_id}")
            return self.cache[cache_key].get('value')
        
        try:
            # FRED API endpoint: /series/observations
            url = f"{self.BASE_URL}/series/observations"
            params = {
                'series_id': series_id,
                'api_key': self.api_key,
                'file_type': 'json',
                'limit': limit,
                'sort_order': 'desc',  # Most recent first
                'observation_start': (datetime.now() - timedelta(days=365 * 2)).strftime('%Y-%m-%d')  # Last 2 years
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'observations' not in data or len(data['observations']) == 0:
                self.logger.warning(f"No observations found for FRED series {series_id}")
                return None
            
            # Get latest non-null value
            observations = data['observations']
            for obs in observations:
                value_str = obs.get('value', '')
                if value_str and value_str != '.':
                    try:
                        value = float(value_str)
                        
                        # Cache the result
                        self.cache[cache_key] = {
                            'value': value,
                            'timestamp': datetime.now().isoformat(),
                            'date': obs.get('date', '')
                        }
                        self._save_cache()
                        
                        self.logger.info(f"Fetched FRED {series_id}: {value}")
                        return value
                    except (ValueError, TypeError):
                        continue
            
            self.logger.warning(f"No valid value found for FRED series {series_id}")
            return None
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"FRED API request failed for {series_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching FRED series {series_id}: {e}", exc_info=True)
            return None
    
    def get_breakeven_rate(self) -> Optional[float]:
        """
        Get 10-Year Breakeven Inflation Rate (T10YIE)
        
        This is market-implied inflation expectation (more accurate than CPI-based)
        
        Returns:
            Breakeven rate as percentage (e.g., 2.5 for 2.5%) or None
        """
        return self.get_series(self.SERIES_BREAKEVEN, update_frequency='daily')
    
    def get_fed_funds_rate(self) -> Optional[float]:
        """
        Get Current Fed Funds Rate (FEDFUNDS)
        
        Returns:
            Fed funds rate as percentage (e.g., 5.25 for 5.25%) or None
        """
        return self.get_series(self.SERIES_FEDFUNDS, update_frequency='daily')
    
    def get_2y_yield(self) -> Optional[float]:
        """
        Get 2-Year Treasury Yield (DGS2)
        
        Used to track Fed expectations (2Y yield changes with Fed expectations)
        
        Returns:
            2Y yield as percentage (e.g., 4.75 for 4.75%) or None
        """
        return self.get_series(self.SERIES_2Y_YIELD, update_frequency='daily')
    
    def get_2y10y_spread(self) -> Optional[float]:
        """
        Get 2Y-10Y Treasury Spread (T10Y2Y)
        
        Inversion signals recession risk → Fed likely to cut
        
        Returns:
            Spread in percentage points (e.g., -0.5 for inverted) or None
        """
        return self.get_series(self.SERIES_2Y10Y_SPREAD, update_frequency='daily')
    
    def get_cpi(self) -> Optional[float]:
        """
        Get Consumer Price Index (CPIAUCSL)
        
        Monthly data, cached for 24 hours
        
        Returns:
            CPI index value or None
        """
        return self.get_series(self.SERIES_CPI, update_frequency='monthly')
    
    def calculate_real_yield(self, us10y_nominal: Optional[float]) -> Optional[float]:
        """
        Calculate real yield using breakeven rate
        
        Real Yield = US10Y Nominal - Breakeven Inflation Rate
        
        Args:
            us10y_nominal: 10-Year Treasury yield (percentage, e.g., 4.5 for 4.5%)
        
        Returns:
            Real yield as percentage or None if data unavailable
        """
        if us10y_nominal is None:
            return None
        
        breakeven = self.get_breakeven_rate()
        if breakeven is None:
            self.logger.warning("Cannot calculate real yield: Breakeven rate unavailable")
            return None
        
        real_yield = us10y_nominal - breakeven
        self.logger.info(f"Real yield calculated: {real_yield:.2f}% (US10Y: {us10y_nominal:.2f}% - Breakeven: {breakeven:.2f}%)")
        return real_yield


# Factory function
def create_fred_service(api_key: Optional[str] = None) -> FREDService:
    """
    Create FREDService instance with API key from settings or environment
    
    Args:
        api_key: FRED API key (or read from settings/env)
    
    Returns:
        FREDService instance (always returned, even without API key)
    """
    if api_key:
        return FREDService(api_key)
    
    # Try to get from settings
    try:
        from config import settings
        api_key = os.getenv("FRED_API_KEY") or getattr(settings, "FRED_API_KEY", None)
        if api_key:
            return FREDService(api_key)
    except Exception:
        pass
    
    # Try to get from environment
    api_key = os.getenv("FRED_API_KEY")
    if api_key:
        return FREDService(api_key)
    
    # Return service without key (will log warnings but won't crash)
    return FREDService(None)


