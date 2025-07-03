"""
Analyze all failed purchase invoices to find patterns
"""

import frappe
import json
from frappe.utils import getdate, add_days

@frappe.whitelist()
def analyze_failed_invoices():
    """Analyze the failed records to find patterns"""
    
    # Read the failed records file
    file_path = "/home/frappe/frappe-bench/sites/dev.veganisme.net/private/files/eboekhouden_migration_logs/failed_records_EBMIG-2025-00012_20250628_205311.json"
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return {"error": f"Could not read file: {str(e)}"}
    
    purchase_invoice_failures = []
    
    for failure in data.get("failed_records", []):
        if failure.get("record_type") == "purchase_invoice":
            record = failure.get("record_data", {})
            
            # Parse the dates
            datum = record.get("Datum")
            posting_date = datum.split('T')[0] if datum and 'T' in datum else datum
            payment_terms_str = record.get("Betalingstermijn", "30")
            
            try:
                payment_terms = int(payment_terms_str)
            except:
                payment_terms = 30
            
            # Calculate what the due date would be
            if posting_date:
                calculated_due_date = add_days(posting_date, payment_terms)
                comparison = getdate(calculated_due_date) >= getdate(posting_date)
            else:
                calculated_due_date = None
                comparison = None
            
            analysis = {
                "invoice_no": record.get("Factuurnummer"),
                "datum": datum,
                "posting_date": posting_date,
                "payment_terms_str": payment_terms_str,
                "payment_terms_int": payment_terms,
                "calculated_due_date": calculated_due_date,
                "comparison_valid": comparison,
                "error": failure.get("error_message")
            }
            
            purchase_invoice_failures.append(analysis)
    
    # Look for patterns
    patterns = {
        "total_failures": len(purchase_invoice_failures),
        "negative_payment_terms": sum(1 for f in purchase_invoice_failures if f["payment_terms_int"] < 0),
        "zero_payment_terms": sum(1 for f in purchase_invoice_failures if f["payment_terms_int"] == 0),
        "invalid_dates": sum(1 for f in purchase_invoice_failures if not f["posting_date"]),
        "would_fail_validation": sum(1 for f in purchase_invoice_failures if f["comparison_valid"] is False)
    }
    
    # Get samples of each type
    samples = {
        "negative_terms": [f for f in purchase_invoice_failures if f["payment_terms_int"] < 0][:3],
        "zero_terms": [f for f in purchase_invoice_failures if f["payment_terms_int"] == 0][:3],
        "normal_terms": [f for f in purchase_invoice_failures if f["payment_terms_int"] > 0][:3]
    }
    
    return {
        "patterns": patterns,
        "samples": samples,
        "all_failures": purchase_invoice_failures[:10]  # First 10 for inspection
    }

if __name__ == "__main__":
    print(analyze_failed_invoices())