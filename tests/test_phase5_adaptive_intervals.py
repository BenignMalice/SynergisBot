"""
Unit tests for Phase 5: Enhanced Adaptive Intervals
Tests minimum interval enforcement, activity-based adjustments, volatility-based adjustments
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestAdaptiveIntervals(unittest.TestCase):
    """Test enhanced adaptive intervals functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        import tempfile
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Create AutoExecutionSystem instance
        self.mt5_service = Mock()
        self.auto_exec = AutoExecutionSystem(
            db_path=self.temp_db.name,
            check_interval=15,
            mt5_service=self.mt5_service
        )
        # Ensure system doesn't start threads
        self.auto_exec.running = False
    
    def tearDown(self):
        """Clean up test fixtures"""
        if hasattr(self, 'auto_exec'):
            # Stop system if running
            if self.auto_exec.running:
                self.auto_exec.running = False
            # Stop threads if they exist
            if hasattr(self.auto_exec, 'monitor_thread') and self.auto_exec.monitor_thread:
                self.auto_exec.monitor_thread = None
            if hasattr(self.auto_exec, 'watchdog_thread') and self.auto_exec.watchdog_thread:
                self.auto_exec.watchdog_thread = None
            # Stop database write queue if it exists
            if hasattr(self.auto_exec, 'db_write_queue') and self.auto_exec.db_write_queue:
                try:
                    self.auto_exec.db_write_queue.stop()
                except:
                    pass
            # Shutdown thread pool if exists
            if hasattr(self.auto_exec, '_condition_check_executor') and self.auto_exec._condition_check_executor:
                try:
                    self.auto_exec._condition_check_executor.shutdown(wait=False)
                except:
                    pass
            # Close database manager
            if hasattr(self.auto_exec, '_db_manager') and self.auto_exec._db_manager:
                try:
                    self.auto_exec._db_manager.close()
                except:
                    pass
        if hasattr(self, 'temp_db'):
            try:
                os.unlink(self.temp_db.name)
            except:
                pass
    
    def test_minimum_interval_enforcement(self):
        """Test that adaptive intervals enforce minimum of 15s"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock config to return close_interval_seconds of 10 (below minimum)
        with patch.dict(self.auto_exec.config, {
            'optimized_intervals': {
                'adaptive_intervals': {
                    'enabled': True,
                    'plan_type_intervals': {
                        'scalp': {
                            'close_interval_seconds': 10,  # Below minimum of 15s
                            'base_interval_seconds': 30,
                            'far_interval_seconds': 60
                        }
                    }
                }
            }
        }):
            with patch.object(self.auto_exec, '_plan_types', {'test_plan': 'scalp'}):
                with patch.object(self.auto_exec, '_detect_plan_type', return_value='scalp'):
                    current_price = 2002.0  # Within tolerance
                    interval = self.auto_exec._calculate_adaptive_interval(plan, current_price)
                    
                    # Should enforce minimum of 15s
                    self.assertGreaterEqual(interval, 15, "Interval should be at least 15s")
    
    def test_activity_based_adjustment_recent(self):
        """Test that recent activity reduces interval by 20%"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Set recent activity (<5 min ago)
        self.auto_exec._plan_activity[plan.plan_id] = datetime.now(timezone.utc) - timedelta(minutes=2)
        
        # Mock config
        with patch.dict(self.auto_exec.config, {
            'optimized_intervals': {
                'adaptive_intervals': {
                    'enabled': True,
                    'plan_type_intervals': {
                        'scalp': {
                            'close_interval_seconds': 20,
                            'base_interval_seconds': 30,
                            'far_interval_seconds': 60
                        }
                    }
                }
            }
        }):
            with patch.object(self.auto_exec, '_plan_types', {'test_plan': 'scalp'}):
                with patch.object(self.auto_exec, '_detect_plan_type', return_value='scalp'):
                    current_price = 2002.0  # Within tolerance (uses close_interval_seconds = 20)
                    interval = self.auto_exec._calculate_adaptive_interval(plan, current_price)
                    
                    # Should be 20 * 0.8 = 16, but minimum is 15, so should be 16
                    # Actually, it should be max(16, 15) = 16
                    self.assertEqual(interval, 16, "Recent activity should reduce interval by 20%")
    
    def test_activity_based_adjustment_old(self):
        """Test that old activity increases interval by 50%"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Set old activity (>1 hour ago)
        self.auto_exec._plan_activity[plan.plan_id] = datetime.now(timezone.utc) - timedelta(hours=2)
        
        # Mock config
        with patch.dict(self.auto_exec.config, {
            'optimized_intervals': {
                'adaptive_intervals': {
                    'enabled': True,
                    'plan_type_intervals': {
                        'scalp': {
                            'close_interval_seconds': 20,
                            'base_interval_seconds': 30,
                            'far_interval_seconds': 60
                        }
                    }
                }
            }
        }):
            with patch.object(self.auto_exec, '_plan_types', {'test_plan': 'scalp'}):
                with patch.object(self.auto_exec, '_detect_plan_type', return_value='scalp'):
                    current_price = 2002.0  # Within tolerance (uses close_interval_seconds = 20)
                    interval = self.auto_exec._calculate_adaptive_interval(plan, current_price)
                    
                    # Should be 20 * 1.5 = 30
                    self.assertEqual(interval, 30, "Old activity should increase interval by 50%")
    
    def test_volatility_based_adjustment_high(self):
        """Test that high volatility reduces interval by 15%"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Set high volatility (>2.0 ATR)
        symbol_norm = plan.symbol.upper().rstrip('Cc') + 'c'
        self.auto_exec._plan_volatility[symbol_norm] = 2.5
        
        # Mock config
        with patch.dict(self.auto_exec.config, {
            'optimized_intervals': {
                'adaptive_intervals': {
                    'enabled': True,
                    'plan_type_intervals': {
                        'scalp': {
                            'close_interval_seconds': 20,
                            'base_interval_seconds': 30,
                            'far_interval_seconds': 60
                        }
                    }
                }
            }
        }):
            with patch.object(self.auto_exec, '_plan_types', {'test_plan': 'scalp'}):
                with patch.object(self.auto_exec, '_detect_plan_type', return_value='scalp'):
                    current_price = 2002.0  # Within tolerance (uses close_interval_seconds = 20)
                    interval = self.auto_exec._calculate_adaptive_interval(plan, current_price)
                    
                    # Should be 20 * 0.85 = 17, but minimum is 15, so should be 17
                    self.assertEqual(interval, 17, "High volatility should reduce interval by 15%")
    
    def test_volatility_based_adjustment_low(self):
        """Test that low volatility increases interval by 20%"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Set low volatility (<0.5 ATR)
        symbol_norm = plan.symbol.upper().rstrip('Cc') + 'c'
        self.auto_exec._plan_volatility[symbol_norm] = 0.3
        
        # Mock config
        with patch.dict(self.auto_exec.config, {
            'optimized_intervals': {
                'adaptive_intervals': {
                    'enabled': True,
                    'plan_type_intervals': {
                        'scalp': {
                            'close_interval_seconds': 20,
                            'base_interval_seconds': 30,
                            'far_interval_seconds': 60
                        }
                    }
                }
            }
        }):
            with patch.object(self.auto_exec, '_plan_types', {'test_plan': 'scalp'}):
                with patch.object(self.auto_exec, '_detect_plan_type', return_value='scalp'):
                    current_price = 2002.0  # Within tolerance (uses close_interval_seconds = 20)
                    interval = self.auto_exec._calculate_adaptive_interval(plan, current_price)
                    
                    # Should be 20 * 1.2 = 24
                    self.assertEqual(interval, 24, "Low volatility should increase interval by 20%")
    
    def test_combined_adjustments(self):
        """Test that activity and volatility adjustments combine correctly"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Set recent activity and high volatility
        self.auto_exec._plan_activity[plan.plan_id] = datetime.now(timezone.utc) - timedelta(minutes=2)
        symbol_norm = plan.symbol.upper().rstrip('Cc') + 'c'
        self.auto_exec._plan_volatility[symbol_norm] = 2.5
        
        # Mock config
        with patch.dict(self.auto_exec.config, {
            'optimized_intervals': {
                'adaptive_intervals': {
                    'enabled': True,
                    'plan_type_intervals': {
                        'scalp': {
                            'close_interval_seconds': 20,
                            'base_interval_seconds': 30,
                            'far_interval_seconds': 60
                        }
                    }
                }
            }
        }):
            with patch.object(self.auto_exec, '_plan_types', {'test_plan': 'scalp'}):
                with patch.object(self.auto_exec, '_detect_plan_type', return_value='scalp'):
                    current_price = 2002.0  # Within tolerance (uses close_interval_seconds = 20)
                    interval = self.auto_exec._calculate_adaptive_interval(plan, current_price)
                    
                    # Should be: 20 * 0.8 (activity) * 0.85 (volatility) = 13.6, but minimum is 15
                    # So should be 15
                    self.assertGreaterEqual(interval, 15, "Combined adjustments should respect minimum")
                    # Actually: 20 * 0.8 = 16, then 16 * 0.85 = 13.6, max(13.6, 15) = 15
                    self.assertEqual(interval, 15, "Combined adjustments should result in minimum when below threshold")
    
    def test_volatility_tracking_initialized(self):
        """Test that volatility tracking is initialized"""
        self.assertTrue(hasattr(self.auto_exec, '_plan_volatility'))
        self.assertIsInstance(self.auto_exec._plan_volatility, dict)
    
    def test_update_volatility_tracking(self):
        """Test that volatility tracking is updated correctly"""
        # Mock volatility calculator
        mock_calculator = Mock()
        mock_calculator.get_atr = Mock(return_value=1.5)
        self.auto_exec.volatility_tolerance_calculator = mock_calculator
        
        symbol = "XAUUSDc"
        self.auto_exec._update_volatility_tracking(symbol)
        
        # Verify volatility was stored
        self.assertIn(symbol, self.auto_exec._plan_volatility)
        self.assertEqual(self.auto_exec._plan_volatility[symbol], 1.5)
    
    def test_update_volatility_tracking_no_calculator(self):
        """Test that volatility tracking handles missing calculator gracefully"""
        self.auto_exec.volatility_tolerance_calculator = None
        
        symbol = "XAUUSDc"
        # Should not raise exception
        self.auto_exec._update_volatility_tracking(symbol)
        
        # Verify volatility was not stored
        self.assertNotIn(symbol, self.auto_exec._plan_volatility)
    
    def test_update_volatility_tracking_none_atr(self):
        """Test that volatility tracking handles None ATR gracefully"""
        # Mock volatility calculator returning None
        mock_calculator = Mock()
        mock_calculator.get_atr = Mock(return_value=None)
        self.auto_exec.volatility_tolerance_calculator = mock_calculator
        
        symbol = "XAUUSDc"
        # Should not raise exception
        self.auto_exec._update_volatility_tracking(symbol)
        
        # Verify volatility was not stored
        self.assertNotIn(symbol, self.auto_exec._plan_volatility)
    
    def test_adaptive_interval_disabled(self):
        """Test that adaptive intervals return base interval when disabled"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock config with adaptive intervals disabled
        with patch.dict(self.auto_exec.config, {
            'optimized_intervals': {
                'adaptive_intervals': {
                    'enabled': False
                }
            }
        }):
            current_price = 2002.0
            interval = self.auto_exec._calculate_adaptive_interval(plan, current_price)
            
            # Should return base check_interval (15s)
            self.assertEqual(interval, 15, "Should return base interval when adaptive intervals disabled")
    
    def test_adaptive_interval_no_tolerance(self):
        """Test that adaptive intervals use base interval when tolerance is 0"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 0},  # No tolerance
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock config
        with patch.dict(self.auto_exec.config, {
            'optimized_intervals': {
                'adaptive_intervals': {
                    'enabled': True,
                    'plan_type_intervals': {
                        'scalp': {
                            'base_interval_seconds': 30
                        }
                    }
                }
            }
        }):
            with patch.object(self.auto_exec, '_plan_types', {'test_plan': 'scalp'}):
                with patch.object(self.auto_exec, '_detect_plan_type', return_value='scalp'):
                    current_price = 2002.0
                    interval = self.auto_exec._calculate_adaptive_interval(plan, current_price)
                    
                    # Should use base_interval_seconds (30), but minimum is 15, so should be 30
                    self.assertEqual(interval, 30, "Should use base interval when tolerance is 0")
    
    def test_adaptive_interval_far_from_entry(self):
        """Test that adaptive intervals use far interval when price is far from entry"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock config
        with patch.dict(self.auto_exec.config, {
            'optimized_intervals': {
                'adaptive_intervals': {
                    'enabled': True,
                    'plan_type_intervals': {
                        'scalp': {
                            'close_interval_seconds': 20,
                            'base_interval_seconds': 30,
                            'far_interval_seconds': 60,
                            'price_proximity_multiplier': 2.0
                        }
                    }
                }
            }
        }):
            with patch.object(self.auto_exec, '_plan_types', {'test_plan': 'scalp'}):
                with patch.object(self.auto_exec, '_detect_plan_type', return_value='scalp'):
                    # Price is far from entry (>2× tolerance = >10 points)
                    current_price = 2015.0  # 15 points away (far)
                    interval = self.auto_exec._calculate_adaptive_interval(plan, current_price)
                    
                    # Should use far_interval_seconds (60)
                    self.assertEqual(interval, 60, "Should use far interval when price is far from entry")
    
    def test_adaptive_interval_within_tolerance(self):
        """Test that adaptive intervals use close interval when price is within tolerance"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock config
        with patch.dict(self.auto_exec.config, {
            'optimized_intervals': {
                'adaptive_intervals': {
                    'enabled': True,
                    'plan_type_intervals': {
                        'scalp': {
                            'close_interval_seconds': 20,
                            'base_interval_seconds': 30,
                            'far_interval_seconds': 60
                        }
                    }
                }
            }
        }):
            with patch.object(self.auto_exec, '_plan_types', {'test_plan': 'scalp'}):
                with patch.object(self.auto_exec, '_detect_plan_type', return_value='scalp'):
                    # Price is within tolerance
                    current_price = 2002.0  # 2 points away (within tolerance)
                    interval = self.auto_exec._calculate_adaptive_interval(plan, current_price)
                    
                    # Should use close_interval_seconds (20)
                    self.assertEqual(interval, 20, "Should use close interval when price is within tolerance")
    
    def test_adaptive_interval_error_handling(self):
        """Test that adaptive intervals handle errors gracefully"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock config to raise exception
        with patch.object(self.auto_exec, 'config', {}):
            # Accessing config.get() will work, but _detect_plan_type might fail
            with patch.object(self.auto_exec, '_detect_plan_type', side_effect=Exception("Test error")):
                current_price = 2002.0
                interval = self.auto_exec._calculate_adaptive_interval(plan, current_price)
                
                # Should return base check_interval (15s) on error
                self.assertEqual(interval, 15, "Should return base interval on error")


if __name__ == '__main__':
    unittest.main()
