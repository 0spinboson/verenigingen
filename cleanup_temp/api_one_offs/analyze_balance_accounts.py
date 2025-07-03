import frappe

@frappe.whitelist()
def analyze_balance_structure():
    """Analyze balance sheet account structure to understand groups and patterns"""
    frappe.set_user("Administrator")
    
    print("=== Analyzing Balance Sheet Account Structure ===\n")
    
    # Get all balance sheet accounts with their groups
    balance_accounts = frappe.db.sql("""
        SELECT 
            a.name, a.account_name, a.eboekhouden_grootboek_nummer as account_code,
            a.root_type, a.is_group,
            p.eboekhouden_grootboek_nummer as parent_group,
            p.account_name as parent_name
        FROM `tabAccount` a
        LEFT JOIN `tabAccount` p ON a.parent_account = p.name
        WHERE a.company = 'Ned Ver Vegan'
        AND a.root_type IN ('Asset', 'Liability', 'Equity')
        AND a.eboekhouden_grootboek_nummer IS NOT NULL
        ORDER BY a.root_type, a.eboekhouden_grootboek_nummer
    """, as_dict=True)
    
    print(f"Found {len(balance_accounts)} balance sheet accounts\n")
    
    # Group by root type and parent group
    by_root_and_group = {}
    
    for acc in balance_accounts:
        root = acc.root_type
        group = acc.parent_group or "No Parent"
        
        if root not in by_root_and_group:
            by_root_and_group[root] = {}
        
        if group not in by_root_and_group[root]:
            by_root_and_group[root][group] = []
        
        by_root_and_group[root][group].append(acc)
    
    # Display analysis
    for root_type in ['Asset', 'Liability', 'Equity']:
        if root_type in by_root_and_group:
            print(f"\n=== {root_type} Accounts ===")
            for group, accounts in sorted(by_root_and_group[root_type].items()):
                print(f"\nGroup {group}:")
                # Show first few accounts in each group
                for i, acc in enumerate(accounts[:5]):
                    if not acc.is_group:  # Only show leaf accounts
                        print(f"  {acc.account_code}: {acc.account_name}")
                if len(accounts) > 5:
                    print(f"  ... and {len(accounts) - 5} more")
    
    # Analyze specific patterns
    print("\n\n=== Pattern Analysis ===")
    
    # Check for common patterns
    patterns = {
        "Bank accounts": [],
        "Cash accounts": [],
        "Receivables": [],
        "Payables": [],
        "Fixed Assets": [],
        "Inventory": [],
        "Tax accounts": []
    }
    
    for acc in balance_accounts:
        if acc.is_group:
            continue
            
        name_lower = acc.account_name.lower()
        code = acc.account_code
        
        # Check patterns
        if 'bank' in name_lower or 'abn' in name_lower or 'triodos' in name_lower:
            patterns["Bank accounts"].append(f"{code}: {acc.account_name}")
        elif 'kas' in name_lower and 'bank' not in name_lower:
            patterns["Cash accounts"].append(f"{code}: {acc.account_name}")
        elif 'debiteur' in name_lower or (code.startswith('13') and acc.root_type == 'Asset'):
            patterns["Receivables"].append(f"{code}: {acc.account_name}")
        elif 'crediteur' in name_lower or (code.startswith('16') and acc.root_type == 'Liability'):
            patterns["Payables"].append(f"{code}: {acc.account_name}")
        elif 'btw' in name_lower or 'vat' in name_lower:
            patterns["Tax accounts"].append(f"{code}: {acc.account_name}")
        elif code.startswith('0') or 'vaste activa' in name_lower or 'inventaris' in name_lower:
            patterns["Fixed Assets"].append(f"{code}: {acc.account_name}")
        elif 'voorraad' in name_lower:
            patterns["Inventory"].append(f"{code}: {acc.account_name}")
    
    # Display patterns found
    for pattern_name, accounts in patterns.items():
        if accounts:
            print(f"\n{pattern_name}:")
            for acc in accounts[:5]:
                print(f"  {acc}")
            if len(accounts) > 5:
                print(f"  ... and {len(accounts) - 5} more")
    
    return {"success": True}