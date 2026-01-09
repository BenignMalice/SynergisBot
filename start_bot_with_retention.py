#!/usr/bin/env python3
"""
Start Bot with Safe Retention
============================
Safely starts the bot with retention system integration
without causing database locking or Binance disconnect issues.
"""

import asyncio
import logging
import subprocess
import sys
import time
import signal
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_with_retention.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BotWithRetentionManager:
    """Manages bot and retention system startup with safety measures"""
    
    def __init__(self):
        self.bot_process = None
        self.retention_process = None
        self.is_running = False
        
    def start(self):
        """Start bot with safe retention system"""
        logger.info("Starting bot with safe retention system...")
        
        try:
            # Step 1: Start retention system first (background)
            logger.info("Starting safe retention system...")
            self.retention_process = subprocess.Popen([
                sys.executable, "safe_retention_integration.py", "--start"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait a moment for retention system to initialize
            time.sleep(5)
            
            # Step 2: Start the main bot
            logger.info("Starting main bot...")
            self.bot_process = subprocess.Popen([
                sys.executable, "chatgpt_bot.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            self.is_running = True
            logger.info("Bot with retention system started successfully")
            
            # Monitor processes
            self._monitor_processes()
            
        except Exception as e:
            logger.error(f"Error starting bot with retention: {e}")
            self.stop()
    
    def stop(self):
        """Stop all processes"""
        logger.info("Stopping bot and retention system...")
        
        if self.bot_process:
            self.bot_process.terminate()
            self.bot_process.wait(timeout=10)
            logger.info("Bot stopped")
        
        if self.retention_process:
            self.retention_process.terminate()
            self.retention_process.wait(timeout=10)
            logger.info("Retention system stopped")
        
        self.is_running = False
        logger.info("All processes stopped")
    
    def _monitor_processes(self):
        """Monitor bot and retention processes"""
        while self.is_running:
            try:
                # Check bot process
                if self.bot_process and self.bot_process.poll() is not None:
                    logger.error("Bot process died, restarting...")
                    self._restart_bot()
                
                # Check retention process
                if self.retention_process and self.retention_process.poll() is not None:
                    logger.warning("Retention process died, restarting...")
                    self._restart_retention()
                
                time.sleep(30)  # Check every 30 seconds
                
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                break
            except Exception as e:
                logger.error(f"Error monitoring processes: {e}")
                time.sleep(60)
    
    def _restart_bot(self):
        """Restart the bot process"""
        try:
            if self.bot_process:
                self.bot_process.terminate()
                self.bot_process.wait(timeout=5)
            
            logger.info("Restarting bot...")
            self.bot_process = subprocess.Popen([
                sys.executable, "chatgpt_bot.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            logger.info("Bot restarted successfully")
            
        except Exception as e:
            logger.error(f"Error restarting bot: {e}")
    
    def _restart_retention(self):
        """Restart the retention system"""
        try:
            if self.retention_process:
                self.retention_process.terminate()
                self.retention_process.wait(timeout=5)
            
            logger.info("Restarting retention system...")
            self.retention_process = subprocess.Popen([
                sys.executable, "safe_retention_integration.py", "--start"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            logger.info("Retention system restarted successfully")
            
        except Exception as e:
            logger.error(f"Error restarting retention system: {e}")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.is_running = False
        self.stop()

def main():
    """Main function"""
    print("=" * 80)
    print("BOT WITH SAFE RETENTION SYSTEM")
    print("=" * 80)
    
    manager = BotWithRetentionManager()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, manager.signal_handler)
    signal.signal(signal.SIGTERM, manager.signal_handler)
    
    try:
        manager.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Manager error: {e}")
    finally:
        manager.stop()

if __name__ == "__main__":
    main()
