#!/usr/bin/env python3
"""
Discord-Only Trading Bot
Trading bot that uses only Discord for notifications (no Telegram)
"""

import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Discord notifications
from discord_notifications import DiscordNotifier

class DiscordOnlyTradingBot:
    def __init__(self):
        self.discord = DiscordNotifier()
        self.running = False
        
        if self.discord.enabled:
            logger.info("SUCCESS: Discord-only trading bot initialized")
        else:
            logger.warning("WARNING: Discord not configured - bot will run without notifications")
    
    async def start(self):
        """Start the trading bot"""
        self.running = True
        logger.info("🚀 Discord-only trading bot started")
        
        # Send startup notification
        if self.discord.enabled:
            self.discord.send_system_alert(
                "BOT_START", 
                "Discord-only trading bot has started successfully"
            )
        
        # Main trading loop
        await self.trading_loop()
    
    async def trading_loop(self):
        """Main trading loop"""
        logger.info("📈 Starting trading loop...")
        
        try:
            while self.running:
                # Simulate trading activity
                await self.check_market_conditions()
                await self.manage_positions()
                await self.check_risk_management()
                
                # Wait before next iteration
                await asyncio.sleep(30)  # Check every 30 seconds
                
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Error in trading loop: {e}")
            if self.discord.enabled:
                self.discord.send_system_alert("ERROR", f"Trading loop error: {e}")
        finally:
            await self.shutdown()
    
    async def check_market_conditions(self):
        """Check market conditions"""
        # Simulate market analysis
        logger.debug("🔍 Checking market conditions...")
        
        # Example: Check if conditions are good for trading
        market_conditions = {
            "volatility": "medium",
            "trend": "bullish",
            "volume": "high"
        }
        
        if market_conditions["volatility"] == "high":
            if self.discord.enabled:
                self.discord.send_risk_alert(
                    "MEDIUM",
                    "High volatility detected",
                    "Reducing position sizes"
                )
    
    async def manage_positions(self):
        """Manage existing positions"""
        logger.debug("💼 Managing positions...")
        
        # Simulate position management
        # In a real bot, this would check MT5 positions
        positions = []  # Empty for now
        
        if len(positions) > 0:
            logger.info(f"📊 Managing {len(positions)} positions")
        else:
            logger.debug("📊 No active positions")
    
    async def check_risk_management(self):
        """Check risk management rules"""
        logger.debug("⚠️ Checking risk management...")
        
        # Simulate risk checks
        risk_level = "low"
        
        if risk_level == "high":
            if self.discord.enabled:
                self.discord.send_risk_alert(
                    "HIGH",
                    "Risk level elevated",
                    "Stopping new trades"
                )
    
    async def simulate_trade(self, symbol, action, price, lot_size):
        """Simulate a trade (for testing)"""
        logger.info(f"📈 Simulating {action} {symbol} at {price}")
        
        if self.discord.enabled:
            self.discord.send_trade_alert(
                symbol=symbol,
                action=action,
                price=price,
                lot_size=lot_size,
                status="OPENED"
            )
    
    async def shutdown(self):
        """Shutdown the bot"""
        logger.info("🛑 Shutting down Discord-only trading bot...")
        
        if self.discord.enabled:
            self.discord.send_system_alert(
                "BOT_STOP", 
                "Discord-only trading bot has stopped"
            )
        
        self.running = False
        logger.info("✅ Bot shutdown complete")

async def main():
    """Main function"""
    print("Discord-Only Trading Bot")
    print("=" * 40)
    
    # Check Discord configuration
    if not os.getenv("DISCORD_WEBHOOK_URL"):
        print("❌ DISCORD_WEBHOOK_URL not found in .env file")
        print("Please add your Discord webhook URL to .env file")
        print("Example: DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...")
        return
    
    # Create and start bot
    bot = DiscordOnlyTradingBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot error: {e}")
    finally:
        await bot.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
