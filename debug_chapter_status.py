import frappe

@frappe.whitelist()
def debug_chapter_status():
    """Debug the status field issue in Chapter"""
    
    # Check if there's a custom field
    custom_fields = frappe.get_all("Custom Field", 
        filters={"dt": "Chapter", "fieldname": "status"},
        fields=["*"]
    )
    
    # Check property setters
    property_setters = frappe.get_all("Property Setter",
        filters={"doc_type": "Chapter", "property": "reqd", "field_name": "status"},
        fields=["*"]
    )
    
    # Check actual table structure
    table_fields = frappe.db.sql("""
        SELECT COLUMN_NAME, IS_NULLABLE, DATA_TYPE, COLUMN_DEFAULT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'tabChapter'
        AND COLUMN_NAME = 'status'
    """, as_dict=True)
    
    # Check if field exists in doctype definition
    meta = frappe.get_meta("Chapter")
    status_field = None
    for field in meta.fields:
        if field.fieldname == "status":
            status_field = {
                "fieldname": field.fieldname,
                "fieldtype": field.fieldtype,
                "label": field.label,
                "reqd": field.reqd,
                "default": field.default
            }
            break
    
    return {
        "custom_fields": custom_fields,
        "property_setters": property_setters,
        "table_fields": table_fields,
        "doctype_field": status_field
    }

if __name__ == "__main__":
    frappe.init(site="dev.veganisme.net")
    frappe.connect()
    import json
    print(json.dumps(debug_chapter_status(), indent=2))
    frappe.destroy()