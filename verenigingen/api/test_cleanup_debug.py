#!/usr/bin/env python
"""Debug the cleanup function"""

import frappe
from frappe import _

@frappe.whitelist()
def test_cleanup_debug():
    """Test and debug the cleanup function"""
    
    # Get default company
    settings = frappe.get_single("E-Boekhouden Settings")
    company = settings.default_company if settings else None
    
    if not company:
        return {"error": "No default company configured"}
    
    results = {}
    
    # First, let's see what sales invoices exist
    all_invoices = frappe.get_all("Sales Invoice",
        filters={"company": company},
        fields=["name", "eboekhouden_invoice_number", "docstatus", "remarks"],
        limit=20)
    
    results["all_invoices"] = all_invoices
    results["total_count"] = frappe.db.count("Sales Invoice", {"company": company})
    
    # Check specifically for E-Boekhouden invoices
    eb_invoices = frappe.get_all("Sales Invoice", filters=[
        ["company", "=", company],
        ["eboekhouden_invoice_number", "is", "set"],
        ["eboekhouden_invoice_number", "!=", ""],
        ["docstatus", "!=", 2]
    ], fields=["name", "eboekhouden_invoice_number", "docstatus"])
    
    results["eboekhouden_invoices"] = eb_invoices
    results["eboekhouden_count"] = len(eb_invoices)
    
    # Now let's test the actual cleanup
    from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import debug_cleanup_all_imported_data
    
    try:
        cleanup_result = debug_cleanup_all_imported_data(company)
        results["cleanup_result"] = cleanup_result
    except Exception as e:
        results["cleanup_error"] = str(e)
        import traceback
        results["cleanup_traceback"] = traceback.format_exc()
    
    # Check what's left after cleanup
    remaining_invoices = frappe.get_all("Sales Invoice",
        filters={"company": company},
        fields=["name", "eboekhouden_invoice_number", "docstatus"],
        limit=20)
    
    results["remaining_invoices"] = remaining_invoices
    results["remaining_count"] = frappe.db.count("Sales Invoice", {"company": company})
    
    return results


@frappe.whitelist()
def test_direct_cleanup():
    """Test direct cleanup of a single invoice"""
    
    # Get a sample E-Boekhouden invoice
    sample = frappe.get_all("Sales Invoice", 
        filters=[
            ["eboekhouden_invoice_number", "is", "set"],
            ["eboekhouden_invoice_number", "!=", ""],
            ["docstatus", "!=", 2]
        ],
        fields=["name", "docstatus", "eboekhouden_invoice_number"],
        limit=1)
    
    if not sample:
        return {"error": "No E-Boekhouden invoices found to test"}
    
    invoice_name = sample[0]["name"]
    results = {"invoice": invoice_name, "initial_state": sample[0]}
    
    try:
        # Try to delete it directly
        si_doc = frappe.get_doc("Sales Invoice", invoice_name)
        
        # First try to cancel if submitted
        if si_doc.docstatus == 1:
            si_doc.flags.ignore_permissions = True
            si_doc.ignore_linked_doctypes = (
                "GL Entry", "Stock Ledger Entry", "Payment Ledger Entry",
                "Repost Payment Ledger", "Repost Payment Ledger Items",
                "Repost Accounting Ledger", "Repost Accounting Ledger Items",
                "Unreconcile Payment", "Unreconcile Payment Entries"
            )
            si_doc.cancel()
            results["cancelled"] = True
        
        # Now try to delete
        frappe.delete_doc("Sales Invoice", invoice_name, force=True)
        results["deleted"] = True
        
        frappe.db.commit()
        
    except Exception as e:
        results["error"] = str(e)
        import traceback
        results["traceback"] = traceback.format_exc()
        
        # Try SQL delete as last resort
        try:
            frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_type = 'Sales Invoice' AND voucher_no = %s", invoice_name)
            frappe.db.sql("UPDATE `tabSales Invoice` SET docstatus = 2 WHERE name = %s", invoice_name)
            frappe.db.sql("DELETE FROM `tabSales Invoice` WHERE name = %s", invoice_name)
            frappe.db.commit()
            results["sql_deleted"] = True
        except Exception as e2:
            results["sql_error"] = str(e2)
    
    return results


if __name__ == "__main__":
    result = test_cleanup_debug()
    print("Cleanup test results:")
    print(f"Total invoices: {result.get('total_count', 0)}")
    print(f"E-Boekhouden invoices: {result.get('eboekhouden_count', 0)}")
    print(f"Cleanup result: {result.get('cleanup_result', {})}")
    print(f"Remaining invoices: {result.get('remaining_count', 0)}")