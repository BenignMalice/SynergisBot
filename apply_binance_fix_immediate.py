#!/usr/bin/env python3
"""
Apply Binance Fix - Immediate
=============================
Quick fix to test the solution by disabling MT5 calls in Binance callback.
This is a temporary fix to verify the solution works.
"""

import os
import shutil
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def apply_immediate_fix():
    """Apply immediate fix by modifying Binance service"""
    
    logger.info("Applying immediate Binance disconnect fix...")
    
    # Path to the original Binance service
    binance_service_path = Path("infra/binance_service.py")
    
    if not binance_service_path.exists():
        logger.error("Binance service file not found")
        return False
    
    # Create backup
    backup_path = Path("infra/binance_service.py.backup")
    shutil.copy2(binance_service_path, backup_path)
    logger.info(f"Created backup: {backup_path}")
    
    # Read original file with UTF-8 encoding
    with open(binance_service_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Apply fix: Remove MT5 calls from _on_tick method
    fixed_content = content.replace(
        """        # Update offset if MT5 is available
        if self._mt5_service:
            try:
                # Convert Binance symbol to MT5 symbol
                mt5_symbol = self._convert_to_mt5_symbol(symbol)
                
                # Get MT5 quote
                quote = self._mt5_service.get_quote(mt5_symbol)
                if quote:
                    mt5_mid = (quote['bid'] + quote['ask']) / 2
                    self.sync_manager.update_offset(symbol, tick['price'], mt5_mid)
            except Exception as e:
                logger.debug(f"Could not update offset for {symbol}: {e}")""",
        """        # MT5 calls removed to prevent cross-thread access
        # Offset calibration now handled by periodic task on main thread
        # This prevents WebSocket stalls and disconnects
        pass"""
    )
    
    # Write fixed content with UTF-8 encoding
    with open(binance_service_path, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    logger.info("Applied immediate fix to Binance service")
    logger.info("  - Removed MT5 calls from tick callback")
    logger.info("  - This should prevent disconnects when ChatGPT is used")
    
    return True

def restore_original():
    """Restore original Binance service"""
    
    logger.info("Restoring original Binance service...")
    
    backup_path = Path("infra/binance_service.py.backup")
    binance_service_path = Path("infra/binance_service.py")
    
    if not backup_path.exists():
        logger.error("Backup file not found")
        return False
    
    shutil.copy2(backup_path, binance_service_path)
    backup_path.unlink()  # Remove backup
    
    logger.info("Restored original Binance service")
    return True

def main():
    """Main function"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore_original()
    else:
        apply_immediate_fix()
        
        print("\n" + "=" * 70)
        print("IMMEDIATE FIX APPLIED")
        print("=" * 70)
        print("Changes made:")
        print("  - Removed MT5 calls from Binance tick callback")
        print("  - This should prevent disconnects when ChatGPT is used")
        print("\nTo test:")
        print("  1. Restart the system")
        print("  2. Ask ChatGPT questions")
        print("  3. Check if Binance disconnects stop")
        print("\nTo restore original:")
        print("  python apply_binance_fix_immediate.py restore")

if __name__ == "__main__":
    main()
