import frappe

@frappe.whitelist()
def check_workspace_issues():
    """Debug function to check for workspace issues causing menu problems"""
    
    # Get all workspace links that might have null values
    problematic_links = frappe.db.sql("""
        SELECT 
            parent as workspace_name, 
            label, 
            link_to,
            link_type,
            type,
            idx
        FROM `tabWorkspace Link`
        WHERE (label IS NULL OR label = '' OR link_to IS NULL OR link_to = '')
        ORDER BY parent, idx
    """, as_dict=True)
    
    # Get workspaces with potential issues
    workspaces_with_issues = frappe.db.sql("""
        SELECT 
            name,
            title,
            module
        FROM `tabWorkspace`
        WHERE title IS NULL OR title = ''
    """, as_dict=True)
    
    # Check for verenigingen-related workspaces
    verenigingen_workspaces = frappe.db.sql("""
        SELECT 
            name,
            title,
            module
        FROM `tabWorkspace`
        WHERE name LIKE '%verenigingen%' 
           OR module LIKE '%verenigingen%'
           OR module = 'Verenigingen'
    """, as_dict=True)
    
    return {
        "problematic_links": problematic_links,
        "workspaces_with_issues": workspaces_with_issues,
        "verenigingen_workspaces": verenigingen_workspaces,
        "total_workspaces": frappe.db.count("Workspace"),
        "total_workspace_links": frappe.db.count("Workspace Link")
    }