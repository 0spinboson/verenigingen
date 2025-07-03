#!/usr/bin/env python3

import frappe
import json

def debug_group_055():
    """Debug why group 055 accounts aren't being classified as Income"""
    try:
        frappe.connect()
        
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Get E-Boekhouden data  
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        result = api.get_chart_of_accounts()
        if not result["success"]:
            print(f"Error getting CoA: {result['error']}")
            return
        
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        print("=== GROUP 055 ACCOUNTS ANALYSIS ===")
        print(f"Total accounts from API: {len(accounts_data)}")
        
        # Find accounts with group 055
        group_055_accounts = []
        for account in accounts_data:
            group = account.get('group', '')
            if group == '055':
                group_055_accounts.append(account)
        
        print(f"Found {len(group_055_accounts)} accounts with group 055:")
        for acc in group_055_accounts:
            print(f"  Code: {acc.get('code', 'N/A')}")
            print(f"  Description: {acc.get('description', 'N/A')}")
            print(f"  Category: {acc.get('category', 'N/A')}")
            print(f"  Group: {acc.get('group', 'N/A')}")
            print(f"  Balance: {acc.get('balance', 'N/A')}")
            print("  ---")
        
        # Also check 8xxx accounts to see their groups
        print("\n=== 8XXX ACCOUNTS ANALYSIS ===")
        accounts_8xxx = []
        for account in accounts_data:
            code = account.get('code', '')
            if code.startswith('8'):
                accounts_8xxx.append(account)
        
        print(f"Found {len(accounts_8xxx)} accounts starting with 8:")
        for acc in accounts_8xxx[:10]:  # Show first 10
            print(f"  Code: {acc.get('code', 'N/A')}")
            print(f"  Description: {acc.get('description', 'N/A')}")
            print(f"  Category: {acc.get('category', 'N/A')}")
            print(f"  Group: {acc.get('group', 'N/A')}")
            print("  ---")
        
        # Check current database state
        print("\n=== CURRENT DATABASE STATE ===")
        company = settings.default_company
        accounts_in_db = frappe.db.sql("""
            SELECT name, account_name, account_type, root_type, eboekhouden_grootboek_nummer
            FROM `tabAccount`
            WHERE company = %s
            AND eboekhouden_grootboek_nummer LIKE '8%'
            ORDER BY eboekhouden_grootboek_nummer
        """, company, as_dict=True)
        
        print(f"Found {len(accounts_in_db)} accounts in database starting with 8:")
        for acc in accounts_in_db[:10]:  # Show first 10
            print(f"  Code: {acc.get('eboekhouden_grootboek_nummer', 'N/A')}")
            print(f"  Name: {acc.get('account_name', 'N/A')}")
            print(f"  Type: {acc.get('account_type', 'N/A')}")
            print(f"  Root: {acc.get('root_type', 'N/A')}")
            print("  ---")
        
        # Check group mappings
        print("\n=== GROUP MAPPINGS ===")
        group_mappings = settings.account_group_mappings
        if group_mappings:
            print("Current group mappings:")
            for line in group_mappings.split('\n'):
                if line.strip():
                    print(f"  {line.strip()}")
        else:
            print("No group mappings configured")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_group_055()