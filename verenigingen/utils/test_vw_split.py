"""
Test VW account splitting
"""

import frappe
import json


@frappe.whitelist()
def test_vw_splitting():
    """
    Test how VW accounts are split into income and expense
    """
    try:
        from verenigingen.utils.eboekhouden_category_mapping_fixed import analyze_accounts_with_proper_categories
        
        # Get the analysis
        result = analyze_accounts_with_proper_categories()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to analyze accounts"}
        
        # Find VW-related proposals
        vw_proposals = []
        
        for proposal in result["mapping_proposals"]:
            # Check if this is a VW subcategory
            if proposal.get("identifier", "").startswith("VW_"):
                vw_proposals.append({
                    "identifier": proposal.get("identifier"),
                    "name": proposal.get("name"),
                    "account_count": proposal.get("account_count"),
                    "suggested_type": proposal.get("suggested_mapping", {}).get("type"),
                    "sample_accounts": [
                        {
                            "code": acc.get("code"),
                            "description": acc.get("description")
                        } for acc in proposal.get("sample_accounts", [])
                    ]
                })
        
        return {
            "success": True,
            "vw_subcategories": vw_proposals,
            "total_vw_proposals": len(vw_proposals)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}