#!/usr/bin/env python3
"""
Simple Trading Bot
A basic trading bot that works without external dependencies
"""

import os
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleTradingBot:
    def __init__(self):
        self.running = False
        self.positions = []
        self.start_time = datetime.now()
        
        logger.info("🚀 Simple Trading Bot initialized")
    
    def start(self):
        """Start the trading bot"""
        self.running = True
        logger.info("📈 Simple Trading Bot started")
        
        try:
            while self.running:
                # Main trading loop
                self.check_market_conditions()
                self.manage_positions()
                self.check_risk_management()
                
                # Wait before next iteration
                time.sleep(30)  # Check every 30 seconds
                
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Error in trading loop: {e}")
        finally:
            self.shutdown()
    
    def check_market_conditions(self):
        """Check market conditions"""
        logger.debug("🔍 Checking market conditions...")
        
        # Simulate market analysis
        market_conditions = {
            "volatility": "medium",
            "trend": "bullish",
            "volume": "high",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        
        logger.info(f"📊 Market: {market_conditions['trend']} trend, {market_conditions['volatility']} volatility")
        
        # Check for high volatility
        if market_conditions["volatility"] == "high":
            logger.warning("⚠️ High volatility detected - reducing position sizes")
    
    def manage_positions(self):
        """Manage existing positions"""
        logger.debug("💼 Managing positions...")
        
        # Simulate position management
        if len(self.positions) > 0:
            logger.info(f"📊 Managing {len(self.positions)} positions")
            
            # Check each position
            for i, position in enumerate(self.positions):
                logger.debug(f"Position {i+1}: {position}")
        else:
            logger.debug("📊 No active positions")
    
    def check_risk_management(self):
        """Check risk management rules"""
        logger.debug("⚠️ Checking risk management...")
        
        # Simulate risk checks
        risk_level = "low"
        max_positions = 5
        current_positions = len(self.positions)
        
        if current_positions >= max_positions:
            logger.warning(f"⚠️ Maximum positions reached ({current_positions}/{max_positions})")
            risk_level = "high"
        
        if risk_level == "high":
            logger.warning("🚨 High risk level - stopping new trades")
    
    def simulate_trade(self, symbol, action, price, lot_size):
        """Simulate a trade (for testing)"""
        logger.info(f"📈 Simulating {action} {symbol} at {price} (lot size: {lot_size})")
        
        # Add to positions
        trade = {
            "symbol": symbol,
            "action": action,
            "price": price,
            "lot_size": lot_size,
            "timestamp": datetime.now(),
            "status": "OPENED"
        }
        
        self.positions.append(trade)
        logger.info(f"✅ Trade opened: {symbol} {action} at {price}")
    
    def close_trade(self, symbol, price, profit=None):
        """Close a trade"""
        for i, position in enumerate(self.positions):
            if position["symbol"] == symbol and position["status"] == "OPENED":
                position["status"] = "CLOSED"
                position["close_price"] = price
                position["close_time"] = datetime.now()
                
                if profit:
                    position["profit"] = profit
                    logger.info(f"💰 Trade closed: {symbol} at {price} (Profit: {profit})")
                else:
                    logger.info(f"📉 Trade closed: {symbol} at {price}")
                
                break
    
    def get_status(self):
        """Get bot status"""
        uptime = datetime.now() - self.start_time
        return {
            "running": self.running,
            "uptime": str(uptime).split('.')[0],  # Remove microseconds
            "positions": len(self.positions),
            "active_positions": len([p for p in self.positions if p["status"] == "OPENED"])
        }
    
    def shutdown(self):
        """Shutdown the bot"""
        logger.info("🛑 Shutting down Simple Trading Bot...")
        
        # Close all open positions
        for position in self.positions:
            if position["status"] == "OPENED":
                self.close_trade(position["symbol"], "0.0000", "Simulated close")
        
        self.running = False
        logger.info("✅ Bot shutdown complete")

def main():
    """Main function"""
    print("Simple Trading Bot")
    print("=" * 30)
    print("This bot runs without external dependencies")
    print("Press Ctrl+C to stop")
    print()
    
    # Create and start bot
    bot = SimpleTradingBot()
    
    try:
        # Simulate some trades for demonstration
        bot.simulate_trade("EURUSD", "BUY", "1.0850", "0.01")
        bot.simulate_trade("GBPUSD", "SELL", "1.2650", "0.01")
        
        # Start main loop
        bot.start()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot error: {e}")
    finally:
        bot.shutdown()

if __name__ == "__main__":
    main()
