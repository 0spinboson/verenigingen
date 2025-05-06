import frappe
from frappe import _

def has_member_permission(doc, user=None, permission_type=None):
    """Direct permission check for Member doctype"""
    if not user:
        user = frappe.session.user
        
    # Log for debugging
    frappe.logger().debug(f"Checking Member permissions for user {user} with roles {frappe.get_roles(user)}")
    
    # Admin roles always have access
    admin_roles = ["System Manager", "Membership Manager", "Association Manager", "Verenigingen Manager"]
    if any(role in frappe.get_roles(user) for role in admin_roles):
        frappe.logger().debug(f"User {user} has admin role, granting access")
        return True
    
    # Other permission checks would go here
    
    # Return None to fall back to standard permission system if no match
    return None

def has_membership_permission(doc, user=None, permission_type=None):
    """Direct permission check for Membership doctype"""
    if not user:
        user = frappe.session.user
        
    # Log for debugging
    frappe.logger().debug(f"Checking Membership permissions for user {user} with roles {frappe.get_roles(user)}")
    
    # Admin roles always have access
    admin_roles = ["System Manager", "Membership Manager", "Association Manager", "Verenigingen Manager"]
    if any(role in frappe.get_roles(user) for role in admin_roles):
        frappe.logger().debug(f"User {user} has admin role, granting access")
        return True
    
    # Other permission checks would go here
    
    # Return None to fall back to standard permission system if no match
    return None

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
