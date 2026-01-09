"""
Execution Quality Monitor
Monitors spread, slippage, and execution quality metrics
"""

import logging
import asyncio
from typing import Dict, Any, Optional
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)


class ExecutionQualityMonitor:
    """Monitor spread, slippage, and execution quality"""
    
    def __init__(self, mt5_service=None, spread_tracker=None):
        self.mt5_service = mt5_service
        
        # Reuse existing SpreadTracker
        if spread_tracker is None:
            from infra.spread_tracker import SpreadTracker
            self.spread_tracker = SpreadTracker()
        else:
            self.spread_tracker = spread_tracker
    
    async def get_execution_context(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Monitor spread, slippage, and execution quality.
        
        Args:
            symbol: Trading symbol (e.g., "XAUUSDc")
        
        Returns:
            {
                "current_spread_points": 19,  # Current spread in points
                "spread_vs_median": 2.1,  # Multiple of median spread (e.g., 2.1x)
                "is_spread_elevated": True,  # True if spread_vs_median > 1.5
                "avg_slippage_points": 6,  # Average slippage from last N trades (if available)
                "slippage_vs_normal": 1.8,  # Multiple of normal slippage
                "is_slippage_elevated": True,  # True if slippage_vs_normal > 1.5
                "execution_quality": "degraded",  # "good" | "degraded" | "poor"
                "slippage_sample_size": 10,  # Number of trades used for slippage calc
                "slippage_data_available": True  # False if no trade history
            }
        """
        try:
            # 1. Get current spread from MT5
            current_spread_points = await self._get_current_spread(symbol)
            
            if current_spread_points is None:
                logger.warning(f"Could not get current spread for {symbol}")
                return self._create_unavailable_response()
            
            # 1.5. Update spread tracker with current spread (if we have bid/ask)
            # This ensures spread history is up-to-date
            try:
                if self.mt5_service:
                    quote = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.mt5_service.get_quote(symbol)
                    )
                    if quote:
                        self.spread_tracker.update_spread(symbol, quote.bid, quote.ask)
            except Exception as e:
                logger.debug(f"Error updating spread tracker: {e}")
            
            # 2. Get spread data from SpreadTracker
            spread_data = self.spread_tracker.get_spread_data(symbol, current_spread_points)
            
            # 3. Get median spread (or use average if median unavailable)
            median_spread = self.spread_tracker.get_median_spread(symbol)
            if median_spread == 0.0:
                # Fallback to average if median unavailable
                median_spread = spread_data.average_spread
            
            # 4. Calculate spread_vs_median
            if median_spread > 0:
                spread_vs_median = current_spread_points / median_spread
            else:
                spread_vs_median = 1.0  # Default if no historical data
            
            is_spread_elevated = spread_vs_median > 1.5
            
            # 5. Query trade history for slippage (if available)
            slippage_result = await self._calculate_slippage_metrics(symbol)
            
            # 6. Calculate execution quality
            execution_quality = self._calculate_execution_quality(
                spread_vs_median,
                slippage_result.get("slippage_vs_normal", 1.0) if slippage_result.get("slippage_data_available", False) else None
            )
            
            return {
                "current_spread_points": float(current_spread_points),
                "spread_vs_median": float(spread_vs_median),
                "is_spread_elevated": is_spread_elevated,
                "avg_slippage_points": slippage_result.get("avg_slippage_points"),
                "slippage_vs_normal": slippage_result.get("slippage_vs_normal"),
                "is_slippage_elevated": slippage_result.get("is_slippage_elevated", False),
                "execution_quality": execution_quality,
                "slippage_sample_size": slippage_result.get("slippage_sample_size", 0),
                "slippage_data_available": slippage_result.get("slippage_data_available", False)
            }
            
        except Exception as e:
            logger.error(f"Error calculating execution context for {symbol}: {e}", exc_info=True)
            return self._create_unavailable_response()
    
    async def _get_current_spread(self, symbol: str) -> Optional[float]:
        """Get current spread from MT5 in points"""
        try:
            if not self.mt5_service:
                # Try direct MT5 call
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    return None
                spread = tick.ask - tick.bid
                
                # Convert to points (get point size from symbol info)
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info is None:
                    return spread  # Return raw spread if can't get point size
                
                point = symbol_info.point
                if point > 0:
                    spread_points = spread / point
                else:
                    spread_points = spread
                
                return spread_points
            else:
                # Use MT5 service
                loop = asyncio.get_event_loop()
                quote = await loop.run_in_executor(
                    None,
                    lambda: self.mt5_service.get_quote(symbol)
                )
                if quote is None:
                    return None
                
                spread = quote.ask - quote.bid
                
                # Get point size
                symbol_info = await loop.run_in_executor(
                    None,
                    lambda: mt5.symbol_info(symbol)
                )
                if symbol_info is None:
                    return spread
                
                point = symbol_info.point
                if point > 0:
                    spread_points = spread / point
                else:
                    spread_points = spread
                
                return spread_points
                
        except Exception as e:
            logger.error(f"Error getting current spread for {symbol}: {e}")
            return None
    
    async def _calculate_slippage_metrics(self, symbol: str) -> Dict[str, Any]:
        """
        Calculate slippage metrics from trade history.
        Returns default values if slippage data unavailable.
        """
        try:
            # Try to query trade history database
            # Note: Slippage data may not be available initially
            # For now, return unavailable - can be enhanced later when trade history is tracked
            
            # TODO: Query trade history database for recent trades
            # Example query:
            # SELECT entry_price, requested_price, slippage
            # FROM trade_history
            # WHERE symbol = ? AND entry_time > datetime('now', '-7 days')
            # ORDER BY entry_time DESC
            # LIMIT 20
            
            # For now, return unavailable
            return {
                "avg_slippage_points": None,
                "slippage_vs_normal": None,
                "is_slippage_elevated": False,
                "slippage_sample_size": 0,
                "slippage_data_available": False
            }
            
        except Exception as e:
            logger.debug(f"Error calculating slippage metrics for {symbol}: {e}")
            return {
                "avg_slippage_points": None,
                "slippage_vs_normal": None,
                "is_slippage_elevated": False,
                "slippage_sample_size": 0,
                "slippage_data_available": False
            }
    
    def _calculate_execution_quality(
        self,
        spread_vs_median: float,
        slippage_vs_normal: Optional[float]
    ) -> str:
        """
        Calculate execution quality based on spread and slippage.
        
        Returns:
            "good" | "degraded" | "poor"
        """
        # If slippage data unavailable, use spread only
        if slippage_vs_normal is None:
            if spread_vs_median < 1.5:
                return "good"
            elif spread_vs_median < 2.0:
                return "degraded"
            else:
                return "poor"
        
        # Use both spread and slippage
        spread_ok = spread_vs_median < 1.5
        slippage_ok = slippage_vs_normal < 1.5
        
        if spread_ok and slippage_ok:
            return "good"
        elif spread_vs_median > 2.0 and slippage_vs_normal > 2.0:
            return "poor"
        else:
            return "degraded"
    
    def _create_unavailable_response(self) -> Dict[str, Any]:
        """Create response dict for unavailable data"""
        return {
            "current_spread_points": 0.0,
            "spread_vs_median": 1.0,
            "is_spread_elevated": False,
            "avg_slippage_points": None,
            "slippage_vs_normal": None,
            "is_slippage_elevated": False,
            "execution_quality": "good",
            "slippage_sample_size": 0,
            "slippage_data_available": False
        }

