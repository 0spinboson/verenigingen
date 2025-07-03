"""
Test cost center creation
"""

import frappe
from frappe import _


@frappe.whitelist()
def test_cost_center_creation():
    """Test creating a cost center"""
    try:
        from verenigingen.utils.eboekhouden_cost_center_fix import create_cost_center_safe, ensure_root_cost_center
        
        # Get default company
        settings = frappe.get_single("E-Boekhouden Settings")
        company = settings.default_company
        
        if not company:
            return {
                "success": False,
                "error": "No default company set in E-Boekhouden Settings"
            }
        
        results = []
        
        # Test 1: Ensure root cost center
        root_cc = ensure_root_cost_center(company)
        results.append({
            "test": "ensure_root_cost_center",
            "result": root_cc,
            "success": bool(root_cc)
        })
        
        # Test 2: Create a test cost center
        test_result = create_cost_center_safe("Test NLVF", company)
        results.append({
            "test": "create_cost_center_safe",
            "result": test_result,
            "success": test_result.get("success", False)
        })
        
        # Test 3: Try creating same cost center again (should return existing)
        duplicate_result = create_cost_center_safe("Test NLVF", company)
        results.append({
            "test": "create_duplicate",
            "result": duplicate_result,
            "success": duplicate_result.get("success", False) and "already exists" in duplicate_result.get("message", "")
        })
        
        # Test 4: Create cost center with specific parent
        if root_cc:
            child_result = create_cost_center_safe("Test Child NLVF", company, root_cc)
            results.append({
                "test": "create_with_parent",
                "result": child_result,
                "success": child_result.get("success", False)
            })
        
        return {
            "success": True,
            "company": company,
            "test_results": results,
            "summary": f"Ran {len(results)} tests, {sum(1 for r in results if r['success'])} passed"
        }
        
    except Exception as e:
        frappe.log_error(f"Error testing cost center creation: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }