# =====================================
# tests/test_phase2_2_signal_learning.py
# =====================================
"""
Tests for Phase 2.2: Real-Time Signal Learning
Tests signal outcome storage, optimal parameters retrieval, and analytics
"""

import unittest
import sys
import os
import tempfile
import sqlite3
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone, timedelta

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.m1_signal_learner import RealTimeSignalLearner


class TestPhase2_2SignalLearning(unittest.TestCase):
    """Test cases for Phase 2.2 Real-Time Signal Learning"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database for each test
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Create signal learner instance
        self.learner = RealTimeSignalLearner(db_path=self.db_path)
    
    def tearDown(self):
        """Clean up test fixtures"""
        if self.learner:
            self.learner.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_database_creation(self):
        """Test that database and tables are created correctly"""
        # Check that database file exists
        self.assertTrue(os.path.exists(self.db_path))
        
        # Check that tables exist
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='signal_outcomes'
        """)
        table = cursor.fetchone()
        self.assertIsNotNone(table, "signal_outcomes table should exist")
        
        # Check indexes exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name LIKE 'idx_%'
        """)
        indexes = cursor.fetchall()
        self.assertGreater(len(indexes), 0, "Indexes should be created")
        conn.close()
    
    def test_store_signal_outcome(self):
        """Test storing signal outcomes"""
        event_id = self.learner.store_signal_outcome(
            symbol="XAUUSD",
            session="LONDON",
            confluence=75.5,
            signal_outcome="WIN",
            event_type="CHOCH",
            rr_achieved=2.5,
            volatility_state="EXPANDING",
            strategy_hint="BREAKOUT",
            initial_confidence=85.0,
            executed=True,
            trade_id="12345"
        )
        
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)
        
        # Verify data was stored
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM signal_outcomes WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()
        self.assertIsNotNone(row, "Signal outcome should be stored")
        conn.close()
    
    def test_store_signal_outcome_with_timestamps(self):
        """Test storing signal outcomes with detection and execution timestamps"""
        detection_ts = datetime.now(timezone.utc) - timedelta(seconds=30)
        execution_ts = datetime.now(timezone.utc)
        
        event_id = self.learner.store_signal_outcome(
            symbol="XAUUSD",
            session="NY",
            confluence=80.0,
            signal_outcome="WIN",
            signal_detection_timestamp=detection_ts,
            execution_timestamp=execution_ts,
            base_confluence=80.0,
            executed=True
        )
        
        # Verify latency was calculated
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT signal_to_execution_latency_ms 
            FROM signal_outcomes 
            WHERE event_id = ?
        """, (event_id,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        latency = row[0]
        self.assertIsNotNone(latency)
        self.assertGreater(latency, 0)
        self.assertLess(latency, 60000)  # Should be less than 60 seconds (30000ms expected)
        conn.close()
    
    def test_get_optimal_parameters_insufficient_data(self):
        """Test that optimal parameters return None with insufficient data"""
        params = self.learner.get_optimal_parameters(
            symbol="XAUUSD",
            session="LONDON",
            min_samples=10
        )
        self.assertIsNone(params, "Should return None with insufficient data")
    
    def test_get_optimal_parameters_sufficient_data(self):
        """Test optimal parameters calculation with sufficient data"""
        # Store multiple outcomes to build history
        for i in range(15):
            outcome = "WIN" if i < 10 else "LOSS"  # 10 wins, 5 losses = 66.7% win rate
            self.learner.store_signal_outcome(
                symbol="XAUUSD",
                session="LONDON",
                confluence=70.0 + (i * 0.5),
                signal_outcome=outcome,
                rr_achieved=2.5 if outcome == "WIN" else 0.5,
                executed=True
            )
        
        params = self.learner.get_optimal_parameters(
            symbol="XAUUSD",
            session="LONDON",
            min_samples=10
        )
        
        self.assertIsNotNone(params, "Should return parameters with sufficient data")
        self.assertIn('optimal_confluence_threshold', params)
        self.assertIn('session_bias_factor', params)
        self.assertIn('win_rate', params)
        self.assertIn('avg_rr_win', params)
        
        # Verify win rate calculation
        self.assertAlmostEqual(params['win_rate'], 10/15, places=2)
    
    def test_get_optimal_parameters_threshold_adjustment(self):
        """Test that thresholds adjust based on win rate"""
        # Low win rate scenario (< 60%)
        for i in range(15):
            outcome = "WIN" if i < 7 else "LOSS"  # 7 wins, 8 losses = 46.7% win rate
            self.learner.store_signal_outcome(
                symbol="XAUUSD",
                session="LONDON",
                confluence=70.0,
                signal_outcome=outcome,
                executed=True
            )
        
        params_low = self.learner.get_optimal_parameters("XAUUSD", "LONDON", min_samples=10)
        self.assertIsNotNone(params_low)
        # Threshold should be increased (base + adjustment)
        self.assertGreaterEqual(params_low['optimal_confluence_threshold'], 70.0)
        
        # High win rate scenario (> 75%)
        # Create new learner for clean test
        self.learner.close()
        os.unlink(self.db_path)
        self.learner = RealTimeSignalLearner(db_path=self.db_path)
        
        for i in range(15):
            outcome = "WIN" if i < 12 else "LOSS"  # 12 wins, 3 losses = 80% win rate
            self.learner.store_signal_outcome(
                symbol="XAUUSD",
                session="LONDON",
                confluence=70.0,
                signal_outcome=outcome,
                executed=True
            )
        
        params_high = self.learner.get_optimal_parameters("XAUUSD", "LONDON", min_samples=10)
        self.assertIsNotNone(params_high)
        # Threshold should be decreased (base - adjustment)
        self.assertLessEqual(params_high['optimal_confluence_threshold'], 70.0)
    
    def test_get_signal_to_execution_latency(self):
        """Test signal-to-execution latency calculation"""
        # Store outcomes with timestamps
        for i in range(5):
            detection_ts = datetime.now(timezone.utc) - timedelta(seconds=30 + i)
            execution_ts = datetime.now(timezone.utc) - timedelta(seconds=i)
            
            self.learner.store_signal_outcome(
                symbol="XAUUSD",
                session="LONDON",
                confluence=75.0,
                signal_outcome="WIN",
                signal_detection_timestamp=detection_ts,
                execution_timestamp=execution_ts,
                executed=True
            )
        
        latency_stats = self.learner.get_signal_to_execution_latency("XAUUSD", "LONDON")
        
        self.assertIsNotNone(latency_stats)
        self.assertIn('avg_latency_ms', latency_stats)
        self.assertIn('min_latency_ms', latency_stats)
        self.assertIn('max_latency_ms', latency_stats)
        self.assertIn('count', latency_stats)
        self.assertEqual(latency_stats['count'], 5)
        self.assertGreater(latency_stats['avg_latency_ms'], 0)
    
    def test_get_success_rate_by_session(self):
        """Test success rate calculation by session"""
        # Store outcomes for different sessions
        sessions = ["ASIAN", "LONDON", "NY", "OVERLAP"]
        for session in sessions:
            for i in range(10):
                outcome = "WIN" if i < 6 else "LOSS"  # 60% win rate for each
                self.learner.store_signal_outcome(
                    symbol="XAUUSD",
                    session=session,
                    confluence=70.0,
                    signal_outcome=outcome,
                    executed=True
                )
        
        success_rates = self.learner.get_success_rate_by_session("XAUUSD")
        
        self.assertIsNotNone(success_rates)
        self.assertEqual(len(success_rates), 4)
        for session in sessions:
            self.assertIn(session, success_rates)
            self.assertAlmostEqual(success_rates[session], 0.6, places=1)
    
    def test_get_confidence_volatility_correlation(self):
        """Test confidence-volatility correlation calculation"""
        # Store outcomes with different confidence and volatility states
        volatility_states = ["CONTRACTING", "STABLE", "EXPANDING"]
        for i, vol_state in enumerate(volatility_states):
            for j in range(10):
                confidence = 60.0 + (i * 10) + (j * 0.5)  # Increasing confidence
                self.learner.store_signal_outcome(
                    symbol="XAUUSD",
                    session="LONDON",
                    confluence=70.0,
                    signal_outcome="WIN",
                    volatility_state=vol_state,
                    initial_confidence=confidence,
                    executed=True
                )
        
        correlation = self.learner.get_confidence_volatility_correlation("XAUUSD")
        
        # Correlation should be positive (higher confidence with higher volatility)
        self.assertIsNotNone(correlation)
        self.assertIsInstance(correlation, float)
        # Note: Actual correlation value depends on data distribution
    
    def test_re_evaluate_metrics(self):
        """Test re-evaluation of all metrics"""
        # Store diverse outcomes
        for i in range(20):
            session = ["ASIAN", "LONDON", "NY"][i % 3]
            outcome = "WIN" if i < 12 else "LOSS"
            vol_state = ["CONTRACTING", "STABLE", "EXPANDING"][i % 3]
            
            self.learner.store_signal_outcome(
                symbol="XAUUSD",
                session=session,
                confluence=70.0 + (i * 0.5),
                signal_outcome=outcome,
                volatility_state=vol_state,
                initial_confidence=75.0 + (i * 0.3),
                executed=True
            )
        
        metrics = self.learner.re_evaluate_metrics("XAUUSD")
        
        self.assertIsNotNone(metrics)
        self.assertIn('signal_to_execution_latency_avg', metrics)
        self.assertIn('success_rate_by_session', metrics)
        self.assertIn('confidence_volatility_correlation', metrics)
        self.assertIn('recommended_adjustments', metrics)
    
    def test_cleanup_old_data(self):
        """Test cleanup of old data"""
        # Store old outcome (90+ days ago)
        old_date = datetime.now(timezone.utc) - timedelta(days=100)
        
        # Manually insert old record (since store_signal_outcome uses current timestamp)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO signal_outcomes 
            (event_id, symbol, event_type, timestamp, session, confluence, signal_outcome)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("old_event", "XAUUSDc", "CHOCH", old_date, "LONDON", 70.0, "WIN"))
        conn.commit()
        conn.close()
        
        # Store recent outcome
        self.learner.store_signal_outcome(
            symbol="XAUUSD",
            session="LONDON",
            confluence=75.0,
            signal_outcome="WIN"
        )
        
        # Cleanup old data
        self.learner.cleanup_old_data(days=90)
        
        # Verify old data is deleted
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM signal_outcomes WHERE event_id = 'old_event'")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 0, "Old data should be deleted")
        
        cursor.execute("SELECT COUNT(*) FROM signal_outcomes")
        total = cursor.fetchone()[0]
        self.assertGreater(total, 0, "Recent data should remain")
        conn.close()
    
    def test_multiple_symbols(self):
        """Test that learner handles multiple symbols correctly"""
        symbols = ["XAUUSD", "BTCUSD", "EURUSD"]
        
        for symbol in symbols:
            for i in range(10):
                self.learner.store_signal_outcome(
                    symbol=symbol,
                    session="LONDON",
                    confluence=70.0,
                    signal_outcome="WIN" if i < 6 else "LOSS",
                    executed=True
                )
        
        # Get parameters for each symbol
        for symbol in symbols:
            params = self.learner.get_optimal_parameters(symbol, "LONDON", min_samples=5)
            self.assertIsNotNone(params, f"Should have parameters for {symbol}")
            self.assertIn('win_rate', params)
    
    def test_event_id_uniqueness(self):
        """Test that event IDs are unique"""
        event_ids = []
        for i in range(10):
            event_id = self.learner.store_signal_outcome(
                symbol="XAUUSD",
                session="LONDON",
                confluence=70.0,
                signal_outcome="WIN"
            )
            event_ids.append(event_id)
        
        # All event IDs should be unique
        self.assertEqual(len(event_ids), len(set(event_ids)), "Event IDs should be unique")
    
    def test_symbol_normalization(self):
        """Test that symbols are normalized correctly (add 'c' suffix)"""
        event_id = self.learner.store_signal_outcome(
            symbol="XAUUSD",  # Without 'c'
            session="LONDON",
            confluence=70.0,
            signal_outcome="WIN"
        )
        
        # Check that symbol was normalized in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT symbol FROM signal_outcomes WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()
        self.assertEqual(row[0], "XAUUSDc", "Symbol should be normalized with 'c' suffix")
        conn.close()


if __name__ == '__main__':
    unittest.main()

