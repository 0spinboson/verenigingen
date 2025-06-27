"""
Check specific accounts and their classification
"""

import frappe
import json


@frappe.whitelist()
def check_three_accounts():
    """
    Check accounts 14600, 17100, 18200
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # Find the specific accounts
        target_codes = ["14600", "17100", "18200"]
        found_accounts = []
        
        for acc in accounts:
            code = acc.get("code", "")
            if code in target_codes:
                found_accounts.append({
                    "code": code,
                    "description": acc.get("description", ""),
                    "category": acc.get("category", ""),
                    "group": acc.get("group", "")
                })
        
        # Sort by code
        found_accounts.sort(key=lambda x: x["code"])
        
        return {
            "success": True,
            "found_accounts": found_accounts,
            "count": len(found_accounts)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}