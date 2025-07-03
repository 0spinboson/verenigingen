"""
Preview functionality for category-based mapping
"""

import frappe
import json
from frappe import _


@frappe.whitelist()
def get_category_mapping_preview(mappings):
    """
    Get preview of category-based mapping changes
    
    Args:
        mappings: Dict like {"FIN_cash": "Cash", "FIN_bank": "Bank", "DEB": "Receivable"}
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
        
        preview = {}
        
        for mapping_key, target_type in mappings.items():
            if not target_type or target_type == "Skip":
                continue
            
            accounts_to_update = []
            accounts_already_correct = []
            accounts_not_found = []
            
            # Handle different mapping key formats
            if "_" in mapping_key and mapping_key.startswith("FIN_"):
                # Subcategory mapping like FIN_cash, FIN_bank
                from verenigingen.utils.apply_category_mapping_fixed import get_accounts_for_mapping
                mapped_accounts = get_accounts_for_mapping(mapping_key, accounts)
                
                for account in mapped_accounts:
                    check_account_for_update(
                        account, target_type, 
                        accounts_to_update, accounts_already_correct, accounts_not_found
                    )
            
            elif "_" in mapping_key and mapping_key.startswith("SMART_"):
                # Smart group mapping for uncategorized accounts
                from verenigingen.utils.apply_category_mapping_fixed import get_accounts_for_mapping
                mapped_accounts = get_accounts_for_mapping(mapping_key, accounts)
                
                for account in mapped_accounts:
                    check_account_for_update(
                        account, target_type,
                        accounts_to_update, accounts_already_correct, accounts_not_found
                    )
            
            elif "_" in mapping_key and mapping_key.startswith("BAL_"):
                # Balance sheet type mapping
                balance_type = mapping_key.split("_", 1)[1]
                
                for account in accounts:
                    if account.get("category") != "BAL":
                        continue
                    
                    from verenigingen.utils.eboekhouden_category_based_mapping import determine_balance_account_type
                    if determine_balance_account_type(account) == balance_type:
                        check_account_for_update(
                            account, target_type,
                            accounts_to_update, accounts_already_correct, accounts_not_found
                        )
            
            else:
                # Regular category mapping (DEB, CRED, etc.)
                category_accounts = [a for a in accounts if a.get("category") == mapping_key]
                
                for account in category_accounts:
                    check_account_for_update(
                        account, target_type,
                        accounts_to_update, accounts_already_correct, accounts_not_found
                    )
            
            # Create display name for the preview
            display_name = get_mapping_display_name(mapping_key)
            
            preview[display_name] = {
                "target_type": target_type,
                "accounts_to_update": accounts_to_update,
                "accounts_already_correct": accounts_already_correct,
                "accounts_not_found": accounts_not_found
            }
        
        return {
            "success": True,
            "preview": preview
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting category preview: {str(e)}")
        return {"success": False, "error": str(e)}


def check_account_for_update(account, target_type, to_update, already_correct, not_found):
    """Check if an account needs updating"""
    account_code = account.get("code", "")
    description = account.get("description", "")
    
    # Find the account in ERPNext
    account_info = frappe.db.get_value(
        "Account",
        {"account_number": account_code},
        ["name", "account_type"],
        as_dict=True
    )
    
    if not account_info:
        not_found.append({
            "code": account_code,
            "description": description
        })
    elif account_info.account_type == target_type:
        already_correct.append({
            "code": account_code,
            "description": description,
            "current_type": account_info.account_type
        })
    else:
        to_update.append({
            "code": account_code,
            "description": description,
            "current_type": account_info.account_type or "Not Set",
            "new_type": target_type
        })


def get_mapping_display_name(mapping_key):
    """Get a user-friendly display name for the mapping key"""
    if mapping_key == "DEB":
        return "Debiteuren (Receivables)"
    elif mapping_key == "CRED":
        return "Crediteuren (Payables)"
    elif mapping_key == "FIN_cash":
        return "Kas accounts (Cash)"
    elif mapping_key == "FIN_bank":
        return "Bankrekeningen (Bank)"
    elif mapping_key == "FIN_psp":
        return "Payment Service Providers (Mollie, PayPal, etc.)"
    elif mapping_key.startswith("SMART_"):
        smart_type = mapping_key.split("_", 1)[1]
        smart_names = {
            "Equity": "Eigen Vermogen & Reserves",
            "Income": "Omzet & Opbrengsten",
            "Expense": "Kosten & Uitgaven",
            "Tax": "BTW Rekeningen",
            "Fixed Asset": "Vaste Activa",
            "Current Asset": "Vlottende Activa",
            "Current Liability": "Kortlopende Schulden"
        }
        return smart_names.get(smart_type, smart_type)
    else:
        return mapping_key