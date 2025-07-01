"""
Member Setup Onboarding Page
"""

import frappe
from frappe import _

no_cache = 1

def get_context(context):
    """Provide context for member setup onboarding page"""
    context.no_cache = 1
    context.show_sidebar = False
    
    # Check permissions
    if not frappe.has_permission("Member", "create"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    
    # Get existing test members count
    test_members_count = frappe.db.count("Member", 
        filters={"email": ["like", "%@testvereniging.nl"]}
    )
    
    context.test_members_count = test_members_count
    context.has_test_members = test_members_count > 0
    
    return context

@frappe.whitelist()
def generate_test_members_from_onboarding():
    """Generate test members from the onboarding page"""
    from verenigingen.api.generate_test_members import generate_test_members
    
    result = generate_test_members()
    
    # Mark onboarding step as complete if successful
    if result.get("success") and result.get("summary", {}).get("created", 0) > 0:
        frappe.db.set_value("Onboarding Step", "Verenigingen-Create-Member", "is_complete", 1)
        frappe.db.commit()
    
    return result

@frappe.whitelist()
def create_single_member():
    """Redirect to create a single member"""
    return {
        "redirect": "/app/member/new-member-1",
        "message": _("Redirecting to create a new member...")
    }