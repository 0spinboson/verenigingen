"""
Test BAL account splitting
"""

import frappe
import json


@frappe.whitelist()
def test_bal_splitting():
    """
    Test how BAL accounts are now split into subtypes
    """
    try:
        from verenigingen.utils.eboekhouden_category_mapping_fixed import analyze_accounts_with_proper_categories
        
        # Get the analysis
        result = analyze_accounts_with_proper_categories()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to analyze accounts"}
        
        # Find BAL-related proposals
        bal_proposals = []
        target_accounts_found = {}
        
        for proposal in result["mapping_proposals"]:
            # Check if this is a BAL subcategory
            if proposal.get("identifier", "").startswith("BAL_"):
                bal_proposals.append({
                    "identifier": proposal.get("identifier"),
                    "name": proposal.get("name"),
                    "account_count": proposal.get("account_count"),
                    "suggested_type": proposal.get("suggested_mapping", {}).get("type"),
                    "sample_codes": [acc.get("code") for acc in proposal.get("sample_accounts", [])]
                })
                
                # Check if our target accounts are in this subcategory
                for sample in proposal.get("sample_accounts", []):
                    if sample.get("code") in ["14600", "17100", "18200"]:
                        target_accounts_found[sample.get("code")] = {
                            "found_in": proposal.get("name"),
                            "suggested_as": proposal.get("suggested_mapping", {}).get("type")
                        }
        
        return {
            "success": True,
            "bal_subcategories": bal_proposals,
            "target_accounts": target_accounts_found,
            "total_bal_proposals": len(bal_proposals)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}