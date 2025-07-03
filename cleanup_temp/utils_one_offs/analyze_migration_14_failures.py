"""
Analyze failures from EBMIG-2025-00014 to see what's still failing
"""

import frappe
import json
from collections import defaultdict

@frappe.whitelist()
def analyze_latest_failures():
    """Analyze the failed records from migration 14"""
    
    file_path = "/home/frappe/frappe-bench/sites/dev.veganisme.net/private/files/eboekhouden_migration_logs/failed_records_EBMIG-2025-00014_20250628_212930.json"
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return {"error": f"Could not read file: {str(e)}"}
    
    # Categorize failures
    failure_types = defaultdict(int)
    error_patterns = defaultdict(int)
    
    for failure in data.get("failed_records", []):
        record_type = failure.get("record_type", "unknown")
        failure_types[record_type] += 1
        
        # Extract error patterns
        error_msg = failure.get("error_message", "")
        if "Paid Amount is mandatory" in error_msg:
            error_patterns["paid_amount_mandatory"] += 1
        elif "Allocated Amount cannot be greater than outstanding amount" in error_msg:
            error_patterns["amount_greater_than_outstanding"] += 1
        elif "already exists" in error_msg:
            error_patterns["already_exists"] += 1
        elif "Due Date cannot be before" in error_msg:
            error_patterns["due_date_validation"] += 1
        else:
            error_patterns["other"] += 1
    
    # Get unique invoice numbers that are failing
    failing_invoices = set()
    for failure in data.get("failed_records", []):
        if failure.get("record_type") == "supplier_payment":
            invoice_no = failure.get("record_data", {}).get("Factuurnummer")
            if invoice_no:
                failing_invoices.add(invoice_no)
    
    # Sample of different error types
    samples = {
        "paid_amount": [],
        "outstanding": [],
        "other": []
    }
    
    for failure in data.get("failed_records", []):
        error_msg = failure.get("error_message", "")
        if "Paid Amount is mandatory" in error_msg and len(samples["paid_amount"]) < 2:
            samples["paid_amount"].append({
                "invoice": failure.get("record_data", {}).get("Factuurnummer"),
                "mutation": failure.get("record_data", {}).get("MutatieNr"),
                "error": error_msg
            })
        elif "outstanding amount" in error_msg and len(samples["outstanding"]) < 2:
            samples["outstanding"].append({
                "invoice": failure.get("record_data", {}).get("Factuurnummer"),
                "mutation": failure.get("record_data", {}).get("MutatieNr"),
                "error": error_msg
            })
        elif len(samples["other"]) < 2 and "Paid Amount" not in error_msg and "outstanding" not in error_msg:
            samples["other"].append({
                "type": failure.get("record_type"),
                "error": error_msg
            })
    
    return {
        "total_failures": data.get("total_failed", 0),
        "failure_types": dict(failure_types),
        "error_patterns": dict(error_patterns),
        "unique_failing_invoices": len(failing_invoices),
        "error_samples": samples,
        "progress": {
            "previous_run": 1602,
            "current_run": data.get("total_failed", 0),
            "improvement": 1602 - data.get("total_failed", 0)
        }
    }

if __name__ == "__main__":
    print(analyze_latest_failures())