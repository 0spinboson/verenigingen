"""
Test creating a purchase invoice directly
"""

import frappe
from frappe.utils import add_days

@frappe.whitelist()
def test_create_invoice():
    """Test creating a purchase invoice with the exact pattern from migration"""
    
    # Use exact data from a failing invoice
    posting_date = "2025-03-03"
    payment_terms = 30
    invoice_no = "TEST-20250303-DIRECT"
    
    company = "R S P"
    supplier = frappe.db.get_value("Supplier", filters={}, fieldname="name")
    credit_to = frappe.db.get_value("Company", company, "default_payable_account")
    cost_center = frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")
    item = frappe.db.get_value("Item", {"is_stock_item": 0}, "name")
    expense_account = frappe.db.get_value("Account", {
        "company": company,
        "root_type": "Expense",
        "is_group": 0
    }, "name")
    
    # Delete if exists
    if frappe.db.exists("Purchase Invoice", {"eboekhouden_invoice_number": invoice_no}):
        frappe.delete_doc("Purchase Invoice", frappe.db.get_value("Purchase Invoice", {"eboekhouden_invoice_number": invoice_no}, "name"))
        frappe.db.commit()
    
    result = {
        "setup": {
            "posting_date": posting_date,
            "payment_terms": payment_terms,
            "supplier": supplier,
            "credit_to": credit_to,
            "cost_center": cost_center
        }
    }
    
    try:
        # Create invoice exactly as migration does
        pi = frappe.new_doc("Purchase Invoice")
        pi.company = company
        pi.supplier = supplier
        pi.posting_date = posting_date
        pi.bill_date = posting_date  # Set bill_date same as posting_date
        pi.eboekhouden_invoice_number = invoice_no
        pi.remarks = "Test invoice"
        
        # Calculate due date exactly as migration does
        calculated_due_date = add_days(posting_date, payment_terms)
        if frappe.utils.getdate(calculated_due_date) < frappe.utils.getdate(posting_date):
            pi.due_date = posting_date
        else:
            pi.due_date = calculated_due_date
        
        result["calculated_due_date"] = calculated_due_date
        result["set_due_date"] = pi.due_date
        
        # Set credit account
        if credit_to:
            pi.credit_to = credit_to
        
        pi.cost_center = cost_center
        
        # Add line item
        pi.append("items", {
            "item_code": item,
            "qty": 1,
            "rate": 100,
            "expense_account": expense_account,
            "cost_center": cost_center
        })
        
        result["invoice_data"] = {
            "posting_date": pi.posting_date,
            "bill_date": pi.bill_date,
            "due_date": pi.due_date,
            "types": {
                "posting_date": type(pi.posting_date).__name__,
                "bill_date": type(pi.bill_date).__name__,
                "due_date": type(pi.due_date).__name__
            }
        }
        
        # Try to insert
        pi.insert(ignore_permissions=True)
        result["status"] = "Success"
        result["invoice_name"] = pi.name
        
        # Clean up
        pi.delete()
        
    except Exception as e:
        result["error"] = str(e)
        
        # Check what validation would see
        if 'pi' in locals():
            validation_posting_date = pi.bill_date or pi.posting_date
            result["validation_check"] = {
                "validation_posting_date": validation_posting_date,
                "due_date": pi.due_date if 'pi' in locals() else None,
                "comparison": frappe.utils.getdate(pi.due_date) >= frappe.utils.getdate(validation_posting_date) if 'pi' in locals() and pi.due_date else None
            }
    
    return result

if __name__ == "__main__":
    print(test_create_invoice())