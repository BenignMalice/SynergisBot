"""
Auto Execution System Integration
Integrates the auto execution system with the main bot.
"""

import logging
import threading
import time
from auto_execution_system import start_auto_execution_system, stop_auto_execution_system

logger = logging.getLogger(__name__)

def start_auto_execution_integration():
    """Start the auto execution system integration"""
    try:
        logger.info("Starting auto execution system integration...")
        
        # Start the auto execution system
        start_auto_execution_system()
        
        logger.info("✅ Auto execution system integration started successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to start auto execution system integration: {e}")
        return False

def stop_auto_execution_integration():
    """Stop the auto execution system integration"""
    try:
        logger.info("Stopping auto execution system integration...")
        
        # Stop the auto execution system
        stop_auto_execution_system()
        
        logger.info("✅ Auto execution system integration stopped successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to stop auto execution system integration: {e}")
        return False

def get_auto_execution_status():
    """Get the status of the auto execution system"""
    try:
        from auto_execution_system import get_auto_execution_system
        
        system = get_auto_execution_system()
        status = system.get_status()
        
        return {
            "success": True,
            "status": status
        }
        
    except Exception as e:
        logger.error(f"Failed to get auto execution status: {e}")
        return {
            "success": False,
            "error": str(e)
        }
