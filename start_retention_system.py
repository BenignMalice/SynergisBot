#!/usr/bin/env python3
"""
Start Retention System
======================
Starts the hybrid retention system as a background service.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from hybrid_retention_system import HybridRetentionSystem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('retention_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RetentionService:
    """Retention system service manager"""
    
    def __init__(self):
        self.retention_system = HybridRetentionSystem()
        self.is_running = False
        
    async def start(self):
        """Start the retention service"""
        logger.info("Starting Hybrid Retention System...")
        
        try:
            # Start the retention system
            await self.retention_system.start()
            self.is_running = True
            
            logger.info("Retention system started successfully")
            logger.info("Retention policies active:")
            logger.info("  - Recent data (0-6 hours): Keep all")
            logger.info("  - Older data (6-24 hours): Sample every 3rd record")
            logger.info("  - Very old data (24+ hours): Delete completely")
            logger.info("  - Analysis data: Keep 7 days")
            logger.info("  - Cleanup runs every hour")
            
            # Keep running
            while self.is_running:
                await asyncio.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Retention system error: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the retention service"""
        if self.is_running:
            logger.info("Stopping retention system...")
            await self.retention_system.stop()
            self.is_running = False
            logger.info("Retention system stopped")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.is_running = False

async def main():
    """Main function"""
    print("=" * 80)
    print("HYBRID RETENTION SYSTEM SERVICE")
    print("=" * 80)
    
    service = RetentionService()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, service.signal_handler)
    signal.signal(signal.SIGTERM, service.signal_handler)
    
    try:
        await service.start()
    except Exception as e:
        logger.error(f"Service error: {e}")
    finally:
        await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
