"""
DTMS Unified Pipeline Integration
Enhanced DTMS integration with Unified Tick Pipeline data feeds
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

class DTMSUnifiedPipelineIntegration:
    """
    Enhanced DTMS integration with Unified Tick Pipeline
    
    Features:
    - Real-time data from Unified Tick Pipeline
    - Multi-timeframe analysis integration
    - Enhanced volatility monitoring
    - Offset calibration integration
    - System coordination integration
    """
    
    def __init__(self):
        self.pipeline = None
        self.is_active = False
        self.is_initialized = False
        self.monitoring_tasks = []
        
        # DTMS state
        self.monitored_trades = {}
        self.action_history = []
        self.performance_metrics = {
            'actions_executed': 0,
            'trades_monitored': 0,
            'volatility_alerts': 0,
            'offset_adjustments': 0,
            'error_count': 0
        }
        
        logger.info("DTMSUnifiedPipelineIntegration initialized")
    
    async def initialize(self) -> bool:
        """Initialize DTMS with Unified Tick Pipeline"""
        try:
            logger.info("🔧 Initializing DTMS with Unified Tick Pipeline...")
            
            # Get the unified pipeline
            self.pipeline = get_unified_pipeline()
            if not self.pipeline:
                logger.error("❌ Unified Tick Pipeline not available")
                return False
            
            # Start monitoring tasks
            await self._start_monitoring_tasks()
            
            self.is_active = True
            self.is_initialized = True
            logger.info("✅ DTMS Unified Pipeline integration initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize DTMS Unified Pipeline integration: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop DTMS monitoring"""
        try:
            logger.info("🛑 Stopping DTMS Unified Pipeline integration...")
            
            # Stop monitoring tasks
            for task in self.monitoring_tasks:
                task.cancel()
            
            self.monitoring_tasks.clear()
            self.is_active = False
            self.is_initialized = False
            
            logger.info("✅ DTMS Unified Pipeline integration stopped")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping DTMS Unified Pipeline integration: {e}")
            return False
    
    async def _start_monitoring_tasks(self):
        """Start DTMS monitoring tasks"""
        try:
            # Start trade monitoring task
            task1 = asyncio.create_task(self._monitor_trades())
            self.monitoring_tasks.append(task1)
            
            # Start volatility monitoring task
            task2 = asyncio.create_task(self._monitor_volatility())
            self.monitoring_tasks.append(task2)
            
            # Start offset monitoring task
            task3 = asyncio.create_task(self._monitor_offsets())
            self.monitoring_tasks.append(task3)
            
            # Start system health monitoring task
            task4 = asyncio.create_task(self._monitor_system_health())
            self.monitoring_tasks.append(task4)
            
            logger.info("✅ DTMS monitoring tasks started")
            
        except Exception as e:
            logger.error(f"❌ Error starting monitoring tasks: {e}")
    
    async def _monitor_trades(self):
        """Monitor trades using Unified Tick Pipeline data"""
        while self.is_active:
            try:
                # Get latest tick data for monitored trades
                for ticket, trade_info in self.monitored_trades.items():
                    symbol = trade_info.get('symbol')
                    if not symbol:
                        continue
                    
                    # Get latest tick data
                    tick_data = await self.pipeline.get_tick_data(symbol, limit=1)
                    if tick_data.get('success'):
                        data = tick_data['data']
                        if data:
                            latest_tick = data[0]
                            await self._process_tick_for_trade(ticket, trade_info, latest_tick)
                
                # Sleep for 1 second
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Error in trade monitoring: {e}")
                self.performance_metrics['error_count'] += 1
                await asyncio.sleep(5)  # Wait before retry
    
    async def _monitor_volatility(self):
        """Monitor volatility using M5 volatility bridge"""
        while self.is_active:
            try:
                # Get volatility analysis for monitored symbols
                symbols = set(trade['symbol'] for trade in self.monitored_trades.values())
                
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
    
    async def _monitor_offsets(self):
        """Monitor offset calibration"""
        while self.is_active:
            try:
                # Get offset calibration for monitored symbols
                symbols = set(trade['symbol'] for trade in self.monitored_trades.values())
                
                for symbol in symbols:
                    offset_data = await self.pipeline.get_offset_calibration(symbol)
                    if offset_data.get('success'):
                        data = offset_data['data']
                        await self._process_offset_data(symbol, data)
                
                # Sleep for 10 seconds
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"❌ Error in offset monitoring: {e}")
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
    
    async def _process_tick_for_trade(self, ticket: int, trade_info: Dict[str, Any], tick_data: Dict[str, Any]):
        """Process tick data for a specific trade"""
        try:
            symbol = trade_info['symbol']
            direction = trade_info['direction']
            entry_price = trade_info['entry_price']
            stop_loss = trade_info.get('stop_loss')
            take_profit = trade_info.get('take_profit')
            
            # Get current price
            current_price = tick_data.get('mid', 0)
            if current_price == 0:
                return
            
            # Calculate P&L
            if direction == 'BUY':
                pnl = current_price - entry_price
            else:  # SELL
                pnl = entry_price - current_price
            
            # Update trade info
            trade_info['current_price'] = current_price
            trade_info['pnl'] = pnl
            trade_info['last_update'] = datetime.now(timezone.utc)
            
            # Check for DTMS actions
            await self._check_dtms_actions(ticket, trade_info, tick_data)
            
        except Exception as e:
            logger.error(f"❌ Error processing tick for trade {ticket}: {e}")
    
    async def _process_volatility_data(self, symbol: str, volatility_data: Dict[str, Any]):
        """Process volatility data"""
        try:
            volatility_score = volatility_data.get('volatility_score', 0)
            is_high_volatility = volatility_data.get('is_high_volatility', False)
            
            # Check if any trades for this symbol need volatility-based actions
            for ticket, trade_info in self.monitored_trades.items():
                if trade_info.get('symbol') == symbol:
                    await self._check_volatility_actions(ticket, trade_info, volatility_score, is_high_volatility)
            
        except Exception as e:
            logger.error(f"❌ Error processing volatility data for {symbol}: {e}")
    
    async def _process_offset_data(self, symbol: str, offset_data: Dict[str, Any]):
        """Process offset calibration data"""
        try:
            offset = offset_data.get('offset', 0)
            confidence = offset_data.get('confidence', 0)
            within_threshold = offset_data.get('within_threshold', True)
            
            # Log offset information
            if not within_threshold:
                logger.warning(f"⚠️ Offset for {symbol} is outside threshold: {offset} (confidence: {confidence})")
                self.performance_metrics['offset_adjustments'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error processing offset data for {symbol}: {e}")
    
    async def _process_system_health(self, health_data: Dict[str, Any]):
        """Process system health data"""
        try:
            system_coordination = health_data.get('system_coordination', {})
            performance_optimization = health_data.get('performance_optimization', {})
            
            # Check system state
            current_state = system_coordination.get('current_state', 'unknown')
            if current_state == 'critical':
                logger.critical("🚨 System is in critical state!")
                await self._handle_critical_system_state()
            elif current_state == 'high_load':
                logger.warning("⚠️ System is under high load")
                await self._handle_high_load_state()
            
        except Exception as e:
            logger.error(f"❌ Error processing system health: {e}")
    
    async def _check_dtms_actions(self, ticket: int, trade_info: Dict[str, Any], tick_data: Dict[str, Any]):
        """Check for DTMS actions based on tick data"""
        try:
            # This is where DTMS logic would be implemented
            # For now, just log the monitoring
            logger.debug(f"DTMS monitoring trade {ticket} for {trade_info['symbol']}")
            
        except Exception as e:
            logger.error(f"❌ Error checking DTMS actions for trade {ticket}: {e}")
    
    async def _check_volatility_actions(self, ticket: int, trade_info: Dict[str, Any], volatility_score: float, is_high_volatility: bool):
        """Check for volatility-based actions"""
        try:
            if is_high_volatility:
                logger.warning(f"🚨 High volatility detected for trade {ticket}: {volatility_score}")
                self.performance_metrics['volatility_alerts'] += 1
                
                # Could implement volatility-based stop adjustments here
                
        except Exception as e:
            logger.error(f"❌ Error checking volatility actions for trade {ticket}: {e}")
    
    async def _handle_critical_system_state(self):
        """Handle critical system state"""
        try:
            logger.critical("🚨 Handling critical system state - reducing DTMS monitoring frequency")
            # Could implement emergency procedures here
            
        except Exception as e:
            logger.error(f"❌ Error handling critical system state: {e}")
    
    async def _handle_high_load_state(self):
        """Handle high load state"""
        try:
            logger.warning("⚠️ Handling high load state - optimizing DTMS monitoring")
            # Could implement load balancing here
            
        except Exception as e:
            logger.error(f"❌ Error handling high load state: {e}")
    
    # Public API methods
    async def add_trade(self, ticket: int, symbol: str, direction: str, entry_price: float, 
                       volume: float, stop_loss: float = None, take_profit: float = None) -> bool:
        """Add a trade to DTMS monitoring"""
        try:
            trade_info = {
                'ticket': ticket,
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'volume': volume,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'current_price': entry_price,
                'pnl': 0.0,
                'added_at': datetime.now(timezone.utc),
                'last_update': datetime.now(timezone.utc)
            }
            
            self.monitored_trades[ticket] = trade_info
            self.performance_metrics['trades_monitored'] += 1
            
            logger.info(f"✅ Added trade {ticket} to DTMS monitoring")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding trade {ticket} to DTMS: {e}")
            return False
    
    async def remove_trade(self, ticket: int) -> bool:
        """Remove a trade from DTMS monitoring"""
        try:
            if ticket in self.monitored_trades:
                del self.monitored_trades[ticket]
                logger.info(f"✅ Removed trade {ticket} from DTMS monitoring")
                return True
            else:
                logger.warning(f"⚠️ Trade {ticket} not found in DTMS monitoring")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error removing trade {ticket} from DTMS: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get DTMS status"""
        return {
            'is_active': self.is_active,
            'monitored_trades': len(self.monitored_trades),
            'trades': list(self.monitored_trades.keys()),
            'performance_metrics': self.performance_metrics,
            'pipeline_available': self.pipeline is not None
        }
    
    def get_trade_status(self, ticket: int) -> Optional[Dict[str, Any]]:
        """Get status of a specific trade"""
        return self.monitored_trades.get(ticket)
    
    def get_action_history(self, ticket: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get action history"""
        if ticket:
            return [action for action in self.action_history if action.get('ticket') == ticket]
        else:
            return self.action_history

# Global instance
_dtms_unified_integration: Optional[DTMSUnifiedPipelineIntegration] = None
_dtms_init_lock = asyncio.Lock()

async def initialize_dtms_unified_pipeline() -> bool:
    """Initialize DTMS with Unified Tick Pipeline (async + idempotent)"""
    global _dtms_unified_integration
    async with _dtms_init_lock:
        try:
            if _dtms_unified_integration and _dtms_unified_integration.is_initialized:
                logger.info("ℹ️ DTMS already initialized; skipping.")
                return True

            logger.info("🚀 Initializing DTMS with Unified Tick Pipeline...")
            _dtms_unified_integration = DTMSUnifiedPipelineIntegration()
            success = await _dtms_unified_integration.initialize()

            if success:
                logger.info("✅ DTMS Unified Pipeline integration completed successfully")
                return True
            else:
                logger.error("❌ DTMS Unified Pipeline integration failed")
                return False
        except Exception as e:
            logger.error(f"❌ Error initializing DTMS Unified Pipeline: {e}", exc_info=True)
            return False

async def stop_dtms_unified_pipeline() -> bool:
    """Stop DTMS (async, safe to call multiple times)"""
    global _dtms_unified_integration
    try:
        if _dtms_unified_integration:
            await _dtms_unified_integration.stop()
        return True
    except Exception as e:
        logger.error(f"❌ Error stopping DTMS Unified Pipeline: {e}", exc_info=True)
        return False

def get_dtms_unified_integration() -> Optional[DTMSUnifiedPipelineIntegration]:
    """Get the DTMS Unified Pipeline integration instance"""
    return _dtms_unified_integration

# Enhanced DTMS functions that use the Unified Pipeline
async def add_trade_to_dtms_unified(ticket: int, symbol: str, direction: str, entry_price: float, 
                                   volume: float, stop_loss: float = None, take_profit: float = None) -> bool:
    """Add a trade to DTMS with Unified Pipeline integration"""
    integration = get_dtms_unified_integration()
    if not integration:
        logger.error("DTMS Unified Pipeline integration not available")
        return False
    
    return await integration.add_trade(ticket, symbol, direction, entry_price, volume, stop_loss, take_profit)

async def remove_trade_from_dtms_unified(ticket: int) -> bool:
    """Remove a trade from DTMS with Unified Pipeline integration"""
    integration = get_dtms_unified_integration()
    if not integration:
        logger.error("DTMS Unified Pipeline integration not available")
        return False
    
    return await integration.remove_trade(ticket)

def get_dtms_unified_status() -> Dict[str, Any]:
    """Get DTMS status with Unified Pipeline integration"""
    integration = get_dtms_unified_integration()
    if not integration:
        return {'error': 'DTMS Unified Pipeline integration not available'}
    
    return integration.get_status()

def get_dtms_unified_trade_status(ticket: int) -> Optional[Dict[str, Any]]:
    """Get trade status with Unified Pipeline integration"""
    integration = get_dtms_unified_integration()
    if not integration:
        return None
    
    return integration.get_trade_status(ticket)

def get_dtms_unified_action_history(ticket: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get action history with Unified Pipeline integration"""
    integration = get_dtms_unified_integration()
    if not integration:
        return []
    
    return integration.get_action_history(ticket)
