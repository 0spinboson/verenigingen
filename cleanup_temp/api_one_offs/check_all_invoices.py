#!/usr/bin/env python
"""Check all invoices"""

import frappe

@frappe.whitelist()
def check_all_invoices():
    """Check all sales invoices in the system"""
    
    total = frappe.db.count("Sales Invoice")
    
    # Get sample of all invoices
    all_invoices = frappe.get_all("Sales Invoice", 
        fields=["name", "eboekhouden_invoice_number", "docstatus", "creation"],
        order_by="creation desc",
        limit=10)
    
    # Check different statuses
    draft_count = frappe.db.count("Sales Invoice", {"docstatus": 0})
    submitted_count = frappe.db.count("Sales Invoice", {"docstatus": 1})
    cancelled_count = frappe.db.count("Sales Invoice", {"docstatus": 2})
    
    # Check E-Boekhouden invoices by different methods
    eb_set_count = len(frappe.get_all("Sales Invoice", filters=[
        ["eboekhouden_invoice_number", "is", "set"]
    ]))
    
    eb_not_empty_count = len(frappe.get_all("Sales Invoice", filters=[
        ["eboekhouden_invoice_number", "!=", ""]
    ]))
    
    # Check by SQL
    sql_result = frappe.db.sql("""
        SELECT COUNT(*) 
        FROM `tabSales Invoice` 
        WHERE eboekhouden_invoice_number IS NOT NULL 
        AND eboekhouden_invoice_number != ''
    """)[0][0]
    
    return {
        "total_invoices": total,
        "draft": draft_count,
        "submitted": submitted_count,
        "cancelled": cancelled_count,
        "eb_set_count": eb_set_count,
        "eb_not_empty_count": eb_not_empty_count,
        "eb_sql_count": sql_result,
        "sample_invoices": all_invoices
    }


if __name__ == "__main__":
    result = check_all_invoices()
    print(f"Total invoices: {result['total_invoices']}")
    print(f"With E-Boekhouden number: {result['eb_sql_count']}")