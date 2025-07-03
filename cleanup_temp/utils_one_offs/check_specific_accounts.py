"""
Check specific accounts and their classification
"""

import frappe
import json


@frappe.whitelist()
def check_accounts_classification():
    """
    Check classification of specific accounts: 14600, 17100, 18200
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        from verenigingen.utils.eboekhouden_category_mapping_fixed import analyze_accounts_by_category
        
        api = EBoekhoudenAPI()
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # Find the specific accounts
        target_codes = ["14600", "17100", "18200"]
        found_accounts = {}
        
        for acc in accounts:
            code = acc.get("code", "")
            if code in target_codes:
                found_accounts[code] = {
                    "code": code,
                    "description": acc.get("description", ""),
                    "category": acc.get("category", ""),
                    "group": acc.get("group", "")
                }
        
        # Get current category analysis to see how they're classified
        analysis = analyze_accounts_by_category()
        
        if not analysis["success"]:
            return {"success": False, "error": "Failed to analyze categories"}
        
        # Find where these accounts appear in the proposals
        classifications = {}
        for proposal in analysis["mapping_proposals"]:
            # Check sample accounts and identifier
            for sample in proposal.get("sample_accounts", []):
                if sample.get("code") in target_codes:
                    code = sample.get("code")
                    classifications[code] = {
                        "proposal_name": proposal.get("name"),
                        "proposal_type": proposal.get("type"),
                        "suggested_type": proposal.get("suggested_mapping", {}).get("type"),
                        "identifier": proposal.get("identifier")
                    }
        
        return {
            "success": True,
            "target_accounts": target_codes,
            "found_accounts": found_accounts,
            "current_classifications": classifications,
            "notes": [
                "These accounts need proper classification",
                "Check if they should be Equity, Liability, or other types"
            ]
        }
        
    except Exception as e:
        frappe.log_error(f"Error checking accounts: {str(e)}")
        return {"success": False, "error": str(e)}