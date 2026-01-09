"""
Feature Builder - Phase 0
Centralized indicator computation and normalization for AI analysis
Provides clean, consistent, and compact features across all timeframes
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
import json

from infra.mt5_service import MT5Service
from infra.indicator_bridge import IndicatorBridge
from config import settings

logger = logging.getLogger(__name__)

class FeatureBuilder:
    """
    IMPROVED: Centralized feature computation and normalization system.
    Provides clean, consistent indicators across all timeframes for AI analysis.
    """
    
    def __init__(self, mt5svc: MT5Service, bridge: IndicatorBridge):
        self.mt5svc = mt5svc
        self.bridge = bridge
        self.cache = {}  # Simple caching for performance
        
    def build(self, symbol: str, timeframes: List[str] = None) -> Dict[str, Any]:
        """
        Build comprehensive feature set for symbol across timeframes.
        Returns normalized, AI-ready features.
        """
        if timeframes is None:
            timeframes = ["M5", "M15", "M30", "H1", "H4"]
            
        try:
            # Get multi-timeframe data
            multi = self.bridge.get_multi(symbol)
            if not multi:
                return self._empty_features()
                
            # Build features for each timeframe
            features = {}
            for tf in timeframes:
                if tf in multi:
                    features[tf] = self._build_timeframe_features(symbol, tf, multi[tf])
                else:
                    features[tf] = self._empty_timeframe_features()
                    
            # Add cross-timeframe analysis
            features["cross_tf"] = self._build_cross_timeframe_features(features)
            
            # Add symbol metadata
            features["symbol"] = symbol
            features["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            return features
            
        except Exception as e:
            logger.error(f"Feature building failed for {symbol}: {e}")
            return self._empty_features()
    
    def _build_timeframe_features(self, symbol: str, timeframe: str, data: Dict) -> Dict[str, Any]:
        """Build features for a single timeframe."""
        try:
            # Check data validity
            if not data:
                logger.debug(f"No data provided for {symbol} {timeframe}")
                return self._empty_timeframe_features()
                
            # Check if data has the minimum required length
            data_len = len(data.get("open", []))
            if data_len < 50:  # Need minimum data
                logger.debug(f"Insufficient data for {symbol} {timeframe}: {data_len} bars (need 50+)")
                return self._empty_timeframe_features()
                
            # Convert to DataFrame for easier processing
            df = self._data_to_dataframe(data)
            if df is None or df.empty:
                logger.warning(f"DataFrame conversion failed or empty for {symbol} {timeframe}")
                return self._empty_timeframe_features()
                
            features = {}
            
            # Import submodules
            from infra.feature_indicators import IndicatorFeatures
            from infra.feature_patterns import PatternFeatures
            from infra.feature_structure import StructureFeatures
            from infra.feature_microstructure import MicrostructureFeatures
            from infra.feature_session_news import SessionNewsFeatures
            
            # Build feature categories
            indicator_features = IndicatorFeatures()
            pattern_features = PatternFeatures()
            structure_features = StructureFeatures()
            microstructure_features = MicrostructureFeatures()
            session_features = SessionNewsFeatures()
            
            # Compute all feature categories
            features.update(indicator_features.compute(df, symbol, timeframe))
            features.update(pattern_features.compute(df, symbol, timeframe))
            features.update(structure_features.compute(df, symbol, timeframe))
            features.update(microstructure_features.compute(df, symbol, timeframe))
            features.update(session_features.compute(df, symbol, timeframe))
            
            # Add timeframe metadata
            features["timeframe"] = timeframe
            features["bars_count"] = len(df)
            features["last_update"] = df.index[-1].isoformat() if not df.empty else None
            
            return features
            
        except Exception as e:
            logger.error(f"Timeframe feature building failed for {symbol} {timeframe}: {e}")
            return self._empty_timeframe_features()
    
    def _build_cross_timeframe_features(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Build cross-timeframe analysis and agreement features."""
        try:
            cross_tf = {}
            
            # Trend agreement analysis
            trend_agreement = self._analyze_trend_agreement(features)
            cross_tf.update(trend_agreement)
            
            # Volatility regime analysis
            vol_regime = self._analyze_volatility_regime(features)
            cross_tf.update(vol_regime)
            
            # Momentum confluence
            momentum_confluence = self._analyze_momentum_confluence(features)
            cross_tf.update(momentum_confluence)
            
            # Structure alignment
            structure_alignment = self._analyze_structure_alignment(features)
            cross_tf.update(structure_alignment)
            
            return cross_tf
            
        except Exception as e:
            logger.error(f"Cross-timeframe analysis failed: {e}")
            return {}
    
    def _analyze_trend_agreement(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze trend agreement across timeframes."""
        try:
            timeframes = ["M5", "M15", "M30", "H1"]
            trend_states = []
            
            for tf in timeframes:
                if tf in features and "trend_state" in features[tf]:
                    trend_states.append(features[tf]["trend_state"])
                    
            if not trend_states:
                return {"trend_agreement": 0.0, "trend_consensus": "mixed"}
                
            # Count trend states
            up_count = sum(1 for state in trend_states if state == "up")
            down_count = sum(1 for state in trend_states if state == "down")
            total = len(trend_states)
            
            agreement_ratio = max(up_count, down_count) / total if total > 0 else 0.0
            
            if up_count > down_count:
                consensus = "up"
            elif down_count > up_count:
                consensus = "down"
            else:
                consensus = "mixed"
                
            return {
                "trend_agreement": agreement_ratio,
                "trend_consensus": consensus,
                "trend_up_count": up_count,
                "trend_down_count": down_count,
                "trend_total_tf": total
            }
            
        except Exception:
            return {"trend_agreement": 0.0, "trend_consensus": "mixed"}
    
    def _analyze_volatility_regime(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze volatility regime across timeframes."""
        try:
            timeframes = ["M5", "M15", "M30", "H1"]
            vol_regimes = []
            atr_values = []
            
            for tf in timeframes:
                if tf in features:
                    if "vol_regime" in features[tf]:
                        vol_regimes.append(features[tf]["vol_regime"])
                    if "atr_14" in features[tf]:
                        atr_values.append(features[tf]["atr_14"])
                        
            if not vol_regimes:
                return {"vol_regime_consensus": "normal", "vol_regime_agreement": 0.0}
                
            # Count volatility regimes
            low_count = sum(1 for regime in vol_regimes if regime == "low")
            normal_count = sum(1 for regime in vol_regimes if regime == "normal")
            high_count = sum(1 for regime in vol_regimes if regime == "high")
            total = len(vol_regimes)
            
            # Determine consensus
            if high_count > max(low_count, normal_count):
                consensus = "high"
            elif low_count > max(normal_count, high_count):
                consensus = "low"
            else:
                consensus = "normal"
                
            agreement_ratio = max(low_count, normal_count, high_count) / total if total > 0 else 0.0
            
            # ATR analysis
            avg_atr = np.mean(atr_values) if atr_values else 0.0
            atr_std = np.std(atr_values) if len(atr_values) > 1 else 0.0
            
            return {
                "vol_regime_consensus": consensus,
                "vol_regime_agreement": agreement_ratio,
                "vol_low_count": low_count,
                "vol_normal_count": normal_count,
                "vol_high_count": high_count,
                "atr_avg": avg_atr,
                "atr_std": atr_std
            }
            
        except Exception:
            return {"vol_regime_consensus": "normal", "vol_regime_agreement": 0.0}
    
    def _analyze_momentum_confluence(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze momentum confluence across timeframes."""
        try:
            timeframes = ["M5", "M15", "M30", "H1"]
            rsi_values = []
            macd_hist_values = []
            
            for tf in timeframes:
                if tf in features:
                    if "rsi_14" in features[tf]:
                        rsi_values.append(features[tf]["rsi_14"])
                    if "macd_histogram" in features[tf]:
                        macd_hist_values.append(features[tf]["macd_histogram"])
                        
            # RSI confluence
            rsi_bullish = sum(1 for rsi in rsi_values if rsi > 50)
            rsi_bearish = sum(1 for rsi in rsi_values if rsi < 50)
            rsi_confluence = max(rsi_bullish, rsi_bearish) / len(rsi_values) if rsi_values else 0.0
            
            # MACD confluence
            macd_bullish = sum(1 for hist in macd_hist_values if hist > 0)
            macd_bearish = sum(1 for hist in macd_hist_values if hist < 0)
            macd_confluence = max(macd_bullish, macd_bearish) / len(macd_hist_values) if macd_hist_values else 0.0
            
            return {
                "rsi_confluence": rsi_confluence,
                "rsi_bullish_count": rsi_bullish,
                "rsi_bearish_count": rsi_bearish,
                "macd_confluence": macd_confluence,
                "macd_bullish_count": macd_bullish,
                "macd_bearish_count": macd_bearish,
                "momentum_consensus": "bullish" if rsi_bullish > rsi_bearish and macd_bullish > macd_bearish else "bearish" if rsi_bearish > rsi_bullish and macd_bearish > macd_bullish else "mixed"
            }
            
        except Exception:
            return {"rsi_confluence": 0.0, "macd_confluence": 0.0, "momentum_consensus": "mixed"}
    
    def _analyze_structure_alignment(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze structure alignment across timeframes."""
        try:
            timeframes = ["M5", "M15", "M30", "H1"]
            support_levels = []
            resistance_levels = []
            
            for tf in timeframes:
                if tf in features:
                    if "support_levels" in features[tf]:
                        support_levels.extend(features[tf]["support_levels"])
                    if "resistance_levels" in features[tf]:
                        resistance_levels.extend(features[tf]["resistance_levels"])
                        
            # Analyze level clustering
            support_clusters = self._find_level_clusters(support_levels)
            resistance_clusters = self._find_level_clusters(resistance_levels)
            
            return {
                "support_clusters": len(support_clusters),
                "resistance_clusters": len(resistance_clusters),
                "structure_density": len(support_levels) + len(resistance_levels),
                "level_alignment": "strong" if len(support_clusters) > 0 and len(resistance_clusters) > 0 else "weak"
            }
            
        except Exception:
            return {"support_clusters": 0, "resistance_clusters": 0, "structure_density": 0, "level_alignment": "weak"}
    
    def _find_level_clusters(self, levels: List[float], tolerance: float = 0.001) -> List[List[float]]:
        """Find clusters of similar price levels."""
        if not levels:
            return []
            
        levels = sorted(levels)
        clusters = []
        current_cluster = [levels[0]]
        
        for i in range(1, len(levels)):
            if abs(levels[i] - levels[i-1]) / levels[i-1] <= tolerance:
                current_cluster.append(levels[i])
            else:
                if len(current_cluster) > 1:
                    clusters.append(current_cluster)
                current_cluster = [levels[i]]
                
        if len(current_cluster) > 1:
            clusters.append(current_cluster)
            
        return clusters
    
    def _data_to_dataframe(self, data: Dict) -> Optional[pd.DataFrame]:
        """Convert indicator bridge data to DataFrame."""
        try:
            # Extract OHLCV data
            ohlcv_data = []
            for i in range(len(data.get("open", []))):
                ohlcv_data.append({
                    "open": data.get("open", [])[i],
                    "high": data.get("high", [])[i],
                    "low": data.get("low", [])[i],
                    "close": data.get("close", [])[i],
                    "volume": data.get("volume", [])[i] if "volume" in data else 0,
                    "time": data.get("time", [])[i] if "time" in data else i
                })
                
            if not ohlcv_data:
                return None
                
            df = pd.DataFrame(ohlcv_data)
            
            # Convert time to datetime if available
            if "time" in df.columns:
                try:
                    df["time"] = pd.to_datetime(df["time"], unit="s")
                    df.set_index("time", inplace=True)
                except:
                    df.set_index(pd.RangeIndex(len(df)), inplace=True)
            else:
                df.set_index(pd.RangeIndex(len(df)), inplace=True)
                
            return df
            
        except Exception as e:
            logger.error(f"DataFrame conversion failed: {e}")
            return None
    
    def _empty_features(self) -> Dict[str, Any]:
        """Return empty feature structure."""
        return {
            "symbol": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "M5": self._empty_timeframe_features(),
            "M15": self._empty_timeframe_features(),
            "M30": self._empty_timeframe_features(),
            "H1": self._empty_timeframe_features(),
            "H4": self._empty_timeframe_features(),
            "cross_tf": {}
        }
    
    def _empty_timeframe_features(self) -> Dict[str, Any]:
        """Return empty timeframe feature structure."""
        return {
            "timeframe": "",
            "bars_count": 0,
            "last_update": None,
            # Trend indicators
            "ema_20": 0.0, "ema_50": 0.0, "ema_200": 0.0,
            "ema_20_slope": 0.0, "ema_50_slope": 0.0, "ema_200_slope": 0.0,
            "ema_alignment": False, "trend_state": "mixed",
            # Momentum indicators
            "rsi_14": 50.0, "rsi_regime": "neutral",
            "macd_line": 0.0, "macd_signal": 0.0, "macd_histogram": 0.0, "macd_hist_slope": 0.0,
            "roc_9": 0.0, "roc_14": 0.0,
            # Volatility indicators
            "atr_14": 0.0, "atr_14_pct": 0.0, "atr_ratio": 1.0,
            "bb_width": 0.0, "bb_percent_b": 0.5, "bb_squeeze": False,
            "kc_distance": 0.0, "donchian_breakout": False,
            # Volume indicators
            "volume_zscore": 0.0, "volume_spike": False,
            "vwap": 0.0, "vwap_distance": 0.0,
            # Structure
            "swing_highs": [], "swing_lows": [], "support_levels": [], "resistance_levels": [],
            "range_high": 0.0, "range_low": 0.0, "range_width": 0.0,
            # Patterns
            "pattern_flags": {},
            "candlestick_flags": {},
            "wick_metrics": {},
            # Microstructure
            "spread_points": 0.0, "spread_atr_pct": 0.0,
            "slippage_proxy": 0.0,
            # Session
            "session": "unknown", "session_minutes": 0,
            "news_minutes": None, "news_blackout": False
        }


def build_features(symbol: str, mt5svc: MT5Service, bridge: IndicatorBridge, 
                  timeframes: List[str] = None) -> Dict[str, Any]:
    """
    Convenience function to build features for a symbol.
    """
    try:
        builder = FeatureBuilder(mt5svc, bridge)
        return builder.build(symbol, timeframes)
    except Exception as e:
        logger.error(f"Feature building failed for {symbol}: {e}")
        return FeatureBuilder(mt5svc, bridge)._empty_features()
