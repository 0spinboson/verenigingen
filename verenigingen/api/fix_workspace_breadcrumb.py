import frappe

@frappe.whitelist()
def diagnose_breadcrumb_issue():
    """Diagnose why breadcrumb shows SEPA Management for E-Boekhouden Migration"""
    
    results = {}
    
    # Check if there's a workspace shortcut or link that's causing the issue
    sepa_shortcuts = frappe.db.sql("""
        SELECT * FROM `tabWorkspace Shortcut`
        WHERE link_to = 'E-Boekhouden Migration'
        AND parent = 'SEPA Management'
    """, as_dict=True)
    results['sepa_shortcuts'] = sepa_shortcuts
    
    # Check if there's a custom route
    custom_routes = frappe.db.sql("""
        SELECT * FROM `tabWebsite Route Meta`
        WHERE name LIKE '%boekhouden%'
    """, as_dict=True)
    results['custom_routes'] = custom_routes
    
    # Check desk page settings
    desk_pages = frappe.db.sql("""
        SELECT * FROM `tabDesk Page`
        WHERE content LIKE '%E-Boekhouden Migration%'
    """, as_dict=True)
    results['desk_pages'] = desk_pages
    
    # Check if there's a user permission issue
    user_perms = frappe.db.sql("""
        SELECT * FROM `tabUser Permission`
        WHERE user = %s
        AND (allow = 'Workspace' OR for_value LIKE '%Boekhouden%' OR for_value = 'SEPA Management')
    """, frappe.session.user, as_dict=True)
    results['user_permissions'] = user_perms
    
    # Check DefaultValue table for workspace preferences
    workspace_defaults = frappe.db.sql("""
        SELECT * FROM `tabDefaultValue`
        WHERE defkey LIKE '%workspace%'
        AND parent = %s
    """, frappe.session.user, as_dict=True)
    results['workspace_defaults'] = workspace_defaults
    
    # Check if there's a module override
    module_overrides = frappe.db.sql("""
        SELECT * FROM `tabModule Def`
        WHERE module_name = 'Verenigingen'
    """, as_dict=True)
    results['module_def'] = module_overrides
    
    return results

@frappe.whitelist()
def force_correct_workspace_assignment():
    """Force E-Boekhouden Migration to use E-Boekhouden workspace"""
    
    fixes = []
    
    # 1. Ensure E-Boekhouden workspace exists and is properly configured
    if frappe.db.exists("Workspace", "E-Boekhouden"):
        frappe.db.set_value("Workspace", "E-Boekhouden", {
            "module": "Verenigingen",
            "is_hidden": 0,
            "sequence_id": 20.0,
            "public": 1
        })
        fixes.append("Updated E-Boekhouden workspace configuration")
    
    # 2. Create a desk page link if needed
    try:
        # Check if there's a desk page that might be overriding
        desk_page_name = "e-boekhouden-desk"
        if not frappe.db.exists("Desk Page", desk_page_name):
            desk_page = frappe.new_doc("Desk Page")
            desk_page.page_name = desk_page_name
            desk_page.workspace = "E-Boekhouden"
            desk_page.module = "Verenigingen"
            desk_page.insert(ignore_permissions=True)
            fixes.append("Created desk page for E-Boekhouden")
    except:
        pass
    
    # 3. Set user default if needed
    try:
        # Check if user has a default workspace set
        existing_default = frappe.db.get_value(
            "DefaultValue",
            {"parent": frappe.session.user, "defkey": "module_Verenigingen_workspace"},
            "name"
        )
        
        if not existing_default:
            default_doc = frappe.new_doc("DefaultValue")
            default_doc.parent = frappe.session.user
            default_doc.parenttype = "User"
            default_doc.parentfield = "defaults"
            default_doc.defkey = "module_Verenigingen_workspace"
            default_doc.defvalue = "E-Boekhouden"
            default_doc.insert(ignore_permissions=True)
            fixes.append("Set user default workspace for Verenigingen module")
    except:
        pass
    
    frappe.db.commit()
    frappe.clear_cache()
    
    return {
        "success": True,
        "fixes_applied": fixes,
        "message": "Applied fixes for workspace assignment. Please refresh your browser and try accessing E-Boekhouden Migration again."
    }

@frappe.whitelist()
def check_workspace_hierarchy():
    """Check the actual workspace hierarchy being used"""
    
    from frappe.desk.desktop import get_desktop_page
    
    try:
        # Get the desktop page for E-Boekhouden Migration
        page_info = get_desktop_page({
            "doctype": "E-Boekhouden Migration",
            "module": "Verenigingen"
        })
        
        return {
            "success": True,
            "page_info": page_info
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }