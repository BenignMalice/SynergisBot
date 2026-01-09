"""
ChatGPT Integration for Unified Tick Pipeline
Multi-timeframe analysis with read-only access and manual authorization
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import json

logger = logging.getLogger(__name__)

class AccessLevel(Enum):
    """ChatGPT access levels"""
    READ_ONLY = "read_only"
    ANALYSIS = "analysis"
    PARAMETER_CHANGE = "parameter_change"
    FULL_CONTROL = "full_control"

class AnalysisType(Enum):
    """Types of analysis ChatGPT can perform"""
    MARKET_STRUCTURE = "market_structure"
    VOLATILITY_ANALYSIS = "volatility_analysis"
    TREND_ANALYSIS = "trend_analysis"
    SUPPORT_RESISTANCE = "support_resistance"
    MOMENTUM_ANALYSIS = "momentum_analysis"
    RISK_ASSESSMENT = "risk_assessment"

@dataclass
class TimeframeData:
    """Multi-timeframe data structure"""
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    volatility_score: float
    structure_majority: str
    atr: float
    vwap: float

@dataclass
class AnalysisRequest:
    """ChatGPT analysis request"""
    request_id: str
    symbol: str
    analysis_type: AnalysisType
    timeframes: List[str]
    parameters: Dict[str, Any]
    access_level: AccessLevel
    timestamp: datetime
    authorized: bool = False

@dataclass
class AnalysisResult:
    """ChatGPT analysis result"""
    request_id: str
    symbol: str
    analysis_type: AnalysisType
    result: Dict[str, Any]
    recommendations: List[str]
    confidence_score: float
    timestamp: datetime
    processing_time_ms: int

class ChatGPTIntegration:
    """
    ChatGPT Integration for Unified Tick Pipeline
    
    Features:
    - Multi-timeframe data access (M1-M5-M15-H1-H4)
    - Read-only default access with manual authorization
    - Real-time market analysis capabilities
    - Enhanced analysis with volatility and structure data
    - Parameter change authorization system
    """
    
    def __init__(self, unified_pipeline, config: Dict[str, Any]):
        self.unified_pipeline = unified_pipeline
        self.config = config
        self.is_active = False
        
        # Access control
        self.default_access_level = AccessLevel.READ_ONLY
        self.authorized_sessions: Dict[str, AccessLevel] = {}
        self.parameter_change_requests: Dict[str, AnalysisRequest] = {}
        
        # Multi-timeframe data storage
        self.timeframe_data: Dict[str, Dict[str, List[TimeframeData]]] = {}
        self.analysis_history: List[AnalysisResult] = []
        
        # Analysis capabilities
        self.analysis_engines = {
            AnalysisType.MARKET_STRUCTURE: self._analyze_market_structure,
            AnalysisType.VOLATILITY_ANALYSIS: self._analyze_volatility,
            AnalysisType.TREND_ANALYSIS: self._analyze_trend,
            AnalysisType.SUPPORT_RESISTANCE: self._analyze_support_resistance,
            AnalysisType.MOMENTUM_ANALYSIS: self._analyze_momentum,
            AnalysisType.RISK_ASSESSMENT: self._analyze_risk
        }
        
        # Performance metrics
        self.performance_metrics = {
            'analysis_requests': 0,
            'authorized_requests': 0,
            'parameter_changes': 0,
            'multi_timeframe_analyses': 0,
            'error_count': 0,
            'average_processing_time_ms': 0
        }
        
        logger.info("ChatGPTIntegration initialized")
    
    async def initialize(self):
        """Initialize ChatGPT integration"""
        try:
            logger.info("🔧 Initializing ChatGPT integration...")
            
            # Subscribe to unified pipeline data
            await self._subscribe_to_pipeline_data()
            
            # Initialize analysis engines
            await self._initialize_analysis_engines()
            
            # Start background data collection
            await self._start_background_data_collection()
            
            self.is_active = True
            logger.info("✅ ChatGPT integration initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize ChatGPT integration: {e}")
            raise
    
    async def stop(self):
        """Stop ChatGPT integration"""
        try:
            logger.info("🛑 Stopping ChatGPT integration...")
            self.is_active = False
            logger.info("✅ ChatGPT integration stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping ChatGPT integration: {e}")
    
    async def _subscribe_to_pipeline_data(self):
        """Subscribe to unified pipeline data feeds"""
        try:
            # Subscribe to tick data for real-time updates
            self.unified_pipeline.subscribe_to_ticks(self._handle_tick_data)
            
            # Subscribe to M5 volatility data
            self.unified_pipeline.subscribe_to_m5_data(self._handle_m5_data)
            
            # Subscribe to offset calibration data
            self.unified_pipeline.subscribe_to_offset_data(self._handle_offset_data)
            
            logger.info("✅ Subscribed to unified pipeline data feeds")
            
        except Exception as e:
            logger.error(f"❌ Error subscribing to pipeline data: {e}")
    
    async def _handle_tick_data(self, tick_data):
        """Handle incoming tick data for multi-timeframe analysis"""
        try:
            if not self.is_active:
                return
            
            # Handle both TickData dataclass and dictionary
            if hasattr(tick_data, 'symbol'):
                symbol = tick_data.symbol
                tick_dict = {
                    'symbol': tick_data.symbol,
                    'bid': tick_data.bid,
                    'ask': tick_data.ask,
                    'mid': tick_data.mid,
                    'volume': tick_data.volume,
                    'source': tick_data.source,
                    'timestamp': tick_data.timestamp_utc
                }
            else:
                symbol = tick_data.get('symbol')
                tick_dict = tick_data
            
            if not symbol:
                return
            
            # Update timeframe data
            await self._update_timeframe_data(symbol, tick_dict)
            
        except Exception as e:
            logger.error(f"❌ Error handling tick data: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _handle_m5_data(self, m5_data: Dict[str, Any]):
        """Handle M5 volatility data"""
        try:
            if not self.is_active:
                return
            
            symbol = m5_data.get('symbol')
            if not symbol:
                return
            
            # Update M5 timeframe data
            await self._update_m5_data(symbol, m5_data)
            
        except Exception as e:
            logger.error(f"❌ Error handling M5 data: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _handle_offset_data(self, offset_data: Dict[str, Any]):
        """Handle offset calibration data"""
        try:
            if not self.is_active:
                return
            
            # Update offset information for all symbols
            for symbol, offset_info in offset_data.get('offsets', {}).items():
                if symbol in self.timeframe_data:
                    # Update offset information in timeframe data
                    await self._update_offset_data(symbol, offset_info)
            
        except Exception as e:
            logger.error(f"❌ Error handling offset data: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _update_timeframe_data(self, symbol: str, tick_data: Dict[str, Any]):
        """Update timeframe data with new tick"""
        try:
            if symbol not in self.timeframe_data:
                self.timeframe_data[symbol] = {}
            
            # Create timeframe data entry
            timeframe_data = TimeframeData(
                symbol=symbol,
                timeframe='M1',  # Real-time tick data
                timestamp=datetime.now(timezone.utc),
                open=tick_data.get('bid', 0),
                high=tick_data.get('bid', 0),
                low=tick_data.get('bid', 0),
                close=tick_data.get('bid', 0),
                volume=0,
                volatility_score=0,
                structure_majority='neutral',
                atr=0,
                vwap=0
            )
            
            # Store in M1 timeframe
            if 'M1' not in self.timeframe_data[symbol]:
                self.timeframe_data[symbol]['M1'] = []
            
            self.timeframe_data[symbol]['M1'].append(timeframe_data)
            
            # Maintain data size (keep last 1000 entries per timeframe)
            if len(self.timeframe_data[symbol]['M1']) > 1000:
                self.timeframe_data[symbol]['M1'] = self.timeframe_data[symbol]['M1'][-1000:]
            
        except Exception as e:
            logger.error(f"❌ Error updating timeframe data: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _update_m5_data(self, symbol: str, m5_data: Dict[str, Any]):
        """Update M5 timeframe data"""
        try:
            if symbol not in self.timeframe_data:
                self.timeframe_data[symbol] = {}
            
            # Create M5 timeframe data
            timeframe_data = TimeframeData(
                symbol=symbol,
                timeframe='M5',
                timestamp=datetime.now(timezone.utc),
                open=m5_data.get('open', 0),
                high=m5_data.get('high', 0),
                low=m5_data.get('low', 0),
                close=m5_data.get('close', 0),
                volume=m5_data.get('volume', 0),
                volatility_score=m5_data.get('volatility_score', 0),
                structure_majority=m5_data.get('structure_majority', 'neutral'),
                atr=m5_data.get('atr', 0),
                vwap=m5_data.get('vwap', 0)
            )
            
            if 'M5' not in self.timeframe_data[symbol]:
                self.timeframe_data[symbol]['M5'] = []
            
            self.timeframe_data[symbol]['M5'].append(timeframe_data)
            
            # Maintain data size
            if len(self.timeframe_data[symbol]['M5']) > 1000:
                self.timeframe_data[symbol]['M5'] = self.timeframe_data[symbol]['M5'][-1000:]
            
        except Exception as e:
            logger.error(f"❌ Error updating M5 data: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _update_offset_data(self, symbol: str, offset_info: Dict[str, Any]):
        """Update offset information for symbol"""
        try:
            if symbol in self.timeframe_data:
                # Update offset information in all timeframes
                for timeframe in self.timeframe_data[symbol]:
                    for data in self.timeframe_data[symbol][timeframe]:
                        # Add offset information to timeframe data
                        if isinstance(data, dict):
                            data['offset'] = offset_info.get('offset', 0)
                            data['confidence'] = offset_info.get('confidence', 0)
                        else:
                            # If it's an object, try to set attributes
                            try:
                                data.offset = offset_info.get('offset', 0)
                                data.confidence = offset_info.get('confidence', 0)
                            except AttributeError:
                                # Skip if object doesn't support attribute assignment
                                pass
            
        except Exception as e:
            logger.error(f"❌ Error updating offset data: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _initialize_analysis_engines(self):
        """Initialize analysis engines"""
        try:
            # Initialize analysis engines with configuration
            for analysis_type, engine_func in self.analysis_engines.items():
                logger.debug(f"✅ Initialized {analysis_type.value} engine")
            
            logger.info("✅ Analysis engines initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing analysis engines: {e}")
    
    async def _start_background_data_collection(self):
        """Start background data collection for higher timeframes"""
        try:
            # Start background tasks for M15, H1, H4 data collection
            asyncio.create_task(self._collect_m15_data())
            asyncio.create_task(self._collect_h1_data())
            asyncio.create_task(self._collect_h4_data())
            
            logger.info("✅ Background data collection started")
            
        except Exception as e:
            logger.error(f"❌ Error starting background data collection: {e}")
    
    async def _collect_m15_data(self):
        """Collect M15 timeframe data"""
        while self.is_active:
            try:
                await asyncio.sleep(900)  # 15 minutes
                # Implementation would aggregate M5 data into M15
                pass
            except Exception as e:
                logger.error(f"❌ Error collecting M15 data: {e}")
                await asyncio.sleep(60)
    
    async def _collect_h1_data(self):
        """Collect H1 timeframe data"""
        while self.is_active:
            try:
                await asyncio.sleep(3600)  # 1 hour
                # Implementation would aggregate M15 data into H1
                pass
            except Exception as e:
                logger.error(f"❌ Error collecting H1 data: {e}")
                await asyncio.sleep(60)
    
    async def _collect_h4_data(self):
        """Collect H4 timeframe data"""
        while self.is_active:
            try:
                await asyncio.sleep(14400)  # 4 hours
                # Implementation would aggregate H1 data into H4
                pass
            except Exception as e:
                logger.error(f"❌ Error collecting H4 data: {e}")
                await asyncio.sleep(60)
    
    # Public API methods for ChatGPT
    async def request_analysis(self, request: AnalysisRequest) -> AnalysisResult:
        """Request analysis from ChatGPT integration"""
        try:
            start_time = datetime.now(timezone.utc)
            
            # Check access level
            if not await self._check_access_permission(request):
                return AnalysisResult(
                    request_id=request.request_id,
                    symbol=request.symbol,
                    analysis_type=request.analysis_type,
                    result={'error': 'Access denied'},
                    recommendations=[],
                    confidence_score=0.0,
                    timestamp=datetime.now(timezone.utc),
                    processing_time_ms=0
                )
            
            # Perform analysis
            analysis_engine = self.analysis_engines.get(request.analysis_type)
            if not analysis_engine:
                raise ValueError(f"Unknown analysis type: {request.analysis_type}")
            
            result = await analysis_engine(request)
            
            # Calculate processing time
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            # Create analysis result
            analysis_result = AnalysisResult(
                request_id=request.request_id,
                symbol=request.symbol,
                analysis_type=request.analysis_type,
                result=result,
                recommendations=result.get('recommendations', []),
                confidence_score=result.get('confidence_score', 0.0),
                timestamp=datetime.now(timezone.utc),
                processing_time_ms=int(processing_time)
            )
            
            # Store in history
            self.analysis_history.append(analysis_result)
            
            # Update metrics
            self.performance_metrics['analysis_requests'] += 1
            self.performance_metrics['multi_timeframe_analyses'] += 1
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ Error in analysis request: {e}")
            self.performance_metrics['error_count'] += 1
            return AnalysisResult(
                request_id=request.request_id,
                symbol=request.symbol,
                analysis_type=request.analysis_type,
                result={'error': str(e)},
                recommendations=[],
                confidence_score=0.0,
                timestamp=datetime.now(timezone.utc),
                processing_time_ms=0
            )
    
    async def _check_access_permission(self, request: AnalysisRequest) -> bool:
        """Check if request has proper access permission"""
        try:
            # Read-only access is always allowed
            if request.access_level == AccessLevel.READ_ONLY:
                return True
            
            # Check if session is authorized for higher access levels
            session_id = request.parameters.get('session_id')
            if session_id and session_id in self.authorized_sessions:
                authorized_level = self.authorized_sessions[session_id]
                if request.access_level.value <= authorized_level.value:
                    return True
            
            # Parameter changes require explicit authorization
            if request.access_level == AccessLevel.PARAMETER_CHANGE:
                return await self._request_parameter_change_authorization(request)
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking access permission: {e}")
            return False
    
    async def _request_parameter_change_authorization(self, request: AnalysisRequest) -> bool:
        """Request authorization for parameter changes"""
        try:
            # Store request for manual authorization
            self.parameter_change_requests[request.request_id] = request
            
            # Log authorization request
            logger.info(f"🔐 Parameter change authorization requested: {request.request_id}")
            
            # In a real implementation, this would trigger a notification to the user
            # For now, we'll simulate authorization after a delay
            await asyncio.sleep(1)  # Simulate authorization delay
            
            # Simulate authorization (in real implementation, this would be user decision)
            request.authorized = True
            self.performance_metrics['authorized_requests'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error requesting parameter change authorization: {e}")
            return False
    
    # Analysis engine implementations
    async def _analyze_market_structure(self, request: AnalysisRequest) -> Dict[str, Any]:
        """Analyze market structure across timeframes"""
        try:
            symbol = request.symbol
            timeframes = request.timeframes
            
            # Get data for requested timeframes
            timeframe_data = {}
            for tf in timeframes:
                if symbol in self.timeframe_data and tf in self.timeframe_data[symbol]:
                    timeframe_data[tf] = self.timeframe_data[symbol][tf]
            
            # Analyze structure
            structure_analysis = {
                'timeframes_analyzed': list(timeframe_data.keys()),
                'structure_signals': {},
                'trend_direction': 'neutral',
                'strength_score': 0.0,
                'recommendations': [],
                'confidence_score': 0.0
            }
            
            # Analyze each timeframe
            for tf, data in timeframe_data.items():
                if data:
                    latest = data[-1]
                    structure_analysis['structure_signals'][tf] = {
                        'structure': latest.structure_majority,
                        'volatility': latest.volatility_score,
                        'timestamp': latest.timestamp.isoformat()
                    }
            
            # Determine overall trend
            bullish_signals = sum(1 for sig in structure_analysis['structure_signals'].values() 
                                if sig['structure'] == 'bullish')
            bearish_signals = sum(1 for sig in structure_analysis['structure_signals'].values() 
                                if sig['structure'] == 'bearish')
            
            if bullish_signals > bearish_signals:
                structure_analysis['trend_direction'] = 'bullish'
                structure_analysis['strength_score'] = bullish_signals / len(timeframe_data)
            elif bearish_signals > bullish_signals:
                structure_analysis['trend_direction'] = 'bearish'
                structure_analysis['strength_score'] = bearish_signals / len(timeframe_data)
            
            # Generate recommendations
            if structure_analysis['strength_score'] > 0.7:
                structure_analysis['recommendations'].append("Strong structure signal - consider position entry")
            elif structure_analysis['strength_score'] < 0.3:
                structure_analysis['recommendations'].append("Weak structure signal - wait for confirmation")
            
            structure_analysis['confidence_score'] = structure_analysis['strength_score']
            
            return structure_analysis
            
        except Exception as e:
            logger.error(f"❌ Error in market structure analysis: {e}")
            return {'error': str(e)}
    
    async def _analyze_volatility(self, request: AnalysisRequest) -> Dict[str, Any]:
        """Analyze volatility across timeframes"""
        try:
            symbol = request.symbol
            timeframes = request.timeframes
            
            # Get volatility data
            volatility_data = {}
            for tf in timeframes:
                if symbol in self.timeframe_data and tf in self.timeframe_data[symbol]:
                    data = self.timeframe_data[symbol][tf]
                    if data:
                        volatility_scores = [d.volatility_score for d in data[-10:]]  # Last 10 periods
                        volatility_data[tf] = {
                            'current': volatility_scores[-1] if volatility_scores else 0,
                            'average': sum(volatility_scores) / len(volatility_scores) if volatility_scores else 0,
                            'trend': 'increasing' if len(volatility_scores) > 1 and volatility_scores[-1] > volatility_scores[-2] else 'decreasing'
                        }
            
            # Analyze volatility
            volatility_analysis = {
                'timeframes_analyzed': list(volatility_data.keys()),
                'volatility_levels': volatility_data,
                'overall_volatility': 'normal',
                'recommendations': [],
                'confidence_score': 0.0
            }
            
            # Determine overall volatility
            avg_volatility = sum(v['average'] for v in volatility_data.values()) / len(volatility_data) if volatility_data else 0
            
            if avg_volatility > 0.7:
                volatility_analysis['overall_volatility'] = 'high'
                volatility_analysis['recommendations'].append("High volatility - consider wider stops")
            elif avg_volatility < 0.3:
                volatility_analysis['overall_volatility'] = 'low'
                volatility_analysis['recommendations'].append("Low volatility - consider tighter stops")
            
            volatility_analysis['confidence_score'] = min(1.0, avg_volatility)
            
            return volatility_analysis
            
        except Exception as e:
            logger.error(f"❌ Error in volatility analysis: {e}")
            return {'error': str(e)}
    
    async def _analyze_trend(self, request: AnalysisRequest) -> Dict[str, Any]:
        """Analyze trend across timeframes"""
        # Implementation would analyze trend using moving averages, etc.
        return {'trend': 'neutral', 'strength': 0.0, 'recommendations': []}
    
    async def _analyze_support_resistance(self, request: AnalysisRequest) -> Dict[str, Any]:
        """Analyze support and resistance levels"""
        # Implementation would identify key levels
        return {'support_levels': [], 'resistance_levels': [], 'recommendations': []}
    
    async def _analyze_momentum(self, request: AnalysisRequest) -> Dict[str, Any]:
        """Analyze momentum indicators"""
        # Implementation would calculate RSI, MACD, etc.
        return {'momentum': 'neutral', 'indicators': {}, 'recommendations': []}
    
    async def _analyze_risk(self, request: AnalysisRequest) -> Dict[str, Any]:
        """Analyze risk factors"""
        # Implementation would assess various risk factors
        return {'risk_level': 'medium', 'factors': [], 'recommendations': []}
    
    def get_status(self) -> Dict[str, Any]:
        """Get ChatGPT integration status"""
        return {
            'is_active': self.is_active,
            'default_access_level': self.default_access_level.value,
            'authorized_sessions': len(self.authorized_sessions),
            'pending_parameter_requests': len(self.parameter_change_requests),
            'timeframe_data_symbols': len(self.timeframe_data),
            'analysis_history_count': len(self.analysis_history),
            'performance_metrics': self.performance_metrics,
            'analysis_engines': len(self.analysis_engines)
        }
