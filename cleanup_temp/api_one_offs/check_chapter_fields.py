"""
Check Chapter doctype fields
"""

import frappe
from frappe import _

@frappe.whitelist()
def check_chapter_fields():
    """Check all fields in Chapter doctype"""
    
    # Get DocType fields
    fields = frappe.db.sql("""
        SELECT 
            fieldname,
            fieldtype,
            label,
            options,
            idx
        FROM `tabDocField`
        WHERE parent = 'Chapter'
        ORDER BY idx
    """, as_dict=True)
    
    # Get some sample chapter data
    sample_chapters = frappe.db.sql("""
        SELECT *
        FROM `tabChapter`
        LIMIT 3
    """, as_dict=True)
    
    # Get Custom Fields if any
    custom_fields = frappe.db.sql("""
        SELECT 
            fieldname,
            fieldtype,
            label
        FROM `tabCustom Field`
        WHERE dt = 'Chapter'
    """, as_dict=True)
    
    return {
        "doctype_fields": fields,
        "custom_fields": custom_fields,
        "sample_chapters": sample_chapters,
        "field_names": [f.fieldname for f in fields]
    }