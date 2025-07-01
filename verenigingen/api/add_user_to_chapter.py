"""
Add current user to a chapter
"""

import frappe
from frappe import _

@frappe.whitelist()
def add_current_user_to_chapter(chapter_name=None):
    """Add current user to a chapter"""
    
    if frappe.session.user == "Guest":
        return {"error": "Please login first"}
    
    # Get member record
    member = frappe.db.get_value("Member", {"email": frappe.session.user}, "name")
    
    if not member:
        return {"error": f"No member record found for {frappe.session.user}"}
    
    # Get a chapter if not specified
    if not chapter_name:
        chapter_name = frappe.db.get_value("Chapter", {"published": 1}, "name")
    
    if not chapter_name:
        return {"error": "No published chapter found"}
    
    # Check if already member
    existing = frappe.db.exists("Chapter Member", {
        "member": member,
        "parent": chapter_name
    })
    
    if existing:
        # Ensure it's enabled
        frappe.db.set_value("Chapter Member", existing, "enabled", 1)
        frappe.db.commit()
        return {
            "message": f"You are already a member of {chapter_name} (ensured enabled)",
            "chapter": chapter_name
        }
    
    # Add member to chapter
    try:
        chapter_doc = frappe.get_doc("Chapter", chapter_name)
        chapter_doc.append("members", {
            "member": member,
            "enabled": 1,
            "joined_date": frappe.utils.today()
        })
        chapter_doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "message": f"Successfully added to {chapter_name}",
            "chapter": chapter_name,
            "member": member
        }
    except Exception as e:
        return {"error": str(e)}

@frappe.whitelist()
def list_available_chapters():
    """List chapters user can join"""
    
    if frappe.session.user == "Guest":
        return {"error": "Please login first"}
    
    member = frappe.db.get_value("Member", {"email": frappe.session.user}, "name")
    
    if not member:
        return {"error": "No member record found"}
    
    # Get user's current chapters
    my_chapters = frappe.db.sql("""
        SELECT parent
        FROM `tabChapter Member`
        WHERE member = %s AND enabled = 1
    """, member, pluck="parent")
    
    # Get all published chapters
    all_chapters = frappe.db.sql("""
        SELECT name
        FROM `tabChapter`
        WHERE published = 1
    """, pluck="name")
    
    # Available chapters are those not in my_chapters
    available = [c for c in all_chapters if c not in my_chapters]
    
    return {
        "my_chapters": my_chapters,
        "available_chapters": available,
        "total_chapters": len(all_chapters)
    }