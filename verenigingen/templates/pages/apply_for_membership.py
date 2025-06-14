"""
Context for the membership application page
"""

import frappe
from frappe import _

def get_context(context):
    """Get context for membership application page"""
    
    # Set page properties
    context.no_cache = 1
    context.show_sidebar = False
    context.title = _("Apply for Membership")
    
    # Check if user is already a member
    if frappe.session.user != "Guest":
        existing_member = frappe.db.get_value("Member", {"email": frappe.session.user})
        if existing_member:
            # Redirect to member profile or show message
            context.already_member = True
            context.member_name = existing_member
            return context
    
    # Get verenigingen settings
    settings = frappe.get_single("Verenigingen Settings")
    context.settings = {
        "enable_chapter_management": settings.enable_chapter_management,
        "company_name": frappe.get_value("Company", settings.company, "company_name")
    }
    
    # Basic context setup
    context.already_member = False
    
    return context

# Add route configuration
no_cache = 1
sitemap = 0  # Don't include in sitemap
