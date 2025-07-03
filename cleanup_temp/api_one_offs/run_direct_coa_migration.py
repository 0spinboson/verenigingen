import frappe
import json

@frappe.whitelist()
def run_direct_coa_migration():
    """Run the E-boekhouden CoA migration directly with hierarchy already in place"""
    frappe.set_user("Administrator")
    
    print("=== Running E-boekhouden CoA Migration ===")
    
    # Check if hierarchy exists
    root_count = frappe.db.count("Account", {
        "company": "Ned Ver Vegan",
        "parent_account": ["is", "not set"],
        "is_group": 1
    })
    
    group_count = frappe.db.count("Account", {
        "company": "Ned Ver Vegan",
        "account_number": ["is", "set"],
        "is_group": 1
    })
    
    print(f"Found {root_count} root accounts and {group_count} group accounts")
    
    if root_count == 0 or group_count == 0:
        print("ERROR: Hierarchy not set up. Run verenigingen.api.run_fixed_coa_migration.run_fixed_coa_migration first")
        return
    
    # Create a new migration document
    migration = frappe.new_doc("E-Boekhouden Migration")
    migration.migration_name = "Direct CoA Account Import"
    migration.migration_type = "Partial Migration"
    migration.migrate_accounts = 1
    migration.migrate_cost_centers = 0
    migration.migrate_transactions = 0
    migration.dry_run = 0
    migration.clear_existing_accounts = 0
    
    # Initialize counters that the migration expects
    migration.total_records = 0
    migration.imported_records = 0
    migration.failed_records = 0
    migration.failed_record_details = []
    
    migration.save()
    
    # Get settings
    settings = frappe.get_single("E-Boekhouden Settings")
    
    # Get the E-boekhouden API data
    from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
    
    api = EBoekhoudenAPI(settings)
    result = api.get_chart_of_accounts()
    
    if not result["success"]:
        print(f"Failed to fetch accounts: {result['error']}")
        return
    
    accounts_data = json.loads(result["data"])
    accounts = accounts_data.get("items", [])
    
    print(f"\n=== Processing {len(accounts)} accounts ===")
    
    # Get group mappings
    group_accounts = {}
    groups = frappe.db.get_list("Account", {
        "company": settings.default_company,
        "account_number": ["is", "set"],
        "is_group": 1
    }, ["name", "account_number"])
    
    for grp in groups:
        group_accounts[grp.account_number] = grp.name
    
    print(f"Available parent groups: {list(group_accounts.keys())}")
    
    # Process accounts
    created = 0
    skipped = 0
    failed = 0
    
    # Sort accounts by code to ensure parents are created before children
    sorted_accounts = sorted(accounts, key=lambda x: (len(x.get('code', '')), x.get('code', '')))
    
    for i, acc in enumerate(sorted_accounts):
        try:
            account_code = acc.get('code', '')
            account_name = acc.get('description', '')
            category = acc.get('category', '')
            group_code = acc.get('group', '')
            
            if not account_code or not account_name:
                failed += 1
                print(f"Invalid account data: {acc}")
                continue
            
            # Clean up account name
            if account_name.startswith(f"{account_code} - "):
                account_name = account_name[len(account_code) + 3:]
            elif account_name.startswith(account_code):
                account_name = account_name[len(account_code):].lstrip(" -")
            
            if not account_name.strip():
                account_name = f"Account {account_code}"
            
            # Check if already exists
            existing = frappe.db.exists("Account", {
                "account_number": account_code,
                "company": settings.default_company
            })
            
            if existing:
                skipped += 1
                if i < 10:  # Show first 10
                    print(f"  Skipped: {account_code} - {account_name} (already exists)")
                continue
            
            # Determine parent account
            parent_account = None
            
            if group_code and group_code in group_accounts:
                parent_account = group_accounts[group_code]
            else:
                print(f"  WARNING: No parent group {group_code} for account {account_code}")
                # Try to find appropriate parent based on category/code
                parent_account = find_fallback_parent(acc, settings.default_company)
            
            if not parent_account:
                failed += 1
                print(f"  FAILED: No parent found for {account_code} - {account_name}")
                continue
            
            # Determine root type
            root_type = determine_root_type(acc)
            
            # Determine if this should be a group
            is_group = any(
                other.get('code', '').startswith(account_code) and 
                other.get('code', '') != account_code 
                for other in sorted_accounts
            )
            
            # Create account
            new_account = frappe.get_doc({
                "doctype": "Account",
                "account_name": f"{account_code} - {account_name}",
                "account_number": account_code,
                "eboekhouden_grootboek_nummer": account_code,
                "company": settings.default_company,
                "parent_account": parent_account,
                "root_type": root_type,
                "is_group": 1 if is_group else 0,
                "disabled": 0
            })
            
            # Add account type if applicable
            account_type = determine_account_type(acc)
            if account_type:
                new_account.account_type = account_type
            
            new_account.insert(ignore_permissions=True)
            created += 1
            
            if i < 10 or created <= 10:  # Show first 10
                print(f"  Created: {account_code} - {account_name} [{'GROUP' if is_group else 'LEAF'}] under {parent_account}")
            
        except Exception as e:
            failed += 1
            print(f"  ERROR creating {acc.get('code', 'Unknown')}: {str(e)}")
    
    frappe.db.commit()
    
    print(f"\n=== Summary ===")
    print(f"Total accounts: {len(accounts)}")
    print(f"Created: {created}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")
    
    # Show some examples of what was created
    if created > 0:
        examples = frappe.db.get_list("Account", {
            "company": settings.default_company,
            "account_number": ["is", "set"],
            "parent_account": ["!=", ""],
            "is_group": 0
        }, ["name", "account_name", "account_number", "parent_account", "root_type"], 
        order_by="creation desc", limit=10)
        
        print("\n=== Recently Created Leaf Accounts ===")
        for ex in examples:
            print(f"{ex.account_number}: {ex.account_name} [{ex.root_type}] (Parent: {ex.parent_account})")

def find_fallback_parent(account_data, company):
    """Find a fallback parent account when group is not found"""
    
    category = account_data.get('category', '')
    code = account_data.get('code', '')
    
    # Map categories to root accounts
    category_map = {
        'FIN': 'Activa - NVV',
        'DEB': 'Activa - NVV',
        'VOOR': 'Activa - NVV',
        'CRED': 'Passiva - NVV',
        'BTWRC': 'Passiva - NVV',
        'AF': 'Passiva - NVV',
        'AF6': 'Passiva - NVV',
        'AF19': 'Passiva - NVV',
        'AFOVERIG': 'Passiva - NVV',
    }
    
    if category in category_map:
        return category_map[category]
    
    # For BAL and VW, determine by code
    if category == 'BAL':
        if code.startswith(('0', '1', '2')):
            return 'Activa - NVV'
        elif code.startswith('5'):
            return 'Eigen Vermogen - NVV'
        else:
            return 'Passiva - NVV'
    elif category == 'VW':
        if code.startswith('8'):
            return 'Opbrengsten - NVV'
        else:
            return 'Kosten - NVV'
    
    return None

def determine_root_type(account_data):
    """Determine root type for an account"""
    
    category = account_data.get('category', '')
    code = account_data.get('code', '')
    
    # Direct category mappings
    if category in ['FIN', 'DEB', 'VOOR']:
        return 'Asset'
    elif category in ['CRED', 'BTWRC', 'AF', 'AF6', 'AF19', 'AFOVERIG']:
        return 'Liability'
    elif category == 'BAL':
        if code.startswith(('0', '1', '2')):
            return 'Asset'
        elif code.startswith('5'):
            return 'Equity'
        else:
            return 'Liability'
    elif category == 'VW':
        if code.startswith('8'):
            return 'Income'
        else:
            return 'Expense'
    
    return 'Expense'  # Default

def determine_account_type(account_data):
    """Determine account type if applicable"""
    
    category = account_data.get('category', '')
    code = account_data.get('code', '')
    
    # Tax accounts
    if category in ['BTWRC', 'AF', 'AF6', 'AF19', 'AFOVERIG', 'VOOR']:
        return 'Tax'
    
    # Bank accounts
    if category == 'FIN':
        return 'Bank'
    
    # Check code patterns
    if code.startswith('15'):
        return 'Bank'
    elif code.startswith('16'):
        return 'Cash'
    
    return None