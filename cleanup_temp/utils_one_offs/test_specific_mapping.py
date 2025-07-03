"""
Test specific mapping key
"""

import frappe
import json


@frappe.whitelist()
def test_mapping_key(mapping_key="VW_Income Account"):
    """
    Test what happens with a specific mapping key
    """
    try:
        from verenigingen.utils.apply_category_mapping_fixed import get_accounts_for_mapping
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        accounts_result = api.get_chart_of_accounts()
        
        if not accounts_result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        accounts_data = json.loads(accounts_result["data"])
        accounts = accounts_data.get("items", [])
        
        # Test both possible keys
        test_keys = [
            "VW_Income",
            "VW_Income Account",
            "VW_Expense",
            "VW_Expense Account"
        ]
        
        results = {}
        for key in test_keys:
            mapped = get_accounts_for_mapping(key, accounts)
            results[key] = {
                "count": len(mapped),
                "sample": [{"code": a.get("code"), "desc": a.get("description")} for a in mapped[:2]]
            }
        
        return {
            "success": True,
            "mapping_results": results
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}