"""
DTMS System Test Suite
Comprehensive tests for the Defensive Trade Management System
"""

import unittest
import time
import pandas as pd
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

# Import DTMS components
from dtms_core.data_manager import DTMSDataManager
from dtms_core.regime_classifier import DTMSRegimeClassifier
from dtms_core.signal_scorer import DTMSSignalScorer
from dtms_core.state_machine import DTMSStateMachine, TradeState
from dtms_core.action_executor import DTMSActionExecutor
from dtms_core.dtms_engine import DTMSEngine
from dtms_config import get_config

class TestDTMSDataManager(unittest.TestCase):
    """Test DTMS Data Manager"""
    
    def setUp(self):
        self.mt5_service = Mock()
        self.binance_service = Mock()
        self.data_manager = DTMSDataManager(self.mt5_service, self.binance_service)
    
    def test_initialize_symbol(self):
        """Test symbol initialization"""
        symbol = "BTCUSD"
        
        # Mock MT5 data
        mock_m5_data = pd.DataFrame({
            'time': [int(time.time()) - 300*i for i in range(10)],
            'open': [100.0] * 10,
            'high': [101.0] * 10,
            'low': [99.0] * 10,
            'close': [100.5] * 10,
            'tick_volume': [1000] * 10
        })
        
        mock_m15_data = pd.DataFrame({
            'time': [int(time.time()) - 900*i for i in range(10)],
            'open': [100.0] * 10,
            'high': [101.0] * 10,
            'low': [99.0] * 10,
            'close': [100.5] * 10,
            'tick_volume': [1000] * 10
        })
        
        self.mt5_service.get_bars.return_value = mock_m5_data
        
        result = self.data_manager.initialize_symbol(symbol)
        self.assertTrue(result)
        self.assertIn(symbol, self.data_manager.m5_data)
        self.assertIn(symbol, self.data_manager.m15_data)
    
    def test_get_current_vwap(self):
        """Test VWAP calculation"""
        symbol = "BTCUSD"
        self.data_manager.initialize_symbol(symbol)
        
        # Add some test data
        test_bar = {
            'time': int(time.time()),
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5,
            'volume': 1000
        }
        self.data_manager.m5_data[symbol].append(test_bar)
        
        # Manually update VWAP data
        self.data_manager.vwap_data[symbol]['sum_pv'] = 100.5 * 1000  # typical_price * volume
        self.data_manager.vwap_data[symbol]['sum_v'] = 1000
        self.data_manager.vwap_data[symbol]['current_vwap'] = 100.5
        
        vwap = self.data_manager.get_current_vwap(symbol)
        self.assertGreater(vwap, 0)
    
    def test_get_vwap_slope(self):
        """Test VWAP slope calculation"""
        symbol = "BTCUSD"
        self.data_manager.initialize_symbol(symbol)
        
        # Add test data with increasing prices
        for i in range(5):
            test_bar = {
                'time': int(time.time()) - 300*i,
                'open': 100.0 + i*0.1,
                'high': 101.0 + i*0.1,
                'low': 99.0 + i*0.1,
                'close': 100.5 + i*0.1,
                'volume': 1000
            }
            self.data_manager.m5_data[symbol].append(test_bar)
        
        slope = self.data_manager.get_vwap_slope(symbol, periods=3)
        self.assertIsInstance(slope, float)

class TestDTMSRegimeClassifier(unittest.TestCase):
    """Test DTMS Regime Classifier"""
    
    def setUp(self):
        self.classifier = DTMSRegimeClassifier()
    
    def test_classify_session(self):
        """Test session classification"""
        session = self.classifier._classify_session()
        self.assertIn(session, ['Asian', 'London', 'NY', 'Overlap'])
    
    def test_classify_volatility(self):
        """Test volatility classification"""
        # Create test data with low volatility
        test_data = pd.DataFrame({
            'time': [int(time.time()) - 900*i for i in range(30)],
            'open': [100.0] * 30,
            'high': [100.1] * 30,
            'low': [99.9] * 30,
            'close': [100.0] * 30,
            'tick_volume': [1000] * 30
        })
        
        volatility = self.classifier._classify_volatility(test_data)
        self.assertIn(volatility, ['Low', 'Normal', 'High'])
    
    def test_classify_structure(self):
        """Test structure classification"""
        # Create test data with range structure (narrow BB)
        test_data = pd.DataFrame({
            'time': [int(time.time()) - 900*i for i in range(30)],
            'open': [100.0] * 30,
            'high': [100.1] * 30,
            'low': [99.9] * 30,
            'close': [100.0] * 30,
            'tick_volume': [1000] * 30
        })
        
        structure = self.classifier._classify_structure(test_data)
        self.assertIn(structure, ['Range', 'Trend'])
    
    def test_get_adaptive_thresholds(self):
        """Test adaptive threshold calculation"""
        symbol = "BTCUSD"
        regime = {
            'session': 'London',
            'volatility': 'Normal',
            'structure': 'Trend'
        }
        
        thresholds = self.classifier.get_adaptive_thresholds(symbol, regime)
        self.assertIn('vwap_threshold', thresholds)
        self.assertIn('rsi_threshold', thresholds)
        self.assertIn('volume_flip_threshold', thresholds)

class TestDTMSSignalScorer(unittest.TestCase):
    """Test DTMS Signal Scorer"""
    
    def setUp(self):
        self.scorer = DTMSSignalScorer()
    
    def test_calculate_signal_score(self):
        """Test signal score calculation"""
        symbol = "BTCUSD"
        trade_direction = "BUY"
        
        # Create test data
        m5_data = pd.DataFrame({
            'time': [int(time.time()) - 300*i for i in range(20)],
            'open': [100.0] * 20,
            'high': [101.0] * 20,
            'low': [99.0] * 20,
            'close': [100.5] * 20,
            'tick_volume': [1000] * 20
        })
        
        m15_data = pd.DataFrame({
            'time': [int(time.time()) - 900*i for i in range(20)],
            'open': [100.0] * 20,
            'high': [101.0] * 20,
            'low': [99.0] * 20,
            'close': [100.5] * 20,
            'tick_volume': [1000] * 20
        })
        
        regime = {
            'session': 'London',
            'volatility': 'Normal',
            'structure': 'Trend'
        }
        
        score_data = self.scorer.calculate_signal_score(
            symbol=symbol,
            trade_direction=trade_direction,
            m5_data=m5_data,
            m15_data=m15_data,
            regime=regime,
            vwap_current=100.0,
            vwap_slope=0.001,
            vwap_cross_counter=0
        )
        
        self.assertIn('total_score', score_data)
        self.assertIn('individual_scores', score_data)
        self.assertIn('warnings', score_data)
        self.assertIn('confluence', score_data)

class TestDTMSStateMachine(unittest.TestCase):
    """Test DTMS State Machine"""
    
    def setUp(self):
        self.state_machine = DTMSStateMachine()
    
    def test_add_trade(self):
        """Test adding trade to state machine"""
        ticket = 12345
        symbol = "BTCUSD"
        direction = "BUY"
        entry_price = 100.0
        volume = 0.1
        
        result = self.state_machine.add_trade(ticket, symbol, direction, entry_price, volume)
        self.assertTrue(result)
        self.assertIn(ticket, self.state_machine.active_trades)
    
    def test_state_transition(self):
        """Test state transition logic"""
        # Add a trade
        ticket = 12345
        symbol = "BTCUSD"
        direction = "BUY"
        entry_price = 100.0
        volume = 0.1
        
        self.state_machine.add_trade(ticket, symbol, direction, entry_price, volume)
        
        # Create score data that should trigger WARNING_L1
        score_data = {
            'total_score': -3.0,  # Below -2 threshold
            'warnings': {'structural': 1},
            'confluence': {'direction': 'BEARISH', 'ratio': 0.8}
        }
        
        transition_result = self.state_machine.update_trade_state(
            ticket=ticket,
            score_data=score_data,
            current_price=99.0,
            vwap_current=100.0,
            vwap_slope=-0.002
        )
        
        self.assertIn('new_state', transition_result)
        self.assertIn('actions', transition_result)
    
    def test_get_trade_status(self):
        """Test getting trade status"""
        ticket = 12345
        symbol = "BTCUSD"
        direction = "BUY"
        entry_price = 100.0
        volume = 0.1
        
        self.state_machine.add_trade(ticket, symbol, direction, entry_price, volume)
        
        status = self.state_machine.get_trade_status(ticket)
        self.assertIsNotNone(status)
        self.assertEqual(status['ticket'], ticket)
        self.assertEqual(status['symbol'], symbol)
        self.assertEqual(status['state'], 'HEALTHY')

class TestDTMSActionExecutor(unittest.TestCase):
    """Test DTMS Action Executor"""
    
    def setUp(self):
        self.mt5_service = Mock()
        self.telegram_service = Mock()
        self.action_executor = DTMSActionExecutor(self.mt5_service, self.telegram_service)
    
    def test_tighten_sl_action(self):
        """Test tighten SL action"""
        action = {
            'type': 'tighten_sl',
            'target_sl': '0.3R_behind_price',
            'reason': 'WARNING_L1 state'
        }
        
        trade_data = {
            'ticket': 12345,
            'symbol': 'BTCUSD',
            'direction': 'BUY',
            'current_price': 100.0,
            'entry_price': 99.0,
            'current_volume': 0.1,
            'initial_sl': 98.0,
            'take_profit': 102.0
        }
        
        # Mock successful MT5 operation
        self.mt5_service.modify_position.return_value = True
        
        result = self.action_executor._execute_single_action(action, trade_data)
        self.assertTrue(result.success)
        self.assertEqual(result.action_type, 'tighten_sl')
    
    def test_partial_close_action(self):
        """Test partial close action"""
        action = {
            'type': 'partial_close',
            'close_percentage': 50,
            'reason': 'WARNING_L2 state'
        }
        
        trade_data = {
            'ticket': 12345,
            'symbol': 'BTCUSD',
            'direction': 'BUY',
            'current_volume': 0.1
        }
        
        # Mock successful MT5 operation
        self.mt5_service.close_position_partial.return_value = True
        
        result = self.action_executor._execute_single_action(action, trade_data)
        self.assertTrue(result.success)
        self.assertEqual(result.action_type, 'partial_close')

class TestDTMSEngine(unittest.TestCase):
    """Test DTMS Engine"""
    
    def setUp(self):
        self.mt5_service = Mock()
        self.binance_service = Mock()
        self.telegram_service = Mock()
        
        # Mock MT5 data
        mock_m5_data = pd.DataFrame({
            'time': [int(time.time()) - 300*i for i in range(20)],
            'open': [100.0] * 20,
            'high': [101.0] * 20,
            'low': [99.0] * 20,
            'close': [100.5] * 20,
            'tick_volume': [1000] * 20
        })
        
        mock_m15_data = pd.DataFrame({
            'time': [int(time.time()) - 900*i for i in range(20)],
            'open': [100.0] * 20,
            'high': [101.0] * 20,
            'low': [99.0] * 20,
            'close': [100.5] * 20,
            'tick_volume': [1000] * 20
        })
        
        self.mt5_service.get_bars.return_value = mock_m5_data
        self.mt5_service.get_tick.return_value = Mock(bid=100.0, ask=100.1)
        
        self.dtms_engine = DTMSEngine(
            self.mt5_service, 
            self.binance_service, 
            self.telegram_service
        )
    
    def test_initialize_dtms(self):
        """Test DTMS initialization"""
        self.assertIsNotNone(self.dtms_engine.data_manager)
        self.assertIsNotNone(self.dtms_engine.regime_classifier)
        self.assertIsNotNone(self.dtms_engine.signal_scorer)
        self.assertIsNotNone(self.dtms_engine.state_machine)
        self.assertIsNotNone(self.dtms_engine.action_executor)
    
    def test_add_trade_monitoring(self):
        """Test adding trade to monitoring"""
        ticket = 12345
        symbol = "BTCUSD"
        direction = "BUY"
        entry_price = 100.0
        volume = 0.1
        
        result = self.dtms_engine.add_trade_monitoring(
            ticket, symbol, direction, entry_price, volume
        )
        self.assertTrue(result)
    
    def test_get_system_status(self):
        """Test getting system status"""
        status = self.dtms_engine.get_system_status()
        self.assertIn('monitoring_active', status)
        self.assertIn('active_trades', status)
        self.assertIn('performance', status)
    
    def test_start_stop_monitoring(self):
        """Test starting and stopping monitoring"""
        # Start monitoring
        result = self.dtms_engine.start_monitoring()
        self.assertTrue(result)
        self.assertTrue(self.dtms_engine.monitoring_active)
        
        # Stop monitoring
        result = self.dtms_engine.stop_monitoring()
        self.assertTrue(result)
        self.assertFalse(self.dtms_engine.monitoring_active)

class TestDTMSIntegration(unittest.TestCase):
    """Test DTMS Integration"""
    
    def setUp(self):
        self.mt5_service = Mock()
        self.binance_service = Mock()
        self.telegram_service = Mock()
    
    def test_dtms_integration_imports(self):
        """Test that DTMS integration can be imported"""
        try:
            # Import from the main integration module file (not the package)
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            
            # Import the actual integration module
            import importlib.util
            spec = importlib.util.spec_from_file_location("dtms_integration_module", "dtms_integration.py")
            dtms_integration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(dtms_integration_module)
            
            # Check if the module has the expected functions
            expected_functions = ['initialize_dtms', 'start_dtms_monitoring', 'add_trade_to_dtms', 'get_dtms_system_status']
            for func in expected_functions:
                self.assertTrue(hasattr(dtms_integration_module, func), f"Missing function: {func}")
        except Exception as e:
            self.fail(f"Failed to import DTMS integration: {e}")
    
    def test_dtms_config_import(self):
        """Test that DTMS config can be imported"""
        try:
            from dtms_config import get_config, DEFAULT_CONFIG
            config = get_config()
            self.assertIsNotNone(config)
            self.assertIsNotNone(DEFAULT_CONFIG)
        except ImportError as e:
            self.fail(f"Failed to import DTMS config: {e}")

class TestDTMSPerformance(unittest.TestCase):
    """Test DTMS Performance"""
    
    def setUp(self):
        self.mt5_service = Mock()
        self.binance_service = Mock()
        self.telegram_service = Mock()
        
        # Create realistic test data
        self.test_data = pd.DataFrame({
            'time': [int(time.time()) - 300*i for i in range(100)],
            'open': [100.0 + np.random.normal(0, 0.1) for _ in range(100)],
            'high': [101.0 + np.random.normal(0, 0.1) for _ in range(100)],
            'low': [99.0 + np.random.normal(0, 0.1) for _ in range(100)],
            'close': [100.5 + np.random.normal(0, 0.1) for _ in range(100)],
            'tick_volume': [1000 + np.random.randint(-100, 100) for _ in range(100)]
        })
        
        self.mt5_service.get_bars.return_value = self.test_data
        self.mt5_service.get_tick.return_value = Mock(bid=100.0, ask=100.1)
        
        self.dtms_engine = DTMSEngine(
            self.mt5_service, 
            self.binance_service, 
            self.telegram_service
        )
    
    def test_signal_scoring_performance(self):
        """Test signal scoring performance"""
        symbol = "BTCUSD"
        trade_direction = "BUY"
        
        regime = {
            'session': 'London',
            'volatility': 'Normal',
            'structure': 'Trend'
        }
        
        start_time = time.time()
        
        # Run multiple signal scoring operations
        for _ in range(10):
            score_data = self.dtms_engine.signal_scorer.calculate_signal_score(
                symbol=symbol,
                trade_direction=trade_direction,
                m5_data=self.test_data,
                m15_data=self.test_data,
                regime=regime,
                vwap_current=100.0,
                vwap_slope=0.001,
                vwap_cross_counter=0
            )
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete 10 operations in less than 1 second
        self.assertLess(duration, 1.0)
        print(f"Signal scoring performance: {duration:.3f}s for 10 operations")
    
    def test_state_machine_performance(self):
        """Test state machine performance"""
        # Add multiple trades
        for i in range(50):
            ticket = 10000 + i
            self.dtms_engine.add_trade_monitoring(
                ticket, "BTCUSD", "BUY", 100.0, 0.1
            )
        
        start_time = time.time()
        
        # Update all trades
        for i in range(50):
            ticket = 10000 + i
            score_data = {
                'total_score': np.random.normal(0, 2),
                'warnings': {},
                'confluence': {'direction': 'NEUTRAL', 'ratio': 0.5}
            }
            
            self.dtms_engine.state_machine.update_trade_state(
                ticket=ticket,
                score_data=score_data,
                current_price=100.0,
                vwap_current=100.0,
                vwap_slope=0.001
            )
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete 50 updates in less than 2 seconds
        self.assertLess(duration, 2.0)
        print(f"State machine performance: {duration:.3f}s for 50 trade updates")

def run_dtms_tests():
    """Run all DTMS tests"""
    print("Running DTMS System Tests...")
    print("=" * 50)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestDTMSDataManager,
        TestDTMSRegimeClassifier,
        TestDTMSSignalScorer,
        TestDTMSStateMachine,
        TestDTMSActionExecutor,
        TestDTMSEngine,
        TestDTMSIntegration,
        TestDTMSPerformance
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print("\n" + "=" * 50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_dtms_tests()
    exit(0 if success else 1)
