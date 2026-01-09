"""
Alpha Vantage Integration
Provides economic indicators, news sentiment, and market data for ChatGPT
"""

import logging
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class AlphaVantageService:
    """
    Alpha Vantage API integration for ChatGPT
    
    Free tier: 25 API calls/day
    Provides:
    - Economic indicators (GDP, inflation, unemployment, retail sales)
    - News sentiment analysis
    - Real-time forex quotes
    - Technical indicators
    """
    
    BASE_URL = "https://www.alphavantage.co/query"
    CACHE_DIR = Path("data/alpha_vantage_cache")
    CACHE_DURATION_HOURS = 24  # Economic data doesn't change often
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.logger.info("AlphaVantageService initialized")
    
    def _get_cached_data(self, cache_key: str) -> Optional[Dict]:
        """Load cached data if available and not expired"""
        cache_file = self.CACHE_DIR / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
            
            # Check if expired
            cached_time = datetime.fromisoformat(cached['timestamp'])
            age_hours = (datetime.now() - cached_time).total_seconds() / 3600
            
            if age_hours < self.CACHE_DURATION_HOURS:
                self.logger.info(f"Using cached data for {cache_key} (age: {age_hours:.1f}h)")
                return cached['data']
        except Exception as e:
            self.logger.warning(f"Failed to load cache for {cache_key}: {e}")
        
        return None
    
    def _save_to_cache(self, cache_key: str, data: Dict):
        """Save data to cache"""
        cache_file = self.CACHE_DIR / f"{cache_key}.json"
        
        try:
            with open(cache_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'data': data
                }, f)
        except Exception as e:
            self.logger.warning(f"Failed to save cache for {cache_key}: {e}")
    
    def _make_request(self, params: Dict) -> Dict:
        """Make API request with error handling"""
        params['apikey'] = self.api_key
        
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Check for API errors
            if 'Error Message' in data:
                raise Exception(f"Alpha Vantage error: {data['Error Message']}")
            
            if 'Note' in data:
                # Rate limit hit
                raise Exception(f"Alpha Vantage rate limit: {data['Note']}")
            
            return data
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {e}")
    
    # ==================== ECONOMIC INDICATORS ====================
    
    def get_economic_indicator(self, indicator: str = "GDP") -> Dict[str, Any]:
        """
        Get US economic indicator data
        
        Args:
            indicator: "GDP", "INFLATION", "UNEMPLOYMENT", "RETAIL_SALES", 
                      "NONFARM_PAYROLL", "CPI", "FEDERAL_FUNDS_RATE"
        
        Returns:
            {
                'indicator': 'GDP',
                'latest_value': '27.36',
                'latest_date': '2024-Q3',
                'previous_value': '27.09',
                'change_pct': 1.0,
                'interpretation': 'GDP growing at 1.0% quarter-over-quarter'
            }
        """
        cache_key = f"econ_{indicator.lower()}"
        
        # Check cache first
        cached = self._get_cached_data(cache_key)
        if cached:
            return cached
        
        # Fetch from API
        params = {
            'function': indicator,
            'interval': 'quarterly' if indicator == 'GDP' else 'monthly'
        }
        
        try:
            data = self._make_request(params)
            
            # Parse response
            data_key = list(data.keys())[1] if len(data.keys()) > 1 else 'data'
            values = data.get(data_key, [])
            
            if not values or len(values) < 2:
                raise Exception(f"Insufficient data for {indicator}")
            
            latest = values[0]
            previous = values[1]
            
            latest_value = float(latest.get('value', 0))
            previous_value = float(previous.get('value', 0))
            change_pct = ((latest_value - previous_value) / previous_value * 100) if previous_value else 0
            
            result = {
                'indicator': indicator,
                'latest_value': latest_value,
                'latest_date': latest.get('date', 'N/A'),
                'previous_value': previous_value,
                'change_pct': round(change_pct, 2),
                'interpretation': self._interpret_indicator(indicator, change_pct)
            }
            
            # Cache result
            self._save_to_cache(cache_key, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to fetch {indicator}: {e}")
            return {
                'indicator': indicator,
                'error': str(e),
                'interpretation': f"Unable to fetch {indicator} data"
            }
    
    def _interpret_indicator(self, indicator: str, change_pct: float) -> str:
        """Generate interpretation of economic indicator"""
        direction = "increasing" if change_pct > 0 else "decreasing"
        
        interpretations = {
            'GDP': f"GDP {direction} {abs(change_pct):.1f}% - economy {'expanding' if change_pct > 0 else 'contracting'}",
            'INFLATION': f"Inflation {direction} {abs(change_pct):.1f}% - prices {'rising faster' if change_pct > 0 else 'cooling'}",
            'UNEMPLOYMENT': f"Unemployment {direction} {abs(change_pct):.1f}% - labor market {'weakening' if change_pct > 0 else 'strengthening'}",
            'RETAIL_SALES': f"Retail sales {direction} {abs(change_pct):.1f}% - consumer spending {'strong' if change_pct > 0 else 'weak'}",
        }
        
        return interpretations.get(indicator, f"{indicator} changed {change_pct:+.1f}%")
    
    # ==================== NEWS SENTIMENT ====================
    
    def get_news_sentiment(self, tickers: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get news sentiment analysis
        
        Args:
            tickers: List of tickers to analyze (e.g., ['FOREX:USD', 'CRYPTO:BTC'])
        
        Returns:
            {
                'overall_sentiment': 'bullish',
                'sentiment_score': 0.35,
                'articles_analyzed': 50,
                'summary': 'Market sentiment is moderately bullish...'
            }
        """
        cache_key = "news_sentiment"
        
        # Check cache (shorter duration for news)
        cached = self._get_cached_data(cache_key)
        if cached:
            cached_time = datetime.fromisoformat(cached.get('timestamp', datetime.now().isoformat()))
            if (datetime.now() - cached_time).total_seconds() < 3600:  # 1 hour for news
                return cached
        
        params = {
            'function': 'NEWS_SENTIMENT',
            'topics': 'forex' if not tickers else ','.join(tickers),
            'limit': 50
        }
        
        try:
            data = self._make_request(params)
            
            feed = data.get('feed', [])
            if not feed:
                return {
                    'overall_sentiment': 'neutral',
                    'sentiment_score': 0.0,
                    'articles_analyzed': 0,
                    'summary': 'No recent news articles found'
                }
            
            # Calculate average sentiment
            sentiments = []
            for article in feed:
                if 'overall_sentiment_score' in article:
                    sentiments.append(float(article['overall_sentiment_score']))
            
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
            
            # Classify sentiment
            if avg_sentiment > 0.15:
                overall = 'bullish'
            elif avg_sentiment < -0.15:
                overall = 'bearish'
            else:
                overall = 'neutral'
            
            result = {
                'overall_sentiment': overall,
                'sentiment_score': round(avg_sentiment, 3),
                'articles_analyzed': len(feed),
                'summary': f"Market sentiment is {overall} based on {len(feed)} recent articles",
                'timestamp': datetime.now().isoformat()
            }
            
            # Cache result
            self._save_to_cache(cache_key, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to fetch news sentiment: {e}")
            return {
                'overall_sentiment': 'neutral',
                'sentiment_score': 0.0,
                'error': str(e),
                'summary': 'Unable to fetch news sentiment data'
            }
    
    # ==================== FOREX QUOTES ====================
    
    def get_forex_quote(self, from_currency: str = "USD", to_currency: str = "EUR") -> Dict[str, Any]:
        """
        Get real-time forex quote
        
        Returns:
            {
                'pair': 'USD/EUR',
                'rate': 0.92,
                'bid': 0.9195,
                'ask': 0.9205,
                'timestamp': '2025-10-09 20:30:00'
            }
        """
        cache_key = f"forex_{from_currency}{to_currency}"
        
        params = {
            'function': 'CURRENCY_EXCHANGE_RATE',
            'from_currency': from_currency,
            'to_currency': to_currency
        }
        
        try:
            data = self._make_request(params)
            
            exchange = data.get('Realtime Currency Exchange Rate', {})
            
            return {
                'pair': f"{from_currency}/{to_currency}",
                'rate': float(exchange.get('5. Exchange Rate', 0)),
                'bid': float(exchange.get('8. Bid Price', 0)),
                'ask': float(exchange.get('9. Ask Price', 0)),
                'timestamp': exchange.get('6. Last Refreshed', 'N/A')
            }
            
        except Exception as e:
            self.logger.error(f"Failed to fetch forex quote: {e}")
            return {
                'pair': f"{from_currency}/{to_currency}",
                'error': str(e)
            }


# Factory function
def create_alpha_vantage_service(api_key: Optional[str] = None) -> Optional[AlphaVantageService]:
    """
    Create AlphaVantageService instance
    
    Args:
        api_key: Alpha Vantage API key (or read from settings/env)
        
    Returns:
        AlphaVantageService instance or None if no API key
    """
    if api_key:
        return AlphaVantageService(api_key)
    
    # Try to get from settings
    try:
        from config import settings
        api_key = getattr(settings, "ALPHA_VANTAGE_API_KEY", None)
        if api_key:
            return AlphaVantageService(api_key)
    except Exception:
        pass
    
    # Try to get from environment
    import os
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if api_key:
        return AlphaVantageService(api_key)
    
    logger.warning("No Alpha Vantage API key found. Economic indicators will be unavailable.")
    return None

