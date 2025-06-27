"""
Debug the mapping application to see why accounts aren't updating
"""

import frappe
import json


@frappe.whitelist()
def debug_mapping_application():
    """
    Debug why mappings aren't being applied
    """
    try:
        # Test with a specific mapping
        test_mappings = {
            "BAL_Current Asset": "Current Asset",
            "VW_Income": "Income Account"
        }
        
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        from verenigingen.utils.apply_category_mapping_fixed import get_accounts_for_mapping, update_account_type_safe
        
        api = EBoekhoudenAPI()
        accounts_result = api.get_chart_of_accounts()
        
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        
        debug_info = {}
        
        for mapping_key, target_type in test_mappings.items():
            # Get accounts for this mapping
            mapped_accounts = get_accounts_for_mapping(mapping_key, accounts)
            
            debug_info[mapping_key] = {
                "target_type": target_type,
                "accounts_found": len(mapped_accounts),
                "account_details": []
            }
            
            # Check first few accounts
            for acc in mapped_accounts[:3]:
                account_code = acc.get("code")
                
                # Check if account exists in ERPNext
                erpnext_account = frappe.db.get_value(
                    "Account",
                    {"account_number": account_code},
                    ["name", "account_type", "disabled"],
                    as_dict=True
                )
                
                if erpnext_account:
                    # Try to update
                    result = update_account_type_safe(
                        account_code,
                        target_type,
                        acc.get("description", "")
                    )
                    
                    debug_info[mapping_key]["account_details"].append({
                        "code": account_code,
                        "description": acc.get("description"),
                        "erpnext_name": erpnext_account.name,
                        "current_type": erpnext_account.account_type,
                        "target_type": target_type,
                        "disabled": erpnext_account.disabled,
                        "update_result": result
                    })
                else:
                    debug_info[mapping_key]["account_details"].append({
                        "code": account_code,
                        "description": acc.get("description"),
                        "error": "Not found in ERPNext"
                    })
        
        return {
            "success": True,
            "debug_info": debug_info
        }
        
    except Exception as e:
        frappe.log_error(f"Error in debug: {str(e)}")
        return {"success": False, "error": str(e)}