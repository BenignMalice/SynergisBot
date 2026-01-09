"""Check if API server startup is executing auto-execution system initialization"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Check if startup_event would execute
print("Checking startup_event code...")
print()

# Read the startup_event function
with open("app/main_api.py", "r", encoding="utf-8") as f:
    content = f.read()
    
    # Find startup_event
    if "async def startup_event" in content:
        print("✅ startup_event function found")
        
        # Check for auto-execution initialization
        if "🤖 Initializing Auto-Execution System" in content:
            print("✅ Auto-execution initialization code found")
        else:
            print("❌ Auto-execution initialization code NOT found")
        
        if "start_auto_execution_system()" in content:
            print("✅ start_auto_execution_system() call found")
        else:
            print("❌ start_auto_execution_system() call NOT found")
        
        # Extract the relevant section
        start_idx = content.find("🤖 Initializing Auto-Execution System")
        if start_idx > 0:
            end_idx = content.find("startup_time = datetime.now()", start_idx)
            if end_idx > start_idx:
                section = content[start_idx:end_idx]
                print("\n📋 Auto-execution initialization section:")
                print("-" * 60)
                for line in section.split('\n')[:15]:
                    print(f"  {line}")
                print("-" * 60)
    else:
        print("❌ startup_event function NOT found")

print()
print("💡 The API server logs go to stdout/stderr (console output)")
print("   Check the console window where start_all_services.bat is running")
print("   Look for these messages:")
print("   • '🤖 Initializing Auto-Execution System...'")
print("   • '✅ Auto-Execution System started'")
print("   • 'Watchdog thread started'")
print("   • Any error messages starting with '❌'")

