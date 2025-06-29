"""
Retry failed supplier payments from migration
"""

import frappe
import json
from verenigingen.utils.eboekhouden_soap_migration import process_supplier_payments

@frappe.whitelist()
def retry_supplier_payments(migration_name="EBMIG-2025-00013"):
    """Retry all failed supplier payments from a migration"""
    
    # Get the failed records file
    file_path = f"/home/frappe/frappe-bench/sites/dev.veganisme.net/private/files/eboekhouden_migration_logs/failed_records_{migration_name}_20250628_212253.json"
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return {"error": f"Could not read file: {str(e)}"}
    
    # Extract supplier payment failures
    supplier_payment_mutations = []
    
    for failure in data.get("failed_records", []):
        if failure.get("record_type") == "supplier_payment":
            mutation = failure.get("record_data", {})
            if mutation:
                supplier_payment_mutations.append(mutation)
    
    if not supplier_payment_mutations:
        return {"message": "No failed supplier payments found"}
    
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
        {"message": f"Retrying {len(supplier_payment_mutations)} failed supplier payments..."},
        user=frappe.session.user
    )
    
    # Process the mutations
    result = process_supplier_payments(supplier_payment_mutations, company, cost_center, migration_doc)
    
    result["total_attempted"] = len(supplier_payment_mutations)
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
        "errors": result["errors"][:20]  # First 20 errors
    }
    
    # Save retry log
    log_filename = f"retry_supplier_payments_{migration_name}_{frappe.utils.now().replace(' ', '_').replace(':', '')}.json"
    log_path = f"/home/frappe/frappe-bench/sites/dev.veganisme.net/private/files/eboekhouden_migration_logs/{log_filename}"
    
    with open(log_path, 'w') as f:
        json.dump(retry_log, f, indent=2)
    
    result["log_file"] = log_filename
    
    # Get a sample of what was processed
    if result["created"] > 0:
        recent_payments = frappe.db.get_all("Payment Entry",
            filters={
                "payment_type": "Pay",
                "party_type": "Supplier",
                "creation": [">=", frappe.utils.add_to_date(frappe.utils.now(), minutes=-5)]
            },
            fields=["name", "party", "paid_amount", "posting_date"],
            limit=5,
            order_by="creation desc"
        )
        result["sample_created"] = recent_payments
    
    return result

if __name__ == "__main__":
    print(retry_supplier_payments())