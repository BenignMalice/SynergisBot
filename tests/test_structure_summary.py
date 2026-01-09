"""
Unit tests for calculate_structure_summary
"""

import unittest
from unittest.mock import Mock

# Import the function
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from desktop_agent import calculate_structure_summary


class TestStructureSummary(unittest.TestCase):
    """Test cases for structure summary calculation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.current_price = 4200.0
        
        # Sample M1 microstructure data
        self.m1_microstructure = {
            'available': True,
            'liquidity_zones': [
                {'type': 'PDH', 'price': 4210.0, 'touches': 3},
                {'type': 'PDL', 'price': 4190.0, 'touches': 2},
                {'type': 'EQUAL_HIGH', 'price': 4205.0, 'touches': 1}
            ],
            'structure': {
                'type': 'HIGHER_HIGH',
                'strength': 85
            },
            'choch_bos': {
                'has_choch': True,
                'has_bos': False,
                'choch_bull': False,
                'choch_bear': True,
                'confidence': 80
            },
            'volatility': {
                'state': 'STABLE'
            }
        }
        
        # Sample SMC data
        self.smc_data = {
            'trend': 'BULLISH',
            'timeframes': {
                'H4': {'bias': 'BULLISH'},
                'H1': {'bias': 'BULLISH'}
            }
        }
    
    def test_calculate_structure_summary_valid(self):
        """Test structure summary with valid data"""
        result = calculate_structure_summary(
            m1_microstructure=self.m1_microstructure,
            smc_data=self.smc_data,
            current_price=self.current_price
        )
        
        self.assertIsNotNone(result)
        self.assertIn("current_range_type", result)
        self.assertIn("range_state", result)
        self.assertIn("has_liquidity_sweep", result)
        self.assertIn("range_high", result)
        self.assertIn("range_low", result)
        self.assertIn("range_mid", result)
        
        # Check range boundaries
        self.assertEqual(result["range_high"], 4210.0)
        self.assertEqual(result["range_low"], 4190.0)
        self.assertEqual(result["range_mid"], 4200.0)
    
    def test_calculate_structure_summary_no_m1_data(self):
        """Test structure summary with no M1 data"""
        result = calculate_structure_summary(
            m1_microstructure=None,
            smc_data=self.smc_data,
            current_price=self.current_price
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result["current_range_type"], "balanced_range")
        self.assertEqual(result["range_state"], "mid_range")
        self.assertFalse(result["has_liquidity_sweep"])
        self.assertIsNone(result["range_high"])
    
    def test_calculate_structure_summary_unavailable_m1(self):
        """Test structure summary with unavailable M1 data"""
        m1_unavailable = {
            'available': False,
            'error': 'Insufficient data'
        }
        
        result = calculate_structure_summary(
            m1_microstructure=m1_unavailable,
            smc_data=self.smc_data,
            current_price=self.current_price
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result["current_range_type"], "balanced_range")
        self.assertFalse(result["has_liquidity_sweep"])
    
    def test_calculate_structure_summary_range_type_trend_channel(self):
        """Test range type detection for trend channel"""
        m1_trend = self.m1_microstructure.copy()
        m1_trend['structure'] = {'type': 'HIGHER_HIGH', 'strength': 90}
        
        result = calculate_structure_summary(
            m1_microstructure=m1_trend,
            smc_data={'trend': 'BULLISH'},
            current_price=self.current_price
        )
        
        self.assertEqual(result["current_range_type"], "trend_channel")
    
    def test_calculate_structure_summary_range_type_breakout(self):
        """Test range type detection for breakout"""
        m1_breakout = self.m1_microstructure.copy()
        m1_breakout['structure'] = {'type': 'CHOPPY', 'strength': 50}
        m1_breakout['choch_bos'] = {'has_bos': True, 'has_choch': False}
        
        result = calculate_structure_summary(
            m1_microstructure=m1_breakout,
            smc_data={'trend': 'BULLISH'},
            current_price=self.current_price
        )
        
        self.assertEqual(result["current_range_type"], "breakout")
    
    def test_calculate_structure_summary_range_type_accumulation(self):
        """Test range type detection for accumulation"""
        m1_accumulation = self.m1_microstructure.copy()
        m1_accumulation['volatility'] = {'state': 'CONTRACTING'}
        
        result = calculate_structure_summary(
            m1_microstructure=m1_accumulation,
            smc_data={'trend': 'RANGE'},
            current_price=self.current_price
        )
        
        self.assertEqual(result["current_range_type"], "accumulation")
    
    def test_calculate_structure_summary_liquidity_sweep_detection(self):
        """Test liquidity sweep detection"""
        m1_sweep = self.m1_microstructure.copy()
        m1_sweep['choch_bos'] = {
            'has_choch': True,
            'has_bos': False,
            'choch_bear': True,
            'confidence': 85
        }
        m1_sweep['structure'] = {'type': 'HIGHER_HIGH', 'strength': 90}
        
        result = calculate_structure_summary(
            m1_microstructure=m1_sweep,
            smc_data=self.smc_data,
            current_price=self.current_price
        )
        
        self.assertTrue(result["has_liquidity_sweep"])
        self.assertEqual(result["sweep_type"], "bear")
        self.assertIsNotNone(result["sweep_level"])
    
    def test_calculate_structure_summary_range_state_mid_range(self):
        """Test range state detection - mid range"""
        # Price at 50% of range (4200 is mid of 4190-4210)
        result = calculate_structure_summary(
            m1_microstructure=self.m1_microstructure,
            smc_data=self.smc_data,
            current_price=4200.0
        )
        
        self.assertEqual(result["range_state"], "mid_range")
    
    def test_calculate_structure_summary_range_state_near_high(self):
        """Test range state detection - near range high"""
        # Price at 75% of range
        result = calculate_structure_summary(
            m1_microstructure=self.m1_microstructure,
            smc_data=self.smc_data,
            current_price=4205.0
        )
        
        self.assertEqual(result["range_state"], "near_range_high")
    
    def test_calculate_structure_summary_range_state_near_low(self):
        """Test range state detection - near range low"""
        # Price at 25% of range
        result = calculate_structure_summary(
            m1_microstructure=self.m1_microstructure,
            smc_data=self.smc_data,
            current_price=4195.0
        )
        
        self.assertEqual(result["range_state"], "near_range_low")
    
    def test_calculate_structure_summary_range_state_just_broke(self):
        """Test range state detection - just broke range"""
        # Price above range with CHOCH/BOS detected
        result = calculate_structure_summary(
            m1_microstructure=self.m1_microstructure,
            smc_data=self.smc_data,
            current_price=4215.0  # Above range_high
        )
        
        self.assertEqual(result["range_state"], "just_broke_range")
    
    def test_calculate_structure_summary_discount_premium_state(self):
        """Test discount/premium state calculation"""
        # Price in premium zone (>66% of range)
        result = calculate_structure_summary(
            m1_microstructure=self.m1_microstructure,
            smc_data=self.smc_data,
            current_price=4208.0  # ~90% of range
        )
        
        self.assertEqual(result["discount_premium_state"], "seeking_premium_liquidity")
    
    def test_calculate_structure_summary_with_htf_levels(self):
        """Test structure summary with HTF levels"""
        htf_levels = {
            'previous_week_high': 4220.0,
            'previous_week_low': 4180.0,
            'previous_day_high': 4210.0,
            'previous_day_low': 4190.0,
            'price_position': 'premium'
        }
        
        # M1 without liquidity zones - should use HTF levels
        m1_no_zones = {
            'available': True,
            'liquidity_zones': [],
            'structure': {'type': 'CHOPPY', 'strength': 50},
            'choch_bos': {'has_choch': False, 'has_bos': False},
            'volatility': {'state': 'STABLE'}
        }
        
        result = calculate_structure_summary(
            m1_microstructure=m1_no_zones,
            smc_data=self.smc_data,
            current_price=self.current_price,
            htf_levels=htf_levels
        )
        
        self.assertEqual(result["range_high"], 4220.0)  # From weekly high
        self.assertEqual(result["range_low"], 4180.0)  # From weekly low
        self.assertEqual(result["discount_premium_state"], "seeking_premium_liquidity")  # From HTF price_position


if __name__ == '__main__':
    unittest.main()

