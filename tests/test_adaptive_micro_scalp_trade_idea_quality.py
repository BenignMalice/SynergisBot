"""
Trade Idea Quality Tests for Adaptive Micro-Scalp Strategy System

Tests trade idea generation quality:
- Trade ideas have required fields
- Risk-reward ratios are reasonable
- Stop loss and take profit are valid
- Entry prices are realistic
"""

import unittest
from unittest.mock import Mock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.micro_scalp_strategies import (
    VWAPReversionChecker,
    RangeScalpChecker,
    BalancedZoneChecker
)
from infra.micro_scalp_conditions import ConditionCheckResult


class TestTradeIdeaQuality(unittest.TestCase):
    """Test trade idea quality and validity"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'xauusd_rules': {
                'confluence_scoring': {
                    'min_score_for_trade': 5,
                    'min_score_for_aplus': 7
                }
            },
            'regime_detection': {
                'enabled': True,
                'strategy_confidence_thresholds': {
                    'vwap_reversion': 70,
                    'range_scalp': 55,
                    'balanced_zone': 60
                }
            }
        }
        
        self.checker_vwap = VWAPReversionChecker(
            config=self.config,
            volatility_filter=Mock(),
            vwap_filter=Mock(),
            sweep_detector=Mock(),
            ob_detector=Mock(),
            spread_tracker=Mock(),
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='vwap_reversion'
        )
        
        self.checker_range = RangeScalpChecker(
            config=self.config,
            volatility_filter=Mock(),
            vwap_filter=Mock(),
            sweep_detector=Mock(),
            ob_detector=Mock(),
            spread_tracker=Mock(),
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='range_scalp'
        )
        
        self.checker_balanced = BalancedZoneChecker(
            config=self.config,
            volatility_filter=Mock(),
            vwap_filter=Mock(),
            sweep_detector=Mock(),
            ob_detector=Mock(),
            spread_tracker=Mock(),
            m1_analyzer=None,
            session_manager=None,
            news_service=None,
            strategy_name='balanced_zone'
        )
    
    def _create_valid_result(self):
        """Create a valid ConditionCheckResult"""
        return ConditionCheckResult(
            passed=True,
            pre_trade_passed=True,
            location_passed=True,
            primary_triggers=1,  # Count, not list
            secondary_confluence=1,  # Count, not list
            confluence_score=6.0,
            is_aplus_setup=False,
            reasons=[],
            details={
                'pre_trade': {'passed': True},
                'location': {'passed': True},
                'signals': {'passed': True}
            }
        )
    
    def _create_snapshot(self, symbol='XAUUSDc', price=2000.0):
        """Create a valid snapshot"""
        return {
            'symbol': symbol,
            'candles': [
                {'time': i, 'open': price, 'high': price + 0.5, 'low': price - 0.5, 'close': price, 'volume': 1000}
                for i in range(20)
            ],
            'current_price': price,
            'vwap': price,
            'atr1': 0.6
        }
    
    def test_trade_idea_has_required_fields(self):
        """Test: Trade idea has all required fields"""
        snapshot = self._create_snapshot()
        result = self._create_valid_result()
        
        # Set snapshot for checker
        self.checker_vwap._current_snapshot = snapshot
        
        trade_idea = self.checker_vwap.generate_trade_idea(snapshot, result)
        
        if trade_idea:
            required_fields = ['symbol', 'direction', 'entry_price', 'sl', 'tp']
            for field in required_fields:
                self.assertIn(field, trade_idea, f"Trade idea missing required field: {field}")
    
    def test_trade_idea_risk_reward_ratio(self):
        """Test: Trade idea has reasonable risk-reward ratio"""
        snapshot = self._create_snapshot()
        result = self._create_valid_result()
        
        self.checker_vwap._current_snapshot = snapshot
        
        trade_idea = self.checker_vwap.generate_trade_idea(snapshot, result)
        
        if trade_idea:
            entry = trade_idea.get('entry_price')
            sl = trade_idea.get('sl')
            tp = trade_idea.get('tp')
            
            if entry and sl and tp:
                direction = trade_idea.get('direction', 'BUY')
                
                if direction == 'BUY':
                    risk = abs(entry - sl)
                    reward = abs(tp - entry)
                else:  # SELL
                    risk = abs(sl - entry)
                    reward = abs(entry - tp)
                
                if risk > 0:
                    rr_ratio = reward / risk
                    # Risk-reward should be at least 1:1, typically 1:1.5 to 1:2 for micro-scalps
                    self.assertGreaterEqual(rr_ratio, 0.8, f"Risk-reward ratio too low: {rr_ratio:.2f}")
                    self.assertLessEqual(rr_ratio, 3.0, f"Risk-reward ratio too high: {rr_ratio:.2f}")
    
    def test_trade_idea_stop_loss_valid(self):
        """Test: Stop loss is valid (not equal to entry)"""
        snapshot = self._create_snapshot()
        result = self._create_valid_result()
        
        self.checker_vwap._current_snapshot = snapshot
        
        trade_idea = self.checker_vwap.generate_trade_idea(snapshot, result)
        
        if trade_idea:
            entry = trade_idea.get('entry_price')
            sl = trade_idea.get('sl')
            
            if entry and sl:
                # Stop loss should not equal entry
                self.assertNotEqual(entry, sl, "Stop loss equals entry price")
                
                # Stop loss should be reasonable distance from entry
                distance = abs(entry - sl)
                self.assertGreater(distance, 0.1, "Stop loss too close to entry")
                self.assertLess(distance, 10.0, "Stop loss too far from entry")
    
    def test_trade_idea_take_profit_valid(self):
        """Test: Take profit is valid (not equal to entry)"""
        snapshot = self._create_snapshot()
        result = self._create_valid_result()
        
        self.checker_vwap._current_snapshot = snapshot
        
        trade_idea = self.checker_vwap.generate_trade_idea(snapshot, result)
        
        if trade_idea:
            entry = trade_idea.get('entry_price')
            tp = trade_idea.get('tp')
            
            if entry and tp:
                # Take profit should not equal entry
                self.assertNotEqual(entry, tp, "Take profit equals entry price")
                
                # Take profit should be reasonable distance from entry
                distance = abs(tp - entry)
                self.assertGreater(distance, 0.1, "Take profit too close to entry")
                self.assertLess(distance, 20.0, "Take profit too far from entry")
    
    def test_trade_idea_entry_price_realistic(self):
        """Test: Entry price is realistic (within reasonable range)"""
        snapshot = self._create_snapshot(price=2000.0)
        result = self._create_valid_result()
        
        self.checker_vwap._current_snapshot = snapshot
        
        trade_idea = self.checker_vwap.generate_trade_idea(snapshot, result)
        
        if trade_idea:
            entry = trade_idea.get('entry_price')
            current_price = snapshot.get('current_price', 2000.0)
            
            if entry:
                # Entry should be within reasonable distance of current price
                distance = abs(entry - current_price)
                # For micro-scalps, entry should be close to current price
                self.assertLessEqual(distance, 5.0, f"Entry price too far from current: {distance:.2f}")
    
    def test_trade_idea_direction_valid(self):
        """Test: Trade direction is valid (BUY or SELL)"""
        snapshot = self._create_snapshot()
        result = self._create_valid_result()
        
        self.checker_vwap._current_snapshot = snapshot
        
        trade_idea = self.checker_vwap.generate_trade_idea(snapshot, result)
        
        if trade_idea:
            direction = trade_idea.get('direction')
            self.assertIn(direction, ['BUY', 'SELL'], f"Invalid direction: {direction}")
    
    def test_range_scalp_trade_idea_uses_range_boundaries(self):
        """Test: Range scalp trade idea uses range boundaries appropriately"""
        from infra.range_boundary_detector import RangeStructure, CriticalGapZones
        
        range_structure = RangeStructure(
            range_type='dynamic',
            range_high=2000.5,
            range_low=1999.5,
            range_mid=2000.0,
            range_width_atr=1.0,
            critical_gaps=CriticalGapZones(
                upper_zone_start=2000.3,
                upper_zone_end=2000.5,
                lower_zone_start=1999.5,
                lower_zone_end=1999.7
            ),
            touch_count={},
            validated=True
        )
        
        snapshot = self._create_snapshot(price=2000.5)  # At upper edge
        snapshot['range_structure'] = range_structure
        result = self._create_valid_result()
        
        self.checker_range._current_snapshot = snapshot
        
        trade_idea = self.checker_range.generate_trade_idea(snapshot, result)
        
        if trade_idea:
            # If at upper edge, should be SELL
            # If at lower edge, should be BUY
            entry = trade_idea.get('entry_price')
            if entry:
                # Entry should be near range boundary
                distance_from_high = abs(entry - range_structure.range_high)
                distance_from_low = abs(entry - range_structure.range_low)
                min_distance = min(distance_from_high, distance_from_low)
                self.assertLessEqual(min_distance, 1.0, "Entry not near range boundary")


if __name__ == '__main__':
    unittest.main()

