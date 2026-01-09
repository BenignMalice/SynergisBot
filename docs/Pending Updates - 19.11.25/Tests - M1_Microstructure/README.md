# M1 Microstructure Integration Plan - Test Suite

This directory contains all test files for the M1 Microstructure Integration Plan.

## Test Files

1. **test_m1_data_fetcher.py** - Tests for Phase 1.1: M1 Data Fetcher Module
2. **test_m1_microstructure_analyzer.py** - Tests for Phase 1.2: M1 Microstructure Analyzer
3. **TEST_RESULTS_PHASE_1.1_1.2.md** - Test results documentation

## Running the Tests

### From Project Root

Navigate to the project root directory:
```bash
cd "C:\Coding\MoneyBotv2.7 - 10 Nov 25"
```

### Run Tests Directly (Recommended)

**Phase 1.1 Tests:**
```bash
python "docs\Pending Updates - 19.11.25\Tests - M1_Microstructure\test_m1_data_fetcher.py"
```

**Phase 1.2 Tests:**
```bash
python "docs\Pending Updates - 19.11.25\Tests - M1_Microstructure\test_m1_microstructure_analyzer.py"
```

**Run Both Tests:**
```bash
python "docs\Pending Updates - 19.11.25\Tests - M1_Microstructure\test_m1_data_fetcher.py" && python "docs\Pending Updates - 19.11.25\Tests - M1_Microstructure\test_m1_microstructure_analyzer.py"
```

### Alternative: Using unittest Module

**Phase 1.1:**
```bash
python -m unittest discover -s "docs\Pending Updates - 19.11.25\Tests - M1_Microstructure" -p "test_m1_data_fetcher.py" -v
```

**Phase 1.2:**
```bash
python -m unittest discover -s "docs\Pending Updates - 19.11.25\Tests - M1_Microstructure" -p "test_m1_microstructure_analyzer.py" -v
```

**Run All Tests:**
```bash
python -m unittest discover -s "docs\Pending Updates - 19.11.25\Tests - M1_Microstructure" -p "test_*.py" -v
```

## Test Results

See `TEST_RESULTS_PHASE_1.1_1.2.md` for detailed test results.

**Status:** ✅ All tests passing (37/37)

- Phase 1.1: 17/17 tests passed
- Phase 1.2: 20/20 tests passed

## Notes

- Test files are located in the docs folder to keep them organized with the integration plan
- Import paths are automatically adjusted to find the project root
- Tests use mock data sources and don't require live MT5 connection

