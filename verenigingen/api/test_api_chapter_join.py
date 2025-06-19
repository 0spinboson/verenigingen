"""
Test API chapter join functionality
"""

import frappe

@frappe.whitelist()
def test_api_chapter_join(chapter_name="Zeist", test_user="fjdh@leden.socialisten.org"):
    """Test the API chapter join functionality"""
    try:
        original_user = frappe.session.user
        if test_user:
            frappe.session.user = test_user
        
        try:
            # Import the API function
            from verenigingen.api.chapter_join import join_chapter
            
            # Test the join_chapter API
            result = join_chapter(chapter_name, "Test introduction for API chapter join")
            
            return {
                "success": True,
                "api_result": result,
                "user": frappe.session.user
            }
            
        finally:
            frappe.session.user = original_user
        
    except Exception as e:
        frappe.session.user = original_user
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }