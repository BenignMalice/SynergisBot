#!/usr/bin/env python3
"""
Initialize DTMS System
This script initializes the DTMS system with required services
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_dtms_system():
    """Initialize the DTMS system with all required services"""
    try:
        # Import required services
        from infra.mt5_service import MT5Service
        from infra.binance_service import BinanceService
        from dtms_integration import initialize_dtms
        
        logger.info("🚀 Starting DTMS system initialization...")
        
        # Initialize MT5 service
        logger.info("📊 Initializing MT5 service...")
        mt5_service = MT5Service()
        if not mt5_service.connect():
            logger.error("❌ Failed to connect to MT5")
            return False
        logger.info("✅ MT5 service connected")
        
        # Initialize Binance service
        logger.info("📈 Initializing Binance service...")
        try:
            binance_service = BinanceService()
            logger.info("✅ Binance service initialized")
        except Exception as e:
            logger.warning(f"⚠️ Binance service not available: {e}")
            binance_service = None
        
        # Initialize DTMS system
        logger.info("🛡️ Initializing DTMS system...")
        success = initialize_dtms(
            mt5_service=mt5_service,
            binance_service=binance_service,
            telegram_service=None  # No Telegram service needed for Discord bot
        )
        
        if success:
            logger.info("✅ DTMS system initialized successfully!")
            logger.info("🎯 DTMS is now ready to protect your trades")
            return True
        else:
            logger.error("❌ Failed to initialize DTMS system")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error initializing DTMS system: {e}")
        return False

if __name__ == "__main__":
    success = initialize_dtms_system()
    if success:
        print("\n🎉 DTMS system is now running and ready!")
        print("You can now use DTMS commands via the API or ChatGPT interface.")
    else:
        print("\n❌ Failed to initialize DTMS system.")
        print("Please check the logs for more details.")
