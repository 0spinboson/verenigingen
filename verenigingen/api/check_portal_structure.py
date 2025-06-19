"""
Check portal menu structure and capabilities
"""

import frappe

@frappe.whitelist()
def check_portal_menu_structure():
    """Check Portal Menu Item doctype structure"""
    try:
        # Get Portal Menu Item fields
        portal_menu_meta = frappe.get_meta("Portal Menu Item")
        fields = []
        for field in portal_menu_meta.fields:
            fields.append({
                "fieldname": field.fieldname,
                "fieldtype": field.fieldtype,
                "label": field.label
            })
        
        # Also check Portal Settings
        portal_settings_meta = frappe.get_meta("Portal Settings")
        settings_fields = []
        for field in portal_settings_meta.fields:
            if field.fieldtype == "Table":
                settings_fields.append({
                    "fieldname": field.fieldname,
                    "fieldtype": field.fieldtype,
                    "label": field.label,
                    "options": field.options
                })
        
        return {
            "success": True,
            "portal_menu_item_fields": fields,
            "portal_settings_table_fields": settings_fields
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }