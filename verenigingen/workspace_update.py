import frappe

def update_workspace():
    workspace = frappe.get_doc('Workspace', 'Verenigingen')
    
    # Links to add
    new_links = [
        # Termination & Appeals Section
        {
            "hidden": 0,
            "is_query_report": 0,
            "label": "Termination & Appeals",
            "link_count": 2,
            "link_type": "DocType",
            "onboard": 0,
            "type": "Card Break"
        },
        {
            "dependencies": "",
            "hidden": 0,
            "is_query_report": 0,
            "label": "Membership Termination Request",
            "link_count": 0,
            "link_to": "Membership Termination Request",
            "link_type": "DocType",
            "onboard": 0,
            "type": "Link"
        },
        {
            "dependencies": "",
            "hidden": 0,
            "is_query_report": 0,
            "label": "SEPA Mandate",
            "link_count": 0,
            "link_to": "SEPA Mandate",
            "link_type": "DocType",
            "onboard": 0,
            "type": "Link"
        },
        {
            "dependencies": "",
            "hidden": 0,
            "is_query_report": 0,
            "label": "Direct Debit Batch", 
            "link_count": 0,
            "link_to": "Direct Debit Batch",
            "link_type": "DocType",
            "onboard": 0,
            "type": "Link"
        }
    ]
    
    # Add each new link
    for link in new_links:
        workspace.append('links', link)
        print(f"Added: {link.get('label')}")
    
    # Add new shortcuts
    new_shortcuts = [
        {
            "color": "Red",
            "label": "Termination Requests",
            "link_to": "Membership Termination Request",
            "type": "DocType"
        },
        {
            "color": "Blue", 
            "label": "SEPA Mandates",
            "link_to": "SEPA Mandate",
            "type": "DocType"
        }
    ]
    
    for shortcut in new_shortcuts:
        workspace.append('shortcuts', shortcut)
        print(f"Added shortcut: {shortcut.get('label')}")
    
    workspace.save()
    frappe.db.commit()
    print(f"Workspace updated! Now has {len(workspace.links)} links and {len(workspace.shortcuts)} shortcuts")