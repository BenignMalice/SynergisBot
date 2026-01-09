"""Check auto-execution monitoring status in detail"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from chatgpt_auto_execution_tools import tool_get_auto_system_status

async def check_status():
    try:
        result = await tool_get_auto_system_status({})
        data = result.get('data', {})
        
        system_status = data.get('system_status', data)
        running = system_status.get('running', False)
        thread_alive = system_status.get('thread_alive', False)
        pending_count = system_status.get('pending_plans', 0)
        check_interval = system_status.get('check_interval', 'Unknown')
        
        print("=" * 80)
        print("AUTO-EXECUTION SYSTEM STATUS")
        print("=" * 80)
        print(f"Running: {running}")
        print(f"Thread Alive: {thread_alive}")
        print(f"Pending Plans: {pending_count}")
        print(f"Check Interval: {check_interval} seconds")
        
        print("\n" + "=" * 80)
        if running and thread_alive:
            print("STATUS: Monitoring is ACTIVE - plans will be executed")
            print("  - System is running and monitoring thread is alive")
            print("  - Plans will be checked every 30 seconds")
            print("  - Trades will execute automatically when conditions are met")
        elif running and not thread_alive:
            print("WARNING: System marked as running but thread is dead")
            print("  - Action needed: Restart main_api.py")
        elif not running:
            print("WARNING: System is NOT running - plans will NOT execute")
            print("  - Action needed: Restart main_api.py to start monitoring")
            print("  - The auto-execution system starts automatically with main_api.py")
    except Exception as e:
        print(f"Error checking status: {e}")
        import traceback
        traceback.print_exc()
        print("\nIs main_api.py running? The auto-execution system starts with main_api.py")

if __name__ == "__main__":
    asyncio.run(check_status())

