"""
Volatility Forecasting & Regime Awareness
Provides advanced volatility analysis including momentum, expansion probability, and session curves

Phase 3.3: Session Volatility Curves - Volatility patterns by trading session (Asia/London/NY)
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, time, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class VolatilityForecaster:
    """
    Advanced volatility forecasting and regime awareness
    
    Features:
    - Volatility momentum (ATR of ATR)
    - Expansion probability (BB width percentile)
    - Range probability
    - Volatility signal (EXPANDING/CONTRACTING/STABLE)
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("VolatilityForecaster initialized")
        # Session definitions (UTC times)
        self.SESSION_TIMES = {
            "ASIA": {"start": 22, "end": 8},      # 22:00 UTC (prev day) to 08:00 UTC
            "LONDON": {"start": 8, "end": 16},   # 08:00 UTC to 16:00 UTC
            "NY": {"start": 13, "end": 21}       # 13:00 UTC to 21:00 UTC
        }
    
    def calculate_atr_momentum(self, df: pd.DataFrame, atr_period: int = 14, momentum_period: int = 20) -> Dict[str, Any]:
        """
        Calculate volatility momentum (ATR of ATR)
        
        This measures the rate of change in volatility itself.
        Rising ATR of ATR = volatility is accelerating (EXPANDING)
        Falling ATR of ATR = volatility is decelerating (CONTRACTING)
        
        Args:
            df: DataFrame with OHLC columns
            atr_period: Period for calculating ATR
            momentum_period: Period for calculating ATR of ATR
        
        Returns:
            {
                'momentum': 0.15,  # ATR of ATR value
                'direction': 'EXPANDING',  # EXPANDING/CONTRACTING/STABLE
                'strength': 'moderate',  # strong/moderate/weak
                'interpretation': 'Volatility momentum rising - volatility accelerating'
            }
        """
        try:
            if len(df) < atr_period + momentum_period:
                return {
                    'momentum': 0.0,
                    'direction': 'STABLE',
                    'strength': 'unknown',
                    'interpretation': 'Insufficient data for ATR momentum calculation'
                }
            
            # Calculate ATR over the full period
            atr_values = []
            for i in range(atr_period, len(df)):
                window = df.iloc[i - atr_period:i + 1]
                atr = self._calculate_atr(window, atr_period)
                if atr and atr > 0:
                    atr_values.append(atr)
            
            if len(atr_values) < momentum_period:
                return {
                    'momentum': 0.0,
                    'direction': 'STABLE',
                    'strength': 'unknown',
                    'interpretation': 'Insufficient ATR values for momentum calculation'
                }
            
            # Calculate ATR of the ATR array (volatility momentum)
            atr_series = pd.Series(atr_values)
            atr_of_atr = self._calculate_atr(atr_series.to_frame(), period=min(momentum_period, len(atr_values)))
            
            if not atr_of_atr or atr_of_atr <= 0:
                return {
                    'momentum': 0.0,
                    'direction': 'STABLE',
                    'strength': 'unknown',
                    'interpretation': 'Cannot calculate ATR of ATR'
                }
            
            # Compare current ATR to recent average to determine direction
            recent_atr = atr_values[-1] if atr_values else 0
            avg_atr = np.mean(atr_values[-momentum_period:]) if len(atr_values) >= momentum_period else recent_atr
            
            if avg_atr == 0:
                direction = 'STABLE'
                strength = 'unknown'
            elif recent_atr > avg_atr * 1.05:
                direction = 'EXPANDING'
                strength = 'strong' if recent_atr > avg_atr * 1.15 else 'moderate'
            elif recent_atr < avg_atr * 0.95:
                direction = 'CONTRACTING'
                strength = 'strong' if recent_atr < avg_atr * 0.85 else 'moderate'
            else:
                direction = 'STABLE'
                strength = 'weak'
            
            # Normalize momentum by average ATR for scale independence
            normalized_momentum = atr_of_atr / avg_atr if avg_atr > 0 else 0.0
            
            interpretation = f"Volatility {direction.lower()} ({strength}) - ATR momentum: {normalized_momentum:.3f}"
            
            return {
                'momentum': round(normalized_momentum, 3),
                'raw_atr_of_atr': round(atr_of_atr, 6),
                'direction': direction,
                'strength': strength,
                'interpretation': interpretation
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating ATR momentum: {e}", exc_info=True)
            return {
                'momentum': 0.0,
                'direction': 'STABLE',
                'strength': 'unknown',
                'interpretation': f'Error: {str(e)}'
            }
    
    def calculate_bb_width_percentile(self, df: pd.DataFrame, bb_period: int = 20, lookback_days: int = 60) -> Dict[str, Any]:
        """
        Calculate Bollinger Band width percentile ranking
        
        BB width percentile indicates expansion probability:
        - High percentile (>80%) = expansion likely
        - Low percentile (<20%) = contraction (squeeze)
        
        Args:
            df: DataFrame with OHLC columns
            bb_period: Period for Bollinger Bands
            lookback_days: Historical window for percentile calculation
        
        Returns:
            {
                'percentile': 85,  # 0-100
                'expansion_probability': 'high',  # high/moderate/low
                'interpretation': 'BB width at 85th percentile - expansion likely'
            }
        """
        try:
            if len(df) < bb_period + 10:
                return {
                    'percentile': 50,
                    'expansion_probability': 'unknown',
                    'interpretation': 'Insufficient data for BB width percentile'
                }
            
            # Calculate BB width for all available periods
            bb_widths = []
            for i in range(bb_period, len(df)):
                window = df.iloc[i - bb_period:i + 1]
                bb = self._calculate_bollinger_bands(window['close'], period=bb_period, std_dev=2)
                if bb:
                    width = bb['upper'] - bb['lower']
                    bb_widths.append(width / bb['middle'] if bb['middle'] > 0 else 0)  # Normalize by price
            
            if len(bb_widths) < 10:
                return {
                    'percentile': 50,
                    'expansion_probability': 'unknown',
                    'interpretation': 'Insufficient BB width history'
                }
            
            # Get recent window for percentile calculation
            lookback_periods = min(lookback_days, len(bb_widths))
            historical_widths = bb_widths[-lookback_periods:]
            current_width = bb_widths[-1] if bb_widths else 0
            
            # Calculate percentile
            percentile = int((sum(1 for w in historical_widths if w <= current_width) / len(historical_widths)) * 100)
            
            # Determine expansion probability
            if percentile >= 80:
                expansion_prob = 'high'
                interpretation = f"BB width at {percentile}th percentile (expansion) → Expect breakout within 2-4 hours"
            elif percentile >= 60:
                expansion_prob = 'moderate'
                interpretation = f"BB width at {percentile}th percentile → Moderate expansion probability"
            elif percentile <= 20:
                expansion_prob = 'low'
                interpretation = f"BB width at {percentile}th percentile (contraction) → Squeeze detected, breakout pending"
            else:
                expansion_prob = 'normal'
                interpretation = f"BB width at {percentile}th percentile → Normal volatility range"
            
            return {
                'percentile': percentile,
                'expansion_probability': expansion_prob,
                'current_width': round(current_width, 6),
                'avg_width': round(np.mean(historical_widths), 6),
                'interpretation': interpretation
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating BB width percentile: {e}", exc_info=True)
            return {
                'percentile': 50,
                'expansion_probability': 'unknown',
                'interpretation': f'Error: {str(e)}'
            }
    
    def calculate_range_probability(self, df: pd.DataFrame, ema_period: int = 20, adx_period: int = 14) -> Dict[str, Any]:
        """
        Calculate range probability (0-100%)
        
        Range probability = flat EMA slope + low ADX + low BB width
        
        Args:
            df: DataFrame with OHLC columns
            ema_period: Period for EMA (trend detection)
            adx_period: Period for ADX (trend strength)
        
        Returns:
            {
                'probability': 75,  # 0-100%
                'interpretation': 'High range probability - avoid breakout trades'
            }
        """
        try:
            if len(df) < max(ema_period, adx_period) + 10:
                return {
                    'probability': 0,
                    'interpretation': 'Insufficient data for range probability'
                }
            
            # Calculate components
            ema_slope = self._calculate_ema_slope(df, ema_period)
            adx = self._calculate_adx(df, adx_period)
            bb_width = self._get_bb_width(df)
            
            # Normalize components to 0-1 scores
            # Flat EMA slope = high range probability
            ema_score = 1.0 - min(1.0, abs(ema_slope) * 10)  # Slope < 0.1 = flat
            
            # Low ADX = high range probability
            adx_score = 1.0 - min(1.0, max(0, (adx - 15) / 15))  # ADX < 15 = range
            
            # Low BB width = high range probability
            avg_bb_width = 0.02  # Typical normalized width threshold
            bb_score = 1.0 - min(1.0, bb_width / avg_bb_width) if bb_width > 0 else 1.0
            
            # Weighted average
            range_probability = int((ema_score * 0.4 + adx_score * 0.4 + bb_score * 0.2) * 100)
            range_probability = max(0, min(100, range_probability))
            
            if range_probability >= 70:
                interpretation = f"High range probability ({range_probability}%) - avoid breakout trades, prefer mean reversion"
            elif range_probability >= 40:
                interpretation = f"Moderate range probability ({range_probability}%) - mixed conditions"
            else:
                interpretation = f"Low range probability ({range_probability}%) - trend likely, breakout trades preferred"
            
            return {
                'probability': range_probability,
                'components': {
                    'ema_slope': round(ema_slope, 4),
                    'adx': round(adx, 2),
                    'bb_width': round(bb_width, 6)
                },
                'interpretation': interpretation
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating range probability: {e}", exc_info=True)
            return {
                'probability': 0,
                'interpretation': f'Error: {str(e)}'
            }
    
    def get_volatility_signal(self, df: pd.DataFrame) -> str:
        """
        Get volatility signal: EXPANDING, CONTRACTING, or STABLE
        
        Combines ATR momentum and BB width percentile
        
        Args:
            df: DataFrame with OHLC columns
        
        Returns:
            "EXPANDING" | "CONTRACTING" | "STABLE"
        """
        try:
            momentum = self.calculate_atr_momentum(df)
            bb_percentile = self.calculate_bb_width_percentile(df)
            
            momentum_dir = momentum.get('direction', 'STABLE')
            bb_prob = bb_percentile.get('expansion_probability', 'normal')
            
            # Combine signals
            if momentum_dir == 'EXPANDING' or bb_prob == 'high':
                return 'EXPANDING'
            elif momentum_dir == 'CONTRACTING' or bb_prob == 'low':
                return 'CONTRACTING'
            else:
                return 'STABLE'
                
        except Exception as e:
            self.logger.error(f"Error getting volatility signal: {e}")
            return 'STABLE'
    
    def _calculate_atr(self, df: pd.DataFrame, period: int) -> Optional[float]:
        """Calculate Average True Range"""
        try:
            if len(df) < period:
                return None
            
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            tr_list = []
            for i in range(1, len(df)):
                tr1 = high[i] - low[i]
                tr2 = abs(high[i] - close[i-1])
                tr3 = abs(low[i] - close[i-1])
                tr_list.append(max(tr1, tr2, tr3))
            
            if not tr_list:
                return None
            
            atr = np.mean(tr_list[-period:]) if len(tr_list) >= period else np.mean(tr_list)
            return float(atr)
            
        except Exception:
            return None
    
    def _calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: int = 2) -> Optional[Dict[str, float]]:
        """Calculate Bollinger Bands"""
        try:
            if len(prices) < period:
                return None
            
            sma = prices.rolling(period).mean().iloc[-1]
            std = prices.rolling(period).std().iloc[-1]
            
            return {
                'upper': float(sma + std_dev * std),
                'middle': float(sma),
                'lower': float(sma - std_dev * std)
            }
        except Exception:
            return None
    
    def _get_bb_width(self, df: pd.DataFrame, period: int = 20) -> float:
        """Get normalized BB width"""
        try:
            bb = self._calculate_bollinger_bands(df['close'], period)
            if bb and bb['middle'] > 0:
                return (bb['upper'] - bb['lower']) / bb['middle']
            return 0.0
        except Exception:
            return 0.0
    
    def _calculate_ema_slope(self, df: pd.DataFrame, period: int) -> float:
        """Calculate EMA slope (normalized)"""
        try:
            if len(df) < period + 5:
                return 0.0
            
            ema = df['close'].ewm(span=period, adjust=False).mean()
            slope = (ema.iloc[-1] - ema.iloc[-5]) / ema.iloc[-1] if ema.iloc[-1] > 0 else 0.0
            return float(slope)
        except Exception:
            return 0.0
    
    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ADX (Average Directional Index)"""
        try:
            if len(df) < period * 2:
                return 25.0  # Default moderate trend
            
            # Simplified ADX calculation
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            # Calculate +DI and -DI
            plus_dm = []
            minus_dm = []
            
            for i in range(1, len(df)):
                move_up = high[i] - high[i-1]
                move_down = low[i-1] - low[i]
                
                if move_up > move_down and move_up > 0:
                    plus_dm.append(move_up)
                else:
                    plus_dm.append(0)
                
                if move_down > move_up and move_down > 0:
                    minus_dm.append(move_down)
                else:
                    minus_dm.append(0)
            
            # Calculate True Range
            tr_list = []
            for i in range(1, len(df)):
                tr = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
                tr_list.append(tr)
            
            # Simplified ADX (using smoothed averages)
            if len(plus_dm) >= period and len(tr_list) >= period:
                plus_di = np.mean(plus_dm[-period:]) / np.mean(tr_list[-period:]) * 100 if np.mean(tr_list[-period:]) > 0 else 0
                minus_di = np.mean(minus_dm[-period:]) / np.mean(tr_list[-period:]) * 100 if np.mean(tr_list[-period:]) > 0 else 0
                
                dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
                adx = float(dx)  # Simplified - full ADX requires smoothing
                return min(100, max(0, adx))
            
            return 25.0  # Default
            
        except Exception:
            return 25.0  # Default moderate trend
    
    def _get_session_from_timestamp(self, dt: datetime) -> str:
        """
        Get trading session from timestamp (UTC).
        
        Returns: "ASIA", "LONDON", "NY", or "UNKNOWN"
        """
        try:
            # Handle timezone: pandas DatetimeIndex from MT5 is naive (assumed UTC)
            # If timezone-aware, convert to UTC then make naive
            if dt.tzinfo is not None:
                # Convert to UTC if timezone-aware
                import pytz
                if dt.tzinfo != pytz.UTC:
                    dt = dt.astimezone(pytz.UTC)
                dt = dt.replace(tzinfo=None)  # Make naive (assumed UTC)
            # If already naive, assume UTC (MT5 returns UTC timestamps)
            
            hour = dt.hour
            weekday = dt.weekday()  # 0=Monday, 6=Sunday
            
            # Weekend
            if weekday >= 5:
                return "UNKNOWN"
            
            # Check sessions (handle Asia wrap-around)
            if 8 <= hour < 16:
                return "LONDON"
            elif 13 <= hour < 21:
                # NY session (overlaps with London 13-16)
                return "NY"
            elif hour >= 22 or hour < 8:
                return "ASIA"
            else:
                return "UNKNOWN"
                
        except Exception:
            return "UNKNOWN"
    
    def calculate_session_volatility_curves(
        self,
        df: pd.DataFrame,
        lookback_days: int = 30,
        atr_period: int = 14
    ) -> Dict[str, Any]:
        """
        Phase 3.3: Calculate session volatility curves.
        
        Tracks historical ATR patterns by trading session (Asia/London/NY)
        and compares current session volatility to historical averages.
        
        Args:
            df: DataFrame with OHLC columns and datetime index
            lookback_days: Days of history to analyze (default: 30)
            atr_period: Period for ATR calculation (default: 14)
        
        Returns:
            {
                "current_session": "LONDON",
                "current_session_atr": 1.25,
                "session_curves": {
                    "ASIA": {
                        "avg_atr": 0.95,
                        "median_atr": 0.92,
                        "percentile_25": 0.85,
                        "percentile_75": 1.05,
                        "max_atr": 1.45,
                        "min_atr": 0.65,
                        "volatility_level": "low",  # low/moderate/high
                        "sample_count": 45
                    },
                    "LONDON": {...},
                    "NY": {...}
                },
                "current_vs_historical": {
                    "vs_avg": 1.32,  # Current is 32% above historical avg
                    "vs_median": 1.36,
                    "percentile": 82,  # Current ATR at 82nd percentile for this session
                    "interpretation": "Higher than normal volatility for LONDON session"
                }
            }
        """
        try:
            if len(df) < atr_period * 2:
                return {
                    "current_session": "UNKNOWN",
                    "current_session_atr": 0.0,
                    "session_curves": {},
                    "current_vs_historical": {}
                }
            
            # Ensure datetime index
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'time' in df.columns:
                    df = df.set_index('time')
                else:
                    logger.warning("Cannot calculate session curves: no datetime index")
                    return {
                        "current_session": "UNKNOWN",
                        "current_session_atr": 0.0,
                        "session_curves": {},
                        "current_vs_historical": {}
                    }
            
            # Group bars by session and calculate ATR for each session period
            session_atrs = defaultdict(list)
            
            # Calculate ATR for each bar
            for i in range(atr_period, len(df)):
                window = df.iloc[i - atr_period:i + 1]
                atr = self._calculate_atr(window, atr_period)
                
                if atr and atr > 0:
                    # Get session for this bar's timestamp
                    bar_time = df.index[i]
                    session = self._get_session_from_timestamp(bar_time)
                    
                    if session != "UNKNOWN":
                        # Filter to lookback period (handle timedelta for pandas DatetimeIndex)
                        current_time = df.index[-1]
                        time_diff = current_time - bar_time
                        # Convert to days (handles both timedelta and differences in DatetimeIndex)
                        days_ago = time_diff.total_seconds() / 86400.0 if hasattr(time_diff, 'total_seconds') else time_diff.days
                        if days_ago <= lookback_days:
                            session_atrs[session].append(atr)
            
            # Calculate statistics for each session
            session_curves = {}
            for session in ["ASIA", "LONDON", "NY"]:
                atrs = session_atrs.get(session, [])
                
                if len(atrs) >= 5:  # Minimum samples
                    atrs_array = np.array(atrs)
                    session_curves[session] = {
                        "avg_atr": float(np.mean(atrs_array)),
                        "median_atr": float(np.median(atrs_array)),
                        "percentile_25": float(np.percentile(atrs_array, 25)),
                        "percentile_75": float(np.percentile(atrs_array, 75)),
                        "max_atr": float(np.max(atrs_array)),
                        "min_atr": float(np.min(atrs_array)),
                        "sample_count": len(atrs)
                    }
                    
                    # Determine volatility level
                    avg = session_curves[session]["avg_atr"]
                    median = session_curves[session]["median_atr"]
                    p75 = session_curves[session]["percentile_75"]
                    p25 = session_curves[session]["percentile_25"]
                    
                    if avg >= p75:
                        vol_level = "high"
                    elif avg <= p25:
                        vol_level = "low"
                    else:
                        vol_level = "moderate"
                    
                    session_curves[session]["volatility_level"] = vol_level
                else:
                    session_curves[session] = {
                        "avg_atr": 0.0,
                        "median_atr": 0.0,
                        "percentile_25": 0.0,
                        "percentile_75": 0.0,
                        "max_atr": 0.0,
                        "min_atr": 0.0,
                        "sample_count": len(atrs),
                        "volatility_level": "unknown"
                    }
            
            # Get current session and current ATR
            current_time = df.index[-1]
            current_session = self._get_session_from_timestamp(current_time)
            
            # Calculate current ATR
            current_window = df.iloc[-atr_period:]
            current_atr = self._calculate_atr(current_window, atr_period)
            current_atr = current_atr if current_atr else 0.0
            
            # Compare current to historical
            current_vs_historical = {}
            if current_session != "UNKNOWN" and current_session in session_curves:
                curve = session_curves[current_session]
                avg_atr = curve.get("avg_atr", 0)
                median_atr = curve.get("median_atr", 0)
                
                if avg_atr > 0:
                    vs_avg = current_atr / avg_atr
                else:
                    vs_avg = 1.0
                
                if median_atr > 0:
                    vs_median = current_atr / median_atr
                else:
                    vs_median = 1.0
                
                # Calculate percentile
                all_session_atrs = session_atrs.get(current_session, [])
                if len(all_session_atrs) > 0:
                    percentile = int((sum(1 for a in all_session_atrs if a <= current_atr) / len(all_session_atrs)) * 100)
                else:
                    percentile = 50
                
                # Interpretation
                if vs_avg >= 1.2:
                    interpretation = f"Higher than normal volatility for {current_session} session ({vs_avg:.1f}x average) - expect wider moves"
                elif vs_avg <= 0.8:
                    interpretation = f"Lower than normal volatility for {current_session} session ({vs_avg:.1f}x average) - tighter ranges expected"
                else:
                    interpretation = f"Normal volatility for {current_session} session"
                
                current_vs_historical = {
                    "vs_avg": round(vs_avg, 2),
                    "vs_median": round(vs_median, 2),
                    "percentile": percentile,
                    "interpretation": interpretation
                }
            
            return {
                "current_session": current_session,
                "current_session_atr": round(current_atr, 6),
                "session_curves": session_curves,
                "current_vs_historical": current_vs_historical
            }
            
        except Exception as e:
            logger.error(f"Error calculating session volatility curves: {e}", exc_info=True)
            return {
                "current_session": "UNKNOWN",
                "current_session_atr": 0.0,
                "session_curves": {},
                "current_vs_historical": {}
            }


# Factory function
def create_volatility_forecaster() -> VolatilityForecaster:
    """Create VolatilityForecaster instance"""
    return VolatilityForecaster()


