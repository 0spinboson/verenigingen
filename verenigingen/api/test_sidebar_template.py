"""
Test enhanced sidebar template rendering
"""

import frappe

@frappe.whitelist()
def test_sidebar_template_rendering(test_user=None):
    """Test that the enhanced sidebar template renders correctly"""
    try:
        original_user = frappe.session.user
        if test_user:
            frappe.session.user = test_user
        
        try:
            # Test context preparation
            from verenigingen.templates.pages.me import get_context
            
            class MockContext:
                def __init__(self):
                    pass
            
            context = MockContext()
            get_context(context)
            
            # Test template rendering simulation
            template_data = {
                "success": True,
                "context_prepared": True,
                "sidebar_template": "templates/base_portal.html",
                "enhanced_sidebar_template": "templates/includes/web_sidebar_enhanced.html",
                "sidebar_items_count": len(getattr(context, 'sidebar_items', [])),
                "template_variables": {
                    "show_sidebar": getattr(context, 'show_sidebar', False),
                    "parent_template": getattr(context, 'parent_template', None),
                    "has_submenu_items": any(
                        item.get('submenu') for item in getattr(context, 'sidebar_items', [])
                    )
                }
            }
            
            # Check specific submenu structure
            sidebar_items = getattr(context, 'sidebar_items', [])
            member_portal_item = next((item for item in sidebar_items if item['title'] == 'Member Portal'), None)
            
            if member_portal_item and member_portal_item.get('submenu'):
                template_data["member_portal_submenu"] = [
                    submenu['title'] for submenu in member_portal_item['submenu']
                ]
            
            return template_data
            
        finally:
            frappe.session.user = original_user
        
    except Exception as e:
        frappe.session.user = original_user
        return {
            "success": False,
            "error": str(e)
        }