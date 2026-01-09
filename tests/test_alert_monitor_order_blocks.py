"""
Test Alert Monitor Order Block Detection

Tests comprehensive order block detection with 10-parameter validation.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from infra.alert_monitor import AlertMonitor
from infra.custom_alerts import CustomAlert, AlertType, AlertCondition


class TestAlertMonitorOrderBlocks(unittest.TestCase):
    """Test order block detection in AlertMonitor"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock dependencies
        self.mock_alert_manager = Mock()
        self.mock_mt5_service = Mock()
        self.mock_m1_data_fetcher = Mock()
        self.mock_m1_analyzer = Mock()
        self.mock_session_manager = Mock()
        
        # Create AlertMonitor instance
        self.alert_monitor = AlertMonitor(
            alert_manager=self.mock_alert_manager,
            mt5_service=self.mock_mt5_service,
            m1_data_fetcher=self.mock_m1_data_fetcher,
            m1_analyzer=self.mock_m1_analyzer,
            session_manager=self.mock_session_manager
        )
    
    def _generate_mock_m1_candles(self, count=200, trend="bullish"):
        """Generate mock M1 candles"""
        candles = []
        base_price = 4080.0 if trend == "bullish" else 4100.0
        
        for i in range(count):
            if trend == "bullish":
                open_price = base_price - (i * 0.1)
                close_price = open_price + 0.5
                high_price = close_price + 0.3
                low_price = open_price - 0.2
            else:  # bearish
                open_price = base_price + (i * 0.1)
                close_price = open_price - 0.5
                high_price = open_price + 0.2
                low_price = close_price - 0.3
            
            candles.append({
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': 100 + (i % 50),
                'timestamp': datetime.now(timezone.utc),
                'symbol': 'XAUUSDc'
            })
        
        return candles
    
    def _generate_order_block_m1_analysis(self, direction="BULLISH"):
        """Generate mock M1 analysis with order block"""
        return {
            'available': True,
            'order_blocks': [{
                'type': direction,
                'price_range': [4075.0, 4085.0] if direction == "BULLISH" else [4095.0, 4105.0],
                'strength': 85
            }],
            'choch_bos': {
                'has_choch': True,
                'has_bos': True,
                'choch_bull': direction == "BULLISH",
                'choch_bear': direction == "BEARISH",
                'choch_confirmed': True,
                'choch_bos_combo': True,
                'last_swing_high': 4090.0 if direction == "BULLISH" else 4100.0,
                'last_swing_low': 4070.0 if direction == "BULLISH" else 4090.0,
                'confidence': 85
            },
            'volatility': {
                'state': 'EXPANDING',
                'atr': 5.0,
                'atr_median': 4.5
            },
            'structure': {
                'type': 'TRENDING',
                'quality': 'GOOD'
            }
        }
    
    def test_order_block_alert_ob_bull_pattern(self):
        """Test order block alert with ob_bull pattern"""
        # Create alert
        alert = CustomAlert(
            alert_id="test_ob_bull",
            symbol="XAUUSDc",
            alert_type=AlertType.STRUCTURE,
            condition=AlertCondition.DETECTED,
            description="Bullish Order Block",
            parameters={"pattern": "ob_bull"},
            created_at=datetime.now().isoformat(),
            enabled=True
        )
        
        # Mock M1 data with proper anchor candle setup
        m1_candles = self._generate_mock_m1_candles(200, "bullish")
        
        # Set up anchor candle and displacement
        anchor_idx = len(m1_candles) - 10
        m1_candles[anchor_idx]['open'] = 4080.0
        m1_candles[anchor_idx]['close'] = 4078.0  # Down candle
        m1_candles[anchor_idx]['high'] = 4081.0
        m1_candles[anchor_idx]['low'] = 4077.0
        m1_candles[anchor_idx + 1]['open'] = 4078.0
        m1_candles[anchor_idx + 1]['close'] = 4085.0  # Strong displacement
        m1_candles[anchor_idx + 1]['high'] = 4086.0
        m1_candles[anchor_idx + 1]['low'] = 4077.5
        m1_candles[anchor_idx + 1]['volume'] = 500  # High volume
        
        # Set low average volume
        for i in range(max(0, anchor_idx - 20), anchor_idx):
            m1_candles[i]['volume'] = 50
        
        # Set up FVG (candle1 high < candle3 low)
        m1_candles[anchor_idx + 1]['high'] = 4078.0
        m1_candles[anchor_idx + 2]['low'] = 4080.0
        m1_candles[anchor_idx + 2]['high'] = 4082.0
        m1_candles[anchor_idx + 3]['low'] = 4083.0  # FVG gap
        
        m1_analysis = self._generate_order_block_m1_analysis("BULLISH")
        # Update OB range to match anchor candle
        m1_analysis['order_blocks'][0]['price_range'] = [4077.0, 4081.0]
        
        self.mock_m1_data_fetcher.fetch_m1_data.return_value = m1_candles
        self.mock_m1_analyzer.analyze_microstructure.return_value = m1_analysis
        self.mock_session_manager.get_current_session.return_value = "LONDON"
        self.mock_mt5_service.get_quote.return_value = Mock(ask=4082.0, bid=4081.0)
        
        # Mock multi_data with M5 candles
        multi_data = {
            "M5": {
                "highs": [4090.0, 4095.0, 4100.0],
                "lows": [4070.0, 4075.0, 4080.0],
                "closes": [4085.0, 4090.0, 4095.0],
                "opens": [4080.0, 4085.0, 4090.0]
            }
        }
        
        # Test
        result = self.alert_monitor._check_order_block_alert(
            alert, "XAUUSDc", 4082.0, multi_data
        )
        
        # Assert
        self.assertIsNotNone(result, "Order block should be detected")
        self.assertEqual(result['order_block_type'], "BULLISH")
        self.assertIn('validation_score', result, "Result should contain validation_score")
        self.assertGreaterEqual(result.get('validation_score', 0), 60, "Validation score should be >= 60")
    
    def test_order_block_alert_ob_bear_pattern(self):
        """Test order block alert with ob_bear pattern"""
        # Create alert
        alert = CustomAlert(
            alert_id="test_ob_bear",
            symbol="BTCUSDc",
            alert_type=AlertType.STRUCTURE,
            condition=AlertCondition.DETECTED,
            description="Bearish Order Block",
            parameters={"pattern": "ob_bear"},
            created_at=datetime.now().isoformat(),
            enabled=True
        )
        
        # Mock M1 data with proper anchor candle setup
        m1_candles = self._generate_mock_m1_candles(200, "bearish")
        
        # Set up anchor candle and displacement
        anchor_idx = len(m1_candles) - 10
        m1_candles[anchor_idx]['open'] = 93000.0
        m1_candles[anchor_idx]['close'] = 93020.0  # Up candle
        m1_candles[anchor_idx]['high'] = 93025.0
        m1_candles[anchor_idx]['low'] = 92995.0
        m1_candles[anchor_idx + 1]['open'] = 93020.0
        m1_candles[anchor_idx + 1]['close'] = 92950.0  # Strong bearish displacement
        m1_candles[anchor_idx + 1]['high'] = 93020.5
        m1_candles[anchor_idx + 1]['low'] = 92945.0
        m1_candles[anchor_idx + 1]['volume'] = 500  # High volume
        
        # Set low average volume
        for i in range(max(0, anchor_idx - 20), anchor_idx):
            m1_candles[i]['volume'] = 50
        
        # Set up FVG
        m1_candles[anchor_idx + 1]['low'] = 93020.0
        m1_candles[anchor_idx + 2]['high'] = 92980.0
        
        m1_analysis = self._generate_order_block_m1_analysis("BEARISH")
        # Update OB range to match anchor candle
        m1_analysis['order_blocks'][0]['price_range'] = [92995.0, 93025.0]
        
        self.mock_m1_data_fetcher.fetch_m1_data.return_value = m1_candles
        self.mock_m1_analyzer.analyze_microstructure.return_value = m1_analysis
        self.mock_session_manager.get_current_session.return_value = "NY"
        self.mock_mt5_service.get_quote.return_value = Mock(ask=93000.0, bid=92999.0)
        
        # Mock multi_data with M5 candles (bearish trend)
        multi_data = {
            "M5": {
                "highs": [93500.0, 93400.0, 93300.0],
                "lows": [93000.0, 92900.0, 92800.0],
                "closes": [93200.0, 93100.0, 93000.0],
                "opens": [93300.0, 93200.0, 93100.0]
            }
        }
        
        # Test
        result = self.alert_monitor._check_order_block_alert(
            alert, "BTCUSDc", 93000.0, multi_data
        )
        
        # Assert
        self.assertIsNotNone(result, "Order block should be detected")
        self.assertEqual(result['order_block_type'], "BEARISH")
    
    def test_order_block_validation_anchor_candle(self):
        """Test anchor candle identification"""
        m1_candles = self._generate_mock_m1_candles(200, "bullish")
        
        # Create a clear anchor candle scenario: down candle followed by up displacement
        # Set up last few candles to have a clear pattern
        m1_candles[-3]['open'] = 4080.0
        m1_candles[-3]['close'] = 4078.0  # Down candle
        m1_candles[-3]['high'] = 4081.0
        m1_candles[-3]['low'] = 4077.0
        m1_candles[-2]['open'] = 4078.0
        m1_candles[-2]['close'] = 4085.0  # Strong up displacement
        m1_candles[-2]['high'] = 4086.0
        m1_candles[-2]['low'] = 4077.5
        
        # Test bullish anchor candle
        anchor_idx = self.alert_monitor._find_anchor_candle(
            m1_candles, "BULLISH", 4077.0, 4081.0
        )
        
        # Should find a candle in the range
        self.assertIsNotNone(anchor_idx, "Should find anchor candle")
        self.assertGreaterEqual(anchor_idx, 0)
        self.assertLess(anchor_idx, len(m1_candles))
    
    def test_order_block_validation_fvg_detection(self):
        """Test FVG (Fair Value Gap) detection"""
        m1_candles = self._generate_mock_m1_candles(200, "bullish")
        
        # Create FVG scenario: candle1 high < candle3 low
        m1_candles[-3]['high'] = 4080.0
        m1_candles[-2]['low'] = 4081.0
        m1_candles[-2]['high'] = 4082.0
        m1_candles[-1]['low'] = 4083.0
        
        anchor_idx = len(m1_candles) - 3
        fvg_detected = self.alert_monitor._detect_fvg_after_displacement(
            m1_candles, anchor_idx, "BULLISH"
        )
        
        self.assertTrue(fvg_detected, "Should detect FVG")
    
    def test_order_block_validation_volume_spike(self):
        """Test volume spike detection"""
        m1_candles = self._generate_mock_m1_candles(200, "bullish")
        
        # Set high volume on displacement candle
        anchor_idx = len(m1_candles) - 10
        m1_candles[anchor_idx + 1]['volume'] = 500  # High volume
        
        # Set low average volume
        for i in range(max(0, anchor_idx - 20), anchor_idx):
            m1_candles[i]['volume'] = 50  # Low volume
        
        volume_spike = self.alert_monitor._check_volume_spike(m1_candles, anchor_idx)
        self.assertTrue(volume_spike, "Should detect volume spike")
    
    def test_order_block_validation_liquidity_grab(self):
        """Test liquidity grab detection"""
        m1_candles = self._generate_mock_m1_candles(200, "bullish")
        
        # Create liquidity grab: large lower wick
        anchor_idx = len(m1_candles) - 5
        displacement_candle = m1_candles[anchor_idx + 1]
        displacement_candle['open'] = 4080.0
        displacement_candle['close'] = 4082.0
        displacement_candle['high'] = 4082.5
        displacement_candle['low'] = 4075.0  # Large lower wick
        
        liquidity_grab = self.alert_monitor._detect_liquidity_grab(
            m1_candles, anchor_idx, "BULLISH"
        )
        
        self.assertTrue(liquidity_grab, "Should detect liquidity grab")
    
    def test_order_block_validation_session_context(self):
        """Test session context validation"""
        # Test strong session
        self.mock_session_manager.get_current_session.return_value = "LONDON"
        score = self.alert_monitor._validate_session_context("XAUUSDc")
        self.assertGreater(score, 5, "London session should score higher")
        
        # Test weak session
        self.mock_session_manager.get_current_session.return_value = "ASIAN"
        score = self.alert_monitor._validate_session_context("XAUUSDc")
        self.assertLess(score, 5, "Asian session should score lower")
    
    def test_order_block_validation_htf_alignment(self):
        """Test higher timeframe alignment"""
        m5_candles = [
            {'close': 4080.0},
            {'close': 4085.0},
            {'close': 4090.0},
            {'close': 4095.0},
            {'close': 4100.0}
        ]
        
        # Bullish alignment (need at least 10 candles for check)
        m5_candles_extended = [{'close': 4070.0 + (i * 2.0)} for i in range(10)]
        alignment = self.alert_monitor._check_htf_alignment(
            m5_candles_extended, None, "BULLISH"
        )
        self.assertTrue(alignment, "Should detect bullish HTF alignment")
        
        # Bearish alignment
        m5_candles_reverse = [{'close': 4100.0 - (i * 2.0)} for i in range(10)]
        alignment = self.alert_monitor._check_htf_alignment(
            m5_candles_reverse, None, "BEARISH"
        )
        self.assertTrue(alignment, "Should detect bearish HTF alignment")
    
    def test_order_block_validation_structural_context(self):
        """Test structural context validation"""
        m1_analysis = {
            'structure': {'type': 'TRENDING', 'quality': 'GOOD'},
            'volatility': {'state': 'EXPANDING'}
        }
        
        m1_candles = self._generate_mock_m1_candles(200, "bullish")
        
        # Good structural context
        context = self.alert_monitor._validate_structural_context(
            m1_candles, m1_analysis, "BULLISH"
        )
        self.assertTrue(context, "Should validate good structural context")
        
        # Bad structural context (choppy)
        m1_analysis['structure']['type'] = 'CHOPPY'
        m1_analysis['volatility']['state'] = 'CONTRACTING'
        context = self.alert_monitor._validate_structural_context(
            m1_candles, m1_analysis, "BULLISH"
        )
        self.assertFalse(context, "Should reject choppy structural context")
    
    def test_order_block_validation_freshness(self):
        """Test order block freshness check"""
        # First check should be fresh
        fresh = self.alert_monitor._check_ob_freshness("XAUUSDc", 4075.0, 4085.0)
        self.assertTrue(fresh, "First OB should be fresh")
        
        # Manually add to cache to simulate detection
        ob_key = f"XAUUSDc_4075.00_4085.00"
        if "XAUUSDc" not in self.alert_monitor._detected_ob_cache:
            self.alert_monitor._detected_ob_cache["XAUUSDc"] = []
        self.alert_monitor._detected_ob_cache["XAUUSDc"].append(ob_key)
        
        # Second check (same zone) should not be fresh
        fresh = self.alert_monitor._check_ob_freshness("XAUUSDc", 4075.0, 4085.0)
        self.assertFalse(fresh, "Same OB should not be fresh")
        
        # Different zone should still be fresh
        fresh = self.alert_monitor._check_ob_freshness("XAUUSDc", 4095.0, 4105.0)
        self.assertTrue(fresh, "Different OB should be fresh")
    
    def test_order_block_validation_vwap_confluence(self):
        """Test VWAP + liquidity confluence"""
        m1_analysis = {
            'volatility': {'atr': 5.0}
        }
        
        # OB within 0.5 ATR of current price
        current_price = 4080.0
        ob_low = 4078.0
        ob_high = 4082.0
        
        confluence = self.alert_monitor._check_vwap_liquidity_confluence(
            m1_analysis, ob_low, ob_high, current_price
        )
        self.assertTrue(confluence, "Should detect VWAP confluence")
        
        # OB too far from current price
        ob_low = 4050.0
        ob_high = 4055.0
        
        confluence = self.alert_monitor._check_vwap_liquidity_confluence(
            m1_analysis, ob_low, ob_high, current_price
        )
        self.assertFalse(confluence, "Should reject OB too far from price")
    
    def test_order_block_validation_comprehensive(self):
        """Test comprehensive order block validation"""
        m1_candles = self._generate_mock_m1_candles(200, "bullish")
        m1_analysis = self._generate_order_block_m1_analysis("BULLISH")
        
        # Create order block
        ob = {
            'type': 'BULLISH',
            'price_range': [4075.0, 4085.0],
            'strength': 85
        }
        
        # Set up anchor candle scenario
        anchor_idx = len(m1_candles) - 10
        m1_candles[anchor_idx]['open'] = 4080.0
        m1_candles[anchor_idx]['close'] = 4078.0  # Down candle
        m1_candles[anchor_idx]['high'] = 4081.0
        m1_candles[anchor_idx]['low'] = 4077.0
        m1_candles[anchor_idx + 1]['open'] = 4078.0
        m1_candles[anchor_idx + 1]['close'] = 4085.0  # Displacement
        m1_candles[anchor_idx + 1]['high'] = 4086.0
        m1_candles[anchor_idx + 1]['low'] = 4077.5
        
        # Set up FVG and volume spike
        m1_candles[anchor_idx + 1]['high'] = 4078.0
        m1_candles[anchor_idx + 2]['low'] = 4080.0
        m1_candles[anchor_idx + 2]['high'] = 4082.0
        m1_candles[anchor_idx + 3]['low'] = 4083.0
        m1_candles[anchor_idx + 1]['volume'] = 500
        
        # Set low average volume
        for i in range(max(0, anchor_idx - 20), anchor_idx):
            m1_candles[i]['volume'] = 50
        
        # Mock M5 candles (need 10+ for alignment check)
        m5_candles = [{'close': 4070.0 + (i * 2.0)} for i in range(10)]
        
        # Mock session manager
        self.mock_session_manager.get_current_session.return_value = "LONDON"
        
        # Validate
        result = self.alert_monitor._validate_order_block(
            ob=ob,
            m1_candles=m1_candles,
            m5_candles=m5_candles,
            m1_analysis=m1_analysis,
            m5_data=None,
            symbol_norm="XAUUSDc",
            current_price=4080.0
        )
        
        # Should pass validation (score >= 60)
        self.assertIsNotNone(result, "Should validate order block")
        self.assertTrue(result.get('valid'), "Order block should be valid")
        self.assertGreaterEqual(result.get('score', 0), 60, "Score should be >= 60")
    
    def test_order_block_validation_fails_mandatory_structure(self):
        """Test that validation fails without mandatory structure shift"""
        m1_candles = self._generate_mock_m1_candles(200, "bullish")
        
        # M1 analysis without structure shift
        m1_analysis = {
            'available': True,
            'order_blocks': [{
                'type': 'BULLISH',
                'price_range': [4075.0, 4085.0],
                'strength': 85
            }],
            'choch_bos': {
                'has_choch': False,  # No structure shift
                'has_bos': False,
                'choch_bull': False,
                'choch_bear': False,
                'choch_confirmed': False,
                'choch_bos_combo': False,
                'confidence': 0
            },
            'volatility': {'state': 'EXPANDING', 'atr': 5.0},
            'structure': {'type': 'TRENDING'}
        }
        
        ob = {
            'type': 'BULLISH',
            'price_range': [4075.0, 4085.0],
            'strength': 85
        }
        
        result = self.alert_monitor._validate_order_block(
            ob=ob,
            m1_candles=m1_candles,
            m5_candles=None,
            m1_analysis=m1_analysis,
            m5_data=None,
            symbol_norm="XAUUSDc",
            current_price=4080.0
        )
        
        # Should fail (no structure shift = mandatory check failed)
        self.assertIsNone(result, "Should reject OB without structure shift")
    
    def test_order_block_validation_low_score(self):
        """Test that validation fails with low score"""
        m1_candles = self._generate_mock_m1_candles(200, "bullish")
        
        # M1 analysis with minimal validation points
        m1_analysis = {
            'available': True,
            'order_blocks': [{
                'type': 'BULLISH',
                'price_range': [4075.0, 4085.0],
                'strength': 50
            }],
            'choch_bos': {
                'has_choch': True,
                'has_bos': True,
                'choch_bull': True,
                'choch_confirmed': True,
                'choch_bos_combo': False,
                'confidence': 60
            },
            'volatility': {
                'state': 'CONTRACTING',  # Bad context
                'atr': 5.0
            },
            'structure': {
                'type': 'CHOPPY',  # Bad context
                'quality': 'POOR'
            }
        }
        
        ob = {
            'type': 'BULLISH',
            'price_range': [4075.0, 4085.0],
            'strength': 50
        }
        
        # Set low volume (no spike)
        for i in range(len(m1_candles)):
            m1_candles[i]['volume'] = 50
        
        result = self.alert_monitor._validate_order_block(
            ob=ob,
            m1_candles=m1_candles,
            m5_candles=None,
            m1_analysis=m1_analysis,
            m5_data=None,
            symbol_norm="XAUUSDc",
            current_price=4080.0
        )
        
        # Should fail (score < 60)
        self.assertIsNone(result, "Should reject OB with low validation score")
    
    def test_order_block_alert_no_m1_components(self):
        """Test that order block detection gracefully handles missing M1 components"""
        # Create alert monitor without M1 components
        alert_monitor_no_m1 = AlertMonitor(
            alert_manager=self.mock_alert_manager,
            mt5_service=self.mock_mt5_service
        )
        
        alert = CustomAlert(
            alert_id="test_no_m1",
            symbol="XAUUSDc",
            alert_type=AlertType.STRUCTURE,
            condition=AlertCondition.DETECTED,
            description="Order Block",
            parameters={"pattern": "ob_bull"},
            created_at=datetime.now().isoformat(),
            enabled=True
        )
        
        result = alert_monitor_no_m1._check_order_block_alert(
            alert, "XAUUSDc", 4080.0, {}
        )
        
        # Should return None gracefully
        self.assertIsNone(result, "Should return None when M1 components unavailable")
    
    def test_order_block_alert_insufficient_data(self):
        """Test order block detection with insufficient M1 data"""
        alert = CustomAlert(
            alert_id="test_insufficient",
            symbol="XAUUSDc",
            alert_type=AlertType.STRUCTURE,
            condition=AlertCondition.DETECTED,
            description="Order Block",
            parameters={"pattern": "ob_bull"},
            created_at=datetime.now().isoformat(),
            enabled=True
        )
        
        # Mock insufficient data
        self.mock_m1_data_fetcher.fetch_m1_data.return_value = []  # No candles
        self.mock_mt5_service.get_quote.return_value = Mock(ask=4080.0, bid=4079.0)
        
        result = self.alert_monitor._check_order_block_alert(
            alert, "XAUUSDc", 4080.0, {}
        )
        
        # Should return None
        self.assertIsNone(result, "Should return None with insufficient data")
    
    def test_order_block_alert_no_order_blocks_detected(self):
        """Test when no order blocks are detected in M1 analysis"""
        alert = CustomAlert(
            alert_id="test_no_obs",
            symbol="XAUUSDc",
            alert_type=AlertType.STRUCTURE,
            condition=AlertCondition.DETECTED,
            description="Order Block",
            parameters={"pattern": "ob_bull"},
            created_at=datetime.now().isoformat(),
            enabled=True
        )
        
        m1_candles = self._generate_mock_m1_candles(200, "bullish")
        m1_analysis = {
            'available': True,
            'order_blocks': [],  # No order blocks
            'choch_bos': {'has_choch': False, 'has_bos': False}
        }
        
        self.mock_m1_data_fetcher.fetch_m1_data.return_value = m1_candles
        self.mock_m1_analyzer.analyze_microstructure.return_value = m1_analysis
        self.mock_mt5_service.get_quote.return_value = Mock(ask=4080.0, bid=4079.0)
        
        result = self.alert_monitor._check_order_block_alert(
            alert, "XAUUSDc", 4080.0, {}
        )
        
        # Should return None
        self.assertIsNone(result, "Should return None when no order blocks detected")


if __name__ == '__main__':
    unittest.main()

