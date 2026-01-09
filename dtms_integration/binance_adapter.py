"""
DTMS Binance Adapter
Wrapper for Binance service integration with DTMS
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class DTMSBinanceAdapter:
    """
    Binance adapter for DTMS system.
    Provides enhanced Binance functionality for defensive trade management.
    """
    
    def __init__(self, binance_service):
        self.binance_service = binance_service
        
        logger.info("DTMSBinanceAdapter initialized")
    
    def get_pressure(self, symbol: str, window: int = 30) -> Optional[Dict[str, Any]]:
        """Get order flow pressure data"""
        try:
            if not self.binance_service:
                return None
            
            return self.binance_service.get_pressure(symbol, window)
        except Exception as e:
            logger.error(f"Failed to get pressure for {symbol}: {e}")
            return None
    
    def get_z_score(self, symbol: str, window: int = 30) -> Optional[float]:
        """Get Z-score for symbol"""
        try:
            if not self.binance_service:
                return None
            
            return self.binance_service.get_z_score(symbol, window)
        except Exception as e:
            logger.error(f"Failed to get Z-score for {symbol}: {e}")
            return None
    
    def get_pivots(self, symbol: str, window: int = 30) -> Optional[Dict[str, Any]]:
        """Get pivot data"""
        try:
            if not self.binance_service:
                return None
            
            return self.binance_service.get_pivots(symbol, window)
        except Exception as e:
            logger.error(f"Failed to get pivots for {symbol}: {e}")
            return None
    
    def get_liquidity(self, symbol: str, window: int = 30) -> Optional[Dict[str, Any]]:
        """Get liquidity data"""
        try:
            if not self.binance_service:
                return None
            
            return self.binance_service.get_liquidity(symbol, window)
        except Exception as e:
            logger.error(f"Failed to get liquidity for {symbol}: {e}")
            return None
    
    def get_bollinger_squeeze(self, symbol: str, window: int = 30) -> Optional[Dict[str, Any]]:
        """Get Bollinger Band squeeze data"""
        try:
            if not self.binance_service:
                return None
            
            return self.binance_service.get_bollinger_squeeze(symbol, window)
        except Exception as e:
            logger.error(f"Failed to get Bollinger squeeze for {symbol}: {e}")
            return None
    
    def get_tape_reading(self, symbol: str, window: int = 30) -> Optional[Dict[str, Any]]:
        """Get tape reading data"""
        try:
            if not self.binance_service:
                return None
            
            return self.binance_service.get_tape_reading(symbol, window)
        except Exception as e:
            logger.error(f"Failed to get tape reading for {symbol}: {e}")
            return None
    
    def get_candle_patterns(self, symbol: str, window: int = 30) -> Optional[Dict[str, Any]]:
        """Get candle pattern data"""
        try:
            if not self.binance_service:
                return None
            
            return self.binance_service.get_candle_patterns(symbol, window)
        except Exception as e:
            logger.error(f"Failed to get candle patterns for {symbol}: {e}")
            return None
    
    def get_order_flow(self, symbol: str, window: int = 30) -> Optional[Dict[str, Any]]:
        """Get order flow data"""
        try:
            if not self.binance_service:
                return None
            
            return self.binance_service.get_order_flow(symbol, window)
        except Exception as e:
            logger.error(f"Failed to get order flow for {symbol}: {e}")
            return None
    
    def is_streaming(self, symbol: str) -> bool:
        """Check if symbol is being streamed"""
        try:
            if not self.binance_service:
                return False
            
            return symbol.lower() in self.binance_service.symbols
        except Exception as e:
            logger.error(f"Failed to check streaming status for {symbol}: {e}")
            return False
    
    def get_streaming_symbols(self) -> list:
        """Get list of streaming symbols"""
        try:
            if not self.binance_service:
                return []
            
            return self.binance_service.symbols.copy()
        except Exception as e:
            logger.error(f"Failed to get streaming symbols: {e}")
            return []
