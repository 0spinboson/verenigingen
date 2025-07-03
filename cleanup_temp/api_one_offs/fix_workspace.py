import frappe

@frappe.whitelist()
def fix_null_workspace_titles():
    """Fix workspaces with null titles that are causing menu issues"""
    
    # Update E-Boekhouden workspace to have a title
    frappe.db.sql("""
        UPDATE `tabWorkspace` 
        SET title = 'E-Boekhouden' 
        WHERE name = 'E-Boekhouden' 
        AND (title IS NULL OR title = '')
    """)
    
    # Check if there are any other workspaces with null titles
    other_null_titles = frappe.db.sql("""
        SELECT name 
        FROM `tabWorkspace` 
        WHERE title IS NULL OR title = ''
    """, as_dict=True)
    
    # Fix any other null titles by using the name as title
    for ws in other_null_titles:
        frappe.db.sql("""
            UPDATE `tabWorkspace` 
            SET title = %s 
            WHERE name = %s
        """, (ws.name, ws.name))
    
    frappe.db.commit()
    
    # Clear cache to ensure changes take effect
    frappe.clear_cache()
    
    return {
        "success": True,
        "message": f"Fixed workspace titles. Updated {len(other_null_titles)} workspaces.",
        "fixed_workspaces": [ws.name for ws in other_null_titles]
    }