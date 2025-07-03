"""
Test classification of specific BAL accounts
"""

import frappe
import json


@frappe.whitelist()
def test_bal_accounts_classification():
    """
    Test how BAL accounts including 14600, 17100, 18200 are classified
    """
    try:
        from verenigingen.utils.eboekhouden_category_mapping_fixed import analyze_accounts_with_proper_categories
        
        # Get the analysis
        result = analyze_accounts_with_proper_categories()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to analyze accounts"}
        
        # Find BAL proposals
        bal_proposals = []
        target_accounts = {}
        
        for proposal in result["mapping_proposals"]:
            # Check if this is a BAL category
            if proposal.get("identifier") == "BAL":
                bal_proposals.append(proposal)
            
            # Check if any of our target accounts appear in the samples
            for sample in proposal.get("sample_accounts", []):
                if sample.get("code") in ["14600", "17100", "18200"]:
                    target_accounts[sample.get("code")] = {
                        "description": sample.get("description"),
                        "found_in": proposal.get("name"),
                        "suggested_type": proposal.get("suggested_mapping", {}).get("type")
                    }
        
        # Also check smart groups for these accounts
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI()
        accounts_result = api.get_chart_of_accounts()
        
        if accounts_result["success"]:
            data = json.loads(accounts_result["data"])
            all_accounts = data.get("items", [])
            
            # Find our specific accounts
            specific_accounts = []
            for acc in all_accounts:
                if acc.get("code") in ["14600", "17100", "18200"]:
                    specific_accounts.append(acc)
            
            # Test the grouping function
            from verenigingen.utils.eboekhouden_category_mapping_fixed import group_accounts_by_type
            smart_groups = group_accounts_by_type(specific_accounts)
            
            # See which group they end up in
            account_groups = {}
            for group_type, accounts in smart_groups.items():
                for acc in accounts:
                    if acc.get("code") in ["14600", "17100", "18200"]:
                        account_groups[acc.get("code")] = group_type
        
        return {
            "success": True,
            "bal_proposals": bal_proposals,
            "target_accounts_in_proposals": target_accounts,
            "smart_group_classification": account_groups,
            "recommendation": "These accounts should be classified as Current Liability"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}