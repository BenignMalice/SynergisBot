"""
Feature Indicators Module
Computes trend, momentum, volatility, and volume indicators
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class IndicatorFeatures:
    """
    IMPROVED: Computes normalized technical indicators for AI analysis.
    Focuses on trend, momentum, volatility, and volume indicators.
    """
    
    def compute(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Compute all indicator features for the given DataFrame."""
        try:
            features = {}
            
            # Trend indicators
            features.update(self._compute_trend_indicators(df))
            
            # Momentum indicators
            features.update(self._compute_momentum_indicators(df))
            
            # Volatility indicators
            features.update(self._compute_volatility_indicators(df))
            
            # Volume indicators
            features.update(self._compute_volume_indicators(df))
            
            return features
            
        except Exception as e:
            logger.error(f"Indicator computation failed for {symbol} {timeframe}: {e}")
            return {}
    
    def _compute_trend_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute trend indicators: EMA, Hull MA, SuperTrend."""
        try:
            features = {}
            
            # EMA calculations
            ema_20 = self._ema(df["close"], 20)
            ema_50 = self._ema(df["close"], 50)
            ema_200 = self._ema(df["close"], 200)
            
            features["ema_20"] = float(ema_20.iloc[-1]) if not ema_20.empty else 0.0
            features["ema_50"] = float(ema_50.iloc[-1]) if not ema_50.empty else 0.0
            features["ema_200"] = float(ema_200.iloc[-1]) if not ema_200.empty else 0.0
            
            # EMA slopes (normalized by price)
            current_price = df["close"].iloc[-1]
            features["ema_20_slope"] = self._calculate_slope(ema_20, current_price)
            features["ema_50_slope"] = self._calculate_slope(ema_50, current_price)
            features["ema_200_slope"] = self._calculate_slope(ema_200, current_price)
            
            # EMA alignment
            features["ema_alignment"] = (ema_20.iloc[-1] > ema_50.iloc[-1] > ema_200.iloc[-1]) if not ema_20.empty else False
            
            # Trend state
            features["trend_state"] = self._determine_trend_state(ema_20, ema_50, ema_200, current_price)
            
            # Hull Moving Average
            hull_ma = self._hull_moving_average(df["close"], 9)
            features["hull_ma"] = float(hull_ma.iloc[-1]) if not hull_ma.empty else 0.0
            features["hull_ma_slope"] = self._calculate_slope(hull_ma, current_price)
            
            # SuperTrend
            supertrend_data = self._supertrend(df, 10, 3.0)
            features["supertrend_value"] = supertrend_data["value"]
            features["supertrend_direction"] = supertrend_data["direction"]
            features["supertrend_distance"] = supertrend_data["distance"]
            
            return features
            
        except Exception as e:
            logger.error(f"Trend indicator computation failed: {e}")
            return {}
    
    def _compute_momentum_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute momentum indicators: RSI, MACD, ROC."""
        try:
            features = {}
            
            # RSI
            rsi_14 = self._rsi(df["close"], 14)
            features["rsi_14"] = float(rsi_14.iloc[-1]) if not rsi_14.empty else 50.0
            features["rsi_regime"] = self._classify_rsi_regime(features["rsi_14"])
            features["rsi_divergence"] = self._check_rsi_divergence(df["close"], rsi_14)
            
            # MACD
            macd_data = self._macd(df["close"], 12, 26, 9)
            features["macd_line"] = float(macd_data["macd"].iloc[-1]) if not macd_data["macd"].empty else 0.0
            features["macd_signal"] = float(macd_data["signal"].iloc[-1]) if not macd_data["signal"].empty else 0.0
            features["macd_histogram"] = float(macd_data["histogram"].iloc[-1]) if not macd_data["histogram"].empty else 0.0
            features["macd_hist_slope"] = self._calculate_histogram_slope(macd_data["histogram"])
            
            # Rate of Change
            roc_9 = self._roc(df["close"], 9)
            roc_14 = self._roc(df["close"], 14)
            features["roc_9"] = float(roc_9.iloc[-1]) if not roc_9.empty else 0.0
            features["roc_14"] = float(roc_14.iloc[-1]) if not roc_14.empty else 0.0
            features["roc_sign_changes"] = self._count_roc_sign_changes(roc_9, 5)
            
            return features
            
        except Exception as e:
            logger.error(f"Momentum indicator computation failed: {e}")
            return {}
    
    def _compute_volatility_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute volatility indicators: ATR, Bollinger Bands, Keltner Channels."""
        try:
            features = {}
            
            # ATR
            atr_14 = self._atr(df, 14)
            atr_100 = self._atr(df, 100)
            features["atr_14"] = float(atr_14.iloc[-1]) if not atr_14.empty else 0.0
            features["atr_14_pct"] = (features["atr_14"] / df["close"].iloc[-1] * 100) if df["close"].iloc[-1] > 0 else 0.0
            features["atr_ratio"] = (features["atr_14"] / float(atr_100.iloc[-1])) if not atr_100.empty and atr_100.iloc[-1] > 0 else 1.0
            
            # Bollinger Bands
            bb_data = self._bollinger_bands(df["close"], 20, 2)
            features["bb_upper"] = float(bb_data["upper"].iloc[-1]) if not bb_data["upper"].empty else 0.0
            features["bb_middle"] = float(bb_data["middle"].iloc[-1]) if not bb_data["middle"].empty else 0.0
            features["bb_lower"] = float(bb_data["lower"].iloc[-1]) if not bb_data["lower"].empty else 0.0
            features["bb_width"] = float(bb_data["width"].iloc[-1]) if not bb_data["width"].empty else 0.0
            features["bb_percent_b"] = float(bb_data["percent_b"].iloc[-1]) if not bb_data["percent_b"].empty else 0.5
            features["bb_squeeze"] = features["bb_width"] < (features["atr_14"] * 0.1)  # Simple squeeze detection
            
            # Keltner Channels
            kc_data = self._keltner_channels(df, 20, 2)
            features["kc_upper"] = float(kc_data["upper"].iloc[-1]) if not kc_data["upper"].empty else 0.0
            features["kc_middle"] = float(kc_data["middle"].iloc[-1]) if not kc_data["middle"].empty else 0.0
            features["kc_lower"] = float(kc_data["lower"].iloc[-1]) if not kc_data["lower"].empty else 0.0
            features["kc_distance"] = self._calculate_band_distance(df["close"].iloc[-1], features["kc_upper"], features["kc_lower"])
            
            # Donchian Channels
            donchian_data = self._donchian_channels(df, 20)
            features["donchian_upper"] = float(donchian_data["upper"].iloc[-1]) if not donchian_data["upper"].empty else 0.0
            features["donchian_lower"] = float(donchian_data["lower"].iloc[-1]) if not donchian_data["lower"].empty else 0.0
            features["donchian_breakout"] = self._check_donchian_breakout(df["close"], donchian_data)
            
            # Volatility regime
            features["vol_regime"] = self._classify_volatility_regime(features["atr_ratio"], features["bb_width"])
            
            return features
            
        except Exception as e:
            logger.error(f"Volatility indicator computation failed: {e}")
            return {}
    
    def _compute_volume_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute volume indicators: Volume Z-score, OBV, VWAP."""
        try:
            features = {}
            
            # Volume Z-score
            if "volume" in df.columns and df["volume"].sum() > 0:
                volume_20_mean = df["volume"].rolling(20).mean()
                volume_20_std = df["volume"].rolling(20).std()
                features["volume_zscore"] = float((df["volume"].iloc[-1] - volume_20_mean.iloc[-1]) / volume_20_std.iloc[-1]) if volume_20_std.iloc[-1] > 0 else 0.0
                features["volume_spike"] = abs(features["volume_zscore"]) > 2.0
            else:
                features["volume_zscore"] = 0.0
                features["volume_spike"] = False
            
            # OBV (On-Balance Volume)
            obv = self._obv(df)
            features["obv"] = float(obv.iloc[-1]) if not obv.empty else 0.0
            features["obv_direction"] = self._calculate_obv_direction(obv, 20)
            features["obv_divergence"] = self._check_obv_divergence(df["close"], obv)
            
            # VWAP
            vwap = self._vwap(df)
            features["vwap"] = float(vwap.iloc[-1]) if not vwap.empty else 0.0
            features["vwap_distance"] = self._calculate_vwap_distance(df["close"].iloc[-1], features["vwap"])
            
            # Anchored VWAP (from session open)
            anchored_vwap = self._anchored_vwap(df)
            features["anchored_vwap"] = float(anchored_vwap.iloc[-1]) if not anchored_vwap.empty else 0.0
            features["anchored_vwap_distance"] = self._calculate_vwap_distance(df["close"].iloc[-1], features["anchored_vwap"])
            
            return features
            
        except Exception as e:
            logger.error(f"Volume indicator computation failed: {e}")
            return {}
    
    # Technical indicator calculation methods
    
    def _ema(self, series: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return series.ewm(span=period).mean()
    
    def _rsi(self, series: pd.Series, period: int) -> pd.Series:
        """Calculate RSI."""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _macd(self, series: pd.Series, fast: int, slow: int, signal: int) -> Dict[str, pd.Series]:
        """Calculate MACD."""
        ema_fast = series.ewm(span=fast).mean()
        ema_slow = series.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        return {"macd": macd_line, "signal": signal_line, "histogram": histogram}
    
    def _atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Average True Range."""
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        return true_range.rolling(window=period).mean()
    
    def _bollinger_bands(self, series: pd.Series, period: int, std_dev: float) -> Dict[str, pd.Series]:
        """Calculate Bollinger Bands."""
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        width = (upper - lower) / middle
        percent_b = (series - lower) / (upper - lower)
        return {"upper": upper, "middle": middle, "lower": lower, "width": width, "percent_b": percent_b}
    
    def _keltner_channels(self, df: pd.DataFrame, period: int, multiplier: float) -> Dict[str, pd.Series]:
        """Calculate Keltner Channels."""
        middle = df["close"].rolling(window=period).mean()
        atr = self._atr(df, period)
        upper = middle + (atr * multiplier)
        lower = middle - (atr * multiplier)
        return {"upper": upper, "middle": middle, "lower": lower}
    
    def _donchian_channels(self, df: pd.DataFrame, period: int) -> Dict[str, pd.Series]:
        """Calculate Donchian Channels."""
        upper = df["high"].rolling(window=period).max()
        lower = df["low"].rolling(window=period).min()
        return {"upper": upper, "lower": lower}
    
    def _hull_moving_average(self, series: pd.Series, period: int) -> pd.Series:
        """Calculate Hull Moving Average."""
        wma_half = series.rolling(window=period//2).mean()
        wma_full = series.rolling(window=period).mean()
        hull_raw = 2 * wma_half - wma_full
        return hull_raw.rolling(window=int(np.sqrt(period))).mean()
    
    def _supertrend(self, df: pd.DataFrame, period: int, multiplier: float) -> Dict[str, Any]:
        """Calculate SuperTrend indicator."""
        try:
            atr = self._atr(df, period)
            hl2 = (df["high"] + df["low"]) / 2
            upper_band = hl2 + (multiplier * atr)
            lower_band = hl2 - (multiplier * atr)
            
            # Calculate SuperTrend
            supertrend = pd.Series(index=df.index, dtype=float)
            direction = pd.Series(index=df.index, dtype=int)
            
            for i in range(len(df)):
                if i == 0:
                    supertrend.iloc[i] = lower_band.iloc[i]
                    direction.iloc[i] = 1
                else:
                    if df["close"].iloc[i] <= supertrend.iloc[i-1]:
                        supertrend.iloc[i] = upper_band.iloc[i]
                        direction.iloc[i] = -1
                    else:
                        supertrend.iloc[i] = lower_band.iloc[i]
                        direction.iloc[i] = 1
            
            current_value = supertrend.iloc[-1] if not supertrend.empty else 0.0
            current_direction = direction.iloc[-1] if not direction.empty else 0
            current_price = df["close"].iloc[-1]
            distance = (current_price - current_value) / current_price if current_price > 0 else 0.0
            
            return {
                "value": current_value,
                "direction": current_direction,
                "distance": distance
            }
            
        except Exception:
            return {"value": 0.0, "direction": 0, "distance": 0.0}
    
    def _roc(self, series: pd.Series, period: int) -> pd.Series:
        """Calculate Rate of Change."""
        return ((series - series.shift(period)) / series.shift(period)) * 100
    
    def _obv(self, df: pd.DataFrame) -> pd.Series:
        """Calculate On-Balance Volume."""
        if "volume" not in df.columns:
            return pd.Series(index=df.index, data=0.0)
        
        obv = pd.Series(index=df.index, dtype=float)
        obv.iloc[0] = df["volume"].iloc[0]
        
        for i in range(1, len(df)):
            if df["close"].iloc[i] > df["close"].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + df["volume"].iloc[i]
            elif df["close"].iloc[i] < df["close"].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - df["volume"].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        
        return obv
    
    def _vwap(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Volume Weighted Average Price."""
        if "volume" not in df.columns or df["volume"].sum() == 0:
            return df["close"].rolling(window=20).mean()
        
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        vwap = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()
        return vwap
    
    def _anchored_vwap(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Anchored VWAP from session start."""
        # Simplified: use last 20 bars as "session"
        return self._vwap(df.tail(20))
    
    # Helper methods
    
    def _calculate_slope(self, series: pd.Series, current_price: float) -> float:
        """Calculate normalized slope of a series."""
        if len(series) < 2 or current_price == 0:
            return 0.0
        return float((series.iloc[-1] - series.iloc[-2]) / current_price)
    
    def _determine_trend_state(self, ema_20: pd.Series, ema_50: pd.Series, ema_200: pd.Series, current_price: float) -> str:
        """Determine overall trend state."""
        if ema_20.empty or ema_50.empty or ema_200.empty:
            return "mixed"
        
        ema_20_val = ema_20.iloc[-1]
        ema_50_val = ema_50.iloc[-1]
        ema_200_val = ema_200.iloc[-1]
        
        if current_price > ema_20_val > ema_50_val > ema_200_val:
            return "up"
        elif current_price < ema_20_val < ema_50_val < ema_200_val:
            return "down"
        else:
            return "mixed"
    
    def _classify_rsi_regime(self, rsi: float) -> str:
        """Classify RSI into regime buckets."""
        if rsi >= 70:
            return "overbought"
        elif rsi <= 30:
            return "oversold"
        elif 40 <= rsi <= 60:
            return "neutral"
        elif rsi > 60:
            return "bullish"
        else:
            return "bearish"
    
    def _check_rsi_divergence(self, price: pd.Series, rsi: pd.Series) -> bool:
        """Check for simple RSI divergence."""
        if len(price) < 10 or len(rsi) < 10:
            return False
        
        # Simple divergence check: price makes new high/low but RSI doesn't
        price_recent = price.tail(5)
        rsi_recent = rsi.tail(5)
        
        price_trend = price_recent.iloc[-1] - price_recent.iloc[0]
        rsi_trend = rsi_recent.iloc[-1] - rsi_recent.iloc[0]
        
        return (price_trend > 0 and rsi_trend < 0) or (price_trend < 0 and rsi_trend > 0)
    
    def _calculate_histogram_slope(self, histogram: pd.Series) -> float:
        """Calculate MACD histogram slope."""
        if len(histogram) < 3:
            return 0.0
        return float(histogram.iloc[-1] - histogram.iloc[-3]) / 2.0
    
    def _count_roc_sign_changes(self, roc: pd.Series, lookback: int) -> int:
        """Count ROC sign changes in recent periods."""
        if len(roc) < lookback:
            return 0
        
        recent_roc = roc.tail(lookback)
        sign_changes = 0
        for i in range(1, len(recent_roc)):
            if (recent_roc.iloc[i] > 0) != (recent_roc.iloc[i-1] > 0):
                sign_changes += 1
        return sign_changes
    
    def _classify_volatility_regime(self, atr_ratio: float, bb_width: float) -> str:
        """Classify volatility regime."""
        if atr_ratio > 1.2 or bb_width > 0.05:
            return "high"
        elif atr_ratio < 0.8 or bb_width < 0.02:
            return "low"
        else:
            return "normal"
    
    def _calculate_band_distance(self, price: float, upper: float, lower: float) -> float:
        """Calculate normalized distance to band."""
        if upper == lower:
            return 0.0
        return (price - lower) / (upper - lower)
    
    def _check_donchian_breakout(self, price: pd.Series, donchian: Dict[str, pd.Series]) -> bool:
        """Check for Donchian channel breakout."""
        if price.empty or donchian["upper"].empty or donchian["lower"].empty:
            return False
        
        current_price = price.iloc[-1]
        upper_band = donchian["upper"].iloc[-1]
        lower_band = donchian["lower"].iloc[-1]
        
        return current_price > upper_band or current_price < lower_band
    
    def _calculate_obv_direction(self, obv: pd.Series, period: int) -> str:
        """Calculate OBV direction over period."""
        if len(obv) < period:
            return "neutral"
        
        recent_obv = obv.tail(period)
        if recent_obv.iloc[-1] > recent_obv.iloc[0]:
            return "up"
        elif recent_obv.iloc[-1] < recent_obv.iloc[0]:
            return "down"
        else:
            return "neutral"
    
    def _check_obv_divergence(self, price: pd.Series, obv: pd.Series) -> bool:
        """Check for OBV divergence."""
        if len(price) < 10 or len(obv) < 10:
            return False
        
        price_recent = price.tail(5)
        obv_recent = obv.tail(5)
        
        price_trend = price_recent.iloc[-1] - price_recent.iloc[0]
        obv_trend = obv_recent.iloc[-1] - obv_recent.iloc[0]
        
        return (price_trend > 0 and obv_trend < 0) or (price_trend < 0 and obv_trend > 0)
    
    def _calculate_vwap_distance(self, price: float, vwap: float) -> float:
        """Calculate normalized distance to VWAP."""
        if vwap == 0:
            return 0.0
        return (price - vwap) / vwap
