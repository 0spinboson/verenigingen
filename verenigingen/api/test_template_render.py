"""
Test template rendering for chapter row
"""

import frappe

@frappe.whitelist() 
def test_template_render():
    """Test rendering the chapter row template"""
    try:
        # Get chapter data
        chapter = frappe.get_doc("Chapter", "Zeist")
        
        # Create a minimal template context similar to what WebsiteGenerator provides
        context = {
            "doc": chapter,
            "frappe": frappe,
            "html2text": frappe.utils.html2text
        }
        
        # Try to render a simplified version of our template logic
        template_test = {
            "success": True,
            "chapter_name": chapter.name,
            "chapter_route": chapter.route,
            "published": chapter.published
        }
        
        # Test member count calculation (simulating Jinja filter)
        if chapter.members:
            enabled_members = [m for m in chapter.members if getattr(m, 'enabled', 0) == 1]
            template_test["member_count"] = len(enabled_members)
            template_test["total_members"] = len(chapter.members)
        else:
            template_test["member_count"] = 0
            template_test["total_members"] = 0
        
        # Test board count calculation (simulating Jinja filter) 
        if chapter.board_members:
            active_board = [b for b in chapter.board_members if getattr(b, 'is_active', 0) == 1]
            template_test["board_count"] = len(active_board)
            template_test["total_board"] = len(chapter.board_members)
        else:
            template_test["board_count"] = 0
            template_test["total_board"] = 0
        
        # Test chapter head
        if chapter.chapter_head:
            try:
                head_doc = frappe.get_doc("Member", chapter.chapter_head)
                template_test["chapter_head_name"] = head_doc.full_name
                template_test["chapter_head_found"] = True
            except:
                template_test["chapter_head_name"] = "Error loading"
                template_test["chapter_head_found"] = False
        else:
            template_test["chapter_head_name"] = "Not Assigned"
            template_test["chapter_head_found"] = False
        
        # Test introduction
        if chapter.introduction:
            intro_text = frappe.utils.html2text(chapter.introduction)
            template_test["introduction_preview"] = intro_text[:180] + "..." if len(intro_text) > 180 else intro_text
            template_test["has_introduction"] = True
        else:
            template_test["introduction_preview"] = ""
            template_test["has_introduction"] = False
        
        return template_test
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }