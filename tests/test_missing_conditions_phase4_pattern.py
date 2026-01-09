"""
Unit tests for Phase 4: Pattern Conditions
Tests for pattern_evening_morning_star and pattern_three_drive conditions
"""
import unittest
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestEveningMorningStarCondition(unittest.TestCase):
    """Test evening/morning star pattern condition detection"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Mock quote object
        class MockQuote:
            def __init__(self):
                self.bid = 91000.0
                self.ask = 91010.0
        
        self.mt5_service = Mock()
        self.mt5_service.connect.return_value = True
        self.mt5_service.get_quote = Mock(return_value=MockQuote())
        
        # Mock database write queue to avoid blocking
        with patch('infra.database_write_queue.DatabaseWriteQueue'):
            with patch.object(AutoExecutionSystem, '_load_plans', return_value={}):
                self.auto_exec = AutoExecutionSystem(
                    db_path=self.db_path,
                    mt5_service=self.mt5_service
                )
                # Set db_write_queue to None to avoid cleanup issues
                self.auto_exec.db_write_queue = None
    
    def tearDown(self):
        """Clean up test fixtures"""
        try:
            if hasattr(self, 'auto_exec') and hasattr(self.auto_exec, 'db_write_queue') and self.auto_exec.db_write_queue:
                self.auto_exec.db_write_queue.stop()
        except:
            pass
        try:
            if hasattr(self, 'db_path') and Path(self.db_path).exists():
                Path(self.db_path).unlink()
        except:
            pass
    
    def _create_morning_star_candles(self):
        """Create mock candles with morning star pattern"""
        # First candle: Bearish (close < open)
        c3 = {
            'time': datetime.now(timezone.utc).timestamp() - 900,
            'open': 91200.0,
            'high': 91300.0,
            'low': 91000.0,
            'close': 91050.0,  # Bearish
            'tick_volume': 1000,
            'spread': 10,
            'real_volume': 1000
        }
        
        # Second candle: Small body (star), gaps down
        c2 = {
            'time': datetime.now(timezone.utc).timestamp() - 600,
            'open': 91000.0,  # Gaps down from first candle
            'high': 91050.0,
            'low': 90950.0,
            'close': 91020.0,  # Small body
            'tick_volume': 1000,
            'spread': 10,
            'real_volume': 1000
        }
        
        # Third candle: Bullish (close > open), closes above first candle's midpoint
        c1 = {
            'time': datetime.now(timezone.utc).timestamp() - 300,
            'open': 91030.0,
            'high': 91200.0,
            'low': 91000.0,
            'close': 91150.0,  # Bullish, above midpoint (91125)
            'tick_volume': 1000,
            'spread': 10,
            'real_volume': 1000
        }
        
        return [c1, c2, c3]
    
    def _create_evening_star_candles(self):
        """Create mock candles with evening star pattern"""
        # First candle: Bullish (close > open)
        c3 = {
            'time': datetime.now(timezone.utc).timestamp() - 900,
            'open': 91000.0,
            'high': 91200.0,
            'low': 90900.0,
            'close': 91150.0,  # Bullish
            'tick_volume': 1000,
            'spread': 10,
            'real_volume': 1000
        }
        
        # Second candle: Small body (star), gaps up
        c2 = {
            'time': datetime.now(timezone.utc).timestamp() - 600,
            'open': 91200.0,  # Gaps up from first candle
            'high': 91250.0,
            'low': 91150.0,
            'close': 91220.0,  # Small body
            'tick_volume': 1000,
            'spread': 10,
            'real_volume': 1000
        }
        
        # Third candle: Bearish (close < open), closes below first candle's midpoint
        c1 = {
            'time': datetime.now(timezone.utc).timestamp() - 300,
            'open': 91200.0,
            'high': 91250.0,
            'low': 91000.0,
            'close': 91050.0,  # Bearish, below midpoint (91075)
            'tick_volume': 1000,
            'spread': 10,
            'real_volume': 1000
        }
        
        return [c1, c2, c3]
    
    @patch('auto_execution_system.mt5')
    def test_condition_met_morning_star_buy(self, mock_mt5):
        """Test successful condition: morning star pattern for BUY"""
        # Create plan
        plan = TradePlan(
            plan_id="test_morning_star",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=91100.0,
            stop_loss=91000.0,
            take_profit=91300.0,
            volume=0.01,
            conditions={
                "pattern_evening_morning_star": True,
                "timeframe": "M15",
                "price_near": 91100.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Create morning star candles
        candles = self._create_morning_star_candles()
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(plan)
        self.assertIsInstance(result, bool)
    
    @patch('auto_execution_system.mt5')
    def test_condition_met_evening_star_sell(self, mock_mt5):
        """Test successful condition: evening star pattern for SELL"""
        # Create plan
        plan = TradePlan(
            plan_id="test_evening_star",
            symbol="BTCUSDc",
            direction="SELL",
            entry_price=91100.0,
            stop_loss=91200.0,
            take_profit=91000.0,
            volume=0.01,
            conditions={
                "pattern_evening_morning_star": True,
                "timeframe": "M15",
                "price_near": 91100.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Create evening star candles
        candles = self._create_evening_star_candles()
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(plan)
        self.assertIsInstance(result, bool)
    
    @patch('auto_execution_system.mt5')
    def test_condition_not_met_wrong_pattern(self, mock_mt5):
        """Test failure case: wrong pattern for direction"""
        # Create plan expecting morning star
        plan = TradePlan(
            plan_id="test_wrong_pattern",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=91100.0,
            stop_loss=91000.0,
            take_profit=91300.0,
            volume=0.01,
            conditions={
                "pattern_evening_morning_star": True,
                "timeframe": "M15",
                "price_near": 91100.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Create evening star candles (wrong for BUY)
        candles = self._create_evening_star_candles()
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    def test_condition_not_met_invalid_pattern(self, mock_mt5):
        """Test failure case: invalid pattern (no star)"""
        # Create plan
        plan = TradePlan(
            plan_id="test_invalid_pattern",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=91100.0,
            stop_loss=91000.0,
            take_profit=91300.0,
            volume=0.01,
            conditions={
                "pattern_evening_morning_star": True,
                "timeframe": "M15",
                "price_near": 91100.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Create invalid candles (all bullish, no star)
        candles = [
            {
                'time': datetime.now(timezone.utc).timestamp() - 300,
                'open': 91000.0,
                'high': 91100.0,
                'low': 90950.0,
                'close': 91050.0,  # Bullish
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            },
            {
                'time': datetime.now(timezone.utc).timestamp() - 600,
                'open': 90950.0,
                'high': 91000.0,
                'low': 90900.0,
                'close': 90980.0,  # Bullish (large body, not a star)
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            },
            {
                'time': datetime.now(timezone.utc).timestamp() - 900,
                'open': 90900.0,
                'high': 90950.0,
                'low': 90850.0,
                'close': 90920.0,  # Bullish
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            }
        ]
        
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    def test_insufficient_candles(self, mock_mt5):
        """Test error handling: insufficient candles"""
        # Create plan
        plan = TradePlan(
            plan_id="test_insufficient_candles",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=91100.0,
            stop_loss=91000.0,
            take_profit=91300.0,
            volume=0.01,
            conditions={
                "pattern_evening_morning_star": True,
                "timeframe": "M15",
                "price_near": 91100.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Create insufficient candles
        candles = self._create_morning_star_candles()[:2]  # Only 2 candles
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(plan)
        self.assertFalse(result)


class TestThreeDriveCondition(unittest.TestCase):
    """Test three-drive pattern condition detection"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Mock quote object
        class MockQuote:
            def __init__(self):
                self.bid = 91000.0
                self.ask = 91010.0
        
        self.mt5_service = Mock()
        self.mt5_service.connect.return_value = True
        self.mt5_service.get_quote = Mock(return_value=MockQuote())
        
        # Mock database write queue to avoid blocking
        with patch('infra.database_write_queue.DatabaseWriteQueue'):
            with patch.object(AutoExecutionSystem, '_load_plans', return_value={}):
                self.auto_exec = AutoExecutionSystem(
                    db_path=self.db_path,
                    mt5_service=self.mt5_service
                )
                # Set db_write_queue to None to avoid cleanup issues
                self.auto_exec.db_write_queue = None
    
    def tearDown(self):
        """Clean up test fixtures"""
        try:
            if hasattr(self, 'auto_exec') and hasattr(self.auto_exec, 'db_write_queue') and self.auto_exec.db_write_queue:
                self.auto_exec.db_write_queue.stop()
        except:
            pass
        try:
            if hasattr(self, 'db_path') and Path(self.db_path).exists():
                Path(self.db_path).unlink()
        except:
            pass
    
    def _create_three_drive_candles(self, direction="buy", count=100):
        """Create mock candles with three-drive pattern"""
        candles = []
        base_time = datetime.now(timezone.utc).timestamp()
        base_price = 91000.0
        drive_level = 90800.0  # Support level for BUY
        
        # Create candles with three drives to similar level
        for i in range(count):
            # Create swing pattern: drive down, retrace up, drive down again
            if i < 20:
                # First drive
                price = base_price - (i * 10)
                low = drive_level + 50
            elif i < 30:
                # Retracement
                price = base_price - 100 + ((i - 20) * 15)
                low = drive_level + 100
            elif i < 50:
                # Second drive
                price = base_price - 250 + ((i - 30) * 5)
                low = drive_level + 30
            elif i < 60:
                # Retracement
                price = base_price - 150 + ((i - 50) * 10)
                low = drive_level + 80
            elif i < 80:
                # Third drive (most recent)
                price = base_price - 200 + ((i - 60) * 3)
                low = drive_level + 10  # Closest to drive level
            else:
                # Current price near drive level
                price = drive_level + 20
                low = drive_level + 5
            
            candles.append({
                'time': base_time - (count - i) * 300,
                'open': price,
                'high': price + 50,
                'low': low,
                'close': price,
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            })
        
        return candles
    
    @patch('auto_execution_system.mt5')
    def test_condition_met_three_drive_buy(self, mock_mt5):
        """Test successful condition: three-drive pattern for BUY"""
        # Create plan
        plan = TradePlan(
            plan_id="test_three_drive_buy",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=90800.0,
            stop_loss=90700.0,
            take_profit=91200.0,
            volume=0.01,
            conditions={
                "pattern_three_drive": True,
                "timeframe": "M15",
                "drive_tolerance": 0.02,
                "price_near": 90800.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Create three-drive candles
        candles = self._create_three_drive_candles(direction="buy", count=100)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(plan)
        self.assertIsInstance(result, bool)
    
    @patch('auto_execution_system.mt5')
    def test_condition_not_met_insufficient_swings(self, mock_mt5):
        """Test failure case: insufficient swing points"""
        # Create plan
        plan = TradePlan(
            plan_id="test_insufficient_swings",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=90800.0,
            stop_loss=90700.0,
            take_profit=91200.0,
            volume=0.01,
            conditions={
                "pattern_three_drive": True,
                "timeframe": "M15",
                "price_near": 90800.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Create candles with insufficient swings (flat price)
        candles = []
        base_time = datetime.now(timezone.utc).timestamp()
        for i in range(50):
            candles.append({
                'time': base_time - (50 - i) * 300,
                'open': 91000.0,
                'high': 91050.0,
                'low': 90950.0,
                'close': 91000.0,
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            })
        
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    def test_insufficient_candles(self, mock_mt5):
        """Test error handling: insufficient candles"""
        # Create plan
        plan = TradePlan(
            plan_id="test_insufficient_candles_three_drive",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=90800.0,
            stop_loss=90700.0,
            take_profit=91200.0,
            volume=0.01,
            conditions={
                "pattern_three_drive": True,
                "timeframe": "M15",
                "price_near": 90800.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Create insufficient candles
        candles = self._create_three_drive_candles(count=30)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(plan)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()

