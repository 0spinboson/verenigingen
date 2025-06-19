"""
Test Jinja filter functionality for chapter template
"""

import frappe

@frappe.whitelist()
def test_jinja_filter():
    """Test if Jinja filters work correctly for chapter data"""
    try:
        # Get Zeist chapter
        chapter = frappe.get_doc("Chapter", "Zeist")
        
        # Test manual counting vs Jinja filter equivalent
        manual_member_count = len([m for m in chapter.members if m.enabled == 1]) if chapter.members else 0
        manual_board_count = len([b for b in chapter.board_members if b.is_active == 1]) if chapter.board_members else 0
        
        # Simulate Jinja template logic
        members_data = []
        if chapter.members:
            for member in chapter.members:
                members_data.append({
                    "member": member.member,
                    "enabled": member.enabled,
                    "chapter_join_date": member.chapter_join_date
                })
        
        board_data = []
        if chapter.board_members:
            for board_member in chapter.board_members:
                board_data.append({
                    "volunteer": board_member.volunteer,
                    "is_active": board_member.is_active,
                    "chapter_role": board_member.chapter_role
                })
        
        return {
            "success": True,
            "manual_member_count": manual_member_count,
            "manual_board_count": manual_board_count,
            "members_data": members_data,
            "board_data": board_data,
            "chapter_name": chapter.name,
            "chapter_head": chapter.chapter_head,
            "has_introduction": bool(chapter.introduction),
            "published": chapter.published
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }