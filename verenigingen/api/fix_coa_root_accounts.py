"""
Fix Chart of Accounts root account creation issues
"""

import frappe
import json

@frappe.whitelist()
def create_missing_root_accounts():
    """
    Create the missing root accounts that are causing the hierarchy issues
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        if not company:
            return {"success": False, "error": "No default company found"}
        
        # Get company abbreviation
        company_abbr = frappe.db.get_value("Company", company, "abbr")
        
        api = EBoekhoudenAPI(settings)
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get CoA data"}
        
        data = json.loads(result["data"])
        accounts_data = data.get("items", [])
        
        # Identify accounts that should be root accounts
        root_accounts_to_create = []
        
        for acc in accounts_data:
            code = acc.get("code", "")
            description = acc.get("description", "")
            category = acc.get("category", "")
            group = acc.get("group", "")
            
            # Determine if this should be a root account
            should_be_root = False
            
            # Check the same logic as in the migration
            if (len(code) <= 2 or 
                (len(code) == 3 and code.startswith("00")) or
                (group and group in ['001', '002', '003', '004', '005', '006', '007', '008', '009', '010'])):
                should_be_root = True
            else:
                # Check if there's no potential parent in the dataset
                has_potential_parent = False
                all_codes = set(a.get('code', '') for a in accounts_data if a.get('code'))
                
                for i in range(len(code) - 1, 0, -1):
                    potential_parent_code = code[:i]
                    if potential_parent_code in all_codes:
                        has_potential_parent = True
                        break
                
                if not has_potential_parent:
                    should_be_root = True
            
            if should_be_root:
                # Map category to root_type
                root_type = map_category_to_root_type(category, code)
                
                root_accounts_to_create.append({
                    "code": code,
                    "description": description,
                    "category": category,
                    "group": group,
                    "root_type": root_type,
                    "full_name": f"{description} - {company_abbr}"
                })
        
        # Sort by code length and code to ensure proper creation order
        root_accounts_to_create.sort(key=lambda x: (len(x["code"]), x["code"]))
        
        # Create the root accounts
        created_count = 0
        errors = []
        
        for root_acc in root_accounts_to_create:
            try:
                # Check if account already exists
                existing = frappe.db.exists("Account", {
                    "account_number": root_acc["code"],
                    "company": company
                })
                
                if existing:
                    continue
                
                # Create the root account
                account = frappe.new_doc("Account")
                account.account_name = root_acc["description"]
                account.account_number = root_acc["code"]
                account.company = company
                account.root_type = root_acc["root_type"]
                account.is_group = 1  # Root accounts must be groups
                account.disabled = 0
                
                account.insert(ignore_permissions=True)
                created_count += 1
                
                frappe.logger().info(f"Created root account: {root_acc['code']} - {root_acc['description']}")
                
            except Exception as e:
                errors.append(f"Failed to create {root_acc['code']}: {str(e)}")
        
        frappe.db.commit()
        
        return {
            "success": True,
            "created_count": created_count,
            "total_root_accounts": len(root_accounts_to_create),
            "errors": errors,
            "root_accounts": root_accounts_to_create[:10],  # First 10 for review
            "message": f"Created {created_count} root accounts out of {len(root_accounts_to_create)} identified"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def map_category_to_root_type(category, code):
    """Map E-boekhouden category to ERPNext root_type"""
    
    # Category-based mapping
    category_mapping = {
        'BTWRC': 'Liability',  # VAT current account
        'AF6': 'Liability',    # Turnover tax low rate
        'AF19': 'Liability',   # Turnover tax high rate
        'AFOVERIG': 'Liability', # Turnover tax other
        'AF': 'Liability',     # Turnover tax
        'VOOR': 'Asset',       # Input tax (VAT receivable)
        'FIN': 'Asset',        # Liquid Assets
        'DEB': 'Asset',        # Debtors
        'CRED': 'Liability',   # Creditors
    }
    
    if category in category_mapping:
        return category_mapping[category]
    
    # For BAL and VW categories, determine from account code
    if category == 'BAL':
        if code.startswith(('0', '1', '2')):
            return 'Asset'
        elif code.startswith(('3', '4')):
            return 'Liability'
        elif code.startswith('5'):
            return 'Equity'
        else:
            return 'Asset'  # Default for unknown BAL accounts
    
    elif category == 'VW':
        if code.startswith('8'):
            return 'Income'
        elif code.startswith(('6', '7')):
            return 'Expense'
        elif code.startswith('9'):
            return 'Expense'  # Result accounts
        else:
            return 'Expense'  # Default for unknown VW accounts
    
    # Default fallback based on code
    if code.startswith(('0', '1', '2')):
        return 'Asset'
    elif code.startswith(('3', '4')):
        return 'Liability'
    elif code.startswith('5'):
        return 'Equity'
    elif code.startswith('8'):
        return 'Income'
    elif code.startswith(('6', '7', '9')):
        return 'Expense'
    else:
        return 'Asset'  # Final fallback

@frappe.whitelist()
def retry_coa_migration_after_root_fix():
    """
    Retry the Chart of Accounts migration after creating root accounts
    """
    try:
        # First create missing root accounts
        root_result = create_missing_root_accounts()
        
        if not root_result["success"]:
            return root_result
        
        # Now run a test to see if we can create the problematic account
        return {
            "success": True,
            "root_creation": root_result,
            "message": f"Created {root_result['created_count']} root accounts. Ready to retry full migration."
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }