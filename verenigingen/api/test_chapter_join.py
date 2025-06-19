"""
Test chapter join functionality
"""

import frappe

@frappe.whitelist()
def test_chapter_join_context(chapter_name="Zeist", test_user=None):
    """Test the chapter join page context"""
    try:
        original_user = frappe.session.user
        if test_user:
            frappe.session.user = test_user
        
        # Set form dict to simulate chapter parameter
        original_form_dict = frappe.form_dict
        frappe.form_dict = frappe._dict({"chapter": chapter_name})
        
        try:
            # Import the page context function
            from verenigingen.templates.pages.chapter_join import get_context
            
            # Create a mock context object
            class MockContext:
                def __init__(self):
                    pass
            
            context = MockContext()
            
            # Call the get_context function
            result = get_context(context)
            
            # Extract the relevant data
            return {
                "success": True,
                "user": frappe.session.user,
                "chapter_found": hasattr(context, 'chapter') and context.chapter is not None,
                "chapter_name": context.chapter.name if hasattr(context, 'chapter') else None,
                "already_member": getattr(context, 'already_member', None),
                "title": getattr(context, 'title', None),
                "no_cache": getattr(context, 'no_cache', None)
            }
            
        finally:
            frappe.session.user = original_user
            frappe.form_dict = original_form_dict
        
    except Exception as e:
        frappe.session.user = original_user
        frappe.form_dict = original_form_dict
        return {
            "success": False,
            "error": str(e)
        }