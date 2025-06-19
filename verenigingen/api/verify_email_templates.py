"""
Verify Email Templates access in workspace
"""

import frappe

@frappe.whitelist()
def verify_email_templates_workspace():
    """Verify Email Templates is accessible in workspace"""
    
    try:
        workspace = frappe.get_doc('Workspace', 'Verenigingen')
        
        # Check for Email Templates in links
        email_template_links = []
        for i, link in enumerate(workspace.links):
            if 'email' in (link.label or "").lower() or link.link_to == 'Email Template':
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
            if 'email' in (shortcut.label or "").lower() or shortcut.link_to == 'Email Template':
                email_template_shortcuts.append({
                    "index": i,
                    "label": shortcut.label,
                    "link_to": shortcut.link_to,
                    "color": shortcut.color,
                    "type": shortcut.type
                })
        
        # Verify Email Template doctype exists
        email_template_exists = frappe.db.exists('DocType', 'Email Template')
        
        # Count Verenigingen email templates
        verenigingen_templates = frappe.get_all('Email Template',
                                               filters={
                                                   'name': ['in', [
                                                       'expense_approval_request',
                                                       'expense_approved', 
                                                       'expense_rejected',
                                                       'donation_confirmation',
                                                       'donation_payment_confirmation',
                                                       'anbi_tax_receipt',
                                                       'termination_overdue_notification',
                                                       'member_contact_request_received',
                                                       'membership_application_rejected',
                                                       'membership_rejection_incomplete',
                                                       'membership_rejection_ineligible',
                                                       'membership_rejection_duplicate',
                                                       'membership_application_approved'
                                                   ]]
                                               },
                                               fields=['name', 'subject'])
        
        return {
            "success": True,
            "email_template_doctype_exists": bool(email_template_exists),
            "workspace_links": email_template_links,
            "workspace_shortcuts": email_template_shortcuts,
            "verenigingen_templates_count": len(verenigingen_templates),
            "verenigingen_templates": verenigingen_templates,
            "workspace_stats": {
                "total_links": len(workspace.links),
                "total_shortcuts": len(workspace.shortcuts),
                "email_links_found": len(email_template_links),
                "email_shortcuts_found": len(email_template_shortcuts)
            },
            "access_methods": [
                {
                    "method": "Direct URL",
                    "url": "/app/List/Email%20Template",
                    "description": "Access all email templates"
                },
                {
                    "method": "Search",
                    "description": "Search for 'Email Template' in ERPNext search bar"
                },
                {
                    "method": "Workspace Link",
                    "available": len(email_template_links) > 0,
                    "description": "Click Email Templates in Verenigingen workspace"
                },
                {
                    "method": "Workspace Shortcut",
                    "available": len(email_template_shortcuts) > 0,
                    "description": "Click Email Templates shortcut tile"
                }
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }