import frappe
from frappe import _

def has_member_permission(doc, user=None, permission_type=None):
    """Direct permission check for Member doctype"""
    if not user:
        user = frappe.session.user
        
    # Log for debugging
    frappe.logger().debug(f"Checking Member permissions for user {user} with roles {frappe.get_roles(user)}")
    
    # Admin roles always have access
    admin_roles = ["System Manager", "Membership Manager", "Association Manager", "Association Manager"]
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
    admin_roles = ["System Manager", "Membership Manager", "Association Manager", "Association Manager"]
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

    admin_roles = ["System Manager", "Membership Manager", "Association Manager", "Association Manager"]
    if any(role in frappe.get_roles(user) for role in admin_roles):
        frappe.logger().debug(f"User {user} has admin role, granting full access")
        return ""
        
    # Other permission logic would go here
    
    # For debugging purposes, grant access to all
    return ""

def get_membership_permission_query(user):
    """Permission query for Membership doctype"""
    if not user:
        user = frappe.session.user
        
    # Always return empty string (no restrictions) for all users
    # This is for debugging - remove this override once the issue is fixed
    return ""

def can_view_financial_info(doctype, name=None, user=None):
    """Check if user can view financial information for a member"""
    if not user:
        user = frappe.session.user
        
    # System managers and Verenigingen managers can always view
    if ("System Manager" in frappe.get_roles(user) or 
        "Association Manager" in frappe.get_roles(user) or
        "Membership Manager" in frappe.get_roles(user)):
        return True
    
    # Get the member for this user
    viewer_member = frappe.db.get_value("Member", {"user": user}, "name")
    if not viewer_member:
        return False
        
    if not name:
        # Just checking general permission
        return False
        
    # Allow members to view their own financial info
    target_member = frappe.get_doc("Member", name)
    if target_member.user == user:
        return True
        
    # Check if viewer is a board member with financial permissions
    if target_member.primary_chapter:
        chapter = frappe.get_doc("Chapter", target_member.primary_chapter)
        return chapter.can_view_member_payments(viewer_member)
        
    # Not permitted
    return False

def check_member_payment_access(member_name, user=None):
    """Check if a user can access payment information for a member"""
    if not user:
        user = frappe.session.user
        
    # Admins can access all
    if ("System Manager" in frappe.get_roles(user) or 
        "Association Manager" in frappe.get_roles(user) or
        "Membership Manager" in frappe.get_roles(user)):
        return True
        
    # Allow members to view their own payment info
    member = frappe.get_doc("Member", member_name)
    if member.user == user:
        return True
        
    # Check permission category
    if member.permission_category == "Public":
        return True
    elif member.permission_category == "Admin Only":
        return False
        
    # For Board Only - check if user is on board with financial permissions
    viewer_member = frappe.db.get_value("Member", {"user": user}, "name")
    if not viewer_member:
        return False
        
    if member.primary_chapter:
        chapter = frappe.get_doc("Chapter", member.primary_chapter)
        return chapter.can_view_member_payments(viewer_member)
        
    return False
