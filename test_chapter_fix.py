import frappe

@frappe.whitelist()
def fix_jantje_chapter_display():
    """Force update Jantje's chapter display"""
    member_name = "Assoc-Member-2025-06-0005"
    
    # Get member document
    member = frappe.get_doc("Member", member_name)
    
    # Force update the chapter display
    member._chapter_assignment_in_progress = True
    member.update_current_chapter_display()
    
    # Save the member document to persist the changes
    member.save(ignore_permissions=True)
    
    return {
        "success": True,
        "message": "Updated chapter display for Jantje",
        "current_chapter_display": getattr(member, 'current_chapter_display', 'Not set')
    }

@frappe.whitelist()
def debug_chapter_query():
    """Debug the chapter query for Jantje"""
    member_name = "Assoc-Member-2025-06-0005"
    
    # Test the SQL query directly
    chapters_data = frappe.db.sql("""
        SELECT 
            cm.parent as chapter,
            cm.chapter_join_date,
            c.region,
            cbm.volunteer as board_volunteer,
            cbm.is_active as is_board_member,
            cbm.chapter_role
        FROM `tabChapter Member` cm
        LEFT JOIN `tabChapter` c ON cm.parent = c.name
        LEFT JOIN `tabVolunteer` v ON v.member = %s
        LEFT JOIN `tabChapter Board Member` cbm ON cbm.parent = cm.parent AND cbm.volunteer = v.name AND cbm.is_active = 1
        WHERE cm.member = %s AND cm.enabled = 1
        ORDER BY cm.chapter_join_date DESC
    """, (member_name, member_name), as_dict=True)
    
    return {
        "query_result": chapters_data
    }

if __name__ == "__main__":
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    result = debug_chapter_query()
    print(result)