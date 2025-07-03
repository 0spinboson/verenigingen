#!/usr/bin/env python3

import frappe
import json

@frappe.whitelist()
def debug_group_055():
    """Debug why group 055 accounts aren't being classified as Income"""
    try:
        # Get settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Get E-Boekhouden data  
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        result = api.get_chart_of_accounts()
        if not result["success"]:
            return f"Error getting CoA: {result['error']}"
        
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        response = []
        response.append("=== GROUP 055 ACCOUNTS ANALYSIS ===")
        response.append(f"Total accounts from API: {len(accounts_data)}")
        
        # Find accounts with group 055
        group_055_accounts = []
        for account in accounts_data:
            group = account.get('group', '')
            if group == '055':
                group_055_accounts.append(account)
        
        response.append(f"Found {len(group_055_accounts)} accounts with group 055:")
        for acc in group_055_accounts:
            response.append(f"  Code: {acc.get('code', 'N/A')}")
            response.append(f"  Description: {acc.get('description', 'N/A')}")
            response.append(f"  Category: {acc.get('category', 'N/A')}")
            response.append(f"  Group: {acc.get('group', 'N/A')}")
            response.append(f"  Balance: {acc.get('balance', 'N/A')}")
            response.append("  ---")
        
        # Also check 8xxx accounts to see their groups
        response.append("\n=== 8XXX ACCOUNTS ANALYSIS ===")
        accounts_8xxx = []
        for account in accounts_data:
            code = account.get('code', '')
            if code.startswith('8'):
                accounts_8xxx.append(account)
        
        response.append(f"Found {len(accounts_8xxx)} accounts starting with 8:")
        for acc in accounts_8xxx[:10]:  # Show first 10
            response.append(f"  Code: {acc.get('code', 'N/A')}")
            response.append(f"  Description: {acc.get('description', 'N/A')}")
            response.append(f"  Category: {acc.get('category', 'N/A')}")
            response.append(f"  Group: {acc.get('group', 'N/A')}")
            response.append("  ---")
        
        # Check current database state
        response.append("\n=== CURRENT DATABASE STATE ===")
        company = settings.default_company
        accounts_in_db = frappe.db.sql("""
            SELECT name, account_name, account_type, root_type, eboekhouden_grootboek_nummer
            FROM `tabAccount`
            WHERE company = %s
            AND eboekhouden_grootboek_nummer LIKE '8%'
            ORDER BY eboekhouden_grootboek_nummer
        """, company, as_dict=True)
        
        response.append(f"Found {len(accounts_in_db)} accounts in database starting with 8:")
        for acc in accounts_in_db[:10]:  # Show first 10
            response.append(f"  Code: {acc.get('eboekhouden_grootboek_nummer', 'N/A')}")
            response.append(f"  Name: {acc.get('account_name', 'N/A')}")
            response.append(f"  Type: {acc.get('account_type', 'N/A')}")
            response.append(f"  Root: {acc.get('root_type', 'N/A')}")
            response.append("  ---")
        
        # Check group mappings
        response.append("\n=== GROUP MAPPINGS ===")
        group_mappings = settings.account_group_mappings
        if group_mappings:
            response.append("Current group mappings:")
            for line in group_mappings.split('\n'):
                if line.strip():
                    response.append(f"  {line.strip()}")
        else:
            response.append("No group mappings configured")
        
        return "\n".join(response)
            
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"