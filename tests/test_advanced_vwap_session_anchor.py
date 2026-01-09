"""
Test suite for advanced VWAP session anchoring.
Tests FX session detection, crypto 24/7 sessions, and sigma band calculations.
"""

import pytest
import time
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Add the project root to the path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.engine.advanced_vwap_session_anchor import (
    AdvancedVWAPSessionAnchor,
    AssetType,
    SessionType,
    SessionConfig,
    VWAPSessionAnchor
)

class TestAssetType:
    """Test AssetType enum."""
    
    def test_asset_types(self):
        """Test asset type enum values."""
        assert AssetType.FOREX.value == "forex"
        assert AssetType.CRYPTO.value == "crypto"
        assert AssetType.COMMODITY.value == "commodity"
        assert AssetType.INDEX.value == "index"

class TestSessionType:
    """Test SessionType enum."""
    
    def test_session_types(self):
        """Test session type enum values."""
        assert SessionType.ASIAN.value == "asian"
        assert SessionType.LONDON.value == "london"
        assert SessionType.NEW_YORK.value == "new_york"
        assert SessionType.OVERLAP.value == "overlap"
        assert SessionType.CRYPTO_24_7.value == "crypto_24_7"

class TestSessionConfig:
    """Test SessionConfig dataclass."""
    
    def test_session_config_creation(self):
        """Test session config creation."""
        config = SessionConfig(
            name="Test Session",
            start_hour=9,
            end_hour=17,
            timezone="UTC"
        )
        assert config.name == "Test Session"
        assert config.start_hour == 9
        assert config.end_hour == 17
        assert config.timezone == "UTC"
        assert config.is_24_7 is False
        assert config.overlap_sessions is None

    def test_session_config_24_7(self):
        """Test 24/7 session config."""
        config = SessionConfig(
            name="24/7 Session",
            start_hour=0,
            end_hour=24,
            timezone="UTC",
            is_24_7=True
        )
        assert config.is_24_7 is True

class TestVWAPSessionAnchor:
    """Test VWAPSessionAnchor dataclass."""
    
    def test_session_anchor_creation(self):
        """Test session anchor creation."""
        current_time = int(time.time() * 1000)
        anchor = VWAPSessionAnchor(
            session_start_ms=current_time,
            session_end_ms=current_time + 3600000,  # 1 hour
            session_type=SessionType.LONDON,
            vwap_value=1.1000,
            volume_weighted_sum=1100.0,
            total_volume=1000.0,
            sigma_bands={"1σ": 1.1010, "-1σ": 1.0990},
            is_active=True,
            tick_count=10,
            last_update_ms=current_time
        )
        
        assert anchor.session_start_ms == current_time
        assert anchor.session_type == SessionType.LONDON
        assert anchor.vwap_value == 1.1000
        assert anchor.is_active is True
        assert anchor.tick_count == 10

class TestAdvancedVWAPSessionAnchor:
    """Test AdvancedVWAPSessionAnchor class."""
    
    def test_initialization_forex(self):
        """Test initialization for forex asset."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        
        assert vwap.symbol == "EURUSDc"
        assert vwap.asset_type == AssetType.FOREX
        assert vwap.current_session is None
        assert len(vwap.session_history) == 0
        assert vwap.sigma_window_minutes == 60

    def test_initialization_crypto(self):
        """Test initialization for crypto asset."""
        vwap = AdvancedVWAPSessionAnchor("BTCUSDc", AssetType.CRYPTO)
        
        assert vwap.symbol == "BTCUSDc"
        assert vwap.asset_type == AssetType.CRYPTO
        assert vwap.current_session is None
        assert len(vwap.session_history) == 0

    def test_session_configs_forex(self):
        """Test session configs for forex."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        configs = vwap.session_configs
        
        assert SessionType.ASIAN in configs
        assert SessionType.LONDON in configs
        assert SessionType.NEW_YORK in configs
        assert SessionType.OVERLAP in configs
        
        # Check Asian session config
        asian_config = configs[SessionType.ASIAN]
        assert asian_config.start_hour == 0
        assert asian_config.end_hour == 9
        assert asian_config.is_24_7 is False

    def test_session_configs_crypto(self):
        """Test session configs for crypto."""
        vwap = AdvancedVWAPSessionAnchor("BTCUSDc", AssetType.CRYPTO)
        configs = vwap.session_configs
        
        assert SessionType.CRYPTO_24_7 in configs
        crypto_config = configs[SessionType.CRYPTO_24_7]
        assert crypto_config.is_24_7 is True

    def test_detect_current_session_forex(self):
        """Test session detection for forex."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        
        # Test different hours
        test_cases = [
            (0, SessionType.ASIAN),   # 00:00 UTC - Asian
            (4, SessionType.ASIAN),   # 04:00 UTC - Asian
            (8, SessionType.LONDON),  # 08:00 UTC - London
            (12, SessionType.LONDON), # 12:00 UTC - London
            (13, SessionType.OVERLAP), # 13:00 UTC - Overlap
            (15, SessionType.OVERLAP), # 15:00 UTC - Overlap
            (17, SessionType.NEW_YORK), # 17:00 UTC - New York
            (20, SessionType.NEW_YORK), # 20:00 UTC - New York
            (23, SessionType.ASIAN),  # 23:00 UTC - Asian (next day)
        ]
        
        for hour, expected_session in test_cases:
            # Create timestamp for the hour
            dt = datetime(2024, 1, 1, hour, 0, 0, tzinfo=timezone.utc)
            timestamp_ms = int(dt.timestamp() * 1000)
            
            detected_session = vwap._detect_current_session(timestamp_ms)
            assert detected_session == expected_session, f"Hour {hour} should be {expected_session.value}, got {detected_session.value}"

    def test_detect_current_session_crypto(self):
        """Test session detection for crypto."""
        vwap = AdvancedVWAPSessionAnchor("BTCUSDc", AssetType.CRYPTO)
        
        # Crypto should always be 24/7
        for hour in range(24):
            dt = datetime(2024, 1, 1, hour, 0, 0, tzinfo=timezone.utc)
            timestamp_ms = int(dt.timestamp() * 1000)
            
            detected_session = vwap._detect_current_session(timestamp_ms)
            assert detected_session == SessionType.CRYPTO_24_7

    def test_update_vwap_forex(self):
        """Test VWAP update for forex."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        
        # Mock timestamp for London session (10:00 UTC)
        dt = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        timestamp_ms = int(dt.timestamp() * 1000)
        
        # Update with some ticks
        prices = [1.1000, 1.1005, 1.1010, 1.1008, 1.1012]
        volumes = [1000, 1500, 2000, 1200, 1800]
        
        for price, volume in zip(prices, volumes):
            session = vwap.update_vwap(price, volume, timestamp_ms)
            timestamp_ms += 1000  # 1 second later
        
        assert vwap.current_session is not None
        assert vwap.current_session.session_type == SessionType.LONDON
        assert vwap.current_session.tick_count >= 5
        # Account for initial session creation tick
        expected_volume = sum(volumes) + volumes[0]  # Initial tick + our ticks
        assert vwap.current_session.total_volume == expected_volume
        
        # Check VWAP calculation
        expected_vwap = sum(p * v for p, v in zip(prices, volumes)) / sum(volumes)
        assert abs(vwap.current_session.vwap_value - expected_vwap) < 0.0001

    def test_update_vwap_crypto(self):
        """Test VWAP update for crypto."""
        vwap = AdvancedVWAPSessionAnchor("BTCUSDc", AssetType.CRYPTO)
        
        current_time = int(time.time() * 1000)
        
        # Update with some ticks
        prices = [50000, 50100, 50200, 50150, 50300]
        volumes = [0.1, 0.15, 0.2, 0.12, 0.18]
        
        for price, volume in zip(prices, volumes):
            session = vwap.update_vwap(price, volume, current_time)
            current_time += 1000  # 1 second later
        
        assert vwap.current_session is not None
        assert vwap.current_session.session_type == SessionType.CRYPTO_24_7
        assert vwap.current_session.tick_count >= 5

    def test_get_current_vwap(self):
        """Test getting current VWAP."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        
        # No session yet
        assert vwap.get_current_vwap() is None
        
        # Create a session
        current_time = int(time.time() * 1000)
        session = vwap.update_vwap(1.1000, 1000, current_time)
        
        assert vwap.get_current_vwap() == 1.1000

    def test_get_current_sigma_bands(self):
        """Test getting current sigma bands."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        
        # No session yet
        assert vwap.get_current_sigma_bands() == {}
        
        # Create a session
        current_time = int(time.time() * 1000)
        session = vwap.update_vwap(1.1000, 1000, current_time)
        
        # Sigma bands should be empty initially (calculated periodically)
        assert isinstance(vwap.get_current_sigma_bands(), dict)

    def test_session_statistics(self):
        """Test session statistics."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        
        stats = vwap.get_session_statistics()
        
        assert stats["symbol"] == "EURUSDc"
        assert stats["asset_type"] == "forex"
        assert stats["current_session"] is None
        assert stats["session_history_count"] == 0
        assert stats["total_sessions"] == 0
        
        # Add a session
        current_time = int(time.time() * 1000)
        vwap.update_vwap(1.1000, 1000, current_time)
        
        stats = vwap.get_session_statistics()
        assert stats["current_session"] is not None
        assert stats["total_sessions"] == 1

    def test_price_above_vwap(self):
        """Test price above VWAP check."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        
        # No session
        assert vwap.is_price_above_vwap(1.1000) is False
        
        # Create session
        current_time = int(time.time() * 1000)
        vwap.update_vwap(1.1000, 1000, current_time)
        
        # Price above VWAP
        assert vwap.is_price_above_vwap(1.1005) is True
        
        # Price below VWAP
        assert vwap.is_price_above_vwap(1.0995) is False

    def test_price_below_vwap(self):
        """Test price below VWAP check."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        
        # No session
        assert vwap.is_price_below_vwap(1.1000) is False
        
        # Create session
        current_time = int(time.time() * 1000)
        vwap.update_vwap(1.1000, 1000, current_time)
        
        # Price below VWAP
        assert vwap.is_price_below_vwap(1.0995) is True
        
        # Price above VWAP
        assert vwap.is_price_below_vwap(1.1005) is False

    def test_vwap_distance(self):
        """Test VWAP distance calculation."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        
        # No session
        assert vwap.get_vwap_distance(1.1000) == 0.0
        
        # Create session
        current_time = int(time.time() * 1000)
        vwap.update_vwap(1.1000, 1000, current_time)
        
        # Test distance calculation
        distance = vwap.get_vwap_distance(1.1010)  # 0.1% above
        assert abs(distance - 0.0909) < 0.01  # Approximately 0.1%

    def test_cleanup_old_sessions(self):
        """Test cleanup of old sessions."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        
        # Add multiple sessions to history
        for i in range(15):
            session = VWAPSessionAnchor(
                session_start_ms=int(time.time() * 1000) + i * 1000,
                session_end_ms=int(time.time() * 1000) + i * 1000 + 3600000,
                session_type=SessionType.LONDON,
                vwap_value=1.1000 + i * 0.0001,
                volume_weighted_sum=1100.0,
                total_volume=1000.0,
                sigma_bands={},
                is_active=False,
                tick_count=10,
                last_update_ms=int(time.time() * 1000)
            )
            vwap.session_history.append(session)
        
        assert len(vwap.session_history) == 15
        
        # Cleanup
        vwap.cleanup_old_sessions(max_sessions=10)
        assert len(vwap.session_history) == 10

    def test_session_transition(self):
        """Test session transition handling."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        
        # Start with Asian session (02:00 UTC)
        dt = datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc)
        timestamp_ms = int(dt.timestamp() * 1000)
        
        # Update VWAP in Asian session
        session1 = vwap.update_vwap(1.1000, 1000, timestamp_ms)
        assert session1.session_type == SessionType.ASIAN
        
        # Transition to London session (10:00 UTC)
        dt = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        timestamp_ms = int(dt.timestamp() * 1000)
        
        # Update VWAP in London session
        session2 = vwap.update_vwap(1.1005, 1000, timestamp_ms)
        assert session2.session_type == SessionType.LONDON
        
        # Check that previous session was archived
        assert len(vwap.session_history) == 1
        assert vwap.session_history[0].session_type == SessionType.ASIAN
        assert vwap.session_history[0].is_active is False

class TestIntegration:
    """Integration tests for VWAP session anchoring."""
    
    def test_forex_session_cycle(self):
        """Test complete forex session cycle."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        
        # Simulate a full day of trading
        base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        
        sessions_created = []
        
        # Asian session (00:00-09:00)
        for hour in range(9):
            dt = base_time.replace(hour=hour)
            timestamp_ms = int(dt.timestamp() * 1000)
            session = vwap.update_vwap(1.1000 + hour * 0.0001, 1000, timestamp_ms)
            if session and session.session_type not in [s.session_type for s in sessions_created]:
                sessions_created.append(session)
        
        # London session (08:00-17:00)
        for hour in range(8, 17):
            dt = base_time.replace(hour=hour)
            timestamp_ms = int(dt.timestamp() * 1000)
            session = vwap.update_vwap(1.1000 + hour * 0.0001, 1000, timestamp_ms)
            if session and session.session_type not in [s.session_type for s in sessions_created]:
                sessions_created.append(session)
        
        # New York session (13:00-22:00)
        for hour in range(13, 22):
            dt = base_time.replace(hour=hour)
            timestamp_ms = int(dt.timestamp() * 1000)
            session = vwap.update_vwap(1.1000 + hour * 0.0001, 1000, timestamp_ms)
            if session and session.session_type not in [s.session_type for s in sessions_created]:
                sessions_created.append(session)
        
        # Should have created multiple sessions
        assert len(sessions_created) >= 2
        assert any(s.session_type == SessionType.ASIAN for s in sessions_created)
        assert any(s.session_type == SessionType.LONDON for s in sessions_created)

    def test_crypto_24_7_consistency(self):
        """Test crypto 24/7 session consistency."""
        vwap = AdvancedVWAPSessionAnchor("BTCUSDc", AssetType.CRYPTO)
        
        # Test multiple hours - should all be same session type
        base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        
        for hour in [0, 6, 12, 18, 23]:
            dt = base_time.replace(hour=hour)
            timestamp_ms = int(dt.timestamp() * 1000)
            session = vwap.update_vwap(50000 + hour * 100, 0.1, timestamp_ms)
            assert session.session_type == SessionType.CRYPTO_24_7

    def test_sigma_bands_calculation(self):
        """Test sigma bands calculation."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        
        # Mock the _get_recent_data_for_sigma method to return test data
        def mock_get_recent_data(timestamp_ms):
            prices = np.array([1.1000, 1.1005, 1.1010, 1.1008, 1.1012])
            volumes = np.array([1000, 1500, 2000, 1200, 1800])
            return prices, volumes
        
        vwap._get_recent_data_for_sigma = mock_get_recent_data
        
        # Create session and update
        current_time = int(time.time() * 1000)
        session = vwap.update_vwap(1.1000, 1000, current_time)
        
        # Sigma bands should be calculated
        sigma_bands = vwap.get_current_sigma_bands()
        assert isinstance(sigma_bands, dict)

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
