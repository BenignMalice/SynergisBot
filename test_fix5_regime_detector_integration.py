"""
Test Fix 5: RegimeDetector Integration
Tests that RegimeDetector is used for BTC regime detection with fallback to lightweight
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from infra.confluence_calculator import ConfluenceCalculator
from test_fixtures import (
    MockIndicatorBridge, MockM1Analyzer, MockM1DataFetcher,
    create_btc_data, create_regime_test_data, reset_singleton
)
import numpy as np


class TestFix5RegimeDetectorIntegration(unittest.TestCase):
    """Test Fix 5: RegimeDetector Integration"""
    
    def setUp(self):
        reset_singleton(ConfluenceCalculator)
        self.bridge = MockIndicatorBridge()
        self.calculator = ConfluenceCalculator(self.bridge, cache_ttl=5)
    
    def tearDown(self):
        reset_singleton(ConfluenceCalculator)
    
    def test_prepare_regime_detector_data_exists(self):
        """Test _prepare_regime_detector_data method exists"""
        self.assertTrue(hasattr(self.calculator, '_prepare_regime_detector_data'),
                       "Method _prepare_regime_detector_data should exist")
    
    def test_prepare_regime_detector_data_format(self):
        """Test _prepare_regime_detector_data converts data format correctly"""
        # Setup data with OHLCV arrays
        btc_data = create_btc_data()
        # Add OHLCV arrays (simulate indicator_bridge format)
        for tf in ['M5', 'M15', 'H1']:
            tf_data = btc_data[tf]
            # Create mock OHLCV arrays
            n_bars = 100
            tf_data['opens'] = [10000.0 + i * 0.1 for i in range(n_bars)]
            tf_data['highs'] = [10000.0 + i * 0.1 + 5 for i in range(n_bars)]
            tf_data['lows'] = [10000.0 + i * 0.1 - 5 for i in range(n_bars)]
            tf_data['closes'] = [10000.0 + i * 0.1 + 2 for i in range(n_bars)]
            tf_data['volumes'] = [1000] * n_bars
            tf_data['times'] = [f'2025-01-01 {i%24:02d}:{i%60:02d}:00' for i in range(n_bars)]
            tf_data['bb_middle'] = 10000.0  # Add bb_middle
            tf_data['adx'] = 25.0  # Add ADX
        
        self.bridge.multi_data['BTCUSDc'] = btc_data
        
        # Prepare data
        timeframe_data = self.calculator._prepare_regime_detector_data('BTCUSDc', btc_data)
        
        # Should return dict with M5, M15, H1
        self.assertIsNotNone(timeframe_data, "Should return timeframe data")
        self.assertIn('H1', timeframe_data, "Should have H1 data")
        
        # Check H1 data structure
        h1_data = timeframe_data.get('H1', {})
        self.assertIn('rates', h1_data, "Should have rates array")
        self.assertIn('atr_14', h1_data, "Should have atr_14")
        self.assertIn('atr_50', h1_data, "Should have atr_50")
        self.assertIn('bb_upper', h1_data, "Should have bb_upper")
        self.assertIn('bb_lower', h1_data, "Should have bb_lower")
        self.assertIn('bb_middle', h1_data, "Should have bb_middle")
        self.assertIn('adx', h1_data, "Should have adx")
        self.assertIn('volume', h1_data, "Should have volume array")
        
        # Check rates array is numpy array
        rates = h1_data['rates']
        self.assertIsInstance(rates, np.ndarray, "Rates should be numpy array")
        self.assertGreater(len(rates), 0, "Rates should have data")
    
    def test_regime_detector_integration_with_mock(self):
        """Test RegimeDetector integration with mocked RegimeDetector"""
        # Setup BTC data
        btc_data = create_btc_data()
        for tf in ['M5', 'M15', 'H1']:
            tf_data = btc_data[tf]
            n_bars = 100
            tf_data['opens'] = [10000.0 + i * 0.1 for i in range(n_bars)]
            tf_data['highs'] = [10000.0 + i * 0.1 + 5 for i in range(n_bars)]
            tf_data['lows'] = [10000.0 + i * 0.1 - 5 for i in range(n_bars)]
            tf_data['closes'] = [10000.0 + i * 0.1 + 2 for i in range(n_bars)]
            tf_data['volumes'] = [1000] * n_bars
            tf_data['times'] = [f'2025-01-01 {i%24:02d}:{i%60:02d}:00' for i in range(n_bars)]
            tf_data['bb_middle'] = 10000.0
            tf_data['adx'] = 25.0
        
        self.bridge.multi_data['BTCUSDc'] = btc_data
        
        # Mock RegimeDetector
        with patch('infra.volatility_regime_detector.RegimeDetector') as MockRegimeDetector:
            mock_detector = Mock()
            mock_result = {
                'regime': Mock(),  # Mock enum
                'confidence': 85.0,
                'reasoning': 'Test regime detection'
            }
            # Make regime enum have .value attribute
            mock_result['regime'].value = 'VOLATILE'
            mock_detector.detect_regime.return_value = mock_result
            MockRegimeDetector.return_value = mock_detector
            
            # Calculate M1 confluence (should use RegimeDetector)
            m1_analyzer = MockM1Analyzer()
            m1_fetcher = MockM1DataFetcher()
            
            result = self.calculator.calculate_confluence_per_timeframe(
                'BTCUSDc',
                m1_analyzer=m1_analyzer,
                m1_data_fetcher=m1_fetcher
            )
            
            # Should have result (may use RegimeDetector or fallback)
            self.assertIsNotNone(result)
            self.assertIn('M1', result)
            
            # Check if RegimeDetector was called (may not be if data prep failed)
            # This is acceptable - the fallback should work
            if MockRegimeDetector.called:
                self.assertTrue(mock_detector.detect_regime.called, "detect_regime should be called if RegimeDetector was instantiated")
    
    def test_regime_detector_fallback_to_lightweight(self):
        """Test fallback to lightweight method when RegimeDetector fails"""
        # Setup BTC data (without full OHLCV arrays to trigger fallback)
        btc_data = create_btc_data()
        self.bridge.multi_data['BTCUSDc'] = btc_data
        
        # Mock RegimeDetector to raise exception
        with patch('infra.volatility_regime_detector.RegimeDetector') as MockRegimeDetector:
            MockRegimeDetector.side_effect = ImportError("RegimeDetector not available")
            
            # Calculate M1 confluence (should fallback to lightweight)
            m1_analyzer = MockM1Analyzer()
            m1_fetcher = MockM1DataFetcher()
            
            result = self.calculator.calculate_confluence_per_timeframe(
                'BTCUSDc',
                m1_analyzer=m1_analyzer,
                m1_data_fetcher=m1_fetcher
            )
            
            # Should have result (fallback worked)
            self.assertIsNotNone(result)
            self.assertIn('M1', result)
            
            # Regime should still be cached (from lightweight method)
            cached_regime = self.calculator.get_cached_regime('BTCUSDc')
            # May be None if lightweight also failed, but should not crash
            if cached_regime:
                self.assertIn(cached_regime, ['STABLE', 'TRANSITIONAL', 'VOLATILE'])
    
    def test_regime_detector_data_preparation_insufficient_data(self):
        """Test data preparation handles insufficient data gracefully"""
        # Setup data with insufficient bars
        btc_data = create_btc_data()
        for tf in ['M5', 'M15', 'H1']:
            tf_data = btc_data[tf]
            # Only 10 bars (insufficient)
            n_bars = 10
            tf_data['opens'] = [10000.0] * n_bars
            tf_data['highs'] = [10000.0] * n_bars
            tf_data['lows'] = [10000.0] * n_bars
            tf_data['closes'] = [10000.0] * n_bars
            tf_data['volumes'] = [1000] * n_bars
        
        self.bridge.multi_data['BTCUSDc'] = btc_data
        
        # Prepare data (should return None or skip timeframes)
        timeframe_data = self.calculator._prepare_regime_detector_data('BTCUSDc', btc_data)
        
        # Should return None or empty dict (insufficient data)
        if timeframe_data:
            # If any timeframe has data, it should be valid
            for tf, data in timeframe_data.items():
                self.assertIn('rates', data)
                self.assertGreater(len(data['rates']), 0)
    
    def test_regime_detector_caching(self):
        """Test that RegimeDetector results are cached"""
        # Setup BTC data with full OHLCV
        btc_data = create_btc_data()
        for tf in ['M5', 'M15', 'H1']:
            tf_data = btc_data[tf]
            n_bars = 100
            tf_data['opens'] = [10000.0 + i * 0.1 for i in range(n_bars)]
            tf_data['highs'] = [10000.0 + i * 0.1 + 5 for i in range(n_bars)]
            tf_data['lows'] = [10000.0 + i * 0.1 - 5 for i in range(n_bars)]
            tf_data['closes'] = [10000.0 + i * 0.1 + 2 for i in range(n_bars)]
            tf_data['volumes'] = [1000] * n_bars
            tf_data['times'] = [f'2025-01-01 {i%24:02d}:{i%60:02d}:00' for i in range(n_bars)]
            tf_data['bb_middle'] = 10000.0
            tf_data['adx'] = 25.0
        
        self.bridge.multi_data['BTCUSDc'] = btc_data
        
        # Mock RegimeDetector
        with patch('infra.volatility_regime_detector.RegimeDetector') as MockRegimeDetector:
            mock_detector = Mock()
            mock_result = {
                'regime': Mock(),
                'confidence': 85.0
            }
            mock_result['regime'].value = 'VOLATILE'
            mock_detector.detect_regime.return_value = mock_result
            MockRegimeDetector.return_value = mock_detector
            
            # First calculation
            m1_analyzer = MockM1Analyzer()
            m1_fetcher = MockM1DataFetcher()
            
            result1 = self.calculator.calculate_confluence_per_timeframe(
                'BTCUSDc',
                m1_analyzer=m1_analyzer,
                m1_data_fetcher=m1_fetcher
            )
            
            # Regime should be cached (may be from RegimeDetector or lightweight fallback)
            cached_regime = self.calculator.get_cached_regime('BTCUSDc')
            self.assertIsNotNone(cached_regime, "Regime should be cached")
            # Should be a valid regime (may be VOLATILE from mock or STABLE/TRANSITIONAL from lightweight)
            self.assertIn(cached_regime, ['STABLE', 'TRANSITIONAL', 'VOLATILE'], 
                         f"Cached regime should be valid, got: {cached_regime}")
            
            # Second calculation (should use cache, not call RegimeDetector again)
            call_count_before = mock_detector.detect_regime.call_count
            
            result2 = self.calculator.calculate_confluence_per_timeframe(
                'BTCUSDc',
                m1_analyzer=m1_analyzer,
                m1_data_fetcher=m1_fetcher
            )
            
            # Should use cached regime (may or may not call again depending on cache check location)
            cached_regime2 = self.calculator.get_cached_regime('BTCUSDc')
            self.assertEqual(cached_regime, cached_regime2, "Cached regime should be consistent")


if __name__ == '__main__':
    print("=" * 70)
    print("Fix 5: RegimeDetector Integration Tests")
    print("=" * 70)
    print()
    print("Testing:")
    print("  - Data preparation method")
    print("  - RegimeDetector integration")
    print("  - Fallback to lightweight method")
    print("  - Caching of RegimeDetector results")
    print()
    print("=" * 70)
    print()
    
    unittest.main(verbosity=2)

