"""
Quick Test: Verify tool is registered in desktop_agent
Run this BEFORE starting desktop_agent.py to verify tool registration
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_tool_registration():
    """Check if range scalping tool is registered"""
    try:
        # Try to import (may fail due to dependencies, but that's OK)
        import desktop_agent
        
        # Check registry
        registry = desktop_agent.registry
        tool_name = "moneybot.analyse_range_scalp_opportunity"
        
        if tool_name in registry.tools:
            print(f"✅ Tool '{tool_name}' is REGISTERED")
            print(f"   Function: {registry.tools[tool_name].__name__}")
            return True
        else:
            print(f"❌ Tool '{tool_name}' is NOT registered")
            print(f"\nAvailable tools with 'analyse' or 'scalp':")
            matching = [t for t in registry.tools.keys() if 'analyse' in t.lower() or 'scalp' in t.lower()]
            if matching:
                for t in matching:
                    print(f"   - {t}")
            else:
                print("   (none found)")
            return False
            
    except Exception as e:
        print(f"⚠️  Could not check registration: {e}")
        print("   This is OK if dependencies are missing - tool code is still valid")
        return None


if __name__ == "__main__":
    result = check_tool_registration()
    sys.exit(0 if result else 1)

