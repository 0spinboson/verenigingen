"""
Test direct chapter join functionality
"""

import frappe

@frappe.whitelist()
def test_direct_chapter_join(chapter_name="Zeist", test_user="fjdh@leden.socialisten.org"):
    """Test direct chapter join without template context"""
    try:
        original_user = frappe.session.user
        if test_user:
            frappe.session.user = test_user
        
        try:
            # Check if user is logged in
            if frappe.session.user == "Guest":
                return {"success": False, "error": "User not logged in"}
            
            # Get member record
            member = frappe.db.get_value("Member", {"email": frappe.session.user})
            if not member:
                return {"success": False, "error": "No member record found"}
            
            # Get chapter document
            chapter = frappe.get_doc("Chapter", chapter_name)
            
            # Check if already a member
            existing_membership = frappe.db.exists("Chapter Member", {
                "member": member,
                "parent": chapter_name
            })
            
            if existing_membership:
                return {"success": False, "error": "Already a member", "already_member": True}
            
            # Test adding member to chapter
            before_member_count = len(chapter.members)
            
            # Add to members child table
            chapter.append("members", {
                "member": member,
                "chapter_join_date": frappe.utils.today(),
                "enabled": 1
            })
            
            # Test save (but don't commit) - ignore permissions for testing
            chapter.save(ignore_permissions=True)
            
            after_member_count = len(chapter.members)
            
            # Don't commit - this is just a test
            frappe.db.rollback()
            
            return {
                "success": True,
                "user": frappe.session.user,
                "member": member,
                "chapter": chapter_name,
                "before_member_count": before_member_count,
                "after_member_count": after_member_count,
                "member_added": after_member_count > before_member_count
            }
            
        finally:
            frappe.session.user = original_user
        
    except Exception as e:
        frappe.session.user = original_user
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }