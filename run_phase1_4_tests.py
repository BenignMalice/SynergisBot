"""
Test runner for Phase 1.4 detection methods
Explicitly saves results to file for PowerShell compatibility
"""

import sys
import os
import unittest

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import test module
from tests.test_volatility_phase1_4_detection import (
    TestPhase1_4_DetectionMethods,
    TestPhase1_4_Integration
)

def run_tests():
    """Run all Phase 1.4 tests and save results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPhase1_4_DetectionMethods))
    suite.addTests(loader.loadTestsFromTestCase(TestPhase1_4_Integration))
    
    # Run tests with detailed output
    stream = open('test_results_phase1_4.txt', 'w', encoding='utf-8')
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2,
        buffer=True
    )
    
    result = runner.run(suite)
    
    # Write summary
    stream.write("\n" + "="*70 + "\n")
    stream.write("TEST SUMMARY\n")
    stream.write("="*70 + "\n")
    stream.write(f"Tests run: {result.testsRun}\n")
    stream.write(f"Failures: {len(result.failures)}\n")
    stream.write(f"Errors: {len(result.errors)}\n")
    stream.write(f"Success: {result.testsRun - len(result.failures) - len(result.errors)}/{result.testsRun}\n")
    stream.write("="*70 + "\n")
    
    if result.failures:
        stream.write("\nFAILURES:\n")
        for test, traceback in result.failures:
            stream.write(f"\n{test}\n")
            stream.write(traceback)
    
    if result.errors:
        stream.write("\nERRORS:\n")
        for test, traceback in result.errors:
            stream.write(f"\n{test}\n")
            stream.write(traceback)
    
    stream.close()
    
    # Also print to console
    print(f"\nTests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.testsRun - len(result.failures) - len(result.errors)}/{result.testsRun}")
    print("\nResults saved to: test_results_phase1_4.txt")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)


