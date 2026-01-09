# =====================================
# tests/test_phase1_5_session_manager.py
# =====================================
"""
Tests for Phase 1.5: Session Manager Integration
Tests SessionVolatilityProfile functionality
"""

import unittest
import sys
import os
from unittest.mock import Mock, MagicMock
from datetime import datetime, timezone

# Add project root to path (adjust for new location in docs folder)
# From: docs/Pending Updates - 19.11.25/Tests - M1_Microstructure/
# To: project root (3 levels up: .. -> .. -> ..)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.m1_session_volatility_profile import SessionVolatilityProfile


class TestSessionVolatilityProfile(unittest.TestCase):
    """Test cases for SessionVolatilityProfile"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.session_profile = SessionVolatilityProfile()
    
    def test_initialization(self):
        """Test SessionVolatilityProfile initialization"""
        self.assertIsNotNone(self.session_profile)
    
    def test_get_current_session_asian(self):
        """Test session detection for Asian session"""
        # Asian: 0-8 UTC
        test_time = datetime(2025, 11, 20, 4, 0, 0, tzinfo=timezone.utc)  # 04:00 UTC
        session = self.session_profile.get_current_session(test_time)
        self.assertEqual(session, "ASIAN")
    
    def test_get_current_session_london(self):
        """Test session detection for London session"""
        # London: 8-13 UTC
        test_time = datetime(2025, 11, 20, 10, 0, 0, tzinfo=timezone.utc)  # 10:00 UTC
        session = self.session_profile.get_current_session(test_time)
        self.assertEqual(session, "LONDON")
    
    def test_get_current_session_overlap(self):
        """Test session detection for Overlap session"""
        # Overlap: 13-16 UTC
        test_time = datetime(2025, 11, 20, 14, 0, 0, tzinfo=timezone.utc)  # 14:00 UTC
        session = self.session_profile.get_current_session(test_time)
        self.assertEqual(session, "OVERLAP")
    
    def test_get_current_session_ny(self):
        """Test session detection for NY session"""
        # NY: 16-21 UTC
        test_time = datetime(2025, 11, 20, 18, 0, 0, tzinfo=timezone.utc)  # 18:00 UTC
        session = self.session_profile.get_current_session(test_time)
        self.assertEqual(session, "NY")
    
    def test_get_current_session_post_ny(self):
        """Test session detection for Post-NY session"""
        # Post-NY: 21-24 UTC
        test_time = datetime(2025, 11, 20, 22, 0, 0, tzinfo=timezone.utc)  # 22:00 UTC
        session = self.session_profile.get_current_session(test_time)
        self.assertEqual(session, "POST_NY")
    
    def test_get_session_profile(self):
        """Test getting complete session profile"""
        profile = self.session_profile.get_session_profile(session="LONDON")
        
        self.assertIn('session', profile)
        self.assertIn('volatility_tier', profile)
        self.assertIn('liquidity_timing', profile)
        self.assertIn('typical_behavior', profile)
        self.assertIn('best_strategy_type', profile)
        self.assertIn('session_bias_factor', profile)
        
        self.assertEqual(profile['session'], "LONDON")
        self.assertIn(profile['volatility_tier'], ['LOW', 'NORMAL', 'HIGH', 'VERY_HIGH'])
        self.assertIn(profile['liquidity_timing'], ['ACTIVE', 'MODERATE', 'LOW'])
    
    def test_get_session_bias_factor(self):
        """Test session bias factor calculation"""
        # Asian should have lower bias (looser threshold)
        bias_asian = self.session_profile.get_session_bias_factor("ASIAN")
        self.assertLess(bias_asian, 1.0)
        
        # Overlap should have higher bias (stricter threshold)
        bias_overlap = self.session_profile.get_session_bias_factor("OVERLAP")
        self.assertGreater(bias_overlap, 1.0)
        
        # London and NY should be neutral
        bias_london = self.session_profile.get_session_bias_factor("LONDON")
        self.assertEqual(bias_london, 1.0)
    
    def test_get_session_bias_factor_with_symbol(self):
        """Test session bias factor with symbol-specific adjustments"""
        # XAUUSD during overlap should be stricter
        bias_xau_overlap = self.session_profile.get_session_bias_factor("OVERLAP", "XAUUSD")
        self.assertGreater(bias_xau_overlap, 1.0)
        
        # BTCUSD during Asian should be looser
        bias_btc_asian = self.session_profile.get_session_bias_factor("ASIAN", "BTCUSD")
        self.assertLess(bias_btc_asian, 1.0)
    
    def test_get_atr_multiplier_adjustment(self):
        """Test ATR multiplier adjustment"""
        # Asian should have lower ATR
        atr_asian = self.session_profile.get_atr_multiplier_adjustment("ASIAN")
        self.assertLess(atr_asian, 1.0)
        
        # Overlap should have higher ATR
        atr_overlap = self.session_profile.get_atr_multiplier_adjustment("OVERLAP")
        self.assertGreater(atr_overlap, 1.0)
    
    def test_get_vwap_stretch_tolerance(self):
        """Test VWAP stretch tolerance"""
        # Asian should have tighter tolerance
        vwap_asian = self.session_profile.get_vwap_stretch_tolerance("ASIAN")
        self.assertLess(vwap_asian, 1.0)
        
        # Overlap should have looser tolerance
        vwap_overlap = self.session_profile.get_vwap_stretch_tolerance("OVERLAP")
        self.assertGreater(vwap_overlap, 1.0)
    
    def test_is_good_time_to_trade(self):
        """Test good time to trade check"""
        # Asian should be False for most symbols
        is_good_asian = self.session_profile.is_good_time_to_trade("ASIAN", "XAUUSD")
        self.assertFalse(is_good_asian)
        
        # BTCUSD should be True even in Asian (24/7)
        is_good_btc_asian = self.session_profile.is_good_time_to_trade("ASIAN", "BTCUSD")
        self.assertTrue(is_good_btc_asian)
        
        # London should be True
        is_good_london = self.session_profile.is_good_time_to_trade("LONDON", "XAUUSD")
        self.assertTrue(is_good_london)
        
        # Overlap should be True
        is_good_overlap = self.session_profile.is_good_time_to_trade("OVERLAP", "XAUUSD")
        self.assertTrue(is_good_overlap)
    
    def test_get_session_context(self):
        """Test getting complete session context"""
        context = self.session_profile.get_session_context(symbol="XAUUSD")
        
        self.assertIn('session', context)
        self.assertIn('volatility_tier', context)
        self.assertIn('liquidity_timing', context)
        self.assertIn('session_bias_factor', context)
        self.assertIn('atr_multiplier_adjustment', context)
        self.assertIn('vwap_stretch_tolerance', context)
        self.assertIn('is_good_time_to_trade', context)
    
    def test_session_profile_all_sessions(self):
        """Test profile for all session types"""
        sessions = ["ASIAN", "LONDON", "OVERLAP", "NY", "POST_NY"]
        
        for session in sessions:
            profile = self.session_profile.get_session_profile(session=session)
            
            self.assertEqual(profile['session'], session)
            self.assertIn(profile['volatility_tier'], ['LOW', 'NORMAL', 'HIGH', 'VERY_HIGH'])
            self.assertIn(profile['liquidity_timing'], ['ACTIVE', 'MODERATE', 'LOW'])
            self.assertIsInstance(profile['session_bias_factor'], float)
            self.assertGreaterEqual(profile['session_bias_factor'], 0.8)
            self.assertLessEqual(profile['session_bias_factor'], 1.2)
    
    def test_integration_with_existing_session_manager(self):
        """Test integration with existing session manager"""
        # Create mock session manager
        mock_session_manager = Mock()
        mock_session_manager.get_session_info.return_value = type('obj', (object,), {
            'primary_session': 'london',
            'is_overlap': False
        })()
        
        profile_with_manager = SessionVolatilityProfile(session_manager=mock_session_manager)
        session = profile_with_manager.get_current_session()
        
        # Should use session manager if available
        self.assertIsNotNone(session)
        self.assertIn(session, ["ASIAN", "LONDON", "NY", "OVERLAP", "POST_NY"])


if __name__ == '__main__':
    unittest.main()

