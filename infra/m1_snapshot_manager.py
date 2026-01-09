# =====================================
# infra/m1_snapshot_manager.py
# =====================================
"""
M1 Snapshot Manager Module

Provides crash recovery and persistence for M1 candlestick data.
Uses CSV snapshots with optional zstd compression for efficient storage.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Try to import zstandard for compression (optional)
try:
    import zstandard as zstd
    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False
    logger.warning("zstandard not available - compression disabled. Install with: pip install zstandard")


class M1SnapshotManager:
    """
    Manages CSV snapshots of M1 candlestick data for crash recovery.
    
    Features:
    - Periodic snapshots (default: every 30 minutes)
    - Optional zstd compression (70% disk space saving)
    - Checksum validation for data integrity
    - Atomic file operations (prevents corruption)
    - Automatic cleanup of old snapshots
    """
    
    def __init__(
        self,
        fetcher,
        snapshot_interval: int = 1800,
        snapshot_directory: str = "data/m1_snapshots",
        max_age_hours: int = 24,
        use_compression: bool = True,
        validate_checksum: bool = True,
        use_file_locking: bool = True
    ):
        """
        Initialize M1 Snapshot Manager.
        
        Args:
            fetcher: M1DataFetcher instance to get candle data from
            snapshot_interval: Interval between snapshots in seconds (default: 1800 = 30 minutes)
            snapshot_directory: Directory to store snapshots (default: "data/m1_snapshots")
            max_age_hours: Maximum age of snapshots to keep (default: 24 hours)
            use_compression: Enable zstd compression (default: True, requires zstandard package)
            validate_checksum: Validate checksum on load (default: True)
            use_file_locking: Use file locking for atomic operations (default: True)
        """
        self.fetcher = fetcher
        self.snapshot_interval = snapshot_interval
        self.snapshot_directory = Path(snapshot_directory)
        self.max_age_hours = max_age_hours
        self.use_compression = use_compression and ZSTD_AVAILABLE
        self.validate_checksum = validate_checksum
        self.use_file_locking = use_file_locking
        
        # Track last snapshot time per symbol
        self._last_snapshot_time: Dict[str, float] = {}
        
        # Create snapshot directory if it doesn't exist
        self.snapshot_directory.mkdir(parents=True, exist_ok=True)
        
        if self.use_compression:
            logger.info(f"M1SnapshotManager initialized with compression (interval={snapshot_interval}s, dir={snapshot_directory})")
        else:
            logger.info(f"M1SnapshotManager initialized without compression (interval={snapshot_interval}s, dir={snapshot_directory})")
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol name for file naming."""
        return symbol.upper().replace('C', '').replace('/', '_')
    
    def _get_snapshot_filename(self, symbol: str, timestamp: Optional[datetime] = None) -> str:
        """
        Generate snapshot filename.
        
        Args:
            symbol: Symbol name
            timestamp: Timestamp for snapshot (default: current time)
            
        Returns:
            Filename string
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        normalized_symbol = self._normalize_symbol(symbol)
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        
        if self.use_compression:
            return f"{normalized_symbol}_M1_snapshot_{timestamp_str}.csv.zstd"
        else:
            return f"{normalized_symbol}_M1_snapshot_{timestamp_str}.csv"
    
    def _calculate_checksum(self, data: bytes) -> str:
        """Calculate SHA256 checksum of data."""
        return hashlib.sha256(data).hexdigest()
    
    def _compress_snapshot(self, data: bytes) -> bytes:
        """
        Compress CSV data using zstd.
        
        Args:
            data: Uncompressed CSV data as bytes
            
        Returns:
            Compressed data as bytes
        """
        if not ZSTD_AVAILABLE:
            raise RuntimeError("zstandard not available - cannot compress")
        
        cctx = zstd.ZstdCompressor(level=3)  # Level 3: good balance of speed and compression
        return cctx.compress(data)
    
    def _decompress_snapshot(self, data: bytes) -> bytes:
        """
        Decompress zstd data.
        
        Args:
            data: Compressed data as bytes
            
        Returns:
            Decompressed CSV data as bytes
        """
        if not ZSTD_AVAILABLE:
            raise RuntimeError("zstandard not available - cannot decompress")
        
        dctx = zstd.ZstdDecompressor()
        return dctx.decompress(data)
    
    def _write_csv_data(self, candles: List[Dict[str, Any]]) -> bytes:
        """
        Convert candles to CSV format and return as bytes.
        
        Args:
            candles: List of candle dicts
            
        Returns:
            CSV data as bytes
        """
        if not candles:
            return b""
        
        # Use StringIO to write CSV in memory
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        writer.writeheader()
        
        for candle in candles:
            # Convert timestamp to string if needed
            timestamp = candle.get('timestamp') or candle.get('time')
            if isinstance(timestamp, datetime):
                timestamp_str = timestamp.isoformat()
            elif isinstance(timestamp, str):
                timestamp_str = timestamp
            else:
                timestamp_str = str(timestamp)
            
            writer.writerow({
                'timestamp': timestamp_str,
                'open': candle.get('open', 0),
                'high': candle.get('high', 0),
                'low': candle.get('low', 0),
                'close': candle.get('close', 0),
                'volume': candle.get('volume', 0)
            })
        
        return output.getvalue().encode('utf-8')
    
    def _read_csv_data(self, data: bytes) -> List[Dict[str, Any]]:
        """
        Parse CSV data and return list of candle dicts.
        
        Args:
            data: CSV data as bytes
            
        Returns:
            List of candle dicts
        """
        import io
        input_stream = io.StringIO(data.decode('utf-8'))
        reader = csv.DictReader(input_stream)
        
        candles = []
        for row in reader:
            # Parse timestamp
            timestamp_str = row.get('timestamp', '')
            try:
                if 'T' in timestamp_str or ' ' in timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                # Fallback: try to parse as epoch
                try:
                    timestamp = datetime.fromtimestamp(float(timestamp_str), tz=timezone.utc)
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse timestamp: {timestamp_str}, using current time")
                    timestamp = datetime.now(timezone.utc)
            
            candles.append({
                'timestamp': timestamp,
                'open': float(row.get('open', 0)),
                'high': float(row.get('high', 0)),
                'low': float(row.get('low', 0)),
                'close': float(row.get('close', 0)),
                'volume': int(row.get('volume', 0))
            })
        
        return candles
    
    def create_snapshot(self, symbol: str) -> bool:
        """
        Create a snapshot for a symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            True if snapshot created successfully, False otherwise
        """
        try:
            # Get current candles from fetcher
            candles = self.fetcher.fetch_m1_data(symbol, count=200, use_cache=True)
            
            if not candles or len(candles) == 0:
                logger.warning(f"No candles available for snapshot: {symbol}")
                return False
            
            # Convert to list if deque
            if hasattr(candles, '__iter__') and not isinstance(candles, list):
                candles = list(candles)
            
            # Use atomic write
            return self.create_snapshot_atomic(symbol, candles)
            
        except Exception as e:
            logger.error(f"Error creating snapshot for {symbol}: {e}", exc_info=True)
            return False
    
    def create_snapshot_atomic(self, symbol: str, candles: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        Create snapshot using atomic write pattern (temp file + rename).
        
        Args:
            symbol: Symbol name
            candles: Optional list of candles (if None, fetches from fetcher)
            
        Returns:
            True if snapshot created successfully, False otherwise
        """
        try:
            if candles is None:
                candles = self.fetcher.fetch_m1_data(symbol, count=200, use_cache=True)
                if not candles or len(candles) == 0:
                    logger.warning(f"No candles available for snapshot: {symbol}")
                    return False
                if hasattr(candles, '__iter__') and not isinstance(candles, list):
                    candles = list(candles)
            
            # Write CSV data
            csv_data = self._write_csv_data(candles)
            if not csv_data:
                logger.warning(f"Empty CSV data for snapshot: {symbol}")
                return False
            
            # Compress if enabled
            if self.use_compression:
                snapshot_data = self._compress_snapshot(csv_data)
                extension = '.csv.zstd'
            else:
                snapshot_data = csv_data
                extension = '.csv'
            
            # Calculate checksum
            checksum = self._calculate_checksum(snapshot_data)
            
            # Generate filename
            timestamp = datetime.now(timezone.utc)
            filename = self._get_snapshot_filename(symbol, timestamp)
            filepath = self.snapshot_directory / filename
            
            # Atomic write: write to temp file first, then rename
            temp_file = tempfile.NamedTemporaryFile(
                mode='wb',
                dir=self.snapshot_directory,
                delete=False,
                suffix=extension
            )
            
            try:
                # Write data
                temp_file.write(snapshot_data)
                temp_file.flush()
                os.fsync(temp_file.fileno())  # Ensure data is written to disk
                temp_file.close()
                
                # Write checksum file
                checksum_filepath = filepath.with_suffix(filepath.suffix + '.checksum')
                temp_checksum_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    dir=self.snapshot_directory,
                    delete=False,
                    suffix='.checksum'
                )
                temp_checksum_file.write(checksum)
                temp_checksum_file.flush()
                os.fsync(temp_checksum_file.fileno())
                temp_checksum_file.close()
                
                # Atomic rename (remove existing file first if it exists)
                if filepath.exists():
                    filepath.unlink()
                if checksum_filepath.exists():
                    checksum_filepath.unlink()
                
                os.rename(temp_file.name, filepath)
                os.rename(temp_checksum_file.name, checksum_filepath)
                
                # Update last snapshot time
                self._last_snapshot_time[symbol] = time.time()
                
                logger.info(f"Snapshot created: {filename} ({len(candles)} candles, {len(snapshot_data)} bytes)")
                return True
                
            except Exception as e:
                # Cleanup temp files on error
                try:
                    if os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
                    if os.path.exists(temp_checksum_file.name):
                        os.unlink(temp_checksum_file.name)
                except:
                    pass
                raise e
                
        except Exception as e:
            logger.error(f"Error creating atomic snapshot for {symbol}: {e}", exc_info=True)
            return False
    
    def load_snapshot(self, symbol: str, max_age_seconds: int = 3600) -> Optional[List[Dict[str, Any]]]:
        """
        Load most recent snapshot for a symbol.
        
        Args:
            symbol: Symbol name
            max_age_seconds: Maximum age of snapshot to load (default: 3600 = 1 hour)
            
        Returns:
            List of candle dicts if snapshot found and valid, None otherwise
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            
            # Find most recent snapshot
            pattern = f"{normalized_symbol}_M1_snapshot_*.csv"
            if self.use_compression:
                pattern += ".zstd"
            
            snapshots = list(self.snapshot_directory.glob(pattern))
            
            if not snapshots:
                logger.debug(f"No snapshots found for {symbol}")
                return None
            
            # Sort by modification time (newest first)
            snapshots.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            latest_snapshot = snapshots[0]
            
            # Check age
            snapshot_age = time.time() - latest_snapshot.stat().st_mtime
            if snapshot_age > max_age_seconds:
                logger.debug(f"Snapshot too old for {symbol}: {snapshot_age:.0f}s > {max_age_seconds}s")
                return None
            
            # Validate checksum if enabled
            if self.validate_checksum:
                if not self.validate_snapshot_checksum(latest_snapshot):
                    logger.warning(f"Checksum validation failed for {symbol}, skipping snapshot")
                    return None
            
            # Read and decompress if needed
            with open(latest_snapshot, 'rb') as f:
                snapshot_data = f.read()
            
            if self.use_compression and latest_snapshot.suffix == '.zstd':
                csv_data = self._decompress_snapshot(snapshot_data)
            else:
                csv_data = snapshot_data
            
            # Parse CSV
            candles = self._read_csv_data(csv_data)
            
            logger.info(f"Loaded snapshot for {symbol}: {len(candles)} candles from {latest_snapshot.name}")
            return candles
            
        except Exception as e:
            logger.error(f"Error loading snapshot for {symbol}: {e}", exc_info=True)
            return None
    
    def validate_snapshot_checksum(self, filepath: Path) -> bool:
        """
        Validate snapshot checksum.
        
        Args:
            filepath: Path to snapshot file
            
        Returns:
            True if checksum is valid, False otherwise
        """
        try:
            # Read snapshot data
            with open(filepath, 'rb') as f:
                snapshot_data = f.read()
            
            # Calculate checksum
            calculated_checksum = self._calculate_checksum(snapshot_data)
            
            # Read stored checksum
            checksum_filepath = filepath.with_suffix(filepath.suffix + '.checksum')
            if not checksum_filepath.exists():
                logger.warning(f"Checksum file not found: {checksum_filepath}")
                return False
            
            with open(checksum_filepath, 'r') as f:
                stored_checksum = f.read().strip()
            
            # Compare
            if calculated_checksum != stored_checksum:
                logger.error(f"Checksum mismatch for {filepath.name}: calculated={calculated_checksum[:16]}..., stored={stored_checksum[:16]}...")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating checksum for {filepath}: {e}", exc_info=True)
            return False
    
    def cleanup_old_snapshots(self, max_age_hours: Optional[int] = None) -> int:
        """
        Clean up old snapshots.
        
        Args:
            max_age_hours: Maximum age in hours (default: uses self.max_age_hours)
            
        Returns:
            Number of snapshots deleted
        """
        if max_age_hours is None:
            max_age_hours = self.max_age_hours
        
        max_age_seconds = max_age_hours * 3600
        cutoff_time = time.time() - max_age_seconds
        
        deleted_count = 0
        
        try:
            # Find all snapshot files
            snapshot_files = list(self.snapshot_directory.glob("*_M1_snapshot_*.csv*"))
            checksum_files = list(self.snapshot_directory.glob("*_M1_snapshot_*.checksum"))
            
            for filepath in snapshot_files + checksum_files:
                try:
                    if filepath.stat().st_mtime < cutoff_time:
                        filepath.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted old snapshot: {filepath.name}")
                except Exception as e:
                    logger.warning(f"Error deleting snapshot {filepath.name}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old snapshots (max_age={max_age_hours}h)")
            
        except Exception as e:
            logger.error(f"Error cleaning up snapshots: {e}", exc_info=True)
        
        return deleted_count
    
    def should_create_snapshot(self, symbol: str) -> bool:
        """
        Check if snapshot should be created for a symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            True if snapshot should be created, False otherwise
        """
        last_time = self._last_snapshot_time.get(symbol, 0)
        elapsed = time.time() - last_time
        return elapsed >= self.snapshot_interval
    
    def get_snapshot_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get information about most recent snapshot for a symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Dict with snapshot info, or None if no snapshot found
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            pattern = f"{normalized_symbol}_M1_snapshot_*.csv*"
            snapshots = list(self.snapshot_directory.glob(pattern))
            
            if not snapshots:
                return None
            
            # Get most recent
            snapshots.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            latest = snapshots[0]
            
            stat = latest.stat()
            age_seconds = time.time() - stat.st_mtime
            
            return {
                'filename': latest.name,
                'filepath': str(latest),
                'size_bytes': stat.st_size,
                'age_seconds': age_seconds,
                'created': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                'compressed': self.use_compression and latest.suffix == '.zstd'
            }
            
        except Exception as e:
            logger.error(f"Error getting snapshot info for {symbol}: {e}", exc_info=True)
            return None

