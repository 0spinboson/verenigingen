"""
E-Boekhouden API with proper pagination support
"""

import frappe
import json


@frappe.whitelist()
def get_all_chart_of_accounts():
    """
    Get ALL chart of accounts with pagination
    The API defaults to 100 items but supports up to 2000 per request
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        all_accounts = []
        offset = 0
        limit = 500  # Use 500 per page for efficiency
        
        while True:
            # Get page of accounts
            result = api.make_request("v1/ledger", "GET", {
                "limit": limit,
                "offset": offset
            })
            
            if not result["success"]:
                return {
                    "success": False,
                    "error": f"Failed at offset {offset}: {result.get('error', 'Unknown error')}"
                }
            
            data = json.loads(result["data"])
            accounts = data.get("items", [])
            
            # Add accounts to collection
            all_accounts.extend(accounts)
            
            # Check if we got less than requested (end of data)
            if len(accounts) < limit:
                break
            
            # Move to next page
            offset += limit
            
            # Safety check to prevent infinite loops
            if offset > 10000:
                frappe.log_error("Safety limit reached in pagination")
                break
        
        # Return complete data
        return {
            "success": True,
            "data": json.dumps({"items": all_accounts}),
            "total_accounts": len(all_accounts),
            "pages_fetched": (offset // limit) + 1
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting all accounts: {str(e)}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def find_account_10460():
    """
    Specifically look for account 10460
    """
    try:
        result = get_all_chart_of_accounts()
        
        if not result["success"]:
            return result
        
        data = json.loads(result["data"])
        all_accounts = data.get("items", [])
        
        # Find account 10460
        account_10460 = None
        fin_accounts = []
        
        for acc in all_accounts:
            if acc.get("code") == "10460":
                account_10460 = acc
            if acc.get("category") == "FIN":
                fin_accounts.append({
                    "code": acc.get("code"),
                    "description": acc.get("description"),
                    "category": acc.get("category"),
                    "group": acc.get("group")
                })
        
        # Sort FIN accounts by code
        fin_accounts.sort(key=lambda x: x["code"])
        
        return {
            "success": True,
            "total_accounts": len(all_accounts),
            "account_10460": account_10460,
            "all_fin_accounts": fin_accounts,
            "fin_account_count": len(fin_accounts)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}