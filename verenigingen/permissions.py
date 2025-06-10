import frappe
from frappe import _

@frappe.whitelist()
def can_terminate_member_api(member_name):
    """Whitelisted API wrapper for can_terminate_member"""
    return can_terminate_member(member_name)

@frappe.whitelist() 
def can_access_termination_functions_api():
    """Whitelisted API wrapper for can_access_termination_functions"""
    return can_access_termination_functions()

def has_member_permission(doc, user=None, permission_type=None):
    """Direct permission check for Member doctype"""
    if not user:
        user = frappe.session.user
        
    # Log for debugging
    frappe.logger().debug(f"Checking Member permissions for user {user} with roles {frappe.get_roles(user)}")
    
    # Admin roles always have access
    admin_roles = ["System Manager", "Membership Manager", "Verenigingen Manager"]
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
    admin_roles = ["System Manager", "Membership Manager", "Verenigingen Manager"]
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

    admin_roles = ["System Manager", "Membership Manager", "Verenigingen Manager"]
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
    target_member_chapters = frappe.get_all(
        "Chapter Member",
        filters={"member": target_member.name, "enabled": 1},
        fields=["parent"],
        order_by="chapter_join_date desc",
        limit=1,
        ignore_permissions=True
    )
    if target_member_chapters:
        chapter = frappe.get_doc("Chapter", target_member_chapters[0].parent)
        return chapter.can_view_member_payments(viewer_member)
        
    # Not permitted
    return False

def check_member_payment_access(member_name, user=None):
    """Check if a user can access payment information for a member"""
    if not user:
        user = frappe.session.user
        
    # Admins can access all
    if ("System Manager" in frappe.get_roles(user) or 
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
        
    # Get member's primary chapter from Chapter Member table
    member_chapters = frappe.get_all(
        "Chapter Member",
        filters={"member": member.name, "enabled": 1},
        fields=["parent"],
        order_by="chapter_join_date desc",
        limit=1
    )
    if member_chapters:
        chapter = frappe.get_doc("Chapter", member_chapters[0].parent)
        return chapter.can_view_member_payments(viewer_member)
        
    return False

def can_terminate_member(member_name, user=None):
    """Check if user can terminate a specific member"""
    if not user:
        user = frappe.session.user
        
    # System managers and Association managers always can
    admin_roles = ["System Manager", "Verenigingen Manager"]
    user_roles = frappe.get_roles(user)
    if any(role in user_roles for role in admin_roles):
        frappe.logger().debug(f"User {user} has admin role, granting termination access")
        return True
    
    # Get the member being terminated
    try:
        member_doc = frappe.get_doc("Member", member_name)
    except Exception:
        frappe.logger().error(f"Member {member_name} not found")
        return False
    
    # Get the user making the request as a member
    requesting_member = frappe.db.get_value("Member", {"user": user}, "name")
    if not requesting_member:
        frappe.logger().debug(f"User {user} is not a member")
        return False
    
    # Check if user is a board member of the member's chapter
    member_chapters = frappe.get_all(
        "Chapter Member",
        filters={"member": member_doc.name, "enabled": 1},
        fields=["parent"],
        order_by="chapter_join_date desc",
        limit=1,
        ignore_permissions=True
    )
    if member_chapters:
        try:
            chapter_doc = frappe.get_doc("Chapter", member_chapters[0].parent)
            if chapter_doc.user_has_board_access(requesting_member):
                frappe.logger().debug(f"User {user} has board access in member's chapter {member_chapters[0].parent}")
                return True
        except Exception as e:
            frappe.logger().error(f"Error checking chapter board access: {str(e)}")
    
    # Check if user is a board member of the national chapter (if configured)
    try:
        settings = frappe.get_single("Verenigingen Settings")
        if hasattr(settings, 'national_chapter') and settings.national_chapter:
            national_chapter_doc = frappe.get_doc("Chapter", settings.national_chapter)
            if national_chapter_doc.user_has_board_access(requesting_member):
                frappe.logger().debug(f"User {user} has board access in national chapter")
                return True
    except Exception as e:
        frappe.logger().debug(f"No national chapter configured or error checking: {str(e)}")
    
    frappe.logger().debug(f"User {user} does not have termination permission for member {member_name}")
    return False

def can_access_termination_functions(user=None):
    """Check if user can access general termination functions"""
    if not user:
        user = frappe.session.user
        
    # System managers and Association managers always can
    admin_roles = ["System Manager", "Verenigingen Manager"]
    user_roles = frappe.get_roles(user)
    if any(role in user_roles for role in admin_roles):
        return True
    
    # Check if user is a board member of any chapter
    requesting_member = frappe.db.get_value("Member", {"user": user}, "name")
    if not requesting_member:
        return False
    
    # Check for active board positions
    volunteer_records = frappe.get_all("Volunteer", filters={"member": requesting_member}, fields=["name"])
    
    for volunteer_record in volunteer_records:
        board_positions = frappe.get_all(
            "Chapter Board Member",
            filters={
                "volunteer": volunteer_record.name,
                "is_active": 1
            },
            fields=["name"]
        )
        
        if board_positions:
            return True
    
    return False

def get_chapter_member_permission_query(user):
    """Permission query for Chapter Member doctype"""
    if not user:
        user = frappe.session.user
        
    # Admin roles get full access
    admin_roles = ["System Manager", "Membership Manager", "Verenigingen Manager"]
    if any(role in frappe.get_roles(user) for role in admin_roles):
        return ""
    
    # Allow users to see Chapter Member records for:
    # 1. Their own member record
    # 2. Chapters where they have board access
    requesting_member = frappe.db.get_value("Member", {"user": user}, "name")
    if not requesting_member:
        return "1=0"  # No access if not a member
    
    # Get chapters where user has board access
    user_chapters = []
    volunteer_records = frappe.get_all("Volunteer", filters={"member": requesting_member}, fields=["name"])
    
    for volunteer_record in volunteer_records:
        board_positions = frappe.get_all(
            "Chapter Board Member",
            filters={
                "volunteer": volunteer_record.name,
                "is_active": 1
            },
            fields=["parent"]
        )
        
        for position in board_positions:
            if position.parent not in user_chapters:
                user_chapters.append(position.parent)
    
    # Build permission filter
    conditions = [f"`tabChapter Member`.member = '{requesting_member}'"]  # Own records
    
    if user_chapters:
        chapter_conditions = " OR ".join([f"`tabChapter Member`.parent = '{chapter}'" for chapter in user_chapters])
        conditions.append(f"({chapter_conditions})")  # Board access chapters
    
    return f"({' OR '.join(conditions)})"

def get_termination_permission_query(user):
    """Permission query for Membership Termination Request doctype"""
    if not user:
        user = frappe.session.user

    # Admin roles get full access
    admin_roles = ["System Manager", "Verenigingen Manager"]
    if any(role in frappe.get_roles(user) for role in admin_roles):
        return ""
    
    # Board members get filtered access based on their chapters
    requesting_member = frappe.db.get_value("Member", {"user": user}, "name")
    if not requesting_member:
        return "1=0"  # No access if not a member
    
    # Get chapters where user has board access
    user_chapters = []
    volunteer_records = frappe.get_all("Volunteer", filters={"member": requesting_member}, fields=["name"])
    
    for volunteer_record in volunteer_records:
        board_positions = frappe.get_all(
            "Chapter Board Member",
            filters={
                "volunteer": volunteer_record.name,
                "is_active": 1
            },
            fields=["parent"]
        )
        
        for position in board_positions:
            if position.parent not in user_chapters:
                user_chapters.append(position.parent)
    
    # Add national chapter if configured
    try:
        settings = frappe.get_single("Verenigingen Settings")
        if hasattr(settings, 'national_chapter') and settings.national_chapter:
            if settings.national_chapter not in user_chapters:
                user_chapters.append(settings.national_chapter)
    except Exception:
        pass
    
    if not user_chapters:
        return "1=0"  # No access if not on any board
    
    # Return filter to only show termination requests for members in their chapters
    chapter_filter = " OR ".join([f"cm.parent = '{chapter}'" for chapter in user_chapters])
    return f"""EXISTS (
        SELECT 1 FROM `tabMember` m
        JOIN `tabChapter Member` cm ON cm.member = m.name 
        WHERE m.name = `tabMembership Termination Request`.member 
        AND cm.enabled = 1 
        AND ({chapter_filter})
    )"""
