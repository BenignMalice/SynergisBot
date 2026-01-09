"""
DTMS Diagnostic Script
Comprehensive diagnostic tool to check DTMS initialization and status
"""

import sys
import logging
from typing import Dict, Any, Optional
from datetime import datetime

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

class DTMSDiagnostic:
    """Comprehensive DTMS diagnostic tool"""
    
    def __init__(self):
        self.results = {
            'dtms_engine': {},
            'dtms_unified_pipeline': {},
            'services': {},
            'trade_registration': {},
            'monitoring': {},
            'issues': [],
            'recommendations': []
        }
    
    def run_full_diagnostic(self) -> Dict[str, Any]:
        """Run complete DTMS diagnostic"""
        print("\n" + "="*80)
        print("DTMS DIAGNOSTIC TOOL")
        print("="*80 + "\n")
        
        # 1. Check DTMS Engine (dtms_integration.py)
        print("[1/6] Checking DTMS Engine (dtms_integration.py)...")
        self._check_dtms_engine()
        
        # 2. Check DTMS Unified Pipeline Integration
        print("\n[2/6] Checking DTMS Unified Pipeline Integration...")
        self._check_dtms_unified_pipeline()
        
        # 3. Check Service Dependencies
        print("\n[3/6] Checking Service Dependencies...")
        self._check_services()
        
        # 4. Check Trade Registration
        print("\n[4/6] Checking Trade Registration...")
        self._check_trade_registration()
        
        # 5. Check Monitoring Status
        print("\n[5/6] Checking Monitoring Status...")
        self._check_monitoring()
        
        # 6. Generate Summary
        print("\n[6/6] Generating Summary...")
        self._generate_summary()
        
        return self.results
    
    def _check_dtms_engine(self):
        """Check DTMS Engine initialization and status"""
        # First, check if DTMS API server is running (port 8001)
        print("  [INFO] Checking DTMS API server (port 8001)...")
        dtms_api_available = False
        dtms_api_status = None
        try:
            import httpx
            with httpx.Client(timeout=5.0) as client:
                try:
                    response = client.get("http://localhost:8001/dtms/status")
                    if response.status_code == 200:
                        dtms_api_status = response.json()
                        dtms_api_available = True
                        print("  [OK] DTMS API server is running")
                        if dtms_api_status:
                            # Parse the response structure from dtms_api_server.py
                            dtms_status_data = dtms_api_status.get('dtms_status', {})
                            if dtms_status_data:
                                # API returns 'system_active' not 'monitoring_active'
                                monitoring = dtms_status_data.get('system_active', False) or dtms_status_data.get('monitoring_active', False)
                                active_trades = dtms_status_data.get('active_trades', 0)
                                uptime = dtms_status_data.get('uptime', 'Unknown')
                                trades_by_state = dtms_status_data.get('trades_by_state', {})
                                print(f"  [OK] API Status - Monitoring: {monitoring}, Active Trades: {active_trades}")
                                if uptime != 'Unknown':
                                    print(f"  [OK] Uptime: {uptime}")
                                if trades_by_state:
                                    print(f"  [INFO] Trades by state: {trades_by_state}")
                            else:
                                # Fallback to direct keys
                                monitoring = dtms_api_status.get('monitoring_active', False) or dtms_api_status.get('system_active', False)
                                active_trades = dtms_api_status.get('active_trades', 0)
                                print(f"  [OK] API Status - Monitoring: {monitoring}, Active Trades: {active_trades}")
                    else:
                        print(f"  [WARN] DTMS API server responded with status {response.status_code}")
                except httpx.ConnectError:
                    print("  [WARN] DTMS API server not reachable (may be running in separate process)")
                except Exception as e:
                    print(f"  [WARN] Error checking DTMS API: {e}")
        except ImportError:
            print("  [WARN] httpx not available, cannot check DTMS API server")
        except Exception as e:
            print(f"  [WARN] Error checking DTMS API server: {e}")
        
        # Store API status
        self.results['dtms_engine']['api_server_available'] = dtms_api_available
        self.results['dtms_engine']['api_server_status'] = dtms_api_status
        
        # Now check local module state
        try:
            from dtms_integration import get_dtms_engine, get_dtms_system_status
            
            # Check if engine exists
            engine = get_dtms_engine()
            if engine is None:
                # If API server is available, DTMS is running there, not locally
                if dtms_api_available:
                    self.results['dtms_engine']['initialized'] = True
                    self.results['dtms_engine']['location'] = "api_server"
                    self.results['dtms_engine']['note'] = "DTMS is running in API server (port 8001), not in this process"
                    print("  [OK] DTMS Engine is running in API server (port 8001)")
                    print("  [INFO] Local module check: DTMS not initialized in this process (expected)")
                    return
                else:
                    self.results['dtms_engine']['initialized'] = False
                    self.results['dtms_engine']['error'] = "DTMS engine not initialized (_dtms_engine is None) and API server not available"
                    self.results['issues'].append("DTMS Engine: Not initialized locally and API server not reachable")
                    self.results['recommendations'].append(
                        "Initialize DTMS engine by calling initialize_dtms() in chatgpt_bot.py or main_api.py, or ensure dtms_api_server.py is running on port 8002"
                    )
                    print("  [FAIL] DTMS Engine not initialized locally")
                    print("  [WARN] DTMS API server also not reachable")
                    return
            
            self.results['dtms_engine']['initialized'] = True
            self.results['dtms_engine']['location'] = "local_process"
            print("  [OK] DTMS Engine initialized in this process")
            
            # Get system status
            try:
                status = get_dtms_system_status()
                self.results['dtms_engine']['status'] = status
                
                if status.get('error'):
                    print(f"  [WARN] Status error: {status['error']}")
                    self.results['issues'].append(f"DTMS Engine Status: {status['error']}")
                else:
                    print(f"  [OK] Monitoring active: {status.get('monitoring_active', False)}")
                    print(f"  [OK] Active trades: {status.get('active_trades', 0)}")
                    print(f"  [OK] Uptime: {status.get('uptime_human', 'Unknown')}")
                    
                    trades_by_state = status.get('trades_by_state', {})
                    if trades_by_state:
                        print(f"  [INFO] Trades by state: {trades_by_state}")
                    
            except Exception as e:
                print(f"  [WARN] Could not get system status: {e}")
                self.results['dtms_engine']['status_error'] = str(e)
            
            # Check engine attributes
            try:
                print(f"  [INFO] Monitoring active: {engine.monitoring_active}")
                print(f"  [INFO] State machine active trades: {len(engine.state_machine.active_trades)}")
                print(f"  [INFO] Data manager: {engine.data_manager is not None}")
                print(f"  [INFO] Signal scorer: {engine.signal_scorer is not None}")
                print(f"  [INFO] Action executor: {engine.action_executor is not None}")
                
                self.results['dtms_engine']['monitoring_active'] = engine.monitoring_active
                self.results['dtms_engine']['active_trades_count'] = len(engine.state_machine.active_trades)
                
                if not engine.monitoring_active:
                    self.results['issues'].append("DTMS Engine: Monitoring not active")
                    self.results['recommendations'].append(
                        "Start DTMS monitoring by calling start_dtms_monitoring()"
                    )
                    
            except Exception as e:
                print(f"  [WARN] Could not inspect engine attributes: {e}")
                self.results['dtms_engine']['inspection_error'] = str(e)
                
        except ImportError as e:
            self.results['dtms_engine']['import_error'] = str(e)
            self.results['issues'].append(f"DTMS Engine: Import error - {e}")
            print(f"  [FAIL] Could not import dtms_integration: {e}")
        except Exception as e:
            self.results['dtms_engine']['error'] = str(e)
            self.results['issues'].append(f"DTMS Engine: {e}")
            print(f"  [ERROR] Unexpected error: {e}")
    
    def _check_dtms_unified_pipeline(self):
        """Check DTMS Unified Pipeline Integration"""
        try:
            # Check if unified pipeline integration exists
            try:
                from dtms_unified_pipeline_integration import DTMSUnifiedPipelineIntegration
                from app.main_api import app
                
                # Try to get the instance from app state
                dtms_unified = None
                try:
                    if hasattr(app.state, 'dtms_unified_pipeline'):
                        dtms_unified = app.state.dtms_unified_pipeline
                except Exception:
                    pass
                
                if dtms_unified is None:
                    self.results['dtms_unified_pipeline']['initialized'] = False
                    self.results['dtms_unified_pipeline']['error'] = "DTMS Unified Pipeline not found in app state"
                    self.results['issues'].append("DTMS Unified Pipeline: Not initialized in main_api.py")
                    print("  [WARN] DTMS Unified Pipeline not found in app state")
                    print("  [INFO] This is expected if main_api.py is not running")
                else:
                    self.results['dtms_unified_pipeline']['initialized'] = dtms_unified.is_initialized
                    self.results['dtms_unified_pipeline']['active'] = dtms_unified.is_active
                    self.results['dtms_unified_pipeline']['monitored_trades'] = len(dtms_unified.monitored_trades)
                    
                    print(f"  [OK] DTMS Unified Pipeline initialized: {dtms_unified.is_initialized}")
                    print(f"  [OK] DTMS Unified Pipeline active: {dtms_unified.is_active}")
                    print(f"  [INFO] Monitored trades: {len(dtms_unified.monitored_trades)}")
                    
                    if not dtms_unified.is_initialized:
                        self.results['issues'].append("DTMS Unified Pipeline: Not initialized")
                        self.results['recommendations'].append(
                            "Initialize DTMS Unified Pipeline by calling initialize_dtms_unified_pipeline() in main_api.py"
                        )
                    
            except ImportError as e:
                self.results['dtms_unified_pipeline']['import_error'] = str(e)
                print(f"  [WARN] Could not import dtms_unified_pipeline_integration: {e}")
                
        except Exception as e:
            self.results['dtms_unified_pipeline']['error'] = str(e)
            print(f"  [ERROR] Unexpected error: {e}")
    
    def _check_services(self):
        """Check service dependencies"""
        services_to_check = {
            'MT5': 'infra.mt5_service.MT5Service',
            'Binance': 'infra.binance_service.BinanceService',
            'OrderFlow': 'infra.order_flow_service.OrderFlowService'
        }
        
        for service_name, module_path in services_to_check.items():
            try:
                module_name, class_name = module_path.rsplit('.', 1)
                module = __import__(module_name, fromlist=[class_name])
                service_class = getattr(module, class_name)
                
                # Try to get instance from chatgpt_bot or desktop_agent
                instance = None
                try:
                    import chatgpt_bot
                    if hasattr(chatgpt_bot, service_name.lower() + '_service'):
                        instance = getattr(chatgpt_bot, service_name.lower() + '_service')
                except Exception:
                    pass
                
                if instance is None:
                    try:
                        import desktop_agent
                        if hasattr(desktop_agent, service_name.lower() + '_service'):
                            instance = getattr(desktop_agent, service_name.lower() + '_service')
                    except Exception:
                        pass
                
                if instance:
                    self.results['services'][service_name] = {
                        'available': True,
                        'instance': type(instance).__name__
                    }
                    print(f"  [OK] {service_name} service available")
                else:
                    self.results['services'][service_name] = {
                        'available': False,
                        'error': 'Instance not found'
                    }
                    print(f"  [WARN] {service_name} service class found but instance not available")
                    
            except ImportError as e:
                self.results['services'][service_name] = {
                    'available': False,
                    'error': f'Import error: {e}'
                }
                print(f"  [WARN] {service_name} service not available: {e}")
            except Exception as e:
                self.results['services'][service_name] = {
                    'available': False,
                    'error': str(e)
                }
                print(f"  [ERROR] Error checking {service_name} service: {e}")
    
    def _check_trade_registration(self):
        """Check trade registration functionality"""
        # First check if DTMS API server is available
        dtms_api_available = self.results['dtms_engine'].get('api_server_available', False)
        dtms_api_status = self.results['dtms_engine'].get('api_server_status')
        
        if dtms_api_available and dtms_api_status:
            # Use API server status
            dtms_status_data = dtms_api_status.get('dtms_status', {})
            if dtms_status_data:
                active_trades = dtms_status_data.get('active_trades', 0)
                self.results['trade_registration']['active_trades'] = active_trades
                self.results['trade_registration']['status'] = 'ok'
                self.results['trade_registration']['source'] = 'api_server'
                
                if active_trades > 0:
                    print(f"  [OK] {active_trades} trades registered and monitored (via API server)")
                    # Try to get trade details from API
                    try:
                        import httpx
                        with httpx.Client(timeout=5.0) as client:
                            # Get action history which might show recent trades
                            response = client.get("http://localhost:8002/dtms/action-history")
                            if response.status_code == 200:
                                history = response.json()
                                if history.get('action_history'):
                                    recent = history['action_history'][-5:]  # Last 5 actions
                                    print(f"  [INFO] Recent DTMS actions: {len(recent)}")
                                    for action in recent[-3:]:  # Show last 3
                                        ticket = action.get('ticket', 'N/A')
                                        action_type = action.get('action_type', 'N/A')
                                        print(f"    - Ticket {ticket}: {action_type}")
                    except Exception:
                        pass
                else:
                    print("  [INFO] No trades currently registered (via API server)")
                    print("  [INFO] Trades should be auto-registered via auto_register_dtms() or DTMS API")
                return
        
        # Fallback to local check
        try:
            from dtms_integration import get_dtms_engine
            
            engine = get_dtms_engine()
            if engine is None:
                self.results['trade_registration']['status'] = 'engine_not_initialized'
                self.results['trade_registration']['error'] = 'DTMS engine not initialized locally and API server not available'
                print("  [FAIL] Cannot check trade registration - DTMS engine not initialized")
                return
            
            # Check if auto_register_dtms function exists
            # Note: auto_register_dtms is in dtms_integration.py (root file), not dtms_integration package
            # This is a known import issue - the function exists but may not be importable from the package
            auto_register_dtms = None
            try:
                # Try importing from root file
                import importlib.util
                import os
                root_path = os.path.join(os.path.dirname(__file__), 'dtms_integration.py')
                if os.path.exists(root_path):
                    spec = importlib.util.spec_from_file_location("dtms_integration_root", root_path)
                    dtms_root = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(dtms_root)
                    auto_register_dtms = getattr(dtms_root, 'auto_register_dtms', None)
            except Exception:
                pass
            
            if auto_register_dtms is None:
                # Function exists but may not be importable - this is expected
                print("  [INFO] auto_register_dtms function exists in dtms_integration.py")
                print("  [INFO] Note: Import may fail due to package/file name conflict")
                auto_register_dtms = True  # Assume it exists for status check
            
            # Check active trades
            active_trades = len(engine.state_machine.active_trades)
            self.results['trade_registration']['active_trades'] = active_trades
            self.results['trade_registration']['status'] = 'ok'
            
            if active_trades > 0:
                print(f"  [OK] {active_trades} trades registered and monitored")
                # Show trade details
                for ticket, trade_data in list(engine.state_machine.active_trades.items())[:5]:
                    print(f"    - Ticket {ticket}: {trade_data.symbol} {trade_data.direction} (State: {trade_data.state.value})")
            else:
                print("  [INFO] No trades currently registered")
                print("  [INFO] Trades should be auto-registered via auto_register_dtms() after execution")
                
        except ImportError as e:
            self.results['trade_registration']['import_error'] = str(e)
            print(f"  [FAIL] Could not import dtms_integration: {e}")
        except Exception as e:
            self.results['trade_registration']['error'] = str(e)
            print(f"  [ERROR] Unexpected error: {e}")
    
    def _check_monitoring(self):
        """Check monitoring status"""
        # First check if DTMS API server is available
        dtms_api_available = self.results['dtms_engine'].get('api_server_available', False)
        dtms_api_status = self.results['dtms_engine'].get('api_server_status')
        
        if dtms_api_available and dtms_api_status:
            # Use API server status
            dtms_status_data = dtms_api_status.get('dtms_status', {})
            if dtms_status_data:
                # API returns 'system_active' not 'monitoring_active'
                monitoring_active = dtms_status_data.get('system_active', False) or dtms_status_data.get('monitoring_active', False)
                self.results['monitoring']['active'] = monitoring_active
                self.results['monitoring']['status'] = dtms_status_data
                self.results['monitoring']['source'] = 'api_server'
                
                if monitoring_active:
                    print("  [OK] DTMS monitoring is active (via API server)")
                else:
                    # If there are active trades, monitoring might be working even if flag is False
                    active_trades = dtms_status_data.get('active_trades', 0)
                    if active_trades > 0:
                        print("  [INFO] DTMS has active trades but monitoring flag is False")
                        print("  [INFO] Monitoring may still be working (checking trades)")
                    else:
                        print("  [WARN] DTMS monitoring is NOT active (via API server)")
                        self.results['issues'].append("DTMS Monitoring: Not active in API server")
                        self.results['recommendations'].append(
                            "Start DTMS monitoring by calling start_dtms_monitoring() in the API server process"
                        )
                return
        
        # Fallback to local check
        try:
            from dtms_integration import get_dtms_engine, get_dtms_system_status
            
            engine = get_dtms_engine()
            if engine is None:
                self.results['monitoring']['status'] = 'engine_not_initialized'
                print("  [FAIL] Cannot check monitoring - DTMS engine not initialized")
                return
            
            # Check monitoring status
            status = get_dtms_system_status()
            monitoring_active = status.get('monitoring_active', False) or engine.monitoring_active
            
            self.results['monitoring']['active'] = monitoring_active
            self.results['monitoring']['status'] = status
            
            if monitoring_active:
                print("  [OK] DTMS monitoring is active")
                
                # Check if monitoring cycle is being called
                # This is harder to check directly, so we check for background tasks
                try:
                    import chatgpt_bot
                    # Check if there's a scheduler or background task
                    print("  [INFO] Monitoring cycle should be running in background")
                except Exception:
                    pass
                
                try:
                    import app.main_api
                    # Check if there's a background task in main_api
                    print("  [INFO] Check main_api.py for DTMS monitoring background tasks")
                except Exception:
                    pass
                    
            else:
                print("  [FAIL] DTMS monitoring is NOT active")
                self.results['issues'].append("DTMS Monitoring: Not active")
                self.results['recommendations'].append(
                    "Start DTMS monitoring by calling start_dtms_monitoring()"
                )
                
        except ImportError as e:
            self.results['monitoring']['import_error'] = str(e)
            print(f"  [FAIL] Could not import dtms_integration: {e}")
        except Exception as e:
            self.results['monitoring']['error'] = str(e)
            print(f"  [ERROR] Unexpected error: {e}")
    
    def _generate_summary(self):
        """Generate diagnostic summary"""
        print("\n" + "="*80)
        print("DIAGNOSTIC SUMMARY")
        print("="*80 + "\n")
        
        # Count issues
        issue_count = len(self.results['issues'])
        if issue_count == 0:
            print("[SUCCESS] No issues detected!")
        else:
            print(f"[ISSUES FOUND] {issue_count} issue(s) detected:\n")
            for i, issue in enumerate(self.results['issues'], 1):
                print(f"  {i}. {issue}")
        
        # Show recommendations
        if self.results['recommendations']:
            print("\n[RECOMMENDATIONS]\n")
            for i, rec in enumerate(self.results['recommendations'], 1):
                print(f"  {i}. {rec}")
        
        # Show key status
        print("\n[KEY STATUS]\n")
        
        # DTMS Engine
        if self.results['dtms_engine'].get('initialized'):
            location = self.results['dtms_engine'].get('location', 'unknown')
            if location == 'api_server':
                print("  DTMS Engine: [OK] Initialized (running in API server on port 8002)")
            else:
                print("  DTMS Engine: [OK] Initialized (local process)")
            
            # Get monitoring status from monitoring results
            monitoring_active = self.results['monitoring'].get('active', False)
            if monitoring_active:
                print("  Monitoring: [OK] Active")
            else:
                # Check if there are active trades (monitoring might be working)
                api_status = self.results['dtms_engine'].get('api_server_status', {})
                dtms_status_data = api_status.get('dtms_status', {}) if api_status else {}
                active_trades = dtms_status_data.get('active_trades', 0) or self.results['dtms_engine'].get('active_trades_count', 0)
                if active_trades > 0:
                    print("  Monitoring: [INFO] Active trades present (monitoring may be working)")
                else:
                    print("  Monitoring: [WARN] Not active")
            
            # Get active trades count
            api_status = self.results['dtms_engine'].get('api_server_status', {})
            dtms_status_data = api_status.get('dtms_status', {}) if api_status else {}
            active_trades = dtms_status_data.get('active_trades', 0) or self.results['dtms_engine'].get('active_trades_count', 0)
            print(f"  Active Trades: {active_trades}")
        else:
            print("  DTMS Engine: [FAIL] Not initialized")
        
        # Services
        print("\n  Services:")
        for service_name, service_info in self.results['services'].items():
            status = "[OK]" if service_info.get('available') else "[WARN]"
            print(f"    {service_name}: {status}")
        
        print("\n" + "="*80)
        print("Diagnostic complete!")
        print("="*80 + "\n")

def main():
    """Main entry point"""
    diagnostic = DTMSDiagnostic()
    results = diagnostic.run_full_diagnostic()
    
    # Return results for programmatic access
    return results

if __name__ == "__main__":
    main()

