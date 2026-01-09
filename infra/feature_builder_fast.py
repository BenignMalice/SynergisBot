"""
Fast Feature Builder - Speed Optimization
Computes only essential features for quick analysis
Skips expensive calculations (patterns, complex structure analysis)
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from infra.mt5_service import MT5Service
from infra.indicator_bridge import IndicatorBridge

logger = logging.getLogger(__name__)


class FastFeatureBuilder:
    """
    SPEED OPTIMIZATION: Lightweight feature computation.
    Computes only essential indicators, skips expensive analysis.
    Typical speedup: ~2s → ~0.5s (75% faster)
    
    Use for:
    - Quick scans across multiple symbols
    - Real-time updates
    - When full analysis isn't needed
    """
    
    # Essential indicators only (keep these)
    ESSENTIAL_INDICATORS = {
        'close', 'open', 'high', 'low',
        'ema_20', 'ema_50', 'ema_200',
        'atr_14', 'adx', 'rsi_14',
        'bb_upper', 'bb_middle', 'bb_lower', 'bb_width',
        'volume', 'regime'
    }
    
    def __init__(self, mt5svc: MT5Service, bridge: IndicatorBridge):
        self.mt5svc = mt5svc
        self.bridge = bridge
        
    def build(self, symbol: str, timeframes: List[str] = None) -> Dict[str, Any]:
        """
        Build FAST feature set for symbol.
        Only computes essential indicators, skips:
        - Pattern detection
        - Complex structure analysis (FVG, liquidity, etc.)
        - Microstructure features
        - Cross-timeframe correlations
        """
        if timeframes is None:
            timeframes = ["M5", "M15"]  # Only 2 timeframes for speed
            
        try:
            # Get multi-timeframe data
            multi = self.bridge.get_multi(symbol)
            if not multi:
                return self._empty_features()
                
            # Build fast features for each timeframe
            features = {}
            for tf in timeframes:
                if tf in multi:
                    features[tf] = self._build_fast_features(symbol, tf, multi[tf])
                else:
                    features[tf] = self._empty_features()
                    
            # Add minimal metadata
            features["symbol"] = symbol
            features["timestamp"] = datetime.now(timezone.utc).isoformat()
            features["fast_mode"] = True
            
            return features
            
        except Exception as e:
            logger.error(f"Fast feature building failed for {symbol}: {e}")
            return self._empty_features()
    
    def _build_fast_features(self, symbol: str, timeframe: str, data: Dict) -> Dict[str, Any]:
        """Build FAST features - essential indicators only."""
        try:
            if not data or len(data) < 20:  # Reduced minimum requirement
                return self._empty_features()
            
            features = {}
            
            # Extract essential indicators directly (no DataFrame overhead for simple extractions)
            for key in self.ESSENTIAL_INDICATORS:
                if key in data:
                    val = data[key]
                    # Normalize to simple types (no numpy/pandas objects)
                    if isinstance(val, (list, tuple)) and len(val) > 0:
                        features[key] = float(val[-1]) if isinstance(val[-1], (int, float, np.number)) else val[-1]
                    elif isinstance(val, (int, float, np.number)):
                        features[key] = float(val)
                    else:
                        features[key] = val
            
            # Calculate only critical derived features (fast calculations)
            if 'close' in features and 'bb_upper' in features and 'bb_lower' in features:
                close = features['close']
                bb_upper = features['bb_upper']
                bb_lower = features['bb_lower']
                bb_range = bb_upper - bb_lower if bb_upper > bb_lower else 1
                features['bb_position'] = (close - bb_lower) / bb_range if bb_range > 0 else 0.5
            
            # Fast EMA alignment check
            if 'ema_20' in features and 'ema_50' in features and 'ema_200' in features:
                ema20 = features['ema_20']
                ema50 = features['ema_50']
                ema200 = features['ema_200']
                features['ema_aligned_bull'] = ema20 > ema50 > ema200
                features['ema_aligned_bear'] = ema20 < ema50 < ema200
            
            # Fast price position vs EMAs
            if 'close' in features and 'ema_20' in features:
                close = features['close']
                ema20 = features['ema_20']
                features['price_above_ema20'] = close > ema20
                if ema20 > 0:
                    features['price_ema20_pct'] = (close - ema20) / ema20
            
            # Fast trend detection (ADX + EMA alignment)
            if 'adx' in features and 'ema_aligned_bull' in features:
                adx = features.get('adx', 0)
                features['trend_strength'] = 'strong' if adx > 25 else 'moderate' if adx > 20 else 'weak'
                if features.get('ema_aligned_bull'):
                    features['trend_direction'] = 'bullish'
                elif features.get('ema_aligned_bear'):
                    features['trend_direction'] = 'bearish'
                else:
                    features['trend_direction'] = 'ranging'
            
            # Add timeframe and mode metadata
            features['timeframe'] = timeframe
            features['fast_mode'] = True
            
            return features
            
        except Exception as e:
            logger.warning(f"Fast feature computation failed for {timeframe}: {e}")
            return self._empty_features()
    
    def _empty_features(self) -> Dict[str, Any]:
        """Return empty feature set."""
        return {
            "symbol": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fast_mode": True,
            "error": "No data available"
        }


def build_fast_features(symbol: str, mt5svc: MT5Service, bridge: IndicatorBridge) -> Dict[str, Any]:
    """
    Convenience function to build fast features.
    
    Usage:
        from infra.feature_builder_fast import build_fast_features
        features = build_fast_features(symbol, mt5svc, bridge)
    
    Returns:
        Dict with essential features only (75% faster than full build)
    """
    builder = FastFeatureBuilder(mt5svc, bridge)
    return builder.build(symbol)


# Speed comparison guide
SPEED_COMPARISON = """
Feature Builder Speed Comparison:

┌─────────────────────┬──────────────┬────────────────────────────┐
│ Builder Type        │ Time         │ Features Included          │
├─────────────────────┼──────────────┼────────────────────────────┤
│ FeatureBuilder      │ ~2.0s        │ ALL (200+ features)        │
│ (Full)              │              │ - Indicators               │
│                     │              │ - Patterns                 │
│                     │              │ - Structure (FVG, sweeps)  │
│                     │              │ - Microstructure           │
│                     │              │ - Cross-timeframe          │
├─────────────────────┼──────────────┼────────────────────────────┤
│ FastFeatureBuilder  │ ~0.5s        │ ESSENTIAL ONLY (~20)       │
│ (Optimized)         │              │ - Core indicators          │
│                     │              │ - Price action             │
│                     │              │ - Trend detection          │
│                     │              │ - BB position              │
└─────────────────────┴──────────────┴────────────────────────────┘

When to use FastFeatureBuilder:
✓ Signal scanning across multiple symbols
✓ Quick market overview
✓ Real-time position monitoring
✓ Testing/development iterations

When to use full FeatureBuilder:
✓ Detailed trade analysis
✓ Entry point optimization
✓ Complex strategy decisions
✓ Post-trade analysis
"""

