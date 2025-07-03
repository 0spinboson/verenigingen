import frappe

@frappe.whitelist()
def create_contribution_mapping():
    """Create mapping for contribution account"""
    frappe.set_user("Administrator")
    
    # Create or get membership contribution item
    if not frappe.db.exists("Item", "Membership Contribution"):
        item = frappe.new_doc("Item")
        item.item_code = "Membership Contribution"
        item.item_name = "Membership Contribution"
        item.item_group = "Services"
        item.stock_uom = "Nos"
        item.is_stock_item = 0
        item.description = "Annual membership contribution"
        item.insert(ignore_permissions=True)
    
    # Create mapping
    if not frappe.db.exists("E-Boekhouden Item Mapping", {
        "company": "Ned Ver Vegan",
        "account_code": "80001"
    }):
        mapping = frappe.new_doc("E-Boekhouden Item Mapping")
        mapping.company = "Ned Ver Vegan"
        mapping.account_code = "80001"
        mapping.account_name = "Contributie Leden plus Abonnementen"
        mapping.item_code = "Membership Contribution"
        mapping.transaction_type = "Sales"
        mapping.is_active = 1
        mapping.insert(ignore_permissions=True)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "mapping": mapping.name
        }
    
    return {"already_exists": True}