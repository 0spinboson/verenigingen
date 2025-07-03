import frappe

@frappe.whitelist()
def debug_workspace_doctype_mapping():
    """Debug how doctypes are mapped to workspaces"""
    
    # Get all workspace links
    workspace_links = frappe.db.sql("""
        SELECT 
            w.name as workspace,
            wl.link_to,
            wl.link_name,
            wl.link_type
        FROM `tabWorkspace` w
        JOIN `tabWorkspace Link` wl ON wl.parent = w.name
        WHERE w.module = 'Verenigingen'
        AND wl.link_type = 'DocType'
        ORDER BY w.name, wl.idx
    """, as_dict=True)
    
    # Group by workspace
    workspace_doctypes = {}
    for link in workspace_links:
        workspace = link['workspace']
        if workspace not in workspace_doctypes:
            workspace_doctypes[workspace] = []
        
        doctype = link['link_to'] or link['link_name']
        if doctype:
            workspace_doctypes[workspace].append(doctype)
    
    # Check which workspace Member belongs to
    member_workspaces = []
    for workspace, doctypes in workspace_doctypes.items():
        if 'Member' in doctypes:
            member_workspaces.append(workspace)
    
    return {
        "workspace_doctypes": workspace_doctypes,
        "member_found_in": member_workspaces,
        "total_links": len(workspace_links)
    }

if __name__ == "__main__":
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    import json
    print(json.dumps(debug_workspace_doctype_mapping(), indent=2))
    frappe.destroy()