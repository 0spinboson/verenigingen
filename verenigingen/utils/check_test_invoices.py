"""
Check test purchase invoices
"""

import frappe

@frappe.whitelist()
def check_test_invoices():
    """Check what test invoices exist"""
    
    invoices = frappe.db.get_all("Purchase Invoice", 
        filters={"eboekhouden_invoice_number": ["like", "%TEST%"]},
        fields=["name", "eboekhouden_invoice_number", "posting_date", "bill_date", "due_date", "docstatus"],
        order_by="creation desc"
    )
    
    return {
        "count": len(invoices),
        "invoices": invoices
    }

if __name__ == "__main__":
    print(check_test_invoices())