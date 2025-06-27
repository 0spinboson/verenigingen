"""
E-Boekhouden Migration Status Utilities

This module provides utilities for checking migration status and capabilities
to support the new capability-based UI in the migration doctype.
"""

import frappe
from frappe import _


@frappe.whitelist()
def get_migration_capabilities(migration_name):
    """
    Get the capabilities of a migration based on its current state
    
    Returns a dict with:
    - can_migrate: Whether new migrations can be started
    - can_post_process: Whether post-migration tools should be shown
    - has_history: Whether migration history exists
    - is_running: Whether a migration is currently in progress
    - can_reset: Whether the migration can be reset to draft
    """
    try:
        if not frappe.db.exists("E-Boekhouden Migration", migration_name):
            return {
                "success": False,
                "error": "Migration not found"
            }
        
        migration = frappe.get_doc("E-Boekhouden Migration", migration_name)
        
        # Check if any migration has been run
        has_history = (
            migration.imported_records > 0 or 
            migration.total_records > 0 or
            migration.migration_status == "Completed"
        )
        
        # Check if migration is currently running
        is_running = migration.migration_status == "In Progress"
        
        # Check if can start new migration
        can_migrate = (
            migration.docstatus == 0 and  # Not submitted
            migration.migration_status != "In Progress"  # Not currently running
        )
        
        # Check if post-migration tools should be available
        can_post_process = has_history and not is_running
        
        # Check if can reset
        can_reset = migration.migration_status == "Failed"
        
        return {
            "success": True,
            "capabilities": {
                "can_migrate": can_migrate,
                "can_post_process": can_post_process,
                "has_history": has_history,
                "is_running": is_running,
                "can_reset": can_reset,
                "status": migration.migration_status,
                "docstatus": migration.docstatus,
                "imported_records": migration.imported_records,
                "total_records": migration.total_records,
                "failed_records": migration.failed_records
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting migration capabilities: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def check_running_migrations():
    """
    Check if any migrations are currently running
    This can be used to prevent multiple simultaneous migrations
    """
    try:
        running_migrations = frappe.get_all(
            "E-Boekhouden Migration",
            filters={"migration_status": "In Progress"},
            fields=["name", "migration_name", "current_operation", "progress_percentage"]
        )
        
        return {
            "success": True,
            "is_running": len(running_migrations) > 0,
            "running_migrations": running_migrations
        }
        
    except Exception as e:
        frappe.log_error(f"Error checking running migrations: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def update_migration_status(migration_name, new_status):
    """
    Update the status of a migration
    Used to implement the new status flow
    """
    try:
        valid_statuses = ["Draft", "In Progress", "Completed", "Failed", "Cancelled"]
        
        if new_status not in valid_statuses:
            return {
                "success": False,
                "error": f"Invalid status: {new_status}"
            }
        
        migration = frappe.get_doc("E-Boekhouden Migration", migration_name)
        
        # Validate status transitions
        current_status = migration.migration_status
        
        # Define valid transitions
        valid_transitions = {
            "Draft": ["In Progress", "Cancelled"],
            "In Progress": ["Completed", "Failed", "Cancelled"],
            "Completed": ["Draft"],  # Allow reset for re-migration
            "Failed": ["Draft"],  # Allow reset to retry
            "Cancelled": ["Draft"]  # Allow reset to retry
        }
        
        if new_status not in valid_transitions.get(current_status, []):
            return {
                "success": False,
                "error": f"Cannot transition from {current_status} to {new_status}"
            }
        
        # Update status
        migration.migration_status = new_status
        
        # Clear error log if resetting to draft
        if new_status == "Draft":
            migration.error_log = ""
            migration.current_operation = ""
            migration.progress_percentage = 0
        
        migration.save()
        
        return {
            "success": True,
            "message": f"Status updated to {new_status}"
        }
        
    except Exception as e:
        frappe.log_error(f"Error updating migration status: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def get_migration_summary_stats():
    """
    Get summary statistics for all migrations
    Useful for showing overall migration history
    """
    try:
        # Get all migrations
        migrations = frappe.get_all(
            "E-Boekhouden Migration",
            fields=[
                "name", "migration_name", "migration_status", 
                "imported_records", "failed_records", "total_records",
                "start_time", "end_time", "company"
            ],
            order_by="creation desc"
        )
        
        # Calculate totals
        total_imported = sum(m.get("imported_records", 0) for m in migrations)
        total_failed = sum(m.get("failed_records", 0) for m in migrations)
        total_processed = sum(m.get("total_records", 0) for m in migrations)
        
        # Count by status
        status_counts = {}
        for m in migrations:
            status = m.get("migration_status", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "success": True,
            "summary": {
                "total_migrations": len(migrations),
                "total_imported": total_imported,
                "total_failed": total_failed,
                "total_processed": total_processed,
                "status_counts": status_counts,
                "recent_migrations": migrations[:5]  # Last 5 migrations
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting migration summary: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }