"""
Test invoice creation directly
"""

import frappe
from frappe.utils import add_days

@frappe.whitelist()
def test_invoice_creation():
    """Test creating a purchase invoice with the same data"""
    try:
        # Test data from failed record
        posting_date = "2025-04-03"
        payment_terms = 30
        
        # Calculate due date
        due_date = add_days(posting_date, payment_terms)
        
        # Get company settings
        company = "R S P"
        
        # Create test invoice
        pi = frappe.new_doc("Purchase Invoice")
        pi.company = company
        pi.supplier = "E-Boekhouden Import Supplier"  # Assuming this exists
        pi.posting_date = posting_date
        pi.due_date = due_date
        
        # Check values before save
        result = {
            "posting_date": pi.posting_date,
            "due_date": pi.due_date,
            "posting_date_type": type(pi.posting_date).__name__,
            "due_date_type": type(pi.due_date).__name__,
            "due_after_posting": pi.due_date > pi.posting_date if pi.due_date and pi.posting_date else "Cannot compare"
        }
        
        # Try to validate
        try:
            pi.validate()
            result["validation"] = "Success"
        except Exception as e:
            result["validation_error"] = str(e)
        
        return result
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    print(test_invoice_creation())