"""
Debug current user chapter visibility
"""

import frappe
from frappe import _

@frappe.whitelist()
def debug_current_user():
    """Debug why current user can't see chapters"""
    
    result = {
        "current_user": frappe.session.user,
        "is_guest": frappe.session.user == "Guest"
    }
    
    # Check if user has Member record
    member = frappe.db.get_value("Member", {"email": frappe.session.user}, "name")
    result["has_member_record"] = bool(member)
    result["member_name"] = member
    
    if member:
        # Get chapter memberships
        chapter_members = frappe.db.sql("""
            SELECT 
                cm.name as record_id,
                cm.parent as chapter,
                cm.enabled,
                cm.joined_date
            FROM `tabChapter Member` cm
            WHERE cm.member = %s
        """, member, as_dict=True)
        
        result["chapter_member_records"] = chapter_members
        result["enabled_chapters"] = [cm for cm in chapter_members if cm.enabled]
    
    # Check what chapters exist
    all_chapters = frappe.db.sql("""
        SELECT 
            name,
            published
        FROM `tabChapter`
    """, as_dict=True)
    
    result["total_chapters"] = len(all_chapters)
    result["published_chapters"] = len([c for c in all_chapters if c.published])
    
    # Test the exact query used in chapter list
    if member:
        user_chapters_pluck = frappe.get_all(
            "Chapter Member",
            filters={"member": member, "enabled": 1},
            pluck="parent"
        )
        result["user_chapters_from_pluck"] = user_chapters_pluck
    
    return result

@frappe.whitelist()
def create_member_for_admin():
    """Create a Member record for Administrator"""
    
    if frappe.session.user != "Administrator":
        return {"error": "This function is only for Administrator"}
    
    # Check if already exists
    existing = frappe.db.get_value("Member", {"email": "Administrator"}, "name")
    if existing:
        return {"message": f"Member record already exists: {existing}"}
    
    # Create member
    member = frappe.get_doc({
        "doctype": "Member",
        "email": "Administrator",
        "full_name": "Administrator",
        "first_name": "Admin",
        "last_name": "User",
        "membership_type": "Regular"
    })
    member.insert(ignore_permissions=True)
    frappe.db.commit()
    
    return {"message": f"Created member: {member.name}"}

@frappe.whitelist()
def simulate_user_view(test_email="fjdh@disroot.org"):
    """Simulate what a specific user would see"""
    
    # Get member
    member = frappe.db.get_value("Member", {"email": test_email}, "name")
    
    if not member:
        return {"error": f"No member record for {test_email}"}
    
    # Simulate get_list_context
    user_chapters = frappe.get_all(
        "Chapter Member",
        filters={"member": member, "enabled": 1},
        pluck="parent"
    )
    
    # Get all chapters (this is what shows in the list)
    all_chapters = frappe.db.sql("""
        SELECT 
            name,
            published,
            introduction
        FROM `tabChapter`
        WHERE published = 1
    """, as_dict=True)
    
    return {
        "test_user": test_email,
        "member": member,
        "user_chapters": user_chapters,
        "all_chapters_count": len(all_chapters),
        "my_chapters_count": len(user_chapters),
        "available_chapters_count": len([c for c in all_chapters if c.name not in user_chapters]),
        "sample_chapters": all_chapters[:3]
    }