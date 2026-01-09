"""
DTMS Telegram Adapter
Wrapper for Telegram service integration with DTMS
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class DTMSTelegramAdapter:
    """
    Telegram adapter for DTMS system.
    Provides enhanced Telegram functionality for defensive trade management.
    """
    
    def __init__(self, telegram_service):
        self.telegram_service = telegram_service
        
        logger.info("DTMSTelegramAdapter initialized")
    
    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send message via Telegram"""
        try:
            if not self.telegram_service:
                logger.info(f"DTMS Notification: {message}")
                return True
            
            return self.telegram_service.send_message(message, parse_mode)
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def send_alert(self, alert_type: str, symbol: str, message: str) -> bool:
        """Send formatted alert"""
        try:
            # Format alert message
            formatted_message = f"🚨 DTMS {alert_type.upper()}\n"
            formatted_message += f"Symbol: {symbol}\n"
            formatted_message += f"Message: {message}\n"
            formatted_message += f"Time: {self._get_current_time()}"
            
            return self.send_message(formatted_message)
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False
    
    def send_trade_update(self, ticket: int, symbol: str, action: str, details: str) -> bool:
        """Send trade update notification"""
        try:
            # Format trade update message
            formatted_message = f"📊 DTMS Trade Update\n"
            formatted_message += f"Ticket: {ticket}\n"
            formatted_message += f"Symbol: {symbol}\n"
            formatted_message += f"Action: {action}\n"
            formatted_message += f"Details: {details}\n"
            formatted_message += f"Time: {self._get_current_time()}"
            
            return self.send_message(formatted_message)
        except Exception as e:
            logger.error(f"Failed to send trade update: {e}")
            return False
    
    def send_state_transition(self, ticket: int, symbol: str, from_state: str, to_state: str, reason: str) -> bool:
        """Send state transition notification"""
        try:
            # Format state transition message
            formatted_message = f"🔄 DTMS State Transition\n"
            formatted_message += f"Ticket: {ticket}\n"
            formatted_message += f"Symbol: {symbol}\n"
            formatted_message += f"Transition: {from_state} → {to_state}\n"
            formatted_message += f"Reason: {reason}\n"
            formatted_message += f"Time: {self._get_current_time()}"
            
            return self.send_message(formatted_message)
        except Exception as e:
            logger.error(f"Failed to send state transition: {e}")
            return False
    
    def send_system_status(self, status_data: Dict[str, Any]) -> bool:
        """Send system status notification"""
        try:
            # Format system status message
            formatted_message = f"📈 DTMS System Status\n"
            formatted_message += f"Monitoring: {'Active' if status_data.get('monitoring_active') else 'Inactive'}\n"
            formatted_message += f"Uptime: {status_data.get('uptime_human', 'Unknown')}\n"
            formatted_message += f"Active Trades: {status_data.get('active_trades', 0)}\n"
            
            # Add trades by state
            trades_by_state = status_data.get('trades_by_state', {})
            if trades_by_state:
                formatted_message += f"States: "
                state_parts = []
                for state, count in trades_by_state.items():
                    state_parts.append(f"{state}({count})")
                formatted_message += ", ".join(state_parts) + "\n"
            
            # Add performance metrics
            performance = status_data.get('performance', {})
            if performance:
                formatted_message += f"Fast Checks: {performance.get('fast_checks_total', 0)}\n"
                formatted_message += f"Deep Checks: {performance.get('deep_checks_total', 0)}\n"
                formatted_message += f"Actions: {performance.get('actions_executed', 0)}\n"
                formatted_message += f"Transitions: {performance.get('state_transitions', 0)}\n"
            
            formatted_message += f"Time: {self._get_current_time()}"
            
            return self.send_message(formatted_message)
        except Exception as e:
            logger.error(f"Failed to send system status: {e}")
            return False
    
    def send_error_notification(self, error_type: str, error_message: str, context: str = "") -> bool:
        """Send error notification"""
        try:
            # Format error message
            formatted_message = f"❌ DTMS Error\n"
            formatted_message += f"Type: {error_type}\n"
            formatted_message += f"Message: {error_message}\n"
            if context:
                formatted_message += f"Context: {context}\n"
            formatted_message += f"Time: {self._get_current_time()}"
            
            return self.send_message(formatted_message)
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
            return False
    
    def _get_current_time(self) -> str:
        """Get current time as formatted string"""
        try:
            from datetime import datetime
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "Unknown"
