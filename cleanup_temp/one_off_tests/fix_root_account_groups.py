#!/usr/bin/env python3
"""
Fix root accounts that need to be groups
Specifically fixes accounts 80008, 80006, 83291 and any other root accounts
"""

import frappe
from verenigingen.utils.eboekhouden_account_group_fix import (
    check_problem_accounts, 
    fix_account_groups
)


def main():
    """Main function to fix root account groups"""
    frappe.init(site='verenigingen.nl')
    frappe.connect()
    
    print("Checking problematic accounts...")
    print("-" * 60)
    
    # First check the specific problem accounts
    check_result = check_problem_accounts()
    
    if check_result["success"]:
        print("\nProblem Accounts Status:")
        for account in check_result["accounts"]:
            if isinstance(account, dict) and "code" in account:
                print(f"\nAccount Code: {account['code']}")
                if "status" in account:
                    print(f"  Status: {account['status']}")
                else:
                    print(f"  Name: {account['name']}")
                    print(f"  Parent: {account['parent']}")
                    print(f"  Is Group: {account['is_group']}")
                    print(f"  Has GL Entries: {account['has_gl_entries']}")
                    print(f"  Has Children: {account['has_children']}")
                    print(f"  Can Fix: {account['can_fix']}")
    else:
        print(f"Error checking accounts: {check_result['error']}")
        return
    
    print("\n" + "-" * 60)
    response = input("\nDo you want to fix these accounts? (yes/no): ")
    
    if response.lower() == 'yes':
        print("\nFixing account groups...")
        fix_result = fix_account_groups()
        
        if fix_result["success"]:
            print(f"\nSuccess! {fix_result['message']}")
            
            if fix_result["fixed_accounts"]:
                print("\nFixed accounts:")
                for acc in fix_result["fixed_accounts"]:
                    print(f"  - {acc}")
            
            if fix_result["errors"]:
                print("\nErrors encountered:")
                for err in fix_result["errors"]:
                    print(f"  - {err}")
        else:
            print(f"\nError: {fix_result['error']}")
    else:
        print("\nOperation cancelled.")
    
    frappe.db.commit()
    frappe.destroy()


if __name__ == "__main__":
    main()