# =====================================
# tests/test_phase2_6_session_asset_integration.py
# =====================================
"""
Tests for Phase 2.6: Session & Asset Behavior Integration
Tests get_session_adjusted_parameters and session/asset integration
"""

import unittest
import sys
import os
import tempfile
from unittest.mock import Mock, MagicMock
from datetime import datetime, timezone

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.m1_session_volatility_profile import SessionVolatilityProfile
from infra.m1_asset_profiles import AssetProfileManager


class TestPhase2_6SessionAssetIntegration(unittest.TestCase):
    """Test cases for Phase 2.6 Session & Asset Behavior Integration"""
    
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
  },
  "EURUSD": {
    "volatility_personality": "MODERATE_VOLATILITY",
    "atr_multiplier_range": [0.8, 1.0],
    "vwap_stretch_tolerance": 1.0,
    "confluence_minimum": 65,
    "primary_sessions": ["LONDON"],
    "preferred_strategies": {
      "LONDON": ["RANGE_SCALP", "VWAP_FADE"]
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
    
    def test_get_session_adjusted_parameters_xauusd_london(self):
        """Test session-adjusted parameters for XAUUSD in London session"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="LONDON",
            asset_profiles=self.asset_profiles
        )
        
        self.assertIn('min_confluence', params)
        self.assertIn('atr_multiplier', params)
        self.assertIn('vwap_stretch_tolerance', params)
        self.assertIn('session_profile', params)
        
        # London session has 1.0 multipliers (normal)
        # XAUUSD base confluence: 70, base ATR: 1.1, base VWAP: 1.5
        # London multipliers: confluence=1.0, atr=1.0, vwap=1.0
        self.assertEqual(params['min_confluence'], 70.0)
        self.assertEqual(params['atr_multiplier'], 1.1)  # (1.0 + 1.2) / 2 * 1.0
        self.assertEqual(params['vwap_stretch_tolerance'], 1.5)
    
    def test_get_session_adjusted_parameters_xauusd_asian(self):
        """Test session-adjusted parameters for XAUUSD in Asian session (stricter)"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="ASIAN",
            asset_profiles=self.asset_profiles
        )
        
        # Asian session has stricter multipliers (confluence=1.1, atr=0.9, vwap=0.8)
        # XAUUSD base confluence: 70, base ATR: 1.1, base VWAP: 1.5
        # Asian multipliers: confluence=1.1, atr=0.9, vwap=0.8
        self.assertEqual(params['min_confluence'], 77.0)  # 70 * 1.1
        self.assertAlmostEqual(params['atr_multiplier'], 0.99, places=2)  # 1.1 * 0.9
        self.assertEqual(params['vwap_stretch_tolerance'], 1.2)  # 1.5 * 0.8
    
    def test_get_session_adjusted_parameters_xauusd_overlap(self):
        """Test session-adjusted parameters for XAUUSD in Overlap session (more aggressive)"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="OVERLAP",
            asset_profiles=self.asset_profiles
        )
        
        # Overlap session has more aggressive multipliers (confluence=0.9, atr=1.2, vwap=1.2)
        # XAUUSD base confluence: 70, base ATR: 1.1, base VWAP: 1.5
        # Overlap multipliers: confluence=0.9, atr=1.2, vwap=1.2
        self.assertEqual(params['min_confluence'], 63.0)  # 70 * 0.9
        self.assertAlmostEqual(params['atr_multiplier'], 1.32, places=2)  # 1.1 * 1.2
        self.assertEqual(params['vwap_stretch_tolerance'], 1.8)  # 1.5 * 1.2
    
    def test_get_session_adjusted_parameters_btcusd_asian(self):
        """Test session-adjusted parameters for BTCUSD in Asian session"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="BTCUSD",
            session="ASIAN",
            asset_profiles=self.asset_profiles
        )
        
        # BTCUSD base confluence: 75, base ATR: 1.75, base VWAP: 2.5
        # Asian multipliers: confluence=1.1, atr=0.9, vwap=0.8
        self.assertEqual(params['min_confluence'], 82.5)  # 75 * 1.1
        self.assertAlmostEqual(params['atr_multiplier'], 1.575, places=2)  # 1.75 * 0.9
        self.assertEqual(params['vwap_stretch_tolerance'], 2.0)  # 2.5 * 0.8
    
    def test_get_session_adjusted_parameters_eurusd_london(self):
        """Test session-adjusted parameters for EURUSD in London session"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="EURUSD",
            session="LONDON",
            asset_profiles=self.asset_profiles
        )
        
        # EURUSD base confluence: 65, base ATR: 0.9, base VWAP: 1.0
        # London multipliers: confluence=1.0, atr=1.0, vwap=1.0
        self.assertEqual(params['min_confluence'], 65.0)
        self.assertEqual(params['atr_multiplier'], 0.9)
        self.assertEqual(params['vwap_stretch_tolerance'], 1.0)
    
    def test_get_session_adjusted_parameters_without_asset_profiles(self):
        """Test session-adjusted parameters without asset profiles (uses defaults)"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="LONDON",
            asset_profiles=None
        )
        
        # Should use default base parameters
        self.assertEqual(params['min_confluence'], 70.0)  # Default base
        self.assertEqual(params['atr_multiplier'], 1.0)  # Default base
        self.assertEqual(params['vwap_stretch_tolerance'], 1.0)  # Default base
    
    def test_get_session_adjusted_parameters_unknown_session(self):
        """Test session-adjusted parameters with unknown session (uses defaults)"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="UNKNOWN",
            asset_profiles=self.asset_profiles
        )
        
        # Unknown session should use default multipliers (1.0, 1.0, 1.0)
        self.assertEqual(params['min_confluence'], 70.0)
        self.assertEqual(params['atr_multiplier'], 1.1)
        self.assertEqual(params['vwap_stretch_tolerance'], 1.5)
    
    def test_get_session_adjusted_parameters_unknown_symbol(self):
        """Test session-adjusted parameters with unknown symbol (uses defaults)"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="UNKNOWN",
            session="LONDON",
            asset_profiles=self.asset_profiles
        )
        
        # Unknown symbol should use default base parameters
        self.assertEqual(params['min_confluence'], 70.0)  # Default base
        self.assertEqual(params['atr_multiplier'], 1.0)  # Default base
        self.assertEqual(params['vwap_stretch_tolerance'], 1.0)  # Default base
    
    def test_get_session_adjusted_parameters_includes_session_profile(self):
        """Test that session-adjusted parameters include full session profile"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="LONDON",
            asset_profiles=self.asset_profiles
        )
        
        self.assertIn('session_profile', params)
        session_profile = params['session_profile']
        self.assertIn('session', session_profile)
        self.assertIn('volatility_tier', session_profile)
        self.assertIn('liquidity_timing', session_profile)
        self.assertEqual(session_profile['session'], 'LONDON')
    
    def test_get_session_adjusted_parameters_includes_base_values(self):
        """Test that session-adjusted parameters include base values"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="LONDON",
            asset_profiles=self.asset_profiles
        )
        
        self.assertIn('base_confluence', params)
        self.assertIn('base_atr_multiplier', params)
        self.assertIn('base_vwap_tolerance', params)
        self.assertIn('session_multipliers', params)
        
        self.assertEqual(params['base_confluence'], 70.0)
        self.assertEqual(params['base_atr_multiplier'], 1.1)
        self.assertEqual(params['base_vwap_tolerance'], 1.5)
    
    def test_get_session_adjusted_parameters_post_ny_session(self):
        """Test session-adjusted parameters for Post-NY session (stricter)"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="POST_NY",
            asset_profiles=self.asset_profiles
        )
        
        # Post-NY session has stricter multipliers (confluence=1.1, atr=0.9, vwap=0.8)
        self.assertEqual(params['min_confluence'], 77.0)  # 70 * 1.1
        self.assertAlmostEqual(params['atr_multiplier'], 0.99, places=2)  # 1.1 * 0.9
        self.assertEqual(params['vwap_stretch_tolerance'], 1.2)  # 1.5 * 0.8
    
    def test_get_session_adjusted_parameters_ny_session(self):
        """Test session-adjusted parameters for NY session (normal)"""
        params = self.session_manager.get_session_adjusted_parameters(
            symbol="XAUUSD",
            session="NY",
            asset_profiles=self.asset_profiles
        )
        
        # NY session has normal multipliers (confluence=1.0, atr=1.0, vwap=1.0)
        self.assertEqual(params['min_confluence'], 70.0)
        self.assertEqual(params['atr_multiplier'], 1.1)
        self.assertEqual(params['vwap_stretch_tolerance'], 1.5)


if __name__ == '__main__':
    unittest.main()

