"""
Unit tests for StrategyPerformanceTracker.get_strategy_stats_by_regime
"""

import unittest
import sqlite3
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# Import the tracker
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.strategy_performance_tracker import StrategyPerformanceTracker


class TestStrategyPerformanceTrackerRegime(unittest.TestCase):
    """Test cases for regime-based strategy stats"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.tracker = StrategyPerformanceTracker(db_path=self.temp_db.name)
        
        # Add test data
        self._populate_test_data()
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def _populate_test_data(self):
        """Populate database with test trades"""
        strategy = "INSIDE_BAR_VOLATILITY_TRAP"
        symbol = "XAUUSDc"
        
        # Add 15 trades in STABLE regime (exact match)
        for i in range(15):
            entry_time = (datetime.now() - timedelta(days=i)).isoformat()
            exit_time = (datetime.now() - timedelta(days=i) + timedelta(minutes=90)).isoformat()
            result = "win" if i % 3 != 0 else "loss"
            rr = 2.0 if result == "win" else -1.0
            self.tracker.record_trade(
                strategy_name=strategy,
                symbol=symbol,
                result=result,
                pnl=100.0 if result == "win" else -50.0,
                rr=rr,
                entry_time=entry_time,
                exit_time=exit_time,
                regime="STABLE"
            )
        
        # Add 20 trades in "stable" regime (fuzzy match)
        for i in range(20):
            entry_time = (datetime.now() - timedelta(days=i+15)).isoformat()
            exit_time = (datetime.now() - timedelta(days=i+15) + timedelta(minutes=100)).isoformat()
            result = "win" if i % 2 == 0 else "loss"
            rr = 1.8 if result == "win" else -1.2
            self.tracker.record_trade(
                strategy_name=strategy,
                symbol=symbol,
                result=result,
                pnl=90.0 if result == "win" else -60.0,
                rr=rr,
                entry_time=entry_time,
                exit_time=exit_time,
                regime="stable"
            )
        
        # Add 5 trades in VOLATILE regime (different regime)
        for i in range(5):
            entry_time = (datetime.now() - timedelta(days=i+35)).isoformat()
            exit_time = (datetime.now() - timedelta(days=i+35) + timedelta(minutes=45)).isoformat()
            result = "win" if i % 2 == 0 else "loss"
            rr = 2.5 if result == "win" else -1.5
            self.tracker.record_trade(
                strategy_name=strategy,
                symbol=symbol,
                result=result,
                pnl=150.0 if result == "win" else -75.0,
                rr=rr,
                entry_time=entry_time,
                exit_time=exit_time,
                regime="VOLATILE"
            )
    
    def test_get_strategy_stats_exact_match(self):
        """Test getting stats with exact regime match"""
        stats = self.tracker.get_strategy_stats_by_regime(
            symbol="XAUUSDc",
            strategy_name="INSIDE_BAR_VOLATILITY_TRAP",
            current_regime="STABLE"
        )
        
        self.assertIsNotNone(stats)
        self.assertEqual(stats["strategy"], "INSIDE_BAR_VOLATILITY_TRAP")
        self.assertEqual(stats["regime"], "STABLE")
        self.assertGreaterEqual(stats["sample_size"], 15)
        self.assertIn("win_rate", stats)
        self.assertIn("avg_rr", stats)
        self.assertEqual(stats["regime_match_quality"], "exact")
    
    def test_get_strategy_stats_fuzzy_match(self):
        """Test getting stats with fuzzy regime match"""
        stats = self.tracker.get_strategy_stats_by_regime(
            symbol="XAUUSDc",
            strategy_name="INSIDE_BAR_VOLATILITY_TRAP",
            current_regime="stable"
        )
        
        self.assertIsNotNone(stats)
        self.assertGreaterEqual(stats["sample_size"], 10)
        self.assertIn(stats["regime_match_quality"], ["exact", "fuzzy", "approximate"])
    
    def test_get_strategy_stats_insufficient_data(self):
        """Test getting stats with insufficient data (< 10 trades)"""
        # Create new strategy with < 10 trades
        for i in range(5):
            self.tracker.record_trade(
                strategy_name="NEW_STRATEGY",
                symbol="XAUUSDc",
                result="win",
                pnl=100.0,
                rr=2.0,
                regime="STABLE"
            )
        
        stats = self.tracker.get_strategy_stats_by_regime(
            symbol="XAUUSDc",
            strategy_name="NEW_STRATEGY",
            current_regime="STABLE"
        )
        
        # Should return None if < 10 trades
        self.assertIsNone(stats)
    
    def test_get_strategy_stats_no_match(self):
        """Test getting stats with no regime match"""
        stats = self.tracker.get_strategy_stats_by_regime(
            symbol="XAUUSDc",
            strategy_name="INSIDE_BAR_VOLATILITY_TRAP",
            current_regime="UNKNOWN_REGIME"
        )
        
        # May return None or approximate match
        if stats is not None:
            self.assertEqual(stats["regime_match_quality"], "approximate")
    
    def test_get_strategy_stats_confidence_levels(self):
        """Test confidence levels based on sample size"""
        # High confidence (>= 30 trades, exact/fuzzy match)
        stats = self.tracker.get_strategy_stats_by_regime(
            symbol="XAUUSDc",
            strategy_name="INSIDE_BAR_VOLATILITY_TRAP",
            current_regime="STABLE"
        )
        
        if stats and stats["sample_size"] >= 30:
            self.assertIn(stats["confidence"], ["high", "medium"])
    
    def test_get_strategy_stats_calculations(self):
        """Test that stats are calculated correctly"""
        stats = self.tracker.get_strategy_stats_by_regime(
            symbol="XAUUSDc",
            strategy_name="INSIDE_BAR_VOLATILITY_TRAP",
            current_regime="STABLE"
        )
        
        if stats:
            self.assertGreaterEqual(stats["win_rate"], 0.0)
            self.assertLessEqual(stats["win_rate"], 1.0)
            self.assertIsNotNone(stats["sample_size"])
            self.assertGreater(stats["sample_size"], 0)
    
    def test_regime_column_migration(self):
        """Test that regime column exists in database"""
        conn = sqlite3.connect(self.temp_db.name)
        cursor = conn.cursor()
        
        # Check if regime column exists
        cursor.execute("PRAGMA table_info(trade_results)")
        columns = [row[1] for row in cursor.fetchall()]
        
        conn.close()
        
        self.assertIn("regime", columns)
    
    def test_record_trade_with_regime(self):
        """Test recording trade with regime"""
        self.tracker.record_trade(
            strategy_name="TEST_STRATEGY",
            symbol="XAUUSDc",
            result="win",
            pnl=100.0,
            rr=2.0,
            regime="STABLE"
        )
        
        # Verify trade was recorded with regime
        conn = sqlite3.connect(self.temp_db.name)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT regime FROM trade_results
            WHERE strategy_name = 'TEST_STRATEGY'
        """)
        row = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "STABLE")


if __name__ == '__main__':
    unittest.main()

