"""
Analyze failures from EBMIG-2025-00013
"""

import frappe
import json
from collections import defaultdict

@frappe.whitelist()
def analyze_migration_13():
    """Analyze the failed records from migration 13"""
    
    file_path = "/home/frappe/frappe-bench/sites/dev.veganisme.net/private/files/eboekhouden_migration_logs/failed_records_EBMIG-2025-00013_20250628_212253.json"
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return {"error": f"Could not read file: {str(e)}"}
    
    # Categorize failures by type
    failure_types = defaultdict(int)
    failure_samples = defaultdict(list)
    
    for failure in data.get("failed_records", []):
        record_type = failure.get("record_type", "unknown")
        failure_types[record_type] += 1
        
        # Collect samples of each type (max 3)
        if len(failure_samples[record_type]) < 3:
            failure_samples[record_type].append({
                "error": failure.get("error_message", ""),
                "data_sample": {
                    "MutatieNr": failure.get("record_data", {}).get("MutatieNr"),
                    "Soort": failure.get("record_data", {}).get("Soort"),
                    "Factuurnummer": failure.get("record_data", {}).get("Factuurnummer")
                }
            })
    
    # Check specific mutation types
    mutation_types = defaultdict(int)
    for failure in data.get("failed_records", []):
        if failure.get("record_type") in ["sales_invoice", "purchase_invoice", "journal_entry", "payment"]:
            soort = failure.get("record_data", {}).get("Soort")
            if soort:
                mutation_types[soort] += 1
    
    # Count invoices that already exist
    existing_invoices = 0
    for failure in data.get("failed_records", []):
        if "already exists" in failure.get("error_message", "").lower():
            existing_invoices += 1
    
    return {
        "total_failures": data.get("total_failed", 0),
        "failure_types": dict(failure_types),
        "failure_samples": dict(failure_samples),
        "mutation_types": dict(mutation_types),
        "existing_invoices": existing_invoices,
        "migration_info": {
            "name": data.get("migration_name"),
            "timestamp": data.get("timestamp")
        }
    }

if __name__ == "__main__":
    print(analyze_migration_13())