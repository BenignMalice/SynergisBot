# =====================================
# tests/test_phase1_3_integration.py
# =====================================
"""
Tests for Phase 1.3: Integration with Existing Analysis Pipeline
Tests M1 microstructure integration into desktop_agent.py
"""

import unittest
import sys
import os
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timezone

# Add project root to path (adjust for new location in docs folder)
# From: docs/Pending Updates - 19.11.25/Tests - M1_Microstructure/
# To: project root (3 levels up: .. -> .. -> ..)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.m1_data_fetcher import M1DataFetcher
from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer


def generate_mock_candles(count: int, base_price: float = 2400.0, trend: str = 'up') -> list:
    """Generate mock M1 candles for testing"""
    candles = []
    base_time = int(datetime.now(timezone.utc).timestamp()) - (count * 60)
    
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


class MockMT5Service:
    """Mock MT5Service for testing"""
    
    def __init__(self):
        self.connected = True
    
    def get_bars(self, symbol, timeframe, count):
        """Mock get_bars method"""
        if timeframe != 'M1':
            return None
        
        # Generate mock M1 candles
        candles = []
        base_price = 2400.0 if 'XAU' in symbol else 50000.0
        base_time = int(datetime.now(timezone.utc).timestamp()) - (count * 60)
        
        for i in range(count):
            candle = {
                'time': base_time + (i * 60),
                'open': base_price + (i * 0.1),
                'high': base_price + (i * 0.1) + 0.5,
                'low': base_price + (i * 0.1) - 0.5,
                'close': base_price + (i * 0.1) + 0.2,
                'tick_volume': 100 + i,
                'real_volume': 50 + i
            }
            candles.append(candle)
        
        return candles


class TestPhase1_3Integration(unittest.TestCase):
    """Test cases for Phase 1.3 Integration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_mt5 = MockMT5Service()
        self.m1_fetcher = M1DataFetcher(data_source=self.mock_mt5, max_candles=200, cache_ttl=300)
        self.m1_analyzer = M1MicrostructureAnalyzer(mt5_service=self.mock_mt5)
    
    def test_m1_components_initialization(self):
        """Test that M1 components can be initialized"""
        self.assertIsNotNone(self.m1_fetcher)
        self.assertIsNotNone(self.m1_analyzer)
    
    def test_m1_data_fetching_integration(self):
        """Test M1 data fetching works with mock MT5Service"""
        candles = self.m1_fetcher.fetch_m1_data("XAUUSD", count=100)
        
        self.assertIsInstance(candles, list)
        self.assertGreater(len(candles), 0)
        self.assertLessEqual(len(candles), 100)
        
        if candles:
            candle = candles[0]
            self.assertIn('timestamp', candle)
            self.assertIn('open', candle)
            self.assertIn('high', candle)
            self.assertIn('low', candle)
            self.assertIn('close', candle)
            self.assertIn('volume', candle)
            self.assertIn('symbol', candle)
    
    def test_m1_analysis_integration(self):
        """Test M1 microstructure analysis works end-to-end"""
        # Fetch M1 data
        candles = self.m1_fetcher.fetch_m1_data("XAUUSD", count=100)
        
        self.assertGreater(len(candles), 0, "M1 data should be fetched")
        
        # Run analysis
        analysis = self.m1_analyzer.analyze_microstructure(
            symbol="XAUUSD",
            candles=candles,
            current_price=2405.0
        )
        
        self.assertIsNotNone(analysis)
        self.assertTrue(analysis.get('available', False), "Analysis should be available")
        self.assertIn('structure', analysis)
        self.assertIn('choch_bos', analysis)
        self.assertIn('liquidity_zones', analysis)
        self.assertIn('volatility', analysis)
        self.assertIn('momentum', analysis)
        self.assertIn('microstructure_confluence', analysis)
    
    def test_m1_analysis_output_structure(self):
        """Test that M1 analysis output has all required fields"""
        candles = generate_mock_candles(100, base_price=2400.0, trend='up')
        
        analysis = self.m1_analyzer.analyze_microstructure(
            symbol="XAUUSD",
            candles=candles,
            current_price=2405.0
        )
        
        # Check required fields
        required_fields = [
            'available', 'symbol', 'timestamp', 'candle_count',
            'structure', 'choch_bos', 'liquidity_zones', 'liquidity_state',
            'volatility', 'rejection_wicks', 'order_blocks', 'momentum',
            'trend_context', 'signal_summary', 'strategy_hint',
            'microstructure_confluence', 'session_context'
        ]
        
        for field in required_fields:
            self.assertIn(field, analysis, f"Missing required field: {field}")
    
    def test_m1_graceful_fallback(self):
        """Test that M1 analysis gracefully handles insufficient data"""
        import logging
        
        # Suppress warning logs during this test (expected behavior)
        logging.getLogger('infra.m1_microstructure_analyzer').setLevel(logging.ERROR)
        
        # Test with insufficient candles
        insufficient_candles = generate_mock_candles(5)  # Too few
        
        analysis = self.m1_analyzer.analyze_microstructure(
            symbol="XAUUSD",
            candles=insufficient_candles
        )
        
        self.assertFalse(analysis.get('available', True))
        self.assertIn('error', analysis)
        
        # Restore logging level
        logging.getLogger('infra.m1_microstructure_analyzer').setLevel(logging.WARNING)
    
    def test_m1_confluence_scoring(self):
        """Test that M1 confluence scoring works"""
        candles = generate_mock_candles(100, base_price=2400.0, trend='up')
        
        analysis = self.m1_analyzer.analyze_microstructure(
            symbol="XAUUSD",
            candles=candles,
            current_price=2405.0
        )
        
        confluence = analysis.get('microstructure_confluence', {})
        
        self.assertIn('score', confluence)
        self.assertIn('grade', confluence)
        self.assertIn('recommended_action', confluence)
        self.assertIn('components', confluence)
        
        self.assertGreaterEqual(confluence['score'], 0)
        self.assertLessEqual(confluence['score'], 100)
        self.assertIn(confluence['grade'], ['A', 'B', 'C', 'D', 'F'])
    
    def test_m1_strategy_hint_generation(self):
        """Test that strategy hints are generated"""
        candles = generate_mock_candles(100, base_price=2400.0, trend='up')
        
        analysis = self.m1_analyzer.analyze_microstructure(
            symbol="XAUUSD",
            candles=candles,
            current_price=2405.0
        )
        
        strategy_hint = analysis.get('strategy_hint')
        
        self.assertIsNotNone(strategy_hint)
        self.assertIn(strategy_hint, ['RANGE_SCALP', 'BREAKOUT', 'REVERSAL', 'TREND_CONTINUATION'])
    
    def test_m1_data_caching(self):
        """Test that M1 data caching works"""
        # First fetch
        candles1 = self.m1_fetcher.fetch_m1_data("XAUUSD", count=100, use_cache=True)
        
        # Second fetch (should use cache)
        candles2 = self.m1_fetcher.fetch_m1_data("XAUUSD", count=100, use_cache=True)
        
        # Should have same number of candles
        self.assertEqual(len(candles1), len(candles2))
    
    def test_m1_analysis_with_higher_timeframe_data(self):
        """Test M1 analysis with higher timeframe context"""
        candles = generate_mock_candles(100, base_price=2400.0, trend='up')
        
        higher_timeframe_data = {
            'm5': {'trend': 'UP'},
            'h1': {'trend': 'UP'}
        }
        
        analysis = self.m1_analyzer.analyze_microstructure(
            symbol="XAUUSD",
            candles=candles,
            current_price=2405.0,
            higher_timeframe_data=higher_timeframe_data
        )
        
        trend_context = analysis.get('trend_context', {})
        self.assertIn('alignment', trend_context)
        self.assertIn('confidence', trend_context)
        self.assertIn('m1_m5_alignment', trend_context)
        self.assertIn('m1_h1_alignment', trend_context)
    
    def test_m1_signal_age_calculation(self):
        """Test that signal age is calculated correctly"""
        candles = generate_mock_candles(100, base_price=2400.0, trend='up')
        
        analysis = self.m1_analyzer.analyze_microstructure(
            symbol="XAUUSD",
            candles=candles,
            current_price=2405.0
        )
        
        # Check signal age
        if analysis.get('last_signal_timestamp'):
            signal_age = analysis.get('signal_age_seconds', 0)
            self.assertGreaterEqual(signal_age, 0)
            self.assertLess(signal_age, 10)  # Should be very recent
    
    def test_m1_error_handling(self):
        """Test that M1 analysis handles errors gracefully"""
        import logging
        
        # Suppress warning logs during this test (expected behavior)
        logging.getLogger('infra.m1_microstructure_analyzer').setLevel(logging.ERROR)
        
        # Test with empty candles
        analysis = self.m1_analyzer.analyze_microstructure(
            symbol="XAUUSD",
            candles=[],
            current_price=2405.0
        )
        
        self.assertFalse(analysis.get('available', True))
        self.assertIn('error', analysis)
        
        # Test with None candles
        analysis2 = self.m1_analyzer.analyze_microstructure(
            symbol="XAUUSD",
            candles=None,
            current_price=2405.0
        )
        
        # Should handle None gracefully
        self.assertIsNotNone(analysis2)
        
        # Restore logging level
        logging.getLogger('infra.m1_microstructure_analyzer').setLevel(logging.WARNING)


class TestDesktopAgentIntegration(unittest.TestCase):
    """Test M1 integration with desktop_agent (requires mocking)"""
    
    def test_m1_formatting_function_exists(self):
        """Test that _format_m1_microstructure_summary function exists"""
        try:
            import desktop_agent
            self.assertTrue(hasattr(desktop_agent, '_format_m1_microstructure_summary'))
        except ImportError:
            self.skipTest("desktop_agent not available for testing")
    
    def test_m1_formatting_with_valid_data(self):
        """Test M1 formatting with valid analysis data"""
        try:
            from desktop_agent import _format_m1_microstructure_summary
            
            m1_data = {
                'available': True,
                'signal_summary': 'BULLISH_MICROSTRUCTURE',
                'choch_bos': {
                    'has_choch': True,
                    'has_bos': False,
                    'confidence': 85
                },
                'structure': {
                    'type': 'HIGHER_HIGH',
                    'strength': 85
                },
                'volatility': {
                    'state': 'EXPANDING',
                    'change_pct': 25.5
                },
                'liquidity_state': 'NEAR_PDH',
                'liquidity_zones': [
                    {'type': 'PDH', 'price': 2407.5, 'touches': 3}
                ],
                'momentum': {
                    'quality': 'GOOD',
                    'consistency': 75
                },
                'strategy_hint': 'TREND_CONTINUATION',
                'microstructure_confluence': {
                    'score': 82.5,
                    'grade': 'A',
                    'recommended_action': 'BUY_CONFIRMED'
                },
                'session_context': {
                    'session': 'LONDON',
                    'volatility_tier': 'HIGH'
                },
                'dynamic_threshold': 70.5,
                'threshold_calculation': {
                    'base_confidence': 70,
                    'atr_ratio': 1.2
                }
            }
            
            formatted = _format_m1_microstructure_summary(m1_data)
            
            self.assertIsInstance(formatted, str)
            self.assertGreater(len(formatted), 0)
            self.assertIn('Signal:', formatted)
            self.assertIn('CHOCH', formatted)
            self.assertIn('Structure:', formatted)
            self.assertIn('Volatility:', formatted)
            self.assertIn('Confluence:', formatted)
            
        except ImportError:
            self.skipTest("desktop_agent not available for testing")
    
    def test_m1_formatting_with_unavailable_data(self):
        """Test M1 formatting with unavailable data"""
        try:
            from desktop_agent import _format_m1_microstructure_summary
            
            m1_data = {
                'available': False,
                'error': 'Insufficient candles'
            }
            
            formatted = _format_m1_microstructure_summary(m1_data)
            
            self.assertIsInstance(formatted, str)
            self.assertIn('unavailable', formatted.lower())
            
        except ImportError:
            self.skipTest("desktop_agent not available for testing")
    
    def test_m1_formatting_with_none(self):
        """Test M1 formatting with None input"""
        try:
            from desktop_agent import _format_m1_microstructure_summary
            
            formatted = _format_m1_microstructure_summary(None)
            
            self.assertIsInstance(formatted, str)
            self.assertIn('unavailable', formatted.lower())
            
        except ImportError:
            self.skipTest("desktop_agent not available for testing")


if __name__ == '__main__':
    unittest.main()

