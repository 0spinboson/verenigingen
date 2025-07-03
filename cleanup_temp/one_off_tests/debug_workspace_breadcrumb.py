#!/usr/bin/env python3

import frappe

def check_workspace_breadcrumb():
    """Debug workspace breadcrumb issue"""
    
    # Get all workspaces for Verenigingen module
    workspaces = frappe.get_all(
        "Workspace",
        filters={"module": "Verenigingen"},
        fields=["name", "label", "module", "sequence_id", "is_hidden", "public"],
        order_by="sequence_id"
    )
    
    print("\n=== Verenigingen Module Workspaces ===")
    for ws in workspaces:
        print(f"Name: {ws.name}, Label: {ws.label}, Sequence: {ws.sequence_id}, Hidden: {ws.is_hidden}, Public: {ws.public}")
    
    # Check if there's a default workspace setting
    print("\n=== Module Defaults ===")
    module_def = frappe.get_all(
        "Module Def",
        filters={"module_name": "Verenigingen"},
        fields=["*"]
    )
    if module_def:
        print(f"Module Def: {module_def[0]}")
    
    # Check workspace permissions
    print("\n=== Workspace Permissions ===")
    for ws in workspaces:
        doc = frappe.get_doc("Workspace", ws.name)
        print(f"\nWorkspace: {ws.name}")
        print(f"Roles: {[r.role for r in doc.roles]}")
        
    # Check which workspace would be loaded first
    print("\n=== Workspace Loading Logic ===")
    # This is how Frappe typically loads workspaces
    first_workspace = frappe.db.get_value(
        "Workspace",
        {
            "module": "Verenigingen",
            "is_hidden": 0,
            "public": 1
        },
        "name",
        order_by="sequence_id asc"
    )
    print(f"First loaded workspace (by sequence): {first_workspace}")
    
    # Check for any custom workspace settings
    print("\n=== Custom Settings ===")
    settings = frappe.get_single("System Settings")
    if hasattr(settings, "default_workspace"):
        print(f"Default Workspace: {settings.default_workspace}")
    else:
        print("No default workspace setting found")

if __name__ == "__main__":
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    check_workspace_breadcrumb()
    frappe.destroy()