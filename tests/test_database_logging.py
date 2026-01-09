"""
Comprehensive Database and Logging Test Suite
Tests all logging infrastructure and analytics
"""

import sys
import time
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_success(msg):
    print(f"{GREEN}[PASS] {msg}{RESET}")

def print_error(msg):
    print(f"{RED}[FAIL] {msg}{RESET}")

def print_info(msg):
    print(f"{BLUE}[INFO] {msg}{RESET}")

def print_warning(msg):
    print(f"{YELLOW}[WARN] {msg}{RESET}")


def test_chatgpt_logger():
    """Test ChatGPT conversation logging"""
    print_info("Testing ChatGPT Logger...")
    
    try:
        from infra.chatgpt_logger import ChatGPTLogger
        logger = ChatGPTLogger()
        
        # Start conversation
        conv_id = logger.start_conversation(user_id=12345, chat_id=67890)
        assert conv_id is not None, "Conversation ID should not be None"
        print_success(f"Started conversation {conv_id}")
        
        # Add messages
        logger.log_message(conv_id, "user", "Hello, analyze XAUUSD for me", tokens_used=10)
        logger.log_message(conv_id, "assistant", "Here's the analysis...", tokens_used=50)
        logger.log_message(conv_id, "user", "What about BTCUSD?", tokens_used=8)
        logger.log_message(conv_id, "assistant", "For BTC...", tokens_used=45)
        print_success("Added 4 messages")
        
        # End conversation
        logger.end_conversation(conv_id)
        print_success("Ended conversation")
        
        # Get recent conversations
        recent = logger.get_user_conversations(user_id=12345, limit=5)
        assert len(recent) > 0, "Should have at least 1 conversation"
        print_success(f"Retrieved {len(recent)} recent conversations")
        
        # Verify message count in conversation
        assert recent[0]["message_count"] == 4, f"Should have 4 messages, got {recent[0]['message_count']}"
        print_success("Verified message count")
        
        return True
        
    except Exception as e:
        print_error(f"ChatGPT Logger test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_recommendation_logger():
    """Test AI recommendation logging"""
    print_info("Testing Recommendation Logger...")
    
    try:
        from infra.recommendation_logger import RecommendationLogger
        logger = RecommendationLogger()
        
        # Log recommendation
        rec_id = logger.log_recommendation(
            user_id=12345,
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2650.00,
            stop_loss=2640.00,
            take_profit=2670.00,
            reasoning="Strong bullish momentum on M15",
            confidence=85,
            market_regime="TRENDING",
            timeframe="M15",
            generation_time=1.2
        )
        assert rec_id is not None, "Recommendation ID should not be None"
        print_success(f"Logged recommendation {rec_id}")
        
        # Mark as executed
        logger.mark_executed(rec_id, ticket=123456)
        print_success("Marked recommendation as executed")
        
        # Update result
        logger.update_result(rec_id, pnl=250.50, r_multiple=2.05)
        print_success("Updated recommendation result")
        
        # Get statistics
        stats = logger.get_recommendation_stats(days=30)
        assert stats["total_recommendations"] > 0, "Should have recommendations"
        print_success(f"Retrieved statistics: {stats['total_recommendations']} total")
        
        # Get recent recommendations
        recent = logger.get_recent_recommendations(limit=5)
        assert len(recent) > 0, "Should have recent recommendations"
        print_success(f"Retrieved {len(recent)} recent recommendations")
        
        return True
        
    except Exception as e:
        print_error(f"Recommendation Logger test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_analytics_logger():
    """Test user analytics logging"""
    print_info("Testing Analytics Logger...")
    
    try:
        from infra.analytics_logger import AnalyticsLogger
        logger = AnalyticsLogger()
        
        # Log various actions
        logger.log_action(12345, 67890, "bot_start")
        logger.log_action(12345, 67890, "menu_button", {"button": "analyze_XAUUSD"})
        logger.log_action(12345, 67890, "analysis_request", {"symbol": "XAUUSD"})
        logger.log_action(12345, 67890, "chatgpt_start")
        logger.log_action(12345, 67890, "chatgpt_end", {"message_count": 6})
        print_success("Logged 5 user actions")
        
        # Get user stats
        stats = logger.get_user_stats(user_id=12345, days=30)
        assert stats["total_actions"] >= 5, f"Should have at least 5 actions, got {stats['total_actions']}"
        print_success(f"User stats: {stats['total_actions']} total actions")
        
        # Get popular actions
        popular = logger.get_popular_actions(days=30, limit=5)
        assert len(popular) > 0, "Should have popular actions"
        print_success(f"Retrieved {len(popular)} popular actions")
        
        # Get engagement metrics
        engagement = logger.get_user_engagement(days=30)
        assert engagement["total_actions"] > 0, "Should have actions"
        print_success(f"Engagement: {engagement['unique_users']} users, {engagement['total_actions']} actions")
        
        return True
        
    except Exception as e:
        print_error(f"Analytics Logger test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_signal_scanner_logger():
    """Test signal scanner logging"""
    print_info("Testing Signal Scanner Logger / Journal Events...")
    
    try:
        # Signal scanner results are logged to signal_scans table
        import sqlite3
        con = sqlite3.connect("data/journal.sqlite")
        cur = con.cursor()
        
        # Check if signal_scans table exists (created by SignalScannerLogger)
        cur.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='signal_scans'
        """)
        
        if cur.fetchone():
            # Get count of scans
            cur.execute("SELECT COUNT(*) FROM signal_scans")
            count = cur.fetchone()[0]
            print_success(f"Signal scans table exists with {count} scans")
        else:
            print_warning("Signal scans table not yet created (needs first scan)")
        
        con.close()
        return True
        
    except Exception as e:
        print_error(f"Signal Scanner Logger test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dashboard_queries():
    """Test performance dashboard queries"""
    print_info("Testing Dashboard Queries...")
    
    try:
        from infra.dashboard_queries import PerformanceDashboard
        dashboard = PerformanceDashboard()
        
        # Full dashboard
        data = dashboard.get_full_dashboard(days=30)
        assert "recommendations" in data, "Should have recommendations data"
        assert "engagement" in data, "Should have engagement data"
        assert "trading" in data, "Should have trading data"
        assert "chatgpt" in data, "Should have ChatGPT data"
        print_success("Retrieved full dashboard")
        
        # Recommendation performance
        rec_perf = dashboard.get_recommendation_performance(days=30)
        print_success(f"Rec performance: {rec_perf['total_recommendations']} total")
        
        # User engagement
        engagement = dashboard.get_user_engagement(days=30)
        print_success(f"Engagement: {engagement['total_actions']} actions")
        
        # Symbol dashboard
        symbol_data = dashboard.get_symbol_dashboard("XAUUSD", days=30)
        print_success(f"Symbol dashboard: {symbol_data['total_recommendations']} recs for XAUUSD")
        
        # Performance trends
        trends = dashboard.get_performance_trends(days=90, interval_days=7)
        print_success(f"Trends: {trends['total_periods']} periods")
        
        # Confidence correlation
        conf_corr = dashboard.get_confidence_correlation(days=30)
        print_success(f"Confidence analysis: {len(conf_corr['confidence_ranges'])} ranges")
        
        return True
        
    except Exception as e:
        print_error(f"Dashboard Queries test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ml_exporter():
    """Test ML data export"""
    print_info("Testing ML Exporter...")
    
    try:
        from infra.ml_exporter import MLExporter
        exporter = MLExporter()
        
        # Get statistics
        stats = exporter.get_feature_statistics()
        print_success(f"ML stats: {stats['training_samples_available']} training samples")
        
        # Export CSV
        csv_path = exporter.export_recommendations_csv(output_file="data/test_ml_export.csv")
        assert Path(csv_path).exists(), "CSV file should exist"
        print_success(f"Exported CSV: {csv_path}")
        
        # Export feature matrix
        json_path = exporter.export_feature_matrix(output_file="data/test_ml_features.json")
        assert Path(json_path).exists(), "JSON file should exist"
        print_success(f"Exported feature matrix: {json_path}")
        
        # Clean up test files
        Path(csv_path).unlink(missing_ok=True)
        Path(json_path).unlink(missing_ok=True)
        print_success("Cleaned up test export files")
        
        return True
        
    except Exception as e:
        print_error(f"ML Exporter test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ab_testing():
    """Test A/B testing framework"""
    print_info("Testing A/B Testing Framework...")
    
    try:
        from infra.ab_testing import ABTestFramework, ABVariant
        ab = ABTestFramework()
        
        # Create experiment
        variants = [
            ABVariant("control", "Control", "Baseline strategy", {"min_confidence": 70}, True),
            ABVariant("test_a", "Test A", "Higher confidence", {"min_confidence": 80}),
            ABVariant("test_b", "Test B", "Lower RR", {"min_rr": 1.5})
        ]
        
        exp_id = ab.create_experiment(
            f"test_experiment_{int(time.time())}",
            "Test confidence thresholds",
            variants
        )
        print_success(f"Created experiment {exp_id}")
        
        # Assign variants to users
        variant1 = ab.assign_variant(f"test_experiment_{int(time.time())}", user_id=12345)
        print_success(f"Assigned variant: {variant1}")
        
        # Get experiment results
        results = ab.get_experiment_results(f"test_experiment_{int(time.time())}")
        print_success(f"Retrieved experiment results: {len(results)} variants")
        
        # List experiments
        experiments = ab.list_experiments()
        assert len(experiments) > 0, "Should have experiments"
        print_success(f"Listed {len(experiments)} experiments")
        
        return True
        
    except Exception as e:
        print_error(f"A/B Testing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("DATABASE & LOGGING INFRASTRUCTURE TEST SUITE")
    print("="*60 + "\n")
    
    tests = [
        ("ChatGPT Logger", test_chatgpt_logger),
        ("Recommendation Logger", test_recommendation_logger),
        ("Analytics Logger", test_analytics_logger),
        ("Signal Scanner Logger", test_signal_scanner_logger),
        ("Dashboard Queries", test_dashboard_queries),
        ("ML Exporter", test_ml_exporter),
        ("A/B Testing", test_ab_testing)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'-'*60}")
        print(f"Testing: {test_name}")
        print('-'*60)
        
        try:
            success = test_func()
            results[test_name] = success
        except Exception as e:
            print_error(f"Unexpected error in {test_name}: {e}")
            results[test_name] = False
        
        time.sleep(0.1)  # Small delay between tests
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, success in results.items():
        status = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
        print(f"{test_name:30s} {status}")
    
    print("-"*60)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print_success("All tests passed!")
        return 0
    else:
        print_error(f"{total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

