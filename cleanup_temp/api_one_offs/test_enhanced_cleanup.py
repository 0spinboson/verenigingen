#!/usr/bin/env python
"""Test the enhanced cleanup function"""

import frappe

@frappe.whitelist()
def test_enhanced_cleanup():
    """Test that the enhanced cleanup now properly deletes Purchase Invoices"""
    
    # Get default company
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company if settings else None
    
    if not company:
        return {"error": "No default company configured"}
    
    # Check what invoices exist before cleanup
    sales_before = frappe.db.count("Sales Invoice", {
        "company": company,
        "docstatus": ["!=", 2]
    })
    
    purchase_before = frappe.db.count("Purchase Invoice", {
        "company": company,
        "docstatus": ["!=", 2]
    })
    
    # Check E-Boekhouden specific invoices
    sales_eb = frappe.db.count("Sales Invoice", {
        "company": company,
        "eboekhouden_invoice_number": ["is", "set"],
        "docstatus": ["!=", 2]
    })
    
    purchase_eb = frappe.db.count("Purchase Invoice", {
        "company": company,
        "eboekhouden_invoice_number": ["is", "set"],
        "docstatus": ["!=", 2]
    })
    
    print(f"Before cleanup:")
    print(f"  Total Sales Invoices: {sales_before} (E-Boekhouden: {sales_eb})")
    print(f"  Total Purchase Invoices: {purchase_before} (E-Boekhouden: {purchase_eb})")
    
    # Run the cleanup
    from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import debug_cleanup_all_imported_data
    
    result = debug_cleanup_all_imported_data(company)
    
    # Check what's left after cleanup
    sales_after = frappe.db.count("Sales Invoice", {
        "company": company,
        "docstatus": ["!=", 2]
    })
    
    purchase_after = frappe.db.count("Purchase Invoice", {
        "company": company,
        "docstatus": ["!=", 2]
    })
    
    print(f"\nAfter cleanup:")
    print(f"  Total Sales Invoices: {sales_after}")
    print(f"  Total Purchase Invoices: {purchase_after}")
    print(f"\nCleanup result: {result}")
    
    return {
        "before": {
            "sales_invoices": sales_before,
            "purchase_invoices": purchase_before,
            "sales_eb": sales_eb,
            "purchase_eb": purchase_eb
        },
        "after": {
            "sales_invoices": sales_after,
            "purchase_invoices": purchase_after
        },
        "cleanup_result": result
    }


@frappe.whitelist()
def check_purchase_invoice_fields():
    """Check what fields exist on Purchase Invoice"""
    
    # Check if the custom field exists
    field_exists = frappe.db.exists("Custom Field", {
        "dt": "Purchase Invoice",
        "fieldname": "eboekhouden_invoice_number"
    })
    
    # Check column in database
    has_column = frappe.db.has_column("Purchase Invoice", "eboekhouden_invoice_number")
    
    # Get sample Purchase Invoices with the field
    sample_with_field = frappe.db.sql("""
        SELECT name, eboekhouden_invoice_number, docstatus
        FROM `tabPurchase Invoice`
        WHERE eboekhouden_invoice_number IS NOT NULL
        AND eboekhouden_invoice_number != ''
        LIMIT 5
    """, as_dict=True)
    
    return {
        "custom_field_exists": field_exists,
        "database_column_exists": has_column,
        "sample_invoices_with_field": sample_with_field
    }


if __name__ == "__main__":
    result = test_enhanced_cleanup()
    print(f"\nFinal result: {result}")