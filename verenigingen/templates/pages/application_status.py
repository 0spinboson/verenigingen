"""
Context for application status page
"""

import frappe
from frappe import _

def get_context(context):
    """Get context for application status page"""
    
    context.no_cache = 1
    context.show_sidebar = False
    context.title = _("Application Status")
    
    # Get member from URL parameter or logged in user
    member_id = frappe.form_dict.get('id')
    
    if not member_id and frappe.session.user != "Guest":
        # Try to find member by email
        member_id = frappe.db.get_value("Member", {"email": frappe.session.user})
    
    if member_id:
        member = frappe.get_doc("Member", member_id)
        context.member = member
    else:
        context.member = None
    
    return context
