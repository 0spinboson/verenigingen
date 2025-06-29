"""
Test minimal invoice creation
"""

import frappe

@frappe.whitelist()
def test_minimal_invoice():
    """Try to create the most minimal purchase invoice possible"""
    try:
        # Check if we already have this test invoice
        if frappe.db.exists("Purchase Invoice", {"eboekhouden_invoice_number": "TEST-MINIMAL"}):
            frappe.db.sql("DELETE FROM `tabPurchase Invoice` WHERE eboekhouden_invoice_number = 'TEST-MINIMAL'")
            frappe.db.commit()
        
        # Create invoice with minimal fields
        pi = frappe.new_doc("Purchase Invoice")
        pi.company = "R S P"
        pi.supplier = frappe.db.get_value("Supplier", filters={}, fieldname="name")  # Get any supplier
        pi.posting_date = "2025-01-01"  # Use a simple date
        pi.due_date = "2025-01-31"  # 30 days later
        pi.eboekhouden_invoice_number = "TEST-MINIMAL"
        
        # Get required accounts
        pi.credit_to = frappe.db.get_value("Company", "R S P", "default_payable_account")
        
        # Get a cost center
        cost_center = frappe.db.get_value("Cost Center", {"company": "R S P", "is_group": 0}, "name")
        
        # Add minimal line item
        item = frappe.db.get_value("Item", {"is_stock_item": 0}, "name")
        expense_account = frappe.db.get_value("Account", {
            "company": "R S P",
            "root_type": "Expense",
            "is_group": 0
        }, "name")
        
        pi.append("items", {
            "item_code": item,
            "qty": 1,
            "rate": 100,
            "expense_account": expense_account,
            "cost_center": cost_center
        })
        
        # Try to save
        result = {
            "supplier": pi.supplier,
            "posting_date": pi.posting_date,
            "due_date": pi.due_date,
            "credit_to": pi.credit_to,
            "item": item,
            "expense_account": expense_account
        }
        
        try:
            pi.insert(ignore_permissions=True)
            result["status"] = "Success"
            result["invoice_name"] = pi.name
            # Clean up
            pi.delete()
        except Exception as e:
            result["error"] = str(e)
            
        return result
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    print(test_minimal_invoice())