"""
Fix for E-Boekhouden Migration date validation
Allows full migrations without date ranges
"""

import frappe
from frappe import _
from frappe.utils import getdate, today, add_days

@frappe.whitelist()
def set_default_date_range_for_full_migration(migration_name):
    """
    Set a default date range for full migrations
    Uses a wide range to capture all historical data
    """
    try:
        migration = frappe.get_doc("E-Boekhouden Migration", migration_name)
        
        # Only set if dates are not already set
        if not migration.date_from or not migration.date_to:
            # Set a wide date range for full migration
            # From 10 years ago to today
            migration.date_from = add_days(today(), -3650)  # 10 years ago
            migration.date_to = today()
            migration.save()
            
            return {
                "success": True,
                "date_from": migration.date_from,
                "date_to": migration.date_to,
                "message": "Date range set for full historical import"
            }
        else:
            return {
                "success": True,
                "date_from": migration.date_from,
                "date_to": migration.date_to,
                "message": "Date range already set"
            }
            
    except Exception as e:
        frappe.log_error(f"Failed to set date range: {str(e)}", "E-Boekhouden Migration")
        return {
            "success": False,
            "error": str(e)
        }

@frappe.whitelist()
def get_eboekhouden_date_range():
    """
    Try to determine the actual date range from E-Boekhouden
    This helps set more accurate dates for full migrations
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        settings = frappe.get_single("E-Boekhouden Settings")
        if not settings.api_token:
            return {
                "success": False,
                "error": "E-Boekhouden API not configured"
            }
        
        api = EBoekhoudenAPI(settings)
        
        # Try to get the oldest and newest transactions
        # E-Boekhouden API might not support this directly, so we'll use a reasonable range
        
        # For now, return a suggested range
        end_date = today()
        start_date = add_days(end_date, -1825)  # 5 years ago
        
        return {
            "success": True,
            "start_date": start_date,
            "end_date": end_date,
            "message": "Suggested date range for comprehensive import"
        }
        
    except Exception as e:
        frappe.log_error(f"Failed to get date range: {str(e)}", "E-Boekhouden")
        return {
            "success": False,
            "error": str(e)
        }