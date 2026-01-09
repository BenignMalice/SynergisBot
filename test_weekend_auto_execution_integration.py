"""
Integration tests for Weekend Auto-Execution Integration
Tests weekend plan expiration, strategy filtering, and CME gap auto-execution.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import sys

# Mock dependencies
sys.modules['MetaTrader5'] = MagicMock()
# Mock requests if not available
try:
    import requests
except ImportError:
    sys.modules['requests'] = MagicMock()
# Mock httpx if not available
try:
    import httpx
except ImportError:
    sys.modules['httpx'] = MagicMock()

from auto_execution_system import AutoExecutionSystem, TradePlan
from infra.weekend_profile_manager import WeekendProfileManager


class TestWeekendPlanExpiration(unittest.TestCase):
    """Test weekend plan expiration logic"""

    def setUp(self):
        self.system = AutoExecutionSystem()
        self.weekend_manager = WeekendProfileManager()

    def test_is_plan_created_during_weekend_session_marker(self):
        """Test weekend detection via session marker in conditions"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=90000.0,
            stop_loss=89500.0,
            take_profit=91000.0,
            volume=0.01,
            conditions={"session": "Weekend"},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="chatgpt",
            status="pending"
        )
        
        result = self.system._is_plan_created_during_weekend(plan)
        self.assertTrue(result)

    def test_is_plan_created_during_weekend_notes(self):
        """Test weekend detection via notes keyword"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=90000.0,
            stop_loss=89500.0,
            take_profit=91000.0,
            volume=0.01,
            conditions={},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="chatgpt",
            status="pending",
            notes="Weekend trading plan"
        )
        
        result = self.system._is_plan_created_during_weekend(plan)
        self.assertTrue(result)

    def test_is_plan_created_during_weekend_creation_time(self):
        """Test weekend detection via creation time"""
        # Create plan with Friday 23:00 UTC creation time
        friday_23_utc = datetime(2025, 1, 10, 23, 0, 0, tzinfo=timezone.utc)  # Friday
        
        plan = TradePlan(
            plan_id="test_plan",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=90000.0,
            stop_loss=89500.0,
            take_profit=91000.0,
            volume=0.01,
            conditions={},
            created_at=friday_23_utc.isoformat(),
            created_by="chatgpt",
            status="pending"
        )
        
        result = self.system._is_plan_created_during_weekend(plan)
        self.assertTrue(result)

    def test_check_weekend_plan_expiration_non_btc(self):
        """Test that expiration check returns False for non-BTC symbols"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"session": "Weekend"},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="chatgpt",
            status="pending"
        )
        
        result = self.system._check_weekend_plan_expiration(plan)
        self.assertFalse(result)

    def test_check_weekend_plan_expiration_less_than_24h(self):
        """Test that plans less than 24h old don't expire"""
        # Create plan 12 hours ago
        created_at = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
        
        plan = TradePlan(
            plan_id="test_plan",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=90000.0,
            stop_loss=89500.0,
            take_profit=91000.0,
            volume=0.01,
            conditions={"session": "Weekend"},
            created_at=created_at,
            created_by="chatgpt",
            status="pending"
        )
        
        result = self.system._check_weekend_plan_expiration(plan)
        self.assertFalse(result)

    @patch('auto_execution_system.mt5')
    def test_check_weekend_plan_expiration_price_far(self, mock_mt5):
        """Test that plans expire when price is > 0.5% away after 24h"""
        # Create plan 25 hours ago
        created_at = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        
        plan = TradePlan(
            plan_id="test_plan",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=90000.0,
            stop_loss=89500.0,
            take_profit=91000.0,
            volume=0.01,
            conditions={"session": "Weekend"},
            created_at=created_at,
            created_by="chatgpt",
            status="pending"
        )
        
        # Mock MT5 service
        self.system.mt5_service = Mock()
        self.system.mt5_service.connect.return_value = True
        
        # Mock tick with price 1% away from entry (should expire)
        mock_tick = Mock()
        mock_tick.bid = 90900.0  # 1% above entry
        mock_tick.ask = 90910.0
        mock_mt5.symbol_info_tick.return_value = mock_tick
        
        result = self.system._check_weekend_plan_expiration(plan)
        self.assertTrue(result)  # Should expire

    @patch('auto_execution_system.mt5')
    def test_check_weekend_plan_expiration_price_near(self, mock_mt5):
        """Test that plans don't expire when price is < 0.5% away after 24h"""
        # Create plan 25 hours ago
        created_at = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        
        plan = TradePlan(
            plan_id="test_plan",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=90000.0,
            stop_loss=89500.0,
            take_profit=91000.0,
            volume=0.01,
            conditions={"session": "Weekend"},
            created_at=created_at,
            created_by="chatgpt",
            status="pending"
        )
        
        # Mock MT5 service
        self.system.mt5_service = Mock()
        self.system.mt5_service.connect.return_value = True
        
        # Mock tick with price 0.3% away from entry (should NOT expire)
        mock_tick = Mock()
        mock_tick.bid = 90270.0  # 0.3% above entry
        mock_tick.ask = 90280.0
        mock_mt5.symbol_info_tick.return_value = mock_tick
        
        result = self.system._check_weekend_plan_expiration(plan)
        self.assertFalse(result)  # Should NOT expire


class TestWeekendStrategyFiltering(unittest.TestCase):
    """Test weekend strategy filtering in auto-execution tools"""

    @patch('chatgpt_auto_execution_tools.WeekendProfileManager')
    def test_weekend_strategy_filtering_disallowed(self, mock_weekend_manager_class):
        """Test that disallowed strategies are rejected during weekend"""
        from chatgpt_auto_execution_tools import tool_create_auto_trade_plan
        
        # Mock weekend active
        mock_weekend_manager = Mock()
        mock_weekend_manager.is_weekend_active.return_value = True
        mock_weekend_manager_class.return_value = mock_weekend_manager
        
        args = {
            "symbol": "BTCUSDc",
            "direction": "BUY",
            "entry": 90000.0,
            "stop_loss": 89500.0,
            "take_profit": 91000.0,
            "volume": 0.01,
            "strategy_type": "breakout_ib_volatility_trap"  # Disallowed
        }
        
        import asyncio
        result = asyncio.run(tool_create_auto_trade_plan(args))
        
        self.assertIn("ERROR", result.get("summary", ""))
        self.assertIn("not allowed", result.get("summary", ""))

    @patch('chatgpt_auto_execution_tools.WeekendProfileManager')
    def test_weekend_strategy_filtering_allowed(self, mock_weekend_manager_class):
        """Test that allowed strategies pass during weekend"""
        from chatgpt_auto_execution_tools import tool_create_auto_trade_plan
        
        # Mock weekend active
        mock_weekend_manager = Mock()
        mock_weekend_manager.is_weekend_active.return_value = True
        mock_weekend_manager_class.return_value = mock_weekend_manager
        
        args = {
            "symbol": "BTCUSDc",
            "direction": "BUY",
            "entry": 90000.0,
            "stop_loss": 89500.0,
            "take_profit": 91000.0,
            "volume": 0.01,
            "strategy_type": "vwap_reversion"  # Allowed
        }
        
        # Mock the API call
        with patch('chatgpt_auto_execution_tools.httpx') as mock_httpx:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"plan_id": "test_plan_123"}
            mock_httpx.AsyncClient.return_value.__aenter__.return_value.post.return_value = mock_response
            
            import asyncio
            result = asyncio.run(tool_create_auto_trade_plan(args))
            
            # Should succeed (not blocked)
            self.assertIn("SUCCESS", result.get("summary", ""))

    @patch('chatgpt_auto_execution_tools.WeekendProfileManager')
    def test_weekend_session_marker_added(self, mock_weekend_manager_class):
        """Test that weekend session marker is added to plan conditions"""
        from chatgpt_auto_execution_tools import tool_create_auto_trade_plan
        
        # Mock weekend active
        mock_weekend_manager = Mock()
        mock_weekend_manager.is_weekend_active.return_value = True
        mock_weekend_manager_class.return_value = mock_weekend_manager
        
        args = {
            "symbol": "BTCUSDc",
            "direction": "BUY",
            "entry": 90000.0,
            "stop_loss": 89500.0,
            "take_profit": 91000.0,
            "volume": 0.01,
            "conditions": {}
        }
        
        # Mock the API call and capture payload
        captured_payload = {}
        
        async def mock_post(url, json=None):
            nonlocal captured_payload
            captured_payload = json
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"plan_id": "test_plan_123"}
            return mock_response
        
        with patch('chatgpt_auto_execution_tools.httpx') as mock_httpx:
            mock_client = Mock()
            mock_client.post = mock_post
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client
            
            import asyncio
            asyncio.run(tool_create_auto_trade_plan(args))
            
            # Check that session marker was added
            self.assertEqual(captured_payload.get("conditions", {}).get("session"), "Weekend")


class TestCMEGapAutoExecution(unittest.TestCase):
    """Test CME gap auto-execution integration"""

    @patch('chatgpt_bot.WeekendProfileManager')
    @patch('chatgpt_bot.CMEGapDetector')
    @patch('chatgpt_bot.httpx')
    def test_cme_gap_auto_plan_creation(self, mock_httpx, mock_gap_detector_class, mock_weekend_manager_class):
        """Test that CME gap detection auto-creates reversion plan"""
        # Mock weekend active (Sunday)
        mock_weekend_manager = Mock()
        mock_weekend_manager.is_weekend_active.return_value = True
        mock_weekend_manager_class.return_value = mock_weekend_manager
        
        # Mock gap detected
        gap_info = {
            'gap_pct': 0.6,
            'gap_direction': 'down',
            'friday_close': 90000.0,
            'sunday_open': 89460.0,
            'target_price': 89932.0,  # 80% gap fill
            'should_trade': True
        }
        
        mock_gap_detector = Mock()
        mock_gap_detector.detect_gap.return_value = gap_info
        mock_gap_detector_class.return_value = mock_gap_detector
        
        # Mock datetime to be Sunday
        with patch('chatgpt_bot.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 12, 10, 0, 0, tzinfo=timezone.utc)  # Sunday
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Mock API response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"plan_id": "cme_gap_plan_123"}
            mock_client = Mock()
            mock_client.post.return_value = mock_response
            mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client
            
            # Import and run the async function
            import asyncio
            from chatgpt_bot import check_cme_gap_and_create_plan
            
            asyncio.run(check_cme_gap_and_create_plan())
            
            # Verify API was called
            self.assertTrue(mock_client.post.called)
            
            # Verify plan parameters
            call_args = mock_client.post.call_args
            payload = call_args[1]['json']
            
            self.assertEqual(payload['symbol'], 'BTCUSDc')
            self.assertEqual(payload['direction'], 'BUY')  # Gap down = BUY
            self.assertEqual(payload['entry_price'], 89460.0)
            self.assertEqual(payload['take_profit'], 89932.0)  # 80% gap fill
            self.assertEqual(payload['conditions']['session'], 'Weekend')
            self.assertEqual(payload['conditions']['min_confluence'], 70)


if __name__ == '__main__':
    unittest.main()

