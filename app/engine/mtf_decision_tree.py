"""
Multi-Timeframe Decision Tree
Hierarchical decision making across H1→M15→M5→M1 timeframes
"""

from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class BiasType(Enum):
    """Market bias types"""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

class SetupType(Enum):
    """Setup types for different timeframes"""
    BOS = "BOS"
    CHOCH = "CHOCH"
    OB_RETEST = "OB_RETEST"
    FVG = "FVG"
    LIQUIDITY_SWEEP = "LIQUIDITY_SWEEP"
    NONE = "NONE"

class DecisionType(Enum):
    """Final decision types"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

@dataclass
class TimeframeAnalysis:
    """Analysis result for a specific timeframe"""
    timeframe: str
    bias: BiasType
    setup: SetupType
    confidence: float
    structure_signals: List[Dict[str, Any]]
    confluence_score: float

@dataclass
class MTFDecision:
    """Multi-timeframe trading decision"""
    symbol: str
    timestamp_utc: int
    h1_bias: BiasType
    h1_setup: SetupType
    m15_setup: SetupType
    m5_structure: str
    m1_confirmation: bool
    final_decision: DecisionType
    confidence: float
    risk_reward: float
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    reasoning: str

class MTFDecisionTree:
    """Multi-timeframe decision tree for trading decisions"""
    
    def __init__(self, symbol_config: Dict[str, Any]):
        self.symbol_config = symbol_config
        self.decision_history = []
        self.performance_metrics = {}
        
    def analyze_h1_bias(self, h1_data: Dict[str, Any]) -> BiasType:
        """Analyze H1 bias based on structure and trend"""
        try:
            # Check for trend direction using EMA and structure
            ema_200 = h1_data.get('ema_200', 0)
            current_price = h1_data.get('close', 0)
            
            if current_price == 0 or ema_200 == 0:
                return BiasType.NEUTRAL
                
            # Check structure signals
            structure_signals = h1_data.get('structure_signals', [])
            bullish_signals = sum(1 for s in structure_signals 
                                if s.get('direction') == 'BULLISH')
            bearish_signals = sum(1 for s in structure_signals 
                                if s.get('direction') == 'BEARISH')
            
            # Price relative to EMA
            price_above_ema = current_price > ema_200
            
            # Determine bias
            if bullish_signals > bearish_signals and price_above_ema:
                return BiasType.BULLISH
            elif bearish_signals > bullish_signals and not price_above_ema:
                return BiasType.BEARISH
            else:
                return BiasType.NEUTRAL
                
        except Exception as e:
            logger.error(f"Error analyzing H1 bias: {e}")
            return BiasType.NEUTRAL
            
    def analyze_m15_setup(self, m15_data: Dict[str, Any], h1_bias: BiasType) -> SetupType:
        """Analyze M15 setup based on H1 bias"""
        try:
            structure_signals = m15_data.get('structure_signals', [])
            
            if not structure_signals:
                return SetupType.NONE
                
            # Get latest signal
            latest_signal = max(structure_signals, key=lambda x: x.get('timestamp', 0))
            signal_type = latest_signal.get('signal_type', '')
            direction = latest_signal.get('direction', 'NEUTRAL')
            
            # Check alignment with H1 bias
            if h1_bias == BiasType.BULLISH and direction == 'BULLISH':
                if signal_type == 'BOS':
                    return SetupType.BOS
                elif signal_type == 'CHOCH':
                    return SetupType.CHOCH
                elif signal_type == 'OB':
                    return SetupType.OB_RETEST
            elif h1_bias == BiasType.BEARISH and direction == 'BEARISH':
                if signal_type == 'BOS':
                    return SetupType.BOS
                elif signal_type == 'CHOCH':
                    return SetupType.CHOCH
                elif signal_type == 'OB':
                    return SetupType.OB_RETEST
                
            return SetupType.NONE
            
        except Exception as e:
            logger.error(f"Error analyzing M15 setup: {e}")
            return SetupType.NONE
            
    def analyze_m5_structure(self, m5_data: Dict[str, Any], m15_setup: SetupType) -> str:
        """Analyze M5 structure for confirmation"""
        try:
            if m15_setup == SetupType.NONE:
                return "NO_SETUP"
                
            structure_signals = m5_data.get('structure_signals', [])
            
            if not structure_signals:
                return "NO_CONFIRMATION"
                
            # Check for structure confirmation
            latest_signal = max(structure_signals, key=lambda x: x.get('timestamp', 0))
            signal_type = latest_signal.get('signal_type', '')
            direction = latest_signal.get('direction', 'NEUTRAL')
            
            # Map to structure type
            if signal_type == 'BOS':
                return f"BOS_{direction}"
            elif signal_type == 'CHOCH':
                return f"CHOCH_{direction}"
            elif signal_type == 'OB':
                return f"OB_{direction}"
            else:
                return "UNKNOWN"
                
        except Exception as e:
            logger.error(f"Error analyzing M5 structure: {e}")
            return "ERROR"
            
    def check_m1_confirmation(self, m1_filters: Dict[str, Any]) -> bool:
        """Check M1 confirmation filters"""
        try:
            # Check if minimum filters passed
            filters_passed = m1_filters.get('filters_passed', 0)
            min_filters = self.symbol_config.get('min_m1_filters', 3)
            
            return filters_passed >= min_filters
            
        except Exception as e:
            logger.error(f"Error checking M1 confirmation: {e}")
            return False
            
    def calculate_risk_reward(self, entry_price: float, stop_loss: float, 
                             take_profit: float) -> float:
        """Calculate risk-reward ratio"""
        try:
            if stop_loss == 0 or entry_price == 0:
                return 0.0
                
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            
            if risk == 0:
                return 0.0
                
            return reward / risk
            
        except Exception as e:
            logger.error(f"Error calculating risk-reward: {e}")
            return 0.0
            
    def calculate_lot_size(self, symbol: str, account_balance: float, 
                           risk_percent: float, stop_loss_distance: float) -> float:
        """Calculate position size based on risk management"""
        try:
            # Get symbol-specific risk parameters
            max_lot_size = self.symbol_config.get('max_lot_size', 0.01)
            default_risk = self.symbol_config.get('default_risk_percent', 0.5)
            
            # Use symbol-specific risk if available
            risk_to_use = risk_percent if risk_percent > 0 else default_risk
            
            # Calculate risk amount
            risk_amount = account_balance * (risk_to_use / 100)
            
            # Calculate lot size based on stop loss distance
            if stop_loss_distance == 0:
                return 0.0
                
            # Simplified lot size calculation (would need proper pip value calculation)
            lot_size = risk_amount / (stop_loss_distance * 100000)  # Simplified for demo
            
            # Apply maximum lot size limit
            return min(lot_size, max_lot_size)
            
        except Exception as e:
            logger.error(f"Error calculating lot size: {e}")
            return 0.0
            
    def make_decision(self, symbol: str, timestamp_utc: int, 
                     h1_analysis: Dict[str, Any], m15_analysis: Dict[str, Any],
                     m5_analysis: Dict[str, Any], m1_filters: Dict[str, Any],
                     current_price: float, account_balance: float = 10000.0) -> MTFDecision:
        """Make multi-timeframe trading decision"""
        
        try:
            # Analyze each timeframe
            h1_bias = self.analyze_h1_bias(h1_analysis)
            m15_setup = self.analyze_m15_setup(m15_analysis, h1_bias)
            m5_structure = self.analyze_m5_structure(m5_analysis, m15_setup)
            m1_confirmation = self.check_m1_confirmation(m1_filters)
            
            # Determine final decision
            final_decision = self._determine_final_decision(
                h1_bias, m15_setup, m5_structure, m1_confirmation
            )
            
            # Calculate confidence
            confidence = self._calculate_decision_confidence(
                h1_bias, m15_setup, m5_structure, m1_confirmation
            )
            
            # Calculate entry, stop, and target levels
            entry_price, stop_loss, take_profit = self._calculate_levels(
                current_price, h1_bias, m15_setup, m5_structure
            )
            
            # Calculate risk-reward
            risk_reward = self.calculate_risk_reward(entry_price, stop_loss, take_profit)
            
            # Calculate lot size
            stop_distance = abs(entry_price - stop_loss)
            lot_size = self.calculate_lot_size(symbol, account_balance, 
                                             self.symbol_config.get('default_risk_percent', 0.5),
                                             stop_distance)
            
            # Generate reasoning
            reasoning = self._generate_reasoning(
                h1_bias, m15_setup, m5_structure, m1_confirmation, final_decision
            )
            
            decision = MTFDecision(
                symbol=symbol,
                timestamp_utc=timestamp_utc,
                h1_bias=h1_bias,
                h1_setup=SetupType.NONE,  # H1 setup not implemented in this phase
                m15_setup=m15_setup,
                m5_structure=m5_structure,
                m1_confirmation=m1_confirmation,
                final_decision=final_decision,
                confidence=confidence,
                risk_reward=risk_reward,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                lot_size=lot_size,
                reasoning=reasoning
            )
            
            # Store decision for performance tracking
            self.decision_history.append(decision)
            
            return decision
            
        except Exception as e:
            logger.error(f"Error making MTF decision: {e}")
            # Return hold decision on error
            return MTFDecision(
                symbol=symbol,
                timestamp_utc=timestamp_utc,
                h1_bias=BiasType.NEUTRAL,
                h1_setup=SetupType.NONE,
                m15_setup=SetupType.NONE,
                m5_structure="ERROR",
                m1_confirmation=False,
                final_decision=DecisionType.HOLD,
                confidence=0.0,
                risk_reward=0.0,
                entry_price=current_price,
                stop_loss=current_price,
                take_profit=current_price,
                lot_size=0.0,
                reasoning=f"Error in decision making: {e}"
            )
            
    def _determine_final_decision(self, h1_bias: BiasType, m15_setup: SetupType,
                                 m5_structure: str, m1_confirmation: bool) -> DecisionType:
        """Determine final trading decision"""
        
        # Must have H1 bias and M1 confirmation
        if h1_bias == BiasType.NEUTRAL or not m1_confirmation:
            return DecisionType.HOLD
            
        # Must have M15 setup
        if m15_setup == SetupType.NONE:
            return DecisionType.HOLD
            
        # Check M5 structure alignment
        if "BULLISH" in m5_structure and h1_bias == BiasType.BULLISH:
            return DecisionType.BUY
        elif "BEARISH" in m5_structure and h1_bias == BiasType.BEARISH:
            return DecisionType.SELL
        else:
            return DecisionType.HOLD
            
    def _calculate_decision_confidence(self, h1_bias: BiasType, m15_setup: SetupType,
                                    m5_structure: str, m1_confirmation: bool) -> float:
        """Calculate decision confidence score"""
        confidence = 0.0
        
        # H1 bias weight
        if h1_bias != BiasType.NEUTRAL:
            confidence += 0.3
            
        # M15 setup weight
        if m15_setup != SetupType.NONE:
            confidence += 0.3
            
        # M5 structure weight
        if "BOS" in m5_structure or "CHOCH" in m5_structure:
            confidence += 0.2
        elif "OB" in m5_structure:
            confidence += 0.15
            
        # M1 confirmation weight
        if m1_confirmation:
            confidence += 0.2
            
        return min(1.0, confidence)
        
    def _calculate_levels(self, current_price: float, h1_bias: BiasType,
                         m15_setup: SetupType, m5_structure: str) -> Tuple[float, float, float]:
        """Calculate entry, stop loss, and take profit levels"""
        
        # Base levels
        entry_price = current_price
        stop_loss = current_price
        take_profit = current_price
        
        # Get ATR for level calculation (simplified)
        atr = self.symbol_config.get('atr_value', 0.001)  # Would come from actual data
        
        if h1_bias == BiasType.BULLISH:
            # Bullish setup
            stop_loss = current_price - (atr * 2)  # 2 ATR stop
            take_profit = current_price + (atr * 6)  # 1:3 R:R
        elif h1_bias == BiasType.BEARISH:
            # Bearish setup
            stop_loss = current_price + (atr * 2)  # 2 ATR stop
            take_profit = current_price - (atr * 6)  # 1:3 R:R
            
        return entry_price, stop_loss, take_profit
        
    def _generate_reasoning(self, h1_bias: BiasType, m15_setup: SetupType,
                          m5_structure: str, m1_confirmation: bool, 
                          final_decision: DecisionType) -> str:
        """Generate human-readable reasoning for decision"""
        
        reasoning_parts = []
        
        # H1 bias
        reasoning_parts.append(f"H1 bias: {h1_bias.value}")
        
        # M15 setup
        reasoning_parts.append(f"M15 setup: {m15_setup.value}")
        
        # M5 structure
        reasoning_parts.append(f"M5 structure: {m5_structure}")
        
        # M1 confirmation
        reasoning_parts.append(f"M1 confirmation: {'Yes' if m1_confirmation else 'No'}")
        
        # Final decision
        reasoning_parts.append(f"Decision: {final_decision.value}")
        
        return " | ".join(reasoning_parts)
        
    def get_performance_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Get performance metrics for recent decisions"""
        try:
            cutoff_time = int(datetime.now(timezone.utc).timestamp()) - (days * 24 * 3600)
            recent_decisions = [d for d in self.decision_history 
                              if d.timestamp_utc >= cutoff_time]
            
            if not recent_decisions:
                return {}
                
            total_decisions = len(recent_decisions)
            buy_decisions = sum(1 for d in recent_decisions if d.final_decision == DecisionType.BUY)
            sell_decisions = sum(1 for d in recent_decisions if d.final_decision == DecisionType.SELL)
            hold_decisions = sum(1 for d in recent_decisions if d.final_decision == DecisionType.HOLD)
            
            avg_confidence = sum(d.confidence for d in recent_decisions) / total_decisions
            avg_risk_reward = sum(d.risk_reward for d in recent_decisions) / total_decisions
            
            return {
                "total_decisions": total_decisions,
                "buy_decisions": buy_decisions,
                "sell_decisions": sell_decisions,
                "hold_decisions": hold_decisions,
                "avg_confidence": avg_confidence,
                "avg_risk_reward": avg_risk_reward,
                "decision_rate": (buy_decisions + sell_decisions) / total_decisions
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}


# Example usage and testing
if __name__ == "__main__":
    # Test MTF decision tree
    config = {
        'max_lot_size': 0.01,
        'default_risk_percent': 0.5,
        'min_m1_filters': 3,
        'atr_value': 0.001
    }
    
    decision_tree = MTFDecisionTree(config)
    
    # Test with sample data
    h1_analysis = {
        'close': 50000.0,
        'ema_200': 49500.0,
        'structure_signals': [
            {'signal_type': 'BOS', 'direction': 'BULLISH', 'timestamp': 1000}
        ]
    }
    
    m15_analysis = {
        'structure_signals': [
            {'signal_type': 'BOS', 'direction': 'BULLISH', 'timestamp': 1000}
        ]
    }
    
    m5_analysis = {
        'structure_signals': [
            {'signal_type': 'BOS', 'direction': 'BULLISH', 'timestamp': 1000}
        ]
    }
    
    m1_filters = {
        'filters_passed': 4,
        'filter_score': 0.8
    }
    
    decision = decision_tree.make_decision(
        symbol="BTCUSDc",
        timestamp_utc=int(datetime.now(timezone.utc).timestamp()),
        h1_analysis=h1_analysis,
        m15_analysis=m15_analysis,
        m5_analysis=m5_analysis,
        m1_filters=m1_filters,
        current_price=50000.0
    )
    
    print(f"Decision: {decision.final_decision.value}")
    print(f"Confidence: {decision.confidence:.2f}")
    print(f"Risk-Reward: {decision.risk_reward:.2f}")
    print(f"Entry: {decision.entry_price:.2f}")
    print(f"Stop Loss: {decision.stop_loss:.2f}")
    print(f"Take Profit: {decision.take_profit:.2f}")
    print(f"Lot Size: {decision.lot_size:.4f}")
    print(f"Reasoning: {decision.reasoning}")
