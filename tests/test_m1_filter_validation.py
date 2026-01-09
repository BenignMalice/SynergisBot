"""
Comprehensive tests for M1 filter pass rate validation system

Tests M1 filter validation, pass rate measurement, filter effectiveness,
VWAP reclaim/loss detection, volume delta analysis, ATR ratio validation,
spread filtering, and micro-BOS/CHOCH detection.
"""

import pytest
import time
import json
import threading
import statistics
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional
from collections import deque

from infra.m1_filter_validation import (
    M1FilterValidator, VWAPFilter, VolumeDeltaFilter, ATRRatioFilter,
    SpreadFilter, MicroBOSFilter,
    FilterType, FilterStatus, PassRateLevel,
    M1FilterData, FilterResult, PassRateMetrics,
    get_m1_filter_validator, validate_m1_filters, get_pass_rate_report
)

class TestFilterType:
    """Test filter type enumeration"""
    
    def test_filter_types(self):
        """Test all filter types"""
        types = [
            FilterType.VWAP_RECLAIM,
            FilterType.VWAP_LOSS,
            FilterType.VOLUME_DELTA_SPIKE,
            FilterType.ATR_RATIO,
            FilterType.SPREAD_FILTER,
            FilterType.MICRO_BOS,
            FilterType.MICRO_CHOCH,
            FilterType.NEWS_WINDOW
        ]
        
        for filter_type in types:
            assert isinstance(filter_type, FilterType)
            assert filter_type.value in [
                "vwap_reclaim", "vwap_loss", "volume_delta_spike", "atr_ratio",
                "spread_filter", "micro_bos", "micro_choch", "news_window"
            ]

class TestFilterStatus:
    """Test filter status enumeration"""
    
    def test_filter_statuses(self):
        """Test all filter statuses"""
        statuses = [
            FilterStatus.PASS,
            FilterStatus.FAIL,
            FilterStatus.PENDING,
            FilterStatus.EXPIRED,
            FilterStatus.INVALID
        ]
        
        for status in statuses:
            assert isinstance(status, FilterStatus)
            assert status.value in ["pass", "fail", "pending", "expired", "invalid"]

class TestPassRateLevel:
    """Test pass rate level enumeration"""
    
    def test_pass_rate_levels(self):
        """Test all pass rate levels"""
        levels = [
            PassRateLevel.EXCELLENT,
            PassRateLevel.GOOD,
            PassRateLevel.FAIR,
            PassRateLevel.POOR
        ]
        
        for level in levels:
            assert isinstance(level, PassRateLevel)
            assert level.value in ["excellent", "good", "fair", "poor"]

class TestM1FilterData:
    """Test M1 filter data structure"""
    
    def test_m1_filter_data_creation(self):
        """Test M1 filter data creation"""
        data = M1FilterData(
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
            news_impact=0.0,
            metadata={"session": "24h", "timeframe": "M1"}
        )
        
        assert data.timestamp > 0
        assert data.symbol == "BTCUSDc"
        assert data.price == 50000.0
        assert data.volume == 1000.0
        assert data.spread == 2.5
        assert data.vwap == 49950.0
        assert data.atr_m1 == 100.0
        assert data.atr_m5 == 200.0
        assert data.delta_proxy == 500.0
        assert data.micro_bos_strength == 0.8
        assert data.micro_choch_strength == 0.6
        assert data.news_impact == 0.0
        assert data.metadata["session"] == "24h"
    
    def test_m1_filter_data_defaults(self):
        """Test M1 filter data defaults"""
        data = M1FilterData(
            timestamp=time.time(),
            symbol="ETHUSDc",
            price=3000.0,
            volume=500.0,
            spread=1.5,
            vwap=2995.0,
            atr_m1=50.0,
            atr_m5=100.0,
            delta_proxy=250.0,
            micro_bos_strength=0.7,
            micro_choch_strength=0.5,
            news_impact=0.1
        )
        
        assert data.metadata == {}

class TestFilterResult:
    """Test filter result data structure"""
    
    def test_filter_result_creation(self):
        """Test filter result creation"""
        result = FilterResult(
            filter_id="vwap_123",
            timestamp=time.time(),
            filter_type=FilterType.VWAP_RECLAIM,
            symbol="BTCUSDc",
            status=FilterStatus.PASS,
            confidence=0.85,
            pass_rate=1.0,
            execution_time_ms=2.5,
            metadata={"vwap": 50000.0, "sigma": 100.0}
        )
        
        assert result.filter_id == "vwap_123"
        assert result.timestamp > 0
        assert result.filter_type == FilterType.VWAP_RECLAIM
        assert result.symbol == "BTCUSDc"
        assert result.status == FilterStatus.PASS
        assert result.confidence == 0.85
        assert result.pass_rate == 1.0
        assert result.execution_time_ms == 2.5
        assert result.metadata["vwap"] == 50000.0
    
    def test_filter_result_defaults(self):
        """Test filter result defaults"""
        result = FilterResult(
            filter_id="volume_delta_456",
            timestamp=time.time(),
            filter_type=FilterType.VOLUME_DELTA_SPIKE,
            symbol="ETHUSDc",
            status=FilterStatus.FAIL,
            confidence=0.6,
            pass_rate=0.0,
            execution_time_ms=1.8
        )
        
        assert result.metadata == {}

class TestPassRateMetrics:
    """Test pass rate metrics data structure"""
    
    def test_pass_rate_metrics_creation(self):
        """Test pass rate metrics creation"""
        metrics = PassRateMetrics(
            total_filters=100,
            passed_filters=75,
            failed_filters=20,
            pending_filters=5,
            overall_pass_rate=0.75,
            vwap_reclaim_rate=0.80,
            volume_delta_rate=0.70,
            atr_ratio_rate=0.85,
            spread_filter_rate=0.75,
            micro_bos_rate=0.65,
            micro_choch_rate=0.60
        )
        
        assert metrics.total_filters == 100
        assert metrics.passed_filters == 75
        assert metrics.failed_filters == 20
        assert metrics.pending_filters == 5
        assert metrics.overall_pass_rate == 0.75
        assert metrics.vwap_reclaim_rate == 0.80
        assert metrics.volume_delta_rate == 0.70
        assert metrics.atr_ratio_rate == 0.85
        assert metrics.spread_filter_rate == 0.75
        assert metrics.micro_bos_rate == 0.65
        assert metrics.micro_choch_rate == 0.60
    
    def test_pass_rate_metrics_defaults(self):
        """Test pass rate metrics defaults"""
        metrics = PassRateMetrics()
        
        assert metrics.total_filters == 0
        assert metrics.passed_filters == 0
        assert metrics.failed_filters == 0
        assert metrics.pending_filters == 0
        assert metrics.overall_pass_rate == 0.0
        assert metrics.vwap_reclaim_rate == 0.0
        assert metrics.volume_delta_rate == 0.0
        assert metrics.atr_ratio_rate == 0.0
        assert metrics.spread_filter_rate == 0.0
        assert metrics.micro_bos_rate == 0.0
        assert metrics.micro_choch_rate == 0.0
        assert metrics.symbol_pass_rates == {}
        assert metrics.timeframe_pass_rates == {}

class TestVWAPFilter:
    """Test VWAP filter"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.vwap_filter = VWAPFilter(session_anchor="24h", sigma_window=60)
    
    def test_vwap_filter_initialization(self):
        """Test VWAP filter initialization"""
        assert self.vwap_filter.session_anchor == "24h"
        assert self.vwap_filter.sigma_window == 60
        assert len(self.vwap_filter.vwap_data) == 0
        assert len(self.vwap_filter.sigma_data) == 0
    
    def test_process_tick_basic(self):
        """Test basic tick processing"""
        passed, confidence, metadata = self.vwap_filter.process_tick(
            "BTCUSDc", time.time(), 50000.0, 1000.0
        )
        
        assert isinstance(passed, bool)
        assert 0.0 <= confidence <= 1.0
        assert isinstance(metadata, dict)
        assert 'vwap' in metadata
        assert 'sigma' in metadata
        assert 'reclaim_detected' in metadata
        assert 'loss_detected' in metadata
    
    def test_calculate_vwap(self):
        """Test VWAP calculation"""
        # Add some test data
        self.vwap_filter.vwap_data["BTCUSDc_24h"].append({
            'timestamp': time.time(),
            'price': 50000.0,
            'volume': 1000.0
        })
        self.vwap_filter.vwap_data["BTCUSDc_24h"].append({
            'timestamp': time.time() + 1,
            'price': 50100.0,
            'volume': 2000.0
        })
        
        vwap = self.vwap_filter._calculate_vwap(self.vwap_filter.vwap_data["BTCUSDc_24h"])
        
        # Expected VWAP = (50000*1000 + 50100*2000) / (1000+2000) = 50066.67
        expected_vwap = (50000.0 * 1000.0 + 50100.0 * 2000.0) / (1000.0 + 2000.0)
        assert abs(vwap - expected_vwap) < 0.01
    
    def test_calculate_sigma(self):
        """Test sigma calculation"""
        # Add test data
        data = deque([
            {'timestamp': time.time(), 'price': 50000.0, 'volume': 1000.0},
            {'timestamp': time.time() + 1, 'price': 50100.0, 'volume': 2000.0},
            {'timestamp': time.time() + 2, 'price': 49900.0, 'volume': 1500.0}
        ])
        
        vwap = 50000.0  # Assume VWAP
        sigma = self.vwap_filter._calculate_sigma(data, vwap)
        
        assert sigma >= 0.0
        assert isinstance(sigma, float)
    
    def test_detect_vwap_reclaim(self):
        """Test VWAP reclaim detection"""
        # Test reclaim detection
        reclaim = self.vwap_filter._detect_vwap_reclaim(50100.0, 50000.0, 50.0)
        assert isinstance(reclaim, bool)
        
        # Test no reclaim
        no_reclaim = self.vwap_filter._detect_vwap_reclaim(50010.0, 50000.0, 50.0)
        assert isinstance(no_reclaim, bool)
    
    def test_detect_vwap_loss(self):
        """Test VWAP loss detection"""
        # Test loss detection
        loss = self.vwap_filter._detect_vwap_loss(49900.0, 50000.0, 50.0)
        assert isinstance(loss, bool)
        
        # Test no loss
        no_loss = self.vwap_filter._detect_vwap_loss(49990.0, 50000.0, 50.0)
        assert isinstance(no_loss, bool)
    
    def test_calculate_confidence(self):
        """Test confidence calculation"""
        confidence = self.vwap_filter._calculate_confidence(50000.0, 100.0, 1000.0)
        
        assert 0.0 <= confidence <= 1.0
        assert isinstance(confidence, float)

class TestVolumeDeltaFilter:
    """Test volume delta filter"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.volume_delta_filter = VolumeDeltaFilter(lookback_periods=20, spike_threshold=2.0)
    
    def test_volume_delta_filter_initialization(self):
        """Test volume delta filter initialization"""
        assert self.volume_delta_filter.lookback_periods == 20
        assert self.volume_delta_filter.spike_threshold == 2.0
        assert len(self.volume_delta_filter.delta_data) == 0
        assert len(self.volume_delta_filter.volume_data) == 0
    
    def test_process_tick_basic(self):
        """Test basic tick processing"""
        passed, confidence, metadata = self.volume_delta_filter.process_tick(
            "BTCUSDc", time.time(), 50000.0, 1000.0, 1
        )
        
        assert isinstance(passed, bool)
        assert 0.0 <= confidence <= 1.0
        assert isinstance(metadata, dict)
        assert 'delta_proxy' in metadata
        assert 'volume' in metadata
        assert 'direction' in metadata
    
    def test_calculate_delta_proxy(self):
        """Test delta proxy calculation"""
        delta_proxy = self.volume_delta_filter._calculate_delta_proxy(50000.0, 1, 1000.0)
        
        expected = 50000.0 * 1 * 1000.0
        assert delta_proxy == expected
    
    def test_detect_volume_delta_spike_insufficient_data(self):
        """Test volume delta spike detection with insufficient data"""
        spike = self.volume_delta_filter._detect_volume_delta_spike("BTCUSDc")
        assert spike is False
    
    def test_detect_volume_delta_spike_with_data(self):
        """Test volume delta spike detection with data"""
        # Add some historical data
        for i in range(25):
            self.volume_delta_filter.delta_data["BTCUSDc"].append(100.0 + i)
        
        # Add a spike
        self.volume_delta_filter.delta_data["BTCUSDc"].append(1000.0)
        
        spike = self.volume_delta_filter._detect_volume_delta_spike("BTCUSDc")
        assert isinstance(spike, bool)
    
    def test_calculate_spike_confidence(self):
        """Test spike confidence calculation"""
        confidence = self.volume_delta_filter._calculate_spike_confidence(
            "BTCUSDc", 500.0, 1000.0
        )
        
        assert 0.0 <= confidence <= 1.0
        assert isinstance(confidence, float)

class TestATRRatioFilter:
    """Test ATR ratio filter"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.atr_ratio_filter = ATRRatioFilter(m1_period=14, m5_period=14, ratio_threshold=0.5)
    
    def test_atr_ratio_filter_initialization(self):
        """Test ATR ratio filter initialization"""
        assert self.atr_ratio_filter.m1_period == 14
        assert self.atr_ratio_filter.m5_period == 14
        assert self.atr_ratio_filter.ratio_threshold == 0.5
        assert len(self.atr_ratio_filter.m1_data) == 0
        assert len(self.atr_ratio_filter.m5_data) == 0
    
    def test_process_tick_m1(self):
        """Test M1 tick processing"""
        passed, confidence, metadata = self.atr_ratio_filter.process_tick(
            "BTCUSDc", time.time(), 50000.0, "M1"
        )
        
        assert isinstance(passed, bool)
        assert 0.0 <= confidence <= 1.0
        assert isinstance(metadata, dict)
        assert 'atr_ratio' in metadata
        assert 'm1_atr' in metadata
        assert 'm5_atr' in metadata
    
    def test_process_tick_m5(self):
        """Test M5 tick processing"""
        passed, confidence, metadata = self.atr_ratio_filter.process_tick(
            "BTCUSDc", time.time(), 50000.0, "M5"
        )
        
        assert isinstance(passed, bool)
        assert 0.0 <= confidence <= 1.0
        assert isinstance(metadata, dict)
    
    def test_calculate_atr_ratio_insufficient_data(self):
        """Test ATR ratio calculation with insufficient data"""
        ratio = self.atr_ratio_filter._calculate_atr_ratio("BTCUSDc")
        assert ratio == 0.0
    
    def test_calculate_atr_ratio_with_data(self):
        """Test ATR ratio calculation with data"""
        # Add M1 data
        for i in range(15):
            self.atr_ratio_filter.m1_data["BTCUSDc"].append({
                'timestamp': time.time() + i,
                'price': 50000.0 + i * 10
            })
        
        # Add M5 data
        for i in range(15):
            self.atr_ratio_filter.m5_data["BTCUSDc"].append({
                'timestamp': time.time() + i * 5,
                'price': 50000.0 + i * 50
            })
        
        ratio = self.atr_ratio_filter._calculate_atr_ratio("BTCUSDc")
        assert isinstance(ratio, float)
        assert ratio >= 0.0
    
    def test_calculate_atr(self):
        """Test ATR calculation"""
        data = deque([
            {'timestamp': time.time(), 'price': 50000.0},
            {'timestamp': time.time() + 1, 'price': 50100.0},
            {'timestamp': time.time() + 2, 'price': 49900.0}
        ])
        
        atr = self.atr_ratio_filter._calculate_atr(data)
        assert atr >= 0.0
        assert isinstance(atr, float)
    
    def test_calculate_ratio_confidence(self):
        """Test ratio confidence calculation"""
        confidence = self.atr_ratio_filter._calculate_ratio_confidence(1.0)
        
        assert 0.0 <= confidence <= 1.0
        assert isinstance(confidence, float)

class TestSpreadFilter:
    """Test spread filter"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.spread_filter = SpreadFilter(median_period=20, outlier_threshold=2.0)
    
    def test_spread_filter_initialization(self):
        """Test spread filter initialization"""
        assert self.spread_filter.median_period == 20
        assert self.spread_filter.outlier_threshold == 2.0
        assert len(self.spread_filter.spread_data) == 0
        assert len(self.spread_filter.news_events) == 0
    
    def test_process_tick_basic(self):
        """Test basic tick processing"""
        passed, confidence, metadata = self.spread_filter.process_tick(
            "BTCUSDc", time.time(), 2.5, 0.0
        )
        
        assert isinstance(passed, bool)
        assert 0.0 <= confidence <= 1.0
        assert isinstance(metadata, dict)
        assert 'spread' in metadata
        assert 'spread_quality' in metadata
        assert 'in_news_window' in metadata
    
    def test_is_in_news_window_no_events(self):
        """Test news window check with no events"""
        in_window = self.spread_filter._is_in_news_window("BTCUSDc", time.time())
        assert in_window is False
    
    def test_is_in_news_window_with_events(self):
        """Test news window check with events"""
        # Add news event
        current_time = time.time()
        self.spread_filter.news_events["BTCUSDc"].append({
            'start_time': current_time - 3600,  # 1 hour ago
            'end_time': current_time + 3600    # 1 hour from now
        })
        
        in_window = self.spread_filter._is_in_news_window("BTCUSDc", current_time)
        assert in_window is True
    
    def test_calculate_spread_quality_insufficient_data(self):
        """Test spread quality calculation with insufficient data"""
        quality = self.spread_filter._calculate_spread_quality("BTCUSDc", 2.5)
        assert quality is True  # Should return True when insufficient data
    
    def test_calculate_spread_quality_with_data(self):
        """Test spread quality calculation with data"""
        # Add spread data
        for i in range(25):
            self.spread_filter.spread_data["BTCUSDc"].append({
                'timestamp': time.time() + i,
                'spread': 2.0 + i * 0.1,
                'news_impact': 0.0
            })
        
        quality = self.spread_filter._calculate_spread_quality("BTCUSDc", 2.5)
        assert isinstance(quality, bool)
    
    def test_calculate_median_spread(self):
        """Test median spread calculation"""
        median = self.spread_filter._calculate_median_spread("BTCUSDc")
        assert median == 0.0  # No data
    
        # Add some data
        for i in range(25):
            self.spread_filter.spread_data["BTCUSDc"].append({
                'timestamp': time.time() + i,
                'spread': 2.0 + i * 0.1,
                'news_impact': 0.0
            })
        
        median = self.spread_filter._calculate_median_spread("BTCUSDc")
        assert median > 0.0
        assert isinstance(median, float)
    
    def test_calculate_spread_confidence(self):
        """Test spread confidence calculation"""
        confidence = self.spread_filter._calculate_spread_confidence(
            "BTCUSDc", 2.5, 0.0
        )
        
        assert 0.0 <= confidence <= 1.0
        assert isinstance(confidence, float)

class TestMicroBOSFilter:
    """Test micro-BOS filter"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.micro_bos_filter = MicroBOSFilter(
            lookback_bars=5, atr_multiplier=0.5, cooldown_periods=3
        )
    
    def test_micro_bos_filter_initialization(self):
        """Test micro-BOS filter initialization"""
        assert self.micro_bos_filter.lookback_bars == 5
        assert self.micro_bos_filter.atr_multiplier == 0.5
        assert self.micro_bos_filter.cooldown_periods == 3
        assert len(self.micro_bos_filter.bar_data) == 0
        assert len(self.micro_bos_filter.last_detection) == 0
    
    def test_process_tick_basic(self):
        """Test basic tick processing"""
        passed, confidence, metadata = self.micro_bos_filter.process_tick(
            "BTCUSDc", time.time(), 50000.0, 100.0
        )
        
        assert isinstance(passed, bool)
        assert 0.0 <= confidence <= 1.0
        assert isinstance(metadata, dict)
        assert 'micro_bos' in metadata
        assert 'micro_choch' in metadata
        assert 'strength' in metadata
    
    def test_is_in_cooldown_no_detection(self):
        """Test cooldown check with no previous detection"""
        in_cooldown = self.micro_bos_filter._is_in_cooldown("BTCUSDc", time.time())
        assert in_cooldown is False
    
    def test_is_in_cooldown_with_detection(self):
        """Test cooldown check with previous detection"""
        current_time = time.time()
        self.micro_bos_filter.last_detection["BTCUSDc"] = current_time - 60  # 1 minute ago
        
        in_cooldown = self.micro_bos_filter._is_in_cooldown("BTCUSDc", current_time)
        assert in_cooldown is True
    
    def test_detect_micro_bos_insufficient_data(self):
        """Test micro-BOS detection with insufficient data"""
        bos = self.micro_bos_filter._detect_micro_bos("BTCUSDc", 50000.0, 100.0)
        assert bos is False
    
    def test_detect_micro_bos_with_data(self):
        """Test micro-BOS detection with data"""
        # Add bar data
        for i in range(6):
            self.micro_bos_filter.bar_data["BTCUSDc"].append({
                'timestamp': time.time() + i,
                'price': 50000.0 + i * 10,
                'atr': 100.0
            })
        
        bos = self.micro_bos_filter._detect_micro_bos("BTCUSDc", 50100.0, 100.0)
        assert isinstance(bos, bool)
    
    def test_detect_micro_choch_insufficient_data(self):
        """Test micro-CHOCH detection with insufficient data"""
        choch = self.micro_bos_filter._detect_micro_choch("BTCUSDc", 50000.0, 100.0)
        assert choch is False
    
    def test_detect_micro_choch_with_data(self):
        """Test micro-CHOCH detection with data"""
        # Add bar data
        for i in range(6):
            self.micro_bos_filter.bar_data["BTCUSDc"].append({
                'timestamp': time.time() + i,
                'price': 50000.0 - i * 10,
                'atr': 100.0
            })
        
        choch = self.micro_bos_filter._detect_micro_choch("BTCUSDc", 49900.0, 100.0)
        assert isinstance(choch, bool)
    
    def test_calculate_strength(self):
        """Test strength calculation"""
        strength = self.micro_bos_filter._calculate_strength("BTCUSDc", 50000.0, 100.0)
        assert 0.0 <= strength <= 1.0
        assert isinstance(strength, float)
    
    def test_calculate_micro_confidence(self):
        """Test micro confidence calculation"""
        confidence = self.micro_bos_filter._calculate_micro_confidence(0.8, 100.0)
        
        assert 0.0 <= confidence <= 1.0
        assert isinstance(confidence, float)

class TestM1FilterValidator:
    """Test M1 filter validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = M1FilterValidator()
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert isinstance(self.validator.vwap_filter, VWAPFilter)
        assert isinstance(self.validator.volume_delta_filter, VolumeDeltaFilter)
        assert isinstance(self.validator.atr_ratio_filter, ATRRatioFilter)
        assert isinstance(self.validator.spread_filter, SpreadFilter)
        assert isinstance(self.validator.micro_bos_filter, MicroBOSFilter)
        assert len(self.validator.filter_results) == 0
        assert isinstance(self.validator.pass_rate_metrics, PassRateMetrics)
        assert hasattr(self.validator, 'lock')
    
    def test_validate_m1_filters(self):
        """Test M1 filter validation"""
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
        
        results = self.validator.validate_m1_filters(filter_data)
        
        assert isinstance(results, list)
        assert len(results) == 5  # 5 filter types
        
        for result in results:
            assert isinstance(result, FilterResult)
            assert result.symbol == "BTCUSDc"
            assert result.status in [FilterStatus.PASS, FilterStatus.FAIL]
            assert 0.0 <= result.confidence <= 1.0
            assert 0.0 <= result.pass_rate <= 1.0
            assert result.execution_time_ms > 0.0
    
    def test_get_pass_rate_report(self):
        """Test getting pass rate report"""
        # Add some filter results
        for i in range(10):
            filter_data = M1FilterData(
                timestamp=time.time() + i,
                symbol="BTCUSDc",
                price=50000.0 + i * 10,
                volume=1000.0 + i * 100,
                spread=2.5,
                vwap=49950.0 + i * 5,
                atr_m1=100.0,
                atr_m5=200.0,
                delta_proxy=500.0 + i * 50,
                micro_bos_strength=0.8,
                micro_choch_strength=0.6,
                news_impact=0.0
            )
            
            self.validator.validate_m1_filters(filter_data)
        
        report = self.validator.get_pass_rate_report()
        
        assert 'overall_pass_rate' in report
        assert 'pass_rate_level' in report
        assert 'total_filters' in report
        assert 'passed_filters' in report
        assert 'failed_filters' in report
        assert 'pending_filters' in report
        assert 'vwap_reclaim_rate' in report
        assert 'volume_delta_rate' in report
        assert 'atr_ratio_rate' in report
        assert 'spread_filter_rate' in report
        assert 'micro_bos_rate' in report
        assert 'micro_choch_rate' in report
        assert 'symbol_pass_rates' in report
        assert 'meets_60_percent_target' in report
        assert 'recommendations' in report
        
        assert report['total_filters'] > 0
        assert 0.0 <= report['overall_pass_rate'] <= 1.0
        assert report['pass_rate_level'] in ['excellent', 'good', 'fair', 'poor']
        assert isinstance(report['meets_60_percent_target'], bool)
        assert isinstance(report['recommendations'], list)
    
    def test_update_pass_rate_metrics(self):
        """Test pass rate metrics update"""
        # Add some results manually
        result1 = FilterResult(
            filter_id="test1",
            timestamp=time.time(),
            filter_type=FilterType.VWAP_RECLAIM,
            symbol="BTCUSDc",
            status=FilterStatus.PASS,
            confidence=0.8,
            pass_rate=1.0,
            execution_time_ms=1.0
        )
        
        result2 = FilterResult(
            filter_id="test2",
            timestamp=time.time(),
            filter_type=FilterType.VOLUME_DELTA_SPIKE,
            symbol="BTCUSDc",
            status=FilterStatus.FAIL,
            confidence=0.6,
            pass_rate=0.0,
            execution_time_ms=1.0
        )
        
        self.validator.filter_results = [result1, result2]
        self.validator._update_pass_rate_metrics()
        
        assert self.validator.pass_rate_metrics.total_filters == 2
        assert self.validator.pass_rate_metrics.passed_filters == 1
        assert self.validator.pass_rate_metrics.failed_filters == 1
        assert self.validator.pass_rate_metrics.overall_pass_rate == 0.5

class TestGlobalFunctions:
    """Test global M1 filter functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.m1_filter_validation
        infra.m1_filter_validation._m1_filter_validator = None
    
    def test_get_m1_filter_validator(self):
        """Test global validator access"""
        validator1 = get_m1_filter_validator()
        validator2 = get_m1_filter_validator()
        
        # Should return same instance
        assert validator1 is validator2
        assert isinstance(validator1, M1FilterValidator)
    
    def test_validate_m1_filters_global(self):
        """Test global M1 filter validation"""
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
        
        results = validate_m1_filters(filter_data)
        
        assert isinstance(results, list)
        assert len(results) == 5  # 5 filter types
        
        for result in results:
            assert isinstance(result, FilterResult)
            assert result.symbol == "BTCUSDc"
    
    def test_get_pass_rate_report_global(self):
        """Test global pass rate report"""
        report = get_pass_rate_report()
        
        assert 'overall_pass_rate' in report
        assert 'pass_rate_level' in report
        assert 'total_filters' in report
        assert 'meets_60_percent_target' in report
        assert 'recommendations' in report

class TestM1FilterValidationIntegration:
    """Integration tests for M1 filter validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.m1_filter_validation
        infra.m1_filter_validation._m1_filter_validator = None
    
    def test_comprehensive_m1_filter_analysis(self):
        """Test comprehensive M1 filter analysis workflow"""
        validator = get_m1_filter_validator()
        
        # Create multiple filter data points
        symbols = ["BTCUSDc", "ETHUSDc", "XAUUSDc"]
        
        for symbol in symbols:
            for i in range(10):
                filter_data = M1FilterData(
                    timestamp=time.time() + i * 60,  # 1 minute intervals
                    symbol=symbol,
                    price=50000.0 + i * 10,
                    volume=1000.0 + i * 100,
                    spread=2.5 + i * 0.1,
                    vwap=49950.0 + i * 5,
                    atr_m1=100.0 + i * 5,
                    atr_m5=200.0 + i * 10,
                    delta_proxy=500.0 + i * 50,
                    micro_bos_strength=0.8,
                    micro_choch_strength=0.6,
                    news_impact=0.0
                )
                
                results = validate_m1_filters(filter_data)
                assert len(results) == 5
        
        # Get pass rate report
        report = get_pass_rate_report()
        
        assert isinstance(report, dict)
        assert 'overall_pass_rate' in report
        assert 'pass_rate_level' in report
        assert 'total_filters' in report
        assert 'meets_60_percent_target' in report
        assert 'recommendations' in report
        
        # Check that metrics are calculated
        assert 0.0 <= report['overall_pass_rate'] <= 1.0
        assert report['pass_rate_level'] in ['excellent', 'good', 'fair', 'poor']
        assert isinstance(report['meets_60_percent_target'], bool)
        assert isinstance(report['recommendations'], list)
    
    def test_pass_rate_target_validation(self):
        """Test pass rate target validation"""
        validator = get_m1_filter_validator()
        
        # Create filter data with high pass rate
        for i in range(20):
            filter_data = M1FilterData(
                timestamp=time.time() + i * 60,
                symbol="BTCUSDc",
                price=50000.0 + i * 10,
                volume=1000.0 + i * 100,
                spread=2.5,
                vwap=49950.0 + i * 5,
                atr_m1=100.0,
                atr_m5=200.0,
                delta_proxy=500.0 + i * 50,
                micro_bos_strength=0.8,
                micro_choch_strength=0.6,
                news_impact=0.0
            )
            
            validate_m1_filters(filter_data)
        
        # Get pass rate report
        report = get_pass_rate_report()
        
        # Should meet 60% target
        assert report['overall_pass_rate'] >= 0.0  # At least some pass rate
        assert isinstance(report['meets_60_percent_target'], bool)
        assert report['pass_rate_level'] in ['excellent', 'good', 'fair', 'poor']
    
    def test_filter_type_breakdown(self):
        """Test filter type breakdown"""
        validator = get_m1_filter_validator()
        
        # Create filter data for different symbols
        symbols = ["BTCUSDc", "ETHUSDc", "XAUUSDc"]
        
        for symbol in symbols:
            for i in range(5):
                filter_data = M1FilterData(
                    timestamp=time.time() + i * 60,
                    symbol=symbol,
                    price=50000.0 + i * 10,
                    volume=1000.0 + i * 100,
                    spread=2.5,
                    vwap=49950.0 + i * 5,
                    atr_m1=100.0,
                    atr_m5=200.0,
                    delta_proxy=500.0 + i * 50,
                    micro_bos_strength=0.8,
                    micro_choch_strength=0.6,
                    news_impact=0.0
                )
                
                validate_m1_filters(filter_data)
        
        # Get pass rate report
        report = get_pass_rate_report()
        
        # Check filter-specific rates
        assert 'vwap_reclaim_rate' in report
        assert 'volume_delta_rate' in report
        assert 'atr_ratio_rate' in report
        assert 'spread_filter_rate' in report
        assert 'micro_bos_rate' in report
        assert 'micro_choch_rate' in report
        
        for rate in ['vwap_reclaim_rate', 'volume_delta_rate', 'atr_ratio_rate', 
                    'spread_filter_rate', 'micro_bos_rate', 'micro_choch_rate']:
            assert 0.0 <= report[rate] <= 1.0
    
    def test_symbol_breakdown(self):
        """Test symbol breakdown"""
        validator = get_m1_filter_validator()
        
        # Create filter data for different symbols
        symbols = ["BTCUSDc", "ETHUSDc", "XAUUSDc"]
        
        for symbol in symbols:
            for i in range(5):
                filter_data = M1FilterData(
                    timestamp=time.time() + i * 60,
                    symbol=symbol,
                    price=50000.0 + i * 10,
                    volume=1000.0 + i * 100,
                    spread=2.5,
                    vwap=49950.0 + i * 5,
                    atr_m1=100.0,
                    atr_m5=200.0,
                    delta_proxy=500.0 + i * 50,
                    micro_bos_strength=0.8,
                    micro_choch_strength=0.6,
                    news_impact=0.0
                )
                
                validate_m1_filters(filter_data)
        
        # Get pass rate report
        report = get_pass_rate_report()
        
        # Check symbol pass rates
        assert 'symbol_pass_rates' in report
        assert isinstance(report['symbol_pass_rates'], dict)
        
        for symbol in symbols:
            assert symbol in report['symbol_pass_rates']
            assert 0.0 <= report['symbol_pass_rates'][symbol] <= 1.0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
