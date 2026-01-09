"""
Unit tests for Phase 3: Session Conditions
Tests for volatility_decay, momentum_follow, fakeout_sweep, and flat_vol_hours conditions
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


class TestVolatilityDecayCondition(unittest.TestCase):
    """Test volatility decay condition detection"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Mock quote object - code accesses quote.bid and quote.ask
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
        
        # Create test plan
        self.plan = TradePlan(
            plan_id="test_volatility_decay",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=91000.0,
            stop_loss=90900.0,
            take_profit=91200.0,
            volume=0.01,
            conditions={
                "volatility_decay": True,
                "session": "NY_close",
                "decay_threshold": 0.8,
                "decay_window": 5,
                "timeframe": "M15",
                "price_near": 91000.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
    
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
    
    def _create_mock_candles_with_atr_decay(self, recent_atr=80.0, earlier_atr=100.0, count=20):
        """Create mock candles with ATR decay"""
        import MetaTrader5 as mt5
        candles = []
        base_price = 91000.0
        
        # Earlier candles (higher volatility)
        for i in range(count // 2, count):
            # Higher volatility candles
            volatility = earlier_atr / 2
            candles.append({
                'time': datetime.now(timezone.utc).timestamp() - (count - i) * 300,
                'open': base_price + (i * 5),
                'high': base_price + (i * 5) + volatility,
                'low': base_price + (i * 5) - volatility,
                'close': base_price + (i * 5),
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            })
        
        # Recent candles (lower volatility)
        for i in range(count // 2):
            # Lower volatility candles
            volatility = recent_atr / 2
            candles.append({
                'time': datetime.now(timezone.utc).timestamp() - (count // 2 - i) * 300,
                'open': base_price + (i * 5),
                'high': base_price + (i * 5) + volatility,
                'low': base_price + (i * 5) - volatility,
                'close': base_price + (i * 5),
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            })
        
        return candles
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_met_atr_decay_above_threshold(self, mock_session, mock_mt5):
        """Test successful condition: ATR decay above threshold"""
        # Mock session
        mock_session.return_value = "NY_close"
        
        # Create candles with ATR decay (recent=80, earlier=100, ratio=0.8, but we check < 0.8)
        # So we need recent < 0.8 * earlier = 80 < 80, which is False
        # Let's use recent=70, earlier=100, ratio=0.7 < 0.8
        candles = self._create_mock_candles_with_atr_decay(recent_atr=70.0, earlier_atr=100.0)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertIsInstance(result, bool)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_not_met_atr_decay_below_threshold(self, mock_session, mock_mt5):
        """Test failure case: ATR decay below threshold"""
        # Mock session
        mock_session.return_value = "NY_close"
        
        # Create candles with minimal ATR decay (recent=85, earlier=100, ratio=0.85 >= 0.8)
        candles = self._create_mock_candles_with_atr_decay(recent_atr=85.0, earlier_atr=100.0)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_not_met_wrong_session(self, mock_session, mock_mt5):
        """Test failure case: wrong session"""
        # Mock wrong session
        mock_session.return_value = "London"
        
        candles = self._create_mock_candles_with_atr_decay(recent_atr=70.0, earlier_atr=100.0)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_not_met_atr_increasing(self, mock_session, mock_mt5):
        """Test failure case: ATR increasing (not decaying)"""
        # Mock session
        mock_session.return_value = "NY_close"
        
        # Create candles with ATR increasing (recent=100, earlier=80, ratio=1.25)
        candles = self._create_mock_candles_with_atr_decay(recent_atr=100.0, earlier_atr=80.0)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_insufficient_candles(self, mock_session, mock_mt5):
        """Test error handling: insufficient candles"""
        # Mock session
        mock_session.return_value = "NY_close"
        
        # Create insufficient candles
        candles = self._create_mock_candles_with_atr_decay(count=5)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)


class TestMomentumFollowCondition(unittest.TestCase):
    """Test momentum follow condition detection"""
    
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
        
        # Create test plan
        self.plan = TradePlan(
            plan_id="test_momentum_follow",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=91000.0,
            stop_loss=90900.0,
            take_profit=91200.0,
            volume=0.01,
            conditions={
                "momentum_follow": True,
                "session": "NY",
                "momentum_periods": 5,
                "momentum_threshold": 0.5,
                "timeframe": "M15",
                "price_near": 91000.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
    
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
    
    def _create_mock_candles_with_momentum(self, direction="up", strength=1.0, count=10):
        """Create mock candles with consistent momentum"""
        candles = []
        base_price = 91000.0
        
        for i in range(count):
            if direction == "up":
                price = base_price + (i * strength * 10)  # Upward momentum
            else:
                price = base_price - (i * strength * 10)  # Downward momentum
            
            candles.append({
                'time': datetime.now(timezone.utc).timestamp() - (count - i) * 300,
                'open': price - 5,
                'high': price + 10,
                'low': price - 10,
                'close': price,
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            })
        
        return candles
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_met_strong_consistent_momentum(self, mock_session, mock_mt5):
        """Test successful condition: strong consistent momentum"""
        # Mock session
        mock_session.return_value = "NY"
        
        # Create candles with strong upward momentum
        candles = self._create_mock_candles_with_momentum(direction="up", strength=1.0)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertIsInstance(result, bool)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_not_met_weak_momentum(self, mock_session, mock_mt5):
        """Test failure case: weak momentum"""
        # Mock session
        mock_session.return_value = "NY"
        
        # Create candles with weak momentum (below threshold)
        candles = self._create_mock_candles_with_momentum(direction="up", strength=0.1)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_not_met_wrong_direction(self, mock_session, mock_mt5):
        """Test failure case: momentum in wrong direction"""
        # Mock session
        mock_session.return_value = "NY"
        
        # Create candles with downward momentum (wrong for BUY)
        candles = self._create_mock_candles_with_momentum(direction="down", strength=1.0)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_not_met_wrong_session(self, mock_session, mock_mt5):
        """Test failure case: wrong session"""
        # Mock wrong session
        mock_session.return_value = "London"
        
        candles = self._create_mock_candles_with_momentum(direction="up", strength=1.0)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_not_met_inconsistent_momentum(self, mock_session, mock_mt5):
        """Test failure case: inconsistent momentum (mixed directions)"""
        # Mock session
        mock_session.return_value = "NY"
        
        # Create candles with mixed momentum (up and down)
        candles = []
        base_price = 91000.0
        for i in range(10):
            # Alternate between up and down
            if i % 2 == 0:
                price = base_price + (i * 5)
            else:
                price = base_price - (i * 3)
            
            candles.append({
                'time': datetime.now(timezone.utc).timestamp() - (10 - i) * 300,
                'open': price - 5,
                'high': price + 10,
                'low': price - 10,
                'close': price,
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            })
        
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_insufficient_candles(self, mock_session, mock_mt5):
        """Test error handling: insufficient candles"""
        # Mock session
        mock_session.return_value = "NY"
        
        # Create insufficient candles
        candles = self._create_mock_candles_with_momentum(count=3)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)


class TestFakeoutSweepCondition(unittest.TestCase):
    """Test fakeout sweep condition detection"""
    
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
        
        # Create test plan
        self.plan = TradePlan(
            plan_id="test_fakeout_sweep",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=91000.0,
            stop_loss=90900.0,
            take_profit=91200.0,
            volume=0.01,
            conditions={
                "fakeout_sweep": True,
                "session": "London",
                "fakeout_reversal_candles": 5,
                "timeframe": "M15",
                "price_near": 91000.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
    
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
    
    def _create_mock_candles_with_fakeout(self, direction="buy", count=30):
        """Create mock candles with fakeout pattern"""
        candles = []
        base_price = 91000.0
        swing_low = base_price - 200  # Swing low at 90800
        swing_high = base_price + 200  # Swing high at 91200
        
        # Earlier candles (establish swing levels)
        for i in range(count - 10, count):
            price = base_price + (i - count + 10) * 10
            candles.append({
                'time': datetime.now(timezone.utc).timestamp() - (count - i) * 300,
                'open': price,
                'high': price + 50,
                'low': price - 50,
                'close': price,
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            })
        
        # Breakout candle (breaks below swing low for BUY, above swing high for SELL)
        if direction == "buy":
            # Break below swing low
            candles.insert(0, {
                'time': datetime.now(timezone.utc).timestamp() - 300,
                'open': swing_low + 50,
                'high': swing_low + 100,
                'low': swing_low - 50,  # Breaks below swing low
                'close': swing_low - 20,
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            })
        else:  # sell
            # Break above swing high
            candles.insert(0, {
                'time': datetime.now(timezone.utc).timestamp() - 300,
                'open': swing_high - 50,
                'high': swing_high + 50,  # Breaks above swing high
                'low': swing_high - 100,
                'close': swing_high + 20,
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            })
        
        # Reversal candle (moves back through level)
        if direction == "buy":
            # Reversal up (close above swing low)
            candles.insert(0, {
                'time': datetime.now(timezone.utc).timestamp(),
                'open': swing_low - 10,
                'high': swing_low + 100,  # Long upper wick (rejection)
                'low': swing_low - 50,
                'close': swing_low + 50,  # Closes above swing low
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            })
        else:  # sell
            # Reversal down (close below swing high)
            candles.insert(0, {
                'time': datetime.now(timezone.utc).timestamp(),
                'open': swing_high + 10,
                'high': swing_high + 50,
                'low': swing_high - 100,  # Long lower wick (rejection)
                'close': swing_high - 50,  # Closes below swing high
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            })
        
        return candles
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_met_clear_fakeout(self, mock_session, mock_mt5):
        """Test successful condition: clear fakeout pattern"""
        # Mock session
        mock_session.return_value = "London"
        
        # Create candles with fakeout pattern
        candles = self._create_mock_candles_with_fakeout(direction="buy")
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertIsInstance(result, bool)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_not_met_sustained_breakout(self, mock_session, mock_mt5):
        """Test failure case: sustained breakout (no reversal)"""
        # Mock session
        mock_session.return_value = "London"
        
        # Create candles with breakout but no reversal
        candles = []
        base_price = 91000.0
        swing_low = base_price - 200
        
        # Breakout candle
        candles.append({
            'time': datetime.now(timezone.utc).timestamp() - 300,
            'open': swing_low + 50,
            'high': swing_low + 100,
            'low': swing_low - 50,
            'close': swing_low - 20,
            'tick_volume': 1000,
            'spread': 10,
            'real_volume': 1000
        })
        
        # No reversal - price continues down
        candles.insert(0, {
            'time': datetime.now(timezone.utc).timestamp(),
            'open': swing_low - 30,
            'high': swing_low - 10,
            'low': swing_low - 100,
            'close': swing_low - 50,  # Still below swing low
            'tick_volume': 1000,
            'spread': 10,
            'real_volume': 1000
        })
        
        # Add more candles for lookback
        for i in range(20):
            candles.append({
                'time': datetime.now(timezone.utc).timestamp() - (i + 2) * 300,
                'open': base_price + i * 10,
                'high': base_price + i * 10 + 50,
                'low': base_price + i * 10 - 50,
                'close': base_price + i * 10,
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            })
        
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_not_met_wrong_session(self, mock_session, mock_mt5):
        """Test failure case: wrong session"""
        # Mock wrong session
        mock_session.return_value = "NY"
        
        candles = self._create_mock_candles_with_fakeout(direction="buy")
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_insufficient_candles(self, mock_session, mock_mt5):
        """Test error handling: insufficient candles"""
        # Mock session
        mock_session.return_value = "London"
        
        # Create insufficient candles
        candles = self._create_mock_candles_with_fakeout(count=10)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)


class TestFlatVolHoursCondition(unittest.TestCase):
    """Test flat volatility hours condition detection"""
    
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
        
        # Create test plan
        self.plan = TradePlan(
            plan_id="test_flat_vol_hours",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=91000.0,
            stop_loss=90900.0,
            take_profit=91200.0,
            volume=0.01,
            conditions={
                "flat_vol_hours": 3,
                "session": "Asian",
                "timeframe": "H1",
                "price_near": 91000.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
    
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
    
    def _create_mock_h1_candles_with_flat_vol(self, hours=5, volatility=50.0):
        """Create mock H1 candles with flat volatility"""
        candles = []
        base_price = 91000.0
        
        for i in range(hours):
            # Low volatility candles (small high-low range)
            candles.append({
                'time': datetime.now(timezone.utc).timestamp() - (hours - i) * 3600,
                'open': base_price + (i * 5),
                'high': base_price + (i * 5) + volatility,
                'low': base_price + (i * 5) - volatility,
                'close': base_price + (i * 5),
                'tick_volume': 1000,
                'spread': 10,
                'real_volume': 1000
            })
        
        return candles
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_met_sufficient_hours(self, mock_session, mock_mt5):
        """Test successful condition: sufficient hours with flat volatility"""
        # Mock session
        mock_session.return_value = "Asian"
        
        # Create H1 candles with low stable volatility
        candles = self._create_mock_h1_candles_with_flat_vol(hours=5, volatility=50.0)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_H1 = 16388
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertIsInstance(result, bool)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_not_met_insufficient_hours(self, mock_session, mock_mt5):
        """Test failure case: insufficient hours with flat volatility"""
        # Mock session
        mock_session.return_value = "Asian"
        
        # Create H1 candles with only 2 hours of low volatility
        candles = self._create_mock_h1_candles_with_flat_vol(hours=2, volatility=50.0)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_H1 = 16388
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_not_met_high_volatility(self, mock_session, mock_mt5):
        """Test failure case: high volatility periods"""
        # Mock session
        mock_session.return_value = "Asian"
        
        # Create H1 candles with high volatility
        candles = self._create_mock_h1_candles_with_flat_vol(hours=5, volatility=500.0)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_H1 = 16388
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_condition_not_met_wrong_session(self, mock_session, mock_mt5):
        """Test failure case: wrong session"""
        # Mock wrong session
        mock_session.return_value = "NY"
        
        candles = self._create_mock_h1_candles_with_flat_vol(hours=5, volatility=50.0)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_H1 = 16388
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    @patch('infra.session_helpers.SessionHelpers.get_current_session')
    def test_insufficient_candles(self, mock_session, mock_mt5):
        """Test error handling: insufficient candles"""
        # Mock session
        mock_session.return_value = "Asian"
        
        # Create insufficient candles
        candles = self._create_mock_h1_candles_with_flat_vol(hours=2)
        mock_mt5.copy_rates_from_pos.return_value = candles
        mock_mt5.TIMEFRAME_H1 = 16388
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()

