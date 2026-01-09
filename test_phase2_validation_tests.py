"""
Phase 2: Validation Tests
Tests edge cases, boundary conditions, and data validation
"""
import unittest
from unittest.mock import Mock
from infra.confluence_calculator import ConfluenceCalculator
from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
from test_fixtures import (
    MockIndicatorBridge, MockM1Analyzer, MockM1DataFetcher,
    create_btc_data, create_xau_data, create_invalid_data,
    create_regime_test_data, reset_singleton
)


class TestDataValidation(unittest.TestCase):
    """Test data validation and edge cases"""
    
    def setUp(self):
        reset_singleton(ConfluenceCalculator)
        self.bridge = MockIndicatorBridge()
        self.calculator = ConfluenceCalculator(self.bridge, cache_ttl=5)
    
    def tearDown(self):
        reset_singleton(ConfluenceCalculator)
    
    def test_missing_timeframe_data(self):
        """Test handling of missing timeframe data"""
        # Create data with missing timeframes
        self.bridge.multi_data['TEST'] = {
            'M5': {},  # Empty
            # M15 missing
            'H1': {'atr14': 100.0, 'current_close': 10000.0}
        }
        
        result = self.calculator.calculate_confluence_per_timeframe('TEST')
        
        # M5 should be unavailable
        self.assertFalse(result['M5']['available'])
        
        # M15 should be unavailable
        self.assertFalse(result['M15']['available'])
        
        # H1 should be available (has data)
        if result['H1'].get('available'):
            self.assertGreaterEqual(result['H1']['score'], 0)
    
    def test_invalid_atr_values(self):
        """Test handling of invalid ATR values"""
        # Negative ATR
        data1 = create_btc_data()
        data1['H1']['atr14'] = -10.0
        self.bridge.multi_data['TEST1'] = data1
        
        result1 = self.calculator.calculate_confluence_per_timeframe('TEST1')
        # Should handle gracefully
        self.assertIsNotNone(result1)
        
        # Zero ATR
        data2 = create_btc_data()
        data2['H1']['atr14'] = 0.0
        self.bridge.multi_data['TEST2'] = data2
        
        result2 = self.calculator.calculate_confluence_per_timeframe('TEST2')
        # Should handle gracefully
        self.assertIsNotNone(result2)
        
        # None ATR
        data3 = create_btc_data()
        data3['H1']['atr14'] = None
        self.bridge.multi_data['TEST3'] = data3
        
        result3 = self.calculator.calculate_confluence_per_timeframe('TEST3')
        # Should handle gracefully
        self.assertIsNotNone(result3)
    
    def test_invalid_price_values(self):
        """Test handling of invalid price values"""
        # Zero price
        data = create_btc_data()
        data['H1']['current_close'] = 0.0
        self.bridge.multi_data['TEST'] = data
        
        result = self.calculator.calculate_confluence_per_timeframe('TEST')
        # Should handle gracefully
        self.assertIsNotNone(result)
        
        # Negative price
        data['H1']['current_close'] = -100.0
        self.bridge.multi_data['TEST2'] = data
        
        result2 = self.calculator.calculate_confluence_per_timeframe('TEST2')
        # Should handle gracefully
        self.assertIsNotNone(result2)
    
    def test_empty_symbol(self):
        """Test handling of empty symbol"""
        result = self.calculator.calculate_confluence_per_timeframe('')
        # Should return empty result
        self.assertIsNotNone(result)
        self.assertIn('M1', result)
    
    def test_none_symbol(self):
        """Test handling of None symbol"""
        result = self.calculator.calculate_confluence_per_timeframe(None)
        # Should return empty result
        self.assertIsNotNone(result)
        self.assertIn('M1', result)
    
    def test_very_large_values(self):
        """Test handling of very large values"""
        data = create_btc_data()
        data['H1']['atr14'] = 1e10  # Very large
        data['H1']['current_close'] = 1e10
        self.bridge.multi_data['TEST'] = data
        
        result = self.calculator.calculate_confluence_per_timeframe('TEST')
        # Should handle gracefully (may clamp scores)
        self.assertIsNotNone(result)
        if result['H1']['available']:
            self.assertLessEqual(result['H1']['score'], 100)


class TestBoundaryConditions(unittest.TestCase):
    """Test boundary conditions"""
    
    def setUp(self):
        reset_singleton(ConfluenceCalculator)
        self.bridge = MockIndicatorBridge()
        self.calculator = ConfluenceCalculator(self.bridge, cache_ttl=5)
    
    def tearDown(self):
        reset_singleton(ConfluenceCalculator)
    
    def test_atr_percent_boundaries(self):
        """Test ATR% boundary conditions"""
        # Test XAU boundaries
        test_cases_xau = [
            (0.3, 60),   # low_min
            (0.4, 100),  # optimal_low
            (1.5, 100),  # optimal_high
            (2.0, 70),   # high_max
        ]
        
        for atr_percent, expected_min in test_cases_xau:
            tf_data = {
                'atr14': 2000.0 * (atr_percent / 100.0),
                'current_close': 2000.0
            }
            score = self.calculator._calculate_volatility_health_for_timeframe(
                tf_data, symbol='XAUUSDc'
            )
            self.assertGreaterEqual(
                score, expected_min - 10,
                f"XAU ATR% {atr_percent}% should score >= {expected_min - 10}"
            )
        
        # Test BTC boundaries
        test_cases_btc = [
            (0.8, 60),   # low_min
            (1.0, 100),  # optimal_low
            (4.0, 100),  # optimal_high
            (5.0, 70),   # high_max
        ]
        
        for atr_percent, expected_min in test_cases_btc:
            tf_data = {
                'atr14': 100000.0 * (atr_percent / 100.0),
                'current_close': 100000.0
            }
            score = self.calculator._calculate_volatility_health_for_timeframe(
                tf_data, symbol='BTCUSDc'
            )
            self.assertGreaterEqual(
                score, expected_min - 10,
                f"BTC ATR% {atr_percent}% should score >= {expected_min - 10}"
            )
    
    def test_score_boundaries(self):
        """Test score boundaries (0-100)"""
        # Create data that would produce extreme scores
        extreme_data = {
            'M5': {
                'atr14': 50.0,
                'current_close': 10000.0,
                'ema20': 10000.0,
                'ema50': 10000.0,
                'ema200': 10000.0,
                'rsi': 0,  # Extreme
                'macd': -1000,  # Extreme
                'macd_signal': 0,
                'bb_upper': 10000.0,
                'bb_lower': 10000.0
            }
        }
        self.bridge.multi_data['TEST'] = extreme_data
        
        result = self.calculator.calculate_confluence_per_timeframe('TEST')
        
        # All scores should be in valid range
        for tf in ['M5', 'M15', 'H1']:
            if result[tf].get('available'):
                score = result[tf]['score']
                self.assertGreaterEqual(score, 0, f"{tf} score should be >= 0")
                self.assertLessEqual(score, 100, f"{tf} score should be <= 100")
                
                # Factor scores should also be in range
                for factor_name, factor_score in result[tf]['factors'].items():
                    self.assertGreaterEqual(
                        factor_score, 0,
                        f"{tf} {factor_name} should be >= 0"
                    )
                    self.assertLessEqual(
                        factor_score, 100,
                        f"{tf} {factor_name} should be <= 100"
                    )


class TestRegimeValidation(unittest.TestCase):
    """Test regime validation edge cases"""
    
    def setUp(self):
        self.analyzer = M1MicrostructureAnalyzer()
        self.analysis = {
            'available': True,
            'choch_bos': {'confidence': 75},
            'session_context': {'volatility_tier': 'NORMAL'},
            'momentum': {'quality': 'STRONG'},
            'liquidity': {'proximity_score': 80},
            'strategy_fit': 70
        }
    
    def test_regime_case_variations(self):
        """Test regime string case variations"""
        cases = ['STABLE', 'stable', 'Stable', 'sTaBlE']
        
        for regime in cases:
            result = self.analyzer.calculate_microstructure_confluence(
                analysis=self.analysis,
                symbol='BTCUSDc',
                volatility_regime=regime
            )
            # Should all map to same value (80 for STABLE)
            self.assertEqual(
                result['components']['session_volatility_suitability'], 80,
                f"Regime '{regime}' should map to 80"
            )
    
    def test_regime_with_whitespace(self):
        """Test regime string with whitespace"""
        result = self.analyzer.calculate_microstructure_confluence(
            analysis=self.analysis,
            symbol='BTCUSDc',
            volatility_regime='  STABLE  '  # With whitespace
        )
        # Should handle whitespace (may fail validation, fall back to session)
        self.assertIsNotNone(result)
    
    def test_regime_numeric_value(self):
        """Test regime with numeric value"""
        result = self.analyzer.calculate_microstructure_confluence(
            analysis=self.analysis,
            symbol='BTCUSDc',
            volatility_regime=123  # Numeric
        )
        # Should fall back to session-based
        self.assertIsNotNone(result)
        self.assertEqual(result['components']['session_volatility_suitability'], 80)
    
    def test_regime_dict_value(self):
        """Test regime with dict value"""
        result = self.analyzer.calculate_microstructure_confluence(
            analysis=self.analysis,
            symbol='BTCUSDc',
            volatility_regime={'regime': 'STABLE'}  # Dict
        )
        # Should fall back to session-based
        self.assertIsNotNone(result)
        self.assertEqual(result['components']['session_volatility_suitability'], 80)


class TestConcurrencyValidation(unittest.TestCase):
    """Test concurrency and thread safety"""
    
    def setUp(self):
        reset_singleton(ConfluenceCalculator)
        self.bridge = MockIndicatorBridge()
        self.calculator = ConfluenceCalculator(self.bridge, cache_ttl=5)
    
    def tearDown(self):
        reset_singleton(ConfluenceCalculator)
    
    def test_concurrent_cache_access(self):
        """Test concurrent cache access is thread-safe"""
        self.bridge.multi_data['BTCUSDc'] = create_btc_data()
        
        results = []
        errors = []
        
        def calculate():
            try:
                result = self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
                results.append(result)
            except Exception as e:
                errors.append(str(e))
        
        # Run 10 concurrent calculations
        threads = [threading.Thread(target=calculate) for _ in range(10)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        
        # Should have results
        self.assertEqual(len(results), 10)
        
        # All results should be valid
        for result in results:
            self.assertIn('M1', result)
            self.assertIn('M5', result)
    
    def test_concurrent_regime_cache_access(self):
        """Test concurrent regime cache access is thread-safe"""
        self.bridge.multi_data['BTCUSDc'] = create_regime_test_data('STABLE')
        
        regimes = []
        errors = []
        
        def get_regime():
            try:
                self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
                regime = self.calculator.get_cached_regime('BTCUSDc')
                regimes.append(regime)
            except Exception as e:
                errors.append(str(e))
        
        # Run 10 concurrent operations
        threads = [threading.Thread(target=get_regime) for _ in range(10)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        
        # All regimes should be same (STABLE)
        for regime in regimes:
            if regime:  # May be None if cache expired
                self.assertEqual(regime, 'STABLE')


if __name__ == '__main__':
    import threading
    
    print("=" * 70)
    print("Phase 2: Validation Tests")
    print("=" * 70)
    print()
    print("Testing:")
    print("  - Data validation and edge cases")
    print("  - Boundary conditions")
    print("  - Regime validation edge cases")
    print("  - Concurrency and thread safety")
    print()
    print("=" * 70)
    print()
    
    unittest.main(verbosity=2)

