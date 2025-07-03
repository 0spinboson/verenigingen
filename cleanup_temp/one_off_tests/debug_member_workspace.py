import frappe

@frappe.whitelist()
def debug_member_workspace():
    """Debug why Member doctype might be showing under SEPA Management workspace"""
    
    results = {}
    
    # 1. Check Member doctype module
    member_module = frappe.db.get_value("DocType", "Member", "module")
    results['member_module'] = member_module
    
    # 2. Check workspace links containing Member
    workspace_links = frappe.db.sql("""
        SELECT 
            w.name as workspace,
            w.module,
            w.label,
            w.sequence_id,
            wl.label as link_label,
            wl.link_to
        FROM `tabWorkspace` w
        JOIN `tabWorkspace Link` wl ON wl.parent = w.name
        WHERE wl.link_to = 'Member'
        ORDER BY w.sequence_id, w.name
    """, as_dict=True)
    results['workspace_links'] = workspace_links
    
    # 3. Check if there's any custom field or property
    custom_fields = frappe.db.sql("""
        SELECT fieldname, label, options
        FROM `tabCustom Field`
        WHERE dt = 'Member' AND fieldname LIKE '%workspace%'
    """, as_dict=True)
    results['custom_fields'] = custom_fields
    
    # 4. Check Property Setter
    property_setters = frappe.db.sql("""
        SELECT property, value
        FROM `tabProperty Setter`
        WHERE doc_type = 'Member' AND property LIKE '%workspace%'
    """, as_dict=True)
    results['property_setters'] = property_setters
    
    # 5. Check workspace sequence
    workspaces = frappe.db.sql("""
        SELECT name, label, module, sequence_id
        FROM `tabWorkspace`
        WHERE module = 'Verenigingen'
        ORDER BY sequence_id
    """, as_dict=True)
    results['verenigingen_workspaces'] = workspaces
    
    return results