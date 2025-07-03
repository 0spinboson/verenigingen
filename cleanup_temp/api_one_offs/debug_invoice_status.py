#!/usr/bin/env python
"""Debug invoice status"""

import frappe

@frappe.whitelist()
def debug_invoice_status():
    """Check the actual status of invoices"""
    
    # Direct SQL query to check
    result = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_invoices,
            SUM(CASE WHEN eboekhouden_invoice_number IS NOT NULL AND eboekhouden_invoice_number != '' THEN 1 ELSE 0 END) as with_eb_number,
            SUM(CASE WHEN docstatus = 0 THEN 1 ELSE 0 END) as draft,
            SUM(CASE WHEN docstatus = 1 THEN 1 ELSE 0 END) as submitted,
            SUM(CASE WHEN docstatus = 2 THEN 1 ELSE 0 END) as cancelled
        FROM `tabSales Invoice`
        WHERE name LIKE 'ACC-SINV-%'
    """, as_dict=True)[0]
    
    # Get a few sample invoices
    samples = frappe.db.sql("""
        SELECT 
            name, 
            eboekhouden_invoice_number,
            docstatus,
            creation
        FROM `tabSales Invoice`
        WHERE eboekhouden_invoice_number IS NOT NULL 
        AND eboekhouden_invoice_number != ''
        AND docstatus != 2
        ORDER BY creation DESC
        LIMIT 5
    """, as_dict=True)
    
    # Check filters used in cleanup
    filter_test = frappe.get_all("Sales Invoice", filters=[
        ["eboekhouden_invoice_number", "is", "set"],
        ["eboekhouden_invoice_number", "!=", ""],
        ["docstatus", "!=", 2]
    ], limit=5)
    
    return {
        "summary": result,
        "sample_invoices": samples,
        "filter_test_count": len(filter_test),
        "filter_test_samples": filter_test
    }


if __name__ == "__main__":
    result = debug_invoice_status()
    print(f"Summary: {result['summary']}")
    print(f"Samples: {result['sample_invoices']}")
    print(f"Filter test: {result['filter_test_count']} found")