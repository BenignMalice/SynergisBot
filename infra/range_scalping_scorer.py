"""
Range Scalping Strategy Scorer
Evaluates and ranks all range scalping strategies by confluence.

Implements:
- Scoring system (0-100) for each strategy
- Dynamic strategy weighting based on ADX
- Conflict filtering (removes opposing signals)
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from infra.range_scalping_strategies import (
    BaseRangeScalpingStrategy,
    EntrySignal,
    VWAPMeanReversionStrategy,
    BollingerBandFadeStrategy,
    PDHPDLRejectionStrategy,
    RSIBounceStrategy,
    LiquiditySweepReversalStrategy
)
from infra.range_boundary_detector import RangeStructure

logger = logging.getLogger(__name__)


@dataclass
class StrategyScore:
    """Scored strategy entry signal"""
    entry_signal: EntrySignal
    total_score: int  # 0-100
    entry_conditions_score: int  # 0-40
    mtf_alignment_score: int  # 0-20
    order_flow_score: int  # 0-20
    session_timing_score: int  # 0-20
    weighted_score: float  # After dynamic weighting
    adx_context: str  # "low", "normal", "high", "trending"


class RangeScalpingScorer:
    """
    Evaluates all strategies simultaneously and ranks by confluence.
    """
    
    def __init__(self, config: Dict, rr_config: Dict):
        self.config = config
        self.rr_config = rr_config
        
        # Initialize all strategies
        self.strategies = [
            VWAPMeanReversionStrategy(config, rr_config),
            BollingerBandFadeStrategy(config, rr_config),
            PDHPDLRejectionStrategy(config, rr_config),
            RSIBounceStrategy(config, rr_config),
            LiquiditySweepReversalStrategy(config, rr_config)
        ]
        
        # Dynamic weighting config
        self.dynamic_config = config.get("dynamic_strategy_weighting", {})
        self.adx_low_threshold = self.dynamic_config.get("adx_low_threshold", 15)
        self.adx_high_threshold = self.dynamic_config.get("adx_high_threshold", 25)
        self.strategy_weights = self.dynamic_config.get("strategy_weights", {})
    
    def score_all_strategies(
        self,
        symbol: str,
        range_data: RangeStructure,
        market_data: Dict,
        session_info: Dict,
        adx_h1: float
    ) -> List[StrategyScore]:
        """
        Score each strategy (0-100):
        - Entry conditions met (0-40 points)
        - Multi-timeframe alignment (0-20 points)
        - Order flow confirmation (0-20 points)
        - Session timing (0-20 points)
        
        Dynamic Strategy Weighting (based on ADX):
        - ADX < 15: Weight VWAP Reversion (35%) and BB Fade (30%) higher
        - ADX > 25: Disable range scalps, suggest BOS/trend logic instead
        - Normal ADX: Standard weighting
        
        Filter conflicts (VWAP long vs PDH short = skip)
        Return top 1-2 strategies
        """
        scored_strategies = []
        
        # Get all entry signals from strategies
        for strategy in self.strategies:
            try:
                entry_signal = strategy.check_entry_conditions(
                    symbol=symbol,
                    range_data=range_data,
                    current_price=market_data.get("current_price", 0),
                    indicators=market_data.get("indicators", {}),
                    market_data=market_data
                )
                
                if not entry_signal:
                    continue  # No entry signal from this strategy
                
                # Score this strategy
                score = self._score_strategy(
                    entry_signal=entry_signal,
                    range_data=range_data,
                    market_data=market_data,
                    session_info=session_info
                )
                
                scored_strategies.append(score)
                
            except Exception as e:
                logger.debug(f"Error scoring {strategy.strategy_name}: {e}")
                continue
        
        # Apply dynamic weighting based on ADX
        weighted_scores = self.apply_dynamic_strategy_weights(
            scored_strategies,
            adx_h1,
            self.config
        )
        
        # Filter conflicts
        filtered_scores = self.check_strategy_conflicts(weighted_scores)
        
        # Sort by weighted score descending
        filtered_scores.sort(key=lambda s: s.weighted_score, reverse=True)
        
        # Return top 1-2 strategies
        return filtered_scores[:2]
    
    def _score_strategy(
        self,
        entry_signal: EntrySignal,
        range_data: RangeStructure,
        market_data: Dict,
        session_info: Dict
    ) -> StrategyScore:
        """
        Score a single strategy entry signal.
        
        Scoring breakdown:
        - Entry conditions: 0-40 points (from strategy confidence)
        - MTF alignment: 0-20 points
        - Order flow: 0-20 points
        - Session timing: 0-20 points
        """
        # Entry conditions score (from strategy confidence, normalized to 0-40)
        entry_conditions_score = min(40, int(entry_signal.confidence * 0.4))
        
        # Multi-timeframe alignment score (0-20)
        mtf_alignment_score = self._calculate_mtf_alignment_score(
            entry_signal.direction,
            market_data
        )
        
        # Order flow confirmation score (0-20)
        order_flow_score = self._calculate_order_flow_score(
            entry_signal.direction,
            market_data
        )
        
        # Session timing score (0-20)
        session_timing_score = self._calculate_session_timing_score(
            entry_signal.strategy_name,
            session_info
        )
        
        # Total score
        total_score = (
            entry_conditions_score +
            mtf_alignment_score +
            order_flow_score +
            session_timing_score
        )
        
        # Determine ADX context for weighting
        adx_h1 = market_data.get("adx_h1", 20)
        if adx_h1 < self.adx_low_threshold:
            adx_context = "low"
        elif adx_h1 > self.adx_high_threshold:
            adx_context = "trending"
        else:
            adx_context = "normal"
        
        return StrategyScore(
            entry_signal=entry_signal,
            total_score=total_score,
            entry_conditions_score=entry_conditions_score,
            mtf_alignment_score=mtf_alignment_score,
            order_flow_score=order_flow_score,
            session_timing_score=session_timing_score,
            weighted_score=float(total_score),  # Will be updated by dynamic weighting
            adx_context=adx_context
        )
    
    def _calculate_mtf_alignment_score(
        self,
        direction: str,
        market_data: Dict
    ) -> int:
        """
        Calculate multi-timeframe alignment score (0-20).
        
        Checks alignment across M5, M15, H1 timeframes.
        """
        mtf_scores = market_data.get("mtf_alignment", {})
        
        # Get alignment for each timeframe
        m5_aligned = mtf_scores.get("m5", {}).get("direction") == direction
        m15_aligned = mtf_scores.get("m15", {}).get("direction") == direction
        h1_aligned = mtf_scores.get("h1", {}).get("direction") == direction
        
        # Score based on alignment count
        aligned_count = sum([m5_aligned, m15_aligned, h1_aligned])
        
        if aligned_count == 3:
            return 20  # Perfect alignment
        elif aligned_count == 2:
            return 12  # Good alignment
        elif aligned_count == 1:
            return 6   # Partial alignment
        else:
            return 0   # No alignment
    
    def _calculate_order_flow_score(
        self,
        direction: str,
        market_data: Dict
    ) -> int:
        """
        Calculate order flow confirmation score (0-20).
        """
        order_flow = market_data.get("order_flow", {})
        
        # Check order flow signal
        of_signal = order_flow.get("signal", "NEUTRAL")
        of_confidence = order_flow.get("confidence", 0)
        
        # Check tape pressure
        tape_pressure = order_flow.get("pressure_side", "NEUTRAL")
        
        # Score based on alignment
        score = 0
        
        if direction == "BUY":
            if of_signal in ["BULLISH", "STRONG_BUY"]:
                score += 12  # Strong order flow confirmation
            elif of_signal == "NEUTRAL":
                score += 6   # Neutral (no conflict)
            
            if tape_pressure in ["BULLISH", "BUY"]:
                score += 8   # Tape pressure bonus
        else:  # SELL
            if of_signal in ["BEARISH", "STRONG_SELL"]:
                score += 12
            elif of_signal == "NEUTRAL":
                score += 6
            
            if tape_pressure in ["BEARISH", "SELL"]:
                score += 8
        
        return min(20, score)
    
    def _calculate_session_timing_score(
        self,
        strategy_name: str,
        session_info: Dict
    ) -> int:
        """
        Calculate session timing score (0-20).
        
        Different strategies work better in different sessions.
        """
        session_name = session_info.get("name", "").lower()
        
        # Session-specific strategy preferences
        session_preferences = {
            "asian": {
                "vwap_reversion": 20,
                "bb_fade": 18,
                "pdh_pdl_rejection": 16,
                "rsi_bounce": 12,
                "liquidity_sweep": 10
            },
            "london": {
                "vwap_reversion": 15,
                "bb_fade": 12,
                "pdh_pdl_rejection": 20,
                "rsi_bounce": 10,
                "liquidity_sweep": 18
            },
            "ny": {
                "vwap_reversion": 18,
                "bb_fade": 15,
                "pdh_pdl_rejection": 15,
                "rsi_bounce": 20,
                "liquidity_sweep": 16
            },
            "late_ny": {
                "vwap_reversion": 16,
                "bb_fade": 14,
                "pdh_pdl_rejection": 10,
                "rsi_bounce": 18,
                "liquidity_sweep": 8
            }
        }
        
        # Get score for current session
        if session_name in session_preferences:
            return session_preferences[session_name].get(strategy_name, 10)
        
        # Default score for unknown sessions
        return 10
    
    def apply_dynamic_strategy_weights(
        self,
        strategies: List[StrategyScore],
        adx_h1: float,
        config: Dict
    ) -> List[StrategyScore]:
        """
        Apply dynamic strategy weighting based on ADX level.
        
        If ADX < 15: Boost VWAP Reversion and BB Fade strategies
        If ADX > 25: Filter out all range scalping strategies (market trending)
        """
        if not self.dynamic_config.get("enabled", True):
            # No weighting, return as-is
            for score in strategies:
                score.weighted_score = float(score.total_score)
            return strategies
        
        # Check ADX level
        if adx_h1 > self.adx_high_threshold:
            # Market trending - filter out all range scalps
            logger.debug(f"ADX {adx_h1:.1f} > {self.adx_high_threshold} - market trending, disabling range scalps")
            return []  # Return empty list (no range scalps in trending markets)
        
        # Apply weights based on ADX
        if adx_h1 < self.adx_low_threshold:
            # Low ADX - boost mean reversion strategies
            weight_context = "low_adx"
        else:
            # Normal ADX
            weight_context = "normal"
        
        # Apply weights to each strategy
        for score in strategies:
            strategy_name = score.entry_signal.strategy_name
            
            # Get weight multiplier for this strategy
            weight_config = self.strategy_weights.get(strategy_name, {})
            weight_multiplier = weight_config.get(weight_context, 1.0)
            
            # Apply weight
            score.weighted_score = score.total_score * weight_multiplier
        
        return strategies
    
    def check_strategy_conflicts(
        self,
        strategies: List[StrategyScore]
    ) -> List[StrategyScore]:
        """
        Remove conflicting strategies.
        Example: VWAP says LONG but PDH rejection says SHORT → skip both
        """
        if len(strategies) <= 1:
            return strategies
        
        # Group by direction
        buy_strategies = [s for s in strategies if s.entry_signal.direction == "BUY"]
        sell_strategies = [s for s in strategies if s.entry_signal.direction == "SELL"]
        
        # If we have both BUY and SELL, keep only the highest scoring ones
        if buy_strategies and sell_strategies:
            # Keep top BUY and top SELL (allows for both directions if both are strong)
            # But if one direction is much stronger, prefer that
            best_buy = max(buy_strategies, key=lambda s: s.weighted_score) if buy_strategies else None
            best_sell = max(sell_strategies, key=lambda s: s.weighted_score) if sell_strategies else None
            
            # If one is significantly better (>20 points), only return that
            if best_buy and best_sell:
                score_diff = abs(best_buy.weighted_score - best_sell.weighted_score)
                if score_diff > 20:
                    # Significant difference - return only the better one
                    return [best_buy if best_buy.weighted_score > best_sell.weighted_score else best_sell]
            
            # Both similar or both strong - return both
            result = []
            if best_buy:
                result.append(best_buy)
            if best_sell:
                result.append(best_sell)
            return result
        
        # All same direction - return all
        return strategies

