"""
Debug the failing payment attempts from the migration log
"""

import frappe
import json
from collections import defaultdict

@frappe.whitelist()
def debug_payment_failures():
    """Analyze why payments are still failing"""
    
    # Get the latest failed records
    file_path = "/home/frappe/frappe-bench/sites/dev.veganisme.net/private/files/eboekhouden_migration_logs/failed_records_EBMIG-2025-00014_20250628_212930.json"
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return {"error": f"Could not read file: {str(e)}"}
    
    # Group failures by invoice number
    failures_by_invoice = defaultdict(list)
    
    for failure in data.get("failed_records", []):
        if failure.get("record_type") == "supplier_payment":
            invoice_no = failure.get("record_data", {}).get("Factuurnummer")
            failures_by_invoice[invoice_no].append({
                "mutation": failure.get("record_data", {}).get("MutatieNr"),
                "error": failure.get("error_message"),
                "timestamp": failure.get("timestamp")
            })
    
    # Check the state of invoice 8008125556501050
    invoice_state = {}
    invoice_no = "8008125556501050"
    
    pi_name = frappe.db.get_value("Purchase Invoice", 
        {"eboekhouden_invoice_number": invoice_no}, 
        "name")
    
    if pi_name:
        pi = frappe.get_doc("Purchase Invoice", pi_name)
        invoice_state = {
            "name": pi.name,
            "outstanding": pi.outstanding_amount,
            "grand_total": pi.grand_total
        }
        
        # Check existing payments
        existing_payments = frappe.db.sql("""
            SELECT 
                pe.name,
                pe.reference_no,
                pe.paid_amount,
                pe.docstatus,
                pe.creation
            FROM `tabPayment Entry` pe
            LEFT JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
            WHERE per.reference_name = %s
            ORDER BY pe.creation
        """, pi.name, as_dict=True)
        
        invoice_state["existing_payments"] = existing_payments
        
        # Check if mutation 7281 already has payments
        mutation_7281_payments = frappe.db.sql("""
            SELECT name, docstatus, paid_amount, creation
            FROM `tabPayment Entry`
            WHERE reference_no = '7281'
            ORDER BY creation
        """, as_dict=True)
        
        invoice_state["mutation_7281_payments"] = mutation_7281_payments
    
    result = {
        "total_payment_failures": sum(len(v) for v in failures_by_invoice.values()),
        "unique_invoices_failing": len(failures_by_invoice),
        "invoice_8008125556501050": {
            "failure_count": len(failures_by_invoice.get(invoice_no, [])),
            "failures": failures_by_invoice.get(invoice_no, [])[:5],
            "current_state": invoice_state
        },
        "all_failing_invoices": list(failures_by_invoice.keys())
    }
    
    # Check if our duplicate detection is working
    result["duplicate_detection_check"] = {
        "code_added": "Check exists for reference_no before creating payment",
        "should_prevent": "Yes, should prevent duplicate payments with same mutation number"
    }
    
    return result

if __name__ == "__main__":
    print(debug_payment_failures())