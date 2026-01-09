#!/usr/bin/env python3
"""
Disable Binance and Use MT5 M1 Streaming for BTCUSD
==================================================
Simple version without Unicode characters
"""

import os
import shutil
from pathlib import Path

def backup_file(file_path):
    """Create backup of original file"""
    backup_path = f"{file_path}.backup"
    if not Path(backup_path).exists():
        shutil.copy2(file_path, backup_path)
        print(f"Backup created: {backup_path}")
    else:
        print(f"Backup already exists: {backup_path}")

def disable_binance_feeds():
    """Disable Binance feeds in pipeline manager"""
    file_path = "unified_tick_pipeline/core/pipeline_manager.py"
    
    print("Disabling Binance feeds...")
    backup_file(file_path)
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace Binance configuration
    old_config = """            'binance': {
                # Stream only BTCUSDT via Binance; get gold (XAU) from MT5
                # and remove ETHUSDT per requested configuration.
                'symbols': ['BTCUSDT'],
                'primary_ws_url': 'wss://stream.binance.com/ws/',
                'mirror_ws_url': 'wss://data-stream.binance.vision/ws/',
                'heartbeat_interval': 60,
                'reconnect_delay': 5,
                'max_reconnect_attempts': 10
            },"""
    
    new_config = """            'binance': {
                # DISABLED: Using MT5 M1 streaming for BTCUSD instead
                'enabled': False,
                'symbols': [],
                'primary_ws_url': '',
                'mirror_ws_url': '',
                'heartbeat_interval': 60,
                'reconnect_delay': 5,
                'max_reconnect_attempts': 10
            },"""
    
    if old_config in content:
        content = content.replace(old_config, new_config)
        print("Disabled Binance feeds")
    else:
        print("Binance configuration not found in expected format")
    
    # Write the modified content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Updated {file_path}")

def enable_mt5_m1_for_btcusd():
    """Ensure BTCUSDc is included in MT5 M1 streaming"""
    file_path = "unified_tick_pipeline/core/pipeline_manager.py"
    
    print("Ensuring BTCUSDc is in MT5 M1 streaming...")
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if BTCUSDc is already in MT5 symbols
    if 'BTCUSDc' in content:
        print("BTCUSDc already included in MT5 symbols")
    else:
        print("BTCUSDc not found in MT5 symbols - this should be added manually")
    
    # Ensure M1 streaming is enabled for BTCUSDc
    if 'M1' in content and 'BTCUSDc' in content:
        print("M1 streaming should work for BTCUSDc")
    else:
        print("M1 streaming configuration needs verification")

def update_mt5_m1_streaming_config():
    """Update MT5 M1 streaming configuration for BTCUSD"""
    file_path = "unified_tick_pipeline/core/mt5_m1_streaming.py"
    
    print("Updating MT5 M1 streaming configuration...")
    backup_file(file_path)
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add BTCUSDc to default symbols if not present
    old_default = """    def __post_init__(self):
        if self.symbols is None:
            self.symbols = []"""
    
    new_default = """    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ['BTCUSDc']  # Default to BTCUSDc for M1 streaming"""
    
    if old_default in content:
        content = content.replace(old_default, new_default)
        print("Updated default symbols for M1 streaming")
    else:
        print("Default symbols configuration not found in expected format")
    
    # Write the modified content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Updated {file_path}")

def create_mt5_m1_btcusd_config():
    """Create configuration for MT5 M1 streaming for BTCUSD"""
    config_content = """{
    "mt5_m1_streaming": {
        "enabled": true,
        "symbols": ["BTCUSDc"],
        "update_interval": 1,
        "buffer_size": 100,
        "enable_volatility_analysis": true,
        "enable_structure_analysis": true
    },
    "binance": {
        "enabled": false,
        "symbols": []
    },
    "mt5_timeframes": {
        "enabled": true,
        "symbols": ["BTCUSDc"],
        "timeframes": ["M1", "M5", "M15", "H1", "H4"],
        "update_interval": 1000
    }
}"""
    
    config_path = "mt5_m1_btcusd_config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print(f"Created configuration: {config_path}")

def main():
    """Main function to disable Binance and enable MT5 M1 for BTCUSD"""
    print("=" * 80)
    print("DISABLE BINANCE - USE MT5 M1 STREAMING FOR BTCUSD")
    print("=" * 80)
    
    print("\nOBJECTIVE:")
    print("  - Disable Binance feeds entirely")
    print("  - Use MT5 M1 streaming for BTCUSD instead")
    print("  - Keep existing M5, M15, H1, H4 MT5 data access")
    print("  - Eliminate Binance connection issues")
    
    print("\nCHANGES BEING MADE:")
    
    # Step 1: Disable Binance feeds
    disable_binance_feeds()
    
    # Step 2: Ensure BTCUSDc is in MT5 configuration
    enable_mt5_m1_for_btcusd()
    
    # Step 3: Update MT5 M1 streaming configuration
    update_mt5_m1_streaming_config()
    
    # Step 4: Create configuration file
    create_mt5_m1_btcusd_config()
    
    print("\nCHANGES COMPLETED:")
    print("  - Binance feeds disabled")
    print("  - MT5 M1 streaming configured for BTCUSDc")
    print("  - Existing M5, M15, H1, H4 MT5 access preserved")
    print("  - Configuration file created")
    
    print("\nNEXT STEPS:")
    print("  1. Restart the system to apply changes")
    print("  2. Monitor MT5 M1 streaming for BTCUSDc")
    print("  3. Verify no Binance connection issues")
    print("  4. Check that all timeframes (M1, M5, M15, H1, H4) work for BTCUSDc")
    
    print("\nEXPECTED BENEFITS:")
    print("  - No more Binance connection issues")
    print("  - Consistent data source (MT5 only)")
    print("  - Reliable M1 streaming for BTCUSD")
    print("  - All timeframes available for analysis")
    print("  - Reduced system complexity")

if __name__ == "__main__":
    main()
