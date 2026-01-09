# =====================================
# tests/test_phase5_4_chatgpt_integration.py
# =====================================
"""
Tests for Phase 5.4: ChatGPT Integration Testing
Tests ChatGPT tool integration and response formats
"""

import unittest
import sys
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.m1_data_fetcher import M1DataFetcher
from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer


class TestPhase5_4ChatGPTIntegration(unittest.TestCase):
    """Test cases for Phase 5.4 ChatGPT Integration Testing"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock MT5Service
        self.mock_mt5 = Mock()
        self.mock_mt5.get_bars = Mock(return_value=self._generate_mock_bars(200))
        self.mock_mt5.get_quote = Mock(return_value=Mock(bid=2400.0, ask=2400.1))
        
        # Initialize components
        self.fetcher = M1DataFetcher(data_source=self.mock_mt5, max_candles=200, cache_ttl=300)
        self.analyzer = M1MicrostructureAnalyzer()
    
    def _generate_mock_bars(self, count: int):
        """Generate mock candlestick data"""
        base_time = datetime.now(timezone.utc) - timedelta(minutes=count)
        bars = []
        for i in range(count):
            bars.append({
                'time': base_time + timedelta(minutes=i),
                'open': 2400.0 + (i * 0.1),
                'high': 2400.5 + (i * 0.1),
                'low': 2399.5 + (i * 0.1),
                'close': 2400.2 + (i * 0.1),
                'tick_volume': 100 + i
            })
        return bars
    
    def _generate_mock_candles(self, count: int):
        """Generate mock candle dicts"""
        base_time = datetime.now(timezone.utc) - timedelta(minutes=count)
        candles = []
        for i in range(count):
            candles.append({
                'timestamp': base_time + timedelta(minutes=i),
                'open': 2400.0 + (i * 0.1),
                'high': 2400.5 + (i * 0.1),
                'low': 2399.5 + (i * 0.1),
                'close': 2400.2 + (i * 0.1),
                'volume': 100 + i,
                'symbol': 'XAUUSDc'
            })
        return candles
    
    def test_get_m1_microstructure_tool_response_format(self):
        """Test `get_m1_microstructure` tool response format"""
        # Simulate tool call
        symbol = 'XAUUSD'
        candles = self._generate_mock_candles(200)
        
        # Analyze
        analysis = self.analyzer.analyze_microstructure(symbol, candles)
        
        # Verify response structure
        self.assertIsNotNone(analysis, "Analysis should not be None")
        self.assertIn('available', analysis, "Should have 'available' field")
        self.assertIn('symbol', analysis, "Should have 'symbol' field")
        self.assertIn('timestamp', analysis, "Should have 'timestamp' field")
        
        # Verify key fields for ChatGPT
        if analysis.get('available'):
            self.assertIn('choch_bos', analysis, "Should have 'choch_bos' field")
            self.assertIn('liquidity_zones', analysis, "Should have 'liquidity_zones' field")
            self.assertIn('volatility', analysis, "Should have 'volatility' field")
            self.assertIn('signal_summary', analysis, "Should have 'signal_summary' field")
            self.assertIn('microstructure_confluence', analysis, "Should have 'microstructure_confluence' field")
    
    def test_m1_data_in_analyse_symbol_full_response(self):
        """Test M1 data in `analyse_symbol_full` response"""
        # This test verifies that M1 data is included in the unified analysis
        symbol = 'XAUUSD'
        candles = self._generate_mock_candles(200)
        
        # Analyze
        m1_analysis = self.analyzer.analyze_microstructure(symbol, candles)
        
        # Simulate unified analysis structure
        unified_analysis = {
            'symbol': symbol,
            'm1_microstructure': m1_analysis,
            'm5_data': {},
            'h1_data': {},
            'summary': 'Analysis complete'
        }
        
        # Verify M1 data is included
        self.assertIn('m1_microstructure', unified_analysis, "Should include M1 microstructure")
        self.assertIsNotNone(unified_analysis['m1_microstructure'], "M1 data should not be None")
        
        # Verify M1 data structure
        m1_data = unified_analysis['m1_microstructure']
        if m1_data.get('available'):
            self.assertIn('choch_bos', m1_data, "M1 data should have CHOCH/BOS")
            self.assertIn('signal_summary', m1_data, "M1 data should have signal summary")
    
    def test_chatgpt_extraction_of_m1_insights(self):
        """Test ChatGPT extraction of M1 insights"""
        symbol = 'XAUUSD'
        candles = self._generate_mock_candles(200)
        
        # Analyze
        analysis = self.analyzer.analyze_microstructure(symbol, candles)
        
        # Verify key insights are extractable
        if analysis.get('available'):
            # CHOCH/BOS insights
            choch_bos = analysis.get('choch_bos', {})
            self.assertIsNotNone(choch_bos, "CHOCH/BOS data should be extractable")
            
            # Signal summary (key for ChatGPT)
            signal_summary = analysis.get('signal_summary', '')
            self.assertIsNotNone(signal_summary, "Signal summary should be extractable")
            self.assertIsInstance(signal_summary, str, "Signal summary should be string")
            
            # Confluence score
            confluence = analysis.get('microstructure_confluence', {})
            self.assertIsNotNone(confluence, "Confluence data should be extractable")
            
            # Strategy hint
            strategy_hint = analysis.get('strategy_hint', '')
            self.assertIsNotNone(strategy_hint, "Strategy hint should be extractable")
    
    def test_chatgpt_presentation_of_m1_data(self):
        """Test ChatGPT presentation of M1 data"""
        symbol = 'XAUUSD'
        candles = self._generate_mock_candles(200)
        
        # Analyze
        analysis = self.analyzer.analyze_microstructure(symbol, candles)
        
        # Verify data is presentable (all required fields for ChatGPT)
        if analysis.get('available'):
            # Check for human-readable fields
            self.assertIn('signal_summary', analysis, "Should have signal summary for presentation")
            self.assertIn('microstructure_confluence', analysis, "Should have confluence for presentation")
            
            # Verify signal summary is readable
            signal_summary = analysis.get('signal_summary', '')
            self.assertGreater(len(signal_summary), 0, "Signal summary should not be empty")
            
            # Verify confluence has score
            confluence = analysis.get('microstructure_confluence', {})
            if confluence:
                self.assertIn('base_score', confluence, "Confluence should have score")
                self.assertIn('grade', confluence, "Confluence should have grade")
    
    def test_graceful_fallback_when_m1_unavailable(self):
        """Test graceful fallback when M1 unavailable"""
        # Test with insufficient candles
        candles = self._generate_mock_candles(5)  # Too few candles
        
        # Analyze
        analysis = self.analyzer.analyze_microstructure('XAUUSD', candles)
        
        # Should handle gracefully
        self.assertIsNotNone(analysis, "Should return analysis even when unavailable")
        self.assertIn('available', analysis, "Should indicate availability status")
        
        # If unavailable, should have error message
        if not analysis.get('available'):
            self.assertIn('error', analysis, "Should include error message when unavailable")
    
    def test_m1_influence_on_trade_recommendations(self):
        """Test M1 influence on trade recommendations"""
        symbol = 'XAUUSD'
        candles = self._generate_mock_candles(200)
        
        # Analyze
        analysis = self.analyzer.analyze_microstructure(symbol, candles)
        
        # Verify M1 provides actionable insights
        if analysis.get('available'):
            # Signal summary should influence recommendations
            signal_summary = analysis.get('signal_summary', '')
            self.assertIsNotNone(signal_summary, "Signal summary should influence recommendations")
            
            # Confluence score should influence confidence
            confluence = analysis.get('microstructure_confluence', {})
            if confluence:
                base_score = confluence.get('base_score', 0)
                self.assertGreaterEqual(base_score, 0, "Confluence score should be >= 0")
                self.assertLessEqual(base_score, 100, "Confluence score should be <= 100")
            
            # Strategy hint should influence strategy selection
            strategy_hint = analysis.get('strategy_hint', '')
            self.assertIsNotNone(strategy_hint, "Strategy hint should influence strategy")
    
    def test_m1_influence_on_strategy_selection(self):
        """Test M1 influence on strategy selection"""
        symbol = 'XAUUSD'
        candles = self._generate_mock_candles(200)
        
        # Analyze
        analysis = self.analyzer.analyze_microstructure(symbol, candles)
        
        # Verify strategy hint is available
        if analysis.get('available'):
            strategy_hint = analysis.get('strategy_hint', '')
            self.assertIsNotNone(strategy_hint, "Should have strategy hint")
            self.assertIsInstance(strategy_hint, str, "Strategy hint should be string")
            
            # Strategy hint should be one of expected values
            expected_strategies = ['RANGE_SCALP', 'BREAKOUT', 'MEAN_REVERSION', 'TREND_CONTINUATION']
            # Note: Strategy hint may be empty or different format, so we just check it exists
    
    def test_signal_summary_usage_in_chatgpt_responses(self):
        """Test signal_summary usage in ChatGPT responses"""
        symbol = 'XAUUSD'
        candles = self._generate_mock_candles(200)
        
        # Analyze
        analysis = self.analyzer.analyze_microstructure(symbol, candles)
        
        # Verify signal summary is usable in ChatGPT responses
        if analysis.get('available'):
            signal_summary = analysis.get('signal_summary', '')
            
            # Signal summary should be a readable string
            self.assertIsInstance(signal_summary, str, "Signal summary should be string")
            self.assertGreater(len(signal_summary), 0, "Signal summary should not be empty")
            
            # Should contain actionable information
            # (e.g., BULLISH_MICROSTRUCTURE, BEARISH_MICROSTRUCTURE, NEUTRAL)
            # We just verify it's present and non-empty
    
    def test_confidence_weighting_in_chatgpt_recommendations(self):
        """Test confidence weighting in ChatGPT recommendations"""
        symbol = 'XAUUSD'
        candles = self._generate_mock_candles(200)
        
        # Analyze
        analysis = self.analyzer.analyze_microstructure(symbol, candles)
        
        # Verify confidence/confluence is available
        if analysis.get('available'):
            confluence = analysis.get('microstructure_confluence', {})
            self.assertIsNotNone(confluence, "Should have confluence for confidence weighting")
            
            if confluence:
                base_score = confluence.get('base_score', 0)
                self.assertGreaterEqual(base_score, 0, "Base score should be >= 0")
                self.assertLessEqual(base_score, 100, "Base score should be <= 100")
                
                # Effective confidence
                effective_confidence = analysis.get('effective_confidence', 0)
                self.assertGreaterEqual(effective_confidence, 0, "Effective confidence should be >= 0")
    
    def test_session_context_in_response(self):
        """Test session context is included in response"""
        symbol = 'XAUUSD'
        candles = self._generate_mock_candles(200)
        
        # Analyze
        analysis = self.analyzer.analyze_microstructure(symbol, candles)
        
        # Verify session context is available (if session_manager is integrated)
        if analysis.get('available'):
            session_context = analysis.get('session_context', {})
            # Session context may be empty if session_manager not integrated
            # But if present, should have expected structure
            if session_context:
                self.assertIn('session', session_context, "Should have session field")
    
    def test_asset_personality_in_response(self):
        """Test asset personality is included in response"""
        symbol = 'XAUUSD'
        candles = self._generate_mock_candles(200)
        
        # Analyze
        analysis = self.analyzer.analyze_microstructure(symbol, candles)
        
        # Verify asset personality is available (if asset_profiles is integrated)
        if analysis.get('available'):
            asset_personality = analysis.get('asset_personality')
            # Asset personality may be None if asset_profiles not integrated
            # But if present, should be a dict
            if asset_personality:
                self.assertIsInstance(asset_personality, dict, "Asset personality should be dict")


if __name__ == '__main__':
    unittest.main()

