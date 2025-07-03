"""
Fix for E-boekhouden CoA migration to properly handle account hierarchy
"""
import frappe
import json

def get_eboekhouden_hierarchy_mapping():
    """
    Define the proper hierarchy for E-boekhouden accounts
    Returns a mapping of group codes to their parent groups and root types
    """
    
    # E-boekhouden uses a flat structure with groups (rekening groepen)
    # We need to create a hierarchy based on the group codes and categories
    
    hierarchy = {
        # Root level groups - these will be created as root accounts
        "roots": {
            "activa": {"root_type": "Asset", "name": "Activa"},
            "passiva": {"root_type": "Liability", "name": "Passiva"}, 
            "eigen_vermogen": {"root_type": "Equity", "name": "Eigen Vermogen"},
            "opbrengsten": {"root_type": "Income", "name": "Opbrengsten"},
            "kosten": {"root_type": "Expense", "name": "Kosten"}
        },
        
        # Group mappings - which groups belong under which root
        "group_to_root": {
            # Asset groups
            "001": "activa",  # Fixed assets
            "002": "activa",  # Financial/liquid assets
            "003": "activa",  # Inventory
            "004": "activa",  # Debtors/receivables
            
            # Liability groups
            "006": "passiva",  # Creditors/payables
            
            # Equity groups
            "005": "eigen_vermogen",  # Equity/reserves
            
            # Expense groups (Winst & Verlies - costs)
            "007": "kosten",  # Personnel costs
            "009": "kosten",  # General costs
            "014": "kosten",  # Other costs
            "016": "kosten",  # Other costs
            "017": "kosten",  # Other costs
            "022": "kosten",  # Other costs
            "023": "kosten",  # Other costs
            "024": "kosten",  # Other costs
            "025": "kosten",  # Other costs
            "027": "kosten",  # Other costs
            "028": "kosten",  # Other costs
            "029": "kosten",  # Other costs
            "031": "kosten",  # Other costs
            "033": "kosten",  # Other costs
            "034": "kosten",  # Other costs
            "035": "kosten",  # Other costs
            "040": "kosten",  # Other costs
            
            # Income groups (Winst & Verlies - income)
            "055": "opbrengsten",  # Income/revenue
        },
        
        # Category to root type mapping for accounts without clear group assignment
        "category_to_root": {
            "FIN": "Asset",      # Financial/liquid assets
            "DEB": "Asset",      # Debtors
            "VOOR": "Asset",     # Input VAT
            "CRED": "Liability", # Creditors
            "BTWRC": "Liability", # VAT current account
            "AF": "Liability",   # VAT payable
            "AF6": "Liability",  # VAT low rate
            "AF19": "Liability", # VAT high rate
            "AFOVERIG": "Liability", # VAT other
        }
    }
    
    return hierarchy

def create_root_accounts_for_migration(company):
    """Create the root accounts needed for E-boekhouden migration"""
    
    hierarchy = get_eboekhouden_hierarchy_mapping()
    created_roots = {}
    
    for root_key, root_config in hierarchy["roots"].items():
        try:
            # Check if root account exists
            existing = frappe.db.get_value("Account", {
                "company": company,
                "account_name": root_config["name"],
                "root_type": root_config["root_type"],
                "parent_account": ["is", "not set"]
            }, "name")
            
            if existing:
                created_roots[root_key] = existing
                frappe.logger().info(f"Root account exists: {existing}")
            else:
                # Create root account with special handling
                account = frappe.new_doc("Account")
                account.account_name = root_config["name"]
                account.company = company
                account.root_type = root_config["root_type"]
                account.is_group = 1
                
                # Use flags to bypass validation
                account.flags.ignore_permissions = True
                account.flags.ignore_mandatory = True
                account.flags.ignore_validate = True
                
                account.insert()
                created_roots[root_key] = account.name
                frappe.logger().info(f"Created root account: {account.name}")
                
        except Exception as e:
            frappe.logger().error(f"Error creating root {root_config['name']}: {str(e)}")
    
    frappe.db.commit()
    return created_roots

def create_group_accounts_for_migration(company, roots):
    """Create the group accounts (rekening groepen) under appropriate roots"""
    
    hierarchy = get_eboekhouden_hierarchy_mapping()
    created_groups = {}
    
    # Get all unique groups from E-boekhouden accounts
    from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenAPI(settings)
    
    result = api.get_chart_of_accounts()
    if not result["success"]:
        frappe.logger().error(f"Failed to fetch accounts: {result['error']}")
        return created_groups
    
    accounts_data = json.loads(result["data"])
    accounts = accounts_data.get("items", [])
    
    # Extract unique groups
    groups = {}
    for acc in accounts:
        group_code = acc.get("group", "")
        if group_code and group_code not in groups:
            groups[group_code] = True
    
    # Create group accounts
    for group_code in sorted(groups.keys()):
        root_key = hierarchy["group_to_root"].get(group_code)
        
        if not root_key or root_key not in roots:
            frappe.logger().warning(f"No root mapping for group {group_code}")
            continue
        
        parent_account = roots[root_key]
        root_info = hierarchy["roots"][root_key]
        
        try:
            # Check if group exists
            existing = frappe.db.get_value("Account", {
                "company": company,
                "account_number": group_code,
                "is_group": 1
            }, "name")
            
            if existing:
                created_groups[group_code] = existing
                frappe.logger().info(f"Group account exists: {existing}")
            else:
                # Create group account
                account = frappe.new_doc("Account")
                account.account_name = f"Groep {group_code}"
                account.account_number = group_code
                account.company = company
                account.parent_account = parent_account
                account.root_type = root_info["root_type"]
                account.is_group = 1
                
                account.insert(ignore_permissions=True)
                created_groups[group_code] = account.name
                frappe.logger().info(f"Created group account: {account.name}")
                
        except Exception as e:
            frappe.logger().error(f"Error creating group {group_code}: {str(e)}")
    
    frappe.db.commit()
    return created_groups

def should_be_root_account(account_data, all_account_codes):
    """
    Determine if an account should be a root account
    This fixes the incorrect logic in the original migration
    """
    
    # E-boekhouden doesn't have root accounts - all accounts belong to groups
    # So NO account should be created as a root account
    return False

def get_parent_account_for_eboekhouden(account_data, company, created_groups):
    """
    Get the correct parent account for an E-boekhouden account
    """
    
    group_code = account_data.get("group", "")
    
    if group_code and group_code in created_groups:
        return created_groups[group_code]
    
    # Fallback - try to determine from category
    category = account_data.get("category", "")
    hierarchy = get_eboekhouden_hierarchy_mapping()
    
    root_type = None
    
    # Check category mapping
    if category in hierarchy["category_to_root"]:
        root_type = hierarchy["category_to_root"][category]
    elif category == "BAL":
        # Balance sheet - determine from account code
        code = account_data.get("code", "")
        if code.startswith(("0", "1", "2", "3")):
            root_type = "Asset"
        elif code.startswith("5"):
            root_type = "Equity"
        else:
            root_type = "Liability"
    elif category == "VW":
        # P&L - determine from account code
        code = account_data.get("code", "")
        if code and code.isdigit():
            if int(code) >= 80000:
                root_type = "Income"
            else:
                root_type = "Expense"
    
    # Find appropriate root account
    if root_type:
        return frappe.db.get_value("Account", {
            "company": company,
            "root_type": root_type,
            "parent_account": ["is", "not set"],
            "is_group": 1
        }, "name")
    
    return None

def determine_if_group_account(account_code, all_account_codes):
    """
    Determine if an account should be a group account
    An account is a group if other accounts have codes that start with this account's code
    """
    
    if not account_code:
        return False
    
    # Check if any other account code starts with this code
    for other_code in all_account_codes:
        if other_code != account_code and other_code.startswith(account_code):
            return True
    
    return False

@frappe.whitelist()
def prepare_coa_hierarchy():
    """Prepare the CoA hierarchy before migration"""
    frappe.set_user("Administrator")
    
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company
    
    print("=== Preparing E-boekhouden CoA Hierarchy ===")
    
    # Step 1: Create root accounts
    print("\n1. Creating root accounts...")
    roots = create_root_accounts_for_migration(company)
    print(f"Created/found {len(roots)} root accounts")
    
    # Step 2: Create group accounts
    print("\n2. Creating group accounts...")
    groups = create_group_accounts_for_migration(company, roots)
    print(f"Created/found {len(groups)} group accounts")
    
    print("\n=== Hierarchy preparation complete ===")
    print("You can now run the E-boekhouden migration.")
    
    return {"roots": roots, "groups": groups}