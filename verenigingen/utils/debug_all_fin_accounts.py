"""
Debug all FIN accounts to find PSPs and bank accounts
"""

import frappe
import json


@frappe.whitelist()
def list_all_fin_accounts():
    """
    List all FIN accounts with their descriptions
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # Get all FIN accounts
        fin_accounts = [acc for acc in accounts if acc.get("category") == "FIN"]
        
        # Sort by code
        fin_accounts.sort(key=lambda x: x.get("code", ""))
        
        # Format for display
        formatted_accounts = []
        for acc in fin_accounts:
            formatted_accounts.append({
                "code": acc.get("code", ""),
                "description": acc.get("description", ""),
                "group": acc.get("group", ""),
                "lower_desc": acc.get("description", "").lower()
            })
        
        # Check current categorization
        from verenigingen.utils.eboekhouden_category_mapping_fixed import split_financial_accounts
        categories = split_financial_accounts(fin_accounts)
        
        return {
            "success": True,
            "total_fin_accounts": len(fin_accounts),
            "all_fin_accounts": formatted_accounts,
            "current_categorization": {
                "cash": len(categories.get("cash", [])),
                "bank": len(categories.get("bank", [])),
                "psp": len(categories.get("psp", [])),
                "cash_list": [{"code": a.get("code"), "desc": a.get("description")} for a in categories.get("cash", [])],
                "bank_list": [{"code": a.get("code"), "desc": a.get("description")} for a in categories.get("bank", [])],
                "psp_list": [{"code": a.get("code"), "desc": a.get("description")} for a in categories.get("psp", [])]
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error listing FIN accounts: {str(e)}")
        return {"success": False, "error": str(e)}