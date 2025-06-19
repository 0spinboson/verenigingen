"""
Restore Home workspace functionality
"""

import frappe

@frappe.whitelist()
def restore_home_workspace():
    """Restore basic functionality to Home workspace"""
    
    try:
        # Check if Home workspace exists
        if not frappe.db.exists("Workspace", "Home"):
            frappe.throw("Home workspace not found")
        
        workspace = frappe.get_doc('Workspace', 'Home')
        
        # Clear existing shortcuts to start fresh
        workspace.shortcuts = []
        
        # Add essential shortcuts that should always be available
        essential_shortcuts = [
            {
                'label': 'User',
                'type': 'DocType',
                'link_to': 'User',
                'color': 'Blue'
            },
            {
                'label': 'Role',
                'type': 'DocType', 
                'link_to': 'Role',
                'color': 'Purple'
            },
            {
                'label': 'System Settings',
                'type': 'DocType',
                'link_to': 'System Settings',
                'color': 'Grey'
            },
            {
                'label': 'Workspace',
                'type': 'DocType',
                'link_to': 'Workspace',
                'color': 'Orange'
            },
            {
                'label': 'Doctype',
                'type': 'DocType',
                'link_to': 'DocType', 
                'color': 'Green'
            }
        ]
        
        # Add ERPNext core shortcuts if modules are available
        if frappe.db.exists("Module Def", "Accounts"):
            essential_shortcuts.extend([
                {
                    'label': 'Accounting',
                    'type': 'Page',
                    'link_to': '/app/accounting',
                    'color': 'Blue'
                },
                {
                    'label': 'Sales',
                    'type': 'Page',
                    'link_to': '/app/selling',
                    'color': 'Green'
                },
                {
                    'label': 'Buying',
                    'type': 'Page',
                    'link_to': '/app/buying',
                    'color': 'Red'
                }
            ])
        
        # Add verenigingen shortcuts
        if frappe.db.exists("Module Def", "Verenigingen"):
            essential_shortcuts.insert(0, {
                'label': 'Verenigingen',
                'type': 'Page',
                'link_to': '/app/verenigingen',
                'color': 'Blue'
            })
        
        # Add shortcuts to workspace
        for shortcut in essential_shortcuts:
            workspace.append("shortcuts", shortcut)
        
        # Make sure it's public and set as standard
        workspace.public = 1
        workspace.is_standard = 1
        
        workspace.save()
        frappe.db.commit()
        
        # Clear cache to refresh
        frappe.clear_cache()
        
        return {
            "success": True,
            "message": f"Home workspace restored with {len(essential_shortcuts)} shortcuts",
            "shortcuts_added": len(essential_shortcuts)
        }
        
    except Exception as e:
        frappe.log_error(f"Error restoring Home workspace: {str(e)}", "Home Workspace Restore")
        return {
            "success": False,
            "error": str(e)
        }