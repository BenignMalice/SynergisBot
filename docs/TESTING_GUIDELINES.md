# Testing Guidelines

## Critical Rules for Testing

1. **NO UNICODE CHARACTERS** - Never use Unicode characters (emojis, special symbols) in test scripts or PowerShell commands as they cause encoding errors on Windows systems.

2. **100% PASS RATE REQUIRED** - Do not claim tests have passed if there are any failures, errors, or warnings. Only proceed with implementation plans when tests achieve 100% pass rate with no issues.

3. **ACCURATE REPORTING** - Always report test results accurately:
   - If tests fail, state they failed
   - If there are warnings, state there are warnings
   - If there are errors, state there are errors
   - Only claim success when ALL tests pass with no issues

4. **NO FALSE POSITIVES** - Do not move forward with implementation unless tests are 100% successful.

## Current Phase 1 Status

**Phase 1 Tests: 75% Pass Rate**
- Unit Tests: PASSED (20/20)
- Integration Tests: PASSED (10/10) 
- Async Tests: PASSED (1/1)
- Performance Tests: FAILED (3/11 failures)

**Issues Found:**
1. Ring buffer memory usage exceeds limit (170MB vs 100MB target)
2. CPU usage exceeds limit under concurrent load (116% vs 80% target)
3. Numba ATR calculation too slow (1840ms vs 100ms target)

**Status: NOT READY FOR PHASE 2** - Performance optimizations required before proceeding.
