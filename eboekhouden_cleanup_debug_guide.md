# E-Boekhouden Account Cleanup and Debug Guide

## Overview

This guide documents the functions created to check and clean up E-Boekhouden accounts in the system. These functions help identify accounts imported from E-Boekhouden (identified by the `eboekhouden_grootboek_nummer` field) and provide safe cleanup options.

## Available Functions

### 1. `check_eboekhouden_accounts(company=None)`

**Purpose**: Check for E-Boekhouden accounts in the system.

**Location**: `/apps/verenigingen/verenigingen/api/check_eboekhouden_accounts.py`

**Usage**:
```python
# Check all E-Boekhouden accounts
frappe.call('verenigingen.api.check_eboekhouden_accounts.check_eboekhouden_accounts')

# Check for specific company
frappe.call('verenigingen.api.check_eboekhouden_accounts.check_eboekhouden_accounts', {
    company: 'Your Company Name'
})
```

**Returns**:
```json
{
    "success": true,
    "total_accounts": 150,
    "leaf_accounts_count": 120,
    "group_accounts_count": 30,
    "by_account_type": {
        "Bank": 5,
        "Cash": 2,
        "Receivable": 10,
        ...
    },
    "by_root_type": {
        "Asset": 50,
        "Liability": 30,
        ...
    },
    "by_company": {
        "Company A": 100,
        "Company B": 50
    },
    "leaf_accounts": [...],  // First 10 leaf accounts
    "group_accounts": [...],  // First 10 group accounts
    "message": "Found 150 E-Boekhouden accounts in the system"
}
```

### 2. `debug_cleanup_eboekhouden_accounts(company, dry_run=True)`

**Purpose**: Debug and optionally clean up E-Boekhouden accounts with safety checks.

**Location**: `/apps/verenigingen/verenigingen/api/check_eboekhouden_accounts.py`

**Key Features**:
- **Dry Run Mode**: Test what would be deleted without actually deleting
- **GL Entry Check**: Won't delete accounts that have transactions
- **Child Account Check**: Won't delete group accounts that have children
- **Detailed Reporting**: Returns information about what was deleted and what failed

**Usage**:
```python
# Dry run (safe - no deletion)
frappe.call('verenigingen.api.check_eboekhouden_accounts.debug_cleanup_eboekhouden_accounts', {
    company: 'Your Company Name',
    dry_run: true
})

# Actual cleanup (CAUTION: This will delete accounts)
frappe.call('verenigingen.api.check_eboekhouden_accounts.debug_cleanup_eboekhouden_accounts', {
    company: 'Your Company Name',
    dry_run: false
})
```

**Returns (Dry Run)**:
```json
{
    "success": true,
    "total_accounts": 50,
    "leaf_accounts": 40,
    "group_accounts": 10,
    "dry_run": true,
    "message": "DRY RUN: Would delete 50 E-Boekhouden accounts",
    "accounts_to_delete": {
        "leaf_accounts": [...],  // Sample of accounts to be deleted
        "group_accounts": [...]
    }
}
```

**Returns (Actual Cleanup)**:
```json
{
    "success": true,
    "total_accounts": 50,
    "accounts_deleted": 35,
    "deleted_accounts": ["ACC-0001", "ACC-0002", ...],
    "failed_accounts": [
        {"name": "ACC-0010", "reason": "Has GL entries"},
        {"name": "ACC-0020", "reason": "Has child accounts"}
    ],
    "message": "Deleted 35 out of 50 E-Boekhouden accounts"
}
```

### 3. `get_eboekhouden_account_details(account_name)`

**Purpose**: Get detailed information about a specific E-Boekhouden account.

**Location**: `/apps/verenigingen/verenigingen/api/check_eboekhouden_accounts.py`

**Usage**:
```python
frappe.call('verenigingen.api.check_eboekhouden_accounts.get_eboekhouden_account_details', {
    account_name: 'ACC-0001'
})
```

**Returns**:
```json
{
    "success": true,
    "account": {
        "name": "ACC-0001",
        "account_name": "Test Account",
        "eboekhouden_grootboek_nummer": "1000",
        "is_group": false,
        "company": "Your Company",
        "account_type": "Bank",
        ...
    },
    "gl_entries_count": 5,
    "child_accounts_count": 0,
    "recent_gl_entries": [...],
    "can_delete": false  // False if has GL entries or child accounts
}
```

## UI-Friendly Wrapper Functions

### 1. `get_eboekhouden_accounts_summary()`

**Location**: `/apps/verenigingen/verenigingen/api/eboekhouden_account_manager.py`

Simple wrapper for UI to get account summary.

### 2. `cleanup_eboekhouden_accounts_with_confirmation(company, confirmed=False)`

**Location**: `/apps/verenigingen/verenigingen/api/eboekhouden_account_manager.py`

Two-step cleanup with confirmation:
- First call (confirmed=false): Returns dry run results and asks for confirmation
- Second call (confirmed=true): Performs actual cleanup

**Usage**:
```javascript
// First call - get confirmation
frappe.call({
    method: 'verenigingen.api.eboekhouden_account_manager.cleanup_eboekhouden_accounts_with_confirmation',
    args: {
        company: 'Your Company',
        confirmed: false
    },
    callback: function(r) {
        if (r.message.requires_confirmation) {
            // Show confirmation dialog
            if (confirm(r.message.confirmation_message)) {
                // Second call - do cleanup
                frappe.call({
                    method: 'verenigingen.api.eboekhouden_account_manager.cleanup_eboekhouden_accounts_with_confirmation',
                    args: {
                        company: 'Your Company',
                        confirmed: true
                    }
                });
            }
        }
    }
});
```

### 3. `get_account_cleanup_status(company)`

**Location**: `/apps/verenigingen/verenigingen/api/eboekhouden_account_manager.py`

Get cleanup status for a company - useful for dashboards.

## Comparison with Original Cleanup Function

The original `cleanup_chart_of_accounts` function in the E-Boekhouden Migration doctype:
- Deletes all accounts with `eboekhouden_grootboek_nummer` using force=True
- No safety checks for GL entries or child accounts
- No dry run option
- Limited error reporting

The new `debug_cleanup_eboekhouden_accounts` function:
- Checks for GL entries before deleting
- Checks for child accounts before deleting group accounts
- Provides dry run mode for testing
- Detailed reporting of successes and failures
- Better error handling and logging

## Testing

Run tests from bench:
```bash
# Check current E-Boekhouden accounts
bench execute verenigingen.api.check_eboekhouden_accounts.check_eboekhouden_accounts

# Test cleanup comparison
bench execute verenigingen.api.test_cleanup_comparison.compare_cleanup_functions

# Test safety features
bench execute verenigingen.api.test_cleanup_comparison.test_cleanup_safety
```

## Best Practices

1. **Always run dry_run first** before actual cleanup
2. **Check the failed_accounts** list to understand why some accounts couldn't be deleted
3. **Backup your database** before running cleanup operations
4. **Review GL entries** for accounts that can't be deleted
5. **Use the UI wrapper functions** for better user experience with confirmations

## Troubleshooting

### Account won't delete
- Check if it has GL entries: Use `get_eboekhouden_account_details()`
- Check if it's a group with children
- Review the error message in failed_accounts

### Cleanup seems stuck
- Check Error Log for detailed error messages
- Try deleting accounts in smaller batches
- Ensure proper permissions for account deletion

### Need to force delete
- Use the original `cleanup_chart_of_accounts` function with caution
- Or manually delete using `frappe.delete_doc("Account", account_name, force=True)`