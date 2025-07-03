import frappe
import json

@frappe.whitelist()
def analyze_rekening_groepen():
    """Analyze E-boekhouden account groups and categories"""
    frappe.set_user("Administrator")
    
    from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenAPI(settings)
    
    # Get accounts to extract unique groups
    print("\n=== Fetching Accounts to Extract Groups ===")
    accounts_result = api.get_chart_of_accounts()
    
    if not accounts_result["success"]:
        print(f"Failed to fetch accounts: {accounts_result['error']}")
        return
    
    accounts_data = json.loads(accounts_result["data"])
    accounts = accounts_data.get("items", [])
    
    print(f"Found {len(accounts)} accounts")
    
    # Extract unique groups from accounts
    groep_map = {}
    for acc in accounts:
        group_code = acc.get("group", "")
        if group_code and group_code not in groep_map:
            # Since we don't have group descriptions from API, use the code as description
            groep_map[group_code] = f"Group {group_code}"
    
    # Show all unique groups
    print("\n=== All Unique Groups from Accounts ===")
    for code in sorted(groep_map.keys()):
        print(f"  {code}")
    
    print(f"\nTotal unique groups: {len(groep_map)}")
    
    # Analyze category to group mapping
    category_group_map = {}
    
    for acc in accounts:
        category = acc.get("category", "")
        group = acc.get("group", "")
        
        if category not in category_group_map:
            category_group_map[category] = set()
        
        if group:
            category_group_map[category].add(group)
    
    print("\n=== Category to Group Mapping ===")
    for category, groups in sorted(category_group_map.items()):
        print(f"\n{category}:")
        for group in sorted(groups):
            print(f"  {group}: {groep_map.get(group, 'Unknown')}")
    
    # Analyze account code patterns per category
    print("\n=== Account Code Patterns per Category ===")
    category_codes = {}
    
    for acc in accounts:
        category = acc.get("category", "")
        code = acc.get("code", "")
        
        if category not in category_codes:
            category_codes[category] = []
        
        category_codes[category].append(code)
    
    for category, codes in sorted(category_codes.items()):
        # Find code ranges
        if codes:
            codes_sorted = sorted(codes)
            min_code = codes_sorted[0]
            max_code = codes_sorted[-1]
            print(f"\n{category}: {len(codes)} accounts")
            print(f"  Range: {min_code} - {max_code}")
            
            # Show first few codes
            print(f"  Examples: {', '.join(codes_sorted[:5])}")
    
    return {
        "groepen": groep_map,
        "categories": list(category_group_map.keys()),
        "category_groups": {k: list(v) for k, v in category_group_map.items()}
    }

@frappe.whitelist()
def create_eboekhouden_hierarchy():
    """Create the proper hierarchy for E-boekhouden accounts"""
    frappe.set_user("Administrator")
    
    company = "Ned Ver Vegan"
    company_abbr = "NVV"
    
    # Map E-boekhouden categories to ERPNext root types
    category_to_root_type = {
        "BAL": None,  # Balance sheet - needs further analysis
        "VW": None,   # Winst en Verlies (P&L) - needs further analysis
        "FIN": "Asset",  # Betalingsmiddelen (Financial/Liquid assets)
        "DEB": "Asset",  # Debiteuren (Debtors)
        "CRED": "Liability",  # Crediteuren (Creditors)
        "BTWRC": "Liability",  # BTW/VAT
        "AF": "Liability",     # VAT payable
        "AF6": "Liability",    # VAT low rate
        "AF19": "Liability",   # VAT high rate
        "AFOVERIG": "Liability",  # VAT other
        "VOOR": "Asset"        # Input VAT
    }
    
    # First create the main root accounts
    root_accounts = [
        {"name": "Activa", "root_type": "Asset"},
        {"name": "Passiva", "root_type": "Liability"},
        {"name": "Eigen Vermogen", "root_type": "Equity"},
        {"name": "Opbrengsten", "root_type": "Income"},
        {"name": "Kosten", "root_type": "Expense"}
    ]
    
    created_roots = {}
    
    print("=== Creating Root Accounts ===")
    
    # ERPNext requires creating all root accounts together in the initial setup
    # We'll use a workaround by creating them as a batch
    
    for root in root_accounts:
        try:
            # Check if exists
            existing = frappe.db.get_value("Account", {
                "company": company,
                "account_name": root["name"],
                "root_type": root["root_type"]
            }, "name")
            
            if existing:
                created_roots[root["root_type"]] = existing
                print(f"Root account exists: {existing}")
            else:
                # We need to create the root accounts using the standard ERPNext method
                # This is a bit complex, so let's use a different approach
                print(f"Root account {root['name']} needs to be created")
                
        except Exception as e:
            print(f"Error checking {root['name']}: {str(e)}")
    
    # Get accounts to extract groups for hierarchy
    from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenAPI(settings)
    
    accounts_result = api.get_chart_of_accounts()
    if not accounts_result["success"]:
        print(f"Failed to fetch accounts: {accounts_result['error']}")
        return
    
    accounts_data = json.loads(accounts_result["data"])
    accounts = accounts_data.get("items", [])
    
    # Extract unique groups
    groepen = {}
    for acc in accounts:
        group_code = acc.get("group", "")
        if group_code and group_code not in groepen:
            groepen[group_code] = {"code": group_code, "description": f"Group {group_code}"}
    
    print(f"\n=== Creating Account Groups from {len(groepen)} Rekening Groepen ===")
    
    # Create groups under appropriate root accounts
    created_groups = {}
    
    for code, groep in groepen.items():
        code = groep.get("code")
        description = groep.get("description", "")
        
        if not code:
            continue
        
        # Determine which root account this group belongs to based on code patterns
        # This is a simplified mapping - you may need to adjust based on your specific setup
        root_type = None
        parent = None
        
        # Map groups to root types based on common Dutch accounting patterns
        if code in ["001", "002", "003", "004"]:  # Asset groups
            root_type = "Asset"
            parent = created_roots.get("Asset")
        elif code in ["005"]:  # Equity groups
            root_type = "Equity"
            parent = created_roots.get("Equity")
        elif code in ["006", "007"]:  # Liability groups
            root_type = "Liability"
            parent = created_roots.get("Liability")
        elif code >= "050":  # Income groups (typically 050+)
            root_type = "Income"
            parent = created_roots.get("Income")
        else:  # Expense groups
            root_type = "Expense"
            parent = created_roots.get("Expense")
        
        if parent:
            try:
                # Check if group exists
                existing = frappe.db.get_value("Account", {
                    "company": company,
                    "account_name": f"{code} - {description}",
                }, "name")
                
                if not existing:
                    # Create the group
                    group_account = frappe.get_doc({
                        "doctype": "Account",
                        "account_name": f"{code} - {description}",
                        "company": company,
                        "parent_account": parent,
                        "root_type": root_type,
                        "is_group": 1,
                        "account_number": code
                    })
                    
                    group_account.insert(ignore_permissions=True)
                    created_groups[code] = group_account.name
                    print(f"Created group: {code} - {description}")
                else:
                    created_groups[code] = existing
                    print(f"Group exists: {code} - {description}")
                    
            except Exception as e:
                print(f"Error creating group {code}: {str(e)}")
    
    frappe.db.commit()
    
    return {
        "root_accounts": created_roots,
        "groups": created_groups
    }