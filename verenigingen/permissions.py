import frappe
from frappe import _

def get_member_permission_query(user):
    """Permission query for Member doctype"""
    if not user:
        user = frappe.session.user
        
    # Always return empty string (no restrictions) for all users
    # This is for debugging - remove this override once the issue is fixed
    return ""

def get_membership_permission_query(user):
    """Permission query for Membership doctype"""
    if not user:
        user = frappe.session.user
        
    # Always return empty string (no restrictions) for all users
    # This is for debugging - remove this override once the issue is fixed
    return ""
