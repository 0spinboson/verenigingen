import frappe

def add_membership_reviews_link():
    workspace = frappe.get_doc('Workspace', 'Verenigingen')
    
    # Check if we already have this link
    existing_links = [link.get('link_to') for link in workspace.links if link.get('link_to')]
    
    # Add pending membership applications report to the Memberships section
    new_link = {
        "dependencies": "",
        "hidden": 0,
        "is_query_report": 1,
        "label": "Pending Membership Applications",
        "link_count": 0,
        "link_to": "Pending Membership Applications",
        "link_type": "Report",
        "onboard": 0,
        "type": "Link"
    }
    
    if "Pending Membership Applications" not in existing_links:
        # Find the position after Membership Type to insert it
        insert_position = None
        for i, link in enumerate(workspace.links):
            if link.get('link_to') == 'Membership Type':
                insert_position = i + 1
                break
        
        workspace.append('links', new_link)
        print("Added Pending Membership Applications report link")
        
        # Also add a shortcut for quick access
        new_shortcut = {
            "color": "Orange",
            "label": "Pending Applications",
            "link_to": "Pending Membership Applications", 
            "type": "Report"
        }
        
        existing_shortcuts = [shortcut.get('link_to') for shortcut in workspace.shortcuts if shortcut.get('link_to')]
        if "Pending Membership Applications" not in existing_shortcuts:
            workspace.append('shortcuts', new_shortcut)
            print("Added Application Reviews shortcut")
        
        workspace.save()
        frappe.db.commit()
        print(f"Workspace updated! Now has {len(workspace.links)} links and {len(workspace.shortcuts)} shortcuts")
    else:
        print("Pending Membership Applications link already exists")