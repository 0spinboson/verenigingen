import frappe
from frappe import _

def get_member_permission_query(user):
    """Permission query for Member doctype"""
    if not user:
        user = frappe.session.user
        
    # Check user roles
    user_roles = frappe.get_roles(user)
    
    # System Managers and Association Managers can access all members
    if ("System Manager" in user_roles or 
        "Membership Manager" in user_roles or 
        "Association Manager" in user_roles or 
        "Verenigingen Manager" in user_roles):
        return ""  # No restrictions
        
    # Membership Users can only view members
    if "Membership User" in user_roles:
        return ""  # Could be restricted if needed
        
    # Board members can view chapter members
    member = frappe.db.get_value("Member", {"user": user}, "name")
    if member:
        # Get chapters where user is a board member
        board_chapters = frappe.get_all(
            "Chapter Board Member",
            filters={"member": member, "is_active": 1},
            fields=["parent as chapter"]
        )
        
        if board_chapters:
            chapter_list = ["'{0}'".format(c.chapter) for c in board_chapters]
            chapters_str = ", ".join(chapter_list)
            
            # Members can see other members in their chapters
            return """(`tabMember`.`primary_chapter` in ({0}))""".format(chapters_str)
        
    # Users can only see their own member record
    return f"""(`tabMember`.`user` = '{user}')"""
    
def get_membership_permission_query(user):
    """Permission query for Membership doctype"""
    if not user:
        user = frappe.session.user
        
    # Check user roles
    user_roles = frappe.get_roles(user)
    
    # System Managers, Membership Managers, Association Managers, and Verenigingen Managers can access all memberships
    if any(role in user_roles for role in ["System Manager", "Membership Manager", "Association Manager", "Verenigingen Manager"]):
        return ""  # No restrictions
        
    # Membership Users can view all memberships
    if "Membership User" in user_roles:
        return ""  # No restrictions for viewing
    
    # Board members can view chapter members' memberships
    member = frappe.db.get_value("Member", {"user": user}, "name")
    if member:
        # Get chapters where user is a board member with financial permissions
        board_chapters_with_permission = []
        
        board_roles = frappe.get_all(
            "Chapter Board Member",
            filters={"member": member, "is_active": 1},
            fields=["parent as chapter", "chapter_role"]
        )
        
        for role in board_roles:
            role_doc = frappe.get_doc("Chapter Role", role.chapter_role)
            if role_doc.permissions_level in ["Financial", "Admin"]:
                board_chapters_with_permission.append(role.chapter)
        
        if board_chapters_with_permission:
            # Get list of members from these chapters
            chapter_members = []
            
            for chapter in board_chapters_with_permission:
                members = frappe.get_all(
                    "Member",
                    filters={"primary_chapter": chapter},
                    fields=["name"]
                )
                
                chapter_members.extend([m.name for m in members])
            
            if chapter_members:
                member_list = ["'{0}'".format(m) for m in chapter_members]
                members_str = ", ".join(member_list)
                
                # Board members can see memberships of their chapter members
                return """(`tabMembership`.`member` in ({0}))""".format(members_str)
        
        # Users can only see memberships linked to their member record
        return f"""(`tabMembership`.`member` = '{member}')"""
    else:
        # If no member record is found, don't allow access to any memberships
        return "1=0"
