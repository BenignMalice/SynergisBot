"""
M5 Volatility Bridge
Hybrid aggregation system for volatility monitoring and price reconciliation
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import statistics
import math

logger = logging.getLogger(__name__)

@dataclass
class M5Candle:
    """M5 candle data structure"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str  # 'binance' or 'mt5'
    fused_close: Optional[float] = None
    volatility_score: float = 0.0
    structure_majority: str = 'neutral'  # 'bullish', 'bearish', 'neutral'

@dataclass
class VolatilityConfig:
    """Volatility bridge configuration"""
    high_vol_threshold: float  # Threshold for high volatility detection
    structure_weight: float    # Weight for structure in majority decision
    volume_weight: float       # Weight for volume in volatility calculation
    price_weight: float       # Weight for price action in volatility calculation
    fusion_window: int        # Time window for price fusion (seconds)
    volatility_periods: int   # Number of periods for volatility calculation

class M5VolatilityBridge:
    """
    M5 Volatility Bridge with hybrid aggregation
    
    Features:
    - Hybrid aggregation (Binance for high-vol, MT5 for FX)
    - Fused close calculation for price reconciliation
    - Structure majority decision logic
    - Real-time volatility monitoring and gating
    - Volatility-based asset classification
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = VolatilityConfig(**config)
        self.is_active = False
        
        # M5 candle storage
        self.m5_candles: Dict[str, List[M5Candle]] = {}
        self.fused_candles: Dict[str, List[M5Candle]] = {}
        
        # Volatility tracking
        self.volatility_scores: Dict[str, float] = {}
        self.volatility_history: Dict[str, List[Tuple[datetime, float]]] = {}
        
        # Asset classification
        self.asset_classification: Dict[str, str] = {}  # 'high_vol', 'fx', 'crypto'
        
        # Performance metrics
        self.performance_metrics = {
            'candles_processed': 0,
            'fusions_performed': 0,
            'volatility_calculations': 0,
            'structure_decisions': 0,
            'error_count': 0
        }
        
        logger.info("M5VolatilityBridge initialized")
    
    async def initialize(self):
        """Initialize M5 volatility bridge"""
        try:
            logger.info("🔧 Initializing M5 volatility bridge...")
            
            # Initialize for all symbols
            symbols = ['BTCUSDT', 'XAUUSDT', 'ETHUSDT', 'EURUSDc', 'GBPUSDc', 'USDJPYc']
            for symbol in symbols:
                self.m5_candles[symbol] = []
                self.fused_candles[symbol] = []
                self.volatility_scores[symbol] = 0.0
                self.volatility_history[symbol] = []
                
                # Classify assets
                if symbol.endswith('c'):
                    self.asset_classification[symbol] = 'fx'
                elif symbol in ['BTCUSDT', 'ETHUSDT']:
                    self.asset_classification[symbol] = 'crypto'
                else:
                    self.asset_classification[symbol] = 'high_vol'
            
            self.is_active = True
            logger.info("✅ M5 volatility bridge initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize M5 volatility bridge: {e}")
            raise
    
    async def stop(self):
        """Stop M5 volatility bridge"""
        try:
            logger.info("🛑 Stopping M5 volatility bridge...")
            self.is_active = False
            logger.info("✅ M5 volatility bridge stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping M5 volatility bridge: {e}")
    
    async def add_m5_candle(self, symbol: str, timestamp: datetime, open_price: float, 
                     high: float, low: float, close: float, volume: float, source: str):
        """Add M5 candle data"""
        try:
            if not self.is_active:
                return
            
            # Create M5 candle
            candle = M5Candle(
                symbol=symbol,
                timestamp=timestamp,
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                source=source
            )
            
            # Calculate volatility score
            candle.volatility_score = await self._calculate_volatility_score(candle)
            
            # Determine structure majority
            candle.structure_majority = await self._determine_structure_majority(candle)
            
            # Add to storage
            if symbol in self.m5_candles:
                self.m5_candles[symbol].append(candle)
                
                # Maintain storage size (keep last 1000 candles)
                if len(self.m5_candles[symbol]) > 1000:
                    self.m5_candles[symbol] = self.m5_candles[symbol][-1000:]
            
            # Update volatility tracking
            self.volatility_scores[symbol] = candle.volatility_score
            self.volatility_history[symbol].append((timestamp, candle.volatility_score))
            
            # Keep only recent history (last 24 hours)
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            self.volatility_history[symbol] = [
                (ts, score) for ts, score in self.volatility_history[symbol]
                if ts >= cutoff_time
            ]
            
            self.performance_metrics['candles_processed'] += 1
            
            # Perform fusion if needed
            await self._perform_fusion(symbol)
            
        except Exception as e:
            logger.error(f"❌ Error adding M5 candle: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _calculate_volatility_score(self, candle: M5Candle) -> float:
        """Calculate volatility score for M5 candle"""
        try:
            # Price range volatility
            price_range = candle.high - candle.low
            price_volatility = price_range / candle.close if candle.close > 0 else 0
            
            # Volume volatility (normalized)
            volume_volatility = min(1.0, candle.volume / 1000)  # Normalize volume
            
            # Time-based volatility (higher for recent candles)
            time_factor = 1.0  # Could be enhanced with time-based weighting
            
            # Combined volatility score
            volatility_score = (
                price_volatility * self.config.price_weight +
                volume_volatility * self.config.volume_weight
            ) * time_factor
            
            return min(1.0, volatility_score)  # Cap at 1.0
            
        except Exception as e:
            logger.error(f"❌ Error calculating volatility score: {e}")
            return 0.0
    
    async def _determine_structure_majority(self, candle: M5Candle) -> str:
        """Determine structure majority (bullish, bearish, neutral)"""
        try:
            # Simple structure analysis based on price action
            if candle.close > candle.open:
                if candle.high > candle.low * 1.01:  # Strong bullish
                    return 'bullish'
                else:
                    return 'neutral'
            elif candle.close < candle.open:
                if candle.low < candle.high * 0.99:  # Strong bearish
                    return 'bearish'
                else:
                    return 'neutral'
            else:
                return 'neutral'
                
        except Exception as e:
            logger.error(f"❌ Error determining structure majority: {e}")
            return 'neutral'
    
    async def _perform_fusion(self, symbol: str):
        """Perform price fusion for M5 candles"""
        try:
            if symbol not in self.m5_candles:
                return
            
            candles = self.m5_candles[symbol]
            if len(candles) < 2:
                return
            
            # Get recent candles from both sources
            recent_candles = candles[-10:]  # Last 10 candles
            
            # Group by timestamp (5-minute intervals)
            timestamp_groups = {}
            for candle in recent_candles:
                # Round to 5-minute intervals
                rounded_time = candle.timestamp.replace(
                    minute=(candle.timestamp.minute // 5) * 5,
                    second=0,
                    microsecond=0
                )
                
                if rounded_time not in timestamp_groups:
                    timestamp_groups[rounded_time] = []
                timestamp_groups[rounded_time].append(candle)
            
            # Perform fusion for each timestamp group
            for timestamp, group_candles in timestamp_groups.items():
                if len(group_candles) >= 2:  # Need at least 2 sources
                    fused_candle = await self._fuse_candles(symbol, timestamp, group_candles)
                    if fused_candle:
                        # Add to fused candles
                        if symbol not in self.fused_candles:
                            self.fused_candles[symbol] = []
                        
                        self.fused_candles[symbol].append(fused_candle)
                        
                        # Maintain storage size
                        if len(self.fused_candles[symbol]) > 1000:
                            self.fused_candles[symbol] = self.fused_candles[symbol][-1000:]
                        
                        self.performance_metrics['fusions_performed'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error performing fusion: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _fuse_candles(self, symbol: str, timestamp: datetime, candles: List[M5Candle]) -> Optional[M5Candle]:
        """Fuse multiple candles into a single fused candle"""
        try:
            if len(candles) < 2:
                return None
            
            # Separate by source
            binance_candles = [c for c in candles if c.source == 'binance']
            mt5_candles = [c for c in candles if c.source == 'mt5']
            
            if not binance_candles or not mt5_candles:
                return None
            
            # Choose primary source based on asset classification
            asset_type = self.asset_classification.get(symbol, 'fx')
            
            if asset_type == 'crypto' or asset_type == 'high_vol':
                # Use Binance as primary for crypto and high-vol assets
                primary_candle = binance_candles[0]
                secondary_candle = mt5_candles[0]
            else:
                # Use MT5 as primary for FX assets
                primary_candle = mt5_candles[0]
                secondary_candle = binance_candles[0]
            
            # Calculate fused close using weighted average
            primary_weight = 0.7  # Primary source gets 70% weight
            secondary_weight = 0.3  # Secondary source gets 30% weight
            
            fused_close = (
                primary_candle.close * primary_weight +
                secondary_candle.close * secondary_weight
            )
            
            # Create fused candle
            fused_candle = M5Candle(
                symbol=symbol,
                timestamp=timestamp,
                open=primary_candle.open,  # Use primary source for OHLC
                high=max(primary_candle.high, secondary_candle.high),
                low=min(primary_candle.low, secondary_candle.low),
                close=fused_close,
                volume=primary_candle.volume + secondary_candle.volume,
                source='fused',
                fused_close=fused_close
            )
            
            # Calculate fused volatility score
            fused_candle.volatility_score = (
                primary_candle.volatility_score * primary_weight +
                secondary_candle.volatility_score * secondary_weight
            )
            
            # Determine fused structure majority
            if primary_candle.structure_majority == secondary_candle.structure_majority:
                fused_candle.structure_majority = primary_candle.structure_majority
            else:
                # Use volatility-weighted decision
                if primary_candle.volatility_score > secondary_candle.volatility_score:
                    fused_candle.structure_majority = primary_candle.structure_majority
                else:
                    fused_candle.structure_majority = secondary_candle.structure_majority
            
            return fused_candle
            
        except Exception as e:
            logger.error(f"❌ Error fusing candles: {e}")
            return None
    
    def get_volatility_score(self, symbol: str) -> float:
        """Get current volatility score for symbol"""
        return self.volatility_scores.get(symbol, 0.0)
    
    def get_fused_candles(self, symbol: str, limit: int = 100) -> List[M5Candle]:
        """Get recent fused candles for symbol"""
        if symbol in self.fused_candles:
            return self.fused_candles[symbol][-limit:]
        return []
    
    def get_volatility_history(self, symbol: str, hours: int = 24) -> List[Tuple[datetime, float]]:
        """Get volatility history for symbol"""
        if symbol not in self.volatility_history:
            return []
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [
            (timestamp, score) for timestamp, score in self.volatility_history[symbol]
            if timestamp >= cutoff_time
        ]
    
    def is_high_volatility(self, symbol: str) -> bool:
        """Check if symbol is in high volatility state"""
        volatility_score = self.get_volatility_score(symbol)
        return volatility_score > self.config.high_vol_threshold
    
    def get_asset_classification(self, symbol: str) -> str:
        """Get asset classification for symbol"""
        return self.asset_classification.get(symbol, 'fx')
    
    def get_status(self) -> Dict[str, Any]:
        """Get bridge status"""
        return {
            'is_active': self.is_active,
            'volatility_scores': self.volatility_scores,
            'asset_classifications': self.asset_classification,
            'high_volatility_assets': [
                symbol for symbol, score in self.volatility_scores.items()
                if score > self.config.high_vol_threshold
            ],
            'performance_metrics': self.performance_metrics
        }
    
    def get_volatility_analysis(self, symbol: str) -> Dict[str, Any]:
        """Get volatility analysis for a symbol"""
        try:
            volatility_score = self.get_volatility_score(symbol)
            asset_class = self.get_asset_classification(symbol)
            is_high_volatility = volatility_score > self.config.high_vol_threshold
            
            return {
                'symbol': symbol,
                'volatility_score': volatility_score,
                'asset_class': asset_class,
                'is_high_volatility': is_high_volatility,
                'threshold': self.config.high_vol_threshold,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Error getting volatility analysis for {symbol}: {e}")
            return {
                'symbol': symbol,
                'volatility_score': 0.0,
                'asset_class': 'unknown',
                'is_high_volatility': False,
                'threshold': self.config.high_vol_threshold,
                'error': str(e)
            }
    
    def get_m5_candles(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get M5 candles for a symbol"""
        try:
            candles = self.get_fused_candles(symbol, limit)
            return [
                {
                    'timestamp': candle.timestamp.isoformat(),
                    'open': candle.open,
                    'high': candle.high,
                    'low': candle.low,
                    'close': candle.close,
                    'volume': candle.volume,
                    'volatility_score': candle.volatility_score,
                    'structure_type': candle.structure_type
                }
                for candle in candles
            ]
        except Exception as e:
            logger.error(f"❌ Error getting M5 candles for {symbol}: {e}")
            return []
