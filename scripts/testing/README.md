# Testing Scripts

Test scripts and test runners organized by type and component.

## Test Runners (`runners/`)

- **`regression_test_runner.py`** - Comprehensive regression test runner
- **`run_erpnext_expense_tests.py`** - ERPNext expense integration test runner
- **`run_volunteer_portal_tests.py`** - Volunteer portal test runner

## Integration Tests (`integration/`)

- **`test_expense_integration_complete.py`** - Complete expense system integration test
- **`test_integration_simple.py`** - Simple integration test
- **`test_sepa_scheduler.py`** - SEPA scheduler integration test

## Unit Tests (`unit/`)

### Board Tests (`unit/board/`)
- **`simple_board_test.py`** - Simple board functionality test
- **`test_board_manual.py`** - Manual board testing
- **`test_board_member_addition.py`** - Board member addition unit test

### Employee Tests (`unit/employee/`)
- **`test_auto_employee_creation.py`** - Automatic employee creation test
- **`test_employee_creation.py`** - Employee creation unit test
- **`test_employee_fix.py`** - Employee-related fixes test

### Volunteer Tests (`unit/volunteer/`)
- **`test_volunteer_creation_fix.py`** - Volunteer creation fix test
- **`test_volunteer_creation_unit.py`** - Volunteer creation unit test
- **`test_volunteer_permissions.py`** - Volunteer permissions test

### Permission Tests (`unit/permissions/`)
- **`test_permission_fix.py`** - Permission system fix test

## Usage

### Run Test Suites
```bash
# Run all regression tests
python scripts/testing/runners/regression_test_runner.py

# Run ERPNext expense tests with options
python scripts/testing/runners/run_erpnext_expense_tests.py --suite all --verbose

# Run volunteer portal tests
python scripts/testing/runners/run_volunteer_portal_tests.py --suite core
```

### Run Individual Tests
```bash
# Run specific integration test
python scripts/testing/integration/test_expense_integration_complete.py

# Run specific unit test
python scripts/testing/unit/board/test_board_member_addition.py
```

## Test Organization

- **Runners** - Execute multiple tests and provide reporting
- **Integration** - Test component interactions and workflows
- **Unit** - Test individual components and functions

Each test category is further organized by component (board, employee, volunteer, permissions) for easy navigation.