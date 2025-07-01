"""
Check prerequisites for migration
"""

import frappe

@frappe.whitelist()
def check_prerequisites():
    """Check if all prerequisites exist"""
    results = {}
    
    # Check Item Group
    results["item_group_services"] = frappe.db.exists("Item Group", "Services")
    results["any_item_group"] = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    
    # Check some items
    results["service_misc_exists"] = frappe.db.exists("Item", "Service MISC")
    results["total_items"] = frappe.db.count("Item")
    
    # Check expense accounts
    results["expense_accounts"] = frappe.db.count("Account", {
        "company": "R S P",
        "root_type": "Expense",
        "is_group": 0
    })
    
    # Check if any purchase invoices exist
    results["existing_purchase_invoices"] = frappe.db.count("Purchase Invoice")
    
    return results

if __name__ == "__main__":
    print(check_prerequisites())