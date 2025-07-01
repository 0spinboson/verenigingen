import frappe

@frappe.whitelist()
def fix_workspace_order():
    """Fix workspace ordering to ensure Verenigingen is the primary workspace"""
    
    # Update sequence IDs to ensure proper ordering
    updates = [
        ("Verenigingen", 1.0),        # Make it first
        ("E-Boekhouden", 50.0),       # Secondary
        ("SEPA Management", 100.0)    # Tertiary
    ]
    
    for workspace_name, new_sequence in updates:
        frappe.db.set_value("Workspace", workspace_name, "sequence_id", new_sequence)
        print(f"Updated {workspace_name} sequence_id to {new_sequence}")
    
    frappe.db.commit()
    
    # Clear cache to ensure changes take effect
    frappe.clear_cache()
    
    return "Workspace order fixed. Verenigingen should now be the primary workspace."

if __name__ == "__main__":
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    print(fix_workspace_order())
    frappe.destroy()