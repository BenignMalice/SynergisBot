"""
Comprehensive tests for Data Retention Manager
Tests data retention policies, compression, archival, and cleanup
"""

import pytest
import asyncio
import tempfile
import os
import json
import gzip
import time
from pathlib import Path
from unittest.mock import Mock, patch
import sqlite3

from app.database.data_retention_manager import (
    DataRetentionManager, RetentionPolicy, RetentionTier, 
    CompressionLevel, CompressionStats, DEFAULT_RETENTION_POLICIES,
    create_default_retention_manager
)

class TestRetentionPolicy:
    """Test retention policy configuration."""
    
    def test_retention_policy_creation(self):
        """Test retention policy creation with default values."""
        policy = RetentionPolicy("BTCUSDc", "M1")
        
        assert policy.symbol == "BTCUSDc"
        assert policy.timeframe == "M1"
        assert policy.hot_days == 7
        assert policy.warm_days == 30
        assert policy.cold_days == 365
        assert policy.archive_days == 1095
        assert policy.hot_compression == CompressionLevel.NONE
        assert policy.warm_compression == CompressionLevel.LIGHT
        assert policy.cold_compression == CompressionLevel.HEAVY
        assert policy.archive_compression == CompressionLevel.MAXIMUM
    
    def test_retention_policy_custom_values(self):
        """Test retention policy with custom values."""
        policy = RetentionPolicy(
            "XAUUSDc", "H1",
            hot_days=14,
            warm_days=60,
            cold_days=730,
            archive_days=2190,
            warm_sampling_ratio=0.3,
            cold_sampling_ratio=0.05,
            archive_sampling_ratio=0.01
        )
        
        assert policy.symbol == "XAUUSDc"
        assert policy.timeframe == "H1"
        assert policy.hot_days == 14
        assert policy.warm_days == 60
        assert policy.cold_days == 730
        assert policy.archive_days == 2190
        assert policy.warm_sampling_ratio == 0.3
        assert policy.cold_sampling_ratio == 0.05
        assert policy.archive_sampling_ratio == 0.01

class TestRetentionTier:
    """Test retention tier determination."""
    
    def test_retention_tier_hot(self):
        """Test hot tier determination for recent data."""
        manager = DataRetentionManager(":memory:")
        policy = RetentionPolicy("BTCUSDc", "M1", hot_days=7)
        
        # Recent timestamp (1 day ago)
        recent_timestamp = int((time.time() - 24 * 60 * 60) * 1000)
        tier = manager.get_retention_tier(recent_timestamp, policy)
        
        assert tier == RetentionTier.HOT
    
    def test_retention_tier_warm(self):
        """Test warm tier determination for medium age data."""
        manager = DataRetentionManager(":memory:")
        policy = RetentionPolicy("BTCUSDc", "M1", hot_days=7, warm_days=30)
        
        # Medium age timestamp (14 days ago)
        medium_timestamp = int((time.time() - 14 * 24 * 60 * 60) * 1000)
        tier = manager.get_retention_tier(medium_timestamp, policy)
        
        assert tier == RetentionTier.WARM
    
    def test_retention_tier_cold(self):
        """Test cold tier determination for old data."""
        manager = DataRetentionManager(":memory:")
        policy = RetentionPolicy("BTCUSDc", "M1", hot_days=7, warm_days=30, cold_days=365)
        
        # Old timestamp (100 days ago)
        old_timestamp = int((time.time() - 100 * 24 * 60 * 60) * 1000)
        tier = manager.get_retention_tier(old_timestamp, policy)
        
        assert tier == RetentionTier.COLD
    
    def test_retention_tier_archive(self):
        """Test archive tier determination for very old data."""
        manager = DataRetentionManager(":memory:")
        policy = RetentionPolicy("BTCUSDc", "M1", hot_days=7, warm_days=30, cold_days=365)
        
        # Very old timestamp (500 days ago)
        very_old_timestamp = int((time.time() - 500 * 24 * 60 * 60) * 1000)
        tier = manager.get_retention_tier(very_old_timestamp, policy)
        
        assert tier == RetentionTier.ARCHIVE

class TestCompression:
    """Test data compression functionality."""
    
    @pytest.mark.asyncio
    async def test_compression_none(self):
        """Test no compression."""
        manager = DataRetentionManager(":memory:")
        test_data = b"test data for compression"
        
        compressed_data, stats = await manager.compress_data(test_data, CompressionLevel.NONE)
        
        assert compressed_data == test_data
        assert stats.original_size == len(test_data)
        assert stats.compressed_size == len(test_data)
        assert stats.compression_ratio == 1.0
        assert stats.compression_time_ms >= 0
    
    @pytest.mark.asyncio
    async def test_compression_light(self):
        """Test light compression."""
        manager = DataRetentionManager(":memory:")
        test_data = b"test data for compression" * 100  # Make it larger for better compression
        
        compressed_data, stats = await manager.compress_data(test_data, CompressionLevel.LIGHT)
        
        assert len(compressed_data) < len(test_data)
        assert stats.original_size == len(test_data)
        assert stats.compressed_size == len(compressed_data)
        assert stats.compression_ratio < 1.0
        assert stats.compression_time_ms >= 0
    
    @pytest.mark.asyncio
    async def test_compression_heavy(self):
        """Test heavy compression."""
        manager = DataRetentionManager(":memory:")
        test_data = b"test data for compression" * 1000  # Make it much larger
        
        compressed_data, stats = await manager.compress_data(test_data, CompressionLevel.HEAVY)
        
        assert len(compressed_data) < len(test_data)
        assert stats.compression_ratio < 0.5  # Should achieve good compression
        assert stats.compression_time_ms >= 0
    
    @pytest.mark.asyncio
    async def test_compression_maximum(self):
        """Test maximum compression."""
        manager = DataRetentionManager(":memory:")
        test_data = b"test data for compression" * 1000
        
        compressed_data, stats = await manager.compress_data(test_data, CompressionLevel.MAXIMUM)
        
        assert len(compressed_data) < len(test_data)
        assert stats.compression_ratio < 0.3  # Should achieve excellent compression
        assert stats.compression_time_ms >= 0

class TestDataSampling:
    """Test data sampling functionality."""
    
    @pytest.mark.asyncio
    async def test_sampling_no_reduction(self):
        """Test sampling with no reduction (ratio >= 1.0)."""
        manager = DataRetentionManager(":memory:")
        test_data = [{"id": i, "value": f"data_{i}"} for i in range(100)]
        
        sampled = await manager.sample_data(test_data, 1.0)
        
        assert len(sampled) == len(test_data)
        assert sampled == test_data
    
    @pytest.mark.asyncio
    async def test_sampling_half_reduction(self):
        """Test sampling with 50% reduction."""
        manager = DataRetentionManager(":memory:")
        test_data = [{"id": i, "value": f"data_{i}"} for i in range(100)]
        
        sampled = await manager.sample_data(test_data, 0.5)
        
        assert len(sampled) == 50
        assert len(sampled) < len(test_data)
    
    @pytest.mark.asyncio
    async def test_sampling_heavy_reduction(self):
        """Test sampling with heavy reduction (10%)."""
        manager = DataRetentionManager(":memory:")
        test_data = [{"id": i, "value": f"data_{i}"} for i in range(1000)]
        
        sampled = await manager.sample_data(test_data, 0.1)
        
        assert len(sampled) == 100
        assert len(sampled) < len(test_data)
    
    @pytest.mark.asyncio
    async def test_sampling_minimum_one(self):
        """Test sampling ensures at least one item is kept."""
        manager = DataRetentionManager(":memory:")
        test_data = [{"id": i, "value": f"data_{i}"} for i in range(5)]
        
        sampled = await manager.sample_data(test_data, 0.01)  # Very small ratio
        
        assert len(sampled) >= 1
        assert len(sampled) <= len(test_data)

class TestDataRetentionManager:
    """Test the main DataRetentionManager class."""
    
    def test_manager_initialization(self):
        """Test manager initialization."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            db_path = tmp_db.name
        
        try:
            manager = DataRetentionManager(db_path, "test_archives")
            
            assert manager.db_path == db_path
            assert manager.archive_path == Path("test_archives")
            assert len(manager.policies) == 0
            assert not manager.running
            assert manager.stats["compression_operations"] == 0
            
        finally:
            os.unlink(db_path)
            if os.path.exists("test_archives"):
                import shutil
                shutil.rmtree("test_archives")
    
    def test_add_retention_policy(self):
        """Test adding retention policies."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            db_path = tmp_db.name
        
        try:
            manager = DataRetentionManager(db_path)
            
            policy = RetentionPolicy("BTCUSDc", "M1", hot_days=7)
            manager.add_retention_policy(policy)
            
            assert len(manager.policies) == 1
            assert "BTCUSDc_M1" in manager.policies
            assert manager.policies["BTCUSDc_M1"] == policy
            
        finally:
            os.unlink(db_path)
    
    def test_get_retention_stats(self):
        """Test getting retention statistics."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            db_path = tmp_db.name
        
        try:
            manager = DataRetentionManager(db_path)
            
            # Add a policy
            policy = RetentionPolicy("BTCUSDc", "M1")
            manager.add_retention_policy(policy)
            
            stats = manager.get_retention_stats()
            
            assert stats["policies_count"] == 1
            assert not stats["running"]
            assert "stats" in stats
            assert stats["stats"]["compression_operations"] == 0
            
        finally:
            os.unlink(db_path)
    
    def test_get_database_size(self):
        """Test getting database size information."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            db_path = tmp_db.name
        
        try:
            # Create a test database with some data
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tick_data (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    timeframe TEXT,
                    timestamp_utc INTEGER,
                    data_json TEXT
                )
            """)
            
            # Insert some test data
            for i in range(100):
                cursor.execute("""
                    INSERT INTO tick_data (symbol, timeframe, timestamp_utc, data_json)
                    VALUES (?, ?, ?, ?)
                """, ("BTCUSDc", "M1", int(time.time() * 1000) - i * 60000, '{"test": "data"}'))
            
            conn.commit()
            conn.close()
            
            manager = DataRetentionManager(db_path)
            size_info = manager.get_database_size()
            
            assert "total_size_bytes" in size_info
            assert "total_size_mb" in size_info
            assert "tables" in size_info
            assert size_info["total_size_bytes"] > 0
            assert size_info["total_size_mb"] > 0
            
        finally:
            os.unlink(db_path)

class TestArchiveOperations:
    """Test archive operations."""
    
    @pytest.mark.asyncio
    async def test_archive_data(self):
        """Test archiving data to compressed files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "archives"
            manager = DataRetentionManager(":memory:", str(archive_path))
            
            test_data = [
                {"timestamp": 1234567890, "price": 50000.0, "volume": 1.5},
                {"timestamp": 1234567891, "price": 50001.0, "volume": 2.0}
            ]
            
            archive_file = await manager.archive_data(
                "BTCUSDc", "M1", test_data, CompressionLevel.MEDIUM
            )
            
            assert os.path.exists(archive_file)
            assert archive_file.endswith(".json.gz")
            
            # Verify archive content
            with gzip.open(archive_file, 'rt', encoding='utf-8') as f:
                archived_data = json.load(f)
            
            assert len(archived_data) == len(test_data)
            assert archived_data[0]["price"] == 50000.0
    
    @pytest.mark.asyncio
    async def test_cleanup_old_archives(self):
        """Test cleanup of old archive files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "archives"
            manager = DataRetentionManager(":memory:", str(archive_path))
            
            # Create some test archive files
            old_file = archive_path / "old_archive.json.gz"
            old_file.parent.mkdir(parents=True, exist_ok=True)
            old_file.write_bytes(b"test data")
            
            # Set file modification time to 400 days ago
            old_time = time.time() - (400 * 24 * 60 * 60)
            os.utime(old_file, (old_time, old_time))
            
            # Create a recent file
            recent_file = archive_path / "recent_archive.json.gz"
            recent_file.write_bytes(b"test data")
            
            # Run cleanup (max age 365 days)
            await manager.cleanup_old_archives(max_age_days=365)
            
            # Old file should be deleted, recent file should remain
            assert not old_file.exists()
            assert recent_file.exists()

class TestDefaultPolicies:
    """Test default retention policies."""
    
    def test_default_policies_structure(self):
        """Test structure of default retention policies."""
        assert "BTCUSDc" in DEFAULT_RETENTION_POLICIES
        assert "XAUUSDc" in DEFAULT_RETENTION_POLICIES
        assert "EURUSDc" in DEFAULT_RETENTION_POLICIES
        
        # Test BTCUSDc policies
        btc_policies = DEFAULT_RETENTION_POLICIES["BTCUSDc"]
        assert "M1" in btc_policies
        assert "M5" in btc_policies
        assert "M15" in btc_policies
        assert "H1" in btc_policies
        assert "H4" in btc_policies
        
        # Test M1 policy values
        m1_policy = btc_policies["M1"]
        assert m1_policy.symbol == "BTCUSDc"
        assert m1_policy.timeframe == "M1"
        assert m1_policy.hot_days == 7
        assert m1_policy.warm_days == 30
        assert m1_policy.cold_days == 365
    
    def test_create_default_retention_manager(self):
        """Test creating retention manager with default policies."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            db_path = tmp_db.name
        
        try:
            manager = create_default_retention_manager(db_path)
            
            # Should have policies for all symbols and timeframes
            expected_policies = 3 * 5  # 3 symbols * 5 timeframes
            assert len(manager.policies) == expected_policies
            
            # Check specific policies exist
            assert "BTCUSDc_M1" in manager.policies
            assert "XAUUSDc_H1" in manager.policies
            assert "EURUSDc_H4" in manager.policies
            
        finally:
            os.unlink(db_path)

class TestIntegration:
    """Integration tests for data retention."""
    
    @pytest.mark.asyncio
    async def test_full_retention_cycle(self):
        """Test a complete retention cycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            archive_path = os.path.join(temp_dir, "archives")
            
            # Create test database with old data
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tick_data (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    timeframe TEXT,
                    timestamp_utc INTEGER,
                    data_json TEXT
                )
            """)
            
            # Insert old data (100 days ago)
            old_timestamp = int((time.time() - 100 * 24 * 60 * 60) * 1000)
            for i in range(50):
                cursor.execute("""
                    INSERT INTO tick_data (symbol, timeframe, timestamp_utc, data_json)
                    VALUES (?, ?, ?, ?)
                """, ("BTCUSDc", "M1", old_timestamp + i * 60000, '{"price": 50000, "volume": 1.0}'))
            
            conn.commit()
            conn.close()
            
            # Create retention manager
            manager = DataRetentionManager(db_path, archive_path)
            
            # Add retention policy
            policy = RetentionPolicy("BTCUSDc", "M1", hot_days=7, warm_days=30, cold_days=90)
            manager.add_retention_policy(policy)
            
            # Run retention cycle
            await manager.run_retention_cycle()
            
            # Verify data was processed
            stats = manager.get_retention_stats()
            assert stats["stats"]["archival_operations"] > 0
            assert stats["stats"]["deletion_operations"] > 0
            
            # Verify archive files were created
            archive_files = list(Path(archive_path).rglob("*.json.gz"))
            assert len(archive_files) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
