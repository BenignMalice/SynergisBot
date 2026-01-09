# File: synergis_trading_cli.py — Command Line Interface for Synergis Trading Bot
import os
import sys
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def show_menu():
    """Display the main menu"""
    print("\n" + "="*60)
    print("SYNERGIS TRADING BOT - COMMAND LINE INTERFACE")
    print("="*60)
    print("1. Start Trading Bot")
    print("2. Check MT5 Connection")
    print("3. View Active Positions")
    print("4. View Trading History")
    print("5. Test Discord Notifications")
    print("6. View System Status")
    print("7. Exit")
    print("="*60)

def check_mt5_connection():
    """Check MT5 connection status"""
    try:
        from infra.mt5_service import MT5Service
        mt5svc = MT5Service()
        if mt5svc.connect():
            print("SUCCESS: MT5 connected successfully")
            return True
        else:
            print("FAILED: MT5 connection failed")
            return False
    except Exception as e:
        print(f"ERROR: MT5 connection error: {e}")
        return False

def view_active_positions():
    """View active trading positions"""
    try:
        from infra.position_watcher import PositionWatcher
        poswatch = PositionWatcher("./data/positions.json")
        positions = poswatch.get_all_positions()
        
        if positions:
            print(f"\nActive Positions ({len(positions)}):")
            print("-" * 50)
            for ticket, details in positions.items():
                print(f"Ticket: {ticket}")
                print(f"  Symbol: {details.get('symbol', 'N/A')}")
                print(f"  Type: {details.get('type', 'N/A')}")
                print(f"  Volume: {details.get('volume', 'N/A')}")
                print(f"  Price: {details.get('price', 'N/A')}")
                print(f"  SL: {details.get('sl', 'N/A')}")
                print(f"  TP: {details.get('tp', 'N/A')}")
                print(f"  Profit: {details.get('profit', 'N/A')}")
                print("-" * 50)
        else:
            print("No active positions")
    except Exception as e:
        print(f"ERROR: Error viewing positions: {e}")

def view_trading_history():
    """View trading history"""
    try:
        from infra.journal_repo import JournalRepo
        journal = JournalRepo(
            db_path="./data/journal.sqlite",
            csv_path="./data/journal_events.csv",
            csv_enable=True
        )
        
        # Get recent trades
        recent_trades = journal.get_recent_trades(limit=10)
        
        if recent_trades:
            print(f"\nRecent Trading History ({len(recent_trades)} trades):")
            print("-" * 80)
            for trade in recent_trades:
                print(f"Time: {trade.get('timestamp', 'N/A')}")
                print(f"Symbol: {trade.get('symbol', 'N/A')}")
                print(f"Action: {trade.get('action', 'N/A')}")
                print(f"Volume: {trade.get('volume', 'N/A')}")
                print(f"Price: {trade.get('price', 'N/A')}")
                print(f"Profit: {trade.get('profit', 'N/A')}")
                print("-" * 80)
        else:
            print("No trading history found")
    except Exception as e:
        print(f"ERROR: Error viewing trading history: {e}")

def test_discord_notifications():
    """Test Discord notifications"""
    try:
        from discord_notifications import DiscordNotifier
        discord_notifier = DiscordNotifier()
        
        if discord_notifier.enabled:
            print("Testing Discord notifications...")
            
            # Test system alert
            discord_notifier.send_system_alert("TEST", "This is a test message from Synergis Trading Bot CLI")
            
            # Test trade alert
            discord_notifier.send_trade_alert("EURUSD", "BUY", "1.0850", "0.01", "TEST")
            
            print("SUCCESS: Discord notifications sent successfully!")
            print("   Check your Discord channel for the test messages.")
        else:
            print("FAILED: Discord notifications not configured")
            print("   Please set DISCORD_WEBHOOK_URL in your .env file")
    except Exception as e:
        print(f"ERROR: Discord notification test failed: {e}")

def view_system_status():
    """View system status"""
    print("\nSystem Status:")
    print("-" * 30)
    
    # Check environment variables
    openai_key = os.getenv("OPENAI_API_KEY")
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    
    print(f"OpenAI API Key: {'Set' if openai_key else 'Not Set'}")
    print(f"Discord Webhook: {'Set' if discord_webhook else 'Not Set'}")
    
    # Check MT5 connection
    mt5_connected = check_mt5_connection()
    print(f"MT5 Connection: {'Connected' if mt5_connected else 'Disconnected'}")
    
    # Check data files
    data_dir = Path("./data")
    if data_dir.exists():
        print(f"Data Directory: Exists")
        print(f"  Positions: {'Yes' if (data_dir / 'positions.json').exists() else 'No'}")
        print(f"  Journal: {'Yes' if (data_dir / 'journal.sqlite').exists() else 'No'}")
        print(f"  Pendings: {'Yes' if (data_dir / 'pendings.json').exists() else 'No'}")
    else:
        print(f"Data Directory: Not Found")

def start_trading_bot():
    """Start the main trading bot"""
    print("Starting Synergis Trading Bot...")
    print("   Press Ctrl+C to stop the bot")
    print("-" * 50)
    
    try:
        # Import and run the main trading bot
        from synergis_trading import main
        main()
    except KeyboardInterrupt:
        print("\nTrading bot stopped by user")
    except Exception as e:
        print(f"\nTrading bot error: {e}")
        logger.exception("Trading bot error")

def main():
    """Main CLI loop"""
    while True:
        show_menu()
        
        try:
            choice = input("\nEnter your choice (1-7): ").strip()
            
            if choice == "1":
                start_trading_bot()
            elif choice == "2":
                check_mt5_connection()
            elif choice == "3":
                view_active_positions()
            elif choice == "4":
                view_trading_history()
            elif choice == "5":
                test_discord_notifications()
            elif choice == "6":
                view_system_status()
            elif choice == "7":
                print("Goodbye!")
                break
            else:
                print("Invalid choice. Please enter 1-7.")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            logger.exception("CLI error")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
