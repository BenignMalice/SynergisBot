"""
Micro-Scalp Engine (Orchestrator)

Main orchestrator for micro-scalp strategy:
- Fetches data (M1 candles, VWAP, spread, volatility, BTC order flow)
- Builds snapshot
- Checks conditions (4-layer validation)
- Executes trades
- Integrates with auto-execution system
"""

from __future__ import annotations

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from infra.micro_scalp_conditions import MicroScalpConditionsChecker, ConditionCheckResult
from infra.micro_scalp_execution import MicroScalpExecutionManager
from infra.micro_scalp_volatility_filter import MicroScalpVolatilityFilter
from infra.vwap_micro_filter import VWAPMicroFilter
from infra.micro_liquidity_sweep_detector import MicroLiquiditySweepDetector
from infra.micro_order_block_detector import MicroOrderBlockDetector
from infra.spread_tracker import SpreadTracker
from infra.m1_data_fetcher import M1DataFetcher
from infra.mt5_service import MT5Service

logger = logging.getLogger(__name__)


class MicroScalpEngine:
    """
    Main orchestrator for micro-scalp strategy.
    
    Responsibilities:
    - Data fetching and snapshot building
    - Condition validation (4-layer system)
    - Trade execution
    - Integration with auto-execution system
    """
    
    def __init__(self, config_path: str = "config/micro_scalp_config.json",
                 mt5_service: Optional[MT5Service] = None,
                 m1_fetcher: Optional[M1DataFetcher] = None,
                 streamer=None,  # NEW: MultiTimeframeStreamer
                 m1_analyzer=None,
                 session_manager=None,
                 btc_order_flow=None,
                 news_service=None):  # NEW: NewsService
        """
        Initialize Micro-Scalp Engine.
        
        Args:
            config_path: Path to configuration file
            mt5_service: Optional MT5Service instance
            m1_fetcher: Optional M1DataFetcher instance
            streamer: Optional MultiTimeframeStreamer instance (for M5/M15 data)
            m1_analyzer: Optional M1MicrostructureAnalyzer instance
            session_manager: Optional session manager
            btc_order_flow: Optional BTCOrderFlowMetrics instance
            news_service: Optional NewsService instance (for news blackout checks)
        """
        # Load config
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            self.config = {}
        
        # Initialize dependencies
        self.mt5_service = mt5_service
        self.m1_fetcher = m1_fetcher
        self.streamer = streamer  # NEW: For M5/M15 data
        self.m1_analyzer = m1_analyzer
        self.session_manager = session_manager
        self.btc_order_flow = btc_order_flow
        self.news_service = news_service  # NEW: For news blackout checks
        
        # Initialize components
        self.spread_tracker = SpreadTracker()
        self.volatility_filter = MicroScalpVolatilityFilter(self.config)
        self.vwap_filter = VWAPMicroFilter(
            tolerance_type=self.config.get('xauusd_rules', {}).get('vwap_tolerance_type', 'fixed'),
            tolerance_fixed=self.config.get('xauusd_rules', {}).get('vwap_tolerance_fixed', 0.0005),
            tolerance_atr_multiplier=self.config.get('xauusd_rules', {}).get('vwap_tolerance_atr_multiplier', 0.1)
        )
        self.sweep_detector = MicroLiquiditySweepDetector(lookback=10)
        self.ob_detector = MicroOrderBlockDetector(lookback=3)
        
        # Initialize conditions checker (kept for backward compatibility)
        self.conditions_checker = MicroScalpConditionsChecker(
            config=self.config,
            volatility_filter=self.volatility_filter,
            vwap_filter=self.vwap_filter,
            sweep_detector=self.sweep_detector,
            ob_detector=self.ob_detector,
            spread_tracker=self.spread_tracker,
            m1_analyzer=m1_analyzer,
            session_manager=session_manager
        )
        
        # NEW: Initialize regime detector
        try:
            from infra.micro_scalp_regime_detector import MicroScalpRegimeDetector
            from infra.micro_scalp_strategy_router import MicroScalpStrategyRouter
            from infra.range_boundary_detector import RangeBoundaryDetector
            
            range_detector = RangeBoundaryDetector(self.config.get("range_detection", {}))
            
            self.regime_detector = MicroScalpRegimeDetector(
                config=self.config,
                m1_analyzer=m1_analyzer,
                vwap_filter=self.vwap_filter,
                range_detector=range_detector,
                volatility_filter=self.volatility_filter,
                streamer=streamer,
                news_service=news_service,
                mt5_service=mt5_service
            )
            
            self.strategy_router = MicroScalpStrategyRouter(
                config=self.config,
                regime_detector=self.regime_detector,
                m1_analyzer=m1_analyzer
            )
            
            # Strategy checker registry
            self.strategy_checkers = {}
            
            logger.info("Adaptive micro-scalp system initialized (regime detector + router)")
        except Exception as e:
            logger.warning(f"Failed to initialize adaptive system: {e}. Using fallback edge-based mode.")
            self.regime_detector = None
            self.strategy_router = None
            self.strategy_checkers = {}
        
        # Initialize execution manager
        if mt5_service and m1_fetcher:
            self.execution_manager = MicroScalpExecutionManager(
                config=self.config,
                mt5_service=mt5_service,
                spread_tracker=self.spread_tracker,
                m1_fetcher=m1_fetcher
            )
        else:
            self.execution_manager = None
            logger.warning("MT5Service or M1DataFetcher not provided - execution disabled")
        
        logger.info("MicroScalpEngine initialized")
    
    def check_micro_conditions(self, symbol: str, plan_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Check micro-scalp conditions for a symbol using adaptive strategy selection.
        
        This is the main entry point for condition checking.
        Called by auto-execution system when monitoring micro-scalp plans.
        
        NEW: Uses adaptive strategy selection based on market regime detection.
        
        Args:
            symbol: Trading symbol
            plan_id: Optional plan ID for logging
        
        Returns:
            Dict with:
            - passed: bool
            - result: ConditionCheckResult
            - snapshot: Dict (data snapshot)
            - trade_idea: Optional Dict (if conditions passed)
            - strategy: str (selected strategy name)
            - regime: str (detected regime)
            - plan_id: Optional[str] (plan ID if provided)
        """
        try:
            # Build snapshot
            snapshot = self._build_snapshot(symbol)
            
            if not snapshot:
                return {
                    'passed': False,
                    'result': None,
                    'snapshot': None,
                    'trade_idea': None,
                    'error': 'Failed to build snapshot',
                    'plan_id': plan_id
                }
            
            # NEW: Store plan_id in snapshot for reference
            if plan_id:
                snapshot['plan_id'] = plan_id
            
            # NEW: Detect regime (with error handling)
            try:
                if not self.regime_detector:
                    logger.warning(f"[{symbol}] Regime detector not initialized, using edge-based fallback")
                    strategy_name = 'edge_based'
                    regime_result = {'regime': 'UNKNOWN', 'detected': False, 'confidence': 0, 'reason': 'regime_detector_not_initialized'}
                else:
                    regime_result = self.regime_detector.detect_regime(snapshot)
                    snapshot['regime_result'] = regime_result
                    
                    # Log regime detection result for debugging
                    regime = regime_result.get('regime')
                    confidence = regime_result.get('confidence', 0)
                    detected = regime_result.get('detected', False)
                    
                    # Convert None to 'UNKNOWN' for display
                    regime_display = regime if regime else 'UNKNOWN'
                    
                    if regime is None or confidence == 0:
                        # Log why regime detection failed with detailed breakdown
                        vwap_result = regime_result.get('vwap_reversion_result', {})
                        range_result = regime_result.get('range_result', {})
                        balanced_result = regime_result.get('balanced_zone_result', {})
                        reason = regime_result.get('reason', 'No regime met confidence thresholds')
                        logger.info(f"[{symbol}] ⚠️ Regime UNKNOWN - {reason}")
                        logger.info(f"[{symbol}]   VWAP Reversion: {vwap_result.get('confidence', 0)}% (threshold: {vwap_result.get('min_confidence_threshold', 70)}%)")
                        logger.info(f"[{symbol}]   Range Scalp: {range_result.get('confidence', 0)}% (threshold: {range_result.get('min_confidence_threshold', 55)}%)")
                        logger.info(f"[{symbol}]   Balanced Zone: {balanced_result.get('confidence', 0)}% (threshold: {balanced_result.get('min_confidence_threshold', 60)}%)")
                        
                        # Log specific failure reasons for each regime
                        if vwap_result.get('confidence', 0) == 0:
                            vwap_reason = vwap_result.get('reason', 'Price too close to VWAP or missing conditions')
                            logger.info(f"[{symbol}]     VWAP failure: {vwap_reason}")
                        if range_result.get('confidence', 0) == 0:
                            range_reason = range_result.get('reason', 'No range structure or price not near edge')
                            logger.info(f"[{symbol}]     Range failure: {range_reason}")
                        if balanced_result.get('confidence', 0) < balanced_result.get('min_confidence_threshold', 60):
                            balanced_details = f"BB compression: {balanced_result.get('bb_compression', False)}, Compression block: {balanced_result.get('compression_block', False)}, ATR dropping: {balanced_result.get('atr_dropping', False)}, Equilibrium: {balanced_result.get('equilibrium_ok', False)}"
                            logger.info(f"[{symbol}]     Balanced Zone details: {balanced_details}")
                    else:
                        logger.debug(f"[{symbol}] ✅ Regime detected: {regime_display} (confidence: {confidence}%, detected: {detected})")
                    
                    # Ensure regime is set to 'UNKNOWN' if None for consistency
                    if regime is None:
                        regime_result['regime'] = 'UNKNOWN'
                    
                    # NEW: Extract key characteristics from regime_result for easy access
                    characteristics = regime_result.get('characteristics', {})
                    if 'range_structure' in characteristics:
                        snapshot['range_structure'] = characteristics['range_structure']
                    if 'vwap_deviation' in characteristics:
                        snapshot['vwap_deviation'] = characteristics['vwap_deviation']
                    if 'compression' in characteristics:
                        snapshot['compression'] = characteristics['compression']
                    if 'vwap_slope' in characteristics:
                        snapshot['vwap_slope'] = characteristics['vwap_slope']
                    if 'bb_compression' in characteristics:
                        snapshot['bb_compression'] = characteristics['bb_compression']
                    
                    # NEW: Select strategy (with error handling)
                    try:
                        if not self.strategy_router:
                            logger.warning("Strategy router not initialized, using edge-based fallback")
                            strategy_name = 'edge_based'
                        else:
                            strategy_name = self.strategy_router.select_strategy(snapshot, regime_result)
                    except Exception as e:
                        logger.error(f"Error in strategy routing: {e}", exc_info=True)
                        # Fallback to edge-based
                        strategy_name = 'edge_based'
            except Exception as e:
                logger.error(f"Error in regime detection: {e}", exc_info=True)
                # Fallback to edge-based
                strategy_name = 'edge_based'
                regime_result = {'regime': 'UNKNOWN', 'detected': False, 'confidence': 0, 'error': str(e)}
            
            snapshot['strategy'] = strategy_name
            
            # NEW: Get strategy-specific checker (with error handling)
            try:
                checker = self._get_strategy_checker(strategy_name)
            except Exception as e:
                logger.error(f"Error getting strategy checker: {e}", exc_info=True)
                # Fallback to edge-based
                checker = self._get_strategy_checker('edge_based')
            
            # Check conditions using strategy-specific checker
            result = checker.validate(snapshot)
            
            if not result.passed:
                return {
                    'passed': False,
                    'result': result,
                    'snapshot': snapshot,
                    'strategy': strategy_name,
                    'regime': regime_result.get('regime'),
                    'reasons': result.reasons,
                    'plan_id': plan_id
                }
            
            # NEW: Generate strategy-specific trade idea
            trade_idea = checker.generate_trade_idea(snapshot, result)
            
            # Handle case where trade idea generation fails
            if not trade_idea:
                logger.warning(f"Trade idea generation failed for {symbol} with strategy {strategy_name}")
                return {
                    'passed': False,
                    'result': result,
                    'snapshot': snapshot,
                    'strategy': strategy_name,
                    'regime': regime_result.get('regime'),
                    'reasons': result.reasons + ['Trade idea generation failed'],
                    'error': 'Trade idea generation failed',
                    'plan_id': plan_id
                }
            
            # NEW: Validate trade idea has required fields
            required_fields = ['symbol', 'direction', 'entry_price', 'sl', 'tp']
            missing_fields = [f for f in required_fields if f not in trade_idea]
            if missing_fields:
                logger.error(f"Trade idea missing required fields: {missing_fields}")
                return {
                    'passed': False,
                    'result': result,
                    'snapshot': snapshot,
                    'strategy': strategy_name,
                    'regime': regime_result.get('regime'),
                    'reasons': result.reasons + [f'Missing trade idea fields: {missing_fields}'],
                    'error': 'Invalid trade idea',
                    'plan_id': plan_id
                }
            
            return {
                'passed': True,
                'result': result,
                'snapshot': snapshot,
                'trade_idea': trade_idea,
                'strategy': strategy_name,
                'regime': regime_result.get('regime'),
                'is_aplus': result.is_aplus_setup,
                'plan_id': plan_id
            }
            
        except Exception as e:
            logger.error(f"Error checking micro conditions for {symbol}: {e}", exc_info=True)
            return {
                'passed': False,
                'result': None,
                'snapshot': None,
                'trade_idea': None,
                'error': str(e),
                'plan_id': plan_id
            }
    
    def _build_snapshot(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Build data snapshot for condition checking.
        
        Fetches:
        - M1 candles (last 20-30)
        - M5 candles (from streamer, if available)
        - M15 candles (from streamer, if available)
        - Current price (bid/ask)
        - VWAP
        - VWAP std (standard deviation)
        - ATR(1)
        - ATR(14) - memoized for efficiency
        - Spread data
        - BTC order flow (if BTCUSD)
        """
        try:
            # Normalize symbol (case-insensitive check for 'c' suffix)
            symbol_norm = symbol.upper().rstrip('Cc')  # Remove any existing 'c' or 'C'
            symbol_norm = symbol_norm + 'c'  # Always add lowercase 'c'
            
            # Fetch M1 candles
            if not self.m1_fetcher:
                logger.error("M1DataFetcher not available")
                return None
            
            candles = self.m1_fetcher.fetch_m1_data(symbol_norm, count=30, use_cache=True)
            if not candles or len(candles) < 10:
                logger.warning(f"Insufficient M1 candles for {symbol_norm}: {len(candles) if candles else 0}")
                return None
            
            # NEW: Fetch M5 candles from streamer
            m5_candles = []
            if self.streamer and self.streamer.is_running:
                try:
                    m5_candle_objects = self.streamer.get_candles(symbol_norm, 'M5', limit=50)
                    if m5_candle_objects:
                        m5_candles = [self._candle_to_dict(c) for c in m5_candle_objects]
                        logger.debug(f"Fetched {len(m5_candles)} M5 candles for {symbol_norm}")
                except Exception as e:
                    logger.debug(f"Error fetching M5 candles: {e}")
            
            # NEW: Fetch M15 candles from streamer
            m15_candles = []
            if self.streamer and self.streamer.is_running:
                try:
                    m15_candle_objects = self.streamer.get_candles(symbol_norm, 'M15', limit=50)
                    if m15_candle_objects:
                        m15_candles = [self._candle_to_dict(c) for c in m15_candle_objects]
                        logger.debug(f"Fetched {len(m15_candles)} M15 candles for {symbol_norm}")
                except Exception as e:
                    logger.debug(f"Error fetching M15 candles: {e}")
            
            # Get current price
            if not self.mt5_service:
                logger.error("MT5Service not available")
                return None
            
            quote = self.mt5_service.get_quote(symbol_norm)
            if not quote:
                logger.error(f"Failed to get quote for {symbol_norm}")
                return None
            
            current_price = (quote.bid + quote.ask) / 2
            
            # Update spread tracker
            self.spread_tracker.update_spread(symbol_norm, quote.bid, quote.ask)
            spread_data = self.spread_tracker.get_spread_data(symbol_norm)
            
            # Calculate VWAP from M1 candles
            vwap = self._calculate_vwap_from_candles(candles)
            
            # NEW: Calculate VWAP std (standard deviation)
            vwap_std = 0.0
            try:
                # Use helper method from BaseStrategyChecker (will be available after integration)
                # For now, calculate directly
                import statistics
                typical_prices = []
                volumes = []
                for candle in candles[-20:]:
                    high = candle.get('high', 0)
                    low = candle.get('low', 0)
                    close = candle.get('close', 0)
                    volume = candle.get('volume', 0)
                    if volume > 0:
                        typical_price = (high + low + close) / 3
                        typical_prices.append(typical_price)
                        volumes.append(volume)
                if typical_prices and volumes:
                    total_volume = sum(volumes)
                    if total_volume > 0:
                        weighted_mean = sum(tp * vol for tp, vol in zip(typical_prices, volumes)) / total_volume
                        weighted_variance = sum(vol * (tp - weighted_mean) ** 2 for tp, vol in zip(typical_prices, volumes)) / total_volume
                        vwap_std = weighted_variance ** 0.5
            except Exception as e:
                logger.debug(f"Error getting VWAP std: {e}")
            
            # Calculate ATR(1)
            atr1 = self.volatility_filter.calculate_atr1(candles)
            
            # NEW: Calculate ATR(14) - memoized for efficiency
            atr14 = self.volatility_filter.calculate_atr14(candles)
            
            # Get BTC order flow (if BTCUSD)
            btc_order_flow = None
            if symbol_norm.upper().startswith('BTC') and self.btc_order_flow:
                try:
                    btc_order_flow = self.btc_order_flow.get_metrics()
                except Exception as e:
                    logger.debug(f"Error getting BTC order flow: {e}")
            
            snapshot = {
                'symbol': symbol_norm,
                'candles': candles,
                'm5_candles': m5_candles,  # NEW
                'm15_candles': m15_candles,  # NEW
                'current_price': current_price,
                'bid': quote.bid,
                'ask': quote.ask,
                'vwap': vwap,
                'vwap_std': vwap_std,  # NEW
                'atr1': atr1,
                'atr14': atr14,  # NEW: Memoized ATR14
                'spread_data': spread_data,
                'btc_order_flow': btc_order_flow,
                'timestamp': datetime.now()
            }
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error building snapshot for {symbol}: {e}", exc_info=True)
            return None
    
    def _candle_to_dict(self, candle) -> Dict[str, Any]:
        """
        Convert streamer candle object to dict.
        
        Handles both dict and object types from MultiTimeframeStreamer.
        """
        if isinstance(candle, dict):
            return candle
        
        # Assume object with attributes (from MultiTimeframeStreamer)
        if hasattr(candle, 'to_dict'):
            return candle.to_dict()
        elif hasattr(candle, '__dict__'):
            return candle.__dict__
        else:
            # Fallback: extract common fields
            return {
                'time': getattr(candle, 'time', None),
                'open': getattr(candle, 'open', 0.0),
                'high': getattr(candle, 'high', 0.0),
                'low': getattr(candle, 'low', 0.0),
                'close': getattr(candle, 'close', 0.0),
                'volume': getattr(candle, 'volume', 0),
                'spread': getattr(candle, 'spread', 0),
                'real_volume': getattr(candle, 'real_volume', 0)
            }
    
    def _calculate_vwap_from_candles(self, candles: List[Dict[str, Any]]) -> float:
        """
        Calculate VWAP from M1 candles.
        
        VWAP = Sum(Price × Volume) / Sum(Volume)
        Where Price = (High + Low + Close) / 3 (typical price)
        """
        if not candles:
            return 0.0
        
        total_pv = 0.0
        total_volume = 0.0
        
        for candle in candles:
            high = candle.get('high', 0)
            low = candle.get('low', 0)
            close = candle.get('close', 0)
            volume = candle.get('volume', 0)
            
            if volume <= 0:
                continue
            
            # Typical price
            typical_price = (high + low + close) / 3
            
            total_pv += typical_price * volume
            total_volume += volume
        
        if total_volume == 0:
            return 0.0
        
        return total_pv / total_volume
    
    def _get_strategy_checker(self, strategy_name: str):
        """
        Get or create strategy-specific checker with error handling.
        
        Args:
            strategy_name: Strategy name ('vwap_reversion', 'range_scalp', 'balanced_zone', 'edge_based')
        
        Returns:
            BaseStrategyChecker instance
        """
        if strategy_name in self.strategy_checkers:
            return self.strategy_checkers[strategy_name]
        
        try:
            # Import strategy checkers
            if strategy_name == 'vwap_reversion':
                from infra.micro_scalp_strategies.vwap_reversion_checker import VWAPReversionChecker
                checker = VWAPReversionChecker(
                    config=self.config,
                    volatility_filter=self.volatility_filter,
                    vwap_filter=self.vwap_filter,
                    sweep_detector=self.sweep_detector,
                    ob_detector=self.ob_detector,
                    spread_tracker=self.spread_tracker,
                    m1_analyzer=self.m1_analyzer,
                    session_manager=self.session_manager,
                    news_service=self.news_service,
                    strategy_name='vwap_reversion'
                )
            elif strategy_name == 'range_scalp':
                from infra.micro_scalp_strategies.range_scalp_checker import RangeScalpChecker
                checker = RangeScalpChecker(
                    config=self.config,
                    volatility_filter=self.volatility_filter,
                    vwap_filter=self.vwap_filter,
                    sweep_detector=self.sweep_detector,
                    ob_detector=self.ob_detector,
                    spread_tracker=self.spread_tracker,
                    m1_analyzer=self.m1_analyzer,
                    session_manager=self.session_manager,
                    news_service=self.news_service,
                    strategy_name='range_scalp'
                )
            elif strategy_name == 'balanced_zone':
                from infra.micro_scalp_strategies.balanced_zone_checker import BalancedZoneChecker
                checker = BalancedZoneChecker(
                    config=self.config,
                    volatility_filter=self.volatility_filter,
                    vwap_filter=self.vwap_filter,
                    sweep_detector=self.sweep_detector,
                    ob_detector=self.ob_detector,
                    spread_tracker=self.spread_tracker,
                    m1_analyzer=self.m1_analyzer,
                    session_manager=self.session_manager,
                    news_service=self.news_service,
                    strategy_name='balanced_zone'
                )
            else:  # edge_based (fallback)
                from infra.micro_scalp_strategies.edge_based_checker import EdgeBasedChecker
                checker = EdgeBasedChecker(
                    config=self.config,
                    volatility_filter=self.volatility_filter,
                    vwap_filter=self.vwap_filter,
                    sweep_detector=self.sweep_detector,
                    ob_detector=self.ob_detector,
                    spread_tracker=self.spread_tracker,
                    m1_analyzer=self.m1_analyzer,
                    session_manager=self.session_manager,
                    news_service=self.news_service,
                    strategy_name='edge_based'
                )
            
            # Cache checker
            self.strategy_checkers[strategy_name] = checker
            return checker
            
        except ImportError as e:
            logger.error(f"Failed to import strategy checker for {strategy_name}: {e}")
            # Fallback to edge-based
            if strategy_name != 'edge_based':
                return self._get_strategy_checker('edge_based')
            raise
        except Exception as e:
            logger.error(f"Error creating strategy checker for {strategy_name}: {e}", exc_info=True)
            # Fallback to edge-based
            if strategy_name != 'edge_based':
                return self._get_strategy_checker('edge_based')
            raise
    
    def _generate_trade_idea(self, symbol: str, snapshot: Dict[str, Any],
                            result: ConditionCheckResult) -> Dict[str, Any]:
        """
        Generate trade idea from validated conditions.
        
        Determines:
        - Direction (BUY/SELL)
        - Entry price
        - SL/TP (ultra-tight)
        - Volume
        """
        symbol_key = symbol.lower().rstrip('c')
        rules_key = f"{symbol_key}_rules"
        rules = self.config.get(rules_key, {})
        
        # Determine direction from signals
        direction = self._determine_direction(snapshot, result)
        
        # Get current price
        current_price = snapshot['current_price']
        
        # Calculate SL/TP (ultra-tight)
        sl_range = rules.get('sl_range', [0.5, 1.2])
        tp_range = rules.get('tp_range', [1.0, 2.5])
        
        # Use middle of range for simplicity (can be made dynamic)
        sl_distance = (sl_range[0] + sl_range[1]) / 2
        tp_distance = (tp_range[0] + tp_range[1]) / 2
        
        if direction == "BUY":
            entry_price = snapshot['ask']  # Use ask for BUY
            sl = entry_price - sl_distance
            tp = entry_price + tp_distance
        else:  # SELL
            entry_price = snapshot['bid']  # Use bid for SELL
            sl = entry_price + sl_distance
            tp = entry_price - tp_distance
        
        # Default volume
        volume = 0.01
        
        return {
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'sl': sl,
            'tp': tp,
            'volume': volume,
            'atr1': snapshot.get('atr1'),
            'confluence_score': result.confluence_score,
            'is_aplus': result.is_aplus_setup
        }
    
    def _determine_direction(self, snapshot: Dict[str, Any],
                           result: ConditionCheckResult) -> str:
        """
        Determine trade direction from signals.
        
        Logic:
        - If bullish signals (sweep up, wick trap up, VWAP tap from below) → BUY
        - If bearish signals (sweep down, wick trap down, VWAP tap from above) → SELL
        - Default: Use VWAP position
        """
        signals = result.details.get('signals', {})
        primary_triggers = signals.get('primary_triggers', [])
        
        # Check for bullish signals
        bullish_signals = ['LONG_WICK_TRAP', 'MICRO_LIQUIDITY_SWEEP', 'VWAP_TAP_REJECTION', 'STRONG_ENGULFING']
        bearish_signals = ['LONG_WICK_TRAP', 'MICRO_LIQUIDITY_SWEEP', 'VWAP_TAP_REJECTION', 'STRONG_ENGULFING']
        
        # Check sweep direction
        if 'MICRO_LIQUIDITY_SWEEP' in primary_triggers:
            # Would need to check sweep direction from sweep detector
            # For now, use VWAP position
            pass
        
        # Use VWAP position as default
        current_price = snapshot['current_price']
        vwap = snapshot.get('vwap', 0)
        
        if vwap > 0:
            if current_price < vwap:
                return "BUY"  # Price below VWAP, expect bounce up
            else:
                return "SELL"  # Price above VWAP, expect rejection down
        
        # Default to BUY if unclear
        return "BUY"
    
    def execute_trade_idea(self, trade_idea: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute trade idea.
        
        Args:
            trade_idea: Trade idea dict from _generate_trade_idea()
        
        Returns:
            Execution result
        """
        if not self.execution_manager:
            return {
                'ok': False,
                'message': 'Execution manager not available'
            }
        
        return self.execution_manager.execute_trade(
            symbol=trade_idea['symbol'],
            direction=trade_idea['direction'],
            entry_price=trade_idea['entry_price'],
            sl=trade_idea['sl'],
            tp=trade_idea['tp'],
            volume=trade_idea.get('volume', 0.01),
            atr1=trade_idea.get('atr1')
        )
    
    def stop(self):
        """Stop engine and cleanup"""
        if self.execution_manager:
            self.execution_manager.stop()
        logger.info("MicroScalpEngine stopped")

