"""
Comprehensive tests for structure detection accuracy validation system

Tests structure detection algorithms, validation accuracy measurement,
BOS/CHOCH detection, support/resistance analysis, and accuracy reporting.
"""

import pytest
import time
import json
import threading
import statistics
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional

from infra.structure_validation import (
    StructureValidationSystem, StructureDetector, StructureValidator,
    StructureType, ValidationStatus, AccuracyLevel,
    StructurePoint, StructureValidation, AccuracyMetrics,
    get_validation_system, analyze_structure_accuracy, get_validation_summary
)

class TestStructureType:
    """Test structure type enumeration"""
    
    def test_structure_types(self):
        """Test all structure types"""
        types = [
            StructureType.BOS,
            StructureType.CHOCH,
            StructureType.SUPPORT,
            StructureType.RESISTANCE,
            StructureType.TREND_LINE,
            StructureType.CHANNEL,
            StructureType.TRIANGLE,
            StructureType.FLAG,
            StructureType.PENNANT
        ]
        
        for structure_type in types:
            assert isinstance(structure_type, StructureType)
            assert structure_type.value in [
                "bos", "choch", "support", "resistance", "trend_line",
                "channel", "triangle", "flag", "pennant"
            ]

class TestValidationStatus:
    """Test validation status enumeration"""
    
    def test_validation_statuses(self):
        """Test all validation statuses"""
        statuses = [
            ValidationStatus.VALID,
            ValidationStatus.INVALID,
            ValidationStatus.PENDING,
            ValidationStatus.EXPIRED,
            ValidationStatus.CONFLICTED
        ]
        
        for status in statuses:
            assert isinstance(status, ValidationStatus)
            assert status.value in [
                "valid", "invalid", "pending", "expired", "conflicted"
            ]

class TestAccuracyLevel:
    """Test accuracy level enumeration"""
    
    def test_accuracy_levels(self):
        """Test all accuracy levels"""
        levels = [
            AccuracyLevel.EXCELLENT,
            AccuracyLevel.GOOD,
            AccuracyLevel.FAIR,
            AccuracyLevel.POOR
        ]
        
        for level in levels:
            assert isinstance(level, AccuracyLevel)
            assert level.value in ["excellent", "good", "fair", "poor"]

class TestStructurePoint:
    """Test structure point data structure"""
    
    def test_structure_point_creation(self):
        """Test structure point creation"""
        point = StructurePoint(
            timestamp=time.time(),
            price=50000.0,
            structure_type=StructureType.BOS,
            timeframe="H1",
            symbol="BTCUSDc",
            strength=0.8,
            confidence=0.85,
            metadata={"lookback_periods": 10, "volume": 1000.0}
        )
        
        assert point.timestamp > 0
        assert point.price == 50000.0
        assert point.structure_type == StructureType.BOS
        assert point.timeframe == "H1"
        assert point.symbol == "BTCUSDc"
        assert point.strength == 0.8
        assert point.confidence == 0.85
        assert point.metadata["lookback_periods"] == 10
    
    def test_structure_point_defaults(self):
        """Test structure point defaults"""
        point = StructurePoint(
            timestamp=time.time(),
            price=3000.0,
            structure_type=StructureType.SUPPORT,
            timeframe="M15",
            symbol="ETHUSDc",
            strength=0.6,
            confidence=0.7
        )
        
        assert point.metadata == {}

class TestStructureValidation:
    """Test structure validation data structure"""
    
    def test_structure_validation_creation(self):
        """Test structure validation creation"""
        validation = StructureValidation(
            structure_id="val_123",
            timestamp=time.time(),
            structure_type=StructureType.BOS,
            symbol="BTCUSDc",
            timeframe="H1",
            detected_price=50000.0,
            actual_price=50100.0,
            price_deviation=0.002,
            time_deviation=300.0,
            validation_status=ValidationStatus.VALID,
            accuracy_score=0.85,
            confidence=0.8,
            validation_time=1.5,
            metadata={"detected_strength": 0.8}
        )
        
        assert validation.structure_id == "val_123"
        assert validation.timestamp > 0
        assert validation.structure_type == StructureType.BOS
        assert validation.symbol == "BTCUSDc"
        assert validation.timeframe == "H1"
        assert validation.detected_price == 50000.0
        assert validation.actual_price == 50100.0
        assert validation.price_deviation == 0.002
        assert validation.time_deviation == 300.0
        assert validation.validation_status == ValidationStatus.VALID
        assert validation.accuracy_score == 0.85
        assert validation.confidence == 0.8
        assert validation.validation_time == 1.5
        assert validation.metadata["detected_strength"] == 0.8
    
    def test_structure_validation_defaults(self):
        """Test structure validation defaults"""
        validation = StructureValidation(
            structure_id="val_456",
            timestamp=time.time(),
            structure_type=StructureType.CHOCH,
            symbol="ETHUSDc",
            timeframe="M15",
            detected_price=3000.0,
            actual_price=3010.0,
            price_deviation=0.003,
            time_deviation=600.0,
            validation_status=ValidationStatus.PENDING,
            accuracy_score=0.7,
            confidence=0.75,
            validation_time=2.0
        )
        
        assert validation.metadata == {}

class TestAccuracyMetrics:
    """Test accuracy metrics data structure"""
    
    def test_accuracy_metrics_creation(self):
        """Test accuracy metrics creation"""
        metrics = AccuracyMetrics(
            total_structures=100,
            valid_structures=85,
            invalid_structures=10,
            pending_structures=5,
            overall_accuracy=0.85,
            price_accuracy=0.82,
            time_accuracy=0.88,
            confidence_accuracy=0.80
        )
        
        assert metrics.total_structures == 100
        assert metrics.valid_structures == 85
        assert metrics.invalid_structures == 10
        assert metrics.pending_structures == 5
        assert metrics.overall_accuracy == 0.85
        assert metrics.price_accuracy == 0.82
        assert metrics.time_accuracy == 0.88
        assert metrics.confidence_accuracy == 0.80
    
    def test_accuracy_metrics_defaults(self):
        """Test accuracy metrics defaults"""
        metrics = AccuracyMetrics()
        
        assert metrics.total_structures == 0
        assert metrics.valid_structures == 0
        assert metrics.invalid_structures == 0
        assert metrics.pending_structures == 0
        assert metrics.overall_accuracy == 0.0
        assert metrics.price_accuracy == 0.0
        assert metrics.time_accuracy == 0.0
        assert metrics.confidence_accuracy == 0.0
        assert metrics.structure_type_accuracy == {}
        assert metrics.timeframe_accuracy == {}
        assert metrics.symbol_accuracy == {}

class TestStructureDetector:
    """Test structure detector"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.detector = StructureDetector(lookback_periods=20)
    
    def test_detector_initialization(self):
        """Test detector initialization"""
        assert self.detector.lookback_periods == 20
        assert len(self.detector.price_data) == 0
        assert len(self.detector.structure_cache) == 0
        assert hasattr(self.detector, 'lock')
    
    def test_add_price_data(self):
        """Test adding price data"""
        self.detector.add_price_data(
            "BTCUSDc", "H1", time.time(), 50000.0, 50100.0, 49900.0, 50050.0, 1000.0
        )
        
        key = "BTCUSDc_H1"
        assert key in self.detector.price_data
        assert len(self.detector.price_data[key]) == 1
        
        data = self.detector.price_data[key][0]
        assert data['open'] == 50000.0
        assert data['high'] == 50100.0
        assert data['low'] == 49900.0
        assert data['close'] == 50050.0
        assert data['volume'] == 1000.0
    
    def test_detect_bos_empty_data(self):
        """Test BOS detection with empty data"""
        bos_structures = self.detector.detect_bos("BTCUSDc", "H1")
        assert len(bos_structures) == 0
    
    def test_detect_bos_with_data(self):
        """Test BOS detection with data"""
        # Add some price data
        base_time = time.time()
        for i in range(15):
            timestamp = base_time + i * 3600  # 1 hour intervals
            open_price = 50000.0 + i * 10
            high_price = open_price + 50
            low_price = open_price - 50
            close_price = open_price + 25
            volume = 1000.0 + i * 100
            
            self.detector.add_price_data(
                "BTCUSDc", "H1", timestamp, open_price, high_price, low_price, close_price, volume
            )
        
        bos_structures = self.detector.detect_bos("BTCUSDc", "H1", lookback=5)
        
        # Should detect some BOS patterns
        assert isinstance(bos_structures, list)
        for structure in bos_structures:
            assert isinstance(structure, StructurePoint)
            assert structure.structure_type == StructureType.BOS
            assert structure.symbol == "BTCUSDc"
            assert structure.timeframe == "H1"
            assert 0.0 <= structure.strength <= 1.0
            assert 0.0 <= structure.confidence <= 1.0
    
    def test_detect_choch_with_data(self):
        """Test CHOCH detection with data"""
        # Add price data with trend changes
        base_time = time.time()
        for i in range(15):
            timestamp = base_time + i * 3600
            # Create trend change pattern
            if i < 8:
                # Uptrend
                open_price = 50000.0 + i * 20
                close_price = open_price + 30
            else:
                # Downtrend
                open_price = 50000.0 + i * 20
                close_price = open_price - 30
            
            high_price = max(open_price, close_price) + 20
            low_price = min(open_price, close_price) - 20
            volume = 1000.0 + i * 100
            
            self.detector.add_price_data(
                "BTCUSDc", "H1", timestamp, open_price, high_price, low_price, close_price, volume
            )
        
        choch_structures = self.detector.detect_choch("BTCUSDc", "H1", lookback=5)
        
        assert isinstance(choch_structures, list)
        for structure in choch_structures:
            assert isinstance(structure, StructurePoint)
            assert structure.structure_type == StructureType.CHOCH
            assert structure.symbol == "BTCUSDc"
            assert structure.timeframe == "H1"
    
    def test_detect_support_resistance_with_data(self):
        """Test support/resistance detection with data"""
        # Add price data with pivot points
        base_time = time.time()
        for i in range(25):
            timestamp = base_time + i * 3600
            # Create pivot pattern
            if i == 10:  # Pivot high
                open_price = 50000.0
                high_price = 50200.0
                low_price = 49900.0
                close_price = 50050.0
            elif i == 15:  # Pivot low
                open_price = 50000.0
                high_price = 50100.0
                low_price = 49800.0
                close_price = 49950.0
            else:
                open_price = 50000.0 + i * 5
                high_price = open_price + 30
                low_price = open_price - 30
                close_price = open_price + 10
            
            volume = 1000.0 + i * 100
            
            self.detector.add_price_data(
                "BTCUSDc", "H1", timestamp, open_price, high_price, low_price, close_price, volume
            )
        
        levels = self.detector.detect_support_resistance("BTCUSDc", "H1", lookback=5)
        
        assert isinstance(levels, list)
        for level in levels:
            assert isinstance(level, StructurePoint)
            assert level.structure_type in [StructureType.SUPPORT, StructureType.RESISTANCE]
            assert level.symbol == "BTCUSDc"
            assert level.timeframe == "H1"
    
    def test_analyze_trend(self):
        """Test trend analysis"""
        # Test uptrend
        uptrend_bars = [
            {'close': 50000.0},
            {'close': 50050.0},
            {'close': 50100.0},
            {'close': 50150.0}
        ]
        trend = self.detector._analyze_trend(uptrend_bars)
        assert trend == 'uptrend'
        
        # Test downtrend
        downtrend_bars = [
            {'close': 50150.0},
            {'close': 50100.0},
            {'close': 50050.0},
            {'close': 50000.0}
        ]
        trend = self.detector._analyze_trend(downtrend_bars)
        assert trend == 'downtrend'
        
        # Test sideways
        sideways_bars = [
            {'close': 50000.0},
            {'close': 50010.0},
            {'close': 49990.0},
            {'close': 50005.0}
        ]
        trend = self.detector._analyze_trend(sideways_bars)
        assert trend == 'sideways'

class TestStructureValidator:
    """Test structure validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = StructureValidator(validation_window_hours=24)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.validation_window_hours == 24
        assert len(self.validator.validations) == 0
        assert isinstance(self.validator.accuracy_metrics, AccuracyMetrics)
        assert hasattr(self.validator, 'lock')
    
    def test_validate_structure_valid(self):
        """Test structure validation with valid result"""
        structure_point = StructurePoint(
            timestamp=time.time(),
            price=50000.0,
            structure_type=StructureType.BOS,
            timeframe="H1",
            symbol="BTCUSDc",
            strength=0.8,
            confidence=0.85
        )
        
        actual_price = 50050.0  # 0.1% deviation
        actual_timestamp = time.time() + 300  # 5 minutes later
        
        validation = self.validator.validate_structure(
            structure_point, actual_price, actual_timestamp
        )
        
        assert isinstance(validation, StructureValidation)
        assert validation.structure_type == StructureType.BOS
        assert validation.symbol == "BTCUSDc"
        assert validation.timeframe == "H1"
        assert validation.detected_price == 50000.0
        assert validation.actual_price == 50050.0
        assert validation.price_deviation > 0
        assert validation.time_deviation > 0
        assert validation.accuracy_score > 0
        assert validation.confidence == 0.85
        
        # Should be stored
        assert len(self.validator.validations) == 1
    
    def test_validate_structure_invalid(self):
        """Test structure validation with invalid result"""
        structure_point = StructurePoint(
            timestamp=time.time(),
            price=50000.0,
            structure_type=StructureType.BOS,
            timeframe="H1",
            symbol="BTCUSDc",
            strength=0.8,
            confidence=0.5  # Low confidence
        )
        
        actual_price = 53500.0  # 7% deviation (above 2x threshold)
        actual_timestamp = time.time() + 10800  # 3 hours later (above 2x threshold)
        
        validation = self.validator.validate_structure(
            structure_point, actual_price, actual_timestamp
        )
        
        assert validation.validation_status == ValidationStatus.INVALID
        assert validation.price_deviation > 0.06  # >6%
        assert validation.time_deviation >= 10800  # >=3 hours
    
    def test_get_accuracy_report(self):
        """Test getting accuracy report"""
        # Add some validations
        for i in range(10):
            structure_point = StructurePoint(
                timestamp=time.time(),
                price=50000.0 + i * 10,
                structure_type=StructureType.BOS,
                timeframe="H1",
                symbol="BTCUSDc",
                strength=0.8,
                confidence=0.85
            )
            
            actual_price = structure_point.price * 1.001  # 0.1% deviation
            actual_timestamp = structure_point.timestamp + 300
            
            self.validator.validate_structure(structure_point, actual_price, actual_timestamp)
        
        report = self.validator.get_accuracy_report()
        
        assert 'overall_accuracy' in report
        assert 'accuracy_level' in report
        assert 'total_structures' in report
        assert 'valid_structures' in report
        assert 'invalid_structures' in report
        assert 'pending_structures' in report
        assert 'price_accuracy' in report
        assert 'time_accuracy' in report
        assert 'confidence_accuracy' in report
        assert 'structure_type_accuracy' in report
        assert 'timeframe_accuracy' in report
        assert 'symbol_accuracy' in report
        assert 'meets_target' in report
        assert 'recommendations' in report
        
        assert report['total_structures'] == 10
        assert isinstance(report['recommendations'], list)
    
    def test_determine_validation_status(self):
        """Test validation status determination"""
        # Test valid status
        status = self.validator._determine_validation_status(0.01, 300, 0.8)
        assert status == ValidationStatus.VALID
        
        # Test pending status
        status = self.validator._determine_validation_status(0.03, 1800, 0.6)
        assert status == ValidationStatus.PENDING
        
        # Test invalid status
        status = self.validator._determine_validation_status(0.05, 7200, 0.5)
        assert status == ValidationStatus.INVALID
    
    def test_calculate_accuracy_score(self):
        """Test accuracy score calculation"""
        # Test high accuracy
        score = self.validator._calculate_accuracy_score(0.01, 300, 0.9)
        assert 0.0 <= score <= 1.0
        assert score > 0.8
        
        # Test low accuracy
        score = self.validator._calculate_accuracy_score(0.05, 7200, 0.3)
        assert 0.0 <= score <= 1.0
        assert score < 0.5

class TestStructureValidationSystem:
    """Test structure validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.system = StructureValidationSystem()
    
    def test_system_initialization(self):
        """Test system initialization"""
        assert isinstance(self.system.detector, StructureDetector)
        assert isinstance(self.system.validator, StructureValidator)
        assert hasattr(self.system, 'lock')
    
    def test_analyze_structure_accuracy(self):
        """Test structure accuracy analysis"""
        # Mock the detector methods to return some structures
        with patch.object(self.system.detector, 'detect_bos', return_value=[]), \
             patch.object(self.system.detector, 'detect_choch', return_value=[]), \
             patch.object(self.system.detector, 'detect_support_resistance', return_value=[]):
            
            report = self.system.analyze_structure_accuracy("BTCUSDc", "H1", lookback_hours=24)
            
            assert isinstance(report, dict)
            assert 'overall_accuracy' in report
            assert 'accuracy_level' in report
            assert 'total_structures' in report
            assert 'meets_target' in report
            assert 'recommendations' in report
    
    def test_get_validation_summary(self):
        """Test getting validation summary"""
        summary = self.system.get_validation_summary()
        
        assert 'total_validations' in summary
        assert 'accuracy_metrics' in summary
        assert 'meets_75_percent_target' in summary
        
        assert summary['total_validations'] == 0
        assert isinstance(summary['accuracy_metrics'], dict)
        assert isinstance(summary['meets_75_percent_target'], bool)

class TestGlobalFunctions:
    """Test global structure validation functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global system
        import infra.structure_validation
        infra.structure_validation._validation_system = None
    
    def test_get_validation_system(self):
        """Test global validation system access"""
        system1 = get_validation_system()
        system2 = get_validation_system()
        
        # Should return same instance
        assert system1 is system2
        assert isinstance(system1, StructureValidationSystem)
    
    def test_analyze_structure_accuracy_global(self):
        """Test global structure accuracy analysis"""
        with patch('infra.structure_validation.StructureValidationSystem.analyze_structure_accuracy') as mock_analyze:
            mock_analyze.return_value = {
                'overall_accuracy': 0.85,
                'accuracy_level': 'good',
                'total_structures': 50,
                'meets_target': True
            }
            
            report = analyze_structure_accuracy("BTCUSDc", "H1", lookback_hours=24)
            
            assert report['overall_accuracy'] == 0.85
            assert report['accuracy_level'] == 'good'
            assert report['total_structures'] == 50
            assert report['meets_target'] is True
    
    def test_get_validation_summary_global(self):
        """Test global validation summary"""
        with patch('infra.structure_validation.StructureValidationSystem.get_validation_summary') as mock_summary:
            mock_summary.return_value = {
                'total_validations': 100,
                'accuracy_metrics': {},
                'meets_75_percent_target': True
            }
            
            summary = get_validation_summary()
            
            assert summary['total_validations'] == 100
            assert summary['meets_75_percent_target'] is True

class TestStructureValidationIntegration:
    """Integration tests for structure validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global system
        import infra.structure_validation
        infra.structure_validation._validation_system = None
    
    def test_comprehensive_structure_analysis(self):
        """Test comprehensive structure analysis workflow"""
        system = get_validation_system()
        
        # Add price data
        base_time = time.time()
        for i in range(30):
            timestamp = base_time + i * 3600
            open_price = 50000.0 + i * 10
            high_price = open_price + 50
            low_price = open_price - 50
            close_price = open_price + 25
            volume = 1000.0 + i * 100
            
            system.detector.add_price_data(
                "BTCUSDc", "H1", timestamp, open_price, high_price, low_price, close_price, volume
            )
        
        # Analyze structure accuracy
        report = analyze_structure_accuracy("BTCUSDc", "H1", lookback_hours=24)
        
        assert isinstance(report, dict)
        assert 'overall_accuracy' in report
        assert 'accuracy_level' in report
        assert 'total_structures' in report
        assert 'meets_target' in report
        assert 'recommendations' in report
        
        # Check that accuracy is calculated
        assert 0.0 <= report['overall_accuracy'] <= 1.0
        assert report['accuracy_level'] in ['excellent', 'good', 'fair', 'poor']
        assert isinstance(report['meets_target'], bool)
        assert isinstance(report['recommendations'], list)
    
    def test_accuracy_target_validation(self):
        """Test accuracy target validation"""
        system = get_validation_system()
        
        # Create mock validations with high accuracy
        for i in range(20):
            structure_point = StructurePoint(
                timestamp=time.time(),
                price=50000.0 + i * 10,
                structure_type=StructureType.BOS,
                timeframe="H1",
                symbol="BTCUSDc",
                strength=0.8,
                confidence=0.85
            )
            
            # Small deviations for high accuracy
            actual_price = structure_point.price * 1.001  # 0.1% deviation
            actual_timestamp = structure_point.timestamp + 300  # 5 minutes
            
            system.validator.validate_structure(structure_point, actual_price, actual_timestamp)
        
        # Get accuracy report
        report = system.validator.get_accuracy_report()
        
        # Should meet 75% target
        assert report['overall_accuracy'] >= 0.75
        assert report['meets_target'] is True
        assert report['accuracy_level'] in ['excellent', 'good']
    
    def test_accuracy_recommendations(self):
        """Test accuracy recommendations generation"""
        system = get_validation_system()
        
        # Create mock validations with poor accuracy
        for i in range(10):
            structure_point = StructurePoint(
                timestamp=time.time(),
                price=50000.0 + i * 10,
                structure_type=StructureType.BOS,
                timeframe="H1",
                symbol="BTCUSDc",
                strength=0.3,  # Low strength
                confidence=0.4  # Low confidence
            )
            
            # Large deviations for poor accuracy
            actual_price = structure_point.price * 1.05  # 5% deviation
            actual_timestamp = structure_point.timestamp + 7200  # 2 hours
            
            system.validator.validate_structure(structure_point, actual_price, actual_timestamp)
        
        # Get accuracy report
        report = system.validator.get_accuracy_report()
        
        # Should not meet 75% target
        assert report['overall_accuracy'] < 0.75
        assert report['meets_target'] is False
        assert report['accuracy_level'] in ['fair', 'poor']
        assert len(report['recommendations']) > 0
        
        # Check recommendation content
        for rec in report['recommendations']:
            assert isinstance(rec, str)
            assert len(rec) > 0
    
    def test_structure_type_accuracy_breakdown(self):
        """Test structure type accuracy breakdown"""
        system = get_validation_system()
        
        # Create validations for different structure types
        structure_types = [StructureType.BOS, StructureType.CHOCH, StructureType.SUPPORT, StructureType.RESISTANCE]
        
        for structure_type in structure_types:
            for i in range(5):
                structure_point = StructurePoint(
                    timestamp=time.time(),
                    price=50000.0 + i * 10,
                    structure_type=structure_type,
                    timeframe="H1",
                    symbol="BTCUSDc",
                    strength=0.8,
                    confidence=0.85
                )
                
                actual_price = structure_point.price * 1.001
                actual_timestamp = structure_point.timestamp + 300
                
                system.validator.validate_structure(structure_point, actual_price, actual_timestamp)
        
        # Get accuracy report
        report = system.validator.get_accuracy_report()
        
        # Check structure type accuracy
        assert 'structure_type_accuracy' in report
        assert len(report['structure_type_accuracy']) > 0
        
        for structure_type, accuracy in report['structure_type_accuracy'].items():
            assert 0.0 <= accuracy <= 1.0
            assert structure_type in ['bos', 'choch', 'support', 'resistance']
    
    def test_timeframe_accuracy_breakdown(self):
        """Test timeframe accuracy breakdown"""
        system = get_validation_system()
        
        # Create validations for different timeframes
        timeframes = ['M15', 'H1', 'H4', 'D1']
        
        for timeframe in timeframes:
            for i in range(5):
                structure_point = StructurePoint(
                    timestamp=time.time(),
                    price=50000.0 + i * 10,
                    structure_type=StructureType.BOS,
                    timeframe=timeframe,
                    symbol="BTCUSDc",
                    strength=0.8,
                    confidence=0.85
                )
                
                actual_price = structure_point.price * 1.001
                actual_timestamp = structure_point.timestamp + 300
                
                system.validator.validate_structure(structure_point, actual_price, actual_timestamp)
        
        # Get accuracy report
        report = system.validator.get_accuracy_report()
        
        # Check timeframe accuracy
        assert 'timeframe_accuracy' in report
        assert len(report['timeframe_accuracy']) > 0
        
        for timeframe, accuracy in report['timeframe_accuracy'].items():
            assert 0.0 <= accuracy <= 1.0
            assert timeframe in ['M15', 'H1', 'H4', 'D1']
    
    def test_symbol_accuracy_breakdown(self):
        """Test symbol accuracy breakdown"""
        system = get_validation_system()
        
        # Create validations for different symbols
        symbols = ['BTCUSDc', 'ETHUSDc', 'XAUUSDc', 'EURUSDc']
        
        for symbol in symbols:
            for i in range(5):
                structure_point = StructurePoint(
                    timestamp=time.time(),
                    price=50000.0 + i * 10,
                    structure_type=StructureType.BOS,
                    timeframe="H1",
                    symbol=symbol,
                    strength=0.8,
                    confidence=0.85
                )
                
                actual_price = structure_point.price * 1.001
                actual_timestamp = structure_point.timestamp + 300
                
                system.validator.validate_structure(structure_point, actual_price, actual_timestamp)
        
        # Get accuracy report
        report = system.validator.get_accuracy_report()
        
        # Check symbol accuracy
        assert 'symbol_accuracy' in report
        assert len(report['symbol_accuracy']) > 0
        
        for symbol, accuracy in report['symbol_accuracy'].items():
            assert 0.0 <= accuracy <= 1.0
            assert symbol in ['BTCUSDc', 'ETHUSDc', 'XAUUSDc', 'EURUSDc']

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
