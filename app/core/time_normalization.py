"""
Time Normalization System
Ensures consistent timestamps across all data sources
Normalizes time to epoch_ms (INTEGER) with source tracking
"""

import time
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
import threading
from collections import deque

logger = logging.getLogger(__name__)

class TimeSource(Enum):
    """Time source types"""
    MT5 = "mt5"
    BINANCE = "binance"
    SYSTEM = "system"
    CALCULATED = "calculated"

class TimeQuality(Enum):
    """Time quality levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    STALE = "stale"

@dataclass
class NormalizedTime:
    """Normalized time structure"""
    epoch_ms: int
    source: TimeSource
    symbol: str
    original_timestamp: Any = None
    quality: TimeQuality = TimeQuality.GOOD
    offset_ms: int = 0
    sequence_id: Optional[int] = None

@dataclass
class TimeOffset:
    """Time offset calibration data"""
    symbol: str
    source: TimeSource
    offset_ms: int
    confidence: float
    last_updated: float
    sample_count: int = 0

@dataclass
class TimeNormalizationStats:
    """Statistics for time normalization"""
    total_normalizations: int = 0
    successful_normalizations: int = 0
    failed_normalizations: int = 0
    avg_processing_time_ns: float = 0.0
    max_processing_time_ns: float = 0.0
    offset_calibrations: int = 0
    quality_distribution: Dict[TimeQuality, int] = field(default_factory=dict)

class TimeNormalizer:
    """
    High-performance time normalization system
    Ensures consistent timestamps across all data sources
    """
    
    def __init__(self):
        # Time offsets per symbol and source
        self.time_offsets: Dict[Tuple[str, TimeSource], TimeOffset] = {}
        
        # Statistics
        self.stats = TimeNormalizationStats()
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Quality monitoring
        self.quality_history = deque(maxlen=1000)
        
        # Callbacks
        self.quality_callbacks: List[callable] = []
        self.offset_callbacks: List[callable] = []
        
        logger.info("TimeNormalizer initialized")
    
    def normalize_time(self, timestamp: Union[int, float, datetime, str], 
                      source: TimeSource, symbol: str, 
                      original_timestamp: Any = None) -> NormalizedTime:
        """
        Normalize timestamp to epoch_ms with source tracking
        """
        start_time = time.perf_counter_ns()
        
        try:
            # Convert timestamp to epoch_ms
            epoch_ms = self._convert_to_epoch_ms(timestamp)
            
            # Apply offset calibration
            offset_ms = self._get_offset(symbol, source)
            adjusted_epoch_ms = epoch_ms + offset_ms
            
            # Determine quality
            quality = self._assess_time_quality(epoch_ms, source, symbol)
            
            # Create normalized time
            normalized_time = NormalizedTime(
                epoch_ms=adjusted_epoch_ms,
                source=source,
                symbol=symbol,
                original_timestamp=original_timestamp,
                quality=quality,
                offset_ms=offset_ms
            )
            
            # Update statistics
            self._update_stats(start_time, True)
            self._update_quality_distribution(quality)
            
            return normalized_time
            
        except Exception as e:
            logger.error(f"Error normalizing time: {e}")
            self._update_stats(start_time, False)
            
            # Return fallback normalized time
            return NormalizedTime(
                epoch_ms=int(time.time() * 1000),
                source=source,
                symbol=symbol,
                original_timestamp=original_timestamp,
                quality=TimeQuality.POOR
            )
    
    def _convert_to_epoch_ms(self, timestamp: Union[int, float, datetime, str]) -> int:
        """Convert various timestamp formats to epoch_ms"""
        if isinstance(timestamp, int):
            # Assume it's already in milliseconds if > 1e10, otherwise seconds
            if timestamp > 1e10:
                return timestamp
            else:
                return timestamp * 1000
        
        elif isinstance(timestamp, float):
            # Convert to milliseconds
            return int(timestamp * 1000)
        
        elif isinstance(timestamp, datetime):
            # Convert datetime to epoch_ms
            if timestamp.tzinfo is None:
                # Assume UTC if no timezone info
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            return int(timestamp.timestamp() * 1000)
        
        elif isinstance(timestamp, str):
            # Parse string timestamp
            try:
                # Try parsing as ISO format
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return int(dt.timestamp() * 1000)
            except ValueError:
                # Try parsing as Unix timestamp
                return int(float(timestamp) * 1000)
        
        else:
            raise ValueError(f"Unsupported timestamp type: {type(timestamp)}")
    
    def _get_offset(self, symbol: str, source: TimeSource) -> int:
        """Get time offset for symbol and source"""
        with self.lock:
            key = (symbol, source)
            if key in self.time_offsets:
                return self.time_offsets[key].offset_ms
            return 0
    
    def _assess_time_quality(self, epoch_ms: int, source: TimeSource, symbol: str) -> TimeQuality:
        """Assess time quality based on various factors"""
        current_time_ms = int(time.time() * 1000)
        time_diff_ms = abs(current_time_ms - epoch_ms)
        
        # Factor 1: Time difference from current time
        if time_diff_ms < 1000:  # 1 second
            quality_score = 1.0
        elif time_diff_ms < 5000:  # 5 seconds
            quality_score = 0.8
        elif time_diff_ms < 30000:  # 30 seconds
            quality_score = 0.6
        elif time_diff_ms < 300000:  # 5 minutes
            quality_score = 0.4
        else:
            quality_score = 0.2
        
        # Factor 2: Source reliability
        source_reliability = {
            TimeSource.MT5: 0.9,
            TimeSource.BINANCE: 0.95,
            TimeSource.SYSTEM: 1.0,
            TimeSource.CALCULATED: 0.7
        }
        quality_score *= source_reliability.get(source, 0.5)
        
        # Factor 3: Symbol-specific factors
        # Some symbols might have better time accuracy
        if symbol in ['BTCUSDc', 'XAUUSDc']:  # Crypto/commodity symbols
            quality_score *= 1.0
        elif symbol in ['EURUSDc', 'GBPUSDc', 'USDJPYc']:  # Major forex
            quality_score *= 0.95
        else:  # Other symbols
            quality_score *= 0.9
        
        # Determine quality level
        if quality_score >= 0.9:
            return TimeQuality.EXCELLENT
        elif quality_score >= 0.7:
            return TimeQuality.GOOD
        elif quality_score >= 0.5:
            return TimeQuality.FAIR
        elif quality_score >= 0.3:
            return TimeQuality.POOR
        else:
            return TimeQuality.STALE
    
    def calibrate_offset(self, symbol: str, source: TimeSource, 
                        reference_time_ms: int, measured_time_ms: int,
                        confidence: float = 1.0) -> bool:
        """
        Calibrate time offset for a symbol and source
        """
        try:
            offset_ms = reference_time_ms - measured_time_ms
            
            with self.lock:
                key = (symbol, source)
                
                if key in self.time_offsets:
                    # Update existing offset with weighted average
                    existing = self.time_offsets[key]
                    new_offset = int((existing.offset_ms * existing.sample_count + offset_ms) / 
                                   (existing.sample_count + 1))
                    existing.offset_ms = new_offset
                    existing.confidence = (existing.confidence * existing.sample_count + confidence) / \
                                        (existing.sample_count + 1)
                    existing.sample_count += 1
                    existing.last_updated = time.time()
                else:
                    # Create new offset
                    self.time_offsets[key] = TimeOffset(
                        symbol=symbol,
                        source=source,
                        offset_ms=offset_ms,
                        confidence=confidence,
                        last_updated=time.time(),
                        sample_count=1
                    )
                
                self.stats.offset_calibrations += 1
                
                # Notify callbacks
                for callback in self.offset_callbacks:
                    try:
                        callback(symbol, source, offset_ms, confidence)
                    except Exception as e:
                        logger.error(f"Error in offset callback: {e}")
                
                logger.debug(f"Calibrated offset for {symbol} {source.value}: {offset_ms}ms")
                return True
                
        except Exception as e:
            logger.error(f"Error calibrating offset for {symbol} {source.value}: {e}")
            return False
    
    def get_offset(self, symbol: str, source: TimeSource) -> Optional[TimeOffset]:
        """Get time offset for symbol and source"""
        with self.lock:
            key = (symbol, source)
            return self.time_offsets.get(key)
    
    def get_all_offsets(self) -> Dict[Tuple[str, TimeSource], TimeOffset]:
        """Get all time offsets"""
        with self.lock:
            return dict(self.time_offsets)
    
    def clear_offsets(self, symbol: Optional[str] = None, source: Optional[TimeSource] = None):
        """Clear time offsets"""
        with self.lock:
            if symbol and source:
                # Clear specific offset
                key = (symbol, source)
                if key in self.time_offsets:
                    del self.time_offsets[key]
            elif symbol:
                # Clear all offsets for symbol
                keys_to_remove = [key for key in self.time_offsets.keys() if key[0] == symbol]
                for key in keys_to_remove:
                    del self.time_offsets[key]
            elif source:
                # Clear all offsets for source
                keys_to_remove = [key for key in self.time_offsets.keys() if key[1] == source]
                for key in keys_to_remove:
                    del self.time_offsets[key]
            else:
                # Clear all offsets
                self.time_offsets.clear()
    
    def _update_stats(self, start_time: int, success: bool):
        """Update normalization statistics"""
        end_time = time.perf_counter_ns()
        processing_time_ns = end_time - start_time
        
        self.stats.total_normalizations += 1
        if success:
            self.stats.successful_normalizations += 1
        else:
            self.stats.failed_normalizations += 1
        
        # Update processing time statistics
        self.stats.avg_processing_time_ns = (
            (self.stats.avg_processing_time_ns * (self.stats.total_normalizations - 1) + processing_time_ns) 
            / self.stats.total_normalizations
        )
        self.stats.max_processing_time_ns = max(self.stats.max_processing_time_ns, processing_time_ns)
    
    def _update_quality_distribution(self, quality: TimeQuality):
        """Update quality distribution statistics"""
        self.stats.quality_distribution[quality] = self.stats.quality_distribution.get(quality, 0) + 1
        self.quality_history.append(quality)
    
    def add_quality_callback(self, callback: callable):
        """Add callback for quality changes"""
        self.quality_callbacks.append(callback)
    
    def add_offset_callback(self, callback: callable):
        """Add callback for offset changes"""
        self.offset_callbacks.append(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get normalization statistics"""
        with self.lock:
            return {
                'stats': {
                    'total_normalizations': self.stats.total_normalizations,
                    'successful_normalizations': self.stats.successful_normalizations,
                    'failed_normalizations': self.stats.failed_normalizations,
                    'success_rate': self.stats.successful_normalizations / max(self.stats.total_normalizations, 1),
                    'avg_processing_time_ns': self.stats.avg_processing_time_ns,
                    'avg_processing_time_ms': self.stats.avg_processing_time_ns / 1_000_000,
                    'max_processing_time_ns': self.stats.max_processing_time_ns,
                    'max_processing_time_ms': self.stats.max_processing_time_ns / 1_000_000,
                    'offset_calibrations': self.stats.offset_calibrations,
                    'quality_distribution': {
                        quality.value: count 
                        for quality, count in self.stats.quality_distribution.items()
                    }
                },
                'offsets': {
                    f"{symbol}_{source.value}": {
                        'offset_ms': offset.offset_ms,
                        'confidence': offset.confidence,
                        'sample_count': offset.sample_count,
                        'last_updated': offset.last_updated
                    }
                    for (symbol, source), offset in self.time_offsets.items()
                }
            }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of time normalization"""
        with self.lock:
            total_offsets = len(self.time_offsets)
            recent_offsets = sum(1 for offset in self.time_offsets.values() 
                               if time.time() - offset.last_updated < 3600)  # 1 hour
            
            return {
                'healthy': self.stats.successful_normalizations / max(self.stats.total_normalizations, 1) > 0.95,
                'total_offsets': total_offsets,
                'recent_offsets': recent_offsets,
                'success_rate': self.stats.successful_normalizations / max(self.stats.total_normalizations, 1),
                'avg_processing_time_ms': self.stats.avg_processing_time_ns / 1_000_000
            }

class SymbolNormalizer:
    """
    Normalizes symbols across different data sources
    Ensures consistent symbol naming
    """
    
    def __init__(self):
        # Symbol mapping between sources
        self.symbol_mappings = {
            'BTCUSDc': {
                TimeSource.MT5: 'BTCUSDc',
                TimeSource.BINANCE: 'BTCUSDT'
            },
            'XAUUSDc': {
                TimeSource.MT5: 'XAUUSDc',
                TimeSource.BINANCE: 'XAUUSDT'
            },
            'EURUSDc': {
                TimeSource.MT5: 'EURUSDc',
                TimeSource.BINANCE: 'EURUSDT'
            },
            'GBPUSDc': {
                TimeSource.MT5: 'GBPUSDc',
                TimeSource.BINANCE: 'GBPUSDT'
            }
        }
        
        # Reverse mappings
        self.reverse_mappings = {}
        for normalized_symbol, source_mappings in self.symbol_mappings.items():
            for source, source_symbol in source_mappings.items():
                if source_symbol not in self.reverse_mappings:
                    self.reverse_mappings[source_symbol] = {}
                self.reverse_mappings[source_symbol][source] = normalized_symbol
    
    def normalize_symbol(self, symbol: str, source: TimeSource) -> str:
        """Normalize symbol to standard format"""
        # Check if symbol is already normalized
        if symbol in self.symbol_mappings:
            return symbol
        
        # Check reverse mapping
        if symbol in self.reverse_mappings:
            source_mappings = self.reverse_mappings[symbol]
            if source in source_mappings:
                return source_mappings[source]
        
        # If no mapping found, return symbol as-is
        return symbol
    
    def get_source_symbol(self, normalized_symbol: str, source: TimeSource) -> str:
        """Get source-specific symbol for normalized symbol"""
        if normalized_symbol in self.symbol_mappings:
            source_mappings = self.symbol_mappings[normalized_symbol]
            return source_mappings.get(source, normalized_symbol)
        
        return normalized_symbol
    
    def add_symbol_mapping(self, normalized_symbol: str, source: TimeSource, source_symbol: str):
        """Add symbol mapping"""
        if normalized_symbol not in self.symbol_mappings:
            self.symbol_mappings[normalized_symbol] = {}
        
        self.symbol_mappings[normalized_symbol][source] = source_symbol
        
        # Update reverse mapping
        if source_symbol not in self.reverse_mappings:
            self.reverse_mappings[source_symbol] = {}
        self.reverse_mappings[source_symbol][source] = normalized_symbol

# Global instances
_time_normalizer: Optional[TimeNormalizer] = None
_symbol_normalizer: Optional[SymbolNormalizer] = None

def get_time_normalizer() -> TimeNormalizer:
    """Get the global time normalizer instance"""
    global _time_normalizer
    if _time_normalizer is None:
        _time_normalizer = TimeNormalizer()
    return _time_normalizer

def get_symbol_normalizer() -> SymbolNormalizer:
    """Get the global symbol normalizer instance"""
    global _symbol_normalizer
    if _symbol_normalizer is None:
        _symbol_normalizer = SymbolNormalizer()
    return _symbol_normalizer

def normalize_timestamp(timestamp: Union[int, float, datetime, str], 
                       source: TimeSource, symbol: str) -> NormalizedTime:
    """Convenience function to normalize timestamp"""
    normalizer = get_time_normalizer()
    return normalizer.normalize_time(timestamp, source, symbol)

def normalize_symbol(symbol: str, source: TimeSource) -> str:
    """Convenience function to normalize symbol"""
    normalizer = get_symbol_normalizer()
    return normalizer.normalize_symbol(symbol, source)
