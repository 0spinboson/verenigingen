"""
Clean up sidebar items and remove unwanted entries
"""

import frappe

@frappe.whitelist()
def clean_sidebar():
    """Remove unwanted sidebar items"""
    
    # Items to hide from sidebar
    items_to_hide = [
        "Newsletter",
        "Projects", 
        "Quotations",
        "Orders", 
        "Invoices",
        "Shipments",
        "Timesheets", 
        "Material Request",
        "Stock",
        "Manufacturing",
        "CRM", 
        "Assets",
        "Support",
        "Quality",
        "Buying",
        "Selling"
    ]
    
    # Hide workspace shortcuts
    for item in items_to_hide:
        # Remove from workspace shortcuts
        shortcuts = frappe.get_all("Workspace Shortcut", 
                                 filters={"label": item},
                                 fields=["name"])
        for shortcut in shortcuts:
            frappe.delete_doc("Workspace Shortcut", shortcut.name, ignore_permissions=True)
            print(f"Removed workspace shortcut: {item}")
    
    # Hide desktop icons
    for item in items_to_hide:
        icons = frappe.get_all("Desktop Icon", 
                              filters={"label": item},
                              fields=["name"])
        for icon in icons:
            desktop_icon = frappe.get_doc("Desktop Icon", icon.name)
            desktop_icon.hidden = 1
            desktop_icon.save(ignore_permissions=True)
            print(f"Hidden desktop icon: {item}")
    
    # Clean up portal menu items
    clean_portal_menu()
    
    frappe.db.commit()
    return {"success": True, "message": "Sidebar cleaned successfully"}

def clean_portal_menu():
    """Clean portal menu items"""
    
    # Remove duplicate projects and unwanted items
    unwanted_portal_items = [
        "Projects",  # Will remove duplicates
        "Newsletter", 
        "Quotations",
        "Orders",
        "Shipments"
    ]
    
    for item in unwanted_portal_items:
        portal_items = frappe.get_all("Portal Menu Item",
                                    filters={"title": item},
                                    fields=["name"])
        for portal_item in portal_items:
            frappe.delete_doc("Portal Menu Item", portal_item.name, ignore_permissions=True)
            print(f"Removed portal menu item: {item}")

@frappe.whitelist() 
def hide_doctype_from_sidebar():
    """Hide specific doctypes from appearing in sidebar"""
    
    doctypes_to_hide = [
        "Quotation",
        "Sales Order", 
        "Purchase Order",
        "Delivery Note",
        "Purchase Receipt", 
        "Stock Entry",
        "Material Request",
        "Timesheet",
        "Project",
        "Newsletter"
    ]
    
    for doctype in doctypes_to_hide:
        if frappe.db.exists("DocType", doctype):
            doc = frappe.get_doc("DocType", doctype)
            # Hide from modules
            doc.hide_toolbar = 1
            doc.save(ignore_permissions=True)
            print(f"Hidden from toolbar: {doctype}")

@frappe.whitelist()
def comprehensive_sidebar_cleanup():
    """Run comprehensive sidebar cleanup"""
    try:
        clean_sidebar()
        hide_doctype_from_sidebar()
        
        # Also update user permissions to hide these modules
        update_user_permissions()
        
        return {
            "success": True,
            "message": "Comprehensive sidebar cleanup completed. Please refresh your browser."
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Sidebar Cleanup Error")
        return {
            "success": False, 
            "message": f"Error: {str(e)}"
        }

def update_user_permissions():
    """Update user permissions to restrict access to unwanted modules"""
    
    # Get all non-administrator users
    users = frappe.get_all("User", 
                          filters={
                              "enabled": 1,
                              "name": ["!=", "Administrator"],
                              "user_type": "System User"
                          },
                          fields=["name"])
    
    restricted_doctypes = [
        "Quotation", "Sales Order", "Purchase Order", 
        "Delivery Note", "Purchase Receipt", "Stock Entry",
        "Material Request", "Timesheet", "Newsletter"
    ]
    
    for user in users:
        for doctype in restricted_doctypes:
            # Check if permission already exists
            existing = frappe.db.exists("User Permission", {
                "user": user.name,
                "allow": doctype,
                "for_value": ""
            })
            
            if not existing and frappe.db.exists("DocType", doctype):
                # Create restrictive permission 
                try:
                    perm = frappe.get_doc({
                        "doctype": "User Permission",
                        "user": user.name,
                        "allow": doctype,
                        "for_value": "RESTRICTED",  # Non-existent value to block access
                        "apply_to_all_doctypes": 0
                    })
                    perm.insert(ignore_permissions=True)
                    print(f"Restricted {doctype} for user {user.name}")
                except:
                    pass  # Skip if error