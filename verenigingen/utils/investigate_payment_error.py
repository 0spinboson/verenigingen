"""
Investigate why payment allocation is failing
"""

import frappe

@frappe.whitelist()
def investigate_payment_allocation_error():
    """Check why the payment allocation is failing for invoice 8008125556501050"""
    
    # Get the invoice
    invoice = frappe.get_doc("Purchase Invoice", 
        {"eboekhouden_invoice_number": "8008125556501050"})
    
    result = {
        "invoice": {
            "name": invoice.name,
            "grand_total": invoice.grand_total,
            "outstanding_amount": invoice.outstanding_amount,
            "status": invoice.status,
            "rounded_total": invoice.rounded_total if hasattr(invoice, 'rounded_total') else None,
            "rounding_adjustment": invoice.rounding_adjustment if hasattr(invoice, 'rounding_adjustment') else None
        }
    }
    
    # Check if there are any pending/draft payments
    all_payments = frappe.db.sql("""
        SELECT 
            pe.name,
            pe.paid_amount,
            pe.docstatus,
            pe.reference_no,
            per.allocated_amount,
            pe.creation
        FROM `tabPayment Entry` pe
        LEFT JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
        WHERE per.reference_name = %s
        ORDER BY pe.creation DESC
    """, invoice.name, as_dict=True)
    
    result["all_payments_for_invoice"] = all_payments
    
    # Calculate total allocated
    total_allocated = sum(p['allocated_amount'] for p in all_payments if p['docstatus'] == 1)
    result["total_allocated"] = total_allocated
    result["calculated_outstanding"] = invoice.grand_total - total_allocated
    
    # Check if there are any advance payments or other adjustments
    result["advance_paid"] = invoice.advance_paid if hasattr(invoice, 'advance_paid') else 0
    result["write_off_amount"] = invoice.write_off_amount if hasattr(invoice, 'write_off_amount') else 0
    
    # Test creating a payment to see the exact error
    try:
        test_pe = frappe.new_doc("Payment Entry")
        test_pe.payment_type = "Pay"
        test_pe.company = invoice.company
        test_pe.posting_date = frappe.utils.today()
        test_pe.party_type = "Supplier"
        test_pe.party = invoice.supplier
        test_pe.paid_amount = 2910.0
        test_pe.received_amount = 2910.0
        test_pe.reference_no = "TEST-7281"
        
        # Get accounts
        test_pe.paid_from = frappe.db.get_value("Account", {
            "company": invoice.company,
            "account_type": "Bank",
            "is_group": 0
        }, "name")
        test_pe.paid_to = invoice.credit_to
        
        # Add reference
        test_pe.append("references", {
            "reference_doctype": "Purchase Invoice",
            "reference_name": invoice.name,
            "allocated_amount": 2910.0
        })
        
        # Validate without saving
        test_pe.validate()
        result["test_payment"] = "Would succeed"
        
    except Exception as e:
        result["test_payment_error"] = str(e)
        
        # Try with exact outstanding amount
        try:
            test_pe2 = frappe.new_doc("Payment Entry")
            test_pe2.payment_type = "Pay"
            test_pe2.company = invoice.company
            test_pe2.posting_date = frappe.utils.today()
            test_pe2.party_type = "Supplier"
            test_pe2.party = invoice.supplier
            test_pe2.paid_amount = invoice.outstanding_amount
            test_pe2.received_amount = invoice.outstanding_amount
            test_pe2.reference_no = "TEST-EXACT"
            test_pe2.paid_from = test_pe.paid_from
            test_pe2.paid_to = test_pe.paid_to
            
            test_pe2.append("references", {
                "reference_doctype": "Purchase Invoice",
                "reference_name": invoice.name,
                "allocated_amount": invoice.outstanding_amount
            })
            
            test_pe2.validate()
            result["test_with_exact_amount"] = f"Would succeed with amount {invoice.outstanding_amount}"
            
        except Exception as e2:
            result["test_with_exact_amount_error"] = str(e2)
    
    return result

if __name__ == "__main__":
    print(investigate_payment_allocation_error())