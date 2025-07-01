"""
Check member chapter relationships
"""

import frappe
from frappe import _

@frappe.whitelist()
def check_member_chapters():
    """Check member chapter relationships"""
    
    # Get some members with chapters
    members_with_chapters = frappe.db.sql("""
        SELECT 
            m.name,
            m.email,
            cm.parent as chapter,
            cm.enabled
        FROM `tabMember` m
        JOIN `tabChapter Member` cm ON cm.member = m.name
        LIMIT 10
    """, as_dict=True)
    
    # Get count of enabled chapter members
    enabled_count = frappe.db.sql("""
        SELECT COUNT(*) as count
        FROM `tabChapter Member`
        WHERE enabled = 1
    """, as_dict=True)[0].count
    
    # Get a sample user with chapters
    sample_user = None
    if members_with_chapters:
        sample_email = members_with_chapters[0].email
        if sample_email:
            sample_user = {
                "email": sample_email,
                "chapters": frappe.db.sql("""
                    SELECT cm.parent, cm.enabled
                    FROM `tabChapter Member` cm
                    JOIN `tabMember` m ON m.name = cm.member
                    WHERE m.email = %s
                """, sample_email, as_dict=True)
            }
    
    return {
        "members_with_chapters": members_with_chapters,
        "enabled_chapter_members": enabled_count,
        "sample_user": sample_user
    }

@frappe.whitelist()
def create_test_chapter_member():
    """Create a test chapter member for testing"""
    
    if "System Manager" not in frappe.get_roles():
        return {"error": "Need System Manager role"}
    
    # Get first member and chapter
    member = frappe.db.get_value("Member", filters={}, fieldname="name")
    chapter = frappe.db.get_value("Chapter", {"published": 1}, fieldname="name")
    
    if not member or not chapter:
        return {"error": "No member or published chapter found"}
    
    # Check if already exists
    existing = frappe.db.exists("Chapter Member", {"member": member, "parent": chapter})
    
    if existing:
        # Update to ensure it's enabled
        frappe.db.set_value("Chapter Member", existing, "enabled", 1)
        frappe.db.commit()
        return {"message": f"Updated existing Chapter Member {existing} to enabled"}
    
    # Create new chapter member
    chapter_doc = frappe.get_doc("Chapter", chapter)
    chapter_doc.append("members", {
        "member": member,
        "enabled": 1,
        "joined_date": frappe.utils.today()
    })
    chapter_doc.save()
    frappe.db.commit()
    
    return {
        "message": f"Created Chapter Member for {member} in {chapter}",
        "member": member,
        "chapter": chapter
    }