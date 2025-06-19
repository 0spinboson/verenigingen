"""
Workspace updater to add Email Templates link programmatically
"""

import frappe

@frappe.whitelist()
def update_workspace_with_email_templates():
    """Update Verenigingen workspace to include Email Templates link"""
    
    try:
        # Get the workspace document
        workspace = frappe.get_doc('Workspace', 'Verenigingen')
        
        # Check if Email Templates link already exists
        email_template_exists = False
        for link in workspace.links:
            if link.link_to == 'Email Template':
                email_template_exists = True
                break
        
        # Add Email Templates link if it doesn't exist
        if not email_template_exists:
            workspace.append('links', {
                'hidden': 0,
                'is_query_report': 0,
                'label': 'Email Templates',
                'link_count': 0,
                'link_to': 'Email Template',
                'link_type': 'DocType',
                'onboard': 0,
                'type': 'Link'
            })
        
        # Check if Email Templates shortcut already exists
        email_shortcut_exists = False
        for shortcut in workspace.shortcuts:
            if shortcut.link_to == 'Email Template':
                email_shortcut_exists = True
                break
        
        # Add Email Templates shortcut if it doesn't exist
        if not email_shortcut_exists:
            workspace.append('shortcuts', {
                'color': 'Purple',
                'doc_view': '',
                'label': 'Email Templates',
                'link_to': 'Email Template',
                'type': 'DocType'
            })
        
        # Save the workspace
        workspace.save()
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Email Templates link and shortcut added to Verenigingen workspace",
            "link_added": not email_template_exists,
            "shortcut_added": not email_shortcut_exists
        }
        
    except Exception as e:
        frappe.log_error(f"Error updating workspace: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def verify_workspace_update():
    """Verify Email Templates is now accessible in workspace"""
    
    try:
        workspace = frappe.get_doc('Workspace', 'Verenigingen')
        
        # Check for Email Templates in links
        email_template_links = []
        for i, link in enumerate(workspace.links):
            if link.link_to == 'Email Template':
                email_template_links.append({
                    "index": i,
                    "label": link.label,
                    "link_to": link.link_to,
                    "link_type": link.link_type,
                    "type": link.type
                })
        
        # Check for Email Templates in shortcuts
        email_template_shortcuts = []
        for i, shortcut in enumerate(workspace.shortcuts):
            if shortcut.link_to == 'Email Template':
                email_template_shortcuts.append({
                    "index": i,
                    "label": shortcut.label,
                    "link_to": shortcut.link_to,
                    "color": shortcut.color,
                    "type": shortcut.type
                })
        
        return {
            "success": True,
            "workspace_links": email_template_links,
            "workspace_shortcuts": email_template_shortcuts,
            "links_found": len(email_template_links),
            "shortcuts_found": len(email_template_shortcuts),
            "total_links": len(workspace.links),
            "total_shortcuts": len(workspace.shortcuts)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }