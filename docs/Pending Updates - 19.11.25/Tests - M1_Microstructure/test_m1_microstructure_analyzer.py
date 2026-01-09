# =====================================
# tests/test_m1_microstructure_analyzer.py
# =====================================
"""
Tests for M1 Microstructure Analyzer Module (Phase 1.2)
"""

import unittest
import time
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock
import sys
import os

# Add project root to path (adjust for new location in docs folder)
# From: docs/Pending Updates - 19.11.25/Tests - M1_Microstructure/
# To: project root (3 levels up: .. -> .. -> ..)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer


def generate_mock_candles(count: int, base_price: float = 2400.0, trend: str = 'up') -> list:
    """Generate mock M1 candles for testing"""
    candles = []
    base_time = int(time.time()) - (count * 60)
    
    for i in range(count):
        if trend == 'up':
            open_price = base_price + (i * 0.5)
            close_price = base_price + (i * 0.5) + 0.3
            high_price = base_price + (i * 0.5) + 0.8
            low_price = base_price + (i * 0.5) - 0.2
        elif trend == 'down':
            open_price = base_price - (i * 0.5)
            close_price = base_price - (i * 0.5) - 0.3
            high_price = base_price - (i * 0.5) + 0.2
            low_price = base_price - (i * 0.5) - 0.8
        else:  # choppy
            open_price = base_price + (i * 0.1 * (-1 if i % 2 == 0 else 1))
            close_price = open_price + (0.2 * (-1 if i % 2 == 0 else 1))
            high_price = max(open_price, close_price) + 0.3
            low_price = min(open_price, close_price) - 0.3
        
        candle = {
            'timestamp': datetime.fromtimestamp(base_time + (i * 60), tz=timezone.utc),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': 100 + (i * 2),
            'symbol': 'XAUUSDc'
        }
        candles.append(candle)
    
    return candles


class TestM1MicrostructureAnalyzer(unittest.TestCase):
    """Test cases for M1MicrostructureAnalyzer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = M1MicrostructureAnalyzer()
    
    def test_initialization(self):
        """Test M1MicrostructureAnalyzer initialization"""
        self.assertIsNotNone(self.analyzer)
        self.assertIsNotNone(self.analyzer.logger)
    
    def test_analyze_microstructure_basic(self):
        """Test basic microstructure analysis"""
        candles = generate_mock_candles(100, base_price=2400.0, trend='up')
        
        analysis = self.analyzer.analyze_microstructure(
            symbol="XAUUSD",
            candles=candles,
            current_price=2405.0
        )
        
        self.assertIsNotNone(analysis)
        self.assertTrue(analysis.get('available', False))
        self.assertEqual(analysis.get('symbol'), 'XAUUSD')
        self.assertIn('structure', analysis)
        self.assertIn('choch_bos', analysis)
        self.assertIn('liquidity_zones', analysis)
        self.assertIn('volatility', analysis)
        self.assertIn('momentum', analysis)
    
    def test_analyze_microstructure_insufficient_candles(self):
        """Test analysis with insufficient candles"""
        candles = generate_mock_candles(5)  # Too few candles
        
        analysis = self.analyzer.analyze_microstructure(
            symbol="XAUUSD",
            candles=candles
        )
        
        self.assertFalse(analysis.get('available', True))
        self.assertIn('error', analysis)
    
    def test_analyze_structure(self):
        """Test structure analysis"""
        # Uptrend candles
        candles_up = generate_mock_candles(50, base_price=2400.0, trend='up')
        structure_up = self.analyzer.analyze_structure(candles_up, "XAUUSD")
        
        self.assertIn('type', structure_up)
        self.assertIn('consecutive_count', structure_up)
        self.assertIn('strength', structure_up)
        self.assertIsInstance(structure_up['strength'], (int, float))
        
        # Downtrend candles
        candles_down = generate_mock_candles(50, base_price=2400.0, trend='down')
        structure_down = self.analyzer.analyze_structure(candles_down, "XAUUSD")
        
        self.assertIn('type', structure_down)
    
    def test_detect_choch_bos(self):
        """Test CHOCH/BOS detection"""
        candles = generate_mock_candles(100, base_price=2400.0, trend='up')
        
        choch_bos = self.analyzer.detect_choch_bos(candles, require_confirmation=True, symbol="XAUUSD")
        
        self.assertIn('has_choch', choch_bos)
        self.assertIn('has_bos', choch_bos)
        self.assertIn('choch_confirmed', choch_bos)
        self.assertIn('confidence', choch_bos)
        self.assertIn('last_swing_high', choch_bos)
        self.assertIn('last_swing_low', choch_bos)
        self.assertIsInstance(choch_bos['has_choch'], bool)
        self.assertIsInstance(choch_bos['has_bos'], bool)
        self.assertGreaterEqual(choch_bos['confidence'], 0)
        self.assertLessEqual(choch_bos['confidence'], 100)
    
    def test_identify_liquidity_zones(self):
        """Test liquidity zones identification"""
        candles = generate_mock_candles(100, base_price=2400.0, trend='up')
        
        zones = self.analyzer.identify_liquidity_zones(candles, "XAUUSD")
        
        self.assertIsInstance(zones, list)
        
        # Check zone structure if zones found
        if zones:
            zone = zones[0]
            self.assertIn('type', zone)
            self.assertIn('price', zone)
            self.assertIn('touches', zone)
            self.assertIn(zone['type'], ['PDH', 'PDL', 'EQUAL_HIGH', 'EQUAL_LOW'])
    
    def test_calculate_liquidity_state(self):
        """Test liquidity state calculation"""
        candles = generate_mock_candles(100, base_price=2400.0, trend='up')
        current_price = 2405.0
        
        state = self.analyzer.calculate_liquidity_state(candles, current_price, "XAUUSD")
        
        self.assertIn(state, ['NEAR_PDH', 'NEAR_PDL', 'BETWEEN', 'AWAY'])
    
    def test_calculate_volatility_state(self):
        """Test volatility state calculation"""
        candles = generate_mock_candles(100, base_price=2400.0, trend='up')
        
        volatility = self.analyzer.calculate_volatility_state(candles, "XAUUSD")
        
        self.assertIn('state', volatility)
        self.assertIn('change_pct', volatility)
        self.assertIn('atr', volatility)
        self.assertIn('atr_median', volatility)
        self.assertIn('squeeze_duration', volatility)
        self.assertIn(volatility['state'], ['CONTRACTING', 'EXPANDING', 'STABLE'])
        self.assertIsInstance(volatility['change_pct'], (int, float))
    
    def test_detect_rejection_wicks(self):
        """Test rejection wicks detection"""
        # Create candles with rejection wicks
        candles = generate_mock_candles(50, base_price=2400.0, trend='up')
        
        # Modify last candle to have upper rejection wick
        if candles:
            last_candle = candles[-1]
            last_candle['high'] = last_candle['close'] + 2.0  # Large upper wick
            last_candle['low'] = last_candle['close'] - 0.1
            last_candle['open'] = last_candle['close'] - 0.1
        
        rejections = self.analyzer.detect_rejection_wicks(candles, "XAUUSD")
        
        self.assertIsInstance(rejections, list)
        
        # Check rejection structure if rejections found
        if rejections:
            rejection = rejections[0]
            self.assertIn('type', rejection)
            self.assertIn('price', rejection)
            self.assertIn('wick_ratio', rejection)
            self.assertIn('body_ratio', rejection)
            self.assertIn(rejection['type'], ['UPPER', 'LOWER'])
    
    def test_find_order_blocks(self):
        """Test order blocks identification"""
        candles = generate_mock_candles(100, base_price=2400.0, trend='up')
        
        order_blocks = self.analyzer.find_order_blocks(candles, "XAUUSD")
        
        self.assertIsInstance(order_blocks, list)
        
        # Check order block structure if blocks found
        if order_blocks:
            block = order_blocks[0]
            self.assertIn('type', block)
            self.assertIn('price_range', block)
            self.assertIn('strength', block)
            self.assertIn(block['type'], ['BULLISH', 'BEARISH'])
            self.assertIsInstance(block['price_range'], list)
            self.assertEqual(len(block['price_range']), 2)
    
    def test_calculate_momentum_quality(self):
        """Test momentum quality calculation"""
        candles = generate_mock_candles(50, base_price=2400.0, trend='up')
        
        momentum = self.analyzer.calculate_momentum_quality(candles, include_rsi=True, symbol="XAUUSD")
        
        self.assertIn('quality', momentum)
        self.assertIn('consistency', momentum)
        self.assertIn('consecutive_moves', momentum)
        self.assertIn('rsi_validation', momentum)
        self.assertIn('rsi_value', momentum)
        self.assertIn(momentum['quality'], ['EXCELLENT', 'GOOD', 'FAIR', 'CHOPPY'])
        self.assertGreaterEqual(momentum['consistency'], 0)
        self.assertLessEqual(momentum['consistency'], 100)
    
    def test_generate_signal_summary(self):
        """Test signal summary generation"""
        candles = generate_mock_candles(100, base_price=2400.0, trend='up')
        
        # Create mock analysis
        analysis = {
            'choch_bos': {'has_choch': True, 'has_bos': True, 'choch_confirmed': True, 'confidence': 85},
            'structure': {'type': 'HIGHER_HIGH', 'consecutive_count': 3, 'strength': 85}
        }
        
        signal = self.analyzer.generate_signal_summary(analysis, "XAUUSD")
        
        self.assertIn(signal, ['BULLISH_MICROSTRUCTURE', 'BEARISH_MICROSTRUCTURE', 'NEUTRAL'])
    
    def test_calculate_signal_age(self):
        """Test signal age calculation"""
        # Recent timestamp
        recent_ts = datetime.now(timezone.utc).isoformat()
        age_recent = self.analyzer.calculate_signal_age(recent_ts)
        
        self.assertGreaterEqual(age_recent, 0)
        self.assertLess(age_recent, 10)  # Should be very recent
        
        # Old timestamp
        old_ts = datetime.now(timezone.utc).replace(year=2020).isoformat()
        age_old = self.analyzer.calculate_signal_age(old_ts)
        
        self.assertGreater(age_old, 0)
    
    def test_is_signal_stale(self):
        """Test signal staleness check"""
        # Recent signal
        recent_ts = datetime.now(timezone.utc).isoformat()
        is_stale_recent = self.analyzer.is_signal_stale(recent_ts, max_age_seconds=300)
        self.assertFalse(is_stale_recent)
        
        # Old signal
        old_ts = datetime.now(timezone.utc).replace(year=2020).isoformat()
        is_stale_old = self.analyzer.is_signal_stale(old_ts, max_age_seconds=300)
        self.assertTrue(is_stale_old)
    
    def test_generate_strategy_hint(self):
        """Test strategy hint generation"""
        analysis = {
            'volatility': {'state': 'CONTRACTING', 'squeeze_duration': 25},
            'structure': {'type': 'CHOPPY'},
            'momentum': {'quality': 'CHOPPY'},
            'trend_context': {'alignment': 'STRONG'}
        }
        
        hint = self.analyzer.generate_strategy_hint(analysis)
        
        self.assertIn(hint, ['RANGE_SCALP', 'BREAKOUT', 'REVERSAL', 'TREND_CONTINUATION'])
    
    def test_calculate_microstructure_confluence(self):
        """Test microstructure confluence calculation"""
        candles = generate_mock_candles(100, base_price=2400.0, trend='up')
        
        # Create complete analysis
        analysis = {
            'choch_bos': {'has_choch': True, 'confidence': 85},
            'session_context': {'volatility_tier': 'NORMAL'},
            'momentum': {'quality': 'GOOD'},
            'liquidity_state': 'BETWEEN',
            'strategy_hint': 'TREND_CONTINUATION',
            'trend_context': {'alignment': 'MODERATE'}
        }
        
        confluence = self.analyzer.calculate_microstructure_confluence(analysis, session='LONDON', symbol="XAUUSD")
        
        self.assertIn('score', confluence)
        self.assertIn('base_score', confluence)
        self.assertIn('grade', confluence)
        self.assertIn('recommended_action', confluence)
        self.assertIn('components', confluence)
        
        self.assertGreaterEqual(confluence['score'], 0)
        self.assertLessEqual(confluence['score'], 100)
        self.assertIn(confluence['grade'], ['A', 'B', 'C', 'D', 'F'])
        self.assertIn(confluence['recommended_action'], ['BUY_CONFIRMED', 'SELL_CONFIRMED', 'WAIT', 'AVOID'])
    
    def test_trend_context(self):
        """Test trend context calculation"""
        candles = generate_mock_candles(50, base_price=2400.0, trend='up')
        
        higher_timeframe_data = {
            'm5': {'trend': 'UP'},
            'h1': {'trend': 'UP'}
        }
        
        trend_context = self.analyzer.trend_context(candles, higher_timeframe_data, include_m15=False, symbol="XAUUSD")
        
        self.assertIn('alignment', trend_context)
        self.assertIn('confidence', trend_context)
        self.assertIn('m1_m5_alignment', trend_context)
        self.assertIn('m1_h1_alignment', trend_context)
        self.assertIn(trend_context['alignment'], ['STRONG', 'MODERATE', 'WEAK', 'UNKNOWN'])
        self.assertGreaterEqual(trend_context['confidence'], 0)
        self.assertLessEqual(trend_context['confidence'], 100)
    
    def test_helper_methods(self):
        """Test helper methods"""
        candles = generate_mock_candles(50, base_price=2400.0, trend='up')
        
        # Test ATR calculation
        atr = self.analyzer._calculate_atr(candles, period=14)
        self.assertGreaterEqual(atr, 0)
        
        # Test RSI calculation
        rsi = self.analyzer._calculate_rsi(candles, period=14)
        self.assertGreaterEqual(rsi, 0)
        self.assertLessEqual(rsi, 100)
        
        # Test VWAP calculation
        vwap = self.analyzer._calculate_vwap(candles)
        self.assertGreater(vwap, 0)
    
    def test_get_vwap_state(self):
        """Test VWAP state calculation"""
        candles = generate_mock_candles(50, base_price=2400.0, trend='up')
        
        vwap_state = self.analyzer._get_vwap_state("XAUUSD", candles)
        
        self.assertIn(vwap_state, ['NEUTRAL', 'STRETCHED', 'ALIGNED', 'REVERSION'])
    
    def test_complete_analysis_workflow(self):
        """Test complete analysis workflow"""
        candles = generate_mock_candles(100, base_price=2400.0, trend='up')
        
        analysis = self.analyzer.analyze_microstructure(
            symbol="XAUUSD",
            candles=candles,
            current_price=2405.0
        )
        
        # Verify all required fields are present
        required_fields = [
            'available', 'symbol', 'timestamp', 'candle_count',
            'structure', 'choch_bos', 'liquidity_zones', 'liquidity_state',
            'volatility', 'rejection_wicks', 'order_blocks', 'momentum',
            'trend_context', 'signal_summary', 'strategy_hint',
            'microstructure_confluence', 'session_context'
        ]
        
        for field in required_fields:
            self.assertIn(field, analysis, f"Missing field: {field}")
        
        # Verify signal age is calculated
        if analysis.get('last_signal_timestamp'):
            self.assertIn('signal_age_seconds', analysis)
            self.assertGreaterEqual(analysis['signal_age_seconds'], 0)


if __name__ == '__main__':
    unittest.main()

