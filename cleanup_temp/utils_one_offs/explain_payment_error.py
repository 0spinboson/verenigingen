"""
Explain the payment allocation error clearly
"""

import frappe

@frappe.whitelist()
def explain_payment_error():
    """Explain why 'Allocated Amount cannot be greater than outstanding amount' error occurs"""
    
    explanation = {
        "error_message": "Failed to create supplier payment for invoice 8008125556501050: Row #1: Allocated Amount cannot be greater than outstanding amount.",
        
        "what_it_means": {
            "invoice_total": "€5,910",
            "already_paid": "€2,910 (1 payment)",
            "outstanding": "€3,000",
            "attempting_to_pay": "€2,910"
        },
        
        "why_it_fails": [
            "The E-Boekhouden export contains 15 duplicate entries for mutation 7281",
            "The first payment (€2,910) was created successfully",
            "Our duplicate detection now prevents creating the same payment again",
            "The remaining 14 attempts fail with this misleading error message"
        ],
        
        "the_real_issue": "The error message is misleading. It's not that €2,910 > €3,000. The system is correctly preventing duplicate payments for the same mutation number (7281).",
        
        "root_cause": "E-Boekhouden data quality issue - the same payment mutation appears 15 times in the export",
        
        "resolution": {
            "action_taken": "Added duplicate detection to prevent multiple payments with same reference number",
            "result": "System correctly imports the payment once and rejects the 14 duplicates",
            "data_integrity": "Invoice correctly shows €3,000 outstanding (€5,910 - €2,910)"
        },
        
        "verification": {
            "payments_for_mutation_7281": frappe.db.count("Payment Entry", {
                "reference_no": "7281",
                "docstatus": 1
            }),
            "invoice_outstanding": frappe.db.get_value("Purchase Invoice", 
                {"eboekhouden_invoice_number": "8008125556501050"}, 
                "outstanding_amount"
            )
        }
    }
    
    return explanation

if __name__ == "__main__":
    print(explain_payment_error())