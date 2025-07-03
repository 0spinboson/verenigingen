#!/usr/bin/env python
"""Simple test of cleanup function"""

import frappe

@frappe.whitelist()
def test_simple_cleanup():
    """Simple test to see what's happening with cleanup"""
    
    # Count invoices before
    before_count = frappe.db.count("Sales Invoice", {
        "eboekhouden_invoice_number": ["!=", ""]
    })
    
    # Get one sample invoice
    sample = frappe.db.get_value("Sales Invoice", 
        {"eboekhouden_invoice_number": ["!=", ""]}, 
        ["name", "eboekhouden_invoice_number", "docstatus"],
        as_dict=True)
    
    # Run the cleanup
    from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import debug_cleanup_all_imported_data
    
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company
    
    result = debug_cleanup_all_imported_data(company)
    
    # Count invoices after
    after_count = frappe.db.count("Sales Invoice", {
        "eboekhouden_invoice_number": ["!=", ""]
    })
    
    return {
        "before_count": before_count,
        "sample_invoice": sample,
        "cleanup_result": result,
        "after_count": after_count,
        "deleted": before_count - after_count
    }


if __name__ == "__main__":
    result = test_simple_cleanup()
    print(f"Result: {result}")