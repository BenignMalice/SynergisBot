"""
DXY (Dollar Index) Service
Fetches DXY trend data from Yahoo Finance (free, no API key needed)
Falls back to Twelve Data if yfinance fails
"""

import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class DXYService:
    """
    Fetches DXY trend data with smart caching.
    
    Data Source Priority:
    1. Yahoo Finance (free, real DXY price ~99-107) - PRIMARY
    2. Twelve Data API (fallback, requires API key)
    
    Caching Strategy:
    - Cache DXY trend for 15 minutes (since we only need direction, not tick-by-tick)
    - Only fetch when cache expires or unavailable
    - No API credit usage with Yahoo Finance (free & unlimited)
    """
    
    CACHE_FILE = Path("data/dxy_cache.json")
    CACHE_DURATION_MINUTES = 15  # Cache DXY trend for 15 minutes
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.use_yfinance = True  # Prefer Yahoo Finance (free, real DXY)
        self.yfinance_symbol = "DX-Y.NYB"  # DXY on Yahoo Finance
        self.cache = self._load_cache()
        self.logger = logging.getLogger(__name__)
        self.logger.info("DXYService initialized (using Yahoo Finance - free, no API key needed)")
    
    def _load_cache(self) -> Dict:
        """Load cache from disk"""
        if self.CACHE_FILE.exists():
            try:
                with open(self.CACHE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load DXY cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save cache to disk"""
        try:
            self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            self.logger.warning(f"Failed to save DXY cache: {e}")
    
    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid"""
        if not self.cache or 'timestamp' not in self.cache:
            return False
        
        cached_time = datetime.fromisoformat(self.cache['timestamp'])
        age_minutes = (datetime.now() - cached_time).total_seconds() / 60
        
        return age_minutes < self.CACHE_DURATION_MINUTES
    
    def get_dxy_trend(self) -> Optional[str]:
        """
        Get DXY trend: "up", "down", or "neutral"
        
        Uses 15-minute cache to minimize API calls.
        
        Returns:
            str: "up", "down", or "neutral"
            None: If data unavailable or API error
        """
        # Check cache first
        if self._is_cache_valid():
            trend = self.cache.get('trend')
            self.logger.info(f"DXY trend from cache: {trend}")
            return trend
        
        # Cache expired, fetch fresh data
        try:
            trend = self._fetch_and_calculate_trend()
            
            # Update cache (keep symbol and price set by _fetch_with_symbol)
            self.cache['trend'] = trend
            self.cache['timestamp'] = datetime.now().isoformat()
            self._save_cache()
            
            self.logger.info(f"DXY trend fetched: {trend}")
            return trend
            
        except Exception as e:
            self.logger.error(f"Failed to fetch DXY trend: {e}")
            # Return cached trend if available, even if expired
            return self.cache.get('trend', None)
    
    def _fetch_and_calculate_trend(self) -> str:
        """
        Fetch DXY data and calculate trend.
        
        Priority:
        1. Yahoo Finance (free, real DXY)
        2. Twelve Data (fallback if yfinance fails)
        
        Strategy:
        - Fetch last 50 bars (1-hour interval)
        - Calculate 20-period SMA
        - If price > SMA and rising → "up"
        - If price < SMA and falling → "down"
        - Otherwise → "neutral"
        """
        # Try Yahoo Finance first (free, real DXY data)
        try:
            return self._fetch_from_yfinance()
        except Exception as e:
            self.logger.warning(f"Yahoo Finance failed: {e}")
            
            # Fallback to Twelve Data if available
            if self.api_key:
                self.logger.info("Falling back to Twelve Data API...")
                try:
                    return self._fetch_from_twelvedata()
                except Exception as e2:
                    self.logger.error(f"Twelve Data also failed: {e2}")
            
            raise Exception(f"Unable to fetch DXY data from any source")
    
    def _fetch_from_yfinance(self) -> str:
        """
        Fetch DXY from Yahoo Finance (free, real DXY ~99-107)
        """
        try:
            import yfinance as yf
        except ImportError:
            raise Exception("yfinance not installed. Run: pip install yfinance")
        
        # Fetch DXY data
        dxy = yf.Ticker(self.yfinance_symbol)
        hist = dxy.history(period="5d", interval="1h")
        
        if len(hist) < 20:
            raise Exception(f"Insufficient data from Yahoo Finance (got {len(hist)} bars, need 20)")
        
        # Extract closing prices
        closes = hist['Close'].tail(20).values
        current_price = float(closes[-1])
        prev_price = float(closes[-2])
        
        # Calculate 20-period SMA
        sma_20 = float(closes.mean())
        
        # Store in cache
        self.cache['price'] = current_price
        self.cache['symbol'] = self.yfinance_symbol
        self.cache['source'] = 'Yahoo Finance'
        
        self.logger.info(f"Yahoo Finance DXY: {current_price:.3f} (SMA: {sma_20:.3f})")
        
        # Determine trend
        price_above_sma = current_price > sma_20
        price_rising = current_price > prev_price
        
        if price_above_sma and price_rising:
            return "up"
        elif not price_above_sma and not price_rising:
            return "down"
        else:
            return "neutral"
    
    def _fetch_from_twelvedata(self) -> str:
        """
        Fallback: Fetch from Twelve Data API
        Note: Free tier may not have real DXY data
        """
        import requests
        
        # Try USDX (the only symbol that works on Twelve Data free tier)
        symbol = "USDX"
        
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": symbol,
            "interval": "1h",
            "outputsize": 50,
            "apikey": self.api_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'status' in data and data['status'] == 'error':
            raise Exception(f"Twelve Data API error: {data.get('message', 'Unknown error')}")
        
        values = data.get('values', [])
        if len(values) < 20:
            raise Exception(f"Insufficient data from Twelve Data (got {len(values)} bars)")
        
        # Extract closing prices
        closes = [float(bar['close']) for bar in values[:20]]
        current_price = closes[0]
        prev_price = closes[1]
        sma_20 = sum(closes) / len(closes)
        
        # Store in cache
        self.cache['price'] = current_price
        self.cache['symbol'] = symbol
        self.cache['source'] = 'Twelve Data'
        
        self.logger.warning(f"Using Twelve Data {symbol}: {current_price:.3f} (may not be real DXY)")
        
        # Determine trend
        if current_price > sma_20 and current_price > prev_price:
            return "up"
        elif current_price < sma_20 and current_price < prev_price:
            return "down"
        else:
            return "neutral"
    
    def _fetch_with_symbol(self, symbol: str) -> str:
        """
        Fetch data for a specific symbol and calculate trend
        """
        # Fetch time series data (1-hour bars for trend)
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": symbol,
            "interval": "1h",
            "outputsize": 50,
            "apikey": self.api_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'status' in data and data['status'] == 'error':
            raise Exception(f"Twelve Data API error: {data.get('message', 'Unknown error')}")
        
        values = data.get('values', [])
        if len(values) < 20:
            self.logger.warning(f"Insufficient data for {symbol} trend calculation")
            return "neutral"
        
        # Extract closing prices
        closes = [float(bar['close']) for bar in values[:20]]
        current_price = closes[0]
        prev_price = closes[1]
        
        # Calculate 20-period SMA
        sma_20 = sum(closes) / len(closes)
        
        # Store current price and symbol in cache
        self.cache['price'] = current_price
        self.cache['symbol'] = symbol
        self.logger.info(f"Successfully fetched {symbol}: price={current_price:.3f}, trend calculation in progress...")
        
        # Determine trend
        price_above_sma = current_price > sma_20
        price_rising = current_price > prev_price
        
        # Calculate trend
        if price_above_sma and price_rising:
            return "up"
        elif not price_above_sma and not price_rising:
            return "down"
        else:
            return "neutral"
    
    def get_dxy_price(self) -> Optional[float]:
        """
        Get current DXY price (from cache if available).
        
        Returns:
            float: Current DXY price
            None: If unavailable
        """
        if self._is_cache_valid():
            return self.cache.get('price')
        
        # If cache expired, trigger trend fetch (which updates price)
        self.get_dxy_trend()
        return self.cache.get('price')
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache status information"""
        if not self.cache or 'timestamp' not in self.cache:
            return {
                'valid': False,
                'age_minutes': None,
                'trend': None,
                'price': None
            }
        
        cached_time = datetime.fromisoformat(self.cache['timestamp'])
        age_minutes = (datetime.now() - cached_time).total_seconds() / 60
        
        return {
            'valid': self._is_cache_valid(),
            'age_minutes': round(age_minutes, 1),
            'trend': self.cache.get('trend'),
            'price': self.cache.get('price'),
            'cached_at': self.cache['timestamp']
        }


# Factory function
def create_dxy_service(api_key: Optional[str] = None) -> Optional[DXYService]:
    """
    Create DXYService instance with API key from settings.
    
    Args:
        api_key: Twelve Data API key (or read from settings/env)
        
    Returns:
        DXYService instance or None if no API key
    """
    if api_key:
        return DXYService(api_key)
    
    # Try to get from settings
    try:
        from config import settings
        api_key = getattr(settings, "TWELVE_DATA_API_KEY", None)
        if api_key:
            return DXYService(api_key)
    except Exception:
        pass
    
    # Try to get from environment
    import os
    api_key = os.getenv("TWELVE_DATA_API_KEY")
    if api_key:
        return DXYService(api_key)
    
    logger.warning("No Twelve Data API key found. DXY correlation filter will be disabled.")
    return None

