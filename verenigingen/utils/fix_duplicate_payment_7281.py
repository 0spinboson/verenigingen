"""
Fix the duplicate payment for mutation 7281
"""

import frappe

@frappe.whitelist()
def fix_duplicate_payment():
    """Remove the duplicate payment and correct the invoice outstanding amount"""
    
    result = {
        "before": {},
        "actions": [],
        "after": {}
    }
    
    # Get the invoice
    invoice_name = frappe.db.get_value("Purchase Invoice", 
        {"eboekhouden_invoice_number": "8008125556501050"}, 
        "name")
    
    if not invoice_name:
        return {"error": "Invoice not found"}
    
    invoice = frappe.get_doc("Purchase Invoice", invoice_name)
    
    # Record before state
    result["before"] = {
        "invoice": invoice_name,
        "grand_total": invoice.grand_total,
        "outstanding_amount": invoice.outstanding_amount
    }
    
    # Get all payments with reference_no 7281
    payments = frappe.db.sql("""
        SELECT 
            pe.name,
            pe.creation,
            pe.paid_amount,
            pe.docstatus,
            per.allocated_amount
        FROM `tabPayment Entry` pe
        LEFT JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
        WHERE pe.reference_no = '7281'
        AND per.reference_name = %s
        ORDER BY pe.creation
    """, invoice_name, as_dict=True)
    
    result["before"]["payments"] = payments
    
    if len(payments) > 1:
        # Keep the first payment, cancel the duplicates
        for i, payment in enumerate(payments[1:], 1):
            try:
                payment_doc = frappe.get_doc("Payment Entry", payment.name)
                if payment_doc.docstatus == 1:
                    # Cancel the duplicate payment
                    payment_doc.cancel()
                    result["actions"].append(f"Cancelled duplicate payment {payment.name}")
                    
                    # Also delete it if needed
                    if frappe.db.get_value("Payment Entry", payment.name, "docstatus") == 2:
                        frappe.delete_doc("Payment Entry", payment.name)
                        result["actions"].append(f"Deleted cancelled payment {payment.name}")
            except Exception as e:
                result["actions"].append(f"Error processing {payment.name}: {str(e)}")
    
    # Refresh the invoice to get updated outstanding amount
    invoice.reload()
    
    result["after"] = {
        "invoice": invoice_name,
        "grand_total": invoice.grand_total,
        "outstanding_amount": invoice.outstanding_amount,
        "expected_outstanding": invoice.grand_total - 2910.0  # Only one payment of 2910
    }
    
    # Verify remaining payments
    remaining_payments = frappe.db.sql("""
        SELECT 
            pe.name,
            pe.paid_amount,
            pe.reference_no
        FROM `tabPayment Entry` pe
        LEFT JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
        WHERE per.reference_name = %s
        AND pe.docstatus = 1
    """, invoice_name, as_dict=True)
    
    result["after"]["remaining_payments"] = remaining_payments
    
    # If the outstanding amount is still wrong, we might need to repost the invoice
    if abs(result["after"]["outstanding_amount"] - result["after"]["expected_outstanding"]) > 0.01:
        result["needs_reposting"] = True
        result["actions"].append("Invoice may need reposting to update outstanding amount correctly")
    
    return result

if __name__ == "__main__":
    print(fix_duplicate_payment())