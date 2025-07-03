"""
Test creating invoice directly
"""

import frappe
from frappe.utils import add_days, getdate

@frappe.whitelist()
def test_direct_invoice():
    """Test creating a purchase invoice exactly as in migration"""
    try:
        # Exact data from failed record
        posting_date = "2025-04-03"
        payment_terms = 30
        
        # Create supplier if not exists
        if not frappe.db.exists("Supplier", "Test E-Book Supplier"):
            supplier = frappe.new_doc("Supplier")
            supplier.supplier_name = "Test E-Book Supplier"
            supplier.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "All Supplier Groups"
            supplier.insert(ignore_permissions=True)
        
        # Create purchase invoice
        pi = frappe.new_doc("Purchase Invoice")
        pi.company = "R S P"
        pi.supplier = "Test E-Book Supplier"
        pi.posting_date = posting_date
        pi.eboekhouden_invoice_number = "TEST-001"
        pi.remarks = "Test invoice"
        
        # Calculate due date exactly as in migration
        calculated_due_date = add_days(posting_date, payment_terms)
        if getdate(calculated_due_date) < getdate(posting_date):
            pi.due_date = posting_date
        else:
            pi.due_date = calculated_due_date
        
        # Get default payable account
        default_payable = frappe.db.get_value("Company", "R S P", "default_payable_account")
        if default_payable:
            pi.credit_to = default_payable
            
        # Get a cost center
        cost_center = frappe.db.get_value("Cost Center", {"company": "R S P", "is_group": 0}, "name")
        if cost_center:
            pi.cost_center = cost_center
        
        # Add a simple line item
        pi.append("items", {
            "item_code": "Service MISC",
            "qty": 1,
            "rate": 100,
            "expense_account": frappe.db.get_value("Account", {
                "company": "R S P",
                "root_type": "Expense",
                "is_group": 0
            }, "name"),
            "cost_center": cost_center
        })
        
        # Debug info before insert
        debug_info = {
            "posting_date": pi.posting_date,
            "due_date": pi.due_date,
            "posting_type": type(pi.posting_date).__name__,
            "due_type": type(pi.due_date).__name__,
            "credit_to": pi.credit_to,
            "cost_center": pi.cost_center,
            "items_count": len(pi.items)
        }
        
        # Try to insert
        try:
            pi.insert(ignore_permissions=True)
            debug_info["result"] = "Success"
            debug_info["invoice_name"] = pi.name
            
            # Clean up
            pi.delete()
            
        except Exception as e:
            debug_info["error"] = str(e)
            debug_info["error_type"] = type(e).__name__
        
        return debug_info
        
    except Exception as e:
        return {"error": str(e), "error_type": type(e).__name__}

if __name__ == "__main__":
    print(test_direct_invoice())