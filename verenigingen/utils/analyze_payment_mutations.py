"""
Analyze payment mutation structure
"""

import frappe
import json

@frappe.whitelist()
def analyze_payment_structure():
    """Check the structure of payment mutations"""
    
    file_path = "/home/frappe/frappe-bench/sites/dev.veganisme.net/private/files/eboekhouden_migration_logs/failed_records_EBMIG-2025-00013_20250628_212253.json"
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return {"error": f"Could not read file: {str(e)}"}
    
    # Get sample payment mutations
    payment_samples = []
    
    for failure in data.get("failed_records", []):
        if failure.get("record_type") == "supplier_payment" and len(payment_samples) < 5:
            record_data = failure.get("record_data", {})
            # Extract all fields to see what's available
            payment_samples.append({
                "MutatieNr": record_data.get("MutatieNr"),
                "Soort": record_data.get("Soort"),
                "Factuurnummer": record_data.get("Factuurnummer"),
                "Datum": record_data.get("Datum"),
                "Bedrag": record_data.get("Bedrag"),
                "available_fields": list(record_data.keys()),
                "full_data": record_data
            })
    
    # Check if there's a pattern in the amount field
    amount_fields = defaultdict(int)
    for failure in data.get("failed_records", []):
        if failure.get("record_type") == "supplier_payment":
            record_data = failure.get("record_data", {})
            # Check various possible amount field names
            for field in record_data.keys():
                if any(term in field.lower() for term in ["bedrag", "amount", "total", "betaal"]):
                    amount_fields[field] += 1
    
    return {
        "payment_samples": payment_samples[:3],  # First 3 samples
        "possible_amount_fields": dict(amount_fields),
        "total_payment_failures": sum(1 for f in data.get("failed_records", []) if f.get("record_type") == "supplier_payment")
    }

from collections import defaultdict

if __name__ == "__main__":
    print(analyze_payment_structure())