"""
Check which account types are available in ERPNext
"""

import frappe
from frappe import _


@frappe.whitelist()
def get_available_account_types():
    """Get all available account types in ERPNext"""
    try:
        # Get the Account DocType meta
        account_meta = frappe.get_meta("Account")
        
        # Find the account_type field
        account_type_field = None
        for field in account_meta.fields:
            if field.fieldname == "account_type":
                account_type_field = field
                break
        
        if not account_type_field:
            return {
                "success": False,
                "error": "account_type field not found"
            }
        
        # Get the options (available values)
        account_types = []
        if account_type_field.options:
            account_types = [t.strip() for t in account_type_field.options.split("\n") if t.strip()]
        
        # Also check what's actually used in the database
        used_types = frappe.db.sql("""
            SELECT DISTINCT account_type 
            FROM `tabAccount` 
            WHERE account_type IS NOT NULL 
            AND account_type != ''
            ORDER BY account_type
        """, as_dict=True)
        
        # Get root types as well
        root_types = frappe.db.sql("""
            SELECT DISTINCT root_type 
            FROM `tabAccount` 
            WHERE root_type IS NOT NULL 
            ORDER BY root_type
        """, as_dict=True)
        
        return {
            "success": True,
            "defined_account_types": account_types,
            "used_account_types": [d.account_type for d in used_types],
            "root_types": [d.root_type for d in root_types],
            "field_info": {
                "fieldtype": account_type_field.fieldtype,
                "options": account_type_field.options
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error checking account types: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }