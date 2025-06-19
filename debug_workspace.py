#!/usr/bin/env python3
"""
Check workspace configuration
"""

import frappe

@frappe.whitelist()
def check_workspace_status():
    """Check current workspace configuration"""
    try:
        # Check workspaces
        workspaces = frappe.get_all('Workspace', fields=['name', 'title', 'is_standard', 'public'])
        print(f"Found {len(workspaces)} workspaces:")
        for ws in workspaces:
            print(f"  {ws.name} - {ws.title} (standard: {ws.is_standard}, public: {ws.public})")
        
        # Check Home workspace specifically
        try:
            home_workspace = frappe.get_doc('Workspace', 'Home')
            print(f"\nHome workspace details:")
            print(f"  Charts: {len(home_workspace.charts)}")
            print(f"  Shortcuts: {len(home_workspace.shortcuts)}")  
            print(f"  Links: {len(home_workspace.links)}")
            print(f"  Is standard: {home_workspace.is_standard}")
            print(f"  Public: {home_workspace.public}")
            
            if home_workspace.shortcuts:
                print("  Shortcuts:")
                for shortcut in home_workspace.shortcuts:
                    print(f"    - {shortcut.label}: {shortcut.link_to}")
                    
        except Exception as e:
            print(f"Error getting Home workspace: {e}")
            
        # Check if domain restrictions are affecting things
        try:
            domain = frappe.get_single_value('System Settings', 'domain')
            print(f"\nDomain setting: {domain}")
        except:
            print("\nNo domain setting found")
        
        return {"success": True}
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    check_workspace_status()