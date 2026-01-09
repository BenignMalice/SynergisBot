"""
Micro-Scalp Monitor

Continuous symbol monitoring for micro-scalp setups.
Operates independently from ChatGPT and auto-execution plans.

Features:
- Continuous scanning (every 5 seconds)
- Immediate execution (no plan creation)
- Symbol-specific rate limiting
- Session-aware filtering
- News blackout detection
- Position limit management
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from infra.micro_scalp_engine import MicroScalpEngine
from infra.micro_scalp_execution import MicroScalpExecutionManager
from infra.multi_timeframe_streamer import MultiTimeframeStreamer
from infra.mt5_service import MT5Service

logger = logging.getLogger(__name__)


class MicroScalpMonitor:
    """
    Continuous symbol monitoring for micro-scalp setups.
    Operates independently from ChatGPT and auto-execution plans.
    
    Features:
    - Continuous scanning (every 5 seconds)
    - Immediate execution (no plan creation)
    - Symbol-specific rate limiting
    - Session-aware filtering
    - News blackout detection
    - Position limit management
    """
    
    def __init__(
        self,
        symbols: List[str],
        check_interval: int = 5,
        micro_scalp_engine: Optional[MicroScalpEngine] = None,
        execution_manager: Optional[MicroScalpExecutionManager] = None,
        streamer: Optional[MultiTimeframeStreamer] = None,
        mt5_service: Optional[MT5Service] = None,
        config_path: str = "config/micro_scalp_automation.json",
        session_manager=None,
        news_service=None
    ):
        """
        Initialize Micro-Scalp Monitor.
        
        Args:
            symbols: List of symbols to monitor (e.g., ["BTCUSDc", "XAUUSDc"])
            check_interval: Seconds between checks (default: 5 for M1 timeframe)
            micro_scalp_engine: MicroScalpEngine instance (existing)
            execution_manager: MicroScalpExecutionManager instance (existing)
            streamer: MultiTimeframeStreamer instance (existing)
            mt5_service: MT5Service instance (existing)
            config_path: Path to configuration file
            session_manager: Optional session manager for session filtering
            news_service: Optional news service for blackout detection
        """
        # Initialize defaults first (before config loading)
        self.enabled = True
        self.config: Dict[str, Any] = {}
        
        # Load config
        self.config_path = config_path
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    self.config = json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config not found: {config_path}, using defaults")
            self.config = {}
        except json.JSONDecodeError as e:
            logger.error(f"Config file {config_path} has invalid JSON: {e}, using defaults")
            self.config = {}
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            self.config = {}
        
        # Validate configuration
        is_valid, errors = self._validate_config(self.config)
        if not is_valid:
            logger.warning(f"Config validation failed: {errors}. Using defaults for invalid fields.")
        
        # Apply config (overrides defaults)
        self.symbols = self.config.get('symbols', symbols)
        self.check_interval = max(1, min(300, self.config.get('check_interval_seconds', check_interval)))
        self.min_execution_interval = max(1, self.config.get('min_execution_interval_seconds', 60))
        self.max_positions_per_symbol = max(1, self.config.get('max_positions_per_symbol', 1))
        self.enabled = self.config.get('enabled', True)
        
        # Store component references
        self.engine = micro_scalp_engine
        self.execution_manager = execution_manager
        self.streamer = streamer
        self.mt5_service = mt5_service
        self.session_manager = session_manager
        self.news_service = news_service
        
        # Streamer API configuration
        self.streamer_api_url = os.getenv(
            "STREAMER_API_URL",
            "http://localhost:8000"
        )
        self.streamer_api_timeout = 1.0  # 1 second timeout
        
        # Get spread tracker from execution manager if available
        self.spread_tracker = None
        if execution_manager and hasattr(execution_manager, 'spread_tracker'):
            self.spread_tracker = execution_manager.spread_tracker
        
        # Graceful degradation - mark components as available
        self.engine_available = self.engine is not None
        self.execution_manager_available = self.execution_manager is not None
        self.streamer_available = self.streamer is not None
        self.news_service_available = self.news_service is not None
        self.session_manager_available = self.session_manager is not None
        
        # Log warnings only once per component type (not per instance)
        # Use debug level for subsequent instances to reduce log noise
        # Log component availability at debug level (expected during testing/graceful degradation)
        if not self.engine_available:
            logger.debug("MicroScalpEngine not available - condition checking disabled")
        if not self.execution_manager_available:
            logger.debug("MicroScalpExecutionManager not available - execution disabled")
        if not self.streamer_available:
            logger.debug("MultiTimeframeStreamer not available - data fetching disabled")
        
        # Monitoring state
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitor_lock = threading.Lock()
        
        # Rate limiting (prevent over-trading)
        self.last_execution_time: Dict[str, datetime] = {}
        self.last_position_cleanup: Dict[str, datetime] = {}
        self.position_cleanup_interval = 60  # Cleanup every 60 seconds
        
        # Load rate limiting config
        rate_limiting_config = self.config.get('rate_limiting', {})
        self.max_trades_per_hour = rate_limiting_config.get('max_trades_per_hour', 10)
        self.max_trades_per_day = rate_limiting_config.get('max_trades_per_day', 50)
        self.trades_per_hour: Dict[str, List[datetime]] = {}  # symbol -> [timestamp1, timestamp2, ...]
        self.trades_per_day: Dict[str, List[datetime]] = {}  # symbol -> [timestamp1, timestamp2, ...]
        
        # Position limits
        position_limits_config = self.config.get('position_limits', {})
        self.max_total_positions = position_limits_config.get('max_total_positions', 3)
        self.active_positions: Dict[str, List[int]] = {}  # symbol -> [ticket1, ticket2, ...]
        
        # Risk per trade
        self.risk_per_trade = self.config.get('risk_per_trade', 0.5)
        
        # Session filters
        session_filters_config = self.config.get('session_filters', {})
        self.session_filters_enabled = session_filters_config.get('enabled', True)
        self.preferred_sessions = session_filters_config.get('preferred_sessions', [])
        self.disable_during_news = session_filters_config.get('disable_during_news', True)
        
        # Performance metrics (initialized even if Phase 5.4 not implemented)
        self.performance_metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_r_multiple': 0.0,
            'avg_r_multiple': 0.0,
            'avg_execution_latency_ms': 0.0,
            'avg_hold_time_seconds': 0.0,
            'largest_win_r': 0.0,
            'largest_loss_r': 0.0,
            'current_streak': 0,
            'best_streak': 0,
            'worst_streak': 0
        }
        
        self.open_positions: Dict[int, Dict] = {}  # ticket -> position data (for performance tracking)
        
        # Statistics (with thread safety)
        self.stats_lock = threading.Lock()
        self.stats = {
            'total_checks': 0,
            'conditions_met': 0,
            'executions': 0,
            'execution_failures': 0,
            'skipped_news': 0,
            'skipped_rate_limit': 0,
            'skipped_position_limit': 0,
            'skipped_session': 0,
            'skipped_spread_validation': 0,
            'circuit_breaker_opens': 0,
            'mt5_heartbeat_failures': 0,
            'config_reloads': 0,
            'last_check_time': None
        }
        
        # Detailed check history (last 100 checks per symbol)
        self.check_history: Dict[str, List[Dict[str, Any]]] = {}  # symbol -> [check1, check2, ...]
        self.max_history_per_symbol = 100
        
        # Config reload tracking
        self.config_last_modified = 0.0
        if os.path.exists(config_path):
            self.config_last_modified = os.path.getmtime(config_path)
        self.config_reload_interval = 60  # Check every 60 seconds
        
        # Discord notifications (Phase 5.6)
        self.discord_notifier = None
        self.discord_enabled = False
        self._init_discord_notifier()
        
        logger.info(f"MicroScalpMonitor initialized for {len(self.symbols)} symbols")
    
    def _validate_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate configuration"""
        errors = []
        
        # Type validation
        if 'symbols' in config and not isinstance(config['symbols'], list):
            errors.append("'symbols' must be a list")
        
        if 'check_interval_seconds' in config:
            interval = config['check_interval_seconds']
            if not isinstance(interval, (int, float)) or interval < 1 or interval > 300:
                errors.append("'check_interval_seconds' must be between 1 and 300")
        
        if 'min_execution_interval_seconds' in config:
            interval = config['min_execution_interval_seconds']
            if not isinstance(interval, (int, float)) or interval < 1:
                errors.append("'min_execution_interval_seconds' must be >= 1")
        
        if 'max_positions_per_symbol' in config:
            max_pos = config['max_positions_per_symbol']
            if not isinstance(max_pos, int) or max_pos < 1:
                errors.append("'max_positions_per_symbol' must be >= 1")
        
        return len(errors) == 0, errors
    
    def _increment_stat(self, key: str, amount: int = 1):
        """Thread-safe stat increment"""
        with self.stats_lock:
            self.stats[key] = self.stats.get(key, 0) + amount
    
    def _init_discord_notifier(self):
        """Initialize Discord notifier (Phase 5.6)"""
        try:
            from discord_notifications import DiscordNotifier
            self.discord_notifier = DiscordNotifier()
            if not self.discord_notifier.enabled:
                logger.debug("Discord notifications not enabled - check DISCORD_WEBHOOK_URL")
                self.discord_enabled = False
            else:
                self.discord_enabled = True
                logger.debug("Discord notifications enabled for micro-scalp monitor")
        except ImportError:
            logger.debug("Discord notifications module not available")
            self.discord_enabled = False
        except Exception as e:
            logger.debug(f"Failed to initialize Discord notifier: {e}")
            self.discord_enabled = False
    
    def _send_discord_notification(self, title: str, message: str, message_type: str = "INFO", color: int = None):
        """Send notification to Discord (Phase 5.6)"""
        if not self.discord_enabled or not self.discord_notifier:
            return False
        
        try:
            # Map message types to colors
            if color is None:
                color_map = {
                    "EXECUTION": 0x00ff00,  # Green
                    "ERROR": 0xff0000,      # Red
                    "WARNING": 0xff9900,   # Orange
                    "PERFORMANCE": 0x0099ff, # Blue
                    "INFO": 0x0099ff        # Blue
                }
                color = color_map.get(message_type, 0x0099ff)
            
            # Send to private channel (micro-scalp executions are private)
            success = self.discord_notifier.send_message(
                message=message,
                message_type=message_type,
                color=color,
                channel="private",
                custom_title=title
            )
            
            return success
        except Exception as e:
            logger.debug(f"Discord notification failed: {e}")
            return False
    
    def _validate_execution_conditions(self, symbol: str, trade_idea: Dict) -> Dict[str, Any]:
        """Validate execution conditions before placing order (Phase 5.3)"""
        try:
            # Get execution validation config
            execution_validation_config = self.config.get('execution_validation', {})
            max_spread_percent = execution_validation_config.get('max_spread_percent', 0.25)
            check_tick_alignment = execution_validation_config.get('check_tick_alignment', False)
            use_spread_tracker = execution_validation_config.get('use_spread_tracker', False)
            
            # Get current spread from MT5
            if not self.mt5_service:
                return {'valid': False, 'reason': 'MT5 service unavailable'}
            
            tick_info = self.mt5_service.get_symbol_info(symbol)
            if not tick_info:
                return {'valid': False, 'reason': 'Symbol info unavailable'}
            
            current_spread = tick_info.spread
            tick_size = tick_info.trade_tick_size
            
            # Calculate target spread (based on entry price)
            entry_price = trade_idea.get('entry_price', 0)
            if entry_price == 0:
                # Get current price
                price_data = self.mt5_service.get_current_price(symbol)
                if not price_data:
                    return {'valid': False, 'reason': 'Price data unavailable'}
                entry_price = price_data.get('mid', 0)
            
            # Calculate spread as percentage
            spread_percent = (current_spread * tick_size / entry_price) * 100 if entry_price > 0 else 0
            
            if spread_percent > max_spread_percent:
                return {
                    'valid': False,
                    'reason': f'Spread too wide: {spread_percent:.3f}% > {max_spread_percent}%'
                }
            
            # Check tick size alignment (optional)
            if check_tick_alignment:
                sl_distance = abs(entry_price - trade_idea.get('sl', 0))
                tp_distance = abs(trade_idea.get('tp', 0) - entry_price)
                
                if sl_distance > 0 and (sl_distance % tick_size) != 0:
                    logger.debug(f"SL distance not aligned to tick size: {sl_distance} vs {tick_size}")
                
                if tp_distance > 0 and (tp_distance % tick_size) != 0:
                    logger.debug(f"TP distance not aligned to tick size: {tp_distance} vs {tick_size}")
            
            # Check liquidity (if available from spread tracker)
            if use_spread_tracker and self.spread_tracker:
                spread_data = self.spread_tracker.get_spread_data(symbol)
                if spread_data and spread_data.spread_ratio > 1.5:  # 50% wider than average
                    return {
                        'valid': False,
                        'reason': f'Spread tracker indicates wide spread (ratio: {spread_data.spread_ratio:.2f})'
                    }
            
            return {'valid': True, 'reason': 'All checks passed'}
        
        except Exception as e:
            logger.error(f"Execution validation error: {e}")
            return {'valid': False, 'reason': f'Validation error: {e}'}
    
    def _update_position_performance(self, ticket: int, close_time: datetime):
        """Update performance metrics when position closes (Phase 5.4)"""
        if ticket not in self.open_positions:
            return
        
        position = self.open_positions.pop(ticket)
        
        # Get close price from MT5
        if not self.mt5_service:
            return
        
        try:
            positions = self.mt5_service.get_positions()
            closed_position = next((p for p in positions if p.ticket == ticket), None)
            if closed_position:
                # Position still exists (shouldn't happen if we're cleaning up closed positions)
                return
            
            # Position is closed - get close price from history or use SL/TP
            # For now, we'll use a simplified approach: check if it hit TP or SL
            # In a full implementation, you'd query MT5 history for the actual close price
            entry_price = position['entry_price']
            direction = position['direction']
            sl = position['sl']
            tp = position['tp']
            
            # Estimate close price (simplified - in production, query MT5 history)
            # This is a placeholder - actual implementation should query MT5 deal history
            close_price = entry_price  # Default fallback
            
            # Calculate P/L
            if direction == 'BUY':
                profit = close_price - entry_price
            else:  # SELL
                profit = entry_price - close_price
            
            risk_amount = position['risk_amount']
            if risk_amount == 0:
                return
            
            # Calculate R-multiple
            r_multiple = profit / risk_amount if risk_amount > 0 else 0
            
            # Update metrics
            with self.stats_lock:  # Thread safety
                self.performance_metrics['total_trades'] += 1
                
                if profit > 0:
                    self.performance_metrics['winning_trades'] += 1
                    self.performance_metrics['current_streak'] = max(0, self.performance_metrics['current_streak']) + 1
                    if r_multiple > self.performance_metrics['largest_win_r']:
                        self.performance_metrics['largest_win_r'] = r_multiple
                else:
                    self.performance_metrics['losing_trades'] += 1
                    self.performance_metrics['current_streak'] = min(0, self.performance_metrics['current_streak']) - 1
                    if r_multiple < self.performance_metrics['largest_loss_r']:
                        self.performance_metrics['largest_loss_r'] = r_multiple
                
                # Update streaks
                if self.performance_metrics['current_streak'] > self.performance_metrics['best_streak']:
                    self.performance_metrics['best_streak'] = self.performance_metrics['current_streak']
                if self.performance_metrics['current_streak'] < self.performance_metrics['worst_streak']:
                    self.performance_metrics['worst_streak'] = self.performance_metrics['current_streak']
                
                # Update R-multiple averages
                self.performance_metrics['total_r_multiple'] += r_multiple
                total_trades = self.performance_metrics['total_trades']
                self.performance_metrics['avg_r_multiple'] = (
                    self.performance_metrics['total_r_multiple'] / total_trades
                    if total_trades > 0 else 0.0
                )
                
                # Update hold time
                hold_time = (close_time - position['entry_time']).total_seconds()
                current_avg_hold = self.performance_metrics['avg_hold_time_seconds']
                self.performance_metrics['avg_hold_time_seconds'] = (
                    (current_avg_hold * (total_trades - 1) + hold_time) / total_trades
                    if total_trades > 0 else hold_time
                )
        except Exception as e:
            logger.debug(f"Error updating performance metrics for ticket {ticket}: {e}")
    
    def start(self):
        """Start continuous monitoring in background thread"""
        with self.monitor_lock:
            if self.monitoring:
                logger.warning("Monitor already running")
                return
            
            if not self.enabled:
                logger.warning("Monitor is disabled in config")
                return
            
            self.monitoring = True
            self._last_heartbeat = datetime.now() - timedelta(seconds=61)  # Initialize to trigger first heartbeat
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name="MicroScalpMonitor"
            )
            self.monitor_thread.start()
            logger.info("MicroScalpMonitor started")
    
    def stop(self):
        """Stop continuous monitoring"""
        with self.monitor_lock:
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=10)
            
            # Cleanup resources
            # Note: Positions remain open (intentional - let them run their course)
            # Statistics are preserved for status endpoint
            # No need to close connections (they're shared)
            
            logger.info("MicroScalpMonitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop - checks each symbol every N seconds"""
        logger.info(f"Monitor loop started (interval: {self.check_interval}s)")
        
        consecutive_errors = 0
        max_consecutive_errors = 10  # Circuit breaker to prevent infinite crash loops
        last_config_check = time.time()
        loop_iteration = 0
        
        try:
            while self.monitoring:
                loop_iteration += 1
                # Log every 12 iterations (~60 seconds at 5s interval) to show loop is running
                if loop_iteration % 12 == 0:
                    logger.info(f"🔄 Monitor loop iteration {loop_iteration}, monitoring: {self.monitoring}, symbols: {len(self.symbols)}")
                
                # Log first iteration to confirm loop started
                if loop_iteration == 1:
                    logger.info(f"✅ Monitor loop running - checking {len(self.symbols)} symbols every {self.check_interval}s")
                
                try:
                    loop_start = time.time()
                    
                    # Check for config changes (every 60 seconds, not every loop)
                    current_time = time.time()
                    if current_time - last_config_check >= self.config_reload_interval:
                        self._reload_config_if_changed()
                        last_config_check = current_time
                    
                    # Fixed: Iterate over copy to avoid modification during iteration
                    for symbol in list(self.symbols):
                        try:
                            # Skip if rate limited (don't increment counter for skipped checks)
                            if self._should_skip_symbol(symbol):
                                if loop_iteration % 10 == 0:  # Log every 10th time to avoid spam
                                    logger.debug(f"[{symbol}] Skipped: rate limited (iteration {loop_iteration})")
                                continue
                        
                            # Check news blackout
                            if self._is_news_blackout(symbol):
                                self._increment_stat('skipped_news')
                                if loop_iteration % 10 == 0:
                                    logger.debug(f"[{symbol}] Skipped: news blackout (iteration {loop_iteration})")
                                continue
                            
                            # Check session filtering
                            if not self._should_monitor_symbol(symbol):
                                self._increment_stat('skipped_session')
                                if loop_iteration % 10 == 0:
                                    logger.debug(f"[{symbol}] Skipped: session filter (iteration {loop_iteration})")
                                continue
                            
                            # Get latest M1 data (tries streamer first, falls back to MT5)
                            m1_candles = self._get_m1_candles(symbol)
                            if not m1_candles:
                                # Log at info level every 3rd iteration to show the issue more frequently
                                if loop_iteration % 3 == 0:
                                    logger.info(f"[{symbol}] ⚠️ No M1 candles available - streamer and MT5 fallback both failed (iteration {loop_iteration})")
                                else:
                                    logger.debug(f"[{symbol}] No M1 candles available - skipping check")
                                # Don't increment counter for skipped checks due to missing data
                                continue
                            
                            # Check engine availability
                            if not self.engine:
                                logger.warning(f"[{symbol}] Engine not available - skipping condition check (iteration {loop_iteration})")
                                continue
                            
                            # Increment total_checks only when we're actually going to check conditions
                            # This tracks that we attempted to check this symbol
                            self._increment_stat('total_checks')
                            current_total = self.stats.get('total_checks', 0)
                            
                            # Check micro-scalp conditions (uses existing engine)
                            check_start_time = datetime.now()
                            result = self.engine.check_micro_conditions(symbol)
                            check_duration_ms = (datetime.now() - check_start_time).total_seconds() * 1000
                            
                            # Extract strategy and regime information
                            strategy = result.get('strategy', 'unknown')
                            regime = result.get('regime', 'UNKNOWN')
                            regime_result = result.get('regime_result', {})
                            confidence = regime_result.get('confidence', 0) if regime_result else 0
                            
                            # Extract detailed regime detection results for display
                            vwap_result = regime_result.get('vwap_reversion_result', {}) if regime_result else {}
                            range_result = regime_result.get('range_result', {}) if regime_result else {}
                            balanced_result = regime_result.get('balanced_zone_result', {}) if regime_result else {}
                            
                            # Log check with strategy information
                            logger.info(f"[{symbol}] ✅ Check #{current_total} | Strategy: {strategy.upper()} | Regime: {regime} | Confidence: {confidence}% | Passed: {result.get('passed', False)}")
                            
                            # Track detailed check information
                            check_details = {
                                'timestamp': check_start_time.isoformat(),
                                'symbol': symbol,
                                'duration_ms': round(check_duration_ms, 2),
                                'passed': result.get('passed', False),
                                'strategy': strategy,  # NEW: Strategy used for this check
                                'regime': regime,  # NEW: Detected regime
                                'regime_confidence': confidence,  # NEW: Regime confidence score
                                'regime_detection': {  # NEW: Detailed regime detection breakdown
                                    'vwap_reversion': {
                                        'confidence': vwap_result.get('confidence', 0),
                                        'threshold': vwap_result.get('min_confidence_threshold', 70),
                                        'reason': vwap_result.get('reason', ''),
                                        'deviation_sigma': vwap_result.get('deviation_sigma'),
                                        'volume_spike': vwap_result.get('volume_spike'),
                                        'vwap_slope': vwap_result.get('vwap_slope'),
                                        'atr_stable': vwap_result.get('atr_stable')
                                    },
                                    'range_scalp': {
                                        'confidence': range_result.get('confidence', 0),
                                        'threshold': range_result.get('min_confidence_threshold', 55),
                                        'reason': range_result.get('reason', ''),
                                        'range_respects': range_result.get('range_respects'),
                                        'near_high': range_result.get('near_high'),
                                        'near_low': range_result.get('near_low'),
                                        'bb_compression': range_result.get('bb_compression'),
                                        'm15_trend': range_result.get('m15_trend')
                                    },
                                    'balanced_zone': {
                                        'confidence': balanced_result.get('confidence', 0),
                                        'threshold': balanced_result.get('min_confidence_threshold', 60),
                                        'reason': balanced_result.get('reason', ''),
                                        'bb_compression': balanced_result.get('bb_compression', False),
                                        'compression_block': balanced_result.get('compression_block', False),
                                        'atr_dropping': balanced_result.get('atr_dropping', False),
                                        'equilibrium_ok': balanced_result.get('equilibrium_ok', False),
                                        'choppy_liquidity': balanced_result.get('choppy_liquidity', False)
                                    }
                                },
                                'pre_filters_passed': True,  # We got here, so pre-filters passed
                                'session_check': self._get_current_session_name(),
                                'news_blackout': self._is_news_blackout(symbol),
                                'rate_limited': False,
                                'position_limit': False
                            }
                            
                            # Add condition check details if available
                            if result.get('result'):
                                condition_result = result.get('result')
                                check_details['condition_details'] = {
                                    'pre_trade_passed': getattr(condition_result, 'pre_trade_passed', None),
                                    'location_passed': getattr(condition_result, 'location_passed', None),
                                    'primary_triggers': getattr(condition_result, 'primary_triggers', 0),
                                    'secondary_confluence': getattr(condition_result, 'secondary_confluence', 0),
                                    'confluence_score': getattr(condition_result, 'confluence_score', 0.0),
                                    'is_aplus_setup': getattr(condition_result, 'is_aplus_setup', False),
                                    'reasons': getattr(condition_result, 'reasons', []),
                                    'details': getattr(condition_result, 'details', {})
                                }
                            
                            if result.get('passed'):
                                self._increment_stat('conditions_met')
                                
                                # Re-check position limit right before execution (with lock) to prevent race condition
                                with self.monitor_lock:
                                    if self._has_max_positions(symbol):
                                        self._increment_stat('skipped_position_limit')
                                        check_details['position_limit'] = True
                                        check_details['block_reason'] = 'position_limit'
                                        self._add_check_history(symbol, check_details)
                                        continue
                                
                                check_details['executed'] = True
                                # Execute immediately (no plan creation)
                                self._execute_micro_scalp(symbol, result.get('trade_idea'))
                            else:
                                # Conditions not met - add failure reasons
                                check_details['block_reason'] = 'conditions_not_met'
                                if result.get('result') and hasattr(result.get('result'), 'reasons'):
                                    check_details['failure_reasons'] = result.get('result').reasons
                                elif result.get('reasons'):
                                    check_details['failure_reasons'] = result.get('reasons')
                            
                            # Add to history
                            self._add_check_history(symbol, check_details)
                        
                        except Exception as e:
                            logger.error(f"Error monitoring {symbol}: {e}", exc_info=True)
                            consecutive_errors += 1
                            if consecutive_errors >= max_consecutive_errors:
                                logger.error(f"Too many consecutive errors ({consecutive_errors}) - stopping monitor")
                                self.monitoring = False
                                return
                    
                    # Reset error counter on successful cycle
                    consecutive_errors = 0
                    with self.stats_lock:
                        self.stats['last_check_time'] = datetime.now()
                        # Log periodic heartbeat every 60 seconds to show activity
                        last_check = self.stats['last_check_time']
                        # Log cycle summary every 12 iterations (~60 seconds) to show what's happening
                        if loop_iteration % 12 == 0:
                            total_checks = self.stats.get('total_checks', 0)
                            skipped = self.stats.get('skipped', {})
                            logger.info(f"📊 Monitor cycle summary (iteration {loop_iteration}): Total checks: {total_checks}, Skipped - Session: {skipped.get('session', 0)}, News: {skipped.get('news', 0)}, Rate limit: {skipped.get('rate_limit', 0)}")
                        if not hasattr(self, '_last_heartbeat') or \
                           (last_check - self._last_heartbeat).total_seconds() >= 60:
                            self._last_heartbeat = last_check
                            stats_summary = {
                                'total_checks': self.stats['total_checks'],
                                'conditions_met': self.stats['conditions_met'],
                                'executions': self.stats['executions'],
                                'skipped': {
                                    'rate_limit': self.stats['skipped_rate_limit'],
                                    'position_limit': self.stats['skipped_position_limit'],
                                    'session': self.stats['skipped_session'],
                                    'news': self.stats['skipped_news']
                                }
                            }
                            logger.info(f"Micro-Scalp Monitor heartbeat: {stats_summary}")
                            # Also log thread status
                            if self.monitor_thread:
                                logger.info(f"Monitor thread alive: {self.monitor_thread.is_alive()}, monitoring: {self.monitoring}")
                    
                    # Sleep until next cycle
                    elapsed = time.time() - loop_start
                    sleep_time = max(0, self.check_interval - elapsed)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                
                except Exception as e:
                    logger.error(f"❌ Critical error in monitor loop (iteration {loop_iteration}): {e}", exc_info=True)
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"❌ Monitor loop crashed after {consecutive_errors} consecutive errors - stopping")
                        self.monitoring = False
                        return
                    logger.warning(f"⚠️ Monitor loop error {consecutive_errors}/{max_consecutive_errors}, retrying in 5s...")
                    time.sleep(5)  # Wait before retrying
        except Exception as fatal_error:
            logger.critical(f"FATAL ERROR in micro-scalp monitor loop: {fatal_error}", exc_info=True)
            self.monitoring = False
        finally:
            logger.info("Micro-scalp monitor loop stopped")
    
    def _should_skip_symbol(self, symbol: str) -> bool:
        """Check if symbol should be skipped (rate limiting)"""
        now = datetime.now()
        
        # Check min execution interval
        if symbol in self.last_execution_time:
            time_since_last = (now - self.last_execution_time[symbol]).total_seconds()
            if time_since_last < self.min_execution_interval:
                self._increment_stat('skipped_rate_limit')
                return True
        
        # Check hourly rate limit
        if symbol in self.trades_per_hour:
            # Clean old entries (older than 1 hour)
            hour_ago = now - timedelta(hours=1)
            self.trades_per_hour[symbol] = [
                ts for ts in self.trades_per_hour[symbol] 
                if ts > hour_ago
            ]
            if len(self.trades_per_hour[symbol]) >= self.max_trades_per_hour:
                self._increment_stat('skipped_rate_limit')
                return True
        
        # Check daily rate limit
        if symbol in self.trades_per_day:
            # Clean old entries (older than 24 hours)
            day_ago = now - timedelta(days=1)
            self.trades_per_day[symbol] = [
                ts for ts in self.trades_per_day[symbol] 
                if ts > day_ago
            ]
            if len(self.trades_per_day[symbol]) >= self.max_trades_per_day:
                self._increment_stat('skipped_rate_limit')
                return True
        
        return False
    
    def _is_news_blackout(self, symbol: str) -> bool:
        """Check if symbol is in news blackout period"""
        # Check if news blackout is enabled in config
        news_blackout_config = self.config.get('news_blackout', {})
        if not news_blackout_config.get('enabled', True):
            return False
        
        if not self.news_service:
            return False
        
        try:
            # Use is_blackout() method instead of get_news_status()
            # Check for macro blackout (affects all symbols)
            macro_blackout = self.news_service.is_blackout(category="macro")
            
            # Check for crypto blackout (affects BTCUSDc)
            crypto_blackout = False
            if symbol.upper().startswith('BTC'):
                crypto_blackout = self.news_service.is_blackout(category="crypto")
            
            is_blackout = macro_blackout or crypto_blackout
            if is_blackout:
                logger.debug(f"News blackout active for {symbol}: macro={macro_blackout}, crypto={crypto_blackout}")
            
            return is_blackout
        except Exception as e:
            logger.debug(f"News check failed: {e}")
            return False
    
    def _has_max_positions(self, symbol: str) -> bool:
        """Check if symbol has reached max positions limit"""
        # Use lock to prevent race condition and optimize cleanup
        now = datetime.now()
        last_cleanup = self.last_position_cleanup.get(symbol)
        cleanup_interval = self.position_cleanup_interval
        
        # Only cleanup periodically, not on every check (performance optimization)
        if not last_cleanup or (now - last_cleanup).total_seconds() >= cleanup_interval:
            with self.monitor_lock:  # Thread safety
                active = self.active_positions.get(symbol, [])
                closed_tickets = []
                for ticket in active:
                    if not self._is_position_open(ticket):
                        closed_tickets.append(ticket)
                        # Update performance metrics for closed position (Phase 5.4)
                        self._update_position_performance(ticket, now)
                active = [t for t in active if t not in closed_tickets]
                self.active_positions[symbol] = active
                self.last_position_cleanup[symbol] = now
        
        # Check per-symbol limit
        active = self.active_positions.get(symbol, [])
        if len(active) >= self.max_positions_per_symbol:
            return True
        
        # Check total positions limit (across all symbols)
        total_active = sum(len(positions) for positions in self.active_positions.values())
        if total_active >= self.max_total_positions:
            return True
        
        return False
    
    def _is_position_open(self, ticket: int) -> bool:
        """Check if position is still open"""
        try:
            if not self.mt5_service:
                return False
            
            positions = self.mt5_service.get_positions(symbol=None)
            
            # Handle None or empty return
            if not positions:
                return False
            
            # Handle both list of objects and list of dicts
            if hasattr(positions[0], 'ticket'):
                return any(p.ticket == ticket for p in positions)
            elif isinstance(positions[0], dict):
                return any(p.get('ticket') == ticket for p in positions if p.get('ticket'))
            else:
                return False
        except Exception as e:
            logger.debug(f"Error checking position {ticket}: {e}")
            return False
    
    def _get_m1_candles(self, symbol: str, limit: int = 50) -> Optional[List[Dict]]:
        """Get M1 candles with priority: HTTP API → Direct Streamer → MT5"""
        # Priority 1: Try HTTP API (streamer via API) - fastest, cross-process
        candles = self._get_candles_from_api(symbol, 'M1', limit)
        if candles:
            return candles
        
        # Priority 2: Try direct streamer (if available in same process)
        if self.streamer:
            # Check if streamer is running
            if hasattr(self.streamer, 'is_running') and self.streamer.is_running:
                try:
                    candles = self.streamer.get_candles(symbol, 'M1', limit=limit)
                    if candles and len(candles) >= 10:  # Need minimum candles for analysis
                        # Convert Candle objects to dicts if needed
                        if hasattr(candles[0], 'to_dict'):
                            # Use built-in to_dict() method (preferred)
                            candles = [c.to_dict() for c in candles]
                        elif hasattr(candles[0], 'open'):
                            # Fallback: manual conversion if to_dict() not available
                            candles = [
                                {
                                    'time': c.time,
                                    'open': c.open,
                                    'high': c.high,
                                    'low': c.low,
                                    'close': c.close,
                                    'volume': c.volume
                                }
                                for c in candles
                            ]
                        logger.debug(f"[{symbol}] ✅ Got {len(candles)} M1 candles from direct streamer")
                        return candles
                    else:
                        candle_count = len(candles) if candles else 0
                        logger.debug(f"[{symbol}] Direct streamer returned {candle_count} M1 candles (need at least 10)")
                except Exception as e:
                    logger.debug(f"[{symbol}] Direct streamer error: {e}, falling back to MT5")
        
        # Priority 3: Fallback to MT5 directly (slower but reliable)
        if self.mt5_service:
            try:
                import MetaTrader5 as mt5
                
                # Check if MT5 is initialized (initialize() returns True if already initialized)
                if not mt5.initialize():
                    logger.debug(f"[{symbol}] MT5 not initialized, cannot fetch M1 candles")
                    return None
                
                symbol_norm = symbol.upper().rstrip('Cc') + 'c'
                
                # Try to get M1 candles from MT5
                rates = mt5.copy_rates_from_pos(symbol_norm, mt5.TIMEFRAME_M1, 0, limit)
                if rates is not None and len(rates) >= 10:
                    # Convert numpy array to list of dicts
                    candles = []
                    for rate in rates:
                        candles.append({
                            'time': int(rate[0]),
                            'open': float(rate[1]),
                            'high': float(rate[2]),
                            'low': float(rate[3]),
                            'close': float(rate[4]),
                            'volume': int(rate[5]) if len(rate) > 5 else 0
                        })
                    logger.debug(f"[{symbol}] ✅ Got {len(candles)} M1 candles from MT5 (fallback)")
                    return candles
                else:
                    logger.debug(f"[{symbol}] MT5 returned {len(rates) if rates is not None else 0} M1 candles (need at least 10)")
            except Exception as e:
                logger.debug(f"[{symbol}] MT5 fallback failed: {e}")
        
        # No data available from any source
        logger.debug(f"[{symbol}] No M1 candles available from API, streamer, or MT5")
        return None
    
    def _get_candles_from_api(self, symbol: str, timeframe: str, limit: int) -> Optional[List[Dict]]:
        """
        Get candles from streamer via HTTP API.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe ('M1', 'M5', 'M15')
            limit: Number of candles
        
        Returns:
            List of candle dicts or None
        """
        try:
            import httpx
            
            url = f"{self.streamer_api_url}/streamer/candles/{symbol}/{timeframe}"
            params = {"limit": limit}
            
            with httpx.Client(timeout=self.streamer_api_timeout) as client:
                response = client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data.get("candles"):
                        candles = data["candles"]
                        # Convert time from timestamp to datetime if needed
                        for candle in candles:
                            if 'time' in candle and isinstance(candle['time'], (int, float)):
                                # Convert timestamp to datetime
                                from datetime import datetime, timezone
                                candle['time'] = datetime.fromtimestamp(candle['time'], tz=timezone.utc)
                        logger.debug(f"[{symbol}] ✅ Got {len(candles)} {timeframe} candles from API")
                        return candles
                    else:
                        logger.debug(f"[{symbol}] API returned unsuccessful response: {data.get('error', 'unknown')}")
                elif response.status_code == 503:
                    # Streamer not running - expected, fall through to other methods
                    logger.debug(f"[{symbol}] Streamer API not available (503), trying other methods")
                else:
                    logger.debug(f"[{symbol}] API call failed with status {response.status_code}")
        except ImportError:
            # httpx not available, skip API call
            logger.debug(f"[{symbol}] httpx not available, skipping API call")
        except Exception as e:
            logger.debug(f"[{symbol}] API call failed: {e}")
        
        return None
    
    def _execute_micro_scalp(self, symbol: str, trade_idea: Optional[Dict]):
        """Execute micro-scalp trade immediately"""
        if not trade_idea:
            logger.warning(f"No trade idea provided for {symbol}")
            return
        
        # Validate execution manager availability
        if not self.execution_manager:
            logger.debug(f"Execution manager not available for {symbol} - skipping execution")
            self._increment_stat('execution_failures')
            return
        
        # Validate required fields
        required_fields = ['entry_price', 'sl', 'tp', 'direction']
        missing_fields = [field for field in required_fields if field not in trade_idea]
        if missing_fields:
            logger.warning(f"Trade idea missing required fields: {missing_fields}")
            return
        
        # Pre-execution validation (Phase 5.3)
        validation_result = self._validate_execution_conditions(symbol, trade_idea)
        if not validation_result['valid']:
            logger.warning(
                f"Execution aborted for {symbol}: {validation_result['reason']}"
            )
            self._increment_stat('skipped_spread_validation')
            return
        
        execution_start = time.time()
        
        try:
            # Use existing execution manager
            result = self.execution_manager.execute_trade(
                symbol=symbol,
                direction=trade_idea.get('direction'),
                entry_price=trade_idea.get('entry_price'),
                sl=trade_idea.get('sl'),
                tp=trade_idea.get('tp'),
                volume=trade_idea.get('volume', 0.01),
                atr1=trade_idea.get('atr1')
            )
            
            # Validate result structure
            if not result or not isinstance(result, dict):
                logger.error(f"Invalid execution result for {symbol}: {result}")
                self._increment_stat('execution_failures')
                return
            
            if result.get('ok'):
                ticket = result.get('ticket')
                if ticket:
                    # Verify position is still open before tracking (may close immediately)
                    if self._is_position_open(ticket):
                        with self.monitor_lock:  # Thread safety for active_positions
                            if symbol not in self.active_positions:
                                self.active_positions[symbol] = []
                            self.active_positions[symbol].append(ticket)
                        
                        # Track position for performance metrics (Phase 5.4)
                        execution_latency_ms = (time.time() - execution_start) * 1000
                        risk_amount = abs(trade_idea.get('entry_price', 0) - trade_idea.get('sl', 0))
                        self.open_positions[ticket] = {
                            'symbol': symbol,
                            'direction': trade_idea.get('direction'),
                            'entry_price': trade_idea.get('entry_price'),
                            'sl': trade_idea.get('sl'),
                            'tp': trade_idea.get('tp'),
                            'entry_time': datetime.now(),
                            'execution_latency_ms': execution_latency_ms,
                            'risk_amount': risk_amount
                        }
                        
                        # Update execution latency (Phase 5.4)
                        total_trades = self.performance_metrics['total_trades']
                        current_avg = self.performance_metrics['avg_execution_latency_ms']
                        self.performance_metrics['avg_execution_latency_ms'] = (
                            (current_avg * total_trades + execution_latency_ms) / (total_trades + 1)
                        )
                        
                        # Update rate limit tracking
                        now = datetime.now()
                        self.last_execution_time[symbol] = now
                        
                        # Track for hourly/daily limits
                        if symbol not in self.trades_per_hour:
                            self.trades_per_hour[symbol] = []
                        if symbol not in self.trades_per_day:
                            self.trades_per_day[symbol] = []
                        
                        self.trades_per_hour[symbol].append(now)
                        self.trades_per_day[symbol].append(now)
                        
                        self._increment_stat('executions')
                        logger.info(
                            f"✅ Micro-scalp executed: {symbol} {trade_idea.get('direction')} "
                            f"@ {trade_idea.get('entry_price')} (ticket: {ticket})"
                        )
                        
                        # Send Discord notification (Phase 5.6)
                        notification_message = (
                            f"**Micro-Scalp Trade Executed**\n\n"
                            f"**Symbol:** {symbol}\n"
                            f"**Direction:** {trade_idea.get('direction')}\n"
                            f"**Entry:** {trade_idea.get('entry_price'):.5f}\n"
                            f"**Stop Loss:** {trade_idea.get('sl'):.5f}\n"
                            f"**Take Profit:** {trade_idea.get('tp'):.5f}\n"
                            f"**Volume:** {trade_idea.get('volume', 0.01)}\n"
                            f"**Ticket:** {ticket}\n"
                            f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        
                        self._send_discord_notification(
                            title=f"✅ Micro-Scalp Executed: {symbol}",
                            message=notification_message,
                            message_type="EXECUTION",
                            color=0x00ff00  # Green
                        )
                    else:
                        # Position closed immediately (stop loss hit, etc.)
                        logger.warning(f"Position {ticket} closed immediately after execution")
                        self._increment_stat('execution_failures')
                else:
                    # Execution succeeded but no ticket returned (unusual but possible)
                    self._increment_stat('execution_failures')
                    logger.warning(f"Execution succeeded but no ticket returned for {symbol}")
            else:
                # Only increment once for failed execution (not double-counted)
                self._increment_stat('execution_failures')
                error_msg = result.get('message', 'Unknown error')
                logger.warning(f"Micro-scalp execution failed for {symbol}: {error_msg}")
                
                # Send Discord error notification (Phase 5.6)
                error_message = (
                    f"**Micro-Scalp Execution Failed**\n\n"
                    f"**Symbol:** {symbol}\n"
                    f"**Direction:** {trade_idea.get('direction')}\n"
                    f"**Error:** {error_msg}\n"
                    f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                
                self._send_discord_notification(
                    title=f"❌ Micro-Scalp Failed: {symbol}",
                    message=error_message,
                    message_type="ERROR",
                    color=0xff0000  # Red
                )
        
        except Exception as e:
            self._increment_stat('execution_failures')
            logger.error(f"Error executing micro-scalp for {symbol}: {e}", exc_info=True)
    
    def _reload_config_if_changed(self):
        """Reload config if file has been modified"""
        try:
            if not os.path.exists(self.config_path):
                return
            
            current_mtime = os.path.getmtime(self.config_path)
            if current_mtime > self.config_last_modified:
                try:
                    with open(self.config_path, 'r') as f:
                        config = json.load(f)
                except json.JSONDecodeError as e:
                    logger.error(f"Config file {self.config_path} has invalid JSON: {e}")
                    return
                except Exception as e:
                    logger.error(f"Error reading config file: {e}")
                    return
                
                # Validate config
                is_valid, errors = self._validate_config(config)
                if not is_valid:
                    logger.warning(f"Config validation failed: {errors}")
                    return
                
                # Update runtime config (thread-safe)
                with self.monitor_lock:
                    # Update symbols (if changed) - copy list to avoid iteration errors
                    old_symbols = self.symbols.copy() if isinstance(self.symbols, list) else list(self.symbols)
                    new_symbols = config.get('symbols', self.symbols)
                    
                    if new_symbols != old_symbols:
                        logger.info(f"Config reload: Symbols updated: {old_symbols} → {new_symbols}")
                        # Copy list to avoid iteration errors if list changes mid-iteration
                        self.symbols = new_symbols.copy() if isinstance(new_symbols, list) else list(new_symbols)
                        
                        # Cleanup execution times for removed symbols (prevent unbounded growth)
                        removed_symbols = set(self.last_execution_time.keys()) - set(self.symbols)
                        for symbol in removed_symbols:
                            del self.last_execution_time[symbol]
                            if symbol in self.trades_per_hour:
                                del self.trades_per_hour[symbol]
                            if symbol in self.trades_per_day:
                                del self.trades_per_day[symbol]
                            logger.debug(f"Cleaned up execution time for removed symbol: {symbol}")
                    
                    # Update check interval
                    self.check_interval = max(1, min(300, config.get('check_interval_seconds', self.check_interval)))
                    
                    # Update rate limiting
                    self.min_execution_interval = max(1, config.get('min_execution_interval_seconds', self.min_execution_interval))
                    
                    # Update position limits
                    self.max_positions_per_symbol = max(1, config.get('max_positions_per_symbol', self.max_positions_per_symbol))
                    position_limits_config = config.get('position_limits', {})
                    self.max_total_positions = position_limits_config.get('max_total_positions', self.max_total_positions)
                    
                    # Update rate limiting config
                    rate_limiting_config = config.get('rate_limiting', {})
                    self.max_trades_per_hour = rate_limiting_config.get('max_trades_per_hour', self.max_trades_per_hour)
                    self.max_trades_per_day = rate_limiting_config.get('max_trades_per_day', self.max_trades_per_day)
                    
                    # Update risk per trade
                    self.risk_per_trade = config.get('risk_per_trade', self.risk_per_trade)
                    
                    # Update session filters
                    session_filters_config = config.get('session_filters', {})
                    self.session_filters_enabled = session_filters_config.get('enabled', self.session_filters_enabled)
                    self.preferred_sessions = session_filters_config.get('preferred_sessions', self.preferred_sessions)
                    self.disable_during_news = session_filters_config.get('disable_during_news', self.disable_during_news)
                    
                    # Update enabled flag
                    self.enabled = config.get('enabled', self.enabled)
                    
                    self.config = config
                
                self.config_last_modified = current_mtime
                self._increment_stat('config_reloads')
                logger.debug("Config reloaded successfully")
        except Exception as e:
            logger.debug(f"Config reload check failed: {e}")
    
    def _should_monitor_symbol(self, symbol: str) -> bool:
        """Check if symbol should be monitored based on session filters"""
        if not self.session_filters_enabled:
            return True
        
        if not self.session_manager:
            return True  # No session manager, allow monitoring
        
        try:
            # Get current session
            current_session = None
            if hasattr(self.session_manager, 'get_current_session'):
                session_data = self.session_manager.get_current_session()
                if isinstance(session_data, dict):
                    current_session = session_data.get('name', '').lower()
                elif isinstance(session_data, str):
                    current_session = session_data.lower()
            else:
                # Fallback to SessionHelpers if available
                try:
                    from infra.session_helpers import SessionHelpers
                    current_session = SessionHelpers.get_current_session().lower()
                except Exception:
                    return True  # Can't determine session, allow monitoring
            
            # Normalize session names for matching
            # Map common variations to standard names
            session_mapping = {
                'ny': 'new_york',
                'new_york': 'new_york',
                'london': 'london',
                'overlap': 'overlap',
                'asian': 'asian',
                'post_ny': 'post_ny'
            }
            
            normalized_current = session_mapping.get(current_session, current_session)
            
            # Check if current session is in preferred sessions
            if self.preferred_sessions:
                preferred_lower = [s.lower() for s in self.preferred_sessions]
                # Normalize preferred sessions too
                normalized_preferred = []
                for pref in preferred_lower:
                    normalized_pref = session_mapping.get(pref, pref)
                    normalized_preferred.append(normalized_pref)
                
                if normalized_current not in normalized_preferred:
                    logger.debug(f"Session filter: {current_session} (normalized: {normalized_current}) not in {normalized_preferred}")
                    return False
            else:
                # No preferred sessions configured, allow all
                logger.debug(f"Session filter: No preferred sessions configured, allowing monitoring")
            
            return True
        except Exception as e:
            logger.debug(f"Session check failed for {symbol}: {e}")
            return True  # On error, allow monitoring
    
    def _add_check_history(self, symbol: str, check_details: Dict[str, Any]):
        """Add check details to history (thread-safe)"""
        with self.stats_lock:
            if symbol not in self.check_history:
                self.check_history[symbol] = []
            self.check_history[symbol].append(check_details)
            # Keep only last N checks
            if len(self.check_history[symbol]) > self.max_history_per_symbol:
                self.check_history[symbol] = self.check_history[symbol][-self.max_history_per_symbol:]
    
    def _get_current_session_name(self) -> str:
        """Get current session name for logging"""
        try:
            if self.session_manager and hasattr(self.session_manager, 'get_current_session'):
                session_data = self.session_manager.get_current_session()
                if isinstance(session_data, dict):
                    return session_data.get('name', 'unknown')
                elif isinstance(session_data, str):
                    return session_data
            from infra.session_helpers import SessionHelpers
            return SessionHelpers.get_current_session()
        except Exception:
            return 'unknown'
    
    def get_status(self) -> Dict[str, Any]:
        """Get monitor status and statistics"""
        # Use timeout to prevent deadlock
        import threading
        stats_copy = {}
        recent_history = {}
        
        # Try to acquire lock with timeout
        if self.stats_lock.acquire(timeout=1.0):
            try:
                stats_copy = self.stats.copy()
                # Copy check history (last 20 per symbol for status)
                for symbol, history in self.check_history.items():
                    recent_history[symbol] = history[-20:] if len(history) > 20 else history
            finally:
                self.stats_lock.release()
        else:
            logger.warning("Could not acquire stats_lock for status - using cached data")
            # Fallback: use last known stats
            stats_copy = self.stats.copy() if hasattr(self, 'stats') else {}
        
        # Check thread status (non-blocking)
        thread_alive = False
        if self.monitor_thread:
            try:
                thread_alive = self.monitor_thread.is_alive()
            except Exception:
                thread_alive = False
        
        # Get current session (with error handling to prevent blocking)
        try:
            current_session = self._get_current_session_name()
        except Exception as e:
            logger.debug(f"Error getting current session: {e}")
            current_session = 'unknown'
        
        # Get active positions (with timeout to prevent deadlock)
        active_positions = {}
        if self.monitor_lock.acquire(timeout=0.5):
            try:
                active_positions = {
                    symbol: len(positions) 
                    for symbol, positions in self.active_positions.items()
                }
            finally:
                self.monitor_lock.release()
        else:
            logger.debug("Could not acquire monitor_lock for active_positions")
            active_positions = {}
        
        return {
            'monitoring': self.monitoring,
            'enabled': self.enabled,
            'symbols': self.symbols,
            'check_interval': self.check_interval,
            'thread_alive': thread_alive,
            'stats': stats_copy,
            'active_positions': active_positions,
            'last_execution_times': {
                symbol: dt.isoformat() 
                for symbol, dt in self.last_execution_time.items()
            },
            'component_availability': {
                'engine': self.engine_available,
                'execution_manager': self.execution_manager_available,
                'streamer': self.streamer_available,
                'news_service': self.news_service_available,
                'session_manager': self.session_manager_available
            },
            'config': {
                'risk_per_trade': self.risk_per_trade,
                'max_trades_per_hour': self.max_trades_per_hour,
                'max_trades_per_day': self.max_trades_per_day,
                'max_positions_per_symbol': self.max_positions_per_symbol,
                'max_total_positions': self.max_total_positions,
                'session_filters_enabled': self.session_filters_enabled,
                'preferred_sessions': self.preferred_sessions
            },
            'recent_checks': recent_history,
            'current_session': current_session
        }
    
    def get_detailed_history(self, symbol: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """Get detailed check history for symbol(s)"""
        with self.stats_lock:
            if symbol:
                history = self.check_history.get(symbol, [])
                return {
                    'symbol': symbol,
                    'total_checks': len(history),
                    'checks': history[-limit:] if len(history) > limit else history
                }
            else:
                # Return all symbols
                result = {}
                for sym, history in self.check_history.items():
                    result[sym] = {
                        'total_checks': len(history),
                        'checks': history[-limit:] if len(history) > limit else history
                    }
                return result

