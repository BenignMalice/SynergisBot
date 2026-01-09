"""
Market Indices Service
Fetches DXY (US Dollar Index) and VIX (Volatility Index) from Yahoo Finance
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class MarketIndicesService:
    """
    Fetches market indices from Yahoo Finance (free, no API key needed)
    
    Provides:
    - DXY (US Dollar Index) - Real DXY ~99-107
    - VIX (Volatility Index) - Market fear gauge
    - US10Y (10-Year Treasury Yield) - Bond yields ~3.5-4.5%
    
    All data is FREE and matches TradingView!
    """
    
    CACHE_FILE = Path("data/market_indices_cache.json")
    CACHE_DURATION_MINUTES = 15  # Cache for 15 minutes
    
    def __init__(self):
        self.dxy_symbol = "DX-Y.NYB"  # Real DXY on Yahoo Finance
        self.vix_symbol = "^VIX"      # VIX on Yahoo Finance
        self.us10y_symbol = "^TNX"    # 10-Year Treasury Yield on Yahoo Finance
        self.sp500_symbol = "^GSPC"   # S&P 500 Index on Yahoo Finance
        self.nasdaq_symbol = "^IXIC"  # NASDAQ Composite Index
        self.cache = self._load_cache()
        self.logger = logging.getLogger(__name__)
        self.logger.info("MarketIndicesService initialized (using Yahoo Finance - free)")
    
    def _load_cache(self) -> Dict:
        """Load cache from disk"""
        if self.CACHE_FILE.exists():
            try:
                with open(self.CACHE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save cache to disk"""
        try:
            self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            self.logger.warning(f"Failed to save cache: {e}")
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid"""
        if key not in self.cache or 'timestamp' not in self.cache[key]:
            return False
        
        cached_time = datetime.fromisoformat(self.cache[key]['timestamp'])
        age_minutes = (datetime.now() - cached_time).total_seconds() / 60
        
        return age_minutes < self.CACHE_DURATION_MINUTES
    
    def get_dxy(self) -> Dict[str, Any]:
        """
        Get DXY (US Dollar Index) data
        
        Returns:
            {
                'price': 99.428,
                'trend': 'up',  # up/down/neutral
                'interpretation': 'USD strengthening',
                'timestamp': '2025-10-09T20:00:00',
                'source': 'Yahoo Finance'
            }
        """
        # Check cache first
        if self._is_cache_valid('dxy'):
            self.logger.info("Using cached DXY data")
            return self.cache['dxy']['data']
        
        try:
            import yfinance as yf
            
            # Fetch DXY data
            dxy = yf.Ticker(self.dxy_symbol)
            hist = dxy.history(period="5d", interval="1h")
            
            if len(hist) < 20:
                raise Exception("Insufficient DXY data")
            
            # Get current price and calculate trend
            closes = hist['Close'].tail(20).values
            current_price = float(closes[-1])
            prev_price = float(closes[-2])
            sma_20 = float(closes.mean())
            
            # Determine trend
            price_above_sma = current_price > sma_20
            price_rising = current_price > prev_price
            
            if price_above_sma and price_rising:
                trend = "up"
                interpretation = "USD strengthening"
            elif not price_above_sma and not price_rising:
                trend = "down"
                interpretation = "USD weakening"
            else:
                trend = "neutral"
                interpretation = "USD mixed/consolidating"
            
            result = {
                'price': round(current_price, 3),
                'trend': trend,
                'interpretation': interpretation,
                'timestamp': datetime.now().isoformat(),
                'source': 'Yahoo Finance (DX-Y.NYB)'
            }
            
            # Cache result
            self.cache['dxy'] = {
                'data': result,
                'timestamp': datetime.now().isoformat()
            }
            self._save_cache()
            
            self.logger.info(f"DXY: {current_price:.3f} ({trend})")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to fetch DXY: {e}")
            return {
                'price': None,
                'trend': 'unknown',
                'interpretation': f"Error fetching DXY: {str(e)}",
                'timestamp': datetime.now().isoformat(),
                'source': 'Yahoo Finance (error)'
            }
    
    def get_vix(self) -> Dict[str, Any]:
        """
        Get VIX (Volatility Index) data
        
        Returns:
            {
                'price': 16.90,
                'level': 'normal',  # low/normal/elevated/high
                'risk': 'moderate',
                'interpretation': 'Standard market conditions',
                'timestamp': '2025-10-09T20:00:00',
                'source': 'Yahoo Finance'
            }
        """
        # Check cache first
        if self._is_cache_valid('vix'):
            self.logger.info("Using cached VIX data")
            return self.cache['vix']['data']
        
        try:
            import yfinance as yf
            
            # Fetch VIX data
            vix = yf.Ticker(self.vix_symbol)
            hist = vix.history(period="5d", interval="1h")
            
            if len(hist) == 0:
                raise Exception("No VIX data available")
            
            current_price = float(hist['Close'].iloc[-1])
            
            # Interpret VIX level
            if current_price < 15:
                level = "low"
                risk = "low"
                interpretation = "Complacent market - good for trend trading"
            elif current_price < 20:
                level = "normal"
                risk = "moderate"
                interpretation = "Standard market conditions"
            elif current_price < 30:
                level = "elevated"
                risk = "high"
                interpretation = "Elevated uncertainty - use wider stops"
            else:
                level = "high"
                risk = "very_high"
                interpretation = "Fear/panic - avoid new positions"
            
            result = {
                'price': round(current_price, 2),
                'level': level,
                'risk': risk,
                'interpretation': interpretation,
                'timestamp': datetime.now().isoformat(),
                'source': 'Yahoo Finance (^VIX)'
            }
            
            # Cache result
            self.cache['vix'] = {
                'data': result,
                'timestamp': datetime.now().isoformat()
            }
            self._save_cache()
            
            self.logger.info(f"VIX: {current_price:.2f} ({level})")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to fetch VIX: {e}")
            return {
                'price': None,
                'level': 'unknown',
                'risk': 'unknown',
                'interpretation': f"Error fetching VIX: {str(e)}",
                'timestamp': datetime.now().isoformat(),
                'source': 'Yahoo Finance (error)'
            }
    
    def get_us10y(self) -> Dict[str, Any]:
        """
        Get US10Y (10-Year Treasury Yield) data
        
        Returns:
            {
                'price': 4.25,  # Yield percentage
                'trend': 'up',  # up/down/neutral
                'level': 'elevated',  # low/normal/elevated/high
                'interpretation': 'Rising yields - bearish for Gold',
                'gold_correlation': 'bearish',  # bearish/neutral/bullish for gold
                'timestamp': '2025-10-09T20:00:00',
                'source': 'Yahoo Finance'
            }
        """
        # Check cache first
        if self._is_cache_valid('us10y'):
            self.logger.info("Using cached US10Y data")
            return self.cache['us10y']['data']
        
        try:
            import yfinance as yf
            
            # Fetch US10Y data
            us10y = yf.Ticker(self.us10y_symbol)
            hist = us10y.history(period="5d", interval="1h")
            
            if len(hist) < 20:
                raise Exception("Insufficient US10Y data")
            
            # Get current yield and calculate trend
            closes = hist['Close'].tail(20).values
            current_yield = float(closes[-1])
            prev_yield = float(closes[-2])
            sma_20 = float(closes.mean())
            
            # Determine trend
            yield_above_sma = current_yield > sma_20
            yield_rising = current_yield > prev_yield
            
            if yield_above_sma and yield_rising:
                trend = "up"
                gold_correlation = "bearish"  # Rising yields = bearish for gold
                interpretation = "Rising yields → Bearish for Gold (opportunity cost)"
            elif not yield_above_sma and not yield_rising:
                trend = "down"
                gold_correlation = "bullish"  # Falling yields = bullish for gold
                interpretation = "Falling yields → Bullish for Gold"
            else:
                trend = "neutral"
                gold_correlation = "neutral"
                interpretation = "Yields consolidating → Mixed for Gold"
            
            # Determine level
            if current_yield < 3.0:
                level = "low"
            elif current_yield < 4.0:
                level = "normal"
            elif current_yield < 5.0:
                level = "elevated"
            else:
                level = "high"
            
            result = {
                'price': round(current_yield, 3),  # Yield as percentage
                'trend': trend,
                'level': level,
                'interpretation': interpretation,
                'gold_correlation': gold_correlation,
                'timestamp': datetime.now().isoformat(),
                'source': 'Yahoo Finance (^TNX)'
            }
            
            # Cache result
            self.cache['us10y'] = {
                'data': result,
                'timestamp': datetime.now().isoformat()
            }
            self._save_cache()
            
            self.logger.info(f"US10Y: {current_yield:.3f}% ({trend}, {gold_correlation} for gold)")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to fetch US10Y: {e}")
            return {
                'price': None,
                'trend': 'unknown',
                'level': 'unknown',
                'interpretation': f"Error fetching US10Y: {str(e)}",
                'gold_correlation': 'unknown',
                'timestamp': datetime.now().isoformat(),
                'source': 'Yahoo Finance (error)'
            }
    
    def get_market_context(self) -> Dict[str, Any]:
        """
        Get combined market context (DXY + VIX + US10Y)
        
        Returns complete picture:
        - USD strength (from DXY)
        - Market volatility/fear (from VIX)
        - Bond yields (from US10Y)
        - Trading implications (especially for Gold)
        """
        dxy_data = self.get_dxy()
        vix_data = self.get_vix()
        us10y_data = self.get_us10y()
        
        # Generate trading implications
        implications = []
        gold_signals = []
        
        # USD implications
        if dxy_data['trend'] == 'up':
            implications.append("USD strengthening → Avoid buying Gold/BTC/EUR")
            gold_signals.append("bearish")
        elif dxy_data['trend'] == 'down':
            implications.append("USD weakening → Good for Gold/BTC/EUR longs")
            gold_signals.append("bullish")
        else:
            gold_signals.append("neutral")
        
        # VIX implications
        if vix_data['level'] == 'low':
            implications.append("Low volatility → Good for tight stops")
        elif vix_data['level'] == 'high':
            implications.append("High volatility → Use wide stops or wait")
        
        # US10Y implications (critical for Gold)
        if us10y_data['gold_correlation'] == 'bearish':
            implications.append("Rising yields → Bearish for Gold (opportunity cost)")
            gold_signals.append("bearish")
        elif us10y_data['gold_correlation'] == 'bullish':
            implications.append("Falling yields → Bullish for Gold")
            gold_signals.append("bullish")
        else:
            gold_signals.append("neutral")
        
        # Calculate Gold confluence (DXY + US10Y)
        bearish_count = gold_signals.count("bearish")
        bullish_count = gold_signals.count("bullish")
        
        if bearish_count >= 2:
            gold_outlook = "🔴 BEARISH - Both DXY and US10Y against Gold"
        elif bullish_count >= 2:
            gold_outlook = "🟢 BULLISH - Both DXY and US10Y favor Gold"
        else:
            gold_outlook = "⚪ MIXED - Conflicting signals for Gold"
        
        return {
            'dxy': dxy_data,
            'vix': vix_data,
            'us10y': us10y_data,
            'implications': implications,
            'gold_outlook': gold_outlook,
            'summary': self._generate_summary(dxy_data, vix_data, us10y_data),
            'timestamp': datetime.now().isoformat()
        }
    
    def _generate_summary(self, dxy: Dict, vix: Dict, us10y: Dict) -> str:
        """Generate human-readable summary"""
        dxy_str = f"DXY {dxy['price']:.2f} ({dxy['interpretation']})" if dxy['price'] else "DXY unavailable"
        vix_str = f"VIX {vix['price']:.2f} ({vix['interpretation']})" if vix['price'] else "VIX unavailable"
        us10y_str = f"US10Y {us10y['price']:.2f}% ({us10y['interpretation']})" if us10y['price'] else "US10Y unavailable"
        
        return f"{dxy_str} | {vix_str} | {us10y_str}"
    
    def get_nasdaq(self) -> Dict[str, Any]:
        """
        Get NASDAQ Composite Index data
        
        Used for BTCUSD correlation (risk-on proxy)
        
        Returns:
            {
                'price': 15123.45,
                'trend': 'up',  # up/down/neutral
                'interpretation': 'NASDAQ rising - risk-on environment',
                'timestamp': '2025-10-09T20:00:00',
                'source': 'Yahoo Finance'
            }
        """
        # Check cache first
        if self._is_cache_valid('nasdaq'):
            self.logger.info("Using cached NASDAQ data")
            return self.cache['nasdaq']['data']
        
        try:
            import yfinance as yf
            
            # Fetch NASDAQ data
            nasdaq = yf.Ticker(self.nasdaq_symbol)
            hist = nasdaq.history(period="5d", interval="1h")
            
            if len(hist) < 20:
                raise Exception("Insufficient NASDAQ data")
            
            # Get current price and calculate trend
            closes = hist['Close'].tail(20).values
            current_price = float(closes[-1])
            prev_price = float(closes[-2])
            sma_20 = float(closes.mean())
            
            # Determine trend
            price_above_sma = current_price > sma_20
            price_rising = current_price > prev_price
            
            if price_above_sma and price_rising:
                trend = "up"
                interpretation = "NASDAQ rising - risk-on environment (bullish for BTCUSD)"
            elif not price_above_sma and not price_rising:
                trend = "down"
                interpretation = "NASDAQ falling - risk-off environment (bearish for BTCUSD)"
            else:
                trend = "neutral"
                interpretation = "NASDAQ consolidating - mixed for BTCUSD"
            
            result = {
                'price': round(current_price, 2),
                'trend': trend,
                'interpretation': interpretation,
                'timestamp': datetime.now().isoformat(),
                'source': 'Yahoo Finance (^IXIC)'
            }
            
            # Cache result
            self.cache['nasdaq'] = {
                'data': result,
                'timestamp': datetime.now().isoformat()
            }
            self._save_cache()
            
            self.logger.info(f"NASDAQ: {current_price:.2f} ({trend})")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to fetch NASDAQ: {e}")
            return {
                'price': None,
                'trend': 'unknown',
                'interpretation': f"Error fetching NASDAQ: {str(e)}",
                'timestamp': datetime.now().isoformat(),
                'source': 'Yahoo Finance (error)'
            }
    
    def get_nasdaq_correlation(self, symbol: str, window_days: int = 30) -> Dict[str, Any]:
        """
        Calculate 30-day rolling correlation between BTCUSD and NASDAQ
        
        BTCUSD typically has ~0.70 correlation with NASDAQ during risk-on periods
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSD' or 'BTCUSDc')
            window_days: Correlation window in days (default: 30)
        
        Returns:
            {
                'correlation': 0.72,  # Pearson correlation coefficient
                'strength': 'strong',  # strong/moderate/weak
                'interpretation': 'BTCUSD strongly correlated with NASDAQ',
                'timestamp': '2025-10-09T20:00:00'
            }
        """
        cache_key = f"nasdaq_corr_{symbol}"
        
        # Check cache first (cache for 1 hour)
        if self._is_cache_valid(cache_key):
            self.logger.debug(f"Using cached NASDAQ correlation for {symbol}")
            return self.cache[cache_key]['data']
        
        try:
            import yfinance as yf
            import pandas as pd
            import numpy as np
            
            # Get NASDAQ data
            nasdaq = yf.Ticker(self.nasdaq_symbol)
            nasdaq_hist = nasdaq.history(period=f"{window_days + 10}d", interval="1d")
            
            # Get crypto data (normalize symbol)
            crypto_symbol = symbol.upper().replace('C', '') if symbol.endswith('c') else symbol.upper()
            
            # Map to Binance symbol
            binance_symbol_map = {
                'BTCUSD': 'BTC-USD',
                'XAUUSD': 'XAU-USD',
                'ETHUSD': 'ETH-USD'
            }
            
            binance_symbol = binance_symbol_map.get(crypto_symbol, f"{crypto_symbol.replace('USD', '')}-USD")
            
            crypto = yf.Ticker(binance_symbol)
            crypto_hist = crypto.history(period=f"{window_days + 10}d", interval="1d")
            
            if len(nasdaq_hist) < window_days or len(crypto_hist) < window_days:
                raise Exception(f"Insufficient data for correlation (need {window_days} days)")
            
            # Align dates and get recent window
            nasdaq_prices = nasdaq_hist['Close'].tail(window_days).pct_change().dropna()
            crypto_prices = crypto_hist['Close'].tail(window_days).pct_change().dropna()
            
            # Align by date
            common_dates = nasdaq_prices.index.intersection(crypto_prices.index)
            if len(common_dates) < window_days // 2:
                raise Exception("Insufficient overlapping dates for correlation")
            
            nasdaq_aligned = nasdaq_prices.loc[common_dates]
            crypto_aligned = crypto_prices.loc[common_dates]
            
            # Calculate correlation
            correlation = float(np.corrcoef(nasdaq_aligned, crypto_aligned)[0, 1])
            
            # Determine strength
            if abs(correlation) >= 0.6:
                strength = "strong"
            elif abs(correlation) >= 0.3:
                strength = "moderate"
            else:
                strength = "weak"
            
            # Interpretation
            if correlation > 0.6:
                interpretation = f"BTCUSD strongly correlated with NASDAQ (risk-on proxy) - correlation: {correlation:.2f}"
            elif correlation > 0.3:
                interpretation = f"BTCUSD moderately correlated with NASDAQ - correlation: {correlation:.2f}"
            elif correlation < -0.3:
                interpretation = f"BTCUSD inversely correlated with NASDAQ (unusual) - correlation: {correlation:.2f}"
            else:
                interpretation = f"BTCUSD weakly correlated with NASDAQ - correlation: {correlation:.2f}"
            
            result = {
                'correlation': round(correlation, 3),
                'strength': strength,
                'interpretation': interpretation,
                'window_days': window_days,
                'common_dates': len(common_dates),
                'timestamp': datetime.now().isoformat()
            }
            
            # Cache result
            self.cache[cache_key] = {
                'data': result,
                'timestamp': datetime.now().isoformat()
            }
            self._save_cache()
            
            self.logger.info(f"NASDAQ correlation for {symbol}: {correlation:.3f} ({strength})")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to calculate NASDAQ correlation for {symbol}: {e}")
            return {
                'correlation': None,
                'strength': 'unknown',
                'interpretation': f"Error calculating correlation: {str(e)}",
                'window_days': window_days,
                'timestamp': datetime.now().isoformat()
            }
    
    async def get_sp500(self) -> Dict[str, Any]:
        """
        Get SP500 (S&P 500 Index) data
        
        Returns:
            {
                'price': 4500.25,
                'trend': 'up',  # up/down/neutral
                'interpretation': 'Risk-on sentiment',
                'timestamp': '2025-10-09T20:00:00',
                'source': 'Yahoo Finance'
            }
        """
        # Check cache first
        if self._is_cache_valid('sp500'):
            self.logger.info("Using cached SP500 data")
            return self.cache['sp500']['data']
        
        try:
            import yfinance as yf
            
            # Fetch SP500 data (run in thread to avoid blocking)
            loop = asyncio.get_event_loop()
            sp500 = await loop.run_in_executor(None, lambda: yf.Ticker(self.sp500_symbol))
            hist = await loop.run_in_executor(None, lambda: sp500.history(period="5d", interval="1h"))
            
            if len(hist) < 20:
                raise Exception("Insufficient SP500 data")
            
            # Get current price and calculate trend
            closes = hist['Close'].tail(20).values
            current_price = float(closes[-1])
            prev_price = float(closes[-2])
            sma_20 = float(closes.mean())
            
            # Determine trend
            price_above_sma = current_price > sma_20
            price_rising = current_price > prev_price
            
            if price_above_sma and price_rising:
                trend = "up"
                interpretation = "Risk-on sentiment (bullish)"
            elif not price_above_sma and not price_rising:
                trend = "down"
                interpretation = "Risk-off sentiment (bearish)"
            else:
                trend = "neutral"
                interpretation = "Mixed/consolidating"
            
            result = {
                'price': round(current_price, 2),
                'trend': trend,
                'interpretation': interpretation,
                'timestamp': datetime.now().isoformat(),
                'source': 'Yahoo Finance (^GSPC)'
            }
            
            # Cache result
            self.cache['sp500'] = {
                'data': result,
                'timestamp': datetime.now().isoformat()
            }
            self._save_cache()
            
            self.logger.info(f"SP500: {current_price:.2f} ({trend})")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to fetch SP500: {e}")
            return {
                'price': None,
                'trend': 'unknown',
                'interpretation': f"Error fetching SP500: {str(e)}",
                'timestamp': datetime.now().isoformat(),
                'source': 'Yahoo Finance (error)'
            }
    
    async def get_dxy_bars(self, period: str = "5d", interval: str = "5m") -> Optional[Any]:
        """
        Get DXY historical bars for correlation calculation.
        
        Args:
            period: Period string (e.g., "5d" for 5 days)
            interval: Interval string (e.g., "5m" for 5 minutes)
        
        Returns:
            pandas.DataFrame with columns: ['time', 'open', 'high', 'low', 'close', 'volume']
            or None if failed
        """
        try:
            import yfinance as yf
            import pandas as pd
            
            # Fetch historical data (run in thread to avoid blocking)
            loop = asyncio.get_event_loop()
            dxy = await loop.run_in_executor(None, lambda: yf.Ticker(self.dxy_symbol))
            hist = await loop.run_in_executor(None, lambda: dxy.history(period=period, interval=interval))
            
            if hist is None or len(hist) == 0:
                self.logger.warning("No DXY historical data returned")
                return None
            
            # Convert to DataFrame with standardized columns
            # yfinance returns DataFrame with DatetimeIndex
            df = hist.copy() if isinstance(hist, pd.DataFrame) else pd.DataFrame(hist)
            
            # Reset index to convert DatetimeIndex to column
            df.reset_index(inplace=True)
            
            # Find the datetime column (could be 'Date', index name, or first column if index was unnamed)
            time_col_name = None
            for col in df.columns:
                col_lower = str(col).lower()
                # Check if column is datetime type or has datetime-like name
                if (pd.api.types.is_datetime64_any_dtype(df[col]) or 
                    col_lower in ['date', 'datetime', 'time', 'timestamp'] or
                    (isinstance(df[col].iloc[0] if len(df) > 0 else None, (pd.Timestamp, datetime)))):
                    time_col_name = col
                    break
            
            # If no datetime column found, check if first column after reset_index is datetime
            if time_col_name is None and len(df.columns) > 0:
                first_col = df.columns[0]
                if pd.api.types.is_datetime64_any_dtype(df[first_col]):
                    time_col_name = first_col
            
            # Rename time column if found
            if time_col_name and time_col_name != 'time':
                df.rename(columns={time_col_name: 'time'}, inplace=True)
            elif time_col_name is None:
                # Last resort: try to use the index if it was datetime
                if isinstance(hist.index, pd.DatetimeIndex):
                    df['time'] = hist.index.values
                else:
                    self.logger.error(f"DXY bars: No time column found. Columns: {df.columns.tolist()}")
                    return None
            
            # Rename OHLCV columns (handle case variations)
            rename_map = {}
            for col in df.columns:
                if col == 'time':
                    continue
                col_lower = str(col).lower()
                if col_lower == 'open' and col != 'open':
                    rename_map[col] = 'open'
                elif col_lower == 'high' and col != 'high':
                    rename_map[col] = 'high'
                elif col_lower == 'low' and col != 'low':
                    rename_map[col] = 'low'
                elif col_lower == 'close' and col != 'close':
                    rename_map[col] = 'close'
                elif col_lower == 'volume' and col != 'volume':
                    rename_map[col] = 'volume'
            
            if rename_map:
                df.rename(columns=rename_map, inplace=True)
            
            # Ensure time column is datetime
            if 'time' in df.columns:
                if not pd.api.types.is_datetime64_any_dtype(df['time']):
                    df['time'] = pd.to_datetime(df['time'])
            else:
                self.logger.error(f"DXY bars: 'time' column missing after processing. Columns: {df.columns.tolist()}")
                return None
            
            # Select only required columns and validate
            required_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                self.logger.error(f"DXY bars: Missing required columns: {missing_cols}. Available: {df.columns.tolist()}")
                return None
            
            df = df[required_cols]
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to fetch DXY bars: {e}", exc_info=True)
            return None
    
    async def get_sp500_bars(self, period: str = "5d", interval: str = "5m") -> Optional[Any]:
        """
        Get SP500 historical bars for correlation calculation.
        
        Args:
            period: Period string (e.g., "5d" for 5 days)
            interval: Interval string (e.g., "5m" for 5 minutes)
        
        Returns:
            pandas.DataFrame with columns: ['time', 'open', 'high', 'low', 'close', 'volume']
            or None if failed
        """
        try:
            import yfinance as yf
            import pandas as pd
            
            # Fetch historical data (run in thread to avoid blocking)
            loop = asyncio.get_event_loop()
            sp500 = await loop.run_in_executor(None, lambda: yf.Ticker(self.sp500_symbol))
            hist = await loop.run_in_executor(None, lambda: sp500.history(period=period, interval=interval))
            
            if hist is None or len(hist) == 0:
                self.logger.warning("No SP500 historical data returned")
                return None
            
            # Convert to DataFrame with standardized columns
            # yfinance returns DataFrame with DatetimeIndex
            df = hist.copy() if isinstance(hist, pd.DataFrame) else pd.DataFrame(hist)
            
            # Reset index to convert DatetimeIndex to column
            df.reset_index(inplace=True)
            
            # Find the datetime column (could be 'Date', index name, or first column if index was unnamed)
            time_col_name = None
            for col in df.columns:
                col_lower = str(col).lower()
                # Check if column is datetime type or has datetime-like name
                if (pd.api.types.is_datetime64_any_dtype(df[col]) or 
                    col_lower in ['date', 'datetime', 'time', 'timestamp'] or
                    (isinstance(df[col].iloc[0] if len(df) > 0 else None, (pd.Timestamp, datetime)))):
                    time_col_name = col
                    break
            
            # If no datetime column found, check if first column after reset_index is datetime
            if time_col_name is None and len(df.columns) > 0:
                first_col = df.columns[0]
                if pd.api.types.is_datetime64_any_dtype(df[first_col]):
                    time_col_name = first_col
            
            # Rename time column if found
            if time_col_name and time_col_name != 'time':
                df.rename(columns={time_col_name: 'time'}, inplace=True)
            elif time_col_name is None:
                # Last resort: try to use the index if it was datetime
                if isinstance(hist.index, pd.DatetimeIndex):
                    df['time'] = hist.index.values
                else:
                    self.logger.error(f"SP500 bars: No time column found. Columns: {df.columns.tolist()}")
                    return None
            
            # Rename OHLCV columns (handle case variations)
            rename_map = {}
            for col in df.columns:
                if col == 'time':
                    continue
                col_lower = str(col).lower()
                if col_lower == 'open' and col != 'open':
                    rename_map[col] = 'open'
                elif col_lower == 'high' and col != 'high':
                    rename_map[col] = 'high'
                elif col_lower == 'low' and col != 'low':
                    rename_map[col] = 'low'
                elif col_lower == 'close' and col != 'close':
                    rename_map[col] = 'close'
                elif col_lower == 'volume' and col != 'volume':
                    rename_map[col] = 'volume'
            
            if rename_map:
                df.rename(columns=rename_map, inplace=True)
            
            # Ensure time column is datetime
            if 'time' in df.columns:
                if not pd.api.types.is_datetime64_any_dtype(df['time']):
                    df['time'] = pd.to_datetime(df['time'])
            else:
                self.logger.error(f"SP500 bars: 'time' column missing after processing. Columns: {df.columns.tolist()}")
                return None
            
            # Select only required columns and validate
            required_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                self.logger.error(f"SP500 bars: Missing required columns: {missing_cols}. Available: {df.columns.tolist()}")
                return None
            
            df = df[required_cols]
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to fetch SP500 bars: {e}", exc_info=True)
            return None
    
    async def get_us10y_bars(self, period: str = "5d", interval: str = "5m") -> Optional[Any]:
        """
        Get US10Y historical bars for correlation calculation.
        
        Args:
            period: Period string (e.g., "5d" for 5 days)
            interval: Interval string (e.g., "5m" for 5 minutes)
        
        Returns:
            pandas.DataFrame with columns: ['time', 'open', 'high', 'low', 'close', 'volume']
            or None if failed
        """
        try:
            import yfinance as yf
            import pandas as pd
            
            # Fetch historical data (run in thread to avoid blocking)
            loop = asyncio.get_event_loop()
            us10y = await loop.run_in_executor(None, lambda: yf.Ticker(self.us10y_symbol))
            hist = await loop.run_in_executor(None, lambda: us10y.history(period=period, interval=interval))
            
            if hist is None or len(hist) == 0:
                self.logger.warning("No US10Y historical data returned")
                return None
            
            # Convert to DataFrame with standardized columns
            # yfinance returns DataFrame with DatetimeIndex
            df = hist.copy() if isinstance(hist, pd.DataFrame) else pd.DataFrame(hist)
            
            # Reset index to convert DatetimeIndex to column
            df.reset_index(inplace=True)
            
            # Find the datetime column (could be 'Date', index name, or first column if index was unnamed)
            time_col_name = None
            for col in df.columns:
                col_lower = str(col).lower()
                # Check if column is datetime type or has datetime-like name
                if (pd.api.types.is_datetime64_any_dtype(df[col]) or 
                    col_lower in ['date', 'datetime', 'time', 'timestamp'] or
                    (isinstance(df[col].iloc[0] if len(df) > 0 else None, (pd.Timestamp, datetime)))):
                    time_col_name = col
                    break
            
            # If no datetime column found, check if first column after reset_index is datetime
            if time_col_name is None and len(df.columns) > 0:
                first_col = df.columns[0]
                if pd.api.types.is_datetime64_any_dtype(df[first_col]):
                    time_col_name = first_col
            
            # Rename time column if found
            if time_col_name and time_col_name != 'time':
                df.rename(columns={time_col_name: 'time'}, inplace=True)
            elif time_col_name is None:
                # Last resort: try to use the index if it was datetime
                if isinstance(hist.index, pd.DatetimeIndex):
                    df['time'] = hist.index.values
                else:
                    self.logger.error(f"US10Y bars: No time column found. Columns: {df.columns.tolist()}")
                    return None
            
            # Rename OHLCV columns (handle case variations)
            rename_map = {}
            for col in df.columns:
                if col == 'time':
                    continue
                col_lower = str(col).lower()
                if col_lower == 'open' and col != 'open':
                    rename_map[col] = 'open'
                elif col_lower == 'high' and col != 'high':
                    rename_map[col] = 'high'
                elif col_lower == 'low' and col != 'low':
                    rename_map[col] = 'low'
                elif col_lower == 'close' and col != 'close':
                    rename_map[col] = 'close'
                elif col_lower == 'volume' and col != 'volume':
                    rename_map[col] = 'volume'
            
            if rename_map:
                df.rename(columns=rename_map, inplace=True)
            
            # Ensure time column is datetime
            if 'time' in df.columns:
                if not pd.api.types.is_datetime64_any_dtype(df['time']):
                    df['time'] = pd.to_datetime(df['time'])
            else:
                self.logger.error(f"US10Y bars: 'time' column missing after processing. Columns: {df.columns.tolist()}")
                return None
            
            # Select only required columns and validate
            required_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                self.logger.error(f"US10Y bars: Missing required columns: {missing_cols}. Available: {df.columns.tolist()}")
                return None
            
            df = df[required_cols]
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to fetch US10Y bars: {e}", exc_info=True)
            return None


# Factory function
def create_market_indices_service() -> MarketIndicesService:
    """Create MarketIndicesService instance (no API key needed)"""
    return MarketIndicesService()

