"""
Apply category-based mappings with proper handling
"""

import frappe
import json
from frappe import _


@frappe.whitelist()
def apply_fixed_category_mappings(mappings):
    """
    Apply mappings from the fixed category analysis
    
    Args:
        mappings: Dict like {"FIN_cash": "Cash", "FIN_bank": "Bank", "SMART_Equity": "Equity"}
    """
    try:
        if isinstance(mappings, str):
            mappings = json.loads(mappings)
        
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # Get all accounts
        accounts_result = api.get_chart_of_accounts()
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        
        results = {
            "updated": [],
            "skipped": [],
            "errors": [],
            "not_found": []
        }
        
        # Process each mapping
        for mapping_key, target_type in mappings.items():
            if not target_type or target_type == "Skip":
                continue
            
            # Get accounts for this mapping
            mapped_accounts = get_accounts_for_mapping(mapping_key, accounts)
            
            for account in mapped_accounts:
                result = update_account_type_safe(
                    account.get("code"),
                    target_type,
                    account.get("description", "")
                )
                
                if result["status"] == "updated":
                    results["updated"].append(result["message"])
                elif result["status"] == "skipped":
                    results["skipped"].append(result["message"])
                elif result["status"] == "not_found":
                    results["not_found"].append(result["message"])
                else:
                    results["errors"].append(result["message"])
        
        return {
            "success": True,
            "summary": {
                "total_updated": len(results["updated"]),
                "total_skipped": len(results["skipped"]),
                "total_not_found": len(results["not_found"]),
                "total_errors": len(results["errors"])
            },
            "details": results
        }
        
    except Exception as e:
        frappe.log_error(f"Error applying mappings: {str(e)}")
        return {"success": False, "error": str(e)}


def get_accounts_for_mapping(mapping_key, all_accounts):
    """Get accounts that match a specific mapping key"""
    accounts = []
    
    if mapping_key.startswith("FIN_"):
        # Financial subcategory
        subtype = mapping_key.split("_", 1)[1]
        from verenigingen.utils.eboekhouden_category_mapping_fixed import split_financial_accounts
        
        fin_accounts = [acc for acc in all_accounts if acc.get("category") == "FIN"]
        fin_groups = split_financial_accounts(fin_accounts)
        accounts = fin_groups.get(subtype, [])
        
    elif mapping_key.startswith("SMART_"):
        # Smart grouping for uncategorized accounts
        group_type = mapping_key.split("_", 1)[1]
        from verenigingen.utils.eboekhouden_category_mapping_fixed import group_accounts_by_type
        
        no_cat_accounts = [acc for acc in all_accounts if not acc.get("category")]
        smart_groups = group_accounts_by_type(no_cat_accounts)
        accounts = smart_groups.get(group_type, [])
        
    else:
        # Regular category
        accounts = [acc for acc in all_accounts if acc.get("category") == mapping_key]
    
    return accounts


def update_account_type_safe(account_code, target_type, description=""):
    """Safely update an account's type with proper error handling"""
    try:
        if not account_code:
            return {
                "status": "error",
                "message": f"No account code provided for {description}"
            }
        
        # Find the account in ERPNext
        account_name = frappe.db.get_value(
            "Account",
            {"account_number": account_code},
            "name"
        )
        
        if not account_name:
            return {
                "status": "not_found",
                "message": f"Account {account_code} - {description} not found in ERPNext"
            }
        
        # Get the account document
        account = frappe.get_doc("Account", account_name)
        old_type = account.account_type
        
        # Check if already correct
        if old_type == target_type:
            return {
                "status": "skipped",
                "message": f"{account_code} - {description} already has type {target_type}"
            }
        
        # Update the account
        account.account_type = target_type
        
        # Ensure correct root type for special account types
        if target_type == "Receivable":
            account.root_type = "Asset"
        elif target_type == "Payable":
            account.root_type = "Liability"
        elif target_type == "Equity":
            account.root_type = "Equity"
        elif target_type in ["Income", "Expense"]:
            # These should not change the root type
            pass
        
        account.save(ignore_permissions=True)
        
        return {
            "status": "updated",
            "message": f"Updated {account_code} - {description}: {old_type or 'Not Set'} → {target_type}"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error updating {account_code}: {str(e)}"
        }