#!/usr/bin/env python
import frappe

def check_member_workspace_issue():
    """Debug why Member doctype might be showing under SEPA Management workspace"""
    
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    
    print("\n=== CHECKING MEMBER DOCTYPE CONFIGURATION ===")
    
    # 1. Check Member doctype module
    member_module = frappe.db.get_value("DocType", "Member", "module")
    print(f"Member DocType module: {member_module}")
    
    # 2. Check workspace links containing Member
    print("\n=== WORKSPACE LINKS CONTAINING MEMBER ===")
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
    
    for link in workspace_links:
        print(f"  Workspace: {link['workspace']} (module: {link['module']}, seq: {link['sequence_id']})")
        print(f"    Link Label: {link['link_label']}")
    
    # 3. Check if there's any custom field or property
    print("\n=== CHECKING CUSTOM FIELDS ===")
    custom_fields = frappe.db.sql("""
        SELECT fieldname, label, options
        FROM `tabCustom Field`
        WHERE dt = 'Member' AND fieldname LIKE '%workspace%'
    """, as_dict=True)
    
    if custom_fields:
        for cf in custom_fields:
            print(f"  Custom Field: {cf['fieldname']} - {cf['label']} ({cf['options']})")
    else:
        print("  No custom fields related to workspace found")
    
    # 4. Check Property Setter
    print("\n=== CHECKING PROPERTY SETTERS ===")
    property_setters = frappe.db.sql("""
        SELECT property, value
        FROM `tabProperty Setter`
        WHERE doc_type = 'Member' AND property LIKE '%workspace%'
    """, as_dict=True)
    
    if property_setters:
        for ps in property_setters:
            print(f"  Property: {ps['property']} = {ps['value']}")
    else:
        print("  No property setters related to workspace found")
    
    # 5. Check if there's a def_workspace field in DocType
    print("\n=== CHECKING DOCTYPE FIELDS ===")
    doctype_fields = frappe.db.sql("""
        SELECT fieldname, label, options
        FROM `tabDocField`
        WHERE parent = 'Member' AND fieldname LIKE '%workspace%'
    """, as_dict=True)
    
    if doctype_fields:
        for df in doctype_fields:
            print(f"  Field: {df['fieldname']} - {df['label']} ({df['options']})")
    else:
        print("  No doctype fields related to workspace found")
    
    # 6. Check for any routing overrides
    print("\n=== CHECKING FRAPPE CONFIGURATION ===")
    try:
        from frappe.desk.doctype.workspace.workspace import get_workspace_for_module
        verenigingen_workspace = get_workspace_for_module("Verenigingen")
        print(f"  get_workspace_for_module('Verenigingen'): {verenigingen_workspace}")
    except Exception as e:
        print(f"  Error getting workspace for module: {str(e)}")
    
    # 7. Check workspace sequence
    print("\n=== WORKSPACE SEQUENCE CHECK ===")
    workspaces = frappe.db.sql("""
        SELECT name, label, module, sequence_id
        FROM `tabWorkspace`
        WHERE module = 'Verenigingen'
        ORDER BY sequence_id
    """, as_dict=True)
    
    for ws in workspaces:
        print(f"  {ws['name']}: seq={ws['sequence_id']}")
    
    frappe.destroy()

if __name__ == "__main__":
    check_member_workspace_issue()