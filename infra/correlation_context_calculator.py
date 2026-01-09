"""
Correlation Context Calculator
Calculates rolling correlation between symbol and reference assets (DXY, SP500, US10Y, BTC)
"""

import logging
import asyncio
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Expected correlation patterns for conflict detection
EXPECTED_CORRELATIONS = {
    "XAUUSD": {
        "dxy": -0.7,
        "us10y": -0.5,
        "sp500": 0.2
    },
    "XAUUSDc": {
        "dxy": -0.7,
        "us10y": -0.5,
        "sp500": 0.2
    },
    "BTCUSD": {
        "dxy": -0.3,
        "sp500": 0.6,
        "us10y": 0.1
    },
    "BTCUSDc": {
        "dxy": -0.3,
        "sp500": 0.6,
        "us10y": 0.1
    },
    "EURUSD": {
        "dxy": -0.9,
        "us10y": -0.4,
        "sp500": 0.3
    },
    "EURUSDc": {
        "dxy": -0.9,
        "us10y": -0.4,
        "sp500": 0.3
    }
}


class CorrelationContextCalculator:
    """Calculate correlation context for symbols vs reference assets"""
    
    def __init__(self, mt5_service=None, market_indices_service=None):
        self.mt5_service = mt5_service
        self.market_indices = market_indices_service
        # Reuse existing correlation calculation (static method - no instantiation needed)
        try:
            from app.engine.historical_analysis_engine import HistoricalAnalysisEngine
            # Note: calculate_correlation is @staticmethod - call directly, no instantiation needed
            self._correlation_calc = HistoricalAnalysisEngine.calculate_correlation
        except ImportError:
            # Fallback to numpy correlation if numba not available
            logger.warning("HistoricalAnalysisEngine not available, using numpy correlation")
            self._correlation_calc = self._numpy_correlation
    
    async def calculate_correlation_context(
        self, 
        symbol: str, 
        window_minutes: int = 240
    ) -> Dict[str, Any]:
        """
        Calculate rolling correlation vs DXY, SP500, US10Y, BTC (if relevant)
        
        Args:
            symbol: Trading symbol (e.g., "XAUUSDc", "BTCUSDc")
            window_minutes: Correlation window in minutes (default: 240 = 4 hours)
        
        Returns:
            {
                "corr_window_minutes": 240,
                "corr_vs_dxy": -0.72,  # -1 to +1, or None if unavailable
                "corr_vs_sp500": 0.15,
                "corr_vs_us10y": -0.48,
                "corr_vs_btc": 0.05,  # Only for non-BTC symbols
                "conflict_flags": {
                    "gold_vs_dxy_conflict": True,  # If correlation breaks expected pattern
                    "sp500_divergence": False
                },
                "data_quality": "good" | "limited" | "unavailable",  # Based on sample size
                "sample_size": 240  # Number of bars used
            }
        """
        try:
            # Normalize symbol (remove 'c' suffix for lookup)
            symbol_base = symbol.upper().rstrip('Cc')
            symbol_norm = symbol_base + 'c' if not symbol_base.endswith('C') else symbol_base
            
            # Calculate required bar count (M5 bars for window_minutes)
            bars_needed = max(48, window_minutes // 5)  # Minimum 48 bars (4 hours)
            
            # 1. Fetch symbol historical data (M5 bars from MT5)
            symbol_bars = await self._fetch_symbol_bars(symbol_norm, bars_needed)
            if symbol_bars is None or len(symbol_bars) == 0:
                logger.warning(f"No symbol bars available for {symbol_norm}")
                return self._create_unavailable_response(window_minutes)
            
            # Validate symbol_bars structure
            if not hasattr(symbol_bars, 'columns') or 'time' not in symbol_bars.columns:
                logger.error(f"Symbol bars for {symbol_norm} missing 'time' column. Columns: {symbol_bars.columns if hasattr(symbol_bars, 'columns') else 'N/A'}")
                return self._create_unavailable_response(window_minutes)
            
            if 'close' not in symbol_bars.columns:
                logger.error(f"Symbol bars for {symbol_norm} missing 'close' column. Columns: {symbol_bars.columns if hasattr(symbol_bars, 'columns') else 'N/A'}")
                return self._create_unavailable_response(window_minutes)
            
            # Convert prices to returns
            symbol_returns = self._prices_to_returns(symbol_bars['close'].values)
            if symbol_returns is None or len(symbol_returns) == 0:
                logger.warning(f"Could not calculate returns for {symbol_norm}")
                return self._create_unavailable_response(window_minutes)
            
            # Get time values (handle both datetime and timestamp formats)
            # IMPORTANT: Returns are one element shorter than prices (returns[i] = (price[i+1] - price[i]) / price[i])
            # So we need to trim times to match: times[1:] corresponds to returns
            try:
                if hasattr(symbol_bars['time'].iloc[0], 'timestamp'):
                    # Already datetime objects
                    symbol_times = symbol_bars['time'].values[1:]  # Trim first element to match returns
                else:
                    # Convert to datetime if needed
                    import pandas as pd
                    symbol_times = pd.to_datetime(symbol_bars['time']).values[1:]  # Trim first element to match returns
            except Exception as e:
                logger.error(f"Error processing time column for {symbol_norm}: {e}")
                return self._create_unavailable_response(window_minutes)
            
            # Validate that returns and times have matching lengths
            if len(symbol_returns) != len(symbol_times):
                logger.error(f"Symbol returns ({len(symbol_returns)}) and times ({len(symbol_times)}) length mismatch after trimming")
                return self._create_unavailable_response(window_minutes)
            
            # 2. Fetch reference asset data and calculate correlations
            correlations = {}
            conflict_flags = {}
            
            # DXY correlation
            corr_dxy, quality_dxy = await self._calculate_correlation(
                symbol_returns, symbol_times, "dxy", bars_needed
            )
            correlations["corr_vs_dxy"] = corr_dxy
            
            # SP500 correlation
            corr_sp500, quality_sp500 = await self._calculate_correlation(
                symbol_returns, symbol_times, "sp500", bars_needed
            )
            correlations["corr_vs_sp500"] = corr_sp500
            
            # US10Y correlation
            corr_us10y, quality_us10y = await self._calculate_correlation(
                symbol_returns, symbol_times, "us10y", bars_needed
            )
            correlations["corr_vs_us10y"] = corr_us10y
            
            # BTC correlation (only for non-BTC symbols)
            if symbol_base != "BTCUSD":
                corr_btc, quality_btc = await self._calculate_correlation(
                    symbol_returns, symbol_bars['time'].values, "btc", bars_needed
                )
                correlations["corr_vs_btc"] = corr_btc
            else:
                correlations["corr_vs_btc"] = None
            
            # 3. Detect conflicts using expected correlation patterns
            symbol_key = symbol_norm if symbol_norm in EXPECTED_CORRELATIONS else symbol_base
            if symbol_key in EXPECTED_CORRELATIONS:
                expected = EXPECTED_CORRELATIONS[symbol_key]
                
                # Check DXY conflict
                if correlations["corr_vs_dxy"] is not None and "dxy" in expected:
                    deviation = abs(correlations["corr_vs_dxy"] - expected["dxy"])
                    conflict_flags["gold_vs_dxy_conflict"] = deviation > 0.3 if symbol_key.startswith("XAU") else False
                    conflict_flags["sp500_divergence"] = False  # Will be set below if needed
                else:
                    conflict_flags["gold_vs_dxy_conflict"] = False
                    conflict_flags["sp500_divergence"] = False
                
                # Check SP500 divergence
                if correlations["corr_vs_sp500"] is not None and "sp500" in expected:
                    deviation = abs(correlations["corr_vs_sp500"] - expected["sp500"])
                    conflict_flags["sp500_divergence"] = deviation > 0.3
                
                # Check US10Y divergence
                if correlations["corr_vs_us10y"] is not None and "us10y" in expected:
                    deviation = abs(correlations["corr_vs_us10y"] - expected["us10y"])
                    conflict_flags["us10y_divergence"] = deviation > 0.3
                else:
                    conflict_flags["us10y_divergence"] = False
                
                # Check BTC divergence (if applicable)
                if correlations["corr_vs_btc"] is not None and "btc" in expected:
                    deviation = abs(correlations["corr_vs_btc"] - expected["btc"])
                    conflict_flags["btc_divergence"] = deviation > 0.3
                else:
                    conflict_flags["btc_divergence"] = False
            else:
                # No expected correlations defined for this symbol
                conflict_flags = {
                    "gold_vs_dxy_conflict": False,
                    "sp500_divergence": False,
                    "us10y_divergence": False,
                    "btc_divergence": False
                }
            
            # 4. Determine overall data quality (worst quality among all correlations)
            qualities = [q for q in [quality_dxy, quality_sp500, quality_us10y] if q]
            if not qualities:
                overall_quality = "unavailable"
            elif "unavailable" in qualities:
                overall_quality = "unavailable"
            elif "limited" in qualities:
                overall_quality = "limited"
            else:
                overall_quality = "good"
            
            # 5. Calculate sample size (use minimum from all correlations)
            sample_size = len(symbol_returns)
            
            # 6. Convert all numpy types to native Python types
            result = {
                "corr_window_minutes": int(window_minutes),
                "corr_vs_dxy": float(corr_dxy) if corr_dxy is not None else None,
                "corr_vs_sp500": float(corr_sp500) if corr_sp500 is not None else None,
                "corr_vs_us10y": float(corr_us10y) if corr_us10y is not None else None,
                "corr_vs_btc": float(correlations["corr_vs_btc"]) if correlations["corr_vs_btc"] is not None else None,
                "conflict_flags": {k: bool(v) for k, v in conflict_flags.items()},
                "data_quality": overall_quality,
                "sample_size": int(sample_size)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating correlation context for {symbol}: {e}", exc_info=True)
            return self._create_unavailable_response(window_minutes)
    
    async def _fetch_symbol_bars(self, symbol: str, count: int) -> Optional[pd.DataFrame]:
        """Fetch symbol historical bars from MT5"""
        try:
            if not self.mt5_service:
                logger.warning("MT5 service not available")
                return None
            
            # Run MT5 call in thread to avoid blocking
            loop = asyncio.get_event_loop()
            bars = await loop.run_in_executor(
                None,
                lambda: self.mt5_service.get_bars(symbol, "M5", count)
            )
            
            if bars is None:
                logger.warning(f"get_bars returned None for {symbol}")
                return None
            
            # Ensure it's a DataFrame with required columns
            if not hasattr(bars, 'columns'):
                logger.error(f"get_bars returned non-DataFrame for {symbol}: {type(bars)}")
                return None
            
            # Check for required columns
            required_cols = ['time', 'close']
            missing_cols = [col for col in required_cols if col not in bars.columns]
            if missing_cols:
                logger.error(f"get_bars for {symbol} missing columns: {missing_cols}. Available: {bars.columns.tolist()}")
                return None
            
            return bars
            
        except Exception as e:
            logger.error(f"Error fetching symbol bars for {symbol}: {e}", exc_info=True)
            return None
    
    async def _fetch_reference_bars(self, asset: str, bars_needed: int) -> Optional[pd.DataFrame]:
        """Fetch reference asset historical bars"""
        try:
            # Calculate period (5 days should be enough for 240 bars at 5min intervals)
            period = "5d"
            interval = "5m"
            
            bars = None
            
            if asset == "btc":
                # Use MT5 for BTC (BTCUSDc) - doesn't need market_indices service
                if not self.mt5_service:
                    logger.warning("MT5 service not available for BTC bars")
                    return None
                loop = asyncio.get_event_loop()
                bars = await loop.run_in_executor(
                    None,
                    lambda: self.mt5_service.get_bars("BTCUSDc", "M5", bars_needed)
                )
            else:
                # For DXY, SP500, US10Y - need market_indices service
                if not self.market_indices:
                    logger.warning("Market indices service not available")
                    return None
                
                if asset == "dxy":
                    bars = await self.market_indices.get_dxy_bars(period=period, interval=interval)
                elif asset == "sp500":
                    bars = await self.market_indices.get_sp500_bars(period=period, interval=interval)
                elif asset == "us10y":
                    bars = await self.market_indices.get_us10y_bars(period=period, interval=interval)
                else:
                    logger.warning(f"Unknown reference asset: {asset}")
                    return None
            
            # Validate bars structure
            if bars is None:
                logger.warning(f"get_*_bars returned None for {asset}")
                return None
            
            if not hasattr(bars, 'columns'):
                logger.error(f"get_*_bars for {asset} returned non-DataFrame: {type(bars)}")
                return None
            
            # Check for required columns
            required_cols = ['time', 'close']
            missing_cols = [col for col in required_cols if col not in bars.columns]
            if missing_cols:
                logger.error(f"get_*_bars for {asset} missing columns: {missing_cols}. Available: {bars.columns.tolist()}")
                return None
            
            return bars
                
        except Exception as e:
            logger.error(f"Error fetching reference bars for {asset}: {e}", exc_info=True)
            return None
    
    def _prices_to_returns(self, prices: np.ndarray) -> Optional[np.ndarray]:
        """Convert prices to percentage returns"""
        try:
            if prices is None or len(prices) < 2:
                return None
            
            # Validate prices (must be positive)
            if np.any(prices <= 0):
                logger.warning("Non-positive prices detected, cannot calculate returns")
                return None
            
            # Calculate returns: (price[t] - price[t-1]) / price[t-1]
            returns = np.diff(prices) / prices[:-1]
            
            # Filter out NaN and Inf values
            returns = returns[np.isfinite(returns)]
            
            if len(returns) < 2:  # Minimum 2 returns for basic calculation (10 required for correlation)
                return None
            
            return returns
            
        except Exception as e:
            logger.error(f"Error converting prices to returns: {e}")
            return None
    
    async def _calculate_correlation(
        self,
        symbol_returns: np.ndarray,
        symbol_times: np.ndarray,
        asset: str,
        bars_needed: int
    ) -> Tuple[Optional[float], str]:
        """
        Calculate correlation between symbol returns and reference asset returns
        
        Returns:
            Tuple of (correlation_value, data_quality)
        """
        try:
            # Fetch reference asset bars
            ref_bars = await self._fetch_reference_bars(asset, bars_needed)
            if ref_bars is None or len(ref_bars) == 0:
                return None, "unavailable"
            
            # Validate ref_bars structure before accessing columns
            if not hasattr(ref_bars, 'columns') or 'time' not in ref_bars.columns or 'close' not in ref_bars.columns:
                logger.error(f"ref_bars for {asset} missing required columns. Columns: {ref_bars.columns.tolist() if hasattr(ref_bars, 'columns') else 'N/A'}")
                return None, "unavailable"
            
            # Convert reference prices to returns
            ref_returns = self._prices_to_returns(ref_bars['close'].values)
            if ref_returns is None or len(ref_returns) == 0:
                return None, "unavailable"
            
            # Get time values (handle both datetime and timestamp formats)
            # IMPORTANT: Returns are one element shorter than prices (returns[i] = (price[i+1] - price[i]) / price[i])
            # So we need to trim times to match: times[1:] corresponds to returns
            try:
                if hasattr(ref_bars['time'].iloc[0], 'timestamp'):
                    # Already datetime objects
                    ref_times = ref_bars['time'].values[1:]  # Trim first element to match returns
                else:
                    # Convert to datetime if needed
                    import pandas as pd
                    ref_times = pd.to_datetime(ref_bars['time']).values[1:]  # Trim first element to match returns
            except Exception as e:
                logger.error(f"Error processing time column for reference asset {asset}: {e}")
                return None, "unavailable"
            
            # Validate that returns and times have matching lengths
            if len(ref_returns) != len(ref_times):
                logger.error(f"Reference returns ({len(ref_returns)}) and times ({len(ref_times)}) length mismatch after trimming")
                return None, "unavailable"
            
            # Align timestamps (pandas merge_asof or reindex)
            aligned_symbol, aligned_ref = self._align_returns(
                symbol_returns, symbol_times, ref_returns, ref_times
            )
            
            if aligned_symbol is None or aligned_ref is None:
                return None, "unavailable"
            
            if len(aligned_symbol) < 10 or len(aligned_ref) < 10:
                return None, "unavailable"
            
            # Ensure equal length
            min_len = min(len(aligned_symbol), len(aligned_ref))
            aligned_symbol = aligned_symbol[:min_len]
            aligned_ref = aligned_ref[:min_len]
            
            # Calculate overlap percentage
            overlap_pct = len(aligned_symbol) / bars_needed if bars_needed > 0 else 0
            
            # Determine data quality
            if overlap_pct >= 0.8 and len(aligned_symbol) >= 192:  # 80% of 240 bars
                quality = "good"
            elif overlap_pct >= 0.5 and len(aligned_symbol) >= 120:  # 50% of 240 bars
                quality = "limited"
            else:
                quality = "unavailable"
            
            if quality == "unavailable":
                return None, quality
            
            # Calculate correlation using static method
            correlation = self._correlation_calc(
                aligned_symbol.astype(np.float32),
                aligned_ref.astype(np.float32)
            )
            
            # Validate correlation (should be in [-1, 1])
            if not np.isfinite(correlation):
                return None, quality
            
            correlation = float(np.clip(correlation, -1.0, 1.0))
            
            return correlation, quality
            
        except Exception as e:
            logger.error(f"Error calculating correlation for {asset}: {e}")
            return None, "unavailable"
    
    def _align_returns(
        self,
        symbol_returns: np.ndarray,
        symbol_times: np.ndarray,
        ref_returns: np.ndarray,
        ref_times: np.ndarray
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Align symbol and reference returns by timestamp"""
        try:
            import pandas as pd
            
            # Validate input arrays have same length
            if len(symbol_returns) != len(symbol_times):
                logger.error(f"Symbol returns ({len(symbol_returns)}) and times ({len(symbol_times)}) length mismatch")
                return None, None
            if len(ref_returns) != len(ref_times):
                logger.error(f"Reference returns ({len(ref_returns)}) and times ({len(ref_times)}) length mismatch")
                return None, None
            
            # Create DataFrames with time as column (not index) for merge_asof
            symbol_df = pd.DataFrame({
                'time': pd.to_datetime(symbol_times),
                'returns': symbol_returns
            })
            ref_df = pd.DataFrame({
                'time': pd.to_datetime(ref_times),
                'returns': ref_returns
            })
            
            # Sort by time (required for merge_asof)
            symbol_df = symbol_df.sort_values('time')
            ref_df = ref_df.sort_values('time')
            
            # Align using merge_asof (forward fill for missing bars)
            # merge_asof requires left_on/right_on when using columns (not index)
            aligned = pd.merge_asof(
                symbol_df,
                ref_df,
                on='time',
                direction='forward',
                tolerance=pd.Timedelta(minutes=10),  # Allow 10-minute tolerance
                suffixes=('_symbol', '_ref')
            )
            
            # Drop rows with NaN (no match found)
            aligned = aligned.dropna(subset=['returns_symbol', 'returns_ref'])
            
            if len(aligned) == 0:
                logger.warning("No aligned returns found after merge_asof")
                return None, None
            
            # Validate aligned arrays have same length
            symbol_aligned = aligned['returns_symbol'].values
            ref_aligned = aligned['returns_ref'].values
            
            if len(symbol_aligned) != len(ref_aligned):
                logger.error(f"Aligned arrays length mismatch: symbol={len(symbol_aligned)}, ref={len(ref_aligned)}")
                return None, None
            
            return symbol_aligned, ref_aligned
            
        except Exception as e:
            logger.error(f"Error aligning returns: {e}", exc_info=True)
            return None, None
    
    def _numpy_correlation(self, series1: np.ndarray, series2: np.ndarray) -> float:
        """Fallback correlation calculation using numpy"""
        if len(series1) != len(series2) or len(series1) == 0:
            return 0.0
        
        # Calculate correlation using numpy
        correlation = np.corrcoef(series1, series2)[0, 1]
        
        if not np.isfinite(correlation):
            return 0.0
        
        return float(correlation)
    
    def _create_unavailable_response(self, window_minutes: int) -> Dict[str, Any]:
        """Create response dict for unavailable data"""
        return {
            "corr_window_minutes": int(window_minutes),
            "corr_vs_dxy": None,
            "corr_vs_sp500": None,
            "corr_vs_us10y": None,
            "corr_vs_btc": None,
            "conflict_flags": {
                "gold_vs_dxy_conflict": False,
                "sp500_divergence": False,
                "us10y_divergence": False,
                "btc_divergence": False
            },
            "data_quality": "unavailable",
            "sample_size": 0
        }
    
    async def calculate_dxy_change_pct(self, window_minutes: int = 60) -> Optional[float]:
        """
        Calculate DXY percentage change over rolling window.
        
        Args:
            window_minutes: Time window in minutes (default: 60 = 1 hour)
        
        Returns:
            Percentage change as float (e.g., 0.3 for +0.3%), or None if unavailable
        """
        try:
            if not self.market_indices:
                logger.warning("Market indices service not available")
                return None
            
            # Get DXY data (cached, 15 minute TTL)
            dxy_data = self.market_indices.get_dxy()
            if not dxy_data or 'price' not in dxy_data:
                return None
            
            # Fetch historical DXY data for percentage change calculation
            # Use market_indices_service to get historical prices
            try:
                import yfinance as yf
                dxy = yf.Ticker("DX-Y.NYB")
                # Get enough bars for the window (1 hour = 12 bars at 5min intervals)
                bars_needed = max(12, window_minutes // 5)
                hist = dxy.history(period="2d", interval="5m")
                
                if len(hist) < bars_needed:
                    logger.warning(f"Insufficient DXY historical data: {len(hist)} < {bars_needed}")
                    return None
                
                current_price = float(hist['Close'].iloc[-1])
                past_price = float(hist['Close'].iloc[-bars_needed])
                
                # Calculate percentage change
                change_pct = ((current_price - past_price) / past_price) * 100
                return round(change_pct, 2)
                
            except Exception as e:
                logger.error(f"Error calculating DXY percentage change: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error in calculate_dxy_change_pct: {e}", exc_info=True)
            return None
    
    async def calculate_spx_change_pct(self, window_minutes: int = 60) -> Optional[float]:
        """
        Calculate S&P 500 (SPX) percentage change over rolling window.
        
        Args:
            window_minutes: Time window in minutes (default: 60 = 1 hour)
        
        Returns:
            Percentage change as float (e.g., 0.5 for +0.5%), or None if unavailable
        """
        try:
            # Use yfinance directly (works even if market_indices is None)
            try:
                import yfinance as yf
                spx = yf.Ticker("^GSPC")
                # Get enough bars for the window (1 hour = 12 bars at 5min intervals)
                bars_needed = max(12, window_minutes // 5)
                hist = spx.history(period="2d", interval="5m")
                
                if len(hist) < bars_needed:
                    logger.warning(f"Insufficient SPX historical data: {len(hist)} < {bars_needed}")
                    return None
                
                current_price = float(hist['Close'].iloc[-1])
                past_price = float(hist['Close'].iloc[-bars_needed])
                
                # Calculate percentage change
                change_pct = ((current_price - past_price) / past_price) * 100
                return round(change_pct, 2)
                
            except Exception as e:
                logger.error(f"Error calculating SPX percentage change: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error in calculate_spx_change_pct: {e}", exc_info=True)
            return None
    
    async def calculate_us10y_yield_change(self, window_minutes: int = 60) -> Optional[float]:
        """
        Calculate US 10Y Treasury yield change over rolling window.
        
        Args:
            window_minutes: Time window in minutes (default: 60 = 1 hour)
        
        Returns:
            Yield change as float (e.g., -0.05 for -5 basis points drop), or None if unavailable
            Positive value = yield increase, negative value = yield drop
        """
        try:
            # Use yfinance directly (works even if market_indices is None)
            try:
                import yfinance as yf
                tnx = yf.Ticker("^TNX")
                # Get enough bars for the window (1 hour = 12 bars at 5min intervals)
                bars_needed = max(12, window_minutes // 5)
                hist = tnx.history(period="2d", interval="5m")
                
                if len(hist) < bars_needed:
                    logger.warning(f"Insufficient US10Y historical data: {len(hist)} < {bars_needed}")
                    return None
                
                current_yield = float(hist['Close'].iloc[-1])
                past_yield = float(hist['Close'].iloc[-bars_needed])
                
                # Calculate yield change (current - past)
                # Negative = yield dropped, positive = yield increased
                yield_change = current_yield - past_yield
                return round(yield_change, 4)  # Round to 4 decimal places (basis points precision)
                
            except Exception as e:
                logger.error(f"Error calculating US10Y yield change: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error in calculate_us10y_yield_change: {e}", exc_info=True)
            return None
    
    async def detect_dxy_divergence(
        self, 
        symbol: str, 
        window_minutes: int = 60,
        divergence_threshold: float = -0.5
    ) -> Dict[str, Any]:
        """
        Detect divergence between DXY and symbol (moving in opposite directions).
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDc", "XAUUSDc")
            window_minutes: Lookback window in minutes (default: 60)
            divergence_threshold: Correlation threshold for divergence (default: -0.5)
        
        Returns:
            {
                "divergence_detected": bool,
                "correlation": float,  # Correlation coefficient (-1 to 1)
                "dxy_direction": str,  # "up", "down", or "neutral"
                "symbol_direction": str,  # "up", "down", or "neutral"
                "data_quality": str  # "good", "limited", or "unavailable"
            }
        """
        try:
            # Get correlation context (already calculates corr_vs_dxy)
            correlation_context = await self.calculate_correlation_context(symbol, window_minutes)
            
            if correlation_context.get("data_quality") == "unavailable":
                return {
                    "divergence_detected": False,
                    "correlation": None,
                    "dxy_direction": None,
                    "symbol_direction": None,
                    "data_quality": "unavailable"
                }
            
            corr_dxy = correlation_context.get("corr_vs_dxy")
            if corr_dxy is None:
                return {
                    "divergence_detected": False,
                    "correlation": None,
                    "dxy_direction": None,
                    "symbol_direction": None,
                    "data_quality": correlation_context.get("data_quality", "unavailable")
                }
            
            # Check if correlation is negative enough (divergence)
            divergence_detected = corr_dxy < divergence_threshold
            
            # Determine direction of movement for both DXY and symbol
            # Fetch recent price movements to determine direction
            try:
                # Get symbol price change
                if self.mt5_service:
                    symbol_norm = symbol.upper().rstrip('Cc') + 'c'
                    symbol_bars = self.mt5_service.get_bars(symbol_norm, "M5", window_minutes // 5 + 5)
                    if symbol_bars and len(symbol_bars) >= 2:
                        symbol_start = float(symbol_bars['close'].iloc[0])
                        symbol_end = float(symbol_bars['close'].iloc[-1])
                        symbol_change_pct = ((symbol_end - symbol_start) / symbol_start) * 100
                        if symbol_change_pct > 0.1:
                            symbol_direction = "up"
                        elif symbol_change_pct < -0.1:
                            symbol_direction = "down"
                        else:
                            symbol_direction = "neutral"
                    else:
                        symbol_direction = "unknown"
                else:
                    symbol_direction = "unknown"
                
                # Get DXY price change
                try:
                    import yfinance as yf
                    dxy = yf.Ticker("DX-Y.NYB")
                    bars_needed = max(12, window_minutes // 5)
                    hist = dxy.history(period="2d", interval="5m")
                    
                    if len(hist) >= bars_needed:
                        dxy_start = float(hist['Close'].iloc[-bars_needed])
                        dxy_end = float(hist['Close'].iloc[-1])
                        dxy_change_pct = ((dxy_end - dxy_start) / dxy_start) * 100
                        if dxy_change_pct > 0.05:
                            dxy_direction = "up"
                        elif dxy_change_pct < -0.05:
                            dxy_direction = "down"
                        else:
                            dxy_direction = "neutral"
                    else:
                        dxy_direction = "unknown"
                except Exception as e:
                    logger.debug(f"Could not determine DXY direction: {e}")
                    dxy_direction = "unknown"
                
            except Exception as e:
                logger.debug(f"Could not determine symbol direction: {e}")
                symbol_direction = "unknown"
                dxy_direction = "unknown"
            
            return {
                "divergence_detected": divergence_detected,
                "correlation": corr_dxy,
                "dxy_direction": dxy_direction,
                "symbol_direction": symbol_direction,
                "data_quality": correlation_context.get("data_quality", "limited")
            }
            
        except Exception as e:
            logger.error(f"Error in detect_dxy_divergence: {e}", exc_info=True)
            return {
                "divergence_detected": False,
                "correlation": None,
                "dxy_direction": None,
                "symbol_direction": None,
                "data_quality": "unavailable"
            }
    
    async def detect_dxy_stall(self, window_minutes: int = 60) -> bool:
        """
        Detect DXY momentum stall (deceleration).
        
        Args:
            window_minutes: Time window in minutes (default: 60 = 1 hour)
        
        Returns:
            True if stall detected, False otherwise
        """
        try:
            if not self.market_indices:
                return False
            
            try:
                import yfinance as yf
                import numpy as np
                
                dxy = yf.Ticker("DX-Y.NYB")
                # Get enough bars for momentum calculation (need 10-20 periods)
                hist = dxy.history(period="2d", interval="5m")
                
                if len(hist) < 20:
                    return False
                
                closes = hist['Close'].tail(20).values
                
                # Calculate rate of change over rolling window
                # Use last 10-20 periods for momentum calculation
                window_size = min(20, len(closes))
                recent_closes = closes[-window_size:]
                
                # Calculate momentum (rate of change)
                if len(recent_closes) < 10:
                    return False
                
                # Calculate momentum slope using linear regression
                x = np.arange(len(recent_closes))
                y = recent_closes
                
                # Simple linear regression
                n = len(x)
                sum_x = np.sum(x)
                sum_y = np.sum(y)
                sum_xy = np.sum(x * y)
                sum_x2 = np.sum(x * x)
                
                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                
                # Calculate peak momentum (from first half vs second half)
                mid_point = len(recent_closes) // 2
                first_half = recent_closes[:mid_point]
                second_half = recent_closes[mid_point:]
                
                if len(first_half) < 5 or len(second_half) < 5:
                    return False
                
                # Calculate momentum for each half
                x1 = np.arange(len(first_half))
                y1 = first_half
                n1 = len(x1)
                sum_x1 = np.sum(x1)
                sum_y1 = np.sum(y1)
                sum_xy1 = np.sum(x1 * y1)
                sum_x2_1 = np.sum(x1 * x1)
                slope1 = (n1 * sum_xy1 - sum_x1 * sum_y1) / (n1 * sum_x2_1 - sum_x1 * sum_x1) if (n1 * sum_x2_1 - sum_x1 * sum_x1) != 0 else 0
                
                x2 = np.arange(len(second_half))
                y2 = second_half
                n2 = len(x2)
                sum_x2 = np.sum(x2)
                sum_y2 = np.sum(y2)
                sum_xy2 = np.sum(x2 * y2)
                sum_x2_2 = np.sum(x2 * x2)
                slope2 = (n2 * sum_xy2 - sum_x2 * sum_y2) / (n2 * sum_x2_2 - sum_x2 * sum_x2) if (n2 * sum_x2_2 - sum_x2 * sum_x2) != 0 else 0
                
                # Detect deceleration: slope becomes negative OR drops >50% from peak
                peak_slope = max(abs(slope1), abs(slope2))
                current_slope = abs(slope)
                
                # Stall detected if: slope negative OR current slope < 50% of peak
                stall_detected = slope < 0 or (peak_slope > 0 and current_slope < peak_slope * 0.5)
                
                return bool(stall_detected)
                
            except Exception as e:
                logger.error(f"Error detecting DXY stall: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error in detect_dxy_stall: {e}", exc_info=True)
            return False
    
    async def calculate_ethbtc_ratio_deviation(self) -> Optional[Dict[str, Any]]:
        """
        Calculate ETH/BTC ratio and deviation from mean.
        
        Returns:
            {
                "ratio": 0.0625,  # Current ETH/BTC ratio
                "deviation": 1.5,  # Deviation in standard deviations
                "direction": "bullish" | "bearish" | None
            } or None if unavailable
        """
        try:
            if not self.mt5_service:
                logger.warning("MT5 service not available for ETH/BTC ratio")
                return None
            
            # Try to get ETH price from Binance API first (more reliable for crypto)
            try:
                import requests
                eth_response = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT", timeout=5)
                btc_response = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5)
                
                if eth_response.status_code == 200 and btc_response.status_code == 200:
                    eth_price = float(eth_response.json()['price'])
                    btc_price = float(btc_response.json()['price'])
                    current_ratio = eth_price / btc_price
                else:
                    raise Exception("Binance API failed")
            except Exception:
                # Fallback to MT5 if Binance unavailable
                try:
                    eth_bars = await self._fetch_symbol_bars("ETHUSDc", 100)
                    btc_bars = await self._fetch_symbol_bars("BTCUSDc", 100)
                    
                    if eth_bars is None or btc_bars is None or len(eth_bars) == 0 or len(btc_bars) == 0:
                        return None
                    
                    eth_price = float(eth_bars['close'].iloc[-1])
                    btc_price = float(btc_bars['close'].iloc[-1])
                    current_ratio = eth_price / btc_price
                except Exception as e:
                    logger.warning(f"Could not get ETH/BTC prices: {e}")
                    return None
            
            # Calculate historical ratio mean and std dev (last 100 periods)
            try:
                eth_bars = await self._fetch_symbol_bars("ETHUSDc", 100)
                btc_bars = await self._fetch_symbol_bars("BTCUSDc", 100)
                
                if eth_bars is None or btc_bars is None or len(eth_bars) < 20 or len(btc_bars) < 20:
                    # Use current ratio as mean if no history
                    return {
                        "ratio": current_ratio,
                        "deviation": 0.0,
                        "direction": None
                    }
                
                # Align bars by time
                min_len = min(len(eth_bars), len(btc_bars))
                eth_closes = eth_bars['close'].tail(min_len).values
                btc_closes = btc_bars['close'].tail(min_len).values
                
                # Calculate ratios
                ratios = eth_closes / btc_closes
                
                # Calculate mean and std dev
                mean_ratio = float(np.mean(ratios))
                std_ratio = float(np.std(ratios))
                
                if std_ratio == 0:
                    deviation = 0.0
                else:
                    deviation = (current_ratio - mean_ratio) / std_ratio
                
                # Determine direction
                if deviation > 0.5:
                    direction = "bullish"  # ETH outperforming BTC
                elif deviation < -0.5:
                    direction = "bearish"  # ETH underperforming BTC
                else:
                    direction = None
                
                return {
                    "ratio": round(current_ratio, 6),
                    "deviation": round(deviation, 2),
                    "direction": direction
                }
                
            except Exception as e:
                logger.error(f"Error calculating ETH/BTC ratio deviation: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error in calculate_ethbtc_ratio_deviation: {e}", exc_info=True)
            return None
    
    async def get_nasdaq_15min_trend(self) -> Optional[Dict[str, Any]]:
        """
        Get NASDAQ 15-minute trend (bullish/bearish).
        
        Returns:
            {
                "trend": "bullish" | "bearish" | "neutral",
                "nasdaq_15min_bullish": bool,
                "nasdaq_correlation_confirmed": bool  # If correlation aligns with expected pattern
            } or None if unavailable
        """
        try:
            if not self.market_indices:
                return None
            
            nasdaq_data = self.market_indices.get_nasdaq()
            if not nasdaq_data or 'trend' not in nasdaq_data:
                return None
            
            trend = nasdaq_data['trend']
            nasdaq_15min_bullish = trend == "up"
            
            # Check correlation confirmation (for BTCUSD, NASDAQ up = bullish)
            nasdaq_correlation_confirmed = nasdaq_15min_bullish  # Simplified - can enhance with actual correlation check
            
            return {
                "trend": "bullish" if nasdaq_15min_bullish else "bearish" if trend == "down" else "neutral",
                "nasdaq_15min_bullish": nasdaq_15min_bullish,
                "nasdaq_correlation_confirmed": nasdaq_correlation_confirmed
            }
            
        except Exception as e:
            logger.error(f"Error getting NASDAQ 15-min trend: {e}", exc_info=True)
            return None
    
    async def check_btc_hold_above_support(self, symbol: str = "BTCUSDc") -> bool:
        """
        Check if BTC holds above support level.
        
        Support definition (priority order):
        1. Recent swing low (last 20-50 bars)
        2. Order block (bullish OB)
        3. VWAP level
        
        Args:
            symbol: Trading symbol (default: BTCUSDc)
        
        Returns:
            True if price holds above support, False otherwise
        """
        try:
            if not self.mt5_service:
                return False
            
            # Fetch recent bars for structure detection
            bars = await self._fetch_symbol_bars(symbol, 50)
            if bars is None or len(bars) < 20:
                return False
            
            current_price = float(bars['close'].iloc[-1])
            lows = bars['low'].tail(20).values
            
            # 1. Find recent swing low (last 20 bars)
            swing_low = float(np.min(lows))
            
            # 2. Check if price holds above swing low by at least 0.1% (or 0.2 ATR)
            # Calculate ATR for normalization
            try:
                highs = bars['high'].tail(20).values
                closes = bars['close'].tail(20).values
                atr = np.mean(np.maximum(highs - lows, np.abs(highs - np.roll(closes, 1))))
            except:
                atr = None
            
            # Check hold: price > support by 0.1% or 0.2 ATR
            if atr and atr > 0:
                hold_threshold = swing_low + (atr * 0.2)
            else:
                hold_threshold = swing_low * 1.001  # 0.1% above support
            
            holds_above = current_price > hold_threshold
            
            # Also check that price hasn't broken below support in last 10-20 bars
            recent_lows = bars['low'].tail(10).values
            never_broke_below = np.all(recent_lows >= swing_low * 0.999)  # Allow 0.1% tolerance for wicks
            
            return bool(holds_above and never_broke_below)
            
        except Exception as e:
            logger.error(f"Error checking BTC hold above support: {e}", exc_info=True)
            return False

