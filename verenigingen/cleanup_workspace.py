import frappe

def cleanup_workspace():
    workspace = frappe.get_doc('Workspace', 'Verenigingen')
    
    # Find and remove links to non-existent doctypes
    links_to_remove = []
    for i, link in enumerate(workspace.links):
        link_to = link.get('link_to')
        if link_to and not frappe.db.exists('DocType', link_to):
            print(f"Removing invalid link: {link.get('label')} -> {link_to}")
            links_to_remove.append(i)
    
    # Remove in reverse order to maintain indices
    for i in reversed(links_to_remove):
        del workspace.links[i]
    
    try:
        workspace.save()
        frappe.db.commit()
        print(f"Workspace cleaned up! Now has {len(workspace.links)} valid links")
    except Exception as e:
        print(f"Error saving workspace: {e}")
        frappe.db.rollback()