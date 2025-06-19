"""
Simple workspace fix for onboarding
"""

import frappe

@frappe.whitelist()
def add_onboarding_shortcut_only():
    """Just add a simple onboarding shortcut"""
    
    try:
        workspace = frappe.get_doc('Workspace', 'Verenigingen')
        
        # Add setup guide shortcut at the beginning
        workspace.shortcuts.insert(0, {
            'label': 'Setup Guide',
            'type': 'DocType',
            'link_to': 'Module Onboarding', 
            'color': 'Green'
        })
        
        workspace.save()
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Setup Guide shortcut added to Verenigingen workspace"
        }
        
    except Exception as e:
        frappe.log_error(f"Error adding shortcut: {str(e)}", "Workspace Fix")
        return {
            "success": False,
            "error": str(e)
        }