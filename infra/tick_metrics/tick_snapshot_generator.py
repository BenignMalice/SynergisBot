"""
Tick Snapshot Generator

Background async loop that maintains fresh tick metrics for all configured symbols.
Fetches ticks, calculates metrics, and updates cache every 60 seconds.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

from .tick_data_fetcher import TickDataFetcher
from .tick_metrics_calculator import TickMetricsCalculator
from .tick_metrics_cache import TickMetricsCache

logger = logging.getLogger(__name__)


class TickSnapshotGenerator:
    """Background generator that maintains fresh tick metrics."""
    
    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        update_interval_seconds: int = 60,
        config_path: str = "config/tick_metrics_config.json"
    ):
        """
        Initialize tick snapshot generator.
        
        Args:
            symbols: List of symbols to monitor (default: from config)
            update_interval_seconds: Update interval in seconds (default: 60)
            config_path: Path to configuration file
        """
        # Load configuration
        if config_path:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    self.config = json.load(f)
            else:
                logger.warning(f"Config file not found: {config_path}, using defaults")
                self.config = self._get_default_config()
        else:
            logger.debug("No config path provided, using defaults")
            self.config = self._get_default_config()
        
        # Override with constructor params if provided
        self.symbols = symbols or self.config.get("symbols", ["BTCUSDc", "XAUUSDc"])
        self.update_interval = update_interval_seconds or self.config.get("update_interval_seconds", 60)
        
        # Initialize components
        self.tick_fetcher = TickDataFetcher()
        # Pass thresholds dict, not full config
        thresholds = self.config.get("thresholds", {})
        self.calculator = TickMetricsCalculator(config={"thresholds": thresholds})
        self.cache = TickMetricsCache(
            db_path=self.config.get("cache", {}).get("database_path"),
            memory_ttl_seconds=self.config.get("cache", {}).get("memory_ttl_seconds", 60),
            db_retention_hours=self.config.get("cache", {}).get("db_retention_hours", 24)
        )
        
        # Background task state
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._cycle_count = 0  # For cleanup scheduling
        # Initialize loading state for all symbols
        self._previous_day_loading: Dict[str, bool] = {s: False for s in self.symbols}
        self._previous_day_cache: Dict[str, Dict[str, Any]] = {}  # Cache previous_day metrics
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration when config file is missing."""
        return {
            "symbols": ["BTCUSDc", "XAUUSDc", "EURUSDc", "USDJPYc", "GBPUSDc"],
            "update_interval_seconds": 60,
            "cache": {
                "database_path": "data/unified_tick_pipeline/tick_metrics_cache.db",
                "memory_ttl_seconds": 60,
                "db_retention_hours": 24
            },
            "thresholds": {
                "absorption_volume_multiplier": 2.0,
                "liquidity_void_spread_multiplier": 3.0,
                "cvd_slope_threshold": 0.1
            }
        }
    
    async def start(self):
        """Start the background update loop."""
        if self._running:
            logger.warning("Tick snapshot generator already running")
            return
        
        self._running = True
        logger.info("Starting Tick Snapshot Generator")
        logger.info(f"   Symbols: {', '.join(self.symbols)}")
        logger.info(f"   Update interval: {self.update_interval} seconds")
        
        # Start main update loop
        self._task = asyncio.create_task(self._update_loop())
        
        # Start previous_day computation after 5 seconds (non-blocking)
        asyncio.create_task(self._previous_day_loader())
    
    async def stop(self):
        """Stop the background update loop."""
        logger.info("Stopping Tick Snapshot Generator")
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Tick Snapshot Generator stopped")
    
    async def _update_loop(self):
        """Main update loop - runs continuously until stopped."""
        try:
            # Run first cycle immediately
            logger.info("Running initial tick metrics update cycle...")
            await self._update_cycle()
            
            while self._running:
                try:
                    # Sleep until next cycle
                    await asyncio.sleep(self.update_interval)
                    
                    if not self._running:
                        break
                    
                    await self._update_cycle()
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in update cycle: {e}", exc_info=True)
                    # Continue running despite errors
                    await asyncio.sleep(self.update_interval)
                    
        except Exception as fatal_error:
            logger.critical(f"FATAL ERROR in tick snapshot generator: {fatal_error}", exc_info=True)
        finally:
            logger.info("Tick snapshot generator update loop stopped")
    
    async def _update_cycle(self):
        """Single update cycle for all symbols."""
        self._cycle_count += 1
        logger.info(f"Running tick metrics update cycle #{self._cycle_count} for {len(self.symbols)} symbol(s)...")
        
        for symbol in self.symbols:
            try:
                logger.debug(f"Computing metrics for {symbol}...")
                metrics = await self._compute_symbol_metrics(symbol)
                if metrics:
                    self.cache.set(symbol, metrics)
                    metadata = metrics.get("metadata", {})
                    data_available = metadata.get("data_available", False)
                    if data_available:
                        m5_count = metrics.get("M5", {}).get("tick_count", 0)
                        logger.info(f"Tick metrics updated for {symbol}: {m5_count} M5 ticks, data_available=True")
                    else:
                        logger.warning(f"Tick metrics updated for {symbol}: data_available=False, market_status={metadata.get('market_status')}")
            except Exception as e:
                logger.error(f"Error computing metrics for {symbol}: {e}", exc_info=True)
                # Store empty metrics to prevent cache misses
                try:
                    empty_metrics = self._empty_metrics(symbol, reason="error")
                    self.cache.set(symbol, empty_metrics)
                except Exception as cache_error:
                    logger.error(f"Error storing empty metrics for {symbol}: {cache_error}", exc_info=True)
                # Continue with next symbol
        
        # Run cleanup every 60 cycles (once per hour if update_interval=60s)
        if self._cycle_count % 60 == 0:
            try:
                self.cache.cleanup_expired()
                logger.debug("Tick metrics cache cleanup completed")
            except Exception as e:
                logger.warning(f"Error during cache cleanup: {e}", exc_info=True)
    
    async def _compute_symbol_metrics(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Compute tick metrics for a single symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Complete metrics dictionary or None if failed
        """
        loop = asyncio.get_event_loop()
        
        # Wrap synchronous MT5 tick fetching in executor to avoid blocking event loop
        ticks = await loop.run_in_executor(
            None,
            lambda: self.tick_fetcher.fetch_previous_hour_ticks(symbol)
        )
        
        if not ticks or len(ticks) == 0:
            return self._empty_metrics(symbol, reason="no_ticks")
        
        # Calculate metrics for different timeframes
        now = datetime.utcnow()
        now_timestamp = now.timestamp()
        
        # M5: Last 5 minutes
        m5_ticks = [t for t in ticks if abs(now_timestamp - t.get('time', 0)) <= 300]
        m5_metrics = self.calculator.calculate_all_metrics(m5_ticks, timeframe="M5") if m5_ticks else self.calculator._empty_metrics()
        
        # M15: Last 15 minutes
        m15_ticks = [t for t in ticks if abs(now_timestamp - t.get('time', 0)) <= 900]
        m15_metrics = self.calculator.calculate_all_metrics(m15_ticks, timeframe="M15") if m15_ticks else self.calculator._empty_metrics()
        
        # H1: Last 60 minutes (all ticks in the hour window)
        h1_metrics = self.calculator.calculate_all_metrics(ticks, timeframe="H1") if ticks else self.calculator._empty_metrics()
        
        # Previous hour: Complete previous clock hour
        prev_hour_ticks = await loop.run_in_executor(
            None,
            lambda: self.tick_fetcher.fetch_previous_clock_hour_ticks(symbol)
        )
        previous_hour_metrics = {}
        if prev_hour_ticks and len(prev_hour_ticks) > 0:
            prev_hour_calc = self.calculator.calculate_all_metrics(prev_hour_ticks, timeframe="previous_hour")
            previous_hour_metrics = {
                "tick_count": len(prev_hour_ticks),
                "avg_tick_rate": prev_hour_calc.get("tick_rate", 0.0),
                "net_delta": prev_hour_calc.get("delta_volume", 0.0),
                "cvd_trend": prev_hour_calc.get("cvd_slope", "flat"),
                "dominant_side": prev_hour_calc.get("dominant_side", "NEUTRAL"),
                "spread_regime": "normal" if prev_hour_calc.get("spread", {}).get("mean", 0) < 5.0 else "wide",
                "volatility_state": "stable" if prev_hour_calc.get("volatility_ratio", 1.0) < 1.2 else "expanding",
                "absorption_zones": prev_hour_calc.get("absorption", {}).get("zones", [])
            }
        
        # Previous day: Use cached value if available
        previous_day_metrics = self._previous_day_cache.get(symbol)
        previous_day_loading = self._previous_day_loading.get(symbol, False)
        
        # Calculate volatility ratios using previous_day as baseline
        if previous_day_metrics and previous_day_metrics.get("realized_volatility"):
            baseline_vol = previous_day_metrics["realized_volatility"]
            m5_metrics["volatility_ratio"] = self.calculator._calculate_volatility_ratio(
                m5_metrics.get("realized_volatility", 0.0),
                baseline_vol
            )
            m15_metrics["volatility_ratio"] = self.calculator._calculate_volatility_ratio(
                m15_metrics.get("realized_volatility", 0.0),
                baseline_vol
            )
            h1_metrics["volatility_ratio"] = self.calculator._calculate_volatility_ratio(
                h1_metrics.get("realized_volatility", 0.0),
                baseline_vol
            )
        
        # Build complete metrics structure
        result = {
            "M5": m5_metrics,
            "M15": m15_metrics,
            "H1": h1_metrics,
            "previous_hour": previous_hour_metrics,
            "previous_day": previous_day_metrics,
            "metadata": {
                "symbol": symbol,
                "last_updated": datetime.utcnow().isoformat(),
                "data_available": True,
                "market_status": "open",
                "previous_day_loading": previous_day_loading,
                "trade_tick_ratio": h1_metrics.get("trade_tick_ratio", 0.0)
            }
        }
        
        return result
    
    async def _previous_day_loader(self):
        """Load previous day metrics asynchronously (non-blocking startup)."""
        # Wait 5 seconds after startup to avoid blocking API readiness
        await asyncio.sleep(5)
        
        logger.info("Starting previous_day tick metrics computation...")
        
        for symbol in self.symbols:
            self._previous_day_loading[symbol] = True
            
            try:
                loop = asyncio.get_event_loop()
                
                # Fetch previous day ticks (may take 10-30 seconds for large symbols)
                ticks = await loop.run_in_executor(
                    None,
                    lambda: self.tick_fetcher.fetch_previous_day_ticks(symbol)
                )
                
                if ticks and len(ticks) > 0:
                    # Calculate previous day metrics
                    prev_day_metrics = self.calculator.calculate_all_metrics(ticks, timeframe="previous_day")
                    
                    # Add session breakdown (simplified - can be enhanced later)
                    prev_day_metrics["total_ticks"] = len(ticks)
                    
                    self._previous_day_cache[symbol] = prev_day_metrics
                    logger.info(f"Previous day metrics computed for {symbol}: {len(ticks)} ticks")
                    
                    # Update the cached metrics to include previous_day
                    cached_metrics = self.cache.get(symbol)
                    if cached_metrics:
                        cached_metrics['previous_day'] = prev_day_metrics
                        cached_metrics['metadata']['previous_day_loading'] = False
                        self.cache.set(symbol, cached_metrics)
                        logger.debug(f"Updated cached metrics for {symbol} with previous_day data")
                else:
                    logger.warning(f"No previous day ticks found for {symbol}")
                    self._previous_day_cache[symbol] = None
                    # Update cached metrics to mark previous_day as unavailable
                    cached_metrics = self.cache.get(symbol)
                    if cached_metrics:
                        cached_metrics['previous_day'] = None
                        cached_metrics['metadata']['previous_day_loading'] = False
                        self.cache.set(symbol, cached_metrics)
                    
            except Exception as e:
                logger.error(f"Error computing previous_day metrics for {symbol}: {e}", exc_info=True)
                self._previous_day_cache[symbol] = None
            finally:
                self._previous_day_loading[symbol] = False
        
        # Refresh previous_day metrics once per hour
        while self._running:
            await asyncio.sleep(3600)  # 1 hour
            
            for symbol in self.symbols:
                try:
                    loop = asyncio.get_event_loop()
                    ticks = await loop.run_in_executor(
                        None,
                        lambda: self.tick_fetcher.fetch_previous_day_ticks(symbol)
                    )
                    
                    if ticks and len(ticks) > 0:
                        prev_day_metrics = self.calculator.calculate_all_metrics(ticks, timeframe="previous_day")
                        prev_day_metrics["total_ticks"] = len(ticks)
                        self._previous_day_cache[symbol] = prev_day_metrics
                        logger.debug(f"Previous day metrics refreshed for {symbol}")
                        
                except Exception as e:
                    logger.error(f"Error refreshing previous_day metrics for {symbol}: {e}", exc_info=True)
    
    def get_latest_metrics(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get latest cached metrics for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Metrics dictionary or None if not available
        """
        return self.cache.get(symbol)
    
    def _empty_metrics(self, symbol: str, reason: str = "unknown") -> Dict[str, Any]:
        """Return empty metrics structure when data is unavailable."""
        return {
            "M5": {},
            "M15": {},
            "H1": {},
            "previous_hour": {},
            "previous_day": None,  # May still be loading
            "metadata": {
                "symbol": symbol,
                "last_updated": datetime.utcnow().isoformat(),
                "data_available": False,
                "market_status": "closed" if reason == "no_ticks" else "error",
                "reason": reason,
                "previous_day_loading": self._previous_day_loading.get(symbol, False),
                "trade_tick_ratio": 0.0
            }
        }

