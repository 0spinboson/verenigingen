"""
Test enhanced portal page
"""

import frappe

@frappe.whitelist()
def test_enhanced_portal_page(test_user=None):
    """Test the enhanced me portal page context"""
    try:
        original_user = frappe.session.user
        if test_user:
            frappe.session.user = test_user
        
        try:
            # Import the page context function
            from verenigingen.templates.pages.me import get_context
            
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
                "has_menu_items": hasattr(context, 'menu_items') and len(context.menu_items) > 0,
                "menu_count": len(context.menu_items) if hasattr(context, 'menu_items') else 0,
                "has_html": hasattr(context, 'enhanced_menu_html') and context.enhanced_menu_html is not None,
                "is_member": getattr(context, 'is_member', False),
                "member_name": getattr(context, 'member_name', None),
                "page_title": getattr(context, 'page_title', None),
                "sample_menu_titles": [item['title'] for item in context.menu_items[:3]] if hasattr(context, 'menu_items') else []
            }
        finally:
            frappe.session.user = original_user
        
    except Exception as e:
        frappe.session.user = original_user
        return {
            "success": False,
            "error": str(e)
        }