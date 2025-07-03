#!/usr/bin/env python
"""
Test script for E-Boekhouden account checking and cleanup functions.
Run this from frappe-bench directory with: bench execute verenigingen.test_eboekhouden_accounts
"""

import frappe
from verenigingen.api.check_eboekhouden_accounts import (
    check_eboekhouden_accounts,
    debug_cleanup_eboekhouden_accounts,
    get_eboekhouden_account_details
)


def test_check_accounts():
    """Test checking E-Boekhouden accounts"""
    print("\n=== Testing check_eboekhouden_accounts ===")
    
    # Check all accounts
    result = check_eboekhouden_accounts()
    print(f"\nAll E-Boekhouden accounts:")
    print(f"Total accounts: {result.get('total_accounts', 0)}")
    print(f"Leaf accounts: {result.get('leaf_accounts_count', 0)}")
    print(f"Group accounts: {result.get('group_accounts_count', 0)}")
    
    if result.get('by_company'):
        print("\nBy Company:")
        for company, count in result['by_company'].items():
            print(f"  {company}: {count}")
    
    if result.get('by_root_type'):
        print("\nBy Root Type:")
        for root_type, count in result['by_root_type'].items():
            print(f"  {root_type}: {count}")
    
    if result.get('by_account_type'):
        print("\nBy Account Type:")
        for account_type, count in result['by_account_type'].items():
            print(f"  {account_type}: {count}")
    
    # Show sample accounts
    if result.get('leaf_accounts'):
        print("\nSample Leaf Accounts:")
        for acc in result['leaf_accounts'][:5]:
            print(f"  - {acc['name']} ({acc['account_name']}) - Grootboek: {acc.get('eboekhouden_grootboek_nummer')}")
    
    return result


def test_cleanup_dry_run(company=None):
    """Test cleanup in dry run mode"""
    print("\n=== Testing debug_cleanup_eboekhouden_accounts (DRY RUN) ===")
    
    if not company:
        # Get first company with E-Boekhouden accounts
        result = check_eboekhouden_accounts()
        if result.get('by_company'):
            company = list(result['by_company'].keys())[0]
        else:
            print("No E-Boekhouden accounts found")
            return
    
    print(f"\nTesting cleanup for company: {company}")
    
    # Dry run
    result = debug_cleanup_eboekhouden_accounts(company, dry_run=True)
    
    print(f"\nDry Run Results:")
    print(f"Total accounts to delete: {result.get('total_accounts', 0)}")
    print(f"Leaf accounts: {result.get('leaf_accounts', 0)}")
    print(f"Group accounts: {result.get('group_accounts', 0)}")
    
    if result.get('accounts_to_delete'):
        if result['accounts_to_delete'].get('leaf_accounts'):
            print("\nSample leaf accounts to delete:")
            for acc in result['accounts_to_delete']['leaf_accounts']:
                print(f"  - {acc['name']} ({acc['account_name']})")
        
        if result['accounts_to_delete'].get('group_accounts'):
            print("\nSample group accounts to delete:")
            for acc in result['accounts_to_delete']['group_accounts']:
                print(f"  - {acc['name']} ({acc['account_name']})")
    
    return result


def test_account_details():
    """Test getting details of a specific E-Boekhouden account"""
    print("\n=== Testing get_eboekhouden_account_details ===")
    
    # Get first E-Boekhouden account
    result = check_eboekhouden_accounts()
    if result.get('leaf_accounts'):
        account_name = result['leaf_accounts'][0]['name']
        
        print(f"\nGetting details for account: {account_name}")
        
        details = get_eboekhouden_account_details(account_name)
        
        if details.get('success'):
            acc = details['account']
            print(f"\nAccount Details:")
            print(f"  Name: {acc['name']}")
            print(f"  Account Name: {acc['account_name']}")
            print(f"  Grootboek Nummer: {acc['eboekhouden_grootboek_nummer']}")
            print(f"  Type: {acc['account_type']}")
            print(f"  Root Type: {acc['root_type']}")
            print(f"  Company: {acc['company']}")
            print(f"  Is Group: {acc['is_group']}")
            print(f"  GL Entries: {details['gl_entries_count']}")
            print(f"  Can Delete: {details['can_delete']}")
            
            if details.get('recent_gl_entries'):
                print("\nRecent GL Entries:")
                for entry in details['recent_gl_entries']:
                    print(f"  - {entry['posting_date']}: {entry['voucher_type']} - Debit: {entry['debit']}, Credit: {entry['credit']}")
        else:
            print(f"Error: {details.get('error')}")
    else:
        print("No E-Boekhouden accounts found")


def main():
    """Main test function"""
    print("Testing E-Boekhouden Account Functions")
    print("=" * 50)
    
    # Test 1: Check accounts
    check_result = test_check_accounts()
    
    # Test 2: Cleanup dry run
    if check_result.get('total_accounts', 0) > 0:
        test_cleanup_dry_run()
    
    # Test 3: Account details
    test_account_details()
    
    print("\n" + "=" * 50)
    print("Testing complete!")


if __name__ == "__main__":
    main()