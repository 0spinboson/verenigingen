"""
Script to update custom fields for custom amount functionality
Run this after adding the custom amount features
"""

import frappe
from verenigingen.setup import make_custom_fields

def execute():
    """Add custom fields for membership amounts"""
    try:
        print("Adding custom fields for membership amounts...")
        make_custom_fields(update=True)
        frappe.db.commit()
        print("✅ Custom fields added successfully!")
        return True
    except Exception as e:
        print(f"❌ Error adding custom fields: {str(e)}")
        frappe.log_error(f"Error adding custom fields: {str(e)}", "Custom Fields Update")
        return False

if __name__ == "__main__":
    execute()