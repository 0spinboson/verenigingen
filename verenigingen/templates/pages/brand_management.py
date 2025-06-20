"""
Brand Management Page
Allows administrators to manage brand colors and theming
"""

import frappe
from frappe import _

def get_context(context):
    """Get context for brand management page"""
    
    # Require login and admin access
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to access this page"), frappe.PermissionError)
    
    # Check admin permissions
    admin_roles = ["System Manager", "Verenigingen Administrator"]
    user_roles = frappe.get_roles()
    if not any(role in user_roles for role in admin_roles):
        frappe.throw(_("You need administrator privileges to access this page"), frappe.PermissionError)
    
    context.no_cache = 1
    context.title = _("Brand Management")
    
    # Get all brand settings
    all_settings = frappe.get_all("Brand Settings", 
        fields=["name", "settings_name", "description", "is_active", "primary_color", "secondary_color", "accent_color"],
        order_by="is_active desc, modified desc")
    
    context.brand_settings = all_settings
    
    # Get active settings for preview
    from verenigingen.verenigingen.doctype.brand_settings.brand_settings import get_active_brand_settings
    context.active_settings = get_active_brand_settings()
    
    return context

def has_website_permission(doc, ptype, user, verbose=False):
    """Check website permission for brand management page"""
    # Only logged-in users can access
    if user == "Guest":
        return False
    
    # Check admin roles
    admin_roles = ["System Manager", "Verenigingen Administrator"]
    user_roles = frappe.get_roles(user)
    return any(role in user_roles for role in admin_roles)