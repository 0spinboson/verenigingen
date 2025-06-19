#!/usr/bin/env python3
"""
Fix home workspace
"""

import frappe

def fix_home_workspace():
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    
    try:
        # Clear cache first
        frappe.clear_cache()
        
        # Try to get the Home workspace
        if frappe.db.exists("Workspace", "Home"):
            home_ws = frappe.get_doc("Workspace", "Home")
            print(f"Found Home workspace with {len(home_ws.shortcuts)} shortcuts")
            
            # If it's empty, try to restore standard shortcuts
            if len(home_ws.shortcuts) == 0:
                print("Home workspace is empty, attempting to restore...")
                
                # Add some basic shortcuts that should always be there
                standard_shortcuts = [
                    {"label": "Settings", "link_to": "Settings", "type": "DocType"},
                    {"label": "User", "link_to": "User", "type": "DocType"},
                    {"label": "Role", "link_to": "Role", "type": "DocType"},
                    {"label": "System Settings", "link_to": "System Settings", "type": "DocType"},
                ]
                
                for shortcut in standard_shortcuts:
                    home_ws.append("shortcuts", shortcut)
                
                home_ws.save()
                print("Added basic shortcuts to Home workspace")
        else:
            print("Home workspace not found")
            
        # Also check what modules are available
        modules = frappe.get_all("Module Def", fields=["name", "app_name"])
        print(f"\nAvailable modules:")
        for module in modules:
            print(f"  {module.name} ({module.app_name})")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_home_workspace()