import frappe
import json
from frappe import _

@frappe.whitelist()
def test_migration_fixes():
    """Test the migration fixes"""
    
    # Get the latest failed migration
    latest_migration = frappe.db.get_value(
        "E-Boekhouden Migration", 
        {"migration_status": ["in", ["Failed", "In Progress"]]},
        ["name", "migration_status", "error_log"],
        order_by="creation desc",
        as_dict=True
    )
    
    if not latest_migration:
        return {"message": "No failed or in-progress migrations found"}
    
    # Check error logs for the specific errors we fixed
    error_logs = frappe.db.sql("""
        SELECT title, creation
        FROM `tabError Log`
        WHERE title LIKE '%mutation_type_distribution%'
           OR title LIKE '%Duplicate entry%'
           OR LENGTH(title) >= 140
        ORDER BY creation DESC
        LIMIT 5
    """, as_dict=True)
    
    # Check error logs instead since E-Boekhouden Migration Error table doesn't exist
    migration_errors = frappe.db.sql("""
        SELECT title, method
        FROM `tabError Log`
        WHERE method LIKE '%E-Boekhouden Migration%'
          AND title LIKE '%Mutation type distribution%'
        ORDER BY creation DESC
        LIMIT 1
    """, as_dict=True)
    
    result = {
        "latest_migration": latest_migration.name,
        "status": latest_migration.migration_status,
        "recent_error_logs": error_logs,
        "mutation_distribution_logged": len(migration_errors) > 0,
        "mutation_distribution": migration_errors[0] if migration_errors else None
    }
    
    # Check if we can get mutation type distribution
    if migration_errors and migration_errors[0]:
        try:
            # Extract JSON from error title
            msg = migration_errors[0].title
            if "Mutation type distribution:" in msg:
                json_str = msg.split("Mutation type distribution:")[1].strip()
                distribution = json.loads(json_str)
                result["parsed_distribution"] = distribution
        except:
            pass
    
    return result

@frappe.whitelist()
def get_latest_migration_status():
    """Get the status of the latest migration"""
    
    latest = frappe.db.get_value(
        "E-Boekhouden Migration",
        {},
        ["name", "migration_status", "total_records", "imported_records", "failed_records", "current_operation"],
        order_by="creation desc",
        as_dict=True
    )
    
    if not latest:
        return {"message": "No migrations found"}
    
    # Get recent errors from Error Log table
    recent_errors = frappe.db.sql("""
        SELECT title, method, creation
        FROM `tabError Log`
        WHERE method LIKE '%E-Boekhouden Migration%'
        ORDER BY creation DESC
        LIMIT 10
    """, as_dict=True)
    
    latest["recent_errors"] = recent_errors
    
    return latest