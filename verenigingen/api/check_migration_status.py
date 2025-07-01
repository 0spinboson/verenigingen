import frappe

@frappe.whitelist()
def check_migration_status():
    """Check the status of E-Boekhouden migrations"""
    
    # Get recent migrations
    migrations = frappe.db.sql("""
        SELECT name, migration_status, docstatus, current_operation, 
               progress_percentage, error_log, start_time, end_time
        FROM `tabE-Boekhouden Migration`
        ORDER BY creation DESC
        LIMIT 5
    """, as_dict=True)
    
    # Check for stuck migrations
    stuck = frappe.db.sql("""
        SELECT name, start_time
        FROM `tabE-Boekhouden Migration`
        WHERE migration_status = 'In Progress'
        AND docstatus = 0
    """, as_dict=True)
    
    return {
        "recent_migrations": migrations,
        "stuck_migrations": stuck,
        "has_stuck": len(stuck) > 0
    }

@frappe.whitelist()
def reset_stuck_migration(migration_name):
    """Reset a stuck migration"""
    frappe.db.set_value("E-Boekhouden Migration", migration_name, {
        "migration_status": "Failed",
        "current_operation": "Migration was stuck and reset",
        "error_log": "Migration was manually reset due to being stuck"
    })
    frappe.db.commit()
    return {"success": True}

@frappe.whitelist()
def get_latest_migration():
    """Get the latest migration document"""
    latest = frappe.db.sql("""
        SELECT name, migration_status, current_operation, progress_percentage
        FROM `tabE-Boekhouden Migration`
        ORDER BY creation DESC
        LIMIT 1
    """, as_dict=True)
    
    if latest:
        return latest[0]
    return None

@frappe.whitelist()
def get_migration_by_name(name):
    """Get migration status by name"""
    return frappe.db.get_value('E-Boekhouden Migration', name, 
        ['migration_status', 'current_operation', 'progress_percentage', 'error_log'], 
        as_dict=True)