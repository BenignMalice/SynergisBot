# =====================================
# tests/test_phase1_6_asset_profiles.py
# =====================================
"""
Tests for Phase 1.6: Asset-Specific Profile Manager
Tests AssetProfileManager functionality
"""

import unittest
import sys
import os
import json
import tempfile
from unittest.mock import Mock, patch

# Add project root to path (adjust for new location in docs folder)
# From: docs/Pending Updates - 19.11.25/Tests - M1_Microstructure/
# To: project root (3 levels up: .. -> .. -> ..)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.m1_asset_profiles import AssetProfileManager


class TestAssetProfileManager(unittest.TestCase):
    """Test cases for AssetProfileManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary profile file for testing
        self.test_profiles = {
            "XAUUSD": {
                "primary_sessions": ["LONDON", "NY", "OVERLAP"],
                "volatility_personality": "HIGH_VOLATILITY",
                "atr_multiplier_range": [1.0, 1.2],
                "confluence_minimum": 75,
                "vwap_stretch_tolerance": 1.5,
                "preferred_strategies": {
                    "LONDON": ["BREAKOUT", "CHOCH_CONTINUATION"],
                    "NY": ["VWAP_FADE", "PULLBACK_SCALP"]
                },
                "behavior_traits": ["Sharp liquidity sweeps"],
                "weekend_trading": False
            },
            "BTCUSD": {
                "primary_sessions": ["ASIAN", "LONDON", "NY", "OVERLAP"],
                "volatility_personality": "VERY_HIGH_VOLATILITY",
                "atr_multiplier_range": [1.5, 2.0],
                "confluence_minimum": 85,
                "vwap_stretch_tolerance": 2.5,
                "preferred_strategies": {
                    "ASIAN": ["TREND_SCALP"],
                    "LONDON": ["BREAKOUT", "MOMENTUM"]
                },
                "behavior_traits": ["High volatility"],
                "weekend_trading": True
            }
        }
        
        # Create temporary file
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(self.test_profiles, self.temp_file)
        self.temp_file.close()
        
        # Initialize manager with temp file
        self.manager = AssetProfileManager(profile_file=self.temp_file.name)
    
    def tearDown(self):
        """Clean up after tests"""
        try:
            os.unlink(self.temp_file.name)
        except:
            pass
    
    def test_initialization(self):
        """Test AssetProfileManager initialization"""
        self.assertIsNotNone(self.manager)
        self.assertGreater(len(self.manager.profiles), 0)
    
    def test_get_asset_profile_xauusd(self):
        """Test getting XAUUSD profile"""
        profile = self.manager.get_asset_profile("XAUUSD")
        
        self.assertEqual(profile["symbol"], "XAUUSD")
        self.assertEqual(profile["volatility_personality"], "HIGH_VOLATILITY")
        self.assertEqual(profile["confluence_minimum"], 75)
        self.assertEqual(profile["vwap_stretch_tolerance"], 1.5)
        self.assertIn("LONDON", profile["primary_sessions"])
    
    def test_get_asset_profile_btcusd(self):
        """Test getting BTCUSD profile"""
        profile = self.manager.get_asset_profile("BTCUSD")
        
        self.assertEqual(profile["symbol"], "BTCUSD")
        self.assertEqual(profile["volatility_personality"], "VERY_HIGH_VOLATILITY")
        self.assertEqual(profile["confluence_minimum"], 85)
        self.assertEqual(profile["vwap_stretch_tolerance"], 2.5)
        self.assertTrue(profile["weekend_trading"])
    
    def test_get_asset_profile_with_suffix(self):
        """Test getting profile with 'c' suffix"""
        profile = self.manager.get_asset_profile("XAUUSDc")
        
        # Should normalize and return XAUUSD profile
        self.assertEqual(profile["symbol"], "XAUUSD")
    
    def test_get_asset_profile_unknown(self):
        """Test getting profile for unknown symbol"""
        profile = self.manager.get_asset_profile("UNKNOWN")
        
        # Should return default profile
        self.assertEqual(profile["symbol"], "UNKNOWN")
        self.assertEqual(profile["confluence_minimum"], 70)  # Default
    
    def test_get_preferred_strategies(self):
        """Test getting preferred strategies"""
        # XAUUSD in London
        strategies = self.manager.get_preferred_strategies("XAUUSD", "LONDON")
        self.assertIn("BREAKOUT", strategies)
        self.assertIn("CHOCH_CONTINUATION", strategies)
        
        # BTCUSD in Asian
        strategies = self.manager.get_preferred_strategies("BTCUSD", "ASIAN")
        self.assertIn("TREND_SCALP", strategies)
    
    def test_get_preferred_strategies_unknown_session(self):
        """Test getting strategies for unknown session"""
        strategies = self.manager.get_preferred_strategies("XAUUSD", "UNKNOWN")
        
        # Should return default or fallback
        self.assertIsInstance(strategies, list)
        self.assertGreater(len(strategies), 0)
    
    def test_get_atr_multiplier(self):
        """Test getting ATR multiplier"""
        # XAUUSD: [1.0, 1.2] -> average = 1.1
        atr = self.manager.get_atr_multiplier("XAUUSD")
        self.assertAlmostEqual(atr, 1.1, places=1)
        
        # BTCUSD: [1.5, 2.0] -> average = 1.75
        atr = self.manager.get_atr_multiplier("BTCUSD")
        self.assertAlmostEqual(atr, 1.75, places=1)
    
    def test_get_confluence_minimum(self):
        """Test getting confluence minimum"""
        # XAUUSD
        confluence = self.manager.get_confluence_minimum("XAUUSD")
        self.assertEqual(confluence, 75)
        
        # BTCUSD
        confluence = self.manager.get_confluence_minimum("BTCUSD")
        self.assertEqual(confluence, 85)
        
        # Unknown symbol
        confluence = self.manager.get_confluence_minimum("UNKNOWN")
        self.assertEqual(confluence, 70)  # Default
    
    def test_get_vwap_stretch_tolerance(self):
        """Test getting VWAP stretch tolerance"""
        # XAUUSD
        vwap = self.manager.get_vwap_stretch_tolerance("XAUUSD")
        self.assertEqual(vwap, 1.5)
        
        # BTCUSD
        vwap = self.manager.get_vwap_stretch_tolerance("BTCUSD")
        self.assertEqual(vwap, 2.5)
    
    def test_is_weekend_trading(self):
        """Test weekend trading check"""
        # XAUUSD
        weekend = self.manager.is_weekend_trading("XAUUSD")
        self.assertFalse(weekend)
        
        # BTCUSD
        weekend = self.manager.is_weekend_trading("BTCUSD")
        self.assertTrue(weekend)
    
    def test_is_session_active_for_symbol(self):
        """Test session active check"""
        # XAUUSD in London
        active = self.manager.is_session_active_for_symbol("XAUUSD", "LONDON")
        self.assertTrue(active)
        
        # XAUUSD in Asian
        active = self.manager.is_session_active_for_symbol("XAUUSD", "ASIAN")
        self.assertFalse(active)
        
        # BTCUSD in any session (24/7)
        active = self.manager.is_session_active_for_symbol("BTCUSD", "ASIAN")
        self.assertTrue(active)
        active = self.manager.is_session_active_for_symbol("BTCUSD", "LONDON")
        self.assertTrue(active)
    
    def test_get_volatility_personality(self):
        """Test getting volatility personality"""
        personality = self.manager.get_volatility_personality("XAUUSD")
        self.assertEqual(personality, "HIGH_VOLATILITY")
        
        personality = self.manager.get_volatility_personality("BTCUSD")
        self.assertEqual(personality, "VERY_HIGH_VOLATILITY")
    
    def test_get_behavior_traits(self):
        """Test getting behavior traits"""
        traits = self.manager.get_behavior_traits("XAUUSD")
        self.assertIsInstance(traits, list)
        self.assertGreater(len(traits), 0)
        self.assertIn("Sharp liquidity sweeps", traits)
    
    def test_is_signal_valid_for_asset(self):
        """Test signal validation for asset"""
        # Valid signal (confluence >= minimum)
        analysis = {
            "microstructure_confluence": {"score": 80},
            "volatility": {"state": "EXPANDING"}
        }
        is_valid = self.manager.is_signal_valid_for_asset("XAUUSD", analysis)
        self.assertTrue(is_valid)
        
        # Invalid signal (confluence < minimum)
        analysis = {
            "microstructure_confluence": {"score": 70},
            "volatility": {"state": "EXPANDING"}
        }
        is_valid = self.manager.is_signal_valid_for_asset("XAUUSD", analysis)
        self.assertFalse(is_valid)
        
        # BTCUSD with stable volatility (should be invalid)
        analysis = {
            "microstructure_confluence": {"score": 90},
            "volatility": {"state": "STABLE"}
        }
        is_valid = self.manager.is_signal_valid_for_asset("BTCUSD", analysis)
        self.assertFalse(is_valid)
    
    def test_get_profile_summary(self):
        """Test getting profile summary"""
        summary = self.manager.get_profile_summary("XAUUSD")
        
        self.assertIn("XAUUSD", summary)
        self.assertIn("HIGH_VOLATILITY", summary)
        self.assertIn("75", summary)  # Confluence minimum
        self.assertIn("1.5", summary)  # VWAP stretch
    
    def test_default_profiles_on_file_not_found(self):
        """Test that default profiles are used when file not found"""
        manager = AssetProfileManager(profile_file="nonexistent.json")
        
        # Should still work with defaults
        profile = manager.get_asset_profile("XAUUSD")
        self.assertIsNotNone(profile)
        self.assertEqual(profile["symbol"], "XAUUSD")


if __name__ == '__main__':
    unittest.main()

