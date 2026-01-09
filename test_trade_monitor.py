"""
Trade Monitor Diagnostic Script
Checks all aspects of the Trade Monitor system
"""

import sys
import logging
from typing import Dict, Any, List, Optional
import threading
import time

# Configure UTF-8 encoding for Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TradeMonitorDiagnostic:
    """Comprehensive Trade Monitor diagnostic"""
    
    def __init__(self):
        self.results = {
            'trailing_stops': {},
            'thread_safety': {},
            'error_handling': {},
            'database_updates': {},
            'universal_integration': {},
            'issues': [],
            'recommendations': []
        }
    
    def run_full_diagnostic(self) -> Dict[str, Any]:
        """Run complete diagnostic"""
        print("\n" + "="*80)
        print("TRADE MONITOR DIAGNOSTIC")
        print("="*80 + "\n")
        
        # 1. Check trailing stops
        print("[1/5] Checking trailing stops functionality...")
        self._check_trailing_stops()
        
        # 2. Check thread safety
        print("\n[2/5] Checking thread safety...")
        self._check_thread_safety()
        
        # 3. Check error handling
        print("\n[3/5] Checking error handling...")
        self._check_error_handling()
        
        # 4. Check database updates
        print("\n[4/5] Checking database updates...")
        self._check_database_updates()
        
        # 5. Check Universal SL/TP Manager integration
        print("\n[5/5] Checking Universal SL/TP Manager integration...")
        self._check_universal_integration()
        
        # Generate summary
        print("\n" + "="*80)
        print("DIAGNOSTIC SUMMARY")
        print("="*80 + "\n")
        self._generate_summary()
        
        return self.results
    
    def _check_trailing_stops(self):
        """Check trailing stops updating correctly"""
        try:
            from infra.trade_monitor import TradeMonitor
            
            # Check if class exists
            print("  [OK] TradeMonitor class exists")
            
            # Check check_trailing_stops method
            if hasattr(TradeMonitor, 'check_trailing_stops'):
                print("  [OK] check_trailing_stops method exists")
                
                # Inspect the method
                import inspect
                source = inspect.getsource(TradeMonitor.check_trailing_stops)
                
                # Check for key functionality
                checks = {
                    'gets_positions': 'get_positions' in source or 'positions_get' in source,
                    'calculates_trailing': 'calculate_trailing_stop' in source,
                    'modifies_position': 'modify_position' in source or 'TRADE_ACTION_SLTP' in source,
                    'rate_limiting': 'min_update_interval' in source or 'last_update' in source,
                    'direction_check': 'direction' in source and ('buy' in source.lower() or 'sell' in source.lower()),
                    'sl_validation': 'current_sl' in source and 'new_sl' in source
                }
                
                for check_name, passed in checks.items():
                    if passed:
                        print(f"  [OK] {check_name.replace('_', ' ').title()}")
                    else:
                        print(f"  [WARN] {check_name.replace('_', ' ').title()} may be missing")
                        self.results['trailing_stops'][check_name] = False
                
                self.results['trailing_stops']['method_exists'] = True
                self.results['trailing_stops']['checks'] = checks
                
            else:
                print("  [FAIL] check_trailing_stops method not found")
                self.results['trailing_stops']['method_exists'] = False
                self.results['issues'].append("check_trailing_stops method not found")
            
            # Check _modify_position_sl method
            if hasattr(TradeMonitor, '_modify_position_sl'):
                print("  [OK] _modify_position_sl method exists")
                self.results['trailing_stops']['modify_method'] = True
            else:
                print("  [FAIL] _modify_position_sl method not found")
                self.results['trailing_stops']['modify_method'] = False
                self.results['issues'].append("_modify_position_sl method not found")
            
        except ImportError as e:
            print(f"  [FAIL] Could not import TradeMonitor: {e}")
            self.results['trailing_stops']['import_error'] = str(e)
            self.results['issues'].append(f"Import error: {e}")
        except Exception as e:
            print(f"  [ERROR] Unexpected error: {e}")
            self.results['trailing_stops']['error'] = str(e)
    
    def _check_thread_safety(self):
        """Check if position monitoring is thread-safe"""
        try:
            from infra.trade_monitor import TradeMonitor
            
            # Check for thread safety mechanisms
            import inspect
            source = inspect.getsource(TradeMonitor.__init__)
            
            # Check for locks
            has_lock = 'Lock' in source or 'lock' in source or 'threading' in source
            if has_lock:
                print("  [OK] Thread synchronization mechanisms found")
                self.results['thread_safety']['has_locks'] = True
            else:
                print("  [WARN] No thread synchronization mechanisms found")
                self.results['thread_safety']['has_locks'] = False
                self.results['issues'].append("No thread synchronization (locks) found")
                self.results['recommendations'].append(
                    "Add threading.Lock() to protect shared data structures (last_update dictionary)"
                )
            
            # Check last_update dictionary access
            source_check = inspect.getsource(TradeMonitor.check_trailing_stops)
            if 'self.last_update' in source_check:
                # Check if it's accessed safely
                if 'lock' in source_check.lower() or 'with' in source_check and 'Lock' in source_check:
                    print("  [OK] last_update dictionary access appears protected")
                    self.results['thread_safety']['last_update_safe'] = True
                else:
                    print("  [WARN] last_update dictionary may be accessed without locks")
                    self.results['thread_safety']['last_update_safe'] = False
                    self.results['issues'].append("last_update dictionary accessed without thread safety")
            
            # Check if positions list iteration is safe
            if 'for position in positions:' in source_check:
                print("  [INFO] Iterates over positions list")
                # Check if list could be modified during iteration
                if 'copy' in source_check or 'list(' in source_check:
                    print("  [OK] Creates copy before iteration (safe)")
                    self.results['thread_safety']['iteration_safe'] = True
                else:
                    print("  [WARN] Iterates directly over positions (could fail if modified)")
                    self.results['thread_safety']['iteration_safe'] = False
                    self.results['issues'].append("Position iteration may not be thread-safe")
            
        except Exception as e:
            print(f"  [ERROR] Error checking thread safety: {e}")
            self.results['thread_safety']['error'] = str(e)
    
    def _check_error_handling(self):
        """Check error handling for closed positions"""
        try:
            from infra.trade_monitor import TradeMonitor
            
            import inspect
            source = inspect.getsource(TradeMonitor.check_trailing_stops)
            
            # Check for try/except blocks
            if 'try:' in source and 'except' in source:
                print("  [OK] Try/except blocks found")
                self.results['error_handling']['has_try_except'] = True
            else:
                print("  [FAIL] No try/except blocks found")
                self.results['error_handling']['has_try_except'] = False
                self.results['issues'].append("No error handling (try/except) found")
            
            # Check for position validation
            checks = {
                'position_exists': 'position' in source and ('if' in source or 'is None' in source),
                'ticket_validation': 'ticket' in source,
                'price_validation': 'current_price' in source and ('if' in source or '== 0' in source),
                'mt5_connection': 'connect()' in source or 'mt5.connect' in source,
                'closed_position_handling': 'closed' in source.lower() or 'not found' in source.lower()
            }
            
            for check_name, passed in checks.items():
                if passed:
                    print(f"  [OK] {check_name.replace('_', ' ').title()} check")
                else:
                    print(f"  [WARN] {check_name.replace('_', ' ').title()} check may be missing")
                    self.results['error_handling'][check_name] = False
            
            self.results['error_handling']['checks'] = checks
            
            # Check for continue on error
            if 'continue' in source:
                print("  [OK] Uses continue to skip failed positions")
                self.results['error_handling']['skips_failures'] = True
            else:
                print("  [WARN] May not skip failed positions (could stop entire check)")
                self.results['error_handling']['skips_failures'] = False
            
        except Exception as e:
            print(f"  [ERROR] Error checking error handling: {e}")
            self.results['error_handling']['error'] = str(e)
    
    def _check_database_updates(self):
        """Check database updates for trade history"""
        try:
            from infra.trade_monitor import TradeMonitor
            
            import inspect
            source_init = inspect.getsource(TradeMonitor.__init__)
            source_check = inspect.getsource(TradeMonitor.check_trailing_stops)
            
            # Check for journal_repo
            if 'journal' in source_init or 'journal_repo' in source_init:
                print("  [OK] Journal repository parameter exists")
                self.results['database_updates']['has_journal'] = True
            else:
                print("  [WARN] No journal repository parameter")
                self.results['database_updates']['has_journal'] = False
            
            # Check if journal is used
            if 'self.journal' in source_check or 'journal.add_event' in source_check:
                print("  [OK] Journal logging implemented")
                self.results['database_updates']['journal_used'] = True
            else:
                print("  [WARN] Journal not used in check_trailing_stops")
                self.results['database_updates']['journal_used'] = False
                self.results['issues'].append("Journal repository not used for logging")
            
            # Check for database persistence
            db_keywords = ['database', 'db', 'sqlite', 'persist', 'save', 'store']
            has_db = any(keyword in source_check.lower() for keyword in db_keywords)
            if has_db:
                print("  [OK] Database persistence found")
                self.results['database_updates']['has_persistence'] = True
            else:
                print("  [INFO] No direct database persistence (uses journal if available)")
                self.results['database_updates']['has_persistence'] = False
            
            # Check for action logging
            if 'actions.append' in source_check:
                print("  [OK] Actions are logged to list")
                self.results['database_updates']['actions_logged'] = True
            else:
                print("  [WARN] Actions may not be logged")
                self.results['database_updates']['actions_logged'] = False
            
        except Exception as e:
            print(f"  [ERROR] Error checking database updates: {e}")
            self.results['database_updates']['error'] = str(e)
    
    def _check_universal_integration(self):
        """Check integration with Universal SL/TP Manager"""
        try:
            from infra.trade_monitor import TradeMonitor
            
            import inspect
            source_init = inspect.getsource(TradeMonitor.__init__)
            source_check = inspect.getsource(TradeMonitor.check_trailing_stops)
            
            # Check for Universal SL/TP Manager imports or references
            universal_keywords = [
                'UniversalDynamicSLTPManager',
                'universal_sl_tp_manager',
                'universal_sl_tp',
                'register_trade',
                'monitor_trade'
            ]
            
            has_universal = any(keyword in source_check or keyword in source_init for keyword in universal_keywords)
            
            if has_universal:
                print("  [OK] Universal SL/TP Manager integration found")
                self.results['universal_integration']['integrated'] = True
            else:
                print("  [WARN] No integration with Universal SL/TP Manager found")
                self.results['universal_integration']['integrated'] = False
                self.results['issues'].append("TradeMonitor not integrated with UniversalDynamicSLTPManager")
                self.results['recommendations'].append(
                    "Consider integrating TradeMonitor with UniversalDynamicSLTPManager to avoid conflicts"
                )
            
            # Check what trailing stop system is used
            if 'calculate_trailing_stop' in source_check:
                print("  [INFO] Uses calculate_trailing_stop from infra.trailing_stops")
                self.results['universal_integration']['uses_legacy'] = True
            else:
                print("  [INFO] Trailing stop calculation method unclear")
            
            # Check for conflicts
            if 'universal' not in source_check.lower() and 'calculate_trailing_stop' in source_check:
                print("  [WARN] May conflict with Universal SL/TP Manager (both manage trailing stops)")
                self.results['universal_integration']['potential_conflict'] = True
                self.results['issues'].append("Potential conflict: TradeMonitor and UniversalDynamicSLTPManager both manage trailing stops")
            
        except Exception as e:
            print(f"  [ERROR] Error checking Universal integration: {e}")
            self.results['universal_integration']['error'] = str(e)
    
    def _generate_summary(self):
        """Generate diagnostic summary"""
        issue_count = len(self.results['issues'])
        
        if issue_count == 0:
            print("[SUCCESS] No critical issues detected!")
        else:
            print(f"[ISSUES FOUND] {issue_count} issue(s) detected:\n")
            for i, issue in enumerate(self.results['issues'], 1):
                print(f"  {i}. {issue}")
        
        if self.results['recommendations']:
            print("\n[RECOMMENDATIONS]\n")
            for i, rec in enumerate(self.results['recommendations'], 1):
                print(f"  {i}. {rec}")
        
        print("\n[KEY FINDINGS]\n")
        
        # Trailing stops
        if self.results['trailing_stops'].get('method_exists'):
            print("  Trailing Stops: [OK] Method exists")
        else:
            print("  Trailing Stops: [FAIL] Method missing")
        
        # Thread safety
        if self.results['thread_safety'].get('has_locks'):
            print("  Thread Safety: [OK] Synchronization mechanisms found")
        else:
            print("  Thread Safety: [WARN] No locks found")
        
        # Error handling
        if self.results['error_handling'].get('has_try_except'):
            print("  Error Handling: [OK] Try/except blocks found")
        else:
            print("  Error Handling: [FAIL] No error handling")
        
        # Database updates
        if self.results['database_updates'].get('journal_used'):
            print("  Database Updates: [OK] Journal logging implemented")
        else:
            print("  Database Updates: [WARN] Journal not used")
        
        # Universal integration
        if self.results['universal_integration'].get('integrated'):
            print("  Universal Integration: [OK] Integrated with Universal SL/TP Manager")
        else:
            print("  Universal Integration: [WARN] Not integrated (potential conflicts)")
        
        print("\n" + "="*80)

def main():
    """Main entry point"""
    diagnostic = TradeMonitorDiagnostic()
    results = diagnostic.run_full_diagnostic()
    return results

if __name__ == "__main__":
    main()

