#!/usr/bin/env python
"""Create the eboekhouden_grootboek_nummer custom field for Account doctype"""

import frappe

@frappe.whitelist()
def create_eboekhouden_account_field():
    """Create custom field for E-Boekhouden account number"""
    try:
        # Check if field already exists
        if frappe.db.exists("Custom Field", {"dt": "Account", "fieldname": "eboekhouden_grootboek_nummer"}):
            return {"success": True, "message": "Field already exists"}
        
        # Create the custom field
        custom_field = frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Account",
            "fieldname": "eboekhouden_grootboek_nummer",
            "fieldtype": "Data",
            "label": "E-Boekhouden Account Number",
            "insert_after": "account_number",
            "description": "Account number from E-Boekhouden system",
            "search_index": 1,
            "permlevel": 0,
            "module": "Verenigingen"
        })
        
        custom_field.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Clear cache
        frappe.clear_cache(doctype="Account")
        
        return {
            "success": True,
            "message": "E-Boekhouden Account Number field created successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating custom field: {str(e)}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    print("Creating E-Boekhouden custom field...")
    result = create_eboekhouden_account_field()
    print(result)