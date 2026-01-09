"""
Fixed Indicator Bridge - Direct MT5 calls instead of file-based system
"""
import logging
from typing import Dict, Any, Optional
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class IndicatorBridgeFixed:
    """Fixed indicator bridge that uses direct MT5 calls"""
    
    def __init__(self, common_files_dir=None):
        # We don't need the common_files_dir for direct MT5 calls
        self.mt5_connected = False
        self._ensure_mt5_connection()
    
    def _ensure_mt5_connection(self):
        """Ensure MT5 is connected"""
        if not self.mt5_connected:
            if not mt5.initialize():
                logger.error("Failed to initialize MT5")
                return False
            self.mt5_connected = True
        return True
    
    def get_multi(self, symbol: str) -> Dict[str, Dict[str, Any]]:
        """
        Get multi-timeframe data directly from MT5
        Returns data for M5, M15, M30, H1, H4 timeframes
        """
        try:
            if not self._ensure_mt5_connection():
                return {}
            
            # Ensure symbol is available
            if not mt5.symbol_select(symbol, True):
                logger.warning(f"Symbol {symbol} not available in MT5")
                return {}
            
            result = {}
            timeframes = {
                "M5": mt5.TIMEFRAME_M5,
                "M15": mt5.TIMEFRAME_M15,
                "M30": mt5.TIMEFRAME_M30,
                "H1": mt5.TIMEFRAME_H1,
                "H4": mt5.TIMEFRAME_H4
            }
            
            for tf_name, tf_enum in timeframes.items():
                try:
                    tf_data = self._get_timeframe_data(symbol, tf_enum, tf_name)
                    if tf_data:
                        result[tf_name] = tf_data
                except Exception as e:
                    logger.error(f"Error getting {tf_name} data for {symbol}: {e}")
                    continue
            
            return result
            
        except Exception as e:
            logger.error(f"Error in get_multi for {symbol}: {e}", exc_info=True)
            return {}
    
    def _get_timeframe_data(self, symbol: str, timeframe: int, tf_name: str) -> Optional[Dict[str, Any]]:
        """Get data for a specific timeframe"""
        try:
            # Get OHLCV data
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 500)
            if rates is None or len(rates) == 0:
                logger.warning(f"No rates data for {symbol} {tf_name}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df = df.set_index('time')
            
            # Calculate indicators
            indicators = self._calculate_indicators(df)
            
            # Get current price
            tick = mt5.symbol_info_tick(symbol)
            current_price = (tick.bid + tick.ask) / 2 if tick else df['close'].iloc[-1]
            
            # Prepare result
            result = {
                'times': df.index.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                'opens': df['open'].tolist(),
                'highs': df['high'].tolist(),
                'lows': df['low'].tolist(),
                'closes': df['close'].tolist(),
                'volumes': df['tick_volume'].tolist(),
                'current_close': float(current_price),
                'current_high': float(df['high'].iloc[-1]),
                'current_low': float(df['low'].iloc[-1]),
                'current_open': float(df['open'].iloc[-1])
            }
            
            # Add indicators
            result.update(indicators)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting {tf_name} data: {e}", exc_info=True)
            return None
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate technical indicators"""
        try:
            indicators = {}
            
            # Basic price data
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df['tick_volume']
            
            # Moving averages
            indicators['ema20'] = float(close.ewm(span=20).mean().iloc[-1])
            indicators['ema50'] = float(close.ewm(span=50).mean().iloc[-1])
            indicators['ema200'] = float(close.ewm(span=200).mean().iloc[-1])
            
            # RSI
            indicators['rsi'] = self._calculate_rsi(close)
            
            # ADX
            indicators['adx'] = self._calculate_adx(high, low, close)
            
            # ATR
            indicators['atr14'] = self._calculate_atr(high, low, close, 14)
            
            # MACD
            macd_line, macd_signal, macd_hist = self._calculate_macd(close)
            indicators['macd'] = float(macd_line.iloc[-1])
            indicators['macd_signal'] = float(macd_signal.iloc[-1])
            indicators['macd_histogram'] = float(macd_hist.iloc[-1])
            
            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(close)
            indicators['bb_upper'] = float(bb_upper.iloc[-1])
            indicators['bb_middle'] = float(bb_middle.iloc[-1])
            indicators['bb_lower'] = float(bb_lower.iloc[-1])
            
            # Stochastic
            stoch_k, stoch_d = self._calculate_stochastic(high, low, close)
            indicators['stoch_k'] = float(stoch_k.iloc[-1])
            indicators['stoch_d'] = float(stoch_d.iloc[-1])
            
            # Volume indicators
            indicators['volume_sma'] = float(volume.rolling(20).mean().iloc[-1])
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}", exc_info=True)
            return {}
    
    def _calculate_rsi(self, close: pd.Series, period: int = 14) -> float:
        """Calculate RSI"""
        try:
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return float(rsi.iloc[-1])
        except:
            return 50.0
    
    def _calculate_adx(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """Calculate ADX"""
        try:
            # True Range
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # Directional Movement
            dm_plus = high.diff()
            dm_minus = -low.diff()
            dm_plus = dm_plus.where((dm_plus > dm_minus) & (dm_plus > 0), 0)
            dm_minus = dm_minus.where((dm_minus > dm_plus) & (dm_minus > 0), 0)
            
            # Smoothed values
            tr_smooth = tr.rolling(window=period).mean()
            dm_plus_smooth = dm_plus.rolling(window=period).mean()
            dm_minus_smooth = dm_minus.rolling(window=period).mean()
            
            # DI values
            di_plus = 100 * (dm_plus_smooth / tr_smooth)
            di_minus = 100 * (dm_minus_smooth / tr_smooth)
            
            # ADX
            dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus)
            adx = dx.rolling(window=period).mean()
            
            return float(adx.iloc[-1])
        except:
            return 20.0
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """Calculate ATR"""
        try:
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()
            return float(atr.iloc[-1])
        except:
            return 0.0
    
    def _calculate_macd(self, close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        """Calculate MACD"""
        try:
            ema_fast = close.ewm(span=fast).mean()
            ema_slow = close.ewm(span=slow).mean()
            macd_line = ema_fast - ema_slow
            macd_signal = macd_line.ewm(span=signal).mean()
            macd_histogram = macd_line - macd_signal
            return macd_line, macd_signal, macd_histogram
        except:
            return pd.Series([0]), pd.Series([0]), pd.Series([0])
    
    def _calculate_bollinger_bands(self, close: pd.Series, period: int = 20, std_dev: float = 2.0):
        """Calculate Bollinger Bands"""
        try:
            sma = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()
            upper = sma + (std * std_dev)
            lower = sma - (std * std_dev)
            return upper, sma, lower
        except:
            return pd.Series([0]), pd.Series([0]), pd.Series([0])
    
    def _calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3):
        """Calculate Stochastic Oscillator"""
        try:
            lowest_low = low.rolling(window=k_period).min()
            highest_high = high.rolling(window=k_period).max()
            k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
            d_percent = k_percent.rolling(window=d_period).mean()
            return k_percent, d_percent
        except:
            return pd.Series([50]), pd.Series([50])
