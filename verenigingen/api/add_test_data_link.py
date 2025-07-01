"""
Add test data generation link to workspace or navigation
"""

import frappe
from frappe import _


@frappe.whitelist()
def get_test_data_info():
    """
    Get information about test data generation
    """
    return {
        "url": "/generate_test_data",
        "title": _("Generate Test Data"),
        "description": _("Create sample members to explore Verenigingen features"),
        "icon": "fa fa-database",
        "message": "Visit /generate_test_data to create test members for exploring the system"
    }


@frappe.whitelist()
def create_test_data_shortcut():
    """
    Create a shortcut for test data generation
    """
    try:
        # Check if shortcut already exists
        existing = frappe.db.exists("Workspace Shortcut", {
            "link_to": "/generate_test_data",
            "type": "URL"
        })
        
        if not existing:
            # Create shortcut
            shortcut = frappe.new_doc("Workspace Shortcut")
            shortcut.label = "Generate Test Data"
            shortcut.type = "URL"
            shortcut.link_to = "/generate_test_data"
            shortcut.icon = "database"
            shortcut.insert(ignore_permissions=True)
            
            return {
                "success": True,
                "message": "Test data shortcut created",
                "shortcut": shortcut.name
            }
        else:
            return {
                "success": True,
                "message": "Test data shortcut already exists",
                "existing": existing
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }