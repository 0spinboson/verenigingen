"""
Test specific groups mentioned by the user
"""

import frappe
from frappe import _


@frappe.whitelist()
def test_specific_group_issues():
    """Test the specific groups that were having issues: 022, 005"""
    try:
        from verenigingen.utils.eboekhouden_group_analysis_improved import (
            get_group_mapping_improved, find_common_phrases
        )
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        # Get the actual data
        api = EBoekhoudenAPI()
        result = api.get_chart_of_accounts()
        
        if not result["success"]:
            return {"success": False, "error": "Failed to get chart of accounts"}
        
        import json
        data = json.loads(result["data"])
        accounts = data.get("items", [])
        
        # Find accounts in groups 022 and 005
        group_022_accounts = [acc for acc in accounts if acc.get("group") == "022"]
        group_005_accounts = [acc for acc in accounts if acc.get("group") == "005"]
        
        # Test phrase detection for these specific groups
        results = {}
        
        # Test group 022
        if group_022_accounts:
            descriptions_022 = [acc.get("description", "") for acc in group_022_accounts]
            phrases_022 = find_common_phrases(descriptions_022)
            results["group_022"] = {
                "account_count": len(group_022_accounts),
                "sample_accounts": descriptions_022[:5],
                "detected_phrases": phrases_022[:5],
                "top_phrase": phrases_022[0] if phrases_022 else None
            }
        
        # Test group 005  
        if group_005_accounts:
            descriptions_005 = [acc.get("description", "") for acc in group_005_accounts]
            phrases_005 = find_common_phrases(descriptions_005)
            results["group_005"] = {
                "account_count": len(group_005_accounts),
                "sample_accounts": descriptions_005[:5],
                "detected_phrases": phrases_005[:5],
                "top_phrase": phrases_005[0] if phrases_005 else None
            }
        
        # Get the improved mapping result
        mapping_result = get_group_mapping_improved()
        
        # Extract info for groups 022 and 005
        improved_groups = {}
        if mapping_result.get("success"):
            for group in mapping_result.get("groups", []):
                if group["group_code"] in ["022", "005"]:
                    improved_groups[group["group_code"]] = {
                        "inferred_name": group["inferred_name"],
                        "categories": group["categories"],
                        "account_count": group["account_count"]
                    }
        
        return {
            "success": True,
            "phrase_detection_results": results,
            "improved_group_names": improved_groups,
            "notes": [
                "Group 022 should now show proper name instead of 'Group 022'",
                "Group 005 'eigen vermogen' should be properly detected",
                "Multi-word phrases are preserved in full"
            ]
        }
        
    except Exception as e:
        frappe.log_error(f"Test specific groups error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }