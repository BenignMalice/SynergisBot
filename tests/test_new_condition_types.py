"""
Test new condition types for auto-execution plans
Tests: liquidity_sweep, vwap_deviation, ema_slope, volatility_state
"""

import unittest
from unittest.mock import MagicMock, Mock, patch
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auto_execution_system import AutoExecutionSystem, TradePlan
from infra.mt5_service import MT5Service


class TestNewConditionTypes(unittest.TestCase):
    """Test new condition types"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock MT5 service
        self.mock_mt5 = MagicMock()
        self.mock_mt5.connect.return_value = True
        mock_quote = Mock()
        mock_quote.bid = 4080.0
        mock_quote.ask = 4081.0
        self.mock_mt5.get_quote.return_value = mock_quote
        
        # Mock M1 components
        self.mock_m1_analyzer = MagicMock()
        self.mock_m1_data_fetcher = MagicMock()
        
        # Create system
        self.system = AutoExecutionSystem(
            mt5_service=self.mock_mt5,
            m1_analyzer=self.mock_m1_analyzer,
            m1_data_fetcher=self.mock_m1_data_fetcher
        )
    
    def test_liquidity_sweep_condition(self):
        """Test liquidity_sweep condition"""
        # Mock M1 data with liquidity sweep
        mock_m1_candles = [{'open': 4080, 'high': 4085, 'low': 4075, 'close': 4082} for _ in range(200)]
        self.mock_m1_data_fetcher.fetch_m1_data.return_value = mock_m1_candles
        
        mock_m1_analysis = {
            'available': True,
            'liquidity_zones': [
                {'type': 'PDL', 'price': 4075.0, 'touches': 3}
            ],
            'liquidity_state': 'NEAR_PDL'
        }
        self.mock_m1_analyzer.analyze_microstructure.return_value = mock_m1_analysis
        
        # Create plan with liquidity_sweep condition
        plan = TradePlan(
            plan_id="test_sweep",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=4080.0,
            stop_loss=4070.0,
            take_profit=4090.0,
            volume=0.01,
            conditions={
                "liquidity_sweep": True,
                "price_near": 4080.0,
                "tolerance": 5.0
            },
            created_at=datetime.now().isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock _detect_liquidity_sweep to return True
        self.system._detect_liquidity_sweep = MagicMock(return_value=True)
        
        result = self.system._check_conditions(plan)
        self.assertTrue(result, "Liquidity sweep condition should pass")
    
    def test_vwap_deviation_condition(self):
        """Test vwap_deviation condition"""
        # Mock M1 data
        mock_m1_candles = [{'open': 4080, 'high': 4085, 'low': 4075, 'close': 4082} for _ in range(200)]
        self.mock_m1_data_fetcher.fetch_m1_data.return_value = mock_m1_candles
        
        # Mock VWAP deviation (price 2.5σ above VWAP)
        mock_m1_analysis = {
            'available': True,
            'vwap': {
                'value': 4070.0,
                'std': 5.0
            }
        }
        self.mock_m1_analyzer.analyze_microstructure.return_value = mock_m1_analysis
        
        plan = TradePlan(
            plan_id="test_vwap",
            symbol="XAUUSDc",
            direction="SELL",
            entry_price=4082.5,
            stop_loss=4090.0,
            take_profit=4070.0,
            volume=0.01,
            conditions={
                "vwap_deviation": True,
                "vwap_deviation_threshold": 2.0,
                "vwap_deviation_direction": "above"
            },
            created_at=datetime.now().isoformat(),
            created_by="test",
            status="pending"
        )
        
        result = self.system._check_conditions(plan)
        # Current price (4081) is 2.2σ above VWAP (4070), so should pass
        self.assertTrue(result, "VWAP deviation condition should pass")
    
    def test_ema_slope_condition(self):
        """Test ema_slope condition"""
        # Mock MT5 candles for EMA calculation
        with patch('auto_execution_system.mt5') as mock_mt5:
            import MetaTrader5 as mt5
            mock_mt5.TIMEFRAME_H1 = mt5.TIMEFRAME_H1
            
            # Create bullish EMA slope (rising prices)
            mock_candles = []
            base_price = 100.0
            for i in range(250):
                price = base_price + (i * 0.1)  # Rising trend
                mock_candles.append({
                    'open': price - 0.05,
                    'high': price + 0.05,
                    'low': price - 0.1,
                    'close': price
                })
            
            mock_mt5.copy_rates_from_pos.return_value = mock_candles
            
            plan = TradePlan(
                plan_id="test_ema",
                symbol="EURUSDc",
                direction="BUY",
                entry_price=125.0,
                stop_loss=120.0,
                take_profit=130.0,
                volume=0.01,
                conditions={
                    "ema_slope": True,
                    "ema_period": 200,
                    "ema_timeframe": "H1",
                    "ema_slope_direction": "bullish",
                    "min_ema_slope_pct": 0.0
                },
                created_at=datetime.now().isoformat(),
                created_by="test",
                status="pending"
            )
            
            result = self.system._check_conditions(plan)
            self.assertTrue(result, "EMA slope condition should pass for bullish trend")
    
    def test_volatility_state_condition(self):
        """Test volatility_state condition"""
        # Mock M1 data
        mock_m1_candles = [{'open': 4080, 'high': 4085, 'low': 4075, 'close': 4082} for _ in range(200)]
        self.mock_m1_data_fetcher.fetch_m1_data.return_value = mock_m1_candles
        
        # Mock EXPANDING volatility state
        mock_m1_analysis = {
            'available': True,
            'volatility_state': 'EXPANDING'
        }
        self.mock_m1_analyzer.analyze_microstructure.return_value = mock_m1_analysis
        
        plan = TradePlan(
            plan_id="test_vol",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=92000.0,
            stop_loss=91000.0,
            take_profit=93000.0,
            volume=0.01,
            conditions={
                "volatility_state": "EXPANDING"
            },
            created_at=datetime.now().isoformat(),
            created_by="test",
            status="pending"
        )
        
        result = self.system._check_conditions(plan)
        self.assertTrue(result, "Volatility state condition should pass")


if __name__ == '__main__':
    unittest.main()

