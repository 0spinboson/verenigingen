"""
Test enhanced sidebar functionality
"""

import frappe

@frappe.whitelist()
def test_enhanced_sidebar_context(test_user=None):
    """Test the enhanced sidebar context for portal pages"""
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
            
            # Check sidebar specific attributes
            sidebar_data = {
                "success": True,
                "user": frappe.session.user,
                "has_sidebar_items": hasattr(context, 'sidebar_items') and len(context.sidebar_items) > 0,
                "sidebar_count": len(context.sidebar_items) if hasattr(context, 'sidebar_items') else 0,
                "show_sidebar": getattr(context, 'show_sidebar', False),
                "parent_template": getattr(context, 'parent_template', None),
                "sidebar_items_with_submenu": []
            }
            
            # Check for submenu items in sidebar
            if hasattr(context, 'sidebar_items'):
                for item in context.sidebar_items:
                    if item.get('submenu'):
                        sidebar_data["sidebar_items_with_submenu"].append({
                            "title": item['title'],
                            "submenu_count": len(item['submenu']),
                            "submenu_titles": [sub['title'] for sub in item['submenu'][:3]]  # First 3 for brevity
                        })
            
            return sidebar_data
            
        finally:
            frappe.session.user = original_user
        
    except Exception as e:
        frappe.session.user = original_user
        return {
            "success": False,
            "error": str(e)
        }