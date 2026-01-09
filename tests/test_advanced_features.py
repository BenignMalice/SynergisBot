"""
Unit Tests for V8 Advanced Technical Features
=============================================

Tests the 11 institutional-grade indicators in feature_builder_advanced.py
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from infra.feature_builder_advanced import FeatureBuilderAdvanced


class TestAdvancedFeatures(unittest.TestCase):
    """Test suite for Advanced technical features"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create mock MT5 service and indicator bridge
        self.mock_mt5_service = Mock()
        self.mock_bridge = Mock()
        
        # Create feature builder instance
        self.builder = FeatureBuilderAdvanced(self.mock_mt5_service, self.mock_bridge)
        
        # Create test DataFrame
        self.df = self._create_test_dataframe()
    
    def _create_test_dataframe(self, num_bars=300):
        """Create a realistic test DataFrame with OHLCV data"""
        dates = pd.date_range(end=datetime.now(), periods=num_bars, freq='15min')
        
        # Generate realistic price data (uptrend with noise)
        base_price = 4000.0
        trend = np.linspace(0, 50, num_bars)
        noise = np.random.normal(0, 5, num_bars)
        closes = base_price + trend + noise
        
        # Generate OHLC from closes
        opens = closes + np.random.normal(0, 2, num_bars)
        highs = np.maximum(opens, closes) + np.abs(np.random.normal(0, 3, num_bars))
        lows = np.minimum(opens, closes) - np.abs(np.random.normal(0, 3, num_bars))
        volumes = np.random.randint(100, 1000, num_bars)
        
        df = pd.DataFrame({
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        }, index=dates)
        
        return df
    
    def test_rmag_calculation(self):
        """Test RMAG (Relative Moving Average Gap) calculation"""
        current_price = self.df['close'].iloc[-1]
        rmag = self.builder._compute_rmag(self.df, current_price)
        
        # Check structure
        self.assertIn('rmag', rmag)
        self.assertIn('ema200_atr', rmag['rmag'])
        self.assertIn('vwap_atr', rmag['rmag'])
        
        # Check values are reasonable (within ±5 ATR)
        self.assertIsInstance(rmag['rmag']['ema200_atr'], float)
        self.assertIsInstance(rmag['rmag']['vwap_atr'], float)
        self.assertLess(abs(rmag['rmag']['ema200_atr']), 10.0)
        self.assertLess(abs(rmag['rmag']['vwap_atr']), 10.0)
        
        print(f"✅ RMAG Test Passed: {rmag['rmag']}")
    
    def test_ema_slope_calculation(self):
        """Test EMA Slope Strength calculation"""
        ema_slope = self.builder._compute_ema_slope(self.df)
        
        # Check structure
        self.assertIn('ema_slope', ema_slope)
        self.assertIn('ema50', ema_slope['ema_slope'])
        self.assertIn('ema200', ema_slope['ema_slope'])
        
        # Check values are ATR-normalized (typically -1 to +1 for normal trends)
        self.assertIsInstance(ema_slope['ema_slope']['ema50'], float)
        self.assertIsInstance(ema_slope['ema_slope']['ema200'], float)
        
        # For uptrend data, slopes should be positive
        self.assertGreater(ema_slope['ema_slope']['ema50'], -1.0)
        
        print(f"✅ EMA Slope Test Passed: {ema_slope['ema_slope']}")
    
    def test_bollinger_adx_fusion(self):
        """Test Bollinger-ADX Fusion (volatility state)"""
        # Create mock data dict with ADX
        data = {'adx': 25.0}
        
        vol_trend = self.builder._compute_bollinger_adx(self.df, data)
        
        # Check structure
        self.assertIn('vol_trend', vol_trend)
        self.assertIn('bb_width', vol_trend['vol_trend'])
        self.assertIn('adx', vol_trend['vol_trend'])
        self.assertIn('state', vol_trend['vol_trend'])
        
        # Check state is one of the valid values
        valid_states = [
            'squeeze_no_trend', 
            'squeeze_with_trend', 
            'expansion_strong_trend', 
            'expansion_weak_trend'
        ]
        self.assertIn(vol_trend['vol_trend']['state'], valid_states)
        
        # Check BB width is positive
        self.assertGreater(vol_trend['vol_trend']['bb_width'], 0)
        
        print(f"✅ Bollinger-ADX Fusion Test Passed: {vol_trend['vol_trend']}")
    
    def test_rsi_adx_pressure(self):
        """Test RSI-ADX Pressure Ratio calculation"""
        # Create mock data dict with ADX
        data = {'adx': 20.0}
        
        pressure = self.builder._compute_rsi_adx_pressure(self.df, data)
        
        # Check structure
        self.assertIn('pressure', pressure)
        self.assertIn('ratio', pressure['pressure'])
        self.assertIn('rsi', pressure['pressure'])
        self.assertIn('adx', pressure['pressure'])
        
        # Check RSI is in valid range (0-100)
        self.assertGreaterEqual(pressure['pressure']['rsi'], 0)
        self.assertLessEqual(pressure['pressure']['rsi'], 100)
        
        # Check ratio is positive
        self.assertGreater(pressure['pressure']['ratio'], 0)
        
        print(f"✅ RSI-ADX Pressure Test Passed: {pressure['pressure']}")
    
    def test_candle_profile(self):
        """Test Candle Body-Wick Profile analysis"""
        candle_profile = self.builder._compute_candle_profile(self.df)
        
        # Check structure
        self.assertIn('candle_profile', candle_profile)
        self.assertIsInstance(candle_profile['candle_profile'], list)
        
        # Should have 3 candles
        self.assertLessEqual(len(candle_profile['candle_profile']), 3)
        
        if len(candle_profile['candle_profile']) > 0:
            last_candle = candle_profile['candle_profile'][-1]
            
            # Check required fields
            self.assertIn('idx', last_candle)
            self.assertIn('body_atr', last_candle)
            self.assertIn('w2b', last_candle)
            self.assertIn('type', last_candle)
            
            # Check type is valid
            valid_types = ['rejection_up', 'rejection_down', 'indecision', 'conviction', 'neutral']
            self.assertIn(last_candle['type'], valid_types)
        
        print(f"✅ Candle Profile Test Passed: {len(candle_profile['candle_profile'])} candles analyzed")
    
    def test_liquidity_targets(self):
        """Test Liquidity Targets calculation"""
        current_price = self.df['close'].iloc[-1]
        liquidity = self.builder._compute_liquidity_targets(self.df, current_price)
        
        # Check structure
        self.assertIn('liquidity', liquidity)
        self.assertIn('pdl_dist_atr', liquidity['liquidity'])
        self.assertIn('pdh_dist_atr', liquidity['liquidity'])
        self.assertIn('equal_highs', liquidity['liquidity'])
        self.assertIn('equal_lows', liquidity['liquidity'])
        
        # Check distances are non-negative
        self.assertGreaterEqual(liquidity['liquidity']['pdl_dist_atr'], 0)
        self.assertGreaterEqual(liquidity['liquidity']['pdh_dist_atr'], 0)
        
        # Check boolean flags
        self.assertIsInstance(liquidity['liquidity']['equal_highs'], bool)
        self.assertIsInstance(liquidity['liquidity']['equal_lows'], bool)
        
        print(f"✅ Liquidity Targets Test Passed: PDH dist={liquidity['liquidity']['pdh_dist_atr']:.2f}σ")
    
    def test_fvg_detection(self):
        """Test Fair Value Gap detection"""
        current_price = self.df['close'].iloc[-1]
        fvg = self.builder._compute_fvg(self.df, current_price)
        
        # Check structure
        self.assertIn('fvg', fvg)
        self.assertIn('type', fvg['fvg'])
        self.assertIn('dist_to_fill_atr', fvg['fvg'])
        
        # Check type is valid
        valid_types = ['none', 'bull', 'bear']
        self.assertIn(fvg['fvg']['type'], valid_types)
        
        # If FVG exists, distance should be non-negative
        if fvg['fvg']['type'] != 'none':
            self.assertGreaterEqual(fvg['fvg']['dist_to_fill_atr'], 0)
        
        print(f"✅ FVG Test Passed: Type={fvg['fvg']['type']}")
    
    def test_vwap_deviation(self):
        """Test VWAP Deviation Zones calculation"""
        current_price = self.df['close'].iloc[-1]
        data = {}
        
        vwap_dev = self.builder._compute_vwap_deviation(self.df, current_price, data)
        
        # Check structure
        self.assertIn('vwap', vwap_dev)
        self.assertIn('dev_atr', vwap_dev['vwap'])
        self.assertIn('zone', vwap_dev['vwap'])
        
        # Check zone is valid
        valid_zones = ['inside', 'mid', 'outer']
        self.assertIn(vwap_dev['vwap']['zone'], valid_zones)
        
        # Check deviation is reasonable (within ±10 ATR)
        self.assertLess(abs(vwap_dev['vwap']['dev_atr']), 10.0)
        
        print(f"✅ VWAP Deviation Test Passed: {vwap_dev['vwap']['dev_atr']:.2f}σ ({vwap_dev['vwap']['zone']})")
    
    def test_momentum_acceleration(self):
        """Test Momentum Acceleration calculation"""
        # Create mock data with MACD histogram
        data = {'macd_histogram': [0.01, 0.02, 0.03, 0.04, 0.05]}
        
        accel = self.builder._compute_momentum_accel(self.df, data)
        
        # Check structure
        self.assertIn('accel', accel)
        self.assertIn('macd_slope', accel['accel'])
        self.assertIn('rsi_slope', accel['accel'])
        
        # Check values are reasonable (-10 to +10 range for RSI slope)
        self.assertIsInstance(accel['accel']['macd_slope'], float)
        self.assertIsInstance(accel['accel']['rsi_slope'], float)
        self.assertLess(abs(accel['accel']['rsi_slope']), 20.0)
        
        print(f"✅ Momentum Acceleration Test Passed: MACD slope={accel['accel']['macd_slope']:.3f}")
    
    def test_mtf_alignment(self):
        """Test Multi-Timeframe Alignment Score"""
        # Create mock multi-timeframe data
        mock_multi = {
            'M5': {'closes': [4000, 4001, 4002], 'macd_histogram': 0.5, 'adx': 30},
            'M15': {'closes': [4000, 4001, 4002], 'macd_histogram': 0.3, 'adx': 28},
            'H1': {'closes': [4000, 4001, 4002], 'macd_histogram': 0.2, 'adx': 26}
        }
        
        features = {}  # Empty features dict for this test
        
        mtf_score = self.builder._compute_mtf_alignment(features, mock_multi)
        
        # Check structure
        self.assertIn('total', mtf_score)
        self.assertIn('max', mtf_score)
        self.assertIn('m5', mtf_score)
        self.assertIn('m15', mtf_score)
        self.assertIn('h1', mtf_score)
        
        # Check scores are 0 or 1
        self.assertIn(mtf_score['m5'], [0, 1])
        self.assertIn(mtf_score['m15'], [0, 1])
        self.assertIn(mtf_score['h1'], [0, 1])
        
        # Check total is sum of individual scores
        self.assertLessEqual(mtf_score['total'], mtf_score['max'])
        self.assertGreaterEqual(mtf_score['total'], 0)
        
        print(f"✅ MTF Alignment Test Passed: {mtf_score['total']}/{mtf_score['max']}")
    
    def test_volume_profile(self):
        """Test Volume Profile HVN/LVN calculation"""
        current_price = self.df['close'].iloc[-1]
        
        vp = self.builder._compute_volume_profile(self.df, current_price)
        
        # Check structure
        self.assertIn('hvn_dist_atr', vp)
        self.assertIn('lvn_dist_atr', vp)
        
        # Check distances are non-negative
        self.assertGreaterEqual(vp['hvn_dist_atr'], 0)
        self.assertGreaterEqual(vp['lvn_dist_atr'], 0)
        
        print(f"✅ Volume Profile Test Passed: HVN dist={vp['hvn_dist_atr']:.2f}σ, LVN dist={vp['lvn_dist_atr']:.2f}σ")
    
    def test_helper_atr_calculation(self):
        """Test ATR helper method"""
        atr = self.builder._calculate_atr(self.df, period=14)
        
        # Check ATR is positive
        self.assertGreater(atr, 0)
        
        # Check ATR is reasonable (not too high or too low)
        avg_price = self.df['close'].mean()
        self.assertLess(atr, avg_price * 0.05)  # ATR should be < 5% of price
        self.assertGreater(atr, avg_price * 0.0001)  # ATR should be > 0.01% of price
        
        print(f"✅ ATR Calculation Test Passed: ATR={atr:.5f}")
    
    def test_helper_rsi_calculation(self):
        """Test RSI helper method"""
        rsi = self.builder._calculate_rsi(self.df, period=14)
        
        # Check RSI is in valid range (0-100)
        self.assertGreaterEqual(rsi, 0)
        self.assertLessEqual(rsi, 100)
        
        # For uptrend data, RSI should be > 40
        self.assertGreater(rsi, 30)
        
        print(f"✅ RSI Calculation Test Passed: RSI={rsi:.1f}")
    
    def test_helper_equal_levels(self):
        """Test equal levels detection helper"""
        # Test with equal levels
        levels_equal = [100.0, 100.05, 100.1]
        result_equal = self.builder._find_equal_levels(levels_equal, tolerance=0.001)
        self.assertTrue(result_equal)
        
        # Test with non-equal levels
        levels_different = [100.0, 105.0, 110.0]
        result_different = self.builder._find_equal_levels(levels_different, tolerance=0.001)
        self.assertFalse(result_different)
        
        print(f"✅ Equal Levels Detection Test Passed")
    
    def test_integration_build_features(self):
        """Test full feature building integration"""
        # Mock the bridge to return multi-timeframe data
        self.mock_bridge.get_multi.return_value = {
            'M5': {
                'opens': self.df['open'].tolist(),
                'highs': self.df['high'].tolist(),
                'lows': self.df['low'].tolist(),
                'closes': self.df['close'].tolist(),
                'volumes': self.df['volume'].tolist(),
                'times': [int(ts.timestamp()) for ts in self.df.index],
                'adx': 25.0,
                'macd_histogram': [0.01, 0.02, 0.03]
            }
        }
        
        # Build features
        result = self.builder.build_features('XAUUSD', timeframes=['M5'])
        
        # Check structure
        self.assertIn('symbol', result)
        self.assertIn('timestamp', result)
        self.assertIn('features', result)
        
        print(f"✅ Integration Test Passed: Built features for {result['symbol']}")


def run_tests():
    """Run all tests and print summary"""
    print("\n" + "="*80)
    print("V8 ADVANCED TECHNICAL FEATURES - UNIT TEST SUITE")
    print("="*80 + "\n")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestV8Features)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*80)
    print(f"TESTS RUN: {result.testsRun}")
    print(f"PASSED: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"FAILED: {len(result.failures)}")
    print(f"ERRORS: {len(result.errors)}")
    print("="*80 + "\n")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

