"""
Simple API endpoint for fixing account types
"""

import frappe
from frappe import _

@frappe.whitelist()
def fix_account_types_now():
    """
    Direct function to fix account types without preview
    """
    try:
        from verenigingen.utils.fix_receivable_payable_entries import analyze_and_fix_entries, apply_account_type_fixes
        
        # First analyze
        analysis = analyze_and_fix_entries()
        
        if not analysis.get("success"):
            return analysis
        
        if analysis.get("action") == "preview" and analysis.get("accounts_to_fix"):
            # Apply fixes directly
            result = apply_account_type_fixes(analysis["accounts_to_fix"])
            return result
        else:
            return {
                "success": True,
                "summary": "No accounts need fixing. All account types are correct."
            }
            
    except Exception as e:
        frappe.log_error(f"Error fixing account types: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }