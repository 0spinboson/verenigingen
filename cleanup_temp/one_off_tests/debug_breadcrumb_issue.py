import frappe

@frappe.whitelist()
def debug_breadcrumb_issue():
    """Comprehensive debug for breadcrumb issue"""
    
    # 1. Check all workspaces
    print("\n=== ALL WORKSPACES ===")
    all_workspaces = frappe.get_all(
        "Workspace",
        fields=["name", "label", "module", "sequence_id", "is_hidden", "public", "title"],
        order_by="module, sequence_id"
    )
    
    for ws in all_workspaces:
        if ws.module == "Verenigingen":
            print(f">>> {ws.name}: module={ws.module}, seq={ws.sequence_id}, hidden={ws.is_hidden}, title={ws.title}")
    
    # 2. Check workspace link existence
    print("\n=== WORKSPACE EXISTENCE CHECK ===")
    for ws_name in ["Verenigingen", "SEPA Management", "E-Boekhouden"]:
        exists = frappe.db.exists("Workspace", ws_name)
        print(f"{ws_name}: {'EXISTS' if exists else 'NOT FOUND'}")
    
    # 3. Check doctype module assignment
    print("\n=== DOCTYPE MODULE ASSIGNMENTS ===")
    doctypes = ["Member", "Membership", "SEPA Mandate", "Direct Debit Batch"]
    for dt in doctypes:
        if frappe.db.exists("DocType", dt):
            module = frappe.db.get_value("DocType", dt, "module")
            print(f"{dt}: module={module}")
    
    # 4. Check if there's a workspace override
    print("\n=== CHECK FOR OVERRIDES ===")
    
    # Check singles for any workspace settings
    singles = ["System Settings", "Verenigingen Settings"]
    for single in singles:
        if frappe.db.exists("DocType", single):
            doc = frappe.get_doc(single)
            for field in doc.as_dict():
                if "workspace" in field.lower():
                    print(f"{single}.{field} = {getattr(doc, field)}")
    
    # 5. Check workspace routing
    print("\n=== WORKSPACE ROUTING ===")
    from frappe.desk.desktop import get_workspace_sidebar_items
    
    try:
        # Get workspace for the module
        workspace_data = get_workspace_sidebar_items(module="Verenigingen")
        print(f"get_workspace_sidebar_items result: {workspace_data}")
    except Exception as e:
        print(f"Error getting workspace sidebar: {str(e)}")
    
    # 6. Direct SQL check
    print("\n=== DIRECT SQL CHECK ===")
    sql = """
    SELECT name, label, module, sequence_id, modified 
    FROM tabWorkspace 
    WHERE module = 'Verenigingen' 
    ORDER BY sequence_id, modified DESC
    """
    results = frappe.db.sql(sql, as_dict=True)
    for r in results:
        print(f"{r.name}: seq={r.sequence_id}, modified={r.modified}")

if __name__ == "__main__":
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    debug_breadcrumb_issue()
    frappe.destroy()