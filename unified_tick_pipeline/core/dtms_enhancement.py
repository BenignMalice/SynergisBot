"""
DTMS Enhancement for Unified Tick Pipeline
Multi-timeframe integration and conflict prevention with Intelligent Exits
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import json

logger = logging.getLogger(__name__)

class ActionPriority(Enum):
    """Action priority levels for hierarchical control"""
    CRITICAL = 1    # Immediate action required (stop loss, emergency close)
    HIGH = 2        # Important action (hedge, partial close)
    MEDIUM = 3      # Standard action (trailing stop, breakeven)
    LOW = 4         # Monitoring action (state update, logging)

class ConflictType(Enum):
    """Types of conflicts between DTMS and Intelligent Exits"""
    STOP_LOSS_CONFLICT = "stop_loss_conflict"
    TAKE_PROFIT_CONFLICT = "take_profit_conflict"
    HEDGE_CONFLICT = "hedge_conflict"
    PARTIAL_CLOSE_CONFLICT = "partial_close_conflict"
    TRAILING_CONFLICT = "trailing_conflict"

@dataclass
class DTMSAction:
    """DTMS action with priority and conflict detection"""
    action_id: str
    ticket: int
    action_type: str
    priority: ActionPriority
    parameters: Dict[str, Any]
    timestamp: datetime
    conflict_checks: List[ConflictType]
    reevaluation_interval: int  # seconds
    last_reevaluation: Optional[datetime] = None
    execution_count: int = 0
    max_executions: int = 3

@dataclass
class HierarchicalControlMatrix:
    """Control matrix for action prioritization"""
    dtms_priority: int
    intelligent_exits_priority: int
    conflict_resolution: str
    override_conditions: List[str]

class DTMSEnhancement:
    """
    Enhanced DTMS with multi-timeframe integration and conflict prevention
    
    Features:
    - Multi-timeframe data integration from Unified Tick Pipeline
    - Hierarchical control matrix for action prioritization
    - Conflict prevention with Intelligent Exits
    - 3-second reevaluation logic
    - Real-time market state monitoring
    """
    
    def __init__(self, unified_pipeline, config: Dict[str, Any]):
        self.unified_pipeline = unified_pipeline
        self.config = config
        self.is_active = False
        
        # Action management
        self.pending_actions: Dict[str, DTMSAction] = {}
        self.action_history: List[DTMSAction] = []
        self.conflict_resolutions: Dict[str, str] = {}
        
        # Multi-timeframe data
        self.multi_timeframe_data: Dict[str, Dict[str, Any]] = {}
        self.market_state_cache: Dict[str, Any] = {}
        
        # Hierarchical control matrix
        self.control_matrix = self._initialize_control_matrix()
        
        # Performance metrics
        self.performance_metrics = {
            'actions_processed': 0,
            'conflicts_detected': 0,
            'conflicts_resolved': 0,
            'reevaluations_performed': 0,
            'multi_timeframe_analyses': 0,
            'error_count': 0
        }
        
        logger.info("DTMSEnhancement initialized")
    
    async def initialize(self):
        """Initialize enhanced DTMS"""
        try:
            logger.info("🔧 Initializing enhanced DTMS...")
            
            # Subscribe to unified pipeline data
            await self._subscribe_to_pipeline_data()
            
            # Initialize conflict resolution rules
            await self._initialize_conflict_resolution()
            
            # Start background monitoring
            await self._start_background_monitoring()
            
            self.is_active = True
            logger.info("✅ Enhanced DTMS initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize enhanced DTMS: {e}")
            raise
    
    async def stop(self):
        """Stop enhanced DTMS"""
        try:
            logger.info("🛑 Stopping enhanced DTMS...")
            self.is_active = False
            logger.info("✅ Enhanced DTMS stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping enhanced DTMS: {e}")
    
    async def _subscribe_to_pipeline_data(self):
        """Subscribe to unified pipeline data feeds"""
        try:
            # Subscribe to tick data
            self.unified_pipeline.subscribe_to_ticks(self._handle_tick_data)
            
            # Subscribe to M5 volatility data
            self.unified_pipeline.subscribe_to_m5_data(self._handle_m5_data)
            
            # Subscribe to offset calibration data
            self.unified_pipeline.subscribe_to_offset_data(self._handle_offset_data)
            
            logger.info("✅ Subscribed to unified pipeline data feeds")
            
        except Exception as e:
            logger.error(f"❌ Error subscribing to pipeline data: {e}")
    
    async def _handle_tick_data(self, tick_data):
        """Handle incoming tick data from unified pipeline"""
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
            
            # Update market state cache
            self.market_state_cache[symbol] = {
                'last_tick': tick_dict,
                'timestamp': datetime.now(timezone.utc),
                'bid': tick_dict.get('bid', 0),
                'ask': tick_dict.get('ask', 0),
                'mid': tick_dict.get('mid', 0)
            }
            
            # Trigger reevaluation for affected actions
            await self._trigger_reevaluation(symbol)
            
        except Exception as e:
            logger.error(f"❌ Error handling tick data: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _handle_m5_data(self, m5_data: Dict[str, Any]):
        """Handle M5 volatility data from unified pipeline"""
        try:
            if not self.is_active:
                return
            
            symbol = m5_data.get('symbol')
            if not symbol:
                return
            
            # Update multi-timeframe data
            self.multi_timeframe_data[symbol] = {
                'm5_volatility': m5_data.get('volatility_score', 0),
                'm5_structure': m5_data.get('structure_majority', 'neutral'),
                'fused_close': m5_data.get('fused_close', 0),
                'timestamp': datetime.now(timezone.utc)
            }
            
            # Update market state with volatility context
            if symbol in self.market_state_cache:
                self.market_state_cache[symbol]['volatility'] = m5_data.get('volatility_score', 0)
                self.market_state_cache[symbol]['structure'] = m5_data.get('structure_majority', 'neutral')
            
            self.performance_metrics['multi_timeframe_analyses'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error handling M5 data: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _handle_offset_data(self, offset_data: Dict[str, Any]):
        """Handle offset calibration data from unified pipeline"""
        try:
            if not self.is_active:
                return
            
            # Update market state with offset information
            for symbol, offset_info in offset_data.get('offsets', {}).items():
                if symbol in self.market_state_cache:
                    self.market_state_cache[symbol]['offset'] = offset_info.get('offset', 0)
                    self.market_state_cache[symbol]['confidence'] = offset_info.get('confidence', 0)
                    self.market_state_cache[symbol]['atr'] = offset_info.get('atr', 0)
            
        except Exception as e:
            logger.error(f"❌ Error handling offset data: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _trigger_reevaluation(self, symbol: str):
        """Trigger reevaluation for actions affecting a symbol"""
        try:
            current_time = datetime.now(timezone.utc)
            
            # Find actions that need reevaluation
            for action_id, action in self.pending_actions.items():
                if action.ticket in self._get_tickets_for_symbol(symbol):
                    # Check if reevaluation is due
                    if (action.last_reevaluation is None or 
                        (current_time - action.last_reevaluation).total_seconds() >= action.reevaluation_interval):
                        
                        await self._reevaluate_action(action_id, current_time)
            
        except Exception as e:
            logger.error(f"❌ Error triggering reevaluation: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _reevaluate_action(self, action_id: str, current_time: datetime):
        """Reevaluate a specific action with current market data"""
        try:
            action = self.pending_actions.get(action_id)
            if not action:
                return
            
            # Get current market state for the symbol
            symbol = self._get_symbol_for_ticket(action.ticket)
            market_state = self.market_state_cache.get(symbol, {})
            multi_timeframe = self.multi_timeframe_data.get(symbol, {})
            
            # Perform conflict detection
            conflicts = await self._detect_conflicts(action, market_state, multi_timeframe)
            
            if conflicts:
                # Resolve conflicts using hierarchical control matrix
                resolution = await self._resolve_conflicts(action, conflicts)
                if resolution:
                    action.conflict_checks = conflicts
                    action.last_reevaluation = current_time
                    self.performance_metrics['conflicts_resolved'] += 1
                else:
                    # Defer action if conflicts cannot be resolved
                    logger.warning(f"⚠️ Deferring action {action_id} due to unresolved conflicts")
                    return
            
            # Execute action if no conflicts or conflicts resolved
            await self._execute_action(action)
            
            action.last_reevaluation = current_time
            self.performance_metrics['reevaluations_performed'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error reevaluating action {action_id}: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _detect_conflicts(self, action: DTMSAction, market_state: Dict, multi_timeframe: Dict) -> List[ConflictType]:
        """Detect conflicts between DTMS and Intelligent Exits"""
        try:
            conflicts = []
            
            # Check for stop loss conflicts
            if action.action_type == 'adjust_stop_loss':
                if self._has_intelligent_exits_stop_loss(action.ticket):
                    conflicts.append(ConflictType.STOP_LOSS_CONFLICT)
            
            # Check for take profit conflicts
            if action.action_type == 'adjust_take_profit':
                if self._has_intelligent_exits_take_profit(action.ticket):
                    conflicts.append(ConflictType.TAKE_PROFIT_CONFLICT)
            
            # Check for hedge conflicts
            if action.action_type == 'hedge_position':
                if self._has_intelligent_exits_hedge(action.ticket):
                    conflicts.append(ConflictType.HEDGE_CONFLICT)
            
            # Check for partial close conflicts
            if action.action_type == 'partial_close':
                if self._has_intelligent_exits_partial_close(action.ticket):
                    conflicts.append(ConflictType.PARTIAL_CLOSE_CONFLICT)
            
            # Check for trailing conflicts
            if action.action_type == 'trailing_stop':
                if self._has_intelligent_exits_trailing(action.ticket):
                    conflicts.append(ConflictType.TRAILING_CONFLICT)
            
            if conflicts:
                self.performance_metrics['conflicts_detected'] += 1
            
            return conflicts
            
        except Exception as e:
            logger.error(f"❌ Error detecting conflicts: {e}")
            return []
    
    async def _resolve_conflicts(self, action: DTMSAction, conflicts: List[ConflictType]) -> bool:
        """Resolve conflicts using hierarchical control matrix"""
        try:
            # Get control matrix entry for this action type
            matrix_entry = self.control_matrix.get(action.action_type)
            if not matrix_entry:
                return False
            
            # Check override conditions
            for condition in matrix_entry.override_conditions:
                if await self._check_override_condition(condition, action):
                    logger.info(f"✅ Override condition met for action {action.action_id}: {condition}")
                    return True
            
            # Use priority-based resolution
            if matrix_entry.dtms_priority < matrix_entry.intelligent_exits_priority:
                logger.info(f"✅ DTMS priority higher for action {action.action_id}")
                return True
            else:
                logger.info(f"⚠️ Intelligent Exits priority higher for action {action.action_id}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Error resolving conflicts: {e}")
            return False
    
    async def _execute_action(self, action: DTMSAction):
        """Execute a DTMS action"""
        try:
            # Check execution limits
            if action.execution_count >= action.max_executions:
                logger.warning(f"⚠️ Action {action.action_id} reached execution limit")
                return
            
            # Execute the action based on type
            success = False
            if action.action_type == 'adjust_stop_loss':
                success = await self._execute_stop_loss_adjustment(action)
            elif action.action_type == 'adjust_take_profit':
                success = await self._execute_take_profit_adjustment(action)
            elif action.action_type == 'hedge_position':
                success = await self._execute_hedge_position(action)
            elif action.action_type == 'partial_close':
                success = await self._execute_partial_close(action)
            elif action.action_type == 'trailing_stop':
                success = await self._execute_trailing_stop(action)
            
            if success:
                action.execution_count += 1
                self.performance_metrics['actions_processed'] += 1
                logger.info(f"✅ Executed action {action.action_id} ({action.action_type})")
            else:
                logger.warning(f"⚠️ Failed to execute action {action.action_id}")
            
        except Exception as e:
            logger.error(f"❌ Error executing action {action.action_id}: {e}")
            self.performance_metrics['error_count'] += 1
    
    def _initialize_control_matrix(self) -> Dict[str, HierarchicalControlMatrix]:
        """Initialize hierarchical control matrix"""
        return {
            'adjust_stop_loss': HierarchicalControlMatrix(
                dtms_priority=1,
                intelligent_exits_priority=2,
                conflict_resolution='dtms_override',
                override_conditions=['emergency_stop_loss', 'high_volatility_stop']
            ),
            'adjust_take_profit': HierarchicalControlMatrix(
                dtms_priority=2,
                intelligent_exits_priority=1,
                conflict_resolution='intelligent_exits_override',
                override_conditions=['profit_target_reached', 'volatility_spike']
            ),
            'hedge_position': HierarchicalControlMatrix(
                dtms_priority=1,
                intelligent_exits_priority=3,
                conflict_resolution='dtms_override',
                override_conditions=['structure_break', 'high_volatility_hedge']
            ),
            'partial_close': HierarchicalControlMatrix(
                dtms_priority=2,
                intelligent_exits_priority=1,
                conflict_resolution='intelligent_exits_override',
                override_conditions=['profit_target_reached', 'risk_reduction']
            ),
            'trailing_stop': HierarchicalControlMatrix(
                dtms_priority=3,
                intelligent_exits_priority=1,
                conflict_resolution='intelligent_exits_override',
                override_conditions=['trend_continuation', 'volatility_expansion']
            )
        }
    
    async def _initialize_conflict_resolution(self):
        """Initialize conflict resolution rules"""
        try:
            # Load conflict resolution rules from config
            resolution_rules = self.config.get('conflict_resolution', {})
            
            for action_type, rules in resolution_rules.items():
                self.conflict_resolutions[action_type] = rules
            
            logger.info("✅ Conflict resolution rules initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing conflict resolution: {e}")
    
    async def _start_background_monitoring(self):
        """Start background monitoring tasks"""
        try:
            # Start 3-second reevaluation loop
            asyncio.create_task(self._reevaluation_loop())
            
            # Start conflict resolution loop
            asyncio.create_task(self._conflict_resolution_loop())
            
            logger.info("✅ Background monitoring started")
            
        except Exception as e:
            logger.error(f"❌ Error starting background monitoring: {e}")
    
    async def _reevaluation_loop(self):
        """3-second reevaluation loop"""
        while self.is_active:
            try:
                await asyncio.sleep(3)  # 3-second interval
                
                current_time = datetime.now(timezone.utc)
                
                # Reevaluate all pending actions
                for action_id, action in list(self.pending_actions.items()):
                    if (action.last_reevaluation is None or 
                        (current_time - action.last_reevaluation).total_seconds() >= action.reevaluation_interval):
                        
                        await self._reevaluate_action(action_id, current_time)
                
            except Exception as e:
                logger.error(f"❌ Error in reevaluation loop: {e}")
                await asyncio.sleep(1)
    
    async def _conflict_resolution_loop(self):
        """Conflict resolution monitoring loop"""
        while self.is_active:
            try:
                await asyncio.sleep(1)  # 1-second interval
                
                # Check for actions with conflicts
                for action_id, action in list(self.pending_actions.items()):
                    if action.conflict_checks:
                        # Attempt to resolve conflicts
                        symbol = self._get_symbol_for_ticket(action.ticket)
                        market_state = self.market_state_cache.get(symbol, {})
                        multi_timeframe = self.multi_timeframe_data.get(symbol, {})
                        
                        resolution = await self._resolve_conflicts(action, action.conflict_checks)
                        if resolution:
                            action.conflict_checks = []
                            await self._execute_action(action)
                
            except Exception as e:
                logger.error(f"❌ Error in conflict resolution loop: {e}")
                await asyncio.sleep(1)
    
    # Helper methods for conflict detection
    def _has_intelligent_exits_stop_loss(self, ticket: int) -> bool:
        """Check if Intelligent Exits has a stop loss for this ticket"""
        # Implementation would check Intelligent Exits system
        return False
    
    def _has_intelligent_exits_take_profit(self, ticket: int) -> bool:
        """Check if Intelligent Exits has a take profit for this ticket"""
        # Implementation would check Intelligent Exits system
        return False
    
    def _has_intelligent_exits_hedge(self, ticket: int) -> bool:
        """Check if Intelligent Exits has a hedge for this ticket"""
        # Implementation would check Intelligent Exits system
        return False
    
    def _has_intelligent_exits_partial_close(self, ticket: int) -> bool:
        """Check if Intelligent Exits has a partial close for this ticket"""
        # Implementation would check Intelligent Exits system
        return False
    
    def _has_intelligent_exits_trailing(self, ticket: int) -> bool:
        """Check if Intelligent Exits has a trailing stop for this ticket"""
        # Implementation would check Intelligent Exits system
        return False
    
    # Helper methods for action execution
    async def _execute_stop_loss_adjustment(self, action: DTMSAction) -> bool:
        """Execute stop loss adjustment"""
        # Implementation would call MT5 API
        return True
    
    async def _execute_take_profit_adjustment(self, action: DTMSAction) -> bool:
        """Execute take profit adjustment"""
        # Implementation would call MT5 API
        return True
    
    async def _execute_hedge_position(self, action: DTMSAction) -> bool:
        """Execute hedge position"""
        # Implementation would call MT5 API
        return True
    
    async def _execute_partial_close(self, action: DTMSAction) -> bool:
        """Execute partial close"""
        # Implementation would call MT5 API
        return True
    
    async def _execute_trailing_stop(self, action: DTMSAction) -> bool:
        """Execute trailing stop"""
        # Implementation would call MT5 API
        return True
    
    # Helper methods for data access
    def _get_tickets_for_symbol(self, symbol: str) -> List[int]:
        """Get tickets for a specific symbol"""
        # Implementation would query MT5 for open positions
        return []
    
    def _get_symbol_for_ticket(self, ticket: int) -> str:
        """Get symbol for a specific ticket"""
        # Implementation would query MT5 for position details
        return "UNKNOWN"
    
    async def _check_override_condition(self, condition: str, action: DTMSAction) -> bool:
        """Check if an override condition is met"""
        # Implementation would check specific conditions
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get enhanced DTMS status"""
        return {
            'is_active': self.is_active,
            'pending_actions': len(self.pending_actions),
            'action_history_count': len(self.action_history),
            'market_state_symbols': len(self.market_state_cache),
            'multi_timeframe_symbols': len(self.multi_timeframe_data),
            'performance_metrics': self.performance_metrics,
            'control_matrix_entries': len(self.control_matrix),
            'conflict_resolutions': len(self.conflict_resolutions)
        }
