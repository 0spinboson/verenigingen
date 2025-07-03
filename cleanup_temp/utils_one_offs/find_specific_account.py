"""
Find specific account by code
"""

import frappe
import json


@frappe.whitelist()
def find_account_by_code(account_code):
    """
    Find account by exact code match
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # Find exact match
        found = None
        for account in accounts:
            if account.get("code", "") == str(account_code):
                found = account
                break
        
        # Also check nearby accounts
        nearby = []
        for account in accounts:
            code = account.get("code", "")
            if code and len(code) >= 4:
                try:
                    code_num = int(code)
                    target_num = int(account_code)
                    if abs(code_num - target_num) <= 10:
                        nearby.append({
                            "code": code,
                            "description": account.get("description", ""),
                            "category": account.get("category", ""),
                            "group": account.get("group", "")
                        })
                except:
                    pass
        
        nearby.sort(key=lambda x: x["code"])
        
        return {
            "success": True,
            "search_code": account_code,
            "found": found,
            "nearby_accounts": nearby
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}