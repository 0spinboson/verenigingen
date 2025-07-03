"""
Check the current status of payment 7281
"""

import frappe

@frappe.whitelist()
def check_payment_7281():
    """Check the current state of mutation 7281 payment"""
    
    # Check payments with reference 7281
    payments_7281 = frappe.db.sql("""
        SELECT name, reference_no, paid_amount, docstatus, creation
        FROM `tabPayment Entry`
        WHERE reference_no = '7281'
    """, as_dict=True)
    
    # Check the invoice
    invoice = frappe.db.get_value("Purchase Invoice",
        {"eboekhouden_invoice_number": "8008125556501050"},
        ["name", "grand_total", "outstanding_amount"],
        as_dict=True
    )
    
    # Check all payments for this invoice
    invoice_payments = []
    if invoice:
        invoice_payments = frappe.db.sql("""
            SELECT pe.name, pe.reference_no, pe.paid_amount, pe.docstatus
            FROM `tabPayment Entry` pe
            JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
            WHERE per.reference_name = %s
            ORDER BY pe.creation
        """, invoice.name, as_dict=True)
    
    return {
        "payments_with_ref_7281": payments_7281,
        "invoice_state": invoice,
        "all_invoice_payments": invoice_payments,
        "summary": {
            "expected": "1 payment of €2,910 for mutation 7281",
            "actual": f"{len([p for p in payments_7281 if p['docstatus'] == 1])} active payments"
        }
    }

if __name__ == "__main__":
    print(check_payment_7281())