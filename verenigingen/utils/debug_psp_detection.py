"""
Debug PSP detection to find why Mollie isn't being categorized properly
"""

import frappe
import json
import re


@frappe.whitelist()
def debug_psp_accounts():
    """
    Debug PSP account detection
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # Look for all potential PSP accounts
        psp_patterns = [
            "paypal", "mollie", "stripe", "adyen", "pay.nl", "pay nl",
            "tikkie", "ideal", "buckaroo", "multisafepay", "sisow"
        ]
        
        potential_psps = []
        fin_accounts = []
        
        for account in accounts:
            code = account.get("code", "")
            desc = account.get("description", "").lower()
            category = account.get("category", "")
            
            # Track all FIN accounts
            if category == "FIN":
                fin_accounts.append({
                    "code": code,
                    "description": account.get("description", ""),
                    "category": category,
                    "group": account.get("group", ""),
                    "detected_as_psp": any(psp in desc for psp in psp_patterns)
                })
            
            # Check if this could be a PSP regardless of category
            for psp in psp_patterns:
                if psp in desc:
                    potential_psps.append({
                        "code": code,
                        "description": account.get("description", ""),
                        "category": category,
                        "group": account.get("group", ""),
                        "matched_pattern": psp,
                        "is_fin": category == "FIN"
                    })
        
        # Analyze Mollie specifically
        mollie_accounts = []
        for account in accounts:
            desc_lower = account.get("description", "").lower()
            if "molli" in desc_lower:  # Check for partial match in case of typo
                mollie_accounts.append({
                    "code": account.get("code", ""),
                    "description": account.get("description", ""),
                    "category": account.get("category", ""),
                    "group": account.get("group", "")
                })
        
        # Check current PSP detection logic
        from verenigingen.utils.eboekhouden_category_mapping_fixed import split_financial_accounts
        fin_only = [acc for acc in accounts if acc.get("category") == "FIN"]
        psp_detection_result = split_financial_accounts(fin_only)
        
        return {
            "success": True,
            "analysis": {
                "total_accounts": len(accounts),
                "fin_accounts": len(fin_accounts),
                "potential_psps_found": len(potential_psps),
                "mollie_specific": len(mollie_accounts)
            },
            "potential_psps": potential_psps,
            "mollie_accounts": mollie_accounts,
            "fin_accounts_sample": fin_accounts[:10],  # First 10 FIN accounts
            "current_psp_detection": {
                "psps_found": len(psp_detection_result.get("psp", [])),
                "psp_list": psp_detection_result.get("psp", [])
            },
            "debug_notes": [
                f"Found {len(potential_psps)} potential PSP accounts across all categories",
                f"Found {len(mollie_accounts)} accounts with 'molli' in description",
                f"Current detection found {len(psp_detection_result.get('psp', []))} PSPs in FIN category",
                "Check if Mollie account exists and what category it has"
            ]
        }
        
    except Exception as e:
        frappe.log_error(f"Error debugging PSP detection: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def search_account_by_name(search_term):
    """
    Search for accounts by name pattern
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        search_lower = search_term.lower()
        matches = []
        
        for account in accounts:
            code = account.get("code", "")
            desc = account.get("description", "").lower()
            
            if search_lower in desc or search_lower in code.lower():
                matches.append({
                    "code": code,
                    "description": account.get("description", ""),
                    "category": account.get("category", ""),
                    "group": account.get("group", ""),
                    "match_in": "description" if search_lower in desc else "code"
                })
        
        return {
            "success": True,
            "search_term": search_term,
            "matches_found": len(matches),
            "matches": matches
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}