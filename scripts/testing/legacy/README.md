# Legacy Test Files

This directory contains legacy test files that were moved from the main application directory during test organization.

## Files in this directory

### Debug/Development Test Scripts
- `test_debug_address.py` - Debug script for address members functionality
- `test_address_ui_quick.py` - Quick test for address UI functionality  
- `test_field_population.py` - Test for field population behavior

### Legacy Test Runners
- `run_recent_changes_tests.py` - Old test runner for recent changes

## Status: DEPRECATED

**These files are deprecated and should not be used for new development.**

### Why these files were moved:

1. **One-off nature**: These were temporary debug scripts for specific issues
2. **Hardcoded dependencies**: They reference specific member IDs that may not exist
3. **Not integrated**: They don't follow the organized test infrastructure
4. **Functionality covered**: The features they test are covered by the comprehensive test suite

### Replacement:

Instead of using these legacy files, use the organized test structure:

```bash
# Use the modern test suite
bench --site dev.veganisme.net execute verenigingen.tests.test_runner.run_validation_tests

# Or run specific test categories
bench --site dev.veganisme.net execute verenigingen.tests.test_application_submission_validation.run_application_submission_tests
```

## Future cleanup

These files will be removed in a future cleanup after ensuring all functionality is covered by the organized test suite.

If you need to reference any of these tests for historical purposes, they are preserved here temporarily.