"""
Debug API account retrieval to see raw data
"""

import frappe
import json


@frappe.whitelist()
def debug_api_raw_response():
    """
    Get raw API response to debug missing accounts
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        data = json.loads(result["data"])
        
        # Get account statistics
        accounts = data.get("items", [])
        
        # Group by category
        by_category = {}
        for acc in accounts:
            cat = acc.get("category", "NONE")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(acc.get("code", ""))
        
        # Sort codes in each category
        for cat in by_category:
            by_category[cat].sort()
        
        # Look for accounts in 10400-10700 range
        range_accounts = []
        for acc in accounts:
            code = acc.get("code", "")
            if code and code.startswith("10"):
                try:
                    code_num = int(code)
                    if 10400 <= code_num <= 10700:
                        range_accounts.append({
                            "code": code,
                            "description": acc.get("description", ""),
                            "category": acc.get("category", ""),
                            "group": acc.get("group", "")
                        })
                except:
                    pass
        
        range_accounts.sort(key=lambda x: x["code"])
        
        return {
            "success": True,
            "total_accounts": len(accounts),
            "categories": {cat: f"{len(codes)} accounts" for cat, codes in by_category.items()},
            "fin_account_codes": by_category.get("FIN", []),
            "accounts_10400_10700": range_accounts,
            "api_endpoint": "GetGrootboekrekeningen",
            "raw_data_sample": accounts[:5] if accounts else []
        }
        
    except Exception as e:
        frappe.log_error(f"Error debugging API: {str(e)}")
        return {"success": False, "error": str(e)}