"""Test if server can start without errors"""
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_startup():
    """Test startup event without actually running the server"""
    try:
        from app.main_api import startup_event
        print("Testing startup_event...")
        await startup_event()
        print("[OK] Startup event completed successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Startup event failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_startup())
    sys.exit(0 if result else 1)

