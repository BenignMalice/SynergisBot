# =====================================
# tests/test_phase2_6_additional_integration.py
# =====================================
"""
Additional Integration Tests for Phase 2.6: Session & Asset Behavior Integration
Tests integration with M1MicrostructureAnalyzer, edge cases, and real-world scenarios
"""

import unittest
import sys
import os
import tempfile
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone, timedelta

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.m1_session_volatility_profile import SessionVolatilityProfile
from infra.m1_asset_profiles import AssetProfileManager
from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer


class TestPhase2_6AdditionalIntegration(unittest.TestCase):
    """Additional integration tests for Phase 2.6"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary asset profiles file
        self.temp_asset_profiles = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_asset_profiles.write('''{
  "XAUUSD": {
    "volatility_personality": "HIGH_VOLATILITY",
    "atr_multiplier_range": [1.0, 1.2],
    "vwap_stretch_tolerance": 1.5,
    "confluence_minimum": 70,
    "primary_sessions": ["LONDON", "NY"],
    "preferred_strategies": {
      "LONDON": ["VWAP_REJECTION", "CHOCH"],
      "NY": ["VWAP_REJECTION", "BREAKOUT"]
    }
  },
  "BTCUSD": {
    "volatility_personality": "VERY_HIGH_VOLATILITY",
    "atr_multiplier_range": [1.5, 2.0],
    "vwap_stretch_tolerance": 2.5,
    "confluence_minimum": 75,
    "primary_sessions": ["24h"],
    "preferred_strategies": {
      "24h": ["MOMENTUM_BREAKOUT", "CHOCH"]
    }
  }
}''')
        self.temp_asset_profiles.close()
        
        # Initialize components
        self.session_manager = SessionVolatilityProfile()
        self.asset_profiles = AssetProfileManager(profile_file=self.temp_asset_profiles.name)
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_asset_profiles.name):
            os.unlink(self.temp_asset_profiles.name)
    
    def test_session_adjusted_parameters_integration_with_m1_analyzer(self):
        """Test that session-adjusted parameters integrate with M1MicrostructureAnalyzer"""
        # Create mock M1 analyzer with session manager and asset profiles
        mock_mt5 = Mock()
        analyzer = M1MicrostructureAnalyzer(
            mt5_service=mock_mt5,
            session_manager=self.session_manager,
            asset_profiles=self.asset_profiles
        )
        
        # Create sample M1 candles
        candles = [
            {'time': datetime.now(timezone.utc) - timedelta(minutes=i), 'open': 2400.0 + i*0.1, 
             'high': 2400.5 + i*0.1, 'low': 2399.5 + i*0.1, 'close': 2400.2 + i*0.1, 'volume': 100}
            for i in range(50, 0, -1)
        ]
        
        # Analyze microstructure
        analysis = analyzer.analyze_microstructure(
            symbol="XAUUSDc",
            candles=candles,
            current_price=2405.0
        )
        
        # Verify session context is included
        self.assertIn('session_context', analysis)
        self.assertIn('session', analysis['session_context'])
        self.assertIn('session_adjusted_parameters', analysis)
        
        # Verify session-adjusted parameters are present
        session_params = analysis.get('session_adjusted_parameters', {})
        self.assertIn('atr_multiplier', session_params)
        self.assertIn('vwap_stretch', session_params)
        self.assertIn('bias_factor', session_params)
    
    def test_session_adjusted_parameters_all_sessions_round_trip(self):
        """Test session-adjusted parameters for all sessions in a round-trip"""
        sessions = ['ASIAN', 'LONDON', 'OVERLAP', 'NY', 'POST_NY']
        symbol = 'XAUUSD'
        
        for session in sessions:
            params = self.session_manager.get_session_adjusted_parameters(
                symbol=symbol,
                session=session,
                asset_profiles=self.asset_profiles
            )
            
            # Verify all required fields are present
            self.assertIn('min_confluence', params)
            self.assertIn('atr_multiplier', params)
            self.assertIn('vwap_stretch_tolerance', params)
            self.assertIn('session_profile', params)
            
            # Verify values are reasonable
            self.assertGreater(params['min_confluence'], 0)
            self.assertGreater(params['atr_multiplier'], 0)
            self.assertGreater(params['vwap_stretch_tolerance'], 0)
    
    def test_session_adjusted_parameters_symbol_normalization(self):
        """Test that symbol normalization works correctly"""
        # Test with 'c' suffix
        params1 = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSDc",
            session="LONDON",
            asset_profiles=self.asset_profiles
        )
        
        # Test without 'c' suffix
        params2 = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="LONDON",
            asset_profiles=self.asset_profiles
        )
        
        # Results should be the same (asset profiles handle normalization)
        # Note: AssetProfileManager normalizes symbols internally
        self.assertEqual(params1['min_confluence'], params2['min_confluence'])
    
    def test_session_adjusted_parameters_edge_case_zero_atr(self):
        """Test session-adjusted parameters with edge case: zero ATR range"""
        # Create asset profile with zero ATR range
        temp_profile = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        temp_profile.write('''{
  "TEST": {
    "volatility_personality": "MODERATE_VOLATILITY",
    "atr_multiplier_range": [0.0, 0.0],
    "vwap_stretch_tolerance": 1.0,
    "confluence_minimum": 70
  }
}''')
        temp_profile.close()
        
        test_asset_profiles = AssetProfileManager(profile_file=temp_profile.name)
        
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="TEST",
            session="LONDON",
            asset_profiles=test_asset_profiles
        )
        
        # Should handle zero ATR gracefully
        self.assertEqual(params['atr_multiplier'], 0.0)
        
        # Cleanup
        os.unlink(temp_profile.name)
    
    def test_session_adjusted_parameters_edge_case_negative_values(self):
        """Test session-adjusted parameters with edge case: negative base values"""
        # Create asset profile with negative values (shouldn't happen, but test robustness)
        temp_profile = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        temp_profile.write('''{
  "TEST": {
    "volatility_personality": "MODERATE_VOLATILITY",
    "atr_multiplier_range": [-1.0, 1.0],
    "vwap_stretch_tolerance": -0.5,
    "confluence_minimum": -10
  }
}''')
        temp_profile.close()
        
        test_asset_profiles = AssetProfileManager(profile_file=temp_profile.name)
        
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="TEST",
            session="LONDON",
            asset_profiles=test_asset_profiles
        )
        
        # Should handle negative values (though not ideal)
        # The method should still return values (may be negative)
        self.assertIn('min_confluence', params)
        self.assertIn('atr_multiplier', params)
        self.assertIn('vwap_stretch_tolerance', params)
        
        # Cleanup
        os.unlink(temp_profile.name)
    
    def test_session_adjusted_parameters_very_high_values(self):
        """Test session-adjusted parameters with very high base values"""
        temp_profile = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        temp_profile.write('''{
  "TEST": {
    "volatility_personality": "VERY_HIGH_VOLATILITY",
    "atr_multiplier_range": [10.0, 20.0],
    "vwap_stretch_tolerance": 10.0,
    "confluence_minimum": 200
  }
}''')
        temp_profile.close()
        
        test_asset_profiles = AssetProfileManager(profile_file=temp_profile.name)
        
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="TEST",
            session="OVERLAP",
            asset_profiles=test_asset_profiles
        )
        
        # Should handle very high values
        self.assertGreater(params['min_confluence'], 0)
        self.assertGreater(params['atr_multiplier'], 0)
        self.assertGreater(params['vwap_stretch_tolerance'], 0)
        
        # Overlap session has aggressive multipliers (0.9, 1.2, 1.2)
        # Base confluence: 200, multiplier: 0.9 → 180
        self.assertEqual(params['min_confluence'], 180.0)
        # Base ATR: 15.0, multiplier: 1.2 → 18.0
        self.assertEqual(params['atr_multiplier'], 18.0)
        # Base VWAP: 10.0, multiplier: 1.2 → 12.0
        self.assertEqual(params['vwap_stretch_tolerance'], 12.0)
        
        # Cleanup
        os.unlink(temp_profile.name)
    
    def test_session_adjusted_parameters_concurrent_sessions(self):
        """Test that different sessions produce different adjusted parameters"""
        symbol = 'XAUUSD'
        
        # Get parameters for different sessions
        asian_params = self.session_manager.get_session_adjusted_parameters(
            symbol=symbol,
            session="ASIAN",
            asset_profiles=self.asset_profiles
        )
        
        overlap_params = self.session_manager.get_session_adjusted_parameters(
            symbol=symbol,
            session="OVERLAP",
            asset_profiles=self.asset_profiles
        )
        
        # Asian should have higher confluence (stricter)
        self.assertGreater(asian_params['min_confluence'], overlap_params['min_confluence'])
        
        # Overlap should have higher ATR multiplier (more aggressive)
        self.assertGreater(overlap_params['atr_multiplier'], asian_params['atr_multiplier'])
        
        # Overlap should have higher VWAP tolerance (more aggressive)
        self.assertGreater(overlap_params['vwap_stretch_tolerance'], asian_params['vwap_stretch_tolerance'])
    
    def test_session_adjusted_parameters_different_symbols_same_session(self):
        """Test that different symbols produce different adjusted parameters in same session"""
        session = 'LONDON'
        
        # Get parameters for different symbols
        xau_params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session=session,
            asset_profiles=self.asset_profiles
        )
        
        btc_params = self.session_manager.get_session_adjusted_parameters(
            symbol="BTCUSD",
            session=session,
            asset_profiles=self.asset_profiles
        )
        
        # BTCUSD should have higher base confluence
        self.assertGreater(btc_params['min_confluence'], xau_params['min_confluence'])
        
        # BTCUSD should have higher ATR multiplier
        self.assertGreater(btc_params['atr_multiplier'], xau_params['atr_multiplier'])
        
        # BTCUSD should have higher VWAP tolerance
        self.assertGreater(btc_params['vwap_stretch_tolerance'], xau_params['vwap_stretch_tolerance'])
    
    def test_session_adjusted_parameters_rounding_precision(self):
        """Test that parameters are rounded to appropriate precision"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="LONDON",
            asset_profiles=self.asset_profiles
        )
        
        # min_confluence should be rounded to 1 decimal place
        self.assertEqual(len(str(params['min_confluence']).split('.')[-1]), 1)
        
        # atr_multiplier should be rounded to 2 decimal places
        self.assertLessEqual(len(str(params['atr_multiplier']).split('.')[-1]), 2)
        
        # vwap_stretch_tolerance should be rounded to 2 decimal places
        self.assertLessEqual(len(str(params['vwap_stretch_tolerance']).split('.')[-1]), 2)
    
    def test_session_adjusted_parameters_session_profile_completeness(self):
        """Test that session profile includes all required fields"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="LONDON",
            asset_profiles=self.asset_profiles
        )
        
        session_profile = params['session_profile']
        
        # Verify all required fields
        required_fields = ['session', 'volatility_tier', 'liquidity_timing', 
                          'typical_behavior', 'best_strategy_type', 'session_bias_factor']
        
        for field in required_fields:
            self.assertIn(field, session_profile, f"Missing field: {field}")
    
    def test_session_adjusted_parameters_base_values_preserved(self):
        """Test that base values are correctly preserved in response"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="LONDON",
            asset_profiles=self.asset_profiles
        )
        
        # Verify base values are present
        self.assertIn('base_confluence', params)
        self.assertIn('base_atr_multiplier', params)
        self.assertIn('base_vwap_tolerance', params)
        
        # Verify base values match asset profile
        self.assertEqual(params['base_confluence'], 70.0)
        self.assertEqual(params['base_atr_multiplier'], 1.1)  # (1.0 + 1.2) / 2
        self.assertEqual(params['base_vwap_tolerance'], 1.5)
    
    def test_session_adjusted_parameters_session_multipliers_included(self):
        """Test that session multipliers are included in response"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="ASIAN",
            asset_profiles=self.asset_profiles
        )
        
        # Verify session multipliers are present
        self.assertIn('session_multipliers', params)
        multipliers = params['session_multipliers']
        
        # Verify multiplier values
        self.assertEqual(multipliers['confluence'], 1.1)
        self.assertEqual(multipliers['atr'], 0.9)
        self.assertEqual(multipliers['vwap'], 0.8)
    
    def test_session_adjusted_parameters_calculation_accuracy(self):
        """Test that calculations are mathematically accurate"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="OVERLAP",
            asset_profiles=self.asset_profiles
        )
        
        # Verify calculations
        base_confluence = params['base_confluence']
        base_atr = params['base_atr_multiplier']
        base_vwap = params['base_vwap_tolerance']
        multipliers = params['session_multipliers']
        
        # Calculate expected values
        expected_confluence = base_confluence * multipliers['confluence']
        expected_atr = base_atr * multipliers['atr']
        expected_vwap = base_vwap * multipliers['vwap']
        
        # Verify actual values match expected (with rounding tolerance)
        self.assertAlmostEqual(params['min_confluence'], expected_confluence, places=1)
        self.assertAlmostEqual(params['atr_multiplier'], expected_atr, places=2)
        self.assertAlmostEqual(params['vwap_stretch_tolerance'], expected_vwap, places=2)
    
    def test_session_adjusted_parameters_missing_asset_profile_field(self):
        """Test handling of missing fields in asset profile"""
        temp_profile = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        temp_profile.write('''{
  "TEST": {
    "volatility_personality": "MODERATE_VOLATILITY"
  }
}''')
        temp_profile.close()
        
        test_asset_profiles = AssetProfileManager(profile_file=temp_profile.name)
        
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="TEST",
            session="LONDON",
            asset_profiles=test_asset_profiles
        )
        
        # Should use defaults for missing fields
        self.assertIn('min_confluence', params)
        self.assertIn('atr_multiplier', params)
        self.assertIn('vwap_stretch_tolerance', params)
        
        # Cleanup
        os.unlink(temp_profile.name)
    
    def test_session_adjusted_parameters_case_insensitive_session(self):
        """Test that session names are case-insensitive"""
        params1 = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="london",
            asset_profiles=self.asset_profiles
        )
        
        params2 = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="LONDON",
            asset_profiles=self.asset_profiles
        )
        
        params3 = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="London",
            asset_profiles=self.asset_profiles
        )
        
        # All should produce same results
        self.assertEqual(params1['min_confluence'], params2['min_confluence'])
        self.assertEqual(params2['min_confluence'], params3['min_confluence'])


if __name__ == '__main__':
    unittest.main()

