"""
Intelligent Exits Unified Pipeline Integration
Enhanced Intelligent Exits system with Unified Tick Pipeline data feeds
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from unified_tick_pipeline_integration import get_unified_pipeline

logger = logging.getLogger(__name__)

class IntelligentExitsUnifiedPipelineIntegration:
    """
    Enhanced Intelligent Exits integration with Unified Tick Pipeline
    
    Features:
    - Real-time data from Unified Tick Pipeline
    - M5 volatility bridge integration
    - Enhanced volatility monitoring
    - Offset calibration integration
    - System coordination integration
    """
    
    def __init__(self):
        self.pipeline = None
        self.is_active = False
        self.is_initialized = False
        self.monitoring_tasks = []
        
        # Intelligent Exits state
        self.exit_rules = {}
        self.action_history = []
        self.performance_metrics = {
            'breakeven_moves': 0,
            'partial_profits': 0,
            'volatility_adjustments': 0,
            'trailing_stops': 0,
            'error_count': 0
        }
        
        logger.info("IntelligentExitsUnifiedPipelineIntegration initialized")
    
    async def initialize(self) -> bool:
        """Initialize Intelligent Exits with Unified Tick Pipeline"""
        try:
            logger.info("🔧 Initializing Intelligent Exits with Unified Tick Pipeline...")
            
            # Get the unified pipeline
            self.pipeline = get_unified_pipeline()
            if not self.pipeline:
                logger.error("❌ Unified Tick Pipeline not available")
                return False
            
            # Start monitoring tasks
            await self._start_monitoring_tasks()
            
            self.is_active = True
            self.is_initialized = True
            logger.info("✅ Intelligent Exits Unified Pipeline integration initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Intelligent Exits Unified Pipeline integration: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop Intelligent Exits monitoring"""
        try:
            logger.info("🛑 Stopping Intelligent Exits Unified Pipeline integration...")
            
            # Stop monitoring tasks
            for task in self.monitoring_tasks:
                task.cancel()
            
            self.monitoring_tasks.clear()
            self.is_active = False
            self.is_initialized = False
            
            logger.info("✅ Intelligent Exits Unified Pipeline integration stopped")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping Intelligent Exits Unified Pipeline integration: {e}")
            return False
    
    async def _start_monitoring_tasks(self):
        """Start Intelligent Exits monitoring tasks"""
        try:
            # Start exit rules monitoring task
            task1 = asyncio.create_task(self._monitor_exit_rules())
            self.monitoring_tasks.append(task1)
            
            # Start volatility monitoring task
            task2 = asyncio.create_task(self._monitor_volatility())
            self.monitoring_tasks.append(task2)
            
            # Start M5 volatility bridge monitoring task
            task3 = asyncio.create_task(self._monitor_m5_volatility())
            self.monitoring_tasks.append(task3)
            
            # Start system health monitoring task
            task4 = asyncio.create_task(self._monitor_system_health())
            self.monitoring_tasks.append(task4)
            
            logger.info("✅ Intelligent Exits monitoring tasks started")
            
        except Exception as e:
            logger.error(f"❌ Error starting monitoring tasks: {e}")
    
    async def _monitor_exit_rules(self):
        """Monitor exit rules using Unified Tick Pipeline data"""
        while self.is_active:
            try:
                # Get latest tick data for monitored trades
                for ticket, rule in self.exit_rules.items():
                    symbol = rule.get('symbol')
                    if not symbol:
                        continue
                    
                    # Get latest tick data
                    tick_data = await self.pipeline.get_tick_data(symbol, limit=1)
                    if tick_data.get('success'):
                        data = tick_data['data']
                        if data:
                            latest_tick = data[0]
                            await self._process_tick_for_exit_rule(ticket, rule, latest_tick)
                
                # Sleep for 1 second
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Error in exit rules monitoring: {e}")
                self.performance_metrics['error_count'] += 1
                await asyncio.sleep(5)  # Wait before retry
    
    async def _monitor_volatility(self):
        """Monitor volatility using Unified Tick Pipeline data"""
        while self.is_active:
            try:
                # Get volatility analysis for monitored symbols
                symbols = set(rule['symbol'] for rule in self.exit_rules.values())
                
                for symbol in symbols:
                    volatility_data = await self.pipeline.get_volatility_analysis(symbol)
                    if volatility_data.get('success'):
                        data = volatility_data['data']
                        await self._process_volatility_data(symbol, data)
                
                # Sleep for 5 seconds
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"❌ Error in volatility monitoring: {e}")
                self.performance_metrics['error_count'] += 1
                await asyncio.sleep(10)  # Wait before retry
    
    async def _monitor_m5_volatility(self):
        """Monitor M5 volatility bridge"""
        while self.is_active:
            try:
                # Get M5 candles for monitored symbols
                symbols = set(rule['symbol'] for rule in self.exit_rules.values())
                
                for symbol in symbols:
                    m5_data = await self.pipeline.get_m5_candles(symbol, limit=1)
                    if m5_data.get('success'):
                        data = m5_data['data']
                        if data:
                            latest_candle = data[0]
                            await self._process_m5_candle(symbol, latest_candle)
                
                # Sleep for 5 seconds
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"❌ Error in M5 volatility monitoring: {e}")
                self.performance_metrics['error_count'] += 1
                await asyncio.sleep(15)  # Wait before retry
    
    async def _monitor_system_health(self):
        """Monitor system health"""
        while self.is_active:
            try:
                # Get system health status
                health_data = await self.pipeline.get_system_health()
                if health_data.get('success'):
                    data = health_data['data']
                    await self._process_system_health(data)
                
                # Sleep for 30 seconds
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"❌ Error in system health monitoring: {e}")
                self.performance_metrics['error_count'] += 1
                await asyncio.sleep(60)  # Wait before retry
    
    async def _process_tick_for_exit_rule(self, ticket: int, rule: Dict[str, Any], tick_data: Dict[str, Any]):
        """Process tick data for a specific exit rule"""
        try:
            symbol = rule['symbol']
            direction = rule['direction']
            entry_price = rule['entry_price']
            current_price = tick_data.get('mid', 0)
            
            if current_price == 0:
                return
            
            # Calculate P&L
            if direction == 'BUY':
                pnl = current_price - entry_price
            else:  # SELL
                pnl = entry_price - current_price
            
            # Update rule with current data
            rule['current_price'] = current_price
            rule['pnl'] = pnl
            rule['last_update'] = datetime.now(timezone.utc)
            
            # Check for exit actions
            await self._check_exit_actions(ticket, rule, tick_data)
            
        except Exception as e:
            logger.error(f"❌ Error processing tick for exit rule {ticket}: {e}")
    
    async def _process_volatility_data(self, symbol: str, volatility_data: Dict[str, Any]):
        """Process volatility data"""
        try:
            volatility_score = volatility_data.get('volatility_score', 0)
            is_high_volatility = volatility_data.get('is_high_volatility', False)
            
            # Check if any exit rules for this symbol need volatility-based actions
            for ticket, rule in self.exit_rules.items():
                if rule.get('symbol') == symbol:
                    await self._check_volatility_actions(ticket, rule, volatility_score, is_high_volatility)
            
        except Exception as e:
            logger.error(f"❌ Error processing volatility data for {symbol}: {e}")
    
    async def _process_m5_candle(self, symbol: str, candle_data: Dict[str, Any]):
        """Process M5 candle data"""
        try:
            volatility_score = candle_data.get('volatility_score', 0)
            structure_bias = candle_data.get('structure_bias', 'neutral')
            
            # Check if any exit rules for this symbol need M5-based actions
            for ticket, rule in self.exit_rules.items():
                if rule.get('symbol') == symbol:
                    await self._check_m5_actions(ticket, rule, volatility_score, structure_bias)
            
        except Exception as e:
            logger.error(f"❌ Error processing M5 candle for {symbol}: {e}")
    
    async def _process_system_health(self, health_data: Dict[str, Any]):
        """Process system health data"""
        try:
            system_coordination = health_data.get('system_coordination', {})
            performance_optimization = health_data.get('performance_optimization', {})
            
            # Check system state
            current_state = system_coordination.get('current_state', 'unknown')
            if current_state == 'critical':
                logger.critical("🚨 System is in critical state - reducing Intelligent Exits monitoring")
                await self._handle_critical_system_state()
            elif current_state == 'high_load':
                logger.warning("⚠️ System is under high load - optimizing Intelligent Exits monitoring")
                await self._handle_high_load_state()
            
        except Exception as e:
            logger.error(f"❌ Error processing system health: {e}")
    
    async def _check_exit_actions(self, ticket: int, rule: Dict[str, Any], tick_data: Dict[str, Any]):
        """Check for exit actions based on tick data"""
        try:
            # This is where Intelligent Exits logic would be implemented
            # For now, just log the monitoring
            logger.debug(f"Intelligent Exits monitoring rule {ticket} for {rule['symbol']}")
            
        except Exception as e:
            logger.error(f"❌ Error checking exit actions for rule {ticket}: {e}")
    
    async def _check_volatility_actions(self, ticket: int, rule: Dict[str, Any], volatility_score: float, is_high_volatility: bool):
        """Check for volatility-based actions"""
        try:
            if is_high_volatility:
                logger.warning(f"🚨 High volatility detected for exit rule {ticket}: {volatility_score}")
                self.performance_metrics['volatility_adjustments'] += 1
                
                # Could implement volatility-based stop adjustments here
                
        except Exception as e:
            logger.error(f"❌ Error checking volatility actions for rule {ticket}: {e}")
    
    async def _check_m5_actions(self, ticket: int, rule: Dict[str, Any], volatility_score: float, structure_bias: str):
        """Check for M5-based actions"""
        try:
            # This is where M5 volatility bridge logic would be implemented
            logger.debug(f"M5 volatility monitoring for rule {ticket}: volatility={volatility_score}, bias={structure_bias}")
            
        except Exception as e:
            logger.error(f"❌ Error checking M5 actions for rule {ticket}: {e}")
    
    async def _handle_critical_system_state(self):
        """Handle critical system state"""
        try:
            logger.critical("🚨 Handling critical system state - reducing Intelligent Exits monitoring frequency")
            # Could implement emergency procedures here
            
        except Exception as e:
            logger.error(f"❌ Error handling critical system state: {e}")
    
    async def _handle_high_load_state(self):
        """Handle high load state"""
        try:
            logger.warning("⚠️ Handling high load state - optimizing Intelligent Exits monitoring")
            # Could implement load balancing here
            
        except Exception as e:
            logger.error(f"❌ Error handling high load state: {e}")
    
    # Public API methods
    async def add_exit_rule(self, ticket: int, symbol: str, direction: str, entry_price: float,
                           initial_sl: float, initial_tp: float, **kwargs) -> bool:
        """Add an exit rule to Intelligent Exits monitoring"""
        try:
            rule = {
                'ticket': ticket,
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'initial_sl': initial_sl,
                'initial_tp': initial_tp,
                'current_price': entry_price,
                'pnl': 0.0,
                'added_at': datetime.now(timezone.utc),
                'last_update': datetime.now(timezone.utc),
                **kwargs
            }
            
            self.exit_rules[ticket] = rule
            
            logger.info(f"✅ Added exit rule {ticket} to Intelligent Exits monitoring")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding exit rule {ticket} to Intelligent Exits: {e}")
            return False
    
    async def remove_exit_rule(self, ticket: int) -> bool:
        """Remove an exit rule from Intelligent Exits monitoring"""
        try:
            if ticket in self.exit_rules:
                del self.exit_rules[ticket]
                logger.info(f"✅ Removed exit rule {ticket} from Intelligent Exits monitoring")
                return True
            else:
                logger.warning(f"⚠️ Exit rule {ticket} not found in Intelligent Exits monitoring")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error removing exit rule {ticket} from Intelligent Exits: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get Intelligent Exits status"""
        return {
            'is_active': self.is_active,
            'exit_rules': len(self.exit_rules),
            'rules': list(self.exit_rules.keys()),
            'performance_metrics': self.performance_metrics,
            'pipeline_available': self.pipeline is not None
        }
    
    def get_exit_rule_status(self, ticket: int) -> Optional[Dict[str, Any]]:
        """Get status of a specific exit rule"""
        return self.exit_rules.get(ticket)
    
    def get_action_history(self, ticket: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get action history"""
        if ticket:
            return [action for action in self.action_history if action.get('ticket') == ticket]
        else:
            return self.action_history

# Global instance
_intelligent_exits_unified_integration: Optional[IntelligentExitsUnifiedPipelineIntegration] = None
_intelligent_exits_init_lock = asyncio.Lock()

async def initialize_intelligent_exits_unified_pipeline() -> bool:
    """Initialize Intelligent Exits with Unified Tick Pipeline (async + idempotent)"""
    global _intelligent_exits_unified_integration
    async with _intelligent_exits_init_lock:
        try:
            if _intelligent_exits_unified_integration and _intelligent_exits_unified_integration.is_initialized:
                logger.info("ℹ️ Intelligent Exits already initialized; skipping.")
                return True

            logger.info("🚀 Initializing Intelligent Exits with Unified Tick Pipeline...")
            _intelligent_exits_unified_integration = IntelligentExitsUnifiedPipelineIntegration()
            success = await _intelligent_exits_unified_integration.initialize()

            if success:
                logger.info("✅ Intelligent Exits Unified Pipeline integration completed successfully")
                return True
            else:
                logger.error("❌ Intelligent Exits Unified Pipeline integration failed")
                return False
        except Exception as e:
            logger.error(f"❌ Error initializing Intelligent Exits Unified Pipeline: {e}", exc_info=True)
            return False

async def stop_intelligent_exits_unified_pipeline() -> bool:
    """Stop Intelligent Exits (async, safe to call multiple times)"""
    global _intelligent_exits_unified_integration
    try:
        if _intelligent_exits_unified_integration:
            await _intelligent_exits_unified_integration.stop()
        return True
    except Exception as e:
        logger.error(f"❌ Error stopping Intelligent Exits Unified Pipeline: {e}", exc_info=True)
        return False

def get_intelligent_exits_unified_integration() -> Optional[IntelligentExitsUnifiedPipelineIntegration]:
    """Get the Intelligent Exits Unified Pipeline integration instance"""
    return _intelligent_exits_unified_integration

# Enhanced Intelligent Exits functions that use the Unified Pipeline
async def add_exit_rule_unified(ticket: int, symbol: str, direction: str, entry_price: float,
                               initial_sl: float, initial_tp: float, **kwargs) -> bool:
    """Add an exit rule to Intelligent Exits with Unified Pipeline integration"""
    integration = get_intelligent_exits_unified_integration()
    if not integration:
        logger.error("Intelligent Exits Unified Pipeline integration not available")
        return False
    
    return await integration.add_exit_rule(ticket, symbol, direction, entry_price, initial_sl, initial_tp, **kwargs)

async def remove_exit_rule_unified(ticket: int) -> bool:
    """Remove an exit rule from Intelligent Exits with Unified Pipeline integration"""
    integration = get_intelligent_exits_unified_integration()
    if not integration:
        logger.error("Intelligent Exits Unified Pipeline integration not available")
        return False
    
    return await integration.remove_exit_rule(ticket)

def get_intelligent_exits_unified_status() -> Dict[str, Any]:
    """Get Intelligent Exits status with Unified Pipeline integration"""
    integration = get_intelligent_exits_unified_integration()
    if not integration:
        return {'error': 'Intelligent Exits Unified Pipeline integration not available'}
    
    return integration.get_status()

def get_intelligent_exits_unified_rule_status(ticket: int) -> Optional[Dict[str, Any]]:
    """Get exit rule status with Unified Pipeline integration"""
    integration = get_intelligent_exits_unified_integration()
    if not integration:
        return None
    
    return integration.get_exit_rule_status(ticket)

def get_intelligent_exits_unified_action_history(ticket: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get action history with Unified Pipeline integration"""
    integration = get_intelligent_exits_unified_integration()
    if not integration:
        return []
    
    return integration.get_action_history(ticket)
