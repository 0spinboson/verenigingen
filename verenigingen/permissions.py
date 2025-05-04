import frappe
from frappe import _

def get_member_permission_query(user):
    """Permission query for Member doctype"""
    if not user:
        user = frappe.session.user
        
    # System Managers can access all members
    if "System Manager" in frappe.get_roles(user):
        return ""
        
    # Membership Managers can access all members
    if "Membership Manager" in frappe.get_roles(user):
        return ""
        
    # Membership Users can only view members
    if "Membership User" in frappe.get_roles(user):
        return ""
        
    # Users can only see their own member record
    return f"""(`tabMember`.`user` = '{user}')"""
    
def get_membership_permission_query(user):
    """Permission query for Membership doctype"""
    if not user:
        user = frappe.session.user
        
    # System Managers can access all memberships
    if "System Manager" in frappe.get_roles(user):
        return ""
        
    # Membership Managers can access all memberships
    if "Membership Manager" in frappe.get_roles(user):
        return ""
        
    # Membership Users can only view memberships
    if "Membership User" in frappe.get_roles(user):
        return ""
        
    # Users can only see memberships linked to their member record
    member = frappe.db.get_value("Member", {"user": user}, "name")
    if member:
        return f"""(`tabMembership`.`member` = '{member}')"""
    else:
        # If no member record is found, don't allow access to any memberships
        return "1=0"
