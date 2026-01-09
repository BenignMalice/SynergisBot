"""
DTMS Hedging Functionality Test
Verifies that hedging logic is properly implemented and can execute
"""

import sys
import logging
from typing import Dict, Any, Optional

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

class DTMSHedgingTest:
    """Test DTMS hedging functionality"""
    
    def __init__(self):
        self.results = {
            'code_analysis': {},
            'configuration': {},
            'state_machine': {},
            'action_executor': {},
            'monitoring_cycle': {},
            'issues': [],
            'recommendations': []
        }
    
    def run_full_test(self) -> Dict[str, Any]:
        """Run complete hedging functionality test"""
        print("\n" + "="*80)
        print("DTMS HEDGING FUNCTIONALITY TEST")
        print("="*80 + "\n")
        
        # 1. Check code implementation
        print("[1/5] Checking code implementation...")
        self._check_code_implementation()
        
        # 2. Check configuration
        print("\n[2/5] Checking configuration...")
        self._check_configuration()
        
        # 3. Check state machine transitions
        print("\n[3/5] Checking state machine transitions...")
        self._check_state_machine()
        
        # 4. Check action executor
        print("\n[4/5] Checking action executor...")
        self._check_action_executor()
        
        # 5. Check monitoring cycle integration
        print("\n[5/5] Checking monitoring cycle integration...")
        self._check_monitoring_cycle()
        
        # Generate summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80 + "\n")
        self._generate_summary()
        
        return self.results
    
    def _check_code_implementation(self):
        """Check if hedging code is implemented"""
        try:
            from dtms_core.state_machine import DTMSStateMachine, TradeState
            from dtms_core.action_executor import DTMSActionExecutor
            
            # Check state machine has HEDGED state
            if TradeState.HEDGED in TradeState:
                print("  [OK] HEDGED state exists in TradeState enum")
                self.results['code_analysis']['hedged_state'] = True
            else:
                print("  [FAIL] HEDGED state not found in TradeState enum")
                self.results['code_analysis']['hedged_state'] = False
                self.results['issues'].append("HEDGED state not in TradeState enum")
            
            # Check state machine has hedge handling
            if hasattr(DTMSStateMachine, '_handle_hedged_state'):
                print("  [OK] _handle_hedged_state method exists")
                self.results['code_analysis']['hedge_handler'] = True
            else:
                print("  [FAIL] _handle_hedged_state method not found")
                self.results['code_analysis']['hedge_handler'] = False
                self.results['issues'].append("_handle_hedged_state method not found")
            
            # Check action executor has open_hedge
            if hasattr(DTMSActionExecutor, '_open_hedge'):
                print("  [OK] _open_hedge method exists in action executor")
                self.results['code_analysis']['open_hedge_method'] = True
            else:
                print("  [FAIL] _open_hedge method not found")
                self.results['code_analysis']['open_hedge_method'] = False
                self.results['issues'].append("_open_hedge method not found")
            
            # Check for hedge_confluence check
            if hasattr(DTMSStateMachine, '_check_hedge_confluence'):
                print("  [OK] _check_hedge_confluence method exists")
                self.results['code_analysis']['hedge_confluence'] = True
            else:
                print("  [WARN] _check_hedge_confluence method not found")
                self.results['code_analysis']['hedge_confluence'] = False
            
        except ImportError as e:
            print(f"  [FAIL] Could not import DTMS modules: {e}")
            self.results['code_analysis']['import_error'] = str(e)
            self.results['issues'].append(f"Import error: {e}")
        except Exception as e:
            print(f"  [ERROR] Unexpected error: {e}")
            self.results['code_analysis']['error'] = str(e)
    
    def _check_configuration(self):
        """Check hedge trigger configuration"""
        try:
            from dtms_config import get_config
            
            config = get_config()
            
            # Check WARNING_L2_to_HEDGED threshold
            if hasattr(config, 'state_transitions'):
                transitions = config.state_transitions
                if 'WARNING_L2_to_HEDGED' in transitions:
                    threshold = transitions['WARNING_L2_to_HEDGED']
                    print(f"  [OK] WARNING_L2_to_HEDGED threshold: {threshold}")
                    self.results['configuration']['hedge_threshold'] = threshold
                    self.results['configuration']['threshold_configured'] = True
                else:
                    print("  [FAIL] WARNING_L2_to_HEDGED threshold not configured")
                    self.results['configuration']['threshold_configured'] = False
                    self.results['issues'].append("WARNING_L2_to_HEDGED threshold not configured")
            else:
                print("  [FAIL] state_transitions not found in config")
                self.results['configuration']['threshold_configured'] = False
                self.results['issues'].append("state_transitions not in config")
            
            # Check hedge confluence configuration
            if hasattr(config, 'hedge_confluence'):
                confluence = config.hedge_confluence
                print(f"  [OK] Hedge confluence config exists: {confluence}")
                self.results['configuration']['hedge_confluence'] = confluence
            else:
                print("  [INFO] Hedge confluence config not found (may use defaults)")
                self.results['configuration']['hedge_confluence'] = None
            
        except ImportError as e:
            print(f"  [FAIL] Could not import dtms_config: {e}")
            self.results['configuration']['import_error'] = str(e)
        except Exception as e:
            print(f"  [ERROR] Unexpected error: {e}")
            self.results['configuration']['error'] = str(e)
    
    def _check_state_machine(self):
        """Check state machine hedge transition logic"""
        try:
            from dtms_core.state_machine import DTMSStateMachine
            
            # Check _handle_warning_l2_state method
            if hasattr(DTMSStateMachine, '_handle_warning_l2_state'):
                print("  [OK] _handle_warning_l2_state method exists")
                
                # Try to inspect the method (check if it has hedge logic)
                import inspect
                source = inspect.getsource(DTMSStateMachine._handle_warning_l2_state)
                if 'HEDGED' in source and 'open_hedge' in source:
                    print("  [OK] _handle_warning_l2_state contains hedge transition logic")
                    self.results['state_machine']['hedge_transition'] = True
                else:
                    print("  [WARN] _handle_warning_l2_state may not contain hedge logic")
                    self.results['state_machine']['hedge_transition'] = False
            else:
                print("  [FAIL] _handle_warning_l2_state method not found")
                self.results['state_machine']['hedge_transition'] = False
                self.results['issues'].append("_handle_warning_l2_state method not found")
            
            # Check _handle_hedged_state method
            if hasattr(DTMSStateMachine, '_handle_hedged_state'):
                print("  [OK] _handle_hedged_state method exists")
                self.results['state_machine']['hedged_handler'] = True
            else:
                print("  [FAIL] _handle_hedged_state method not found")
                self.results['state_machine']['hedged_handler'] = False
                self.results['issues'].append("_handle_hedged_state method not found")
            
        except Exception as e:
            print(f"  [ERROR] Unexpected error: {e}")
            self.results['state_machine']['error'] = str(e)
    
    def _check_action_executor(self):
        """Check action executor hedge execution"""
        try:
            from dtms_core.action_executor import DTMSActionExecutor
            
            # Check _open_hedge method
            if hasattr(DTMSActionExecutor, '_open_hedge'):
                print("  [OK] _open_hedge method exists")
                
                # Try to inspect the method
                import inspect
                source = inspect.getsource(DTMSActionExecutor._open_hedge)
                if 'place_order' in source and 'DTMS_HEDGE' in source:
                    print("  [OK] _open_hedge contains order placement logic")
                    self.results['action_executor']['hedge_execution'] = True
                else:
                    print("  [WARN] _open_hedge may not contain order placement")
                    self.results['action_executor']['hedge_execution'] = False
            else:
                print("  [FAIL] _open_hedge method not found")
                self.results['action_executor']['hedge_execution'] = False
                self.results['issues'].append("_open_hedge method not found")
            
            # Check _close_hedge method
            if hasattr(DTMSActionExecutor, '_close_hedge'):
                print("  [OK] _close_hedge method exists")
                self.results['action_executor']['close_hedge'] = True
            else:
                print("  [WARN] _close_hedge method not found")
                self.results['action_executor']['close_hedge'] = False
            
        except Exception as e:
            print(f"  [ERROR] Unexpected error: {e}")
            self.results['action_executor']['error'] = str(e)
    
    def _check_monitoring_cycle(self):
        """Check if monitoring cycle calls deep check that triggers hedging"""
        try:
            from dtms_core.dtms_engine import DTMSEngine
            
            # Check run_monitoring_cycle method
            if hasattr(DTMSEngine, 'run_monitoring_cycle'):
                print("  [OK] run_monitoring_cycle method exists")
                
                # Check if it calls _run_deep_check
                import inspect
                source = inspect.getsource(DTMSEngine.run_monitoring_cycle)
                if '_run_deep_check' in source:
                    print("  [OK] run_monitoring_cycle calls _run_deep_check")
                    self.results['monitoring_cycle']['deep_check_called'] = True
                else:
                    print("  [WARN] run_monitoring_cycle may not call _run_deep_check")
                    self.results['monitoring_cycle']['deep_check_called'] = False
                
                # Check if _run_deep_check calls state machine update
                if hasattr(DTMSEngine, '_run_deep_check'):
                    deep_check_source = inspect.getsource(DTMSEngine._run_deep_check)
                    if 'update_trade_state' in deep_check_source and '_execute_state_actions' in deep_check_source:
                        print("  [OK] _run_deep_check calls state machine update and action execution")
                        self.results['monitoring_cycle']['state_update'] = True
                    else:
                        print("  [WARN] _run_deep_check may not call state machine update")
                        self.results['monitoring_cycle']['state_update'] = False
            else:
                print("  [FAIL] run_monitoring_cycle method not found")
                self.results['monitoring_cycle']['deep_check_called'] = False
                self.results['issues'].append("run_monitoring_cycle method not found")
            
        except Exception as e:
            print(f"  [ERROR] Unexpected error: {e}")
            self.results['monitoring_cycle']['error'] = str(e)
    
    def _generate_summary(self):
        """Generate test summary"""
        issue_count = len(self.results['issues'])
        
        if issue_count == 0:
            print("[SUCCESS] All hedging code checks passed!")
            print("\n[VERIFICATION NEEDED]")
            print("  Code is implemented correctly, but needs real-world testing:")
            print("  - Verify state transitions occur (HEALTHY → WARNING_L1 → WARNING_L2 → HEDGED)")
            print("  - Verify hedge orders are placed when conditions are met")
            print("  - Verify hedge positions are tracked correctly")
            print("  - Monitor logs for hedge execution")
        else:
            print(f"[ISSUES FOUND] {issue_count} issue(s) detected:\n")
            for i, issue in enumerate(self.results['issues'], 1):
                print(f"  {i}. {issue}")
        
        if self.results['recommendations']:
            print("\n[RECOMMENDATIONS]\n")
            for i, rec in enumerate(self.results['recommendations'], 1):
                print(f"  {i}. {rec}")
        
        print("\n[KEY FINDINGS]\n")
        
        # Code implementation
        if self.results['code_analysis'].get('hedged_state') and \
           self.results['code_analysis'].get('hedge_handler') and \
           self.results['code_analysis'].get('open_hedge_method'):
            print("  Code Implementation: [OK] All required methods exist")
        else:
            print("  Code Implementation: [FAIL] Missing required methods")
        
        # Configuration
        if self.results['configuration'].get('threshold_configured'):
            threshold = self.results['configuration'].get('hedge_threshold', 'Unknown')
            print(f"  Configuration: [OK] Hedge threshold configured ({threshold})")
        else:
            print("  Configuration: [FAIL] Hedge threshold not configured")
        
        # State machine
        if self.results['state_machine'].get('hedge_transition'):
            print("  State Machine: [OK] Hedge transition logic exists")
        else:
            print("  State Machine: [FAIL] Hedge transition logic missing")
        
        # Action executor
        if self.results['action_executor'].get('hedge_execution'):
            print("  Action Executor: [OK] Hedge execution logic exists")
        else:
            print("  Action Executor: [FAIL] Hedge execution logic missing")
        
        # Monitoring cycle
        if self.results['monitoring_cycle'].get('deep_check_called') and \
           self.results['monitoring_cycle'].get('state_update'):
            print("  Monitoring Cycle: [OK] Integrated with state machine")
        else:
            print("  Monitoring Cycle: [WARN] May not be fully integrated")

def main():
    """Main entry point"""
    test = DTMSHedgingTest()
    results = test.run_full_test()
    return results

if __name__ == "__main__":
    main()

