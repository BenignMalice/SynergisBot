"""
Offset Calibrator
Dynamic price synchronization between Binance and MT5 feeds
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)

@dataclass
class OffsetConfig:
    """Offset calibration configuration"""
    calibration_interval: int
    atr_threshold: float  # 0.5 ATR threshold for price differences
    max_offset: float
    drift_threshold: float
    m5_structure_weight: float  # Weight for M5 structure in reconciliation
    min_samples_for_calibration: int  # Minimum samples needed
    time_alignment_window: int  # Seconds for time alignment

@dataclass
class OffsetData:
    """Offset calibration data"""
    symbol: str
    offset: float
    confidence: float
    last_calibration: datetime
    sample_count: int
    drift_rate: float

class OffsetCalibrator:
    """
    Dynamic Offset Engine for Binance-MT5 price synchronization
    
    Features:
    - Continuous offset calibration
    - ATR-based threshold detection
    - Weighted reconciliation logic
    - Drift detection and correction
    - M5 structure discrepancy handling
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = OffsetConfig(**config)
        self.is_active = False
        
        # Offset storage
        self.offsets: Dict[str, OffsetData] = {}
        self.calibration_history: Dict[str, List[Tuple[datetime, float]]] = {}
        
        # Price samples for calibration
        self.binance_samples: Dict[str, List[Tuple[datetime, float]]] = {}
        self.mt5_samples: Dict[str, List[Tuple[datetime, float]]] = {}
        
        # M5 structure data for enhanced reconciliation
        self.m5_structure_data: Dict[str, Dict[str, Any]] = {}
        
        # ATR data for threshold detection
        self.atr_data: Dict[str, float] = {}
        
        # Performance metrics
        self.performance_metrics = {
            'calibrations_performed': 0,
            'last_calibration': None,
            'average_offset': 0.0,
            'drift_detections': 0,
            'error_count': 0
        }
        
        logger.info("OffsetCalibrator initialized")
    
    async def initialize(self):
        """Initialize offset calibrator"""
        try:
            logger.info("🔧 Initializing offset calibrator...")
            
            # Initialize offset data for all symbols
            symbols = ['BTCUSDT', 'XAUUSDT', 'ETHUSDT']  # Binance symbols
            for symbol in symbols:
                self.offsets[symbol] = OffsetData(
                    symbol=symbol,
                    offset=0.0,
                    confidence=0.0,
                    last_calibration=datetime.now(timezone.utc),
                    sample_count=0,
                    drift_rate=0.0
                )
                self.calibration_history[symbol] = []
                self.binance_samples[symbol] = []
                self.mt5_samples[symbol] = []
                self.m5_structure_data[symbol] = {
                    'high': 0.0,
                    'low': 0.0,
                    'close': 0.0,
                    'volume': 0.0,
                    'timestamp': None
                }
                self.atr_data[symbol] = 0.0
            
            self.is_active = True
            logger.info("✅ Offset calibrator initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize offset calibrator: {e}")
            raise
    
    async def stop(self):
        """Stop offset calibrator"""
        try:
            logger.info("🛑 Stopping offset calibrator...")
            self.is_active = False
            logger.info("✅ Offset calibrator stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping offset calibrator: {e}")
    
    async def calibrate_offsets(self):
        """Perform offset calibration for all symbols"""
        try:
            if not self.is_active:
                return
            
            logger.debug("🔄 Performing offset calibration...")
            
            for symbol in self.offsets.keys():
                await self._calibrate_symbol_offset(symbol)
            
            self.performance_metrics['calibrations_performed'] += 1
            self.performance_metrics['last_calibration'] = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"❌ Error in offset calibration: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _calibrate_symbol_offset(self, symbol: str):
        """Calibrate offset for a specific symbol"""
        try:
            # Get recent samples
            binance_samples = self._get_recent_samples(self.binance_samples[symbol], minutes=5)
            mt5_samples = self._get_recent_samples(self.mt5_samples[symbol], minutes=5)
            
            if len(binance_samples) < 3 or len(mt5_samples) < 3:
                logger.debug(f"⚠️ Insufficient samples for {symbol} calibration")
                return
            
            # Calculate offset using weighted reconciliation
            offset, confidence = await self._calculate_weighted_offset(
                symbol, binance_samples, mt5_samples
            )
            
            # Check if offset is within acceptable range
            if abs(offset) > self.config.max_offset:
                logger.warning(f"⚠️ Offset for {symbol} too large: {offset:.4f}")
                return
            
            # Check for drift
            drift_rate = await self._detect_drift(symbol, offset)
            
            # Update offset data
            self.offsets[symbol].offset = offset
            self.offsets[symbol].confidence = confidence
            self.offsets[symbol].last_calibration = datetime.now(timezone.utc)
            self.offsets[symbol].sample_count = len(binance_samples) + len(mt5_samples)
            self.offsets[symbol].drift_rate = drift_rate
            
            # Store in history
            self.calibration_history[symbol].append((
                datetime.now(timezone.utc),
                offset
            ))
            
            # Keep only recent history
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            self.calibration_history[symbol] = [
                (timestamp, offset_val) for timestamp, offset_val in self.calibration_history[symbol]
                if timestamp >= cutoff_time
            ]
            
            logger.debug(f"✅ {symbol} offset calibrated: {offset:.4f} (confidence: {confidence:.2f})")
            
        except Exception as e:
            logger.error(f"❌ Error calibrating {symbol} offset: {e}")
    
    def _get_recent_samples(self, samples: List[Tuple[datetime, float]], minutes: int) -> List[Tuple[datetime, float]]:
        """Get recent samples within time window"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return [
            (timestamp, price) for timestamp, price in samples
            if timestamp >= cutoff_time
        ]
    
    async def _calculate_weighted_offset(self, symbol: str, binance_samples: List[Tuple[datetime, float]], 
                                       mt5_samples: List[Tuple[datetime, float]]) -> Tuple[float, float]:
        """Calculate weighted offset using enhanced reconciliation logic with M5 structure"""
        try:
            # Align samples by time
            aligned_pairs = self._align_samples_by_time(binance_samples, mt5_samples)
            
            if len(aligned_pairs) < self.config.min_samples_for_calibration:
                return 0.0, 0.0
            
            # Calculate ATR for threshold detection
            atr = await self._calculate_atr(symbol, aligned_pairs)
            self.atr_data[symbol] = atr
            
            # Calculate individual offsets with enhanced weighting
            offsets = []
            weights = []
            
            for binance_time, binance_price, mt5_time, mt5_price in aligned_pairs:
                # Calculate time difference weight (closer times = higher weight)
                time_diff = abs((binance_time - mt5_time).total_seconds())
                time_weight = max(0, 1 - (time_diff / self.config.time_alignment_window))
                
                # Calculate price difference weight using ATR threshold
                price_diff = abs(binance_price - mt5_price)
                atr_threshold = atr * self.config.atr_threshold  # 0.5 ATR threshold
                price_weight = max(0, 1 - (price_diff / atr_threshold)) if atr_threshold > 0 else 1.0
                
                # M5 structure weight (if available)
                m5_weight = await self._get_m5_structure_weight(symbol, binance_time, mt5_time)
                
                # Combined weight with M5 structure consideration
                weight = time_weight * price_weight * (1 + m5_weight * self.config.m5_structure_weight)
                
                if weight > 0.1:  # Minimum weight threshold
                    offset = mt5_price - binance_price
                    offsets.append(offset)
                    weights.append(weight)
            
            if not offsets:
                return 0.0, 0.0
            
            # Calculate weighted average offset
            weighted_offset = sum(o * w for o, w in zip(offsets, weights)) / sum(weights)
            
            # Calculate confidence based on consistency and ATR threshold compliance
            variance = statistics.variance(offsets) if len(offsets) > 1 else 0
            atr_compliance = 1.0 if abs(weighted_offset) <= atr * self.config.atr_threshold else 0.5
            confidence = max(0, (1 - (variance / (abs(weighted_offset) + 0.001))) * atr_compliance)
            
            return weighted_offset, confidence
            
        except Exception as e:
            logger.error(f"❌ Error calculating weighted offset: {e}")
            return 0.0, 0.0
    
    def _align_samples_by_time(self, binance_samples: List[Tuple[datetime, float]], 
                              mt5_samples: List[Tuple[datetime, float]]) -> List[Tuple[datetime, float, datetime, float]]:
        """Align samples by time for comparison"""
        aligned_pairs = []
        
        for binance_time, binance_price in binance_samples:
            # Find closest MT5 sample within 30 seconds
            closest_mt5 = None
            min_time_diff = float('inf')
            
            for mt5_time, mt5_price in mt5_samples:
                time_diff = abs((binance_time - mt5_time).total_seconds())
                if time_diff < 30 and time_diff < min_time_diff:
                    closest_mt5 = (mt5_time, mt5_price)
                    min_time_diff = time_diff
            
            if closest_mt5:
                aligned_pairs.append((binance_time, binance_price, closest_mt5[0], closest_mt5[1]))
        
        return aligned_pairs
    
    async def _calculate_atr(self, symbol: str, aligned_pairs: List[Tuple[datetime, float, datetime, float]]) -> float:
        """Calculate Average True Range (ATR) for threshold detection"""
        try:
            if len(aligned_pairs) < 14:  # Need at least 14 periods for ATR
                return 0.0
            
            # Extract prices and calculate true ranges
            true_ranges = []
            for i in range(1, len(aligned_pairs)):
                current_high = max(aligned_pairs[i][1], aligned_pairs[i][3])  # Max of Binance and MT5
                current_low = min(aligned_pairs[i][1], aligned_pairs[i][3])   # Min of Binance and MT5
                previous_close = (aligned_pairs[i-1][1] + aligned_pairs[i-1][3]) / 2  # Average of previous
                
                # True Range = max(high - low, |high - prev_close|, |low - prev_close|)
                tr1 = current_high - current_low
                tr2 = abs(current_high - previous_close)
                tr3 = abs(current_low - previous_close)
                true_range = max(tr1, tr2, tr3)
                true_ranges.append(true_range)
            
            # Calculate ATR as simple moving average of true ranges
            atr = sum(true_ranges) / len(true_ranges)
            return atr
            
        except Exception as e:
            logger.error(f"❌ Error calculating ATR: {e}")
            return 0.0
    
    async def _get_m5_structure_weight(self, symbol: str, binance_time: datetime, mt5_time: datetime) -> float:
        """Get M5 structure weight for enhanced reconciliation"""
        try:
            if symbol not in self.m5_structure_data:
                return 0.0
            
            structure = self.m5_structure_data[symbol]
            if not structure['timestamp']:
                return 0.0
            
            # Check if M5 structure is recent (within 5 minutes)
            time_diff = abs((binance_time - structure['timestamp']).total_seconds())
            if time_diff > 300:  # 5 minutes
                return 0.0
            
            # Calculate structure weight based on volume and price action
            volume_weight = min(1.0, structure['volume'] / 1000)  # Normalize volume
            price_action_weight = 1.0 if structure['high'] > structure['low'] else 0.5
            
            return volume_weight * price_action_weight
            
        except Exception as e:
            logger.error(f"❌ Error getting M5 structure weight: {e}")
            return 0.0
    
    async def _detect_drift(self, symbol: str, current_offset: float) -> float:
        """Detect offset drift over time"""
        try:
            history = self.calibration_history[symbol]
            
            if len(history) < 5:
                return 0.0
            
            # Calculate drift rate over last 10 calibrations
            recent_history = history[-10:]
            offsets = [offset for _, offset in recent_history]
            
            if len(offsets) < 3:
                return 0.0
            
            # Calculate linear trend
            time_points = [(timestamp - recent_history[0][0]).total_seconds() / 3600 for timestamp, _ in recent_history]
            offset_values = offsets
            
            # Simple linear regression
            n = len(time_points)
            sum_x = sum(time_points)
            sum_y = sum(offset_values)
            sum_xy = sum(x * y for x, y in zip(time_points, offset_values))
            sum_x2 = sum(x * x for x in time_points)
            
            if n * sum_x2 - sum_x * sum_x == 0:
                return 0.0
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            
            # Check if drift exceeds threshold
            if abs(slope) > self.config.drift_threshold:
                self.performance_metrics['drift_detections'] += 1
                logger.warning(f"⚠️ Drift detected for {symbol}: {slope:.4f} per hour")
            
            return slope
            
        except Exception as e:
            logger.error(f"❌ Error detecting drift: {e}")
            return 0.0
    
    def add_binance_sample(self, symbol: str, timestamp: datetime, price: float):
        """Add Binance price sample for calibration"""
        try:
            if symbol in self.binance_samples:
                self.binance_samples[symbol].append((timestamp, price))
                
                # Keep only recent samples (last hour)
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
                self.binance_samples[symbol] = [
                    (ts, p) for ts, p in self.binance_samples[symbol]
                    if ts >= cutoff_time
                ]
                
        except Exception as e:
            logger.error(f"❌ Error adding Binance sample: {e}")
    
    def add_mt5_sample(self, symbol: str, timestamp: datetime, price: float):
        """Add MT5 price sample for calibration"""
        try:
            if symbol in self.mt5_samples:
                self.mt5_samples[symbol].append((timestamp, price))
                
                # Keep only recent samples (last hour)
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
                self.mt5_samples[symbol] = [
                    (ts, p) for ts, p in self.mt5_samples[symbol]
                    if ts >= cutoff_time
                ]
                
        except Exception as e:
            logger.error(f"❌ Error adding MT5 sample: {e}")
    
    def get_offset(self, symbol: str) -> float:
        """Get current offset for symbol"""
        if symbol in self.offsets:
            return self.offsets[symbol].offset
        return 0.0
    
    def get_all_offsets(self) -> Dict[str, float]:
        """Get all current offsets"""
        return {symbol: data.offset for symbol, data in self.offsets.items()}
    
    def get_offset_data(self, symbol: str) -> Optional[OffsetData]:
        """Get detailed offset data for symbol"""
        return self.offsets.get(symbol)
    
    def is_active(self) -> bool:
        """Check if calibrator is active"""
        return self.is_active
    
    def update_m5_structure(self, symbol: str, high: float, low: float, close: float, volume: float, timestamp: datetime):
        """Update M5 structure data for enhanced reconciliation"""
        try:
            if symbol in self.m5_structure_data:
                self.m5_structure_data[symbol] = {
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': volume,
                    'timestamp': timestamp
                }
                logger.debug(f"📊 Updated M5 structure for {symbol}: H={high:.4f}, L={low:.4f}, V={volume:.0f}")
                
        except Exception as e:
            logger.error(f"❌ Error updating M5 structure: {e}")
    
    def get_atr(self, symbol: str) -> float:
        """Get current ATR for symbol"""
        return self.atr_data.get(symbol, 0.0)
    
    def get_m5_structure(self, symbol: str) -> Dict[str, Any]:
        """Get M5 structure data for symbol"""
        return self.m5_structure_data.get(symbol, {})
    
    def is_offset_within_threshold(self, symbol: str, offset: float) -> bool:
        """Check if offset is within ATR threshold"""
        atr = self.get_atr(symbol)
        threshold = atr * self.config.atr_threshold
        return abs(offset) <= threshold
    
    def get_status(self) -> Dict[str, Any]:
        """Get calibrator status"""
        return {
            'is_active': self.is_active,
            'offsets': {symbol: {
                'offset': data.offset,
                'confidence': data.confidence,
                'last_calibration': data.last_calibration.isoformat(),
                'sample_count': data.sample_count,
                'drift_rate': data.drift_rate,
                'atr': self.atr_data.get(symbol, 0.0),
                'within_threshold': self.is_offset_within_threshold(symbol, data.offset)
            } for symbol, data in self.offsets.items()},
            'performance_metrics': self.performance_metrics
        }
