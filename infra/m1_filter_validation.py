"""
M1 Filter Pass Rate Validation System

This module implements a comprehensive validation system for M1 filter pass rates,
ensuring the system meets the >60% pass rate target for post-confirmation M1 filters.

Key Features:
- M1 filter pass rate measurement
- Post-confirmation filter validation
- VWAP reclaim/loss detection
- Volume delta spike analysis
- ATR ratio validation
- Spread filter effectiveness
- Micro-BOS/CHOCH detection
- Filter performance analytics
"""

import time
import json
import logging
import threading
import statistics
import numpy as np
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import hashlib

logger = logging.getLogger(__name__)

class FilterType(Enum):
    """Types of M1 filters"""
    VWAP_RECLAIM = "vwap_reclaim"
    VWAP_LOSS = "vwap_loss"
    VOLUME_DELTA_SPIKE = "volume_delta_spike"
    ATR_RATIO = "atr_ratio"
    SPREAD_FILTER = "spread_filter"
    MICRO_BOS = "micro_bos"
    MICRO_CHOCH = "micro_choch"
    NEWS_WINDOW = "news_window"

class FilterStatus(Enum):
    """Filter status"""
    PASS = "pass"
    FAIL = "fail"
    PENDING = "pending"
    EXPIRED = "expired"
    INVALID = "invalid"

class PassRateLevel(Enum):
    """Pass rate level classifications"""
    EXCELLENT = "excellent"  # >80%
    GOOD = "good"  # 60-80%
    FAIR = "fair"  # 40-60%
    POOR = "poor"  # <40%

@dataclass
class M1FilterData:
    """M1 filter data point"""
    timestamp: float
    symbol: str
    price: float
    volume: float
    spread: float
    vwap: float
    atr_m1: float
    atr_m5: float
    delta_proxy: float
    micro_bos_strength: float
    micro_choch_strength: float
    news_impact: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FilterResult:
    """M1 filter result"""
    filter_id: str
    timestamp: float
    filter_type: FilterType
    symbol: str
    status: FilterStatus
    confidence: float
    pass_rate: float
    execution_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PassRateMetrics:
    """Pass rate metrics for M1 filters"""
    total_filters: int = 0
    passed_filters: int = 0
    failed_filters: int = 0
    pending_filters: int = 0
    overall_pass_rate: float = 0.0
    vwap_reclaim_rate: float = 0.0
    volume_delta_rate: float = 0.0
    atr_ratio_rate: float = 0.0
    spread_filter_rate: float = 0.0
    micro_bos_rate: float = 0.0
    micro_choch_rate: float = 0.0
    symbol_pass_rates: Dict[str, float] = field(default_factory=dict)
    timeframe_pass_rates: Dict[str, float] = field(default_factory=dict)

class VWAPFilter:
    """VWAP reclaim/loss filter"""
    
    def __init__(self, session_anchor: str = "24h", sigma_window: int = 60):
        self.session_anchor = session_anchor
        self.sigma_window = sigma_window
        self.vwap_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.sigma_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=sigma_window))
    
    def process_tick(self, symbol: str, timestamp: float, price: float, 
                    volume: float) -> Tuple[bool, float, Dict[str, Any]]:
        """Process tick for VWAP analysis"""
        key = f"{symbol}_{self.session_anchor}"
        
        # Add to VWAP data
        self.vwap_data[key].append({
            'timestamp': timestamp,
            'price': price,
            'volume': volume
        })
        
        # Calculate VWAP
        vwap = self._calculate_vwap(self.vwap_data[key])
        
        # Calculate sigma
        sigma = self._calculate_sigma(self.vwap_data[key], vwap)
        
        # Add to sigma data
        self.sigma_data[key].append(sigma)
        
        # Check for VWAP reclaim/loss
        reclaim_detected = self._detect_vwap_reclaim(price, vwap, sigma)
        loss_detected = self._detect_vwap_loss(price, vwap, sigma)
        
        confidence = self._calculate_confidence(vwap, sigma, volume)
        
        metadata = {
            'vwap': vwap,
            'sigma': sigma,
            'reclaim_detected': reclaim_detected,
            'loss_detected': loss_detected,
            'session_anchor': self.session_anchor
        }
        
        return reclaim_detected or loss_detected, confidence, metadata
    
    def _calculate_vwap(self, data: deque) -> float:
        """Calculate VWAP"""
        if not data:
            return 0.0
        
        total_volume = sum(item['volume'] for item in data)
        if total_volume == 0:
            return 0.0
        
        weighted_sum = sum(item['price'] * item['volume'] for item in data)
        return weighted_sum / total_volume
    
    def _calculate_sigma(self, data: deque, vwap: float) -> float:
        """Calculate VWAP sigma"""
        if len(data) < 2:
            return 0.0
        
        # Calculate variance
        variance = sum((item['price'] - vwap) ** 2 * item['volume'] for item in data)
        total_volume = sum(item['volume'] for item in data)
        
        if total_volume == 0:
            return 0.0
        
        return np.sqrt(variance / total_volume)
    
    def _detect_vwap_reclaim(self, price: float, vwap: float, sigma: float) -> bool:
        """Detect VWAP reclaim"""
        if sigma == 0:
            return False
        
        # Price reclaims VWAP from below
        return price > vwap and (price - vwap) > sigma * 0.5
    
    def _detect_vwap_loss(self, price: float, vwap: float, sigma: float) -> bool:
        """Detect VWAP loss"""
        if sigma == 0:
            return False
        
        # Price loses VWAP from above
        return price < vwap and (vwap - price) > sigma * 0.5
    
    def _calculate_confidence(self, vwap: float, sigma: float, volume: float) -> float:
        """Calculate filter confidence"""
        if sigma == 0:
            return 0.0
        
        # Confidence based on sigma and volume
        sigma_confidence = min(1.0, sigma / (vwap * 0.01))  # 1% of price
        volume_confidence = min(1.0, volume / 1000.0)  # Normalize volume
        
        return (sigma_confidence + volume_confidence) / 2.0

class VolumeDeltaFilter:
    """Volume delta spike filter"""
    
    def __init__(self, lookback_periods: int = 20, spike_threshold: float = 2.0):
        self.lookback_periods = lookback_periods
        self.spike_threshold = spike_threshold
        self.delta_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.volume_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
    
    def process_tick(self, symbol: str, timestamp: float, price: float, 
                    volume: float, direction: int) -> Tuple[bool, float, Dict[str, Any]]:
        """Process tick for volume delta analysis"""
        key = symbol
        
        # Calculate delta proxy
        delta_proxy = self._calculate_delta_proxy(price, direction, volume)
        
        # Add to data
        self.delta_data[key].append(delta_proxy)
        self.volume_data[key].append(volume)
        
        # Check for volume delta spike
        spike_detected = self._detect_volume_delta_spike(key)
        
        confidence = self._calculate_spike_confidence(key, delta_proxy, volume)
        
        metadata = {
            'delta_proxy': delta_proxy,
            'volume': volume,
            'direction': direction,
            'spike_threshold': self.spike_threshold
        }
        
        return spike_detected, confidence, metadata
    
    def _calculate_delta_proxy(self, price: float, direction: int, volume: float) -> float:
        """Calculate delta proxy"""
        # Simple delta proxy: price change * direction * volume
        return price * direction * volume
    
    def _detect_volume_delta_spike(self, symbol: str) -> bool:
        """Detect volume delta spike"""
        if len(self.delta_data[symbol]) < self.lookback_periods:
            return False
        
        current_delta = self.delta_data[symbol][-1]
        historical_deltas = list(self.delta_data[symbol])[-self.lookback_periods:-1]
        
        if not historical_deltas:
            return False
        
        avg_delta = statistics.mean(historical_deltas)
        std_delta = statistics.stdev(historical_deltas) if len(historical_deltas) > 1 else 0
        
        if std_delta == 0:
            return False
        
        # Check if current delta is above threshold
        z_score = abs(current_delta - avg_delta) / std_delta
        return z_score > self.spike_threshold
    
    def _calculate_spike_confidence(self, symbol: str, delta_proxy: float, volume: float) -> float:
        """Calculate spike confidence"""
        if len(self.delta_data[symbol]) < 2:
            return 0.0
        
        # Confidence based on delta magnitude and volume
        delta_confidence = min(1.0, abs(delta_proxy) / 10000.0)  # Normalize
        volume_confidence = min(1.0, volume / 1000.0)  # Normalize
        
        return (delta_confidence + volume_confidence) / 2.0

class ATRRatioFilter:
    """ATR ratio filter"""
    
    def __init__(self, m1_period: int = 14, m5_period: int = 14, 
                 ratio_threshold: float = 0.5):
        self.m1_period = m1_period
        self.m5_period = m5_period
        self.ratio_threshold = ratio_threshold
        self.m1_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.m5_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
    
    def process_tick(self, symbol: str, timestamp: float, price: float, 
                    timeframe: str) -> Tuple[bool, float, Dict[str, Any]]:
        """Process tick for ATR ratio analysis"""
        key = f"{symbol}_{timeframe}"
        
        # Add to appropriate timeframe data
        if timeframe == "M1":
            self.m1_data[symbol].append({
                'timestamp': timestamp,
                'price': price
            })
        elif timeframe == "M5":
            self.m5_data[symbol].append({
                'timestamp': timestamp,
                'price': price
            })
        
        # Calculate ATR ratio
        atr_ratio = self._calculate_atr_ratio(symbol)
        
        # Check if ratio meets threshold
        ratio_valid = atr_ratio >= self.ratio_threshold
        
        confidence = self._calculate_ratio_confidence(atr_ratio)
        
        metadata = {
            'atr_ratio': atr_ratio,
            'm1_atr': self._calculate_atr(self.m1_data[symbol]) if self.m1_data[symbol] else 0.0,
            'm5_atr': self._calculate_atr(self.m5_data[symbol]) if self.m5_data[symbol] else 0.0,
            'ratio_threshold': self.ratio_threshold
        }
        
        return ratio_valid, confidence, metadata
    
    def _calculate_atr_ratio(self, symbol: str) -> float:
        """Calculate ATR ratio (M1 ATR / M5 ATR)"""
        m1_atr = self._calculate_atr(self.m1_data[symbol])
        m5_atr = self._calculate_atr(self.m5_data[symbol])
        
        if m5_atr == 0:
            return 0.0
        
        return m1_atr / m5_atr
    
    def _calculate_atr(self, data: deque) -> float:
        """Calculate ATR"""
        if len(data) < 2:
            return 0.0
        
        # Calculate True Range for each period
        true_ranges = []
        for i in range(1, len(data)):
            high = data[i]['price']
            low = data[i]['price']
            prev_close = data[i-1]['price']
            
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)
        
        if not true_ranges:
            return 0.0
        
        # Calculate ATR as average of True Ranges
        return statistics.mean(true_ranges)
    
    def _calculate_ratio_confidence(self, atr_ratio: float) -> float:
        """Calculate ratio confidence"""
        # Confidence based on ratio magnitude
        return min(1.0, atr_ratio / 2.0)  # Normalize to 2.0 max

class SpreadFilter:
    """Spread filter"""
    
    def __init__(self, median_period: int = 20, outlier_threshold: float = 2.0):
        self.median_period = median_period
        self.outlier_threshold = outlier_threshold
        self.spread_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.news_events: Dict[str, List[Dict]] = defaultdict(list)
    
    def process_tick(self, symbol: str, timestamp: float, spread: float, 
                    news_impact: float = 0.0) -> Tuple[bool, float, Dict[str, Any]]:
        """Process tick for spread analysis"""
        key = symbol
        
        # Add spread data
        self.spread_data[key].append({
            'timestamp': timestamp,
            'spread': spread,
            'news_impact': news_impact
        })
        
        # Check if in news window
        in_news_window = self._is_in_news_window(symbol, timestamp)
        
        # Calculate spread quality
        spread_quality = self._calculate_spread_quality(key, spread)
        
        # Check if spread is acceptable
        spread_acceptable = spread_quality and not in_news_window
        
        confidence = self._calculate_spread_confidence(key, spread, news_impact)
        
        metadata = {
            'spread': spread,
            'spread_quality': spread_quality,
            'in_news_window': in_news_window,
            'news_impact': news_impact,
            'median_spread': self._calculate_median_spread(key)
        }
        
        return spread_acceptable, confidence, metadata
    
    def _is_in_news_window(self, symbol: str, timestamp: float) -> bool:
        """Check if timestamp is in news window"""
        if symbol not in self.news_events:
            return False
        
        for event in self.news_events[symbol]:
            if event['start_time'] <= timestamp <= event['end_time']:
                return True
        
        return False
    
    def _calculate_spread_quality(self, symbol: str, current_spread: float) -> bool:
        """Calculate spread quality"""
        if len(self.spread_data[symbol]) < self.median_period:
            return True  # Not enough data, assume good
        
        # Get recent spreads
        recent_spreads = [item['spread'] for item in list(self.spread_data[symbol])[-self.median_period:]]
        
        # Calculate median
        median_spread = statistics.median(recent_spreads)
        
        # Check if current spread is within acceptable range
        return current_spread <= median_spread * 1.5  # 50% above median
    
    def _calculate_median_spread(self, symbol: str) -> float:
        """Calculate median spread"""
        if len(self.spread_data[symbol]) < self.median_period:
            return 0.0
        
        recent_spreads = [item['spread'] for item in list(self.spread_data[symbol])[-self.median_period:]]
        return statistics.median(recent_spreads)
    
    def _calculate_spread_confidence(self, symbol: str, spread: float, news_impact: float) -> float:
        """Calculate spread confidence"""
        median_spread = self._calculate_median_spread(symbol)
        
        if median_spread == 0:
            return 0.0
        
        # Confidence based on spread relative to median
        spread_confidence = min(1.0, median_spread / spread) if spread > 0 else 0.0
        
        # Reduce confidence if in news window
        news_penalty = news_impact * 0.5
        
        return max(0.0, spread_confidence - news_penalty)

class MicroBOSFilter:
    """Micro-BOS/CHOCH filter"""
    
    def __init__(self, lookback_bars: int = 5, atr_multiplier: float = 0.5, 
                 cooldown_periods: int = 3):
        self.lookback_bars = lookback_bars
        self.atr_multiplier = atr_multiplier
        self.cooldown_periods = cooldown_periods
        self.bar_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.last_detection: Dict[str, float] = {}
    
    def process_tick(self, symbol: str, timestamp: float, price: float, 
                   atr: float) -> Tuple[bool, float, Dict[str, Any]]:
        """Process tick for micro-BOS/CHOCH analysis"""
        key = symbol
        
        # Add bar data
        self.bar_data[key].append({
            'timestamp': timestamp,
            'price': price,
            'atr': atr
        })
        
        # Check cooldown
        if self._is_in_cooldown(symbol, timestamp):
            return False, 0.0, {'cooldown': True}
        
        # Detect micro-BOS
        micro_bos = self._detect_micro_bos(key, price, atr)
        
        # Detect micro-CHOCH
        micro_choch = self._detect_micro_choch(key, price, atr)
        
        # Calculate strength
        strength = self._calculate_strength(key, price, atr)
        
        # Update last detection if found
        if micro_bos or micro_choch:
            self.last_detection[symbol] = timestamp
        
        confidence = self._calculate_micro_confidence(strength, atr)
        
        metadata = {
            'micro_bos': micro_bos,
            'micro_choch': micro_choch,
            'strength': strength,
            'atr': atr,
            'atr_multiplier': self.atr_multiplier
        }
        
        return micro_bos or micro_choch, confidence, metadata
    
    def _is_in_cooldown(self, symbol: str, timestamp: float) -> bool:
        """Check if in cooldown period"""
        if symbol not in self.last_detection:
            return False
        
        time_since_detection = timestamp - self.last_detection[symbol]
        cooldown_duration = self.cooldown_periods * 60  # 3 minutes in seconds
        
        return time_since_detection < cooldown_duration
    
    def _detect_micro_bos(self, symbol: str, price: float, atr: float) -> bool:
        """Detect micro-BOS"""
        if len(self.bar_data[symbol]) < self.lookback_bars:
            return False
        
        # Get recent bars
        recent_bars = list(self.bar_data[symbol])[-self.lookback_bars:]
        
        # Check for break of structure
        recent_highs = [bar['price'] for bar in recent_bars]
        max_recent_high = max(recent_highs)
        
        # Check if price breaks above recent high with ATR displacement
        atr_displacement = atr * self.atr_multiplier
        return price > max_recent_high + atr_displacement
    
    def _detect_micro_choch(self, symbol: str, price: float, atr: float) -> bool:
        """Detect micro-CHOCH"""
        if len(self.bar_data[symbol]) < self.lookback_bars:
            return False
        
        # Get recent bars
        recent_bars = list(self.bar_data[symbol])[-self.lookback_bars:]
        
        # Check for change of character
        recent_lows = [bar['price'] for bar in recent_bars]
        min_recent_low = min(recent_lows)
        
        # Check if price breaks below recent low with ATR displacement
        atr_displacement = atr * self.atr_multiplier
        return price < min_recent_low - atr_displacement
    
    def _calculate_strength(self, symbol: str, price: float, atr: float) -> float:
        """Calculate micro-BOS/CHOCH strength"""
        if len(self.bar_data[symbol]) < 2:
            return 0.0
        
        # Strength based on ATR displacement
        recent_bars = list(self.bar_data[symbol])[-2:]
        price_change = abs(price - recent_bars[0]['price'])
        
        if atr == 0:
            return 0.0
        
        return min(1.0, price_change / (atr * self.atr_multiplier))
    
    def _calculate_micro_confidence(self, strength: float, atr: float) -> float:
        """Calculate micro-BOS/CHOCH confidence"""
        # Confidence based on strength and ATR
        strength_confidence = strength
        atr_confidence = min(1.0, atr / 100.0)  # Normalize ATR
        
        return (strength_confidence + atr_confidence) / 2.0

class M1FilterValidator:
    """M1 filter validation system"""
    
    def __init__(self):
        self.vwap_filter = VWAPFilter()
        self.volume_delta_filter = VolumeDeltaFilter()
        self.atr_ratio_filter = ATRRatioFilter()
        self.spread_filter = SpreadFilter()
        self.micro_bos_filter = MicroBOSFilter()
        
        self.filter_results: List[FilterResult] = []
        self.pass_rate_metrics = PassRateMetrics()
        self.lock = threading.RLock()
    
    def validate_m1_filters(self, filter_data: M1FilterData) -> List[FilterResult]:
        """Validate M1 filters for given data"""
        results = []
        timestamp = time.time()
        
        # VWAP Filter
        vwap_passed, vwap_confidence, vwap_metadata = self.vwap_filter.process_tick(
            filter_data.symbol, filter_data.timestamp, filter_data.price, filter_data.volume
        )
        
        vwap_result = FilterResult(
            filter_id=f"vwap_{int(timestamp)}_{hashlib.md5(str(filter_data.timestamp).encode()).hexdigest()[:8]}",
            timestamp=timestamp,
            filter_type=FilterType.VWAP_RECLAIM,
            symbol=filter_data.symbol,
            status=FilterStatus.PASS if vwap_passed else FilterStatus.FAIL,
            confidence=vwap_confidence,
            pass_rate=1.0 if vwap_passed else 0.0,
            execution_time_ms=1.0,
            metadata=vwap_metadata
        )
        results.append(vwap_result)
        
        # Volume Delta Filter
        volume_delta_passed, volume_delta_confidence, volume_delta_metadata = self.volume_delta_filter.process_tick(
            filter_data.symbol, filter_data.timestamp, filter_data.price, 
            filter_data.volume, 1  # Assume bullish direction
        )
        
        volume_delta_result = FilterResult(
            filter_id=f"volume_delta_{int(timestamp)}_{hashlib.md5(str(filter_data.timestamp).encode()).hexdigest()[:8]}",
            timestamp=timestamp,
            filter_type=FilterType.VOLUME_DELTA_SPIKE,
            symbol=filter_data.symbol,
            status=FilterStatus.PASS if volume_delta_passed else FilterStatus.FAIL,
            confidence=volume_delta_confidence,
            pass_rate=1.0 if volume_delta_passed else 0.0,
            execution_time_ms=1.0,
            metadata=volume_delta_metadata
        )
        results.append(volume_delta_result)
        
        # ATR Ratio Filter
        atr_ratio_passed, atr_ratio_confidence, atr_ratio_metadata = self.atr_ratio_filter.process_tick(
            filter_data.symbol, filter_data.timestamp, filter_data.price, "M1"
        )
        
        atr_ratio_result = FilterResult(
            filter_id=f"atr_ratio_{int(timestamp)}_{hashlib.md5(str(filter_data.timestamp).encode()).hexdigest()[:8]}",
            timestamp=timestamp,
            filter_type=FilterType.ATR_RATIO,
            symbol=filter_data.symbol,
            status=FilterStatus.PASS if atr_ratio_passed else FilterStatus.FAIL,
            confidence=atr_ratio_confidence,
            pass_rate=1.0 if atr_ratio_passed else 0.0,
            execution_time_ms=1.0,
            metadata=atr_ratio_metadata
        )
        results.append(atr_ratio_result)
        
        # Spread Filter
        spread_passed, spread_confidence, spread_metadata = self.spread_filter.process_tick(
            filter_data.symbol, filter_data.timestamp, filter_data.spread, filter_data.news_impact
        )
        
        spread_result = FilterResult(
            filter_id=f"spread_{int(timestamp)}_{hashlib.md5(str(filter_data.timestamp).encode()).hexdigest()[:8]}",
            timestamp=timestamp,
            filter_type=FilterType.SPREAD_FILTER,
            symbol=filter_data.symbol,
            status=FilterStatus.PASS if spread_passed else FilterStatus.FAIL,
            confidence=spread_confidence,
            pass_rate=1.0 if spread_passed else 0.0,
            execution_time_ms=1.0,
            metadata=spread_metadata
        )
        results.append(spread_result)
        
        # Micro-BOS Filter
        micro_bos_passed, micro_bos_confidence, micro_bos_metadata = self.micro_bos_filter.process_tick(
            filter_data.symbol, filter_data.timestamp, filter_data.price, filter_data.atr_m1
        )
        
        micro_bos_result = FilterResult(
            filter_id=f"micro_bos_{int(timestamp)}_{hashlib.md5(str(filter_data.timestamp).encode()).hexdigest()[:8]}",
            timestamp=timestamp,
            filter_type=FilterType.MICRO_BOS,
            symbol=filter_data.symbol,
            status=FilterStatus.PASS if micro_bos_passed else FilterStatus.FAIL,
            confidence=micro_bos_confidence,
            pass_rate=1.0 if micro_bos_passed else 0.0,
            execution_time_ms=1.0,
            metadata=micro_bos_metadata
        )
        results.append(micro_bos_result)
        
        # Store results
        with self.lock:
            self.filter_results.extend(results)
            self._update_pass_rate_metrics()
        
        return results
    
    def _update_pass_rate_metrics(self) -> None:
        """Update pass rate metrics"""
        if not self.filter_results:
            return
        
        # Count results by status
        total_filters = len(self.filter_results)
        passed_filters = sum(1 for r in self.filter_results if r.status == FilterStatus.PASS)
        failed_filters = sum(1 for r in self.filter_results if r.status == FilterStatus.FAIL)
        pending_filters = sum(1 for r in self.filter_results if r.status == FilterStatus.PENDING)
        
        # Update overall metrics
        self.pass_rate_metrics.total_filters = total_filters
        self.pass_rate_metrics.passed_filters = passed_filters
        self.pass_rate_metrics.failed_filters = failed_filters
        self.pass_rate_metrics.pending_filters = pending_filters
        self.pass_rate_metrics.overall_pass_rate = passed_filters / total_filters if total_filters > 0 else 0.0
        
        # Calculate filter-specific pass rates
        filter_types = set(r.filter_type for r in self.filter_results)
        for filter_type in filter_types:
            type_results = [r for r in self.filter_results if r.filter_type == filter_type]
            if type_results:
                type_pass_rate = sum(1 for r in type_results if r.status == FilterStatus.PASS) / len(type_results)
                
                if filter_type == FilterType.VWAP_RECLAIM:
                    self.pass_rate_metrics.vwap_reclaim_rate = type_pass_rate
                elif filter_type == FilterType.VOLUME_DELTA_SPIKE:
                    self.pass_rate_metrics.volume_delta_rate = type_pass_rate
                elif filter_type == FilterType.ATR_RATIO:
                    self.pass_rate_metrics.atr_ratio_rate = type_pass_rate
                elif filter_type == FilterType.SPREAD_FILTER:
                    self.pass_rate_metrics.spread_filter_rate = type_pass_rate
                elif filter_type == FilterType.MICRO_BOS:
                    self.pass_rate_metrics.micro_bos_rate = type_pass_rate
                elif filter_type == FilterType.MICRO_CHOCH:
                    self.pass_rate_metrics.micro_choch_rate = type_pass_rate
        
        # Calculate symbol-specific pass rates
        symbols = set(r.symbol for r in self.filter_results)
        for symbol in symbols:
            symbol_results = [r for r in self.filter_results if r.symbol == symbol]
            if symbol_results:
                symbol_pass_rate = sum(1 for r in symbol_results if r.status == FilterStatus.PASS) / len(symbol_results)
                self.pass_rate_metrics.symbol_pass_rates[symbol] = symbol_pass_rate
    
    def get_pass_rate_report(self) -> Dict[str, Any]:
        """Get comprehensive pass rate report"""
        with self.lock:
            # Determine pass rate level
            overall_pass_rate = self.pass_rate_metrics.overall_pass_rate
            if overall_pass_rate >= 0.8:
                pass_rate_level = PassRateLevel.EXCELLENT
            elif overall_pass_rate >= 0.6:
                pass_rate_level = PassRateLevel.GOOD
            elif overall_pass_rate >= 0.4:
                pass_rate_level = PassRateLevel.FAIR
            else:
                pass_rate_level = PassRateLevel.POOR
            
            return {
                'overall_pass_rate': overall_pass_rate,
                'pass_rate_level': pass_rate_level.value,
                'total_filters': self.pass_rate_metrics.total_filters,
                'passed_filters': self.pass_rate_metrics.passed_filters,
                'failed_filters': self.pass_rate_metrics.failed_filters,
                'pending_filters': self.pass_rate_metrics.pending_filters,
                'vwap_reclaim_rate': self.pass_rate_metrics.vwap_reclaim_rate,
                'volume_delta_rate': self.pass_rate_metrics.volume_delta_rate,
                'atr_ratio_rate': self.pass_rate_metrics.atr_ratio_rate,
                'spread_filter_rate': self.pass_rate_metrics.spread_filter_rate,
                'micro_bos_rate': self.pass_rate_metrics.micro_bos_rate,
                'micro_choch_rate': self.pass_rate_metrics.micro_choch_rate,
                'symbol_pass_rates': self.pass_rate_metrics.symbol_pass_rates,
                'meets_60_percent_target': overall_pass_rate >= 0.6,
                'recommendations': self._generate_recommendations()
            }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on pass rate analysis"""
        recommendations = []
        
        overall_pass_rate = self.pass_rate_metrics.overall_pass_rate
        
        if overall_pass_rate < 0.6:
            recommendations.append("M1 filter pass rate below 60% target. Review filter parameters and thresholds.")
        
        if self.pass_rate_metrics.vwap_reclaim_rate < 0.5:
            recommendations.append("VWAP reclaim rate below 50%. Review VWAP calculation and session anchoring.")
        
        if self.pass_rate_metrics.volume_delta_rate < 0.5:
            recommendations.append("Volume delta rate below 50%. Review delta proxy calculation and spike detection.")
        
        if self.pass_rate_metrics.atr_ratio_rate < 0.5:
            recommendations.append("ATR ratio rate below 50%. Review ATR calculation and ratio thresholds.")
        
        if self.pass_rate_metrics.spread_filter_rate < 0.5:
            recommendations.append("Spread filter rate below 50%. Review spread analysis and news window detection.")
        
        if self.pass_rate_metrics.micro_bos_rate < 0.5:
            recommendations.append("Micro-BOS rate below 50%. Review micro-BOS detection algorithms.")
        
        return recommendations

# Global M1 filter validator
_m1_filter_validator: Optional[M1FilterValidator] = None

def get_m1_filter_validator() -> M1FilterValidator:
    """Get global M1 filter validator instance"""
    global _m1_filter_validator
    if _m1_filter_validator is None:
        _m1_filter_validator = M1FilterValidator()
    return _m1_filter_validator

def validate_m1_filters(filter_data: M1FilterData) -> List[FilterResult]:
    """Validate M1 filters"""
    validator = get_m1_filter_validator()
    return validator.validate_m1_filters(filter_data)

def get_pass_rate_report() -> Dict[str, Any]:
    """Get pass rate report"""
    validator = get_m1_filter_validator()
    return validator.get_pass_rate_report()

if __name__ == "__main__":
    # Example usage
    validator = get_m1_filter_validator()
    
    # Create sample filter data
    filter_data = M1FilterData(
        timestamp=time.time(),
        symbol="BTCUSDc",
        price=50000.0,
        volume=1000.0,
        spread=2.5,
        vwap=49950.0,
        atr_m1=100.0,
        atr_m5=200.0,
        delta_proxy=500.0,
        micro_bos_strength=0.8,
        micro_choch_strength=0.6,
        news_impact=0.0
    )
    
    # Validate filters
    results = validate_m1_filters(filter_data)
    
    # Get pass rate report
    report = get_pass_rate_report()
    
    print(f"M1 Filter Pass Rate Report:")
    print(f"Overall Pass Rate: {report['overall_pass_rate']:.2%}")
    print(f"Pass Rate Level: {report['pass_rate_level']}")
    print(f"Meets 60% Target: {report['meets_60_percent_target']}")
    print(f"Total Filters: {report['total_filters']}")
    print(f"Passed Filters: {report['passed_filters']}")
    
    if report['recommendations']:
        print("\nRecommendations:")
        for rec in report['recommendations']:
            print(f"- {rec}")
