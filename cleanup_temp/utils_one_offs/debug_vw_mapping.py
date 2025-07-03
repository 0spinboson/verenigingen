"""
Debug VW mapping specifically
"""

import frappe
import json


@frappe.whitelist()
def debug_vw_accounts():
    """
    Debug VW account detection and mapping
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        from verenigingen.utils.eboekhouden_category_mapping_fixed import split_vw_accounts
        
        api = EBoekhoudenAPI()
        accounts_result = api.get_chart_of_accounts()
        
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        
        # Get VW accounts
        vw_accounts = [acc for acc in accounts if acc.get("category") == "VW"]
        
        # Split them
        vw_groups = split_vw_accounts(vw_accounts)
        
        # Check specific accounts
        sample_income = []
        sample_expense = []
        
        for group_name, group_accounts in vw_groups.items():
            if "Income" in group_name:
                sample_income = group_accounts[:5]
            else:
                sample_expense = group_accounts[:5]
        
        # Check their status in ERPNext
        income_status = []
        for acc in sample_income:
            erpnext_info = frappe.db.get_value(
                "Account",
                {"account_number": acc.get("code")},
                ["name", "account_type"],
                as_dict=True
            )
            income_status.append({
                "code": acc.get("code"),
                "description": acc.get("description"),
                "erpnext": erpnext_info
            })
        
        expense_status = []
        for acc in sample_expense:
            erpnext_info = frappe.db.get_value(
                "Account",
                {"account_number": acc.get("code")},
                ["name", "account_type"],
                as_dict=True
            )
            expense_status.append({
                "code": acc.get("code"),
                "description": acc.get("description"),
                "erpnext": erpnext_info
            })
        
        return {
            "success": True,
            "vw_accounts_count": len(vw_accounts),
            "vw_groups": {k: len(v) for k, v in vw_groups.items()},
            "sample_income_accounts": income_status,
            "sample_expense_accounts": expense_status,
            "group_keys": list(vw_groups.keys())
        }
        
    except Exception as e:
        frappe.log_error(f"Error debugging VW: {str(e)}")
        return {"success": False, "error": str(e)}