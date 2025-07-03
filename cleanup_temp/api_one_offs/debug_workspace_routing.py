import frappe

@frappe.whitelist()
def check_doctype_workspace_routing():
    """Debug why E-Boekhouden Migration shows under SEPA Management"""
    
    results = {}
    
    # 1. Check the doctype module
    doctype_info = frappe.db.get_value(
        "DocType", 
        "E-Boekhouden Migration",
        ["module", "name"],
        as_dict=True
    )
    results['doctype_module'] = doctype_info
    
    # 2. Check all workspaces that have this module
    workspaces_in_module = frappe.db.sql("""
        SELECT name, label, title, module, sequence_id
        FROM `tabWorkspace`
        WHERE module = %s
        ORDER BY sequence_id, name
    """, doctype_info.get('module'), as_dict=True)
    results['workspaces_in_module'] = workspaces_in_module
    
    # 3. Check for any workspace-doctype mappings
    workspace_links = frappe.db.sql("""
        SELECT w.name as workspace, w.module, wl.link_to
        FROM `tabWorkspace` w
        JOIN `tabWorkspace Link` wl ON wl.parent = w.name
        WHERE wl.link_to = 'E-Boekhouden Migration'
    """, as_dict=True)
    results['workspace_links'] = workspace_links
    
    # 4. Check desk settings for default workspace
    try:
        from frappe.desk.desktop import get_workspace_sidebar_items
        sidebar_items = get_workspace_sidebar_items()
        results['sidebar_available'] = True
        
        # Find which workspace shows when accessing the module
        for item in sidebar_items.get('pages', []):
            if item.get('module') == 'Verenigingen':
                results['module_workspace_info'] = item
                break
    except:
        results['sidebar_available'] = False
    
    # 5. Check if there's a preferred workspace for the module
    preferred_workspace = frappe.db.sql("""
        SELECT name, sequence_id
        FROM `tabWorkspace`
        WHERE module = 'Verenigingen'
        AND is_hidden = 0
        ORDER BY sequence_id ASC
        LIMIT 1
    """, as_dict=True)
    results['preferred_workspace'] = preferred_workspace[0] if preferred_workspace else None
    
    # 6. Check user's default workspace
    user_default = frappe.db.get_value(
        "DefaultValue",
        {"parent": frappe.session.user, "defkey": "default_workspace"},
        "defvalue"
    )
    results['user_default_workspace'] = user_default
    
    # 7. Check if SEPA Management has lower sequence_id
    sepa_info = frappe.db.get_value(
        "Workspace",
        "SEPA Management",
        ["sequence_id", "module"],
        as_dict=True
    )
    results['sepa_workspace_info'] = sepa_info
    
    eb_info = frappe.db.get_value(
        "Workspace",
        "E-Boekhouden",
        ["sequence_id", "module"],
        as_dict=True
    )
    results['eboekhouden_workspace_info'] = eb_info
    
    return results

@frappe.whitelist()
def fix_workspace_sequence():
    """Fix workspace sequence to ensure E-Boekhouden appears correctly"""
    
    # Give E-Boekhouden a lower sequence number than SEPA Management
    frappe.db.set_value("Workspace", "E-Boekhouden", "sequence_id", 20.0)
    frappe.db.set_value("Workspace", "SEPA Management", "sequence_id", 25.0)
    frappe.db.set_value("Workspace", "Verenigingen", "sequence_id", 15.0)
    
    frappe.db.commit()
    frappe.clear_cache()
    
    return {
        "success": True,
        "message": "Workspace sequence updated. E-Boekhouden should now appear before SEPA Management."
    }