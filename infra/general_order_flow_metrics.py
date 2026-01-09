"""
General Order Flow Metrics
Calculates order flow metrics for all symbols (BTC uses true order flow, others use proxy)
"""

import logging
import asyncio
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class GeneralOrderFlowMetrics:
    """Calculate order flow metrics for all symbols"""
    
    def __init__(self, mt5_service=None, order_flow_service=None):
        self.mt5_service = mt5_service
        self.order_flow_service = order_flow_service
        
        # For proxy calculations (requires symbol_config)
        try:
            from app.engine.volume_delta_proxy import VolumeDeltaProxy
            # Create symbol config with defaults
            symbol_config = {
                'delta_threshold': 1.5,
                'delta_lookback_ticks': 100,
                'delta_spike_threshold': 2.0,
                'delta_spike_cooldown_ticks': 50
            }
            self.volume_proxy = VolumeDeltaProxy(symbol_config)
        except ImportError:
            logger.warning("VolumeDeltaProxy not available, will use fallback methods")
            self.volume_proxy = None
    
    async def get_order_flow_metrics(
        self,
        symbol: str,
        window_minutes: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate order flow metrics for all symbols.
        - BTC: Uses Binance true order flow (data_quality: "good")
        - Others: Uses MT5 tick proxy (data_quality: "proxy")
        
        Args:
            symbol: Trading symbol (e.g., "XAUUSDc", "BTCUSDc")
            window_minutes: Time window in minutes (default: 30)
        
        Returns:
            {
                "cvd_value": 132.5,  # Cumulative volume delta (proxy for non-BTC)
                "cvd_slope": "falling",  # "up" | "down" | "flat"
                "aggressor_ratio": 0.84,  # buy_vol / sell_vol (proxy)
                "imbalance_score": 30,  # 0-100 (how one-sided)
                "large_trade_count": 2,  # Blocks > X size in N mins (if available)
                "data_quality": "proxy",  # "proxy" | "limited" | "good" | "unavailable"
                "data_source": "mt5_tick_proxy",  # Source of data
                "window_minutes": 30
            }
        """
        try:
            # Normalize symbol
            symbol_base = symbol.upper().rstrip('Cc')
            symbol_norm = symbol_base + 'c' if not symbol_base.endswith('C') else symbol_base
            
            # Check if BTC - use true order flow
            if symbol_base == "BTCUSD":
                return await self._get_btc_order_flow(symbol_norm, window_minutes)
            
            # For non-BTC symbols, use MT5 tick proxy
            return await self._get_proxy_order_flow(symbol_norm, window_minutes)
            
        except Exception as e:
            logger.error(f"Error calculating order flow metrics for {symbol}: {e}", exc_info=True)
            return self._create_unavailable_response(window_minutes)
    
    async def _get_btc_order_flow(
        self,
        symbol: str,
        window_minutes: int
    ) -> Optional[Dict[str, Any]]:
        """Get true order flow for BTC using Binance data"""
        try:
            if not self.order_flow_service or not self.order_flow_service.running:
                logger.warning("Order flow service not available for BTC")
                return self._create_unavailable_response(window_minutes)
            
            # Convert window_minutes to seconds
            window_seconds = window_minutes * 60
            
            # Get buy/sell pressure from OrderFlowService
            binance_symbol = "BTCUSDT"  # Binance uses BTCUSDT
            pressure_data = self.order_flow_service.get_buy_sell_pressure(binance_symbol, window_seconds)
            
            if not pressure_data:
                logger.warning(f"No pressure data available for {binance_symbol}")
                return self._create_unavailable_response(window_minutes)
            
            buy_volume = pressure_data.get("buy_volume", 0)
            sell_volume = pressure_data.get("sell_volume", 0)
            net_volume = pressure_data.get("net_volume", 0)
            pressure_ratio = pressure_data.get("pressure", 1.0)
            
            # Calculate CVD (cumulative volume delta)
            # For BTC, we can use the net_volume as delta, but for true CVD we'd need historical bars
            # For now, use net_volume as a proxy for current delta
            cvd_value = float(net_volume)
            
            # Calculate CVD slope (simplified - would need historical data for true slope)
            # For now, use pressure ratio to infer slope
            if pressure_ratio > 1.1:
                cvd_slope = "up"
            elif pressure_ratio < 0.9:
                cvd_slope = "down"
            else:
                cvd_slope = "flat"
            
            # Calculate aggressor ratio
            if sell_volume > 0:
                aggressor_ratio = buy_volume / sell_volume
            else:
                aggressor_ratio = 999.0 if buy_volume > 0 else 1.0
            
            # Calculate imbalance score (0-100)
            total_volume = buy_volume + sell_volume
            if total_volume > 0:
                imbalance_score = int(abs((buy_volume - sell_volume) / total_volume) * 100)
            else:
                imbalance_score = 0
            
            # Large trade count (from whale detector if available)
            large_trade_count = 0
            try:
                recent_whales = self.order_flow_service.get_recent_whales(binance_symbol, min_size="medium")
                if recent_whales:
                    large_trade_count = len(recent_whales)
            except Exception:
                pass  # Not critical
            
            return {
                "cvd_value": cvd_value,
                "cvd_slope": cvd_slope,
                "aggressor_ratio": float(aggressor_ratio) if np.isfinite(aggressor_ratio) else None,
                "imbalance_score": imbalance_score,
                "large_trade_count": large_trade_count,
                "data_quality": "good",  # True order flow from Binance
                "data_source": "binance_aggtrades",
                "window_minutes": window_minutes
            }
            
        except Exception as e:
            logger.error(f"Error getting BTC order flow: {e}")
            return self._create_unavailable_response(window_minutes)
    
    async def _get_proxy_order_flow(
        self,
        symbol: str,
        window_minutes: int
    ) -> Optional[Dict[str, Any]]:
        """Get proxy order flow for non-BTC symbols using MT5 tick data"""
        try:
            if not self.mt5_service:
                logger.warning("MT5 service not available for proxy order flow")
                return self._create_unavailable_response(window_minutes)
            
            # Fetch recent bars to calculate proxy metrics
            # Use M5 bars for the window
            bars_needed = max(6, window_minutes // 5)  # At least 6 bars (30 minutes)
            
            loop = asyncio.get_event_loop()
            bars = await loop.run_in_executor(
                None,
                lambda: self.mt5_service.get_bars(symbol, "M5", bars_needed)
            )
            
            if bars is None or len(bars) == 0:
                logger.warning(f"No bars available for {symbol}")
                return self._create_unavailable_response(window_minutes)
            
            # Calculate proxy metrics from price action
            closes = bars['close'].values
            volumes = bars.get('volume', bars.get('tick_volume', np.zeros(len(bars)))).values
            
            if len(closes) < 2:
                return self._create_unavailable_response(window_minutes)
            
            # Calculate price changes and directions
            price_changes = np.diff(closes)
            directions = np.where(price_changes > 0, 1, np.where(price_changes < 0, -1, 0))
            
            # Calculate volume delta proxy: delta = direction * volume
            # Use volumes[:-1] to match price_changes length
            volumes_for_delta = volumes[:-1] if len(volumes) > len(directions) else volumes[:len(directions)]
            if len(volumes_for_delta) < len(directions):
                volumes_for_delta = np.pad(volumes_for_delta, (0, len(directions) - len(volumes_for_delta)), 'constant')
            
            volume_deltas = directions * volumes_for_delta[:len(directions)]
            
            # Calculate CVD (cumulative sum of deltas)
            cvd = np.cumsum(volume_deltas)
            cvd_value = float(cvd[-1]) if len(cvd) > 0 else 0.0
            
            # Calculate CVD slope (compare last 10% of bars, minimum 3 bars)
            slope_bars = max(3, min(10, len(cvd) // 10))
            if len(cvd) >= slope_bars * 2:
                recent_cvd = cvd[-slope_bars:]
                earlier_cvd = cvd[-slope_bars * 2:-slope_bars]
                
                recent_avg = np.mean(recent_cvd)
                earlier_avg = np.mean(earlier_cvd)
                
                change_pct = abs((recent_avg - earlier_avg) / earlier_avg) if earlier_avg != 0 else 0
                
                if change_pct > 0.05:  # 5% change threshold
                    cvd_slope = "up" if recent_avg > earlier_avg else "down"
                else:
                    cvd_slope = "flat"
            else:
                cvd_slope = "flat"
            
            # Calculate aggressor ratio (proxy: positive_delta / negative_delta)
            positive_delta = np.sum(volume_deltas[volume_deltas > 0])
            negative_delta = abs(np.sum(volume_deltas[volume_deltas < 0]))
            
            if negative_delta > 0:
                aggressor_ratio = positive_delta / negative_delta
            else:
                aggressor_ratio = 999.0 if positive_delta > 0 else 1.0
            
            # Calculate imbalance score (0-100)
            total_delta_volume = positive_delta + negative_delta
            if total_delta_volume > 0:
                imbalance_score = int(abs((positive_delta - negative_delta) / total_delta_volume) * 100)
            else:
                imbalance_score = 0
            
            # Large trade count (not available from MT5 tick data)
            large_trade_count = 0
            
            # Determine data quality
            if len(bars) >= bars_needed * 0.8:  # 80% of requested bars
                data_quality = "proxy"
            elif len(bars) >= bars_needed * 0.5:  # 50% of requested bars
                data_quality = "limited"
            else:
                data_quality = "unavailable"
            
            if data_quality == "unavailable":
                return self._create_unavailable_response(window_minutes)
            
            return {
                "cvd_value": cvd_value,
                "cvd_slope": cvd_slope,
                "aggressor_ratio": float(aggressor_ratio) if np.isfinite(aggressor_ratio) else None,
                "imbalance_score": imbalance_score,
                "large_trade_count": large_trade_count,
                "data_quality": data_quality,
                "data_source": "mt5_tick_proxy",
                "window_minutes": window_minutes
            }
            
        except Exception as e:
            logger.error(f"Error getting proxy order flow for {symbol}: {e}")
            return self._create_unavailable_response(window_minutes)
    
    def _create_unavailable_response(self, window_minutes: int) -> Dict[str, Any]:
        """Create response dict for unavailable data"""
        return {
            "cvd_value": 0.0,
            "cvd_slope": "flat",
            "aggressor_ratio": None,
            "imbalance_score": 0,
            "large_trade_count": 0,
            "data_quality": "unavailable",
            "data_source": "unavailable",
            "window_minutes": window_minutes
        }

