"""
Volatility-Aware Strategy Selector - Phase 2 Implementation

Scores and selects trading strategies based on volatility regime and market conditions.
Strategies:
1. Breakout-Continuation
2. Volatility Reversion Scalp
3. Post-News Reaction Trade
4. Inside Bar Volatility Trap

Each strategy receives a score (0-100) based on confluence of conditions.
Minimum threshold: 75+ before selection.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class VolatilityStrategy(Enum):
    """Volatility-aware trading strategies"""
    BREAKOUT_CONTINUATION = "BREAKOUT_CONTINUATION"
    VOLATILITY_REVERSION_SCALP = "VOLATILITY_REVERSION_SCALP"
    POST_NEWS_REACTION = "POST_NEWS_REACTION"
    INSIDE_BAR_VOLATILITY_TRAP = "INSIDE_BAR_VOLATILITY_TRAP"
    WAIT = "WAIT"


class StrategyScore:
    """Represents a scored strategy"""
    
    def __init__(
        self,
        strategy: VolatilityStrategy,
        score: float,
        reasoning: str,
        entry_conditions: Dict[str, Any],
        entry: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        confidence: float = 0.0,
        direction: Optional[str] = None,
        risk_reward_ratio: Optional[float] = None
    ):
        self.strategy = strategy
        self.score = score
        self.reasoning = reasoning
        self.entry_conditions = entry_conditions
        self.entry = entry
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.confidence = confidence
        self.direction = direction  # "BUY" or "SELL"
        self.risk_reward_ratio = risk_reward_ratio  # R:R ratio
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "strategy": self.strategy.value,
            "score": self.score,
            "reasoning": self.reasoning,
            "entry_conditions": self.entry_conditions,
            "entry": self.entry,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "confidence": self.confidence,
            "direction": self.direction,
            "risk_reward_ratio": self.risk_reward_ratio
        }


class VolatilityStrategySelector:
    """
    Selects trading strategies based on volatility regime and market conditions.
    """
    
    # Minimum score threshold for strategy selection
    MIN_SCORE_THRESHOLD = 75.0
    
    def __init__(self):
        """Initialize the strategy selector"""
        pass
    
    def select_strategy(
        self,
        symbol: str,
        volatility_regime: Dict[str, Any],
        market_data: Dict[str, Any],
        timeframe_data: Dict[str, Dict[str, Any]],
        news_data: Optional[Dict[str, Any]] = None,
        current_time: Optional[datetime] = None
    ) -> Tuple[Optional[StrategyScore], List[StrategyScore]]:
        """
        Select best strategy based on volatility regime and market conditions.
        
        Args:
            symbol: Trading symbol
            volatility_regime: Detected volatility regime data
            market_data: Current market data (price, indicators, etc.)
            timeframe_data: Multi-timeframe data (M5, M15, H1)
            news_data: Optional news/event data
            current_time: Current timestamp
        
        Returns:
            Tuple of (best_strategy, all_scores):
            - best_strategy: Selected strategy if score >= 75, else None
            - all_scores: List of all strategy scores for transparency
        """
        if current_time is None:
            current_time = datetime.now()
        
        # Score all strategies
        all_scores = []
        
        # 1. Breakout-Continuation
        breakout_score = self._score_breakout_continuation(
            symbol, volatility_regime, market_data, timeframe_data
        )
        all_scores.append(breakout_score)
        
        # 2. Volatility Reversion Scalp
        reversion_score = self._score_volatility_reversion_scalp(
            symbol, volatility_regime, market_data, timeframe_data
        )
        all_scores.append(reversion_score)
        
        # 3. Post-News Reaction Trade
        post_news_score = self._score_post_news_reaction(
            symbol, volatility_regime, market_data, timeframe_data, news_data, current_time
        )
        all_scores.append(post_news_score)
        
        # 4. Inside Bar Volatility Trap
        inside_bar_score = self._score_inside_bar_volatility_trap(
            symbol, volatility_regime, market_data, timeframe_data
        )
        all_scores.append(inside_bar_score)
        
        # Sort by score (descending)
        all_scores.sort(key=lambda x: x.score, reverse=True)
        
        # Select best strategy if score >= threshold
        best_strategy = None
        if all_scores and all_scores[0].score >= self.MIN_SCORE_THRESHOLD:
            best_strategy = all_scores[0]
            
            # Calculate Entry/SL/TP for selected strategy (Phase 3)
            try:
                best_strategy = self._calculate_trade_levels(
                    best_strategy,
                    symbol,
                    volatility_regime,
                    market_data,
                    timeframe_data
                )
            except Exception as e:
                logger.warning(f"Error calculating trade levels: {e}")
                # Continue with strategy without levels
            
            logger.info(
                f"Selected strategy: {best_strategy.strategy.value} "
                f"(score: {best_strategy.score:.1f}, confidence: {best_strategy.confidence:.1f}%)"
            )
            if best_strategy.entry:
                logger.info(
                    f"Trade levels: Entry={best_strategy.entry:.5f}, "
                    f"SL={best_strategy.stop_loss:.5f}, "
                    f"TP={best_strategy.take_profit:.5f}, "
                    f"R:R={best_strategy.risk_reward_ratio:.2f}"
                )
        else:
            best_score = all_scores[0].score if all_scores else 0
            logger.info(
                f"No strategy selected (best score: {best_score:.1f} < {self.MIN_SCORE_THRESHOLD})"
            )
        
        return best_strategy, all_scores
    
    def _score_breakout_continuation(
        self,
        symbol: str,
        volatility_regime: Dict[str, Any],
        market_data: Dict[str, Any],
        timeframe_data: Dict[str, Dict[str, Any]]
    ) -> StrategyScore:
        """
        Score Breakout-Continuation strategy (0-100).
        
        Conditions:
        - ATR rising (ratio > 1.3)
        - ADX > 28 and rising
        - Price breaking structure (higher high / lower low)
        - Volume confirms breakout
        - Strong candle body, minimal wick
        
        Scoring: 40% ATR + 30% Structure + 30% Volume
        """
        score = 0.0
        reasoning_parts = []
        entry_conditions = {}
        
        # Get regime data
        regime = volatility_regime.get("regime")
        atr_ratio = volatility_regime.get("atr_ratio", 1.0)
        adx_composite = volatility_regime.get("adx_composite", 0.0)
        
        # Get market data
        m5_data = timeframe_data.get("M5", {})
        m15_data = timeframe_data.get("M15", {})
        h1_data = timeframe_data.get("H1", {})
        current_price = market_data.get("current_price", 0)
        
        # ATR component (40% weight)
        atr_score = 0.0
        if atr_ratio >= 1.4:  # Volatile
            atr_score = min(40, 25 + (atr_ratio - 1.4) * 50)
            reasoning_parts.append(f"ATR ratio {atr_ratio:.2f}x (strong)")
        elif atr_ratio >= 1.3:
            atr_score = 20 + (atr_ratio - 1.3) * 50
            reasoning_parts.append(f"ATR ratio {atr_ratio:.2f}x (moderate)")
        else:
            reasoning_parts.append(f"ATR ratio {atr_ratio:.2f}x (weak)")
        score += atr_score
        entry_conditions["atr_ratio"] = atr_ratio
        
        # ADX component (part of ATR score)
        if adx_composite >= 28:
            adx_bonus = min(10, (adx_composite - 28) * 0.5)
            score += adx_bonus
            reasoning_parts.append(f"ADX {adx_composite:.1f} (strong trend)")
        entry_conditions["adx"] = adx_composite
        
        # Structure component (30% weight)
        structure_score = 0.0
        # Check for structure breaks (higher high / lower low)
        # This is simplified - in production, would check actual structure breaks
        if h1_data.get("high") and h1_data.get("low"):
            # Placeholder: check if price is near recent highs/lows
            recent_high = h1_data.get("high")
            recent_low = h1_data.get("low")
            # Handle lists - take last value if list
            if isinstance(recent_high, list) and len(recent_high) > 0:
                recent_high = float(recent_high[-1])
            elif recent_high:
                recent_high = float(recent_high)
            else:
                recent_high = None
                
            if isinstance(recent_low, list) and len(recent_low) > 0:
                recent_low = float(recent_low[-1])
            elif recent_low:
                recent_low = float(recent_low)
            else:
                recent_low = None
                
            if recent_high and recent_low and isinstance(recent_high, (int, float)) and isinstance(recent_low, (int, float)):
                price_position = (current_price - recent_low) / (recent_high - recent_low) if (recent_high - recent_low) > 0 else 0.5
                if price_position > 0.8 or price_position < 0.2:
                    structure_score = 20
                    reasoning_parts.append("Near structure extremes")
                else:
                    structure_score = 10
        score += structure_score
        entry_conditions["structure_break"] = structure_score > 15
        
        # Volume component (30% weight)
        volume_score = 0.0
        volume_confirmed = volatility_regime.get("volume_confirmed", False)
        if volume_confirmed:
            volume_score = 30
            reasoning_parts.append("Volume confirms breakout")
        else:
            volume_score = 10
            reasoning_parts.append("Volume not confirmed")
        score += volume_score
        entry_conditions["volume_confirmed"] = volume_confirmed
        
        # Clamp score to 0-100
        score = min(100, max(0, score))
        
        # Calculate confidence (based on score and regime confidence)
        regime_confidence = volatility_regime.get("confidence", 0)
        confidence = (score * 0.7) + (regime_confidence * 0.3)
        
        reasoning = "Breakout-Continuation: " + " | ".join(reasoning_parts) if reasoning_parts else "No conditions met"
        
        return StrategyScore(
            strategy=VolatilityStrategy.BREAKOUT_CONTINUATION,
            score=score,
            reasoning=reasoning,
            entry_conditions=entry_conditions,
            confidence=confidence
        )
    
    def _score_volatility_reversion_scalp(
        self,
        symbol: str,
        volatility_regime: Dict[str, Any],
        market_data: Dict[str, Any],
        timeframe_data: Dict[str, Dict[str, Any]]
    ) -> StrategyScore:
        """
        Score Volatility Reversion Scalp strategy (0-100).
        
        Conditions:
        - ATR high but flattening (not rising)
        - RSI > 80 or < 20 + divergence forming
        - Volume spike then drop (exhaustion)
        - Long wick rejection after parabolic move
        
        Scoring: 35% ATR slope + 35% RSI + 30% Volume
        """
        score = 0.0
        reasoning_parts = []
        entry_conditions = {}
        
        # Get regime data
        atr_ratio = volatility_regime.get("atr_ratio", 1.0)
        
        # Get market data
        m5_data = timeframe_data.get("M5", {})
        m15_data = timeframe_data.get("M15", {})
        current_price = market_data.get("current_price", 0)
        
        # ATR slope component (35% weight)
        # Check if ATR is high but flattening
        atr_slope_score = 0.0
        if atr_ratio >= 1.4:  # High ATR
            # Check if ATR is flattening (would need ATR history - simplified here)
            # For now, assume if ATR is high, it might be flattening
            atr_slope_score = 20
            reasoning_parts.append(f"ATR elevated {atr_ratio:.2f}x (potential flattening)")
        else:
            reasoning_parts.append(f"ATR {atr_ratio:.2f}x (not elevated)")
        score += atr_slope_score
        entry_conditions["atr_ratio"] = atr_ratio
        
        # RSI component (35% weight)
        rsi_score = 0.0
        rsi = m5_data.get("rsi") or m15_data.get("rsi")
        if rsi:
            if rsi > 80 or rsi < 20:
                rsi_score = 35
                reasoning_parts.append(f"RSI extreme {rsi:.1f} (overbought/oversold)")
            elif rsi > 70 or rsi < 30:
                rsi_score = 20
                reasoning_parts.append(f"RSI {rsi:.1f} (approaching extremes)")
            else:
                reasoning_parts.append(f"RSI {rsi:.1f} (neutral)")
        else:
            reasoning_parts.append("RSI not available")
        score += rsi_score
        entry_conditions["rsi"] = rsi
        
        # Volume exhaustion component (30% weight)
        # Check for volume spike then drop
        volume_score = 0.0
        volume_confirmed = volatility_regime.get("volume_confirmed", False)
        # Simplified: if volume was confirmed but now might be dropping
        if volume_confirmed:
            volume_score = 15  # Partial score (volume was high, might be dropping)
            reasoning_parts.append("Volume spike detected (potential exhaustion)")
        else:
            reasoning_parts.append("No volume exhaustion signal")
        score += volume_score
        entry_conditions["volume_exhaustion"] = volume_score > 10
        
        # Clamp score to 0-100
        score = min(100, max(0, score))
        
        # Calculate confidence
        regime_confidence = volatility_regime.get("confidence", 0)
        confidence = (score * 0.7) + (regime_confidence * 0.3)
        
        reasoning = "Volatility Reversion Scalp: " + " | ".join(reasoning_parts) if reasoning_parts else "No conditions met"
        
        return StrategyScore(
            strategy=VolatilityStrategy.VOLATILITY_REVERSION_SCALP,
            score=score,
            reasoning=reasoning,
            entry_conditions=entry_conditions,
            confidence=confidence
        )
    
    def _score_post_news_reaction(
        self,
        symbol: str,
        volatility_regime: Dict[str, Any],
        market_data: Dict[str, Any],
        timeframe_data: Dict[str, Dict[str, Any]],
        news_data: Optional[Dict[str, Any]],
        current_time: datetime
    ) -> StrategyScore:
        """
        Score Post-News Reaction Trade strategy (0-100).
        
        Conditions:
        - News < 30 minutes ago
        - ATR spike → contraction
        - Volume elevated
        - Pullback to EMA(20) with structure confirmation
        
        Scoring: 40% News timing + 30% ATR + 30% Structure
        """
        score = 0.0
        reasoning_parts = []
        entry_conditions = {}
        
        # News timing component (40% weight)
        news_score = 0.0
        if news_data:
            # Check if news event occurred recently
            news_time = news_data.get("timestamp")
            if news_time:
                try:
                    if isinstance(news_time, str):
                        # Try dateutil parser first, fallback to datetime.fromisoformat
                        try:
                            from dateutil import parser
                            news_time = parser.parse(news_time)
                        except ImportError:
                            # Fallback to ISO format parsing
                            from datetime import datetime
                            news_time = datetime.fromisoformat(news_time.replace('Z', '+00:00'))
                    
                    time_diff = (current_time - news_time).total_seconds() / 60  # minutes
                except Exception as e:
                    logger.debug(f"Error parsing news timestamp: {e}")
                    time_diff = 999  # Treat as old news
                if 15 <= time_diff <= 30:
                    news_score = 40
                    reasoning_parts.append(f"News {time_diff:.0f} min ago (optimal timing)")
                elif 10 <= time_diff < 15 or 30 < time_diff <= 45:
                    news_score = 25
                    reasoning_parts.append(f"News {time_diff:.0f} min ago (acceptable timing)")
                else:
                    reasoning_parts.append(f"News {time_diff:.0f} min ago (timing not optimal)")
            else:
                reasoning_parts.append("No news timestamp")
        else:
            reasoning_parts.append("No news data available")
        score += news_score
        entry_conditions["news_timing"] = news_score >= 25
        
        # ATR component (30% weight)
        atr_score = 0.0
        atr_ratio = volatility_regime.get("atr_ratio", 1.0)
        if atr_ratio >= 1.3:
            atr_score = 30
            reasoning_parts.append(f"ATR elevated {atr_ratio:.2f}x (post-news spike)")
        elif atr_ratio >= 1.2:
            atr_score = 20
            reasoning_parts.append(f"ATR {atr_ratio:.2f}x (moderate)")
        else:
            reasoning_parts.append(f"ATR {atr_ratio:.2f}x (low)")
        score += atr_score
        entry_conditions["atr_ratio"] = atr_ratio
        
        # Structure component (30% weight)
        structure_score = 0.0
        m5_data = timeframe_data.get("M5", {})
        ema20 = m5_data.get("ema20")
        current_price = market_data.get("current_price", 0)
        
        if ema20 and current_price:
            # Check if price is near EMA(20) (pullback)
            price_vs_ema = abs(current_price - ema20) / ema20 * 100 if ema20 > 0 else 100
            if price_vs_ema < 0.5:  # Within 0.5% of EMA
                structure_score = 30
                reasoning_parts.append("Price at EMA(20) pullback")
            elif price_vs_ema < 1.0:
                structure_score = 20
                reasoning_parts.append("Price near EMA(20)")
            else:
                reasoning_parts.append("Price not at EMA pullback")
        else:
            reasoning_parts.append("EMA(20) not available")
        score += structure_score
        entry_conditions["ema20_pullback"] = structure_score >= 20
        
        # Clamp score to 0-100
        score = min(100, max(0, score))
        
        # Calculate confidence
        regime_confidence = volatility_regime.get("confidence", 0)
        confidence = (score * 0.7) + (regime_confidence * 0.3)
        
        reasoning = "Post-News Reaction: " + " | ".join(reasoning_parts) if reasoning_parts else "No conditions met"
        
        return StrategyScore(
            strategy=VolatilityStrategy.POST_NEWS_REACTION,
            score=score,
            reasoning=reasoning,
            entry_conditions=entry_conditions,
            confidence=confidence
        )
    
    def _score_inside_bar_volatility_trap(
        self,
        symbol: str,
        volatility_regime: Dict[str, Any],
        market_data: Dict[str, Any],
        timeframe_data: Dict[str, Dict[str, Any]]
    ) -> StrategyScore:
        """
        Score Inside Bar Volatility Trap strategy (0-100).
        
        Conditions:
        - Multiple inside bars (2-5) forming
        - Bollinger Bands tightening
        - ATR decreasing
        - Volume dropping
        
        Scoring: 40% Pattern + 30% Compression + 30% ATR
        """
        score = 0.0
        reasoning_parts = []
        entry_conditions = {}
        
        # Pattern component (40% weight) - inside bars
        pattern_score = 0.0
        # Simplified: would need to analyze recent candles for inside bar patterns
        # For now, check if BB width is tight (compression)
        m5_data = timeframe_data.get("M5", {})
        bb_upper = m5_data.get("bb_upper")
        bb_lower = m5_data.get("bb_lower")
        bb_middle = m5_data.get("bb_middle")
        
        if bb_upper and bb_lower and bb_middle:
            bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
            # Check if BB is tight (compression)
            if bb_width < 0.01:  # Very tight (< 1% width)
                pattern_score = 40
                reasoning_parts.append("BB width tight (compression detected)")
            elif bb_width < 0.02:
                pattern_score = 25
                reasoning_parts.append(f"BB width {bb_width*100:.2f}% (moderate compression)")
            else:
                reasoning_parts.append(f"BB width {bb_width*100:.2f}% (not compressed)")
        else:
            reasoning_parts.append("BB data not available")
        score += pattern_score
        entry_conditions["bb_compression"] = pattern_score >= 25
        
        # Compression component (30% weight) - ATR decreasing
        compression_score = 0.0
        atr_ratio = volatility_regime.get("atr_ratio", 1.0)
        # If ATR is decreasing (would need ATR history - simplified)
        # Lower ATR ratio suggests compression
        if atr_ratio < 1.2:
            compression_score = 30
            reasoning_parts.append(f"ATR {atr_ratio:.2f}x (compression)")
        elif atr_ratio < 1.3:
            compression_score = 20
            reasoning_parts.append(f"ATR {atr_ratio:.2f}x (moderate)")
        else:
            reasoning_parts.append(f"ATR {atr_ratio:.2f}x (not compressed)")
        score += compression_score
        entry_conditions["atr_ratio"] = atr_ratio
        
        # Volume component (30% weight) - volume dropping
        volume_score = 0.0
        volume_confirmed = volatility_regime.get("volume_confirmed", False)
        # If volume is NOT confirmed (was high, now dropping)
        if not volume_confirmed and atr_ratio < 1.3:
            volume_score = 30
            reasoning_parts.append("Volume dropping (compression)")
        else:
            volume_score = 10
            reasoning_parts.append("Volume not dropping")
        score += volume_score
        entry_conditions["volume_dropping"] = volume_score >= 20
        
        # Clamp score to 0-100
        score = min(100, max(0, score))
        
        # Calculate confidence
        regime_confidence = volatility_regime.get("confidence", 0)
        confidence = (score * 0.7) + (regime_confidence * 0.3)
        
        reasoning = "Inside Bar Volatility Trap: " + " | ".join(reasoning_parts) if reasoning_parts else "No conditions met"
        
        return StrategyScore(
            strategy=VolatilityStrategy.INSIDE_BAR_VOLATILITY_TRAP,
            score=score,
            reasoning=reasoning,
            entry_conditions=entry_conditions,
            confidence=confidence
        )
    
    def _calculate_trade_levels(
        self,
        strategy_score: StrategyScore,
        symbol: str,
        volatility_regime: Dict[str, Any],
        market_data: Dict[str, Any],
        timeframe_data: Dict[str, Dict[str, Any]]
    ) -> StrategyScore:
        """
        Calculate Entry/SL/TP levels for a selected strategy.
        
        Args:
            strategy_score: Selected strategy score
            symbol: Trading symbol
            volatility_regime: Detected volatility regime data
            market_data: Current market data
            timeframe_data: Multi-timeframe data
        
        Returns:
            StrategyScore with calculated Entry/SL/TP levels
        """
        try:
            from infra.volatility_risk_manager import VolatilityRiskManager
            
            current_price = market_data.get("current_price", 0)
            if current_price == 0:
                # Try to get from timeframe data
                m5_data = timeframe_data.get("M5", {})
                current_price = (
                    m5_data.get("current_close") or
                    m5_data.get("close") or
                    0
                )
                if isinstance(current_price, list) and len(current_price) > 0:
                    current_price = float(current_price[-1])
                else:
                    current_price = float(current_price) if current_price else 0
            
            if current_price == 0:
                logger.warning("Cannot calculate trade levels: no current price available")
                return strategy_score
            
            # Get ATR for level calculations
            m5_data = timeframe_data.get("M5", {})
            h1_data = timeframe_data.get("H1", {})
            atr_14 = m5_data.get("atr14") or m5_data.get("atr_14") or h1_data.get("atr14") or h1_data.get("atr_14")
            
            if not atr_14 or atr_14 == 0:
                logger.warning("Cannot calculate trade levels: no ATR available")
                return strategy_score
            
            risk_manager = VolatilityRiskManager()
            
            # Determine direction based on strategy and conditions
            direction = self._determine_direction(
                strategy_score.strategy,
                market_data,
                timeframe_data
            )
            
            # Calculate stop loss based on strategy and regime
            stop_loss = self._calculate_strategy_stop_loss(
                strategy_score.strategy,
                current_price,
                direction,
                atr_14,
                volatility_regime,
                timeframe_data
            )
            
            # Calculate entry (varies by strategy)
            entry = self._calculate_strategy_entry(
                strategy_score.strategy,
                current_price,
                direction,
                atr_14,
                timeframe_data
            )
            
            # Calculate take profit
            take_profit = risk_manager.calculate_volatility_adjusted_take_profit(
                entry_price=entry,
                stop_loss=stop_loss,
                direction=direction,
                atr=atr_14,
                volatility_regime=volatility_regime
            )
            
            # Calculate risk:reward ratio
            if direction == "BUY":
                risk = entry - stop_loss
                reward = take_profit - entry
            else:  # SELL
                risk = stop_loss - entry
                reward = entry - take_profit
            
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            # Update strategy score with calculated levels
            strategy_score.entry = entry
            strategy_score.stop_loss = stop_loss
            strategy_score.take_profit = take_profit
            strategy_score.direction = direction
            strategy_score.risk_reward_ratio = risk_reward_ratio
            
            return strategy_score
            
        except Exception as e:
            logger.error(f"Error calculating trade levels: {e}", exc_info=True)
            return strategy_score
    
    def _determine_direction(
        self,
        strategy: VolatilityStrategy,
        market_data: Dict[str, Any],
        timeframe_data: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        Determine trade direction based on strategy and market conditions.
        
        Returns:
            "BUY" or "SELL"
        """
        # For now, use simple heuristics - can be enhanced with actual signal detection
        m5_data = timeframe_data.get("M5", {})
        m15_data = timeframe_data.get("M15", {})
        h1_data = timeframe_data.get("H1", {})
        
        # Check trend/ADX
        adx = h1_data.get("adx") or m15_data.get("adx") or 0
        # Check price momentum
        current_price = market_data.get("current_price", 0)
        
        # Simplified: if ADX > 25, check recent price action
        # For now, default to BUY (can be enhanced with actual signal analysis)
        # In production, this would use the actual strategy signals
        
        # For Breakout-Continuation: check structure breaks
        if strategy == VolatilityStrategy.BREAKOUT_CONTINUATION:
            # Check if price is near recent highs (potential breakout up) or lows (breakout down)
            # Simplified for now
            return "BUY"  # Default - would need actual structure analysis
        
        # For Reversion Scalp: check RSI extremes
        elif strategy == VolatilityStrategy.VOLATILITY_REVERSION_SCALP:
            rsi = m5_data.get("rsi") or m15_data.get("rsi")
            if rsi:
                if rsi > 80:
                    return "SELL"  # Overbought - sell
                elif rsi < 20:
                    return "BUY"  # Oversold - buy
            return "BUY"  # Default
        
        # For Post-News Reaction: check initial spike direction
        elif strategy == VolatilityStrategy.POST_NEWS_REACTION:
            # Would need news data analysis - default for now
            return "BUY"
        
        # For Inside Bar Volatility Trap: check compression direction
        elif strategy == VolatilityStrategy.INSIDE_BAR_VOLATILITY_TRAP:
            # Would need pattern analysis - default for now
            return "BUY"
        
        return "BUY"  # Default
    
    def _calculate_strategy_entry(
        self,
        strategy: VolatilityStrategy,
        current_price: float,
        direction: str,
        atr: float,
        timeframe_data: Dict[str, Dict[str, Any]]
    ) -> float:
        """
        Calculate entry price based on strategy type.
        
        Returns:
            Entry price
        """
        if strategy == VolatilityStrategy.BREAKOUT_CONTINUATION:
            # Entry: Buy/Sell Stop 5-10 pips beyond breakout candle close
            # For now, use current price + small buffer
            buffer = atr * 0.1  # Small buffer
            if direction == "BUY":
                return current_price + buffer
            else:
                return current_price - buffer
        
        elif strategy == VolatilityStrategy.VOLATILITY_REVERSION_SCALP:
            # Entry: At strong wick rejection, opposite direction of spike
            # Use current price (would need wick analysis in production)
            return current_price
        
        elif strategy == VolatilityStrategy.POST_NEWS_REACTION:
            # Entry: Pullback to EMA(20) with structure confirmation
            m5_data = timeframe_data.get("M5", {})
            ema20 = m5_data.get("ema20")
            if ema20:
                return float(ema20)
            return current_price
        
        elif strategy == VolatilityStrategy.INSIDE_BAR_VOLATILITY_TRAP:
            # Entry: Stop order beyond range high/low
            # For now, use current price + buffer
            buffer = atr * 0.15
            if direction == "BUY":
                return current_price + buffer
            else:
                return current_price - buffer
        
        return current_price
    
    def _calculate_strategy_stop_loss(
        self,
        strategy: VolatilityStrategy,
        current_price: float,
        direction: str,
        atr: float,
        volatility_regime: Dict[str, Any],
        timeframe_data: Dict[str, Dict[str, Any]]
    ) -> float:
        """
        Calculate stop loss based on strategy type.
        
        Returns:
            Stop loss price
        """
        from infra.volatility_risk_manager import VolatilityRiskManager
        
        risk_manager = VolatilityRiskManager()
        
        if strategy == VolatilityStrategy.BREAKOUT_CONTINUATION:
            # Stop Loss: 1.5× ATR below/above structure
            return risk_manager.calculate_volatility_adjusted_stop_loss(
                entry_price=current_price,
                direction=direction,
                atr=atr,
                volatility_regime=volatility_regime
            )
        
        elif strategy == VolatilityStrategy.VOLATILITY_REVERSION_SCALP:
            # Stop Loss: Beyond extreme wick (2.0× ATR for safety)
            stop_distance = atr * 2.0
            if direction == "BUY":
                return current_price - stop_distance
            else:
                return current_price + stop_distance
        
        elif strategy == VolatilityStrategy.POST_NEWS_REACTION:
            # Stop Loss: 1.5× ATR
            return risk_manager.calculate_volatility_adjusted_stop_loss(
                entry_price=current_price,
                direction=direction,
                atr=atr,
                volatility_regime=volatility_regime
            )
        
        elif strategy == VolatilityStrategy.INSIDE_BAR_VOLATILITY_TRAP:
            # Stop Loss: Opposite side of inside bar range (1.0× ATR)
            stop_distance = atr * 1.0
            if direction == "BUY":
                return current_price - stop_distance
            else:
                return current_price + stop_distance
        
        # Default: use volatility-adjusted stop
        return risk_manager.calculate_volatility_adjusted_stop_loss(
            entry_price=current_price,
            direction=direction,
            atr=atr,
            volatility_regime=volatility_regime
        )

