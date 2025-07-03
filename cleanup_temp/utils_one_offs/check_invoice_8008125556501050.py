"""
Check the specific invoice that's causing payment failures
"""

import frappe

@frappe.whitelist()
def check_problem_invoice():
    """Check invoice 8008125556501050 status"""
    
    # Find the invoice
    invoice_name = frappe.db.get_value("Purchase Invoice", 
        {"eboekhouden_invoice_number": "8008125556501050"}, 
        "name")
    
    if not invoice_name:
        return {"error": "Invoice 8008125556501050 not found"}
    
    # Get invoice details
    invoice = frappe.get_doc("Purchase Invoice", invoice_name)
    
    result = {
        "invoice": {
            "name": invoice.name,
            "supplier": invoice.supplier,
            "grand_total": invoice.grand_total,
            "outstanding_amount": invoice.outstanding_amount,
            "status": invoice.status,
            "posting_date": str(invoice.posting_date),
            "due_date": str(invoice.due_date)
        }
    }
    
    # Get existing payments
    payments = frappe.db.get_all("Payment Entry Reference",
        filters={
            "reference_doctype": "Purchase Invoice",
            "reference_name": invoice_name,
            "docstatus": 1
        },
        fields=["parent", "allocated_amount"]
    )
    
    payment_details = []
    total_paid = 0
    
    for payment_ref in payments:
        payment = frappe.db.get_value("Payment Entry", payment_ref.parent, 
            ["posting_date", "paid_amount", "reference_no"], as_dict=True)
        if payment:
            payment_details.append({
                "payment_entry": payment_ref.parent,
                "allocated_amount": payment_ref.allocated_amount,
                "posting_date": str(payment.posting_date),
                "reference_no": payment.reference_no
            })
            total_paid += payment_ref.allocated_amount
    
    result["payments"] = {
        "count": len(payment_details),
        "total_paid": total_paid,
        "details": payment_details
    }
    
    # Check failed payment attempts from the log
    file_path = "/home/frappe/frappe-bench/sites/dev.veganisme.net/private/files/eboekhouden_migration_logs/failed_records_EBMIG-2025-00014_20250628_212930.json"
    
    try:
        import json
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Find all payment attempts for this invoice
        payment_attempts = []
        for failure in data.get("failed_records", []):
            if (failure.get("record_type") == "supplier_payment" and 
                failure.get("record_data", {}).get("Factuurnummer") == "8008125556501050"):
                
                mut_data = failure.get("record_data", {})
                amount = 0
                for regel in mut_data.get("MutatieRegels", []):
                    amount += float(regel.get("BedragInvoer", 0))
                
                payment_attempts.append({
                    "mutation_nr": mut_data.get("MutatieNr"),
                    "date": mut_data.get("Datum"),
                    "amount": amount
                })
        
        result["failed_attempts"] = {
            "count": len(payment_attempts),
            "attempts": payment_attempts[:5]  # First 5
        }
        
    except Exception as e:
        result["log_error"] = str(e)
    
    return result

if __name__ == "__main__":
    print(check_problem_invoice())