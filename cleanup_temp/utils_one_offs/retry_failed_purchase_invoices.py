"""
Retry failed purchase invoices from the migration
"""

import frappe
import json
from verenigingen.utils.eboekhouden_soap_migration import process_purchase_invoices

@frappe.whitelist()
def retry_failed_invoices(migration_name="EBMIG-2025-00012"):
    """Retry all failed purchase invoices from a migration"""
    
    # Get the failed records file
    file_path = f"/home/frappe/frappe-bench/sites/dev.veganisme.net/private/files/eboekhouden_migration_logs/failed_records_{migration_name}_20250628_205311.json"
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return {"error": f"Could not read file: {str(e)}"}
    
    # Extract purchase invoice failures
    purchase_invoice_mutations = []
    
    for failure in data.get("failed_records", []):
        if failure.get("record_type") == "purchase_invoice":
            mutation = failure.get("record_data", {})
            if mutation:
                purchase_invoice_mutations.append(mutation)
    
    if not purchase_invoice_mutations:
        return {"message": "No failed purchase invoices found"}
    
    # Get settings
    company = "R S P"
    cost_center = frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")
    
    # Create a mock migration doc
    class MockMigrationDoc:
        def __init__(self):
            self.errors = []
            
        def log_error(self, message, record_type, data):
            self.errors.append({"message": message, "type": record_type})
    
    migration_doc = MockMigrationDoc()
    
    frappe.publish_realtime(
        "migration_progress",
        {"message": f"Retrying {len(purchase_invoice_mutations)} failed purchase invoices..."},
        user=frappe.session.user
    )
    
    # Process the mutations
    result = process_purchase_invoices(purchase_invoice_mutations, company, cost_center, migration_doc)
    
    result["total_attempted"] = len(purchase_invoice_mutations)
    result["new_errors"] = migration_doc.errors
    
    frappe.publish_realtime(
        "migration_progress",
        {"message": f"Retry complete: {result['created']} created, {len(result['errors'])} failed"},
        user=frappe.session.user
    )
    
    # Create a new log file for the retry results
    retry_log = {
        "retry_timestamp": frappe.utils.now(),
        "original_migration": migration_name,
        "total_attempted": result["total_attempted"],
        "successful": result["created"],
        "failed": len(result["errors"]),
        "errors": result["errors"]
    }
    
    # Save retry log
    log_filename = f"retry_purchase_invoices_{migration_name}_{frappe.utils.now().replace(' ', '_').replace(':', '')}.json"
    log_path = f"/home/frappe/frappe-bench/sites/dev.veganisme.net/private/files/eboekhouden_migration_logs/{log_filename}"
    
    with open(log_path, 'w') as f:
        json.dump(retry_log, f, indent=2)
    
    result["log_file"] = log_filename
    
    return result

if __name__ == "__main__":
    print(retry_failed_invoices())