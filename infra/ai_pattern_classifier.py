"""
AI Pattern Classifier (Phase 2.1)

Weighted confluence pattern classification for order flow scalping.
Combines multiple order flow signals into a single probability score.
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class AIPatternClassifier:
    """
    Weighted confluence pattern classifier for order flow signals.
    
    Combines multiple order flow signals (absorption, divergence, etc.)
    into a single probability score (0-100%) to determine trade quality.
    """
    
    # Default pattern weights (configurable via config file)
    DEFAULT_WEIGHTS = {
        'absorption': 0.30,          # Absorption zone detection (highest weight)
        'delta_divergence': 0.25,    # Delta divergence (price vs delta trend)
        'liquidity_sweep': 0.20,      # Liquidity sweep detection
        'cvd_divergence': 0.15,       # CVD divergence (price vs CVD trend)
        'vwap_deviation': 0.10        # VWAP deviation (mean reversion signal)
    }
    
    def __init__(self, config: Dict = None):
        """
        Initialize AI pattern classifier.
        
        Args:
            config: Optional config dict with:
                - 'pattern_weights': Dict of signal_name -> weight (0.0-1.0)
                - 'pattern_threshold': Minimum probability threshold (0.0-1.0, default 0.75)
        """
        self.config = config or {}
        self.weights = self.config.get('pattern_weights', self.DEFAULT_WEIGHTS.copy())
        self.threshold = self.config.get('pattern_threshold', 0.75)  # 75% minimum
        
        # Normalize weights to sum to 1.0
        total_weight = sum(self.weights.values())
        if total_weight > 0:
            self.weights = {k: v / total_weight for k, v in self.weights.items()}
        
        logger.debug(f"AIPatternClassifier initialized (threshold: {self.threshold*100:.0f}%)")
    
    def classify_pattern(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify pattern and calculate probability.
        
        Phase 2.1: Combines multiple order flow signals into probability score.
        
        Args:
            signals: Dict with signal names and values:
                - Boolean: True/False (signal present/absent)
                - Float: 0.0-1.0 (normalized signal strength)
                - Dict: {'strength': 0.0-1.0, 'type': 'bullish'/'bearish', ...}
        
        Returns:
            Dict with:
                - 'probability': float (0-100%) - Overall pattern probability
                - 'pattern_type': str - Dominant pattern type
                - 'signal_scores': Dict[str, float] - Individual signal scores
                - 'total_score': float - Raw score before normalization
                - 'meets_threshold': bool - Whether probability >= threshold
                - 'threshold': float - Threshold value (0-100%)
        """
        signal_scores = {}
        total_score = 0.0
        
        # Check each signal
        for signal_name, weight in self.weights.items():
            signal_value = signals.get(signal_name, False)
            
            # Calculate score based on signal type
            score = self._calculate_signal_score(signal_value, weight)
            
            signal_scores[signal_name] = score
            total_score += score
        
        # Calculate probability (0-100%)
        # Since weights sum to 1.0, total_score is already normalized
        probability = min(total_score * 100, 100.0)
        
        # Classify pattern type
        pattern_type = self._classify_pattern_type(signals, signal_scores)
        
        return {
            "probability": probability,
            "pattern_type": pattern_type,
            "signal_scores": signal_scores,
            "total_score": total_score,
            "meets_threshold": probability >= (self.threshold * 100),
            "threshold": self.threshold * 100
        }
    
    def _calculate_signal_score(self, signal_value: Any, weight: float) -> float:
        """
        Calculate score for a single signal.
        
        Args:
            signal_value: Signal value (bool, float, dict, etc.)
            weight: Signal weight (0.0-1.0)
        
        Returns:
            Score (0.0-weight) based on signal value
        """
        if isinstance(signal_value, bool):
            # Boolean signal: full weight if True
            return weight if signal_value else 0.0
        
        elif isinstance(signal_value, (int, float)):
            # Numeric signal: normalize to 0-1, then apply weight
            normalized = min(max(float(signal_value), 0.0), 1.0)
            return normalized * weight
        
        elif isinstance(signal_value, dict):
            # Complex signal: extract strength/confidence
            strength = signal_value.get('strength', 0.0)
            if isinstance(strength, (int, float)):
                strength = min(max(float(strength), 0.0), 1.0)
                return strength * weight
            # If strength is bool, treat as boolean signal
            elif isinstance(strength, bool):
                return weight if strength else 0.0
        
        # Unknown type: no score
        return 0.0
    
    def _classify_pattern_type(self, signals: Dict, scores: Dict[str, float]) -> str:
        """
        Classify the dominant pattern type.
        
        Args:
            signals: Original signals dict
            scores: Calculated signal scores
        
        Returns:
            Pattern type name (e.g., 'absorption', 'delta_divergence', etc.)
        """
        if not scores:
            return "unknown"
        
        # Find highest scoring signal
        max_signal = max(scores.items(), key=lambda x: x[1])
        if max_signal[1] > 0:
            return max_signal[0]
        
        return "unknown"
    
    def get_pattern_confidence(self, signals: Dict[str, Any]) -> float:
        """
        Get pattern confidence (0-100%) - alias for probability.
        
        Args:
            signals: Dict with signal names and values
        
        Returns:
            Confidence percentage (0-100)
        """
        result = self.classify_pattern(signals)
        return result['probability']
    
    def should_execute(self, signals: Dict[str, Any]) -> bool:
        """
        Determine if pattern meets threshold for execution.
        
        Args:
            signals: Dict with signal names and values
        
        Returns:
            True if pattern probability >= threshold, False otherwise
        """
        result = self.classify_pattern(signals)
        return result['meets_threshold']
    
    def get_signal_breakdown(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get detailed breakdown of signal scores.
        
        Args:
            signals: Dict with signal names and values
        
        Returns:
            Dict with detailed breakdown including:
                - Individual signal scores
                - Signal contributions (percentage)
                - Missing signals
        """
        result = self.classify_pattern(signals)
        signal_scores = result['signal_scores']
        total_score = result['total_score']
        
        # Calculate contributions
        contributions = {}
        for signal_name, score in signal_scores.items():
            if total_score > 0:
                contributions[signal_name] = (score / total_score) * 100
            else:
                contributions[signal_name] = 0.0
        
        # Find missing signals (weight > 0 but score = 0)
        missing = [
            signal_name 
            for signal_name, weight in self.weights.items()
            if weight > 0 and signal_scores.get(signal_name, 0) == 0
        ]
        
        return {
            "signal_scores": signal_scores,
            "contributions": contributions,
            "missing_signals": missing,
            "total_score": total_score,
            "probability": result['probability']
        }
