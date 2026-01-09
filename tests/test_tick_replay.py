"""
Comprehensive Tick Replay Tests
Tests deterministic testing for 4 symbols with MT5 I/O shim
"""

import pytest
import time
import threading
import tempfile
import os
import csv
import struct
import gzip
from unittest.mock import Mock, patch
from typing import Dict, Any, List
from datetime import datetime, timedelta

# Import tick replay components
from infra.tick_replay import (
    TickReplayEngine,
    MT5ReplayShim,
    TickReplayManager,
    TickData,
    ReplayConfig,
    ReplayStats,
    ReplayMode,
    ReplaySpeed,
    ReplayStatus,
    get_replay_manager,
    create_replay,
    get_replay,
    get_mt5_shim
)

class TestTickData:
    """Test tick data structure."""
    
    def test_tick_data_creation(self):
        """Test tick data creation."""
        tick = TickData(
            symbol="BTCUSDc",
            timestamp_ms=1640995200000,
            bid=50000.0,
            ask=50001.0,
            volume=1.5,
            source="replay"
        )
        
        assert tick.symbol == "BTCUSDc"
        assert tick.timestamp_ms == 1640995200000
        assert tick.bid == 50000.0
        assert tick.ask == 50001.0
        assert tick.volume == 1.5
        assert tick.source == "replay"
        assert tick.sequence_id == 0
    
    def test_tick_data_validation(self):
        """Test tick data validation."""
        # Valid tick
        valid_tick = TickData(
            symbol="BTCUSDc",
            timestamp_ms=1640995200000,
            bid=50000.0,
            ask=50001.0,
            volume=1.5
        )
        
        # Invalid tick (bid >= ask)
        invalid_tick = TickData(
            symbol="BTCUSDc",
            timestamp_ms=1640995200000,
            bid=50001.0,
            ask=50000.0,
            volume=1.5
        )
        
        assert valid_tick.bid < valid_tick.ask
        assert invalid_tick.bid >= invalid_tick.ask

class TestReplayConfig:
    """Test replay configuration."""
    
    def test_replay_config_creation(self):
        """Test replay config creation."""
        config = ReplayConfig(
            symbols=["BTCUSDc", "XAUUSDc"],
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now(),
            mode=ReplayMode.DETERMINISTIC,
            speed=ReplaySpeed.REAL_TIME
        )
        
        assert len(config.symbols) == 2
        assert config.mode == ReplayMode.DETERMINISTIC
        assert config.speed == ReplaySpeed.REAL_TIME
        assert config.batch_size == 1000
        assert config.max_ticks_per_second == 1000
    
    def test_replay_config_defaults(self):
        """Test replay config defaults."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        
        assert config.mode == ReplayMode.DETERMINISTIC
        assert config.speed == ReplaySpeed.REAL_TIME
        assert config.data_source == "database"
        assert config.batch_size == 1000
        assert config.enable_compression is True
        assert config.enable_validation is True

class TestTickReplayEngine:
    """Test tick replay engine functionality."""
    
    def test_replay_engine_initialization(self):
        """Test replay engine initialization."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        
        assert engine.config == config
        assert engine.status == ReplayStatus.STOPPED
        assert len(engine.tick_callbacks) == 0
        assert len(engine.progress_callbacks) == 0
        assert len(engine.error_callbacks) == 0
    
    def test_add_callbacks(self):
        """Test adding callbacks."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        
        # Add callbacks
        tick_callback = Mock()
        progress_callback = Mock()
        error_callback = Mock()
        
        engine.add_tick_callback(tick_callback)
        engine.add_progress_callback(progress_callback)
        engine.add_error_callback(error_callback)
        
        assert len(engine.tick_callbacks) == 1
        assert len(engine.progress_callbacks) == 1
        assert len(engine.error_callbacks) == 1
    
    def test_load_data_simulation(self):
        """Test loading data (simulation)."""
        config = ReplayConfig(
            symbols=["BTCUSDc", "XAUUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now(),
            data_source="database"
        )
        engine = TickReplayEngine(config)
        
        # Mock the database loading
        with patch.object(engine, '_load_from_database', return_value=True):
            result = engine.load_data()
            assert result is True
    
    def test_load_data_csv(self):
        """Test loading data from CSV."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test CSV file
            csv_file = os.path.join(temp_dir, "BTCUSDc_ticks.csv")
            with open(csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp_ms', 'bid', 'ask', 'volume'])
                writer.writerow([1640995200000, 50000.0, 50001.0, 1.5])
                writer.writerow([1640995201000, 50001.0, 50002.0, 2.0])
            
            config = ReplayConfig(
                symbols=["BTCUSDc"],
                start_time=datetime.now(),
                end_time=datetime.now(),
                data_source="csv",
                data_path=temp_dir
            )
            engine = TickReplayEngine(config)
            
            result = engine.load_data()
            assert result is True
            assert "BTCUSDc" in engine.tick_data
            assert len(engine.tick_data["BTCUSDc"]) == 2
    
    def test_load_data_binary(self):
        """Test loading data from binary."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test binary file
            binary_file = os.path.join(temp_dir, "BTCUSDc_ticks.bin")
            with open(binary_file, 'wb') as f:
                # Write test tick data (timestamp_ms, bid, ask, volume)
                f.write(struct.pack('Qddd', 1640995200000, 50000.0, 50001.0, 1.5))
                f.write(struct.pack('Qddd', 1640995201000, 50001.0, 50002.0, 2.0))
            
            config = ReplayConfig(
                symbols=["BTCUSDc"],
                start_time=datetime.now(),
                end_time=datetime.now(),
                data_source="binary",
                data_path=temp_dir,
                enable_compression=False
            )
            engine = TickReplayEngine(config)
            
            result = engine.load_data()
            assert result is True
            assert "BTCUSDc" in engine.tick_data
            assert len(engine.tick_data["BTCUSDc"]) == 2
    
    def test_load_data_binary_compressed(self):
        """Test loading data from compressed binary."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test compressed binary file
            binary_file = os.path.join(temp_dir, "BTCUSDc_ticks.bin")
            with gzip.open(binary_file, 'wb') as f:
                # Write test tick data (timestamp_ms, bid, ask, volume)
                f.write(struct.pack('Qddd', 1640995200000, 50000.0, 50001.0, 1.5))
                f.write(struct.pack('Qddd', 1640995201000, 50001.0, 50002.0, 2.0))
            
            config = ReplayConfig(
                symbols=["BTCUSDc"],
                start_time=datetime.now(),
                end_time=datetime.now(),
                data_source="binary",
                data_path=temp_dir,
                enable_compression=True
            )
            engine = TickReplayEngine(config)
            
            result = engine.load_data()
            assert result is True
            assert "BTCUSDc" in engine.tick_data
            assert len(engine.tick_data["BTCUSDc"]) == 2
    
    def test_tick_validation(self):
        """Test tick data validation."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        
        # Valid tick
        valid_tick = TickData(
            symbol="BTCUSDc",
            timestamp_ms=1640995200000,
            bid=50000.0,
            ask=50001.0,
            volume=1.5
        )
        assert engine._validate_tick(valid_tick) is True
        
        # Invalid tick (bid >= ask)
        invalid_tick = TickData(
            symbol="BTCUSDc",
            timestamp_ms=1640995200000,
            bid=50001.0,
            ask=50000.0,
            volume=1.5
        )
        assert engine._validate_tick(invalid_tick) is False
        
        # Invalid tick (negative timestamp)
        invalid_tick2 = TickData(
            symbol="BTCUSDc",
            timestamp_ms=-1,
            bid=50000.0,
            ask=50001.0,
            volume=1.5
        )
        assert engine._validate_tick(invalid_tick2) is False
    
    def test_replay_control(self):
        """Test replay control (start/stop/pause/resume)."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now(),
            speed=ReplaySpeed.REAL_TIME
        )
        engine = TickReplayEngine(config)
        
        # Add some test data with more ticks
        engine.tick_data["BTCUSDc"] = [
            TickData("BTCUSDc", 1640995200000 + i * 1000, 50000.0 + i, 50001.0 + i, 1.5)
            for i in range(10)
        ]
        # Initialize current positions
        engine.current_positions["BTCUSDc"] = 0
        
        # Test start
        result = engine.start_replay()
        assert result is True
        assert engine.status == ReplayStatus.RUNNING
        
        # Test pause
        engine.pause_replay()
        assert engine.status == ReplayStatus.PAUSED
        
        # Test resume
        engine.resume_replay()
        assert engine.status == ReplayStatus.RUNNING
        
        # Test stop
        engine.stop_replay()
        assert engine.status == ReplayStatus.STOPPED
    
    def test_replay_stats(self):
        """Test replay statistics."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        
        # Add some test data
        engine.tick_data["BTCUSDc"] = [
            TickData("BTCUSDc", 1640995200000, 50000.0, 50001.0, 1.5),
            TickData("BTCUSDc", 1640995201000, 50001.0, 50002.0, 2.0)
        ]
        
        # Start replay
        engine.start_replay()
        time.sleep(0.1)  # Let it process some ticks
        engine.stop_replay()
        
        # Check stats
        stats = engine.get_stats()
        assert stats.total_ticks >= 0
        assert stats.processed_ticks >= 0
        assert stats.duration_seconds >= 0
    
    def test_replay_progress(self):
        """Test replay progress calculation."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        
        # Add some test data
        engine.tick_data["BTCUSDc"] = [
            TickData("BTCUSDc", 1640995200000, 50000.0, 50001.0, 1.5),
            TickData("BTCUSDc", 1640995201000, 50001.0, 50002.0, 2.0)
        ]
        
        # Test progress
        progress = engine.get_progress()
        assert 0.0 <= progress <= 1.0
    
    def test_replay_reset(self):
        """Test replay reset."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        
        # Add some test data and process
        engine.tick_data["BTCUSDc"] = [
            TickData("BTCUSDc", 1640995200000, 50000.0, 50001.0, 1.5)
        ]
        engine.current_positions["BTCUSDc"] = 1
        
        # Reset
        engine.reset_replay()
        
        assert engine.current_positions == {}
        assert engine.symbol_sequences == {}
        assert engine.status == ReplayStatus.STOPPED

class TestMT5ReplayShim:
    """Test MT5 replay shim functionality."""
    
    def test_mt5_shim_initialization(self):
        """Test MT5 shim initialization."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        shim = MT5ReplayShim(engine)
        
        assert shim.replay_engine == engine
        assert shim.symbol_info_cache == {}
        assert shim.account_info_cache == {}
        assert shim.positions_cache == []
        assert shim.orders_cache == []
    
    def test_tick_data_handling(self):
        """Test tick data handling in shim."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        shim = MT5ReplayShim(engine)
        
        # Simulate tick data
        tick = TickData(
            symbol="BTCUSDc",
            timestamp_ms=1640995200000,
            bid=50000.0,
            ask=50001.0,
            volume=1.5
        )
        
        shim._on_tick_data(tick)
        
        assert "BTCUSDc" in shim.symbol_info_cache
        assert shim.symbol_info_cache["BTCUSDc"]["bid"] == 50000.0
        assert shim.symbol_info_cache["BTCUSDc"]["ask"] == 50001.0
        assert shim.symbol_info_cache["BTCUSDc"]["spread"] == 1.0
    
    def test_symbol_info_tick(self):
        """Test symbol info tick retrieval."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        shim = MT5ReplayShim(engine)
        
        # Add some data
        shim.symbol_info_cache["BTCUSDc"] = {
            'symbol': 'BTCUSDc',
            'bid': 50000.0,
            'ask': 50001.0,
            'spread': 1.0,
            'volume': 1.5,
            'time': 1640995200000
        }
        
        info = shim.symbol_info_tick("BTCUSDc")
        assert info is not None
        assert info['bid'] == 50000.0
        assert info['ask'] == 50001.0
    
    def test_symbol_info(self):
        """Test symbol info retrieval."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        shim = MT5ReplayShim(engine)
        
        # Add some data
        shim.symbol_info_cache["BTCUSDc"] = {
            'symbol': 'BTCUSDc',
            'bid': 50000.0,
            'ask': 50001.0,
            'spread': 1.0,
            'volume': 1.5,
            'time': 1640995200000
        }
        
        info = shim.symbol_info("BTCUSDc")
        assert info is not None
        assert info['bid'] == 50000.0
        assert info['ask'] == 50001.0
    
    def test_account_info(self):
        """Test account info retrieval."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        shim = MT5ReplayShim(engine)
        
        # Set account info
        shim.account_info_cache = {
            'balance': 10000.0,
            'equity': 10000.0,
            'margin': 0.0,
            'free_margin': 10000.0
        }
        
        info = shim.account_info()
        assert info['balance'] == 10000.0
        assert info['equity'] == 10000.0
    
    def test_positions_get(self):
        """Test positions retrieval."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        shim = MT5ReplayShim(engine)
        
        # Add some positions
        shim.positions_cache = [
            {
                'ticket': 12345,
                'symbol': 'BTCUSDc',
                'type': 0,
                'volume': 0.01,
                'price': 50000.0
            }
        ]
        
        positions = shim.positions_get()
        assert len(positions) == 1
        assert positions[0]['symbol'] == 'BTCUSDc'
        
        # Test with symbol filter
        positions = shim.positions_get("BTCUSDc")
        assert len(positions) == 1
        
        positions = shim.positions_get("XAUUSDc")
        assert len(positions) == 0
    
    def test_orders_get(self):
        """Test orders retrieval."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        shim = MT5ReplayShim(engine)
        
        # Add some orders
        shim.orders_cache = [
            {
                'ticket': 67890,
                'symbol': 'BTCUSDc',
                'type': 0,
                'volume': 0.01,
                'price': 50000.0
            }
        ]
        
        orders = shim.orders_get()
        assert len(orders) == 1
        assert orders[0]['symbol'] == 'BTCUSDc'
        
        # Test with symbol filter
        orders = shim.orders_get("BTCUSDc")
        assert len(orders) == 1
        
        orders = shim.orders_get("XAUUSDc")
        assert len(orders) == 0
    
    def test_order_send(self):
        """Test order sending."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        shim = MT5ReplayShim(engine)
        
        # Send order
        request = {
            'symbol': 'BTCUSDc',
            'type': 0,
            'volume': 0.01,
            'price': 50000.0,
            'comment': 'Test order'
        }
        
        result = shim.order_send(request)
        
        assert result['retcode'] == 10009  # TRADE_RETCODE_DONE
        assert 'deal' in result
        assert 'order' in result
        assert result['volume'] == 0.01
        
        # Check that order was added to cache
        assert len(shim.orders_cache) == 1
        assert shim.orders_cache[0]['symbol'] == 'BTCUSDc'
    
    def test_position_close(self):
        """Test position closing."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        shim = MT5ReplayShim(engine)
        
        # Add a position
        shim.positions_cache = [
            {
                'ticket': 12345,
                'symbol': 'BTCUSDc',
                'type': 0,
                'volume': 0.01,
                'price': 50000.0
            }
        ]
        
        # Close position
        result = shim.position_close(12345)
        
        assert result['retcode'] == 10009  # TRADE_RETCODE_DONE
        assert 'deal' in result
        
        # Check that position was removed from cache
        assert len(shim.positions_cache) == 0

class TestTickReplayManager:
    """Test tick replay manager functionality."""
    
    def test_manager_initialization(self):
        """Test manager initialization."""
        manager = TickReplayManager()
        
        assert manager.replay_engines == {}
        assert manager.mt5_shims == {}
        assert manager.global_callbacks == []
    
    def test_create_replay(self):
        """Test creating replay instance."""
        manager = TickReplayManager()
        
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        
        engine = manager.create_replay("test_replay", config)
        
        assert "test_replay" in manager.replay_engines
        assert "test_replay" in manager.mt5_shims
        assert manager.replay_engines["test_replay"] == engine
    
    def test_get_replay(self):
        """Test getting replay instance."""
        manager = TickReplayManager()
        
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        
        engine = manager.create_replay("test_replay", config)
        retrieved_engine = manager.get_replay("test_replay")
        
        assert retrieved_engine == engine
        
        # Test non-existent replay
        non_existent = manager.get_replay("non_existent")
        assert non_existent is None
    
    def test_get_mt5_shim(self):
        """Test getting MT5 shim."""
        manager = TickReplayManager()
        
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        
        manager.create_replay("test_replay", config)
        shim = manager.get_mt5_shim("test_replay")
        
        assert shim is not None
        assert isinstance(shim, MT5ReplayShim)
        
        # Test non-existent shim
        non_existent = manager.get_mt5_shim("non_existent")
        assert non_existent is None
    
    def test_replay_control(self):
        """Test replay control through manager."""
        manager = TickReplayManager()
        
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        
        engine = manager.create_replay("test_replay", config)
        
        # Add some test data
        engine.tick_data["BTCUSDc"] = [
            TickData("BTCUSDc", 1640995200000, 50000.0, 50001.0, 1.5),
            TickData("BTCUSDc", 1640995201000, 50001.0, 50002.0, 2.0)
        ]
        # Initialize current positions
        engine.current_positions["BTCUSDc"] = 0
        
        # Test start
        result = manager.start_replay("test_replay")
        assert result is True
        
        # Test pause
        manager.pause_replay("test_replay")
        
        # Test resume
        manager.resume_replay("test_replay")
        
        # Test stop
        manager.stop_replay("test_replay")
    
    def test_get_all_stats(self):
        """Test getting all statistics."""
        manager = TickReplayManager()
        
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        
        manager.create_replay("test_replay", config)
        stats = manager.get_all_stats()
        
        assert "test_replay" in stats
        assert isinstance(stats["test_replay"], ReplayStats)
    
    def test_cleanup_replay(self):
        """Test cleanup replay."""
        manager = TickReplayManager()
        
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        
        manager.create_replay("test_replay", config)
        assert "test_replay" in manager.replay_engines
        
        manager.cleanup_replay("test_replay")
        assert "test_replay" not in manager.replay_engines
        assert "test_replay" not in manager.mt5_shims

class TestGlobalFunctions:
    """Test global tick replay functions."""
    
    def test_get_replay_manager(self):
        """Test getting global replay manager."""
        manager = get_replay_manager()
        assert manager is not None
        assert isinstance(manager, TickReplayManager)
    
    def test_create_replay_global(self):
        """Test creating replay through global function."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        
        engine = create_replay("global_test", config)
        assert engine is not None
        assert isinstance(engine, TickReplayEngine)
    
    def test_get_replay_global(self):
        """Test getting replay through global function."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        
        create_replay("global_test2", config)
        engine = get_replay("global_test2")
        
        assert engine is not None
        assert isinstance(engine, TickReplayEngine)
    
    def test_get_mt5_shim_global(self):
        """Test getting MT5 shim through global function."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        
        create_replay("global_test3", config)
        shim = get_mt5_shim("global_test3")
        
        assert shim is not None
        assert isinstance(shim, MT5ReplayShim)

class TestReplayModes:
    """Test different replay modes."""
    
    def test_deterministic_mode(self):
        """Test deterministic replay mode."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now(),
            mode=ReplayMode.DETERMINISTIC
        )
        engine = TickReplayEngine(config)
        
        assert engine.config.mode == ReplayMode.DETERMINISTIC
    
    def test_historical_mode(self):
        """Test historical replay mode."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now(),
            mode=ReplayMode.HISTORICAL
        )
        engine = TickReplayEngine(config)
        
        assert engine.config.mode == ReplayMode.HISTORICAL
    
    def test_live_simulation_mode(self):
        """Test live simulation replay mode."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now(),
            mode=ReplayMode.LIVE_SIMULATION
        )
        engine = TickReplayEngine(config)
        
        assert engine.config.mode == ReplayMode.LIVE_SIMULATION
    
    def test_stress_test_mode(self):
        """Test stress test replay mode."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now(),
            mode=ReplayMode.STRESS_TEST
        )
        engine = TickReplayEngine(config)
        
        assert engine.config.mode == ReplayMode.STRESS_TEST

class TestReplaySpeeds:
    """Test different replay speeds."""
    
    def test_real_time_speed(self):
        """Test real-time replay speed."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now(),
            speed=ReplaySpeed.REAL_TIME
        )
        engine = TickReplayEngine(config)
        
        assert engine.config.speed == ReplaySpeed.REAL_TIME
    
    def test_fast_speeds(self):
        """Test fast replay speeds."""
        speeds = [ReplaySpeed.FAST_2X, ReplaySpeed.FAST_5X, ReplaySpeed.FAST_10X]
        
        for speed in speeds:
            config = ReplayConfig(
                symbols=["BTCUSDc"],
                start_time=datetime.now(),
                end_time=datetime.now(),
                speed=speed
            )
            engine = TickReplayEngine(config)
            assert engine.config.speed == speed
    
    def test_instant_speed(self):
        """Test instant replay speed."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now(),
            speed=ReplaySpeed.INSTANT
        )
        engine = TickReplayEngine(config)
        
        assert engine.config.speed == ReplaySpeed.INSTANT

class TestConcurrency:
    """Test concurrent access to tick replay."""
    
    def test_concurrent_replay_creation(self):
        """Test concurrent replay creation."""
        manager = TickReplayManager()
        
        def create_replay_thread(name):
            config = ReplayConfig(
                symbols=["BTCUSDc"],
                start_time=datetime.now(),
                end_time=datetime.now()
            )
            return manager.create_replay(name, config)
        
        # Create multiple replays concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_replay_thread, args=(f"replay_{i}",))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Check that all replays were created
        assert len(manager.replay_engines) == 5
        for i in range(5):
            assert f"replay_{i}" in manager.replay_engines
    
    def test_concurrent_tick_processing(self):
        """Test concurrent tick processing."""
        config = ReplayConfig(
            symbols=["BTCUSDc"],
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        engine = TickReplayEngine(config)
        
        # Add test data
        engine.tick_data["BTCUSDc"] = [
            TickData("BTCUSDc", 1640995200000 + i * 1000, 50000.0 + i, 50001.0 + i, 1.5)
            for i in range(100)
        ]
        # Initialize current positions
        engine.current_positions["BTCUSDc"] = 0
        
        # Add tick callback
        processed_ticks = []
        def tick_callback(tick):
            processed_ticks.append(tick)
        
        engine.add_tick_callback(tick_callback)
        
        # Start replay
        engine.start_replay()
        time.sleep(0.1)  # Let it process some ticks
        engine.stop_replay()
        
        # Check that some ticks were processed
        assert len(processed_ticks) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
