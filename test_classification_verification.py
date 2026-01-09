#!/usr/bin/env python3
"""
Classification System Verification Script

This script helps verify that the classification system is properly configured
and ready for manual testing. It does NOT execute trades - it only checks
configuration and system readiness.
"""

import os
import sys
from pathlib import Path

# Try to load environment variables (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available, use system environment variables

def check_feature_flag():
    """Check if feature flag is enabled"""
    flag = os.getenv("ENABLE_TRADE_TYPE_CLASSIFICATION", "0")
    enabled = flag.lower() in ("1", "true", "yes")
    
    print("=" * 70)
    print("Feature Flag Check")
    print("=" * 70)
    if enabled:
        print("OK: ENABLE_TRADE_TYPE_CLASSIFICATION=1 (Enabled)")
        return True
    else:
        print("WARNING: ENABLE_TRADE_TYPE_CLASSIFICATION=0 (Disabled)")
        print("   -> Classification will not run. Enable in .env file.")
        return False

def check_metrics_config():
    """Check metrics collection configuration"""
    enabled = os.getenv("CLASSIFICATION_METRICS_ENABLED", "1").lower() in ("1", "true", "yes")
    
    print("\n" + "=" * 70)
    print("Metrics Configuration Check")
    print("=" * 70)
    if enabled:
        print("OK: CLASSIFICATION_METRICS_ENABLED=1 (Enabled)")
    else:
        print("INFO: CLASSIFICATION_METRICS_ENABLED=0 (Disabled)")
        print("   -> Metrics will not be collected.")
    
    daily = os.getenv("CLASSIFICATION_METRICS_DISCORD_DAILY", "1").lower() in ("1", "true", "yes")
    weekly = os.getenv("CLASSIFICATION_METRICS_DISCORD_WEEKLY", "1").lower() in ("1", "true", "yes")
    
    if enabled:
        if daily:
            print("OK: Daily Discord summaries enabled")
        else:
            print("INFO: Daily Discord summaries disabled")
        
        if weekly:
            print("OK: Weekly Discord summaries enabled")
        else:
            print("INFO: Weekly Discord summaries disabled")
    
    return enabled

def check_discord_config():
    """Check Discord webhook configuration"""
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
    
    print("\n" + "=" * 70)
    print("Discord Configuration Check")
    print("=" * 70)
    if webhook:
        print("OK: DISCORD_WEBHOOK_URL configured")
        print(f"   -> Webhook URL: {webhook[:50]}...")
        return True
    else:
        print("WARNING: DISCORD_WEBHOOK_URL not configured")
        print("   -> Discord notifications will not be sent.")
        print("   -> Task 25 (Discord verification) will fail.")
        return False

def check_module_imports():
    """Check that required modules can be imported"""
    print("\n" + "=" * 70)
    print("Module Import Check")
    print("=" * 70)
    
    modules_ok = True
    
    # Check TradeTypeClassifier
    try:
        from infra.trade_type_classifier import TradeTypeClassifier
        print("OK: TradeTypeClassifier module available")
    except ImportError as e:
        print(f"ERROR: Cannot import TradeTypeClassifier: {e}")
        modules_ok = False
    
    # Check ClassificationMetrics
    try:
        from infra.classification_metrics import ClassificationMetrics
        print("OK: ClassificationMetrics module available")
    except ImportError as e:
        print(f"ERROR: Cannot import ClassificationMetrics: {e}")
        modules_ok = False
    
    # Check SessionAnalyzer
    try:
        from infra.session_analyzer import SessionAnalyzer
        print("OK: SessionAnalyzer module available")
    except ImportError as e:
        print(f"ERROR: Cannot import SessionAnalyzer: {e}")
        modules_ok = False
    
    # Check DiscordNotifier
    try:
        from discord_notifications import DiscordNotifier
        print("OK: DiscordNotifier module available")
    except ImportError as e:
        print(f"WARNING: Cannot import DiscordNotifier: {e}")
        print("   -> Discord notifications may not work")
    
    return modules_ok

def check_config_file():
    """Check config.py for required settings"""
    print("\n" + "=" * 70)
    print("Config File Check")
    print("=" * 70)
    
    try:
        # Try to read config.py directly to avoid import issues
        config_path = Path("config.py")
        if not config_path.exists():
            print("WARNING: config.py not found")
            return False
        
        config_content = config_path.read_text(encoding="utf-8")
        
        if "ENABLE_TRADE_TYPE_CLASSIFICATION" in config_content:
            print("OK: ENABLE_TRADE_TYPE_CLASSIFICATION setting found in config.py")
        else:
            print("ERROR: ENABLE_TRADE_TYPE_CLASSIFICATION setting not found")
            return False
        
        if "CLASSIFICATION_METRICS_ENABLED" in config_content:
            print("OK: CLASSIFICATION_METRICS_ENABLED setting found")
        else:
            print("WARNING: CLASSIFICATION_METRICS_ENABLED setting not found")
        
        if "INTELLIGENT_EXITS_BREAKEVEN_PCT" in config_content:
            print("OK: INTELLIGENT_EXITS settings found")
        else:
            print("WARNING: INTELLIGENT_EXITS settings not found")
        
        return True
    except Exception as e:
        print(f"ERROR: Cannot check config.py: {e}")
        return False

def check_desktop_agent_integration():
    """Check that desktop_agent has classification integration"""
    print("\n" + "=" * 70)
    print("Desktop Agent Integration Check")
    print("=" * 70)
    
    try:
        # Read desktop_agent.py source directly to avoid import issues
        desktop_agent_path = Path("desktop_agent.py")
        if not desktop_agent_path.exists():
            print("WARNING: desktop_agent.py not found")
            return False
        
        desktop_agent_source = desktop_agent_path.read_text(encoding="utf-8")
        
        # Check if tool_toggle_intelligent_exits exists
        if "def tool_toggle_intelligent_exits" in desktop_agent_source or "@registry.register" in desktop_agent_source and "tool_toggle_intelligent_exits" in desktop_agent_source:
            print("OK: tool_toggle_intelligent_exits function found")
        else:
            print("WARNING: tool_toggle_intelligent_exits function not found")
            return False
        
        # Check if classification code is present
        if "ENABLE_TRADE_TYPE_CLASSIFICATION" in desktop_agent_source:
            print("OK: Classification feature flag check found in desktop_agent")
        else:
            print("WARNING: Classification code may not be integrated")
            return False
        
        if "TradeTypeClassifier" in desktop_agent_source:
            print("OK: TradeTypeClassifier import found")
        else:
            print("WARNING: TradeTypeClassifier may not be imported")
            return False
        
        if "record_classification_metric" in desktop_agent_source:
            print("OK: Metrics recording found")
        else:
            print("WARNING: Metrics recording may not be integrated")
            return False
            
        if "discord_notifier.send_system_alert" in desktop_agent_source or "DiscordNotifier" in desktop_agent_source:
            print("OK: Discord notification code found")
        else:
            print("INFO: Discord notification code may not be integrated")
        
        return True
    except Exception as e:
        print(f"ERROR: Cannot check desktop_agent.py: {e}")
        return False

def print_test_summary():
    """Print summary of what to test"""
    print("\n" + "=" * 70)
    print("Manual Testing Tasks Summary")
    print("=" * 70)
    print("""
Task 21: Test Manual Override
  - Test !force:scalp override
  - Test !force:intraday override
  - Verify override takes priority

Task 22: Test Edge Cases
  - Missing ATR data
  - Missing session data
  - Missing comment
  - Invalid stop size
  - Very small stop size

Task 23: Manual Scalp Trade Verification
  - Open scalp trade
  - Enable intelligent exits
  - Verify SCALP classification
  - Verify 25%/40%/70% parameters

Task 24: Manual Intraday Trade Verification
  - Open intraday trade
  - Enable intelligent exits
  - Verify INTRADAY classification
  - Verify 30%/60%/50% parameters

Task 25: Verify Discord Notifications
  - Check notification format
  - Verify classification info included
  - Test SCALP trade notification
  - Test INTRADAY trade notification

See docs/MANUAL_TESTING_GUIDE_AIES.md for detailed test procedures.
""")

def main():
    """Run all verification checks"""
    print("\n")
    print("=" * 70)
    print("AIES Phase 1 MVP - System Readiness Verification")
    print("=" * 70)
    print("\nThis script verifies system configuration for manual testing.")
    print("It does NOT execute trades or modify any positions.\n")
    
    results = []
    
    # Run checks
    results.append(("Feature Flag", check_feature_flag()))
    results.append(("Metrics Config", check_metrics_config()))
    results.append(("Discord Config", check_discord_config()))
    results.append(("Module Imports", check_module_imports()))
    results.append(("Config File", check_config_file()))
    results.append(("Desktop Agent Integration", check_desktop_agent_integration()))
    
    # Print summary
    print("\n" + "=" * 70)
    print("Verification Summary")
    print("=" * 70)
    
    critical_ok = True
    for name, result in results:
        status = "OK" if result else "ISSUES"
        if not result and name in ["Feature Flag", "Module Imports", "Desktop Agent Integration"]:
            critical_ok = False
        print(f"{name}: {status}")
    
    print("\n" + "=" * 70)
    if critical_ok:
        print("System Ready for Manual Testing")
        print("=" * 70)
        print("\nAll critical checks passed. You can proceed with manual testing.")
        print("\nNext steps:")
        print("1. Review docs/MANUAL_TESTING_GUIDE_AIES.md")
        print("2. Start with Task 21 (Manual Override tests)")
        print("3. Follow the test procedures in the guide")
    else:
        print("System NOT Ready - Issues Found")
        print("=" * 70)
        print("\nPlease fix the issues above before starting manual testing.")
        return 1
    
    print_test_summary()
    return 0

if __name__ == "__main__":
    sys.exit(main())

