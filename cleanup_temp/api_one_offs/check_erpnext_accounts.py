"""
Check ERPNext account structure
"""

import frappe

@frappe.whitelist()
def check_erpnext_account_structure():
    """
    Check the current ERPNext account structure to understand the hierarchy
    """
    try:
        company = "Ned Ver Vegan"
        
        # Get all accounts for the company
        all_accounts = frappe.db.get_all("Account",
            filters={"company": company},
            fields=["name", "account_name", "parent_account", "root_type", "is_group", "account_number"],
            order_by="name"
        )
        
        # Find root accounts (no parent)
        root_accounts = [acc for acc in all_accounts if not acc.parent_account]
        
        # Find accounts with parents
        child_accounts = [acc for acc in all_accounts if acc.parent_account]
        
        # Check for standard ERPNext accounts
        standard_roots = []
        for root_type in ["Asset", "Liability", "Equity", "Income", "Expense"]:
            matching_roots = [acc for acc in root_accounts if acc.root_type == root_type]
            standard_roots.extend(matching_roots)
        
        return {
            "success": True,
            "company": company,
            "total_accounts": len(all_accounts),
            "root_accounts": root_accounts,
            "child_accounts": child_accounts[:10],  # First 10 for review
            "standard_root_types": standard_roots,
            "has_root_accounts": len(root_accounts) > 0,
            "account_structure_analysis": {
                "needs_standard_roots": len(standard_roots) == 0,
                "has_hierarchy": len(child_accounts) > 0
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def create_standard_erpnext_roots():
    """
    Create the standard ERPNext root accounts if they don't exist
    """
    try:
        company = "Ned Ver Vegan"
        company_abbr = frappe.db.get_value("Company", company, "abbr")
        
        # Standard ERPNext root accounts
        standard_roots = [
            {"name": "Assets", "root_type": "Asset"},
            {"name": "Liabilities", "root_type": "Liability"},
            {"name": "Equity", "root_type": "Equity"},
            {"name": "Income", "root_type": "Income"},
            {"name": "Expenses", "root_type": "Expense"}
        ]
        
        created = []
        errors = []
        
        for root_config in standard_roots:
            try:
                # Check if root account already exists
                account_name_with_abbr = f"{root_config['name']} - {company_abbr}"
                existing = frappe.db.exists("Account", {"name": account_name_with_abbr})
                
                if existing:
                    continue
                
                # Create the standard root account
                account = frappe.new_doc("Account")
                account.account_name = root_config["name"]
                account.company = company
                account.root_type = root_config["root_type"]
                account.is_group = 1  # Root accounts must be groups
                account.disabled = 0
                # Don't set parent_account - this should be empty for root accounts
                
                account.insert(ignore_permissions=True)
                created.append(account_name_with_abbr)
                
            except Exception as e:
                errors.append(f"Failed to create {root_config['name']}: {str(e)}")
        
        frappe.db.commit()
        
        return {
            "success": True,
            "created": created,
            "errors": errors,
            "message": f"Created {len(created)} standard root accounts"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }