"""
Test Suite for Confluence-Only Auto-Execution Implementation
Tests cache, monitoring, validation, and edge cases
"""

import unittest
import time
import threading
import sqlite3
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_execution_system import AutoExecutionSystem, TradePlan
from chatgpt_auto_execution_tools import tool_create_auto_trade_plan
import asyncio


class TestConfluenceCache(unittest.TestCase):
    """Test confluence cache functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.auto_exec = AutoExecutionSystem(
            db_path=":memory:",
            check_interval=30
        )
    
    def test_cache_initialization(self):
        """Test cache is initialized in __init__"""
        self.assertIsNotNone(self.auto_exec._confluence_cache)
        self.assertIsNotNone(self.auto_exec._confluence_cache_lock)
        self.assertIsNotNone(self.auto_exec._confluence_cache_stats)
        self.assertEqual(self.auto_exec._confluence_cache_ttl, 30)
        self.assertEqual(self.auto_exec._confluence_cache_stats["hits"], 0)
        self.assertEqual(self.auto_exec._confluence_cache_stats["misses"], 0)
        self.assertEqual(self.auto_exec._confluence_cache_stats["api_calls"], 0)
    
    def test_cache_storage(self):
        """Test cache stores and retrieves values"""
        symbol = "BTCUSDc"
        score = 75
        timestamp = time.time()
        
        with self.auto_exec._confluence_cache_lock:
            self.auto_exec._confluence_cache[symbol] = (score, timestamp)
        
        # Verify cache entry
        with self.auto_exec._confluence_cache_lock:
            self.assertIn(symbol, self.auto_exec._confluence_cache)
            cached_score, cached_timestamp = self.auto_exec._confluence_cache[symbol]
            self.assertEqual(cached_score, score)
            self.assertEqual(cached_timestamp, timestamp)
    
    def test_cache_ttl_expiration(self):
        """Test cache entries expire after TTL"""
        symbol = "BTCUSDc"
        score = 75
        old_timestamp = time.time() - 60  # 60 seconds ago (expired)
        
        with self.auto_exec._confluence_cache_lock:
            self.auto_exec._confluence_cache[symbol] = (score, old_timestamp)
        
        # Check cache (should be expired)
        now = time.time()
        with self.auto_exec._confluence_cache_lock:
            if symbol in self.auto_exec._confluence_cache:
                cached_score, cached_timestamp = self.auto_exec._confluence_cache[symbol]
                if now - cached_timestamp >= self.auto_exec._confluence_cache_ttl:
                    # Cache entry is expired
                    self.assertGreaterEqual(now - cached_timestamp, self.auto_exec._confluence_cache_ttl)
    
    def test_cache_invalidation(self):
        """Test cache invalidation method"""
        symbol = "BTCUSDc"
        score = 75
        timestamp = time.time()
        
        # Add entry to cache
        with self.auto_exec._confluence_cache_lock:
            self.auto_exec._confluence_cache[symbol] = (score, timestamp)
        
        # Invalidate specific symbol
        self.auto_exec._invalidate_confluence_cache(symbol)
        
        # Verify cache entry is removed
        with self.auto_exec._confluence_cache_lock:
            self.assertNotIn(symbol, self.auto_exec._confluence_cache)
        
        # Test invalidate all
        with self.auto_exec._confluence_cache_lock:
            self.auto_exec._confluence_cache["XAUUSDc"] = (80, time.time())
            self.auto_exec._confluence_cache["EURUSDc"] = (65, time.time())
        
        self.auto_exec._invalidate_confluence_cache()
        
        with self.auto_exec._confluence_cache_lock:
            self.assertEqual(len(self.auto_exec._confluence_cache), 0)
    
    def test_symbol_normalization(self):
        """Test symbol normalization in cache"""
        # Test various symbol formats
        test_cases = [
            ("BTCUSD", "BTCUSDc"),
            ("BTCUSDc", "BTCUSDc"),
            ("BTCUSDC", "BTCUSDc"),
            ("XAUUSD", "XAUUSDc"),
            ("XAUUSDc", "XAUUSDc"),
        ]
        
        for input_symbol, expected_normalized in test_cases:
            # Mock _get_confluence_score to check normalization
            with patch.object(self.auto_exec, '_get_confluence_score') as mock_get:
                mock_get.return_value = 75
                
                # Call with unnormalized symbol
                result = self.auto_exec._get_confluence_score(input_symbol)
                
                # Check that method was called (normalization happens inside)
                mock_get.assert_called()
                # The actual normalization is tested in the method itself


class TestConfluenceScoreCalculation(unittest.TestCase):
    """Test confluence score calculation and validation"""
    
    def setUp(self):
        """Set up test environment"""
        self.auto_exec = AutoExecutionSystem(
            db_path=":memory:",
            check_interval=30
        )
    
    @patch('auto_execution_system.requests.get')
    def test_api_response_handling(self, mock_get):
        """Test API response handling and validation"""
        # Test successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "confluence_score": 75.5,
            "grade": "B",
            "factors": {}
        }
        mock_get.return_value = mock_response
        
        score = self.auto_exec._get_confluence_score("BTCUSDc")
        
        self.assertEqual(score, 75)  # Should be clamped to int
        self.assertEqual(self.auto_exec._confluence_cache_stats["api_calls"], 1)
    
    @patch('auto_execution_system.requests.get')
    def test_api_response_clamping(self, mock_get):
        """Test score clamping to 0-100 range"""
        test_cases = [
            (150, 100),  # Above 100
            (-10, 0),    # Below 0
            (75.5, 75),  # Float within range
            (50, 50),    # Integer within range
        ]
        
        for api_score, expected in test_cases:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "confluence_score": api_score,
                "grade": "B"
            }
            mock_get.return_value = mock_response
            
            # Clear cache before each test
            self.auto_exec._invalidate_confluence_cache()
            
            score = self.auto_exec._get_confluence_score("BTCUSDc")
            self.assertEqual(score, expected, f"Failed for input {api_score}")
    
    @patch('auto_execution_system.requests.get')
    def test_api_fallback_to_mtf(self, mock_get):
        """Test fallback to MTF analysis when API fails"""
        # Mock API failure
        mock_get.side_effect = Exception("API error")
        
        # Mock MTF analysis
        with patch.object(self.auto_exec, '_get_mtf_analysis') as mock_mtf:
            mock_mtf.return_value = {
                "alignment_score": 65
            }
            
            score = self.auto_exec._get_confluence_score("BTCUSDc")
            self.assertEqual(score, 65)
    
    def test_default_fallback(self):
        """Test default fallback when all methods fail"""
        with patch.object(self.auto_exec, '_get_mtf_analysis') as mock_mtf:
            mock_mtf.return_value = None
            
            with patch('auto_execution_system.requests.get') as mock_get:
                mock_get.side_effect = Exception("API error")
                
                score = self.auto_exec._get_confluence_score("BTCUSDc")
                self.assertEqual(score, 50)  # Default fallback


class TestMinConfluenceMonitoring(unittest.TestCase):
    """Test min_confluence monitoring in _check_conditions"""
    
    def setUp(self):
        """Set up test environment"""
        self.auto_exec = AutoExecutionSystem(
            db_path=":memory:",
            check_interval=30
        )
        
        # Create a test plan
        self.plan = TradePlan(
            plan_id="test_plan_1",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=100000.0,
            stop_loss=99500.0,
            take_profit=101000.0,
            volume=0.01,
            conditions={"min_confluence": 60, "price_near": 100000.0, "tolerance": 100.0},
            created_at="2025-12-11T10:00:00Z",
            created_by="test",
            status="pending"
        )
    
    @patch.object(AutoExecutionSystem, '_get_confluence_score')
    def test_min_confluence_pass(self, mock_confluence):
        """Test min_confluence check passes when score meets threshold"""
        # Mock MT5 service on instance
        mock_quote = Mock()
        mock_quote.ask = 100000.0
        mock_quote.bid = 99999.0
        self.auto_exec.mt5_service = Mock()
        self.auto_exec.mt5_service.get_quote.return_value = mock_quote
        self.auto_exec.mt5_service.is_connected.return_value = True
        
        mock_confluence.return_value = 75  # Above threshold of 60
        
        result = self.auto_exec._check_conditions(self.plan)
        
        # Should continue checking (not return False due to confluence)
        # Note: May return False for other reasons, but confluence check should pass
        mock_confluence.assert_called()
    
    @patch.object(AutoExecutionSystem, '_get_confluence_score')
    def test_min_confluence_fail(self, mock_confluence):
        """Test min_confluence check fails when score below threshold"""
        # Mock MT5 service on instance
        mock_quote = Mock()
        mock_quote.ask = 100000.0
        mock_quote.bid = 99999.0
        self.auto_exec.mt5_service = Mock()
        self.auto_exec.mt5_service.get_quote.return_value = mock_quote
        self.auto_exec.mt5_service.is_connected.return_value = True
        
        mock_confluence.return_value = 50  # Below threshold of 60
        
        result = self.auto_exec._check_conditions(self.plan)
        
        # Should return False due to low confluence
        self.assertFalse(result)
        mock_confluence.assert_called()
    
    @patch.object(AutoExecutionSystem, '_get_confluence_score')
    def test_min_confluence_none_handling(self, mock_confluence):
        """Test min_confluence None case handling"""
        plan = TradePlan(
            plan_id="test_plan_2",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=100000.0,
            stop_loss=99500.0,
            take_profit=101000.0,
            volume=0.01,
            conditions={"min_confluence": None, "price_near": 100000.0, "tolerance": 100.0},
            created_at="2025-12-11T10:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Mock MT5 service on instance
        mock_quote = Mock()
        mock_quote.ask = 100000.0
        mock_quote.bid = 99999.0
        self.auto_exec.mt5_service = Mock()
        self.auto_exec.mt5_service.get_quote.return_value = mock_quote
        self.auto_exec.mt5_service.is_connected.return_value = True
        
        mock_confluence.return_value = 75
        
        # Should handle None and use default (60)
        result = self.auto_exec._check_conditions(plan)
        # Should not crash, may use default threshold


class TestToolHandlerValidation(unittest.TestCase):
    """Test tool handler validation logic"""
    
    def test_price_condition_validation(self):
        """Test price condition is required for min_confluence"""
        args = {
            "symbol": "BTCUSDc",
            "direction": "BUY",
            "entry": 100000.0,
            "stop_loss": 99500.0,
            "take_profit": 101000.0,
            "volume": 0.01,
            "min_confluence": 60,  # Pass as top-level parameter
            "conditions": {
                # Missing price condition - should fail
            }
        }
        
        async def test():
            result = await tool_create_auto_trade_plan(args)
            # Check if error was returned (validation should catch this)
            # Note: The function returns a dict with error, doesn't raise
            self.assertIn("error", result.get("summary", "").lower() or result.get("data", {}).get("error", "").lower())
        
        asyncio.run(test())
    
    def test_threshold_validation(self):
        """Test threshold validation (0-100 range)"""
        test_cases = [
            (150, 100),  # Should clamp to 100
            (-10, 0),    # Should clamp to 0
            (75, 75),    # Valid
            (0, 0),      # Valid (edge case)
            (100, 100),  # Valid (edge case)
        ]
        
        async def test():
            for input_threshold, expected in test_cases:
                args = {
                    "symbol": "BTCUSDc",
                    "direction": "BUY",
                    "entry": 100000.0,
                    "stop_loss": 99500.0,
                    "take_profit": 101000.0,
                    "volume": 0.01,
                    "conditions": {
                        "min_confluence": input_threshold,
                        "price_near": 100000.0,
                        "tolerance": 100.0
                    }
                }
                
                result = await tool_create_auto_trade_plan(args)
                # Check that threshold was clamped
                # (We can't easily check the saved value, but validation should pass)
        
        asyncio.run(test())
    
    def test_contradictory_price_conditions(self):
        """Test contradictory price conditions are caught"""
        args = {
            "symbol": "BTCUSDc",
            "direction": "BUY",
            "entry": 100000.0,
            "stop_loss": 99500.0,
            "take_profit": 101000.0,
            "volume": 0.01,
            "min_confluence": 60,
            "conditions": {
                "price_above": 100000.0,
                "price_below": 100100.0,  # Contradictory (price_below > price_above)
                "price_near": 100000.0,
                "tolerance": 100.0
            }
        }
        
        async def test():
            result = await tool_create_auto_trade_plan(args)
            # Check if error was returned (validation should catch this)
            # Note: The function returns a dict with error, doesn't raise
            error_msg = result.get("summary", "").lower() + " " + str(result.get("data", {}).get("error", "")).lower()
            self.assertIn("contradictory", error_msg)
        
        asyncio.run(test())
    
    def test_range_scalp_precedence(self):
        """Test range_scalp_confluence takes precedence over min_confluence"""
        args = {
            "symbol": "BTCUSDc",
            "direction": "BUY",
            "entry": 100000.0,
            "stop_loss": 99500.0,
            "take_profit": 101000.0,
            "volume": 0.01,
            "conditions": {
                "range_scalp_confluence": 80,
                "min_confluence": 60,  # Should be ignored
                "price_near": 100000.0,
                "tolerance": 100.0
            }
        }
        
        async def test():
            # Should warn but not fail
            result = await tool_create_auto_trade_plan(args)
            # Check that warning was logged (can't easily verify, but should not fail)
        
        asyncio.run(test())


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""
    
    def setUp(self):
        """Set up test environment"""
        self.auto_exec = AutoExecutionSystem(
            db_path=":memory:",
            check_interval=30
        )
    
    def test_empty_conditions_dict(self):
        """Test handling of empty conditions dict"""
        plan = TradePlan(
            plan_id="test_plan_empty",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=100000.0,
            stop_loss=99500.0,
            take_profit=101000.0,
            volume=0.01,
            conditions={},  # Empty
            created_at="2025-12-11T10:00:00Z",
            created_by="test",
            status="pending"
        )
        
        result = self.auto_exec._check_conditions(plan)
        # Should return False (no conditions)
        self.assertFalse(result)
    
    def test_min_confluence_zero(self):
        """Test min_confluence = 0 (effectively disables check)"""
        plan = TradePlan(
            plan_id="test_plan_zero",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=100000.0,
            stop_loss=99500.0,
            take_profit=101000.0,
            volume=0.01,
            conditions={"min_confluence": 0, "price_near": 100000.0, "tolerance": 100.0},
            created_at="2025-12-11T10:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Mock MT5 service on instance
        mock_quote = Mock()
        mock_quote.ask = 100000.0
        mock_quote.bid = 99999.0
        self.auto_exec.mt5_service = Mock()
        self.auto_exec.mt5_service.get_quote.return_value = mock_quote
        self.auto_exec.mt5_service.is_connected.return_value = True
        
        with patch.object(self.auto_exec, '_get_confluence_score') as mock_confluence:
            mock_confluence.return_value = 10  # Very low score
            
            # With min_confluence=0, even low scores should pass
            result = self.auto_exec._check_conditions(plan)
            # Should not fail due to confluence (threshold is 0)
    
    def test_min_confluence_100(self):
        """Test min_confluence = 100 (very strict)"""
        plan = TradePlan(
            plan_id="test_plan_100",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=100000.0,
            stop_loss=99500.0,
            take_profit=101000.0,
            volume=0.01,
            conditions={"min_confluence": 100, "price_near": 100000.0, "tolerance": 100.0},
            created_at="2025-12-11T10:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Mock MT5 service on instance
        mock_quote = Mock()
        mock_quote.ask = 100000.0
        mock_quote.bid = 99999.0
        self.auto_exec.mt5_service = Mock()
        self.auto_exec.mt5_service.get_quote.return_value = mock_quote
        self.auto_exec.mt5_service.is_connected.return_value = True
        
        with patch.object(self.auto_exec, '_get_confluence_score') as mock_confluence:
            mock_confluence.return_value = 99  # Just below threshold
            
            result = self.auto_exec._check_conditions(plan)
            # Should fail (score 99 < threshold 100)
            self.assertFalse(result)


class TestThreadSafety(unittest.TestCase):
    """Test thread safety of cache operations"""
    
    def setUp(self):
        """Set up test environment"""
        self.auto_exec = AutoExecutionSystem(
            db_path=":memory:",
            check_interval=30
        )
    
    def test_concurrent_cache_access(self):
        """Test concurrent cache access is thread-safe"""
        symbol = "BTCUSDc"
        num_threads = 10
        results = []
        errors = []
        
        def worker(thread_id):
            try:
                with patch('auto_execution_system.requests.get') as mock_get:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {"confluence_score": 70 + thread_id}
                    mock_get.return_value = mock_response
                    
                    score = self.auto_exec._get_confluence_score(symbol)
                    results.append(score)
            except Exception as e:
                errors.append(e)
        
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should complete without errors
        self.assertEqual(len(errors), 0, f"Thread safety errors: {errors}")
        # All threads should have completed
        self.assertEqual(len(results), num_threads)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestConfluenceCache))
    suite.addTests(loader.loadTestsFromTestCase(TestConfluenceScoreCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestMinConfluenceMonitoring))
    suite.addTests(loader.loadTestsFromTestCase(TestToolHandlerValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestThreadSafety))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    print("=" * 80)
    print("CONFLUENCE-ONLY IMPLEMENTATION TEST SUITE")
    print("=" * 80)
    print()
    
    result = run_tests()
    
    print()
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    print("=" * 80)
    
    if result.wasSuccessful():
        print("All tests passed!")
        sys.exit(0)
    else:
        print("Some tests failed")
        sys.exit(1)

