#!/usr/bin/env python
"""Check E-Boekhouden fields in Sales Invoice"""

import frappe

@frappe.whitelist()
def check_sales_invoice_fields():
    """Check what E-Boekhouden related fields exist in Sales Invoice"""
    
    # Get all columns for Sales Invoice table
    columns = frappe.db.get_table_columns("Sales Invoice")
    
    # Filter for E-Boekhouden related columns
    eboekhouden_fields = [col for col in columns if 'boekhouden' in col.lower()]
    
    # Also check custom fields
    custom_fields = frappe.get_all("Custom Field", 
        filters={"dt": "Sales Invoice"},
        fields=["fieldname", "label", "fieldtype"])
    
    eboekhouden_custom_fields = [
        field for field in custom_fields 
        if 'boekhouden' in field.fieldname.lower() or 
           'boekhouden' in (field.label or '').lower()
    ]
    
    # Check for any sales invoices with E-Boekhouden data
    sample_invoices = []
    if eboekhouden_fields:
        for field in eboekhouden_fields:
            invoices = frappe.db.sql(f"""
                SELECT name, {field} 
                FROM `tabSales Invoice` 
                WHERE {field} IS NOT NULL 
                AND {field} != ''
                LIMIT 5
            """, as_dict=True)
            if invoices:
                sample_invoices.append({
                    "field": field,
                    "invoices": invoices
                })
    
    return {
        "table_columns": columns,
        "eboekhouden_columns": eboekhouden_fields,
        "custom_fields": eboekhouden_custom_fields,
        "sample_invoices": sample_invoices
    }


if __name__ == "__main__":
    result = check_sales_invoice_fields()
    print("E-Boekhouden fields in Sales Invoice:")
    print(f"Table columns: {result['eboekhouden_columns']}")
    print(f"Custom fields: {result['custom_fields']}")
    print(f"Sample invoices: {result['sample_invoices']}")