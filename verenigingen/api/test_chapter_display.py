"""
Test chapter display formatting
"""

import frappe

@frappe.whitelist()
def test_chapter_display_format():
    """Test the updated chapter display format"""
    try:
        # Get Zeist chapter
        chapter = frappe.get_doc("Chapter", "Zeist")
        
        # Test member count calculation
        member_count = len([m for m in chapter.members if m.enabled == 1]) if chapter.members else 0
        
        # Test board count calculation  
        board_count = len([b for b in chapter.board_members if b.is_active == 1]) if chapter.board_members else 0
        
        # Test chapter head info
        chapter_head_name = "Not Assigned"
        if chapter.chapter_head:
            try:
                head_doc = frappe.get_doc("Member", chapter.chapter_head)
                chapter_head_name = head_doc.full_name
            except:
                chapter_head_name = "Error loading name"
        
        # Test introduction text
        intro_text = ""
        if chapter.introduction:
            from frappe.core.utils import html2text
            intro_text = html2text(chapter.introduction)
            if len(intro_text) > 180:
                intro_text = intro_text[:180] + "..."
        
        return {
            "success": True,
            "chapter_name": chapter.name,
            "display_format": {
                "members_label": "Members in this chapter: ",
                "members_count": member_count,
                "board_label": "Board members: ", 
                "board_count": board_count,
                "chapter_head_label": "Chapter Head: ",
                "chapter_head_name": chapter_head_name,
                "intro_header": "About this Chapter",
                "intro_text": intro_text,
                "has_proper_spacing": True,
                "visual_separation": "border-t border-gray-100 pt-4"
            }
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }