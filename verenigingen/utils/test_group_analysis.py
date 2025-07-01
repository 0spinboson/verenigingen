"""
Test the improved group analysis
"""

import frappe
from frappe import _


@frappe.whitelist()
def test_group_name_detection():
    """Test the improved group name detection"""
    try:
        from verenigingen.utils.eboekhouden_group_analysis_improved import (
            find_common_phrases, get_group_mapping_improved
        )
        
        # Test phrase detection with sample data
        test_cases = [
            {
                "descriptions": [
                    "022 BTW te vorderen hoog",
                    "022 BTW te vorderen laag", 
                    "022 BTW te vorderen overig"
                ],
                "expected": "BTW te vorderen"
            },
            {
                "descriptions": [
                    "005 Eigen vermogen algemeen",
                    "005 Eigen vermogen reserve",
                    "005 Eigen vermogen resultaat"
                ],
                "expected": "Eigen vermogen"
            },
            {
                "descriptions": [
                    "002 Liquide middelen kas",
                    "002 Liquide middelen bank",
                    "002 Liquide middelen spaar"
                ],
                "expected": "Liquide middelen"
            }
        ]
        
        phrase_test_results = []
        for test in test_cases:
            phrases = find_common_phrases(test["descriptions"])
            top_phrase = phrases[0][0] if phrases else "No common phrase found"
            phrase_test_results.append({
                "test": test["expected"],
                "found": top_phrase,
                "all_phrases": phrases[:3],  # Top 3 phrases
                "success": test["expected"].lower() in top_phrase.lower()
            })
        
        # Test actual group mapping
        group_result = get_group_mapping_improved()
        
        # Extract specific groups of interest
        groups_of_interest = {}
        if group_result.get("success"):
            for group in group_result.get("groups", []):
                code = group["group_code"]
                if code in ["002", "005", "022"]:
                    groups_of_interest[code] = {
                        "inferred_name": group["inferred_name"],
                        "account_count": group["account_count"],
                        "sample_accounts": group.get("sample_accounts", [])[:2]
                    }
        
        return {
            "success": True,
            "phrase_detection_tests": phrase_test_results,
            "actual_groups": groups_of_interest,
            "total_groups_found": len(group_result.get("groups", [])) if group_result.get("success") else 0,
            "improvements": [
                "Multi-word phrases are now properly detected",
                "Short words like '022' are preserved in group codes",
                "Common phrase detection prefers longer, more specific phrases",
                "Special handling for known groups like 002, 005, 022"
            ]
        }
        
    except Exception as e:
        frappe.log_error(f"Test group analysis error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist() 
def compare_group_analysis_methods():
    """Compare old vs new group analysis methods"""
    try:
        # Get results from both methods
        from verenigingen.utils.eboekhouden_group_analysis import get_group_mapping as get_old
        from verenigingen.utils.eboekhouden_group_analysis_improved import get_group_mapping_improved as get_new
        
        old_result = get_old()
        new_result = get_new()
        
        if not (old_result.get("success") and new_result.get("success")):
            return {
                "success": False,
                "error": "Failed to get results from one or both methods"
            }
        
        # Compare group names
        comparison = []
        old_groups = {g["group_code"]: g for g in old_result.get("groups", [])}
        new_groups = {g["group_code"]: g for g in new_result.get("groups", [])}
        
        for code in sorted(set(old_groups.keys()) | set(new_groups.keys())):
            old_name = old_groups.get(code, {}).get("inferred_name", "Not found")
            new_name = new_groups.get(code, {}).get("inferred_name", "Not found")
            
            comparison.append({
                "group_code": code,
                "old_name": old_name,
                "new_name": new_name,
                "improved": old_name != new_name and not new_name.startswith("Group"),
                "account_count": new_groups.get(code, {}).get("account_count", 0)
            })
        
        # Count improvements
        improvements = sum(1 for c in comparison if c["improved"])
        
        return {
            "success": True,
            "comparison": comparison,
            "summary": {
                "total_groups": len(comparison),
                "improved_names": improvements,
                "improvement_rate": f"{(improvements/len(comparison)*100):.1f}%" if comparison else "0%"
            },
            "notable_improvements": [c for c in comparison if c["improved"]][:5]
        }
        
    except Exception as e:
        frappe.log_error(f"Compare group analysis error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }