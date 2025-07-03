import frappe

@frappe.whitelist()
def check_workspace_issues():
    """Debug function to check for workspace issues causing menu problems"""
    frappe.set_user("Administrator")
    
    # Check all workspaces
    workspaces = frappe.get_all("Workspace", 
        fields=["name", "title", "module", "is_standard", "content"],
        order_by="name")
    
    issues = []
    
    for ws in workspaces:
        # Check for null or empty titles
        if not ws.get("title"):
            issues.append(f"Workspace '{ws.name}' has no title")
        
        # Check for null module
        if not ws.get("module"):
            issues.append(f"Workspace '{ws.name}' has no module")
        
        # Check workspace content for null pages
        if ws.get("content"):
            try:
                import json
                content = json.loads(ws.content)
                
                # Check pages in content
                for item in content.get("items", []):
                    if item.get("type") == "page":
                        if not item.get("data", {}).get("page_name"):
                            issues.append(f"Workspace '{ws.name}' has a page with no page_name")
                        if not item.get("data", {}).get("label"):
                            issues.append(f"Workspace '{ws.name}' has a page with no label")
                            
            except Exception as e:
                issues.append(f"Error parsing content for workspace '{ws.name}': {str(e)}")
    
    # Check for duplicate workspace names
    duplicate_check = frappe.db.sql("""
        SELECT name, COUNT(*) as count 
        FROM `tabWorkspace` 
        GROUP BY name 
        HAVING count > 1
    """, as_dict=True)
    
    for dup in duplicate_check:
        issues.append(f"Duplicate workspace name: {dup.name} (count: {dup.count})")
    
    # Check for pages that might have issues
    pages = frappe.get_all("Page", 
        fields=["name", "title", "module", "standard"],
        order_by="name")
    
    for page in pages:
        if not page.get("title"):
            issues.append(f"Page '{page.name}' has no title")
    
    # Check workspace links
    workspace_links = frappe.db.sql("""
        SELECT parent, parenttype, link_to, label, type
        FROM `tabWorkspace Link`
        WHERE link_to IS NULL OR link_to = ''
    """, as_dict=True)
    
    for link in workspace_links:
        issues.append(f"Null link in workspace '{link.parent}': {link}")
    
    return {
        "issues": issues,
        "workspace_count": len(workspaces),
        "page_count": len(pages),
        "verenigingen_workspaces": [ws for ws in workspaces if "verenigingen" in ws.name.lower() or (ws.module and "verenigingen" in ws.module.lower())]
    }

if __name__ == "__main__":
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    result = check_workspace_issues()
    print("Workspace Debug Results:")
    print(f"Total workspaces: {result['workspace_count']}")
    print(f"Total pages: {result['page_count']}")
    print(f"\nIssues found: {len(result['issues'])}")
    for issue in result['issues']:
        print(f"- {issue}")
    print(f"\nVerenigingen workspaces:")
    for ws in result['verenigingen_workspaces']:
        print(f"- {ws.name} (title: {ws.title}, module: {ws.module})")
    frappe.destroy()