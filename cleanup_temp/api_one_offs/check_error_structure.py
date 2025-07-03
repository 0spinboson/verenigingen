import frappe

@frappe.whitelist()
def get_error_log_structure():
    """Get Error Log table structure"""
    
    # Get column names from database
    columns = frappe.db.sql("""
        DESCRIBE `tabError Log`
    """, as_dict=True)
    
    return {"columns": [c.Field for c in columns]}