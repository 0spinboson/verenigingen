"""
Simple test page to verify portal functionality
"""

import frappe
from frappe import _

def get_context(context):
    """Simple test context"""
    context.title = "Portal Test"
    context.message = "Portal pages are working!"
    
    # Check if user is logged in
    if frappe.session.user == "Guest":
        context.user_status = "Not logged in"
        context.login_url = "/login"
    else:
        context.user_status = f"Logged in as: {frappe.session.user}"
        
        # Try to find member record
        member = frappe.db.get_value("Member", {"email": frappe.session.user}, "name")
        if not member:
            member = frappe.db.get_value("Member", {"user": frappe.session.user}, "name")
        
        if member:
            context.member_found = f"Member record found: {member}"
        else:
            context.member_found = "No member record found for this user"
    
    return context