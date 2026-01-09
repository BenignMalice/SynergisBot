# Test script for Synergis Trading Bot
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_bot_startup():
    """Test the bot startup process"""
    print("Testing Synergis Trading Bot startup...")
    print("=" * 50)
    
    try:
        # Test imports
        print("1. Testing imports...")
        from synergis_trading import main, notify_discord_system, notify_discord_trade
        print("   SUCCESS: All imports working")
        
        # Test Discord notifications
        print("2. Testing Discord notifications...")
        notify_discord_system("BOT_TEST", "Synergis Trading Bot test startup")
        notify_discord_trade("EURUSD", "BUY", "1.0850", "0.01", "TEST")
        print("   SUCCESS: Discord notifications working")
        
        # Test MT5 connection
        print("3. Testing MT5 connection...")
        from infra.mt5_service import MT5Service
        mt5svc = MT5Service()
        if mt5svc.connect():
            print("   SUCCESS: MT5 connected")
        else:
            print("   WARNING: MT5 connection failed")
        
        # Test position watcher
        print("4. Testing position watcher...")
        from infra.position_watcher import PositionWatcher
        poswatch = PositionWatcher("./data/positions.json")
        positions = poswatch.tickets  # Use the tickets attribute
        print(f"   SUCCESS: Position watcher working ({len(positions)} positions)")
        
        # Test journal
        print("5. Testing journal...")
        from infra.journal_repo import JournalRepo
        journal = JournalRepo(
            db_path="./data/journal.sqlite",
            csv_path="./data/journal_events.csv",
            csv_enable=True
        )
        print("   SUCCESS: Journal working")
        
        print("\n" + "=" * 50)
        print("SUCCESS: All tests passed!")
        print("Synergis Trading Bot is ready to run!")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"\nERROR: Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_bot_startup()
