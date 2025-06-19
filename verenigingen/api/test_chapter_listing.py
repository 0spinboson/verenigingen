"""
Test chapter listing layout
"""

import frappe

@frappe.whitelist()
def test_chapter_listing():
    """Test the chapter listing page context and data"""
    try:
        # Get chapters with their data for testing layout
        chapters = frappe.get_all("Chapter", 
            filters={"published": 1},
            fields=["name", "chapter_head", "introduction", "route"],
            limit=3)
        
        result = {"success": True, "chapters": []}
        
        for chapter in chapters:
            # Get full chapter document to test template data
            chapter_doc = frappe.get_doc("Chapter", chapter.name)
            
            # Calculate member count (enabled)
            member_count = len([m for m in chapter_doc.members if m.enabled == 1]) if chapter_doc.members else 0
            
            # Calculate board member count (active)
            board_count = len([b for b in chapter_doc.board_members if b.is_active == 1]) if chapter_doc.board_members else 0
            
            # Get chapter head info
            chapter_head_name = None
            if chapter_doc.chapter_head:
                try:
                    head_doc = frappe.get_doc("Member", chapter_doc.chapter_head)
                    chapter_head_name = head_doc.full_name
                except:
                    chapter_head_name = "Error loading name"
            
            result["chapters"].append({
                "name": chapter_doc.name,
                "route": chapter_doc.route,
                "member_count": member_count,
                "board_count": board_count,
                "chapter_head": chapter_head_name or "Not Assigned",
                "introduction_length": len(chapter_doc.introduction or ""),
                "has_introduction": bool(chapter_doc.introduction),
                "members_data_available": bool(chapter_doc.members),
                "board_data_available": bool(chapter_doc.board_members)
            })
        
        return result
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }