"""
Count E-Boekhouden invoices
"""

import frappe

@frappe.whitelist()
def count_invoices():
    """Count purchase invoices with eboekhouden invoice numbers"""
    
    purchase_invoices = frappe.db.count("Purchase Invoice", 
        filters={"eboekhouden_invoice_number": ["is", "set"]})
    
    sales_invoices = frappe.db.count("Sales Invoice",
        filters={"eboekhouden_invoice_number": ["is", "set"]})
    
    # Get some samples
    purchase_samples = frappe.db.get_all("Purchase Invoice",
        filters={"eboekhouden_invoice_number": ["is", "set"]},
        fields=["name", "eboekhouden_invoice_number", "posting_date", "supplier"],
        limit=5,
        order_by="creation desc"
    )
    
    return {
        "purchase_invoices": purchase_invoices,
        "sales_invoices": sales_invoices,
        "recent_purchases": purchase_samples
    }

if __name__ == "__main__":
    print(count_invoices())