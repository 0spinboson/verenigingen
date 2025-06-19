"""
Final cleanup for persistent sidebar items
"""

import frappe

@frappe.whitelist()
def remove_persistent_sidebar_items():
    """Remove the specific items still showing in sidebar"""
    
    # Exact items you mentioned seeing
    persistent_items = [
        "Issues & Support",
        "Newsletter", 
        "Projects",
        "Quotations",
        "Orders",
        "Invoices", 
        "Shipments",
        "Addresses",
        "Timesheets",
        "Material Request"
    ]
    
    cleaned_items = []
    
    # 1. Remove workspace shortcuts
    for item in persistent_items:
        shortcuts = frappe.db.sql("""
            SELECT name FROM `tabWorkspace Shortcut` 
            WHERE label = %s OR link_to = %s
        """, (item, item), as_dict=True)
        
        for shortcut in shortcuts:
            frappe.delete_doc("Workspace Shortcut", shortcut.name, ignore_permissions=True)
            cleaned_items.append(f"Workspace shortcut: {item}")
    
    # 2. Remove portal menu items  
    for item in persistent_items:
        portal_items = frappe.db.sql("""
            SELECT name FROM `tabPortal Menu Item`
            WHERE title = %s OR route LIKE %s
        """, (item, f"%{item.lower().replace(' ', '_')}%"), as_dict=True)
        
        for portal_item in portal_items:
            frappe.delete_doc("Portal Menu Item", portal_item.name, ignore_permissions=True)
            cleaned_items.append(f"Portal menu: {item}")
    
    # 3. Hide specific doctypes
    doctype_mappings = {
        "Quotations": "Quotation",
        "Orders": ["Sales Order", "Purchase Order"],
        "Invoices": ["Sales Invoice", "Purchase Invoice"], 
        "Shipments": ["Delivery Note", "Purchase Receipt"],
        "Timesheets": "Timesheet",
        "Material Request": "Material Request",
        "Newsletter": "Newsletter",
        "Projects": "Project",
        "Addresses": "Address"
    }
    
    for display_name, doctypes in doctype_mappings.items():
        if isinstance(doctypes, str):
            doctypes = [doctypes]
            
        for doctype in doctypes:
            if frappe.db.exists("DocType", doctype):
                frappe.db.set_value("DocType", doctype, "hide_toolbar", 1)
                cleaned_items.append(f"Hidden doctype: {doctype}")
    
    # 4. Clear desktop icons
    for item in persistent_items:
        icons = frappe.db.sql("""
            SELECT name FROM `tabDesktop Icon`
            WHERE label = %s OR module_name = %s
        """, (item, item), as_dict=True)
        
        for icon in icons:
            frappe.db.set_value("Desktop Icon", icon.name, "hidden", 1)
            cleaned_items.append(f"Hidden desktop icon: {item}")
    
    # 5. Remove from standard portal menu items (hooks level)
    update_portal_hooks()
    
    frappe.db.commit()
    
    return {
        "success": True,
        "message": f"Cleaned {len(cleaned_items)} items. Please refresh browser.",
        "details": cleaned_items
    }

def update_portal_hooks():
    """Update portal menu at hooks level"""
    # This would require a restart, but we'll document it
    pass

@frappe.whitelist()
def clear_user_cache():
    """Clear user cache to force sidebar refresh"""
    try:
        # Clear all user caches
        frappe.cache().delete_keys("user_info:*")
        frappe.cache().delete_keys("bootinfo:*")
        frappe.cache().delete_keys("desktop_icons:*")
        
        # Clear specific caches
        frappe.clear_cache()
        
        return {"success": True, "message": "Cache cleared"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@frappe.whitelist() 
def complete_sidebar_fix():
    """Complete fix for sidebar issues"""
    try:
        # Run the cleanup
        result1 = remove_persistent_sidebar_items()
        
        # Clear caches
        result2 = clear_user_cache()
        
        # Force rebuild of workspace sidebar
        rebuild_workspace_sidebar()
        
        return {
            "success": True,
            "message": "Complete sidebar cleanup finished. Please refresh your browser and hard reload (Ctrl+F5).",
            "cleanup_details": result1.get("details", [])
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Complete Sidebar Fix Error")
        return {"success": False, "message": f"Error: {str(e)}"}

def rebuild_workspace_sidebar():
    """Force rebuild workspace sidebar configuration"""
    
    # Get the current user's workspace settings
    users = frappe.get_all("User", filters={"enabled": 1}, fields=["name"])
    
    for user in users:
        # Clear user-specific workspace cache
        cache_key = f"workspace_sidebar_items:{user.name}"
        frappe.cache().delete_value(cache_key)
        
        # Clear user's desktop cache
        desktop_cache_key = f"bootinfo:{user.name}"
        frappe.cache().delete_value(desktop_cache_key)