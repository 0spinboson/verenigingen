"""
Simple test for chapter join functionality
"""

import frappe

@frappe.whitelist()
def test_simple_chapter_context(chapter_name="Zeist"):
    """Simple test of chapter join context"""
    try:
        # Test getting chapter
        chapter = frappe.get_doc("Chapter", chapter_name)
        
        # Test member lookup for current user
        member = frappe.db.get_value("Member", {"email": frappe.session.user})
        
        # Test chapter membership check
        already_member = False
        if member:
            chapter_membership = frappe.db.exists("Chapter Member", {
                "member": member,
                "parent": chapter_name
            })
            already_member = bool(chapter_membership)
        
        return {
            "success": True,
            "chapter_found": True,
            "chapter_name": chapter.name,
            "chapter_title": chapter.name,
            "user": frappe.session.user,
            "member": member,
            "already_member": already_member
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }