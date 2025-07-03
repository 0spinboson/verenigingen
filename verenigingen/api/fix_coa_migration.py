import frappe
import json

@frappe.whitelist()
def create_proper_coa_hierarchy():
    """Create the proper CoA hierarchy for E-boekhouden migration"""
    frappe.set_user("Administrator")
    
    company = "Ned Ver Vegan"
    company_abbr = "NVV"
    
    print("=== Creating E-boekhouden CoA Hierarchy ===")
    
    # First, we need to create the root accounts
    # E-boekhouden categories map to ERPNext root types as follows:
    root_mapping = {
        "Asset": {
            "name": "Activa",
            "categories": ["BAL", "FIN", "DEB", "VOOR"],  # Balance sheet assets, financial assets, debtors, input VAT
            "groups": ["001", "002", "003", "004"]  # Groups that typically contain assets
        },
        "Liability": {
            "name": "Passiva", 
            "categories": ["BAL", "CRED", "BTWRC", "AF", "AF6", "AF19", "AFOVERIG"],  # Balance sheet liabilities, creditors, VAT
            "groups": ["006"]  # Groups that typically contain liabilities
        },
        "Equity": {
            "name": "Eigen Vermogen",
            "categories": ["BAL"],  # Balance sheet equity items
            "groups": ["005"]  # Equity groups
        },
        "Income": {
            "name": "Opbrengsten",
            "categories": ["VW"],  # P&L income items
            "groups": ["050", "051", "052", "053", "054", "055"]  # Income groups (typically 050+)
        },
        "Expense": {
            "name": "Kosten",
            "categories": ["VW"],  # P&L expense items
            "groups": ["007", "009", "014", "016", "017", "022", "023", "024", "025", "027", "028", "029", "031", "033", "034", "035", "040"]  # Expense groups
        }
    }
    
    # Step 1: Create root accounts using the ERPNext standard method
    # We need to create a minimal CoA structure first
    from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import create_account
    
    created_roots = {}
    
    for root_type, config in root_mapping.items():
        try:
            # Check if root account exists
            existing = frappe.db.get_value("Account", {
                "company": company,
                "root_type": root_type,
                "parent_account": ["is", "not set"],
                "is_group": 1
            }, "name")
            
            if existing:
                created_roots[root_type] = existing
                print(f"Root account exists: {existing}")
            else:
                # Create root account
                account = create_account(
                    account_name=config["name"],
                    account_number=None,
                    parent_account=None,
                    company=company,
                    root_type=root_type
                )
                created_roots[root_type] = account
                print(f"Created root account: {account}")
                
        except Exception as e:
            print(f"Error with root {config['name']}: {str(e)}")
            # Try alternative approach
            try:
                account = frappe.new_doc("Account")
                account.account_name = config["name"]
                account.company = company
                account.root_type = root_type
                account.is_group = 1
                account.flags.ignore_mandatory = True
                account.save(ignore_permissions=True)
                created_roots[root_type] = account.name
                print(f"Created root account (alternative): {account.name}")
            except Exception as e2:
                print(f"Alternative also failed: {str(e2)}")
    
    frappe.db.commit()
    
    # Step 2: Get all accounts from E-boekhouden to extract groups
    from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenAPI(settings)
    
    accounts_result = api.get_chart_of_accounts()
    if not accounts_result["success"]:
        print(f"Failed to fetch accounts: {accounts_result['error']}")
        return
    
    accounts_data = json.loads(accounts_result["data"])
    accounts = accounts_data.get("items", [])
    
    # Extract groups and analyze their categories
    group_info = {}
    for acc in accounts:
        group_code = acc.get("group", "")
        category = acc.get("category", "")
        
        if group_code:
            if group_code not in group_info:
                group_info[group_code] = {
                    "categories": set(),
                    "account_codes": [],
                    "min_code": None,
                    "max_code": None
                }
            
            group_info[group_code]["categories"].add(category)
            group_info[group_code]["account_codes"].append(acc.get("code", ""))
    
    # Determine root type for each group based on categories and account codes
    group_root_types = {}
    
    for group_code, info in group_info.items():
        categories = info["categories"]
        account_codes = [c for c in info["account_codes"] if c]
        
        # Determine root type based on categories and account code ranges
        root_type = None
        
        # Check categories first
        if "FIN" in categories or "DEB" in categories or "VOOR" in categories:
            root_type = "Asset"
        elif "CRED" in categories or any(cat.startswith("AF") for cat in categories) or "BTWRC" in categories:
            root_type = "Liability"
        elif "VW" in categories:
            # P&L accounts - determine by account code
            if account_codes:
                avg_code = sum(int(c) for c in account_codes if c.isdigit()) / len(account_codes)
                if avg_code >= 80000:  # Income accounts typically 80000+
                    root_type = "Income"
                else:  # Expense accounts typically < 80000
                    root_type = "Expense"
        elif "BAL" in categories:
            # Balance sheet - determine by group code
            if group_code in ["001", "002", "003", "004"]:
                root_type = "Asset"
            elif group_code == "005":
                root_type = "Equity"
            elif group_code == "006":
                root_type = "Liability"
            else:
                # Determine by account codes
                if account_codes:
                    first_digit = account_codes[0][0] if account_codes[0] else "0"
                    if first_digit in ["0", "1", "2", "3"]:
                        root_type = "Asset"
                    elif first_digit == "5":
                        root_type = "Equity"
                    else:
                        root_type = "Liability"
        
        if root_type:
            group_root_types[group_code] = root_type
    
    print(f"\n=== Creating {len(group_info)} Account Groups ===")
    
    # Step 3: Create account groups
    created_groups = {}
    
    for group_code in sorted(group_info.keys()):
        root_type = group_root_types.get(group_code)
        
        if not root_type:
            print(f"Could not determine root type for group {group_code}")
            continue
        
        parent_account = created_roots.get(root_type)
        
        if not parent_account:
            print(f"No parent account for group {group_code} (root_type: {root_type})")
            continue
        
        try:
            # Check if group exists
            existing = frappe.db.get_value("Account", {
                "company": company,
                "account_number": group_code,
                "is_group": 1
            }, "name")
            
            if existing:
                created_groups[group_code] = existing
                print(f"Group exists: {group_code}")
            else:
                # Create group account
                group_name = f"Groep {group_code}"
                
                account = frappe.get_doc({
                    "doctype": "Account",
                    "account_name": group_name,
                    "company": company,
                    "parent_account": parent_account,
                    "root_type": root_type,
                    "is_group": 1,
                    "account_number": group_code
                })
                
                account.insert(ignore_permissions=True)
                created_groups[group_code] = account.name
                print(f"Created group: {group_code} - {group_name} under {root_type}")
                
        except Exception as e:
            print(f"Error creating group {group_code}: {str(e)}")
    
    frappe.db.commit()
    
    print(f"\n=== Summary ===")
    print(f"Root accounts: {len(created_roots)}")
    print(f"Account groups: {len(created_groups)}")
    
    return {
        "roots": created_roots,
        "groups": created_groups,
        "group_mappings": group_root_types
    }

@frappe.whitelist()
def test_fixed_migration():
    """Test the fixed CoA migration"""
    frappe.set_user("Administrator")
    
    # First create the hierarchy
    result = create_proper_coa_hierarchy()
    
    if not result:
        print("Failed to create hierarchy")
        return
    
    print("\n=== Now running CoA migration with proper hierarchy ===")
    
    # Get or create a migration document
    migration = frappe.new_doc("E-Boekhouden Migration")
    migration.migration_name = "Fixed CoA Migration Test"
    migration.migration_type = "Partial Migration"
    migration.migrate_accounts = 1
    migration.migrate_cost_centers = 0
    migration.migrate_transactions = 0
    migration.dry_run = 0
    migration.clear_existing_accounts = 0
    
    migration.save()
    
    # Get settings
    settings = frappe.get_single("E-Boekhouden Settings")
    
    try:
        # The migration should now work properly with the hierarchy in place
        result = migration.migrate_chart_of_accounts(settings)
        print(f"\nMigration result: {result}")
        
        # Check what was created
        accounts_created = frappe.db.count("Account", {
            "company": settings.default_company,
            "account_number": ["is", "set"]
        })
        
        print(f"\nTotal accounts with account numbers: {accounts_created}")
        
    except Exception as e:
        print(f"\nMigration failed: {str(e)}")
        import traceback
        traceback.print_exc()