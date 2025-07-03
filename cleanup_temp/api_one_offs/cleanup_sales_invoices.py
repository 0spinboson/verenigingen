#!/usr/bin/env python
"""Enhanced Sales Invoice cleanup for E-Boekhouden migration"""

import frappe
from frappe import _

@frappe.whitelist()
def cleanup_all_sales_invoices(company=None, dry_run=True):
    """
    Clean up ALL sales invoices for a company
    
    Args:
        company: Company name (uses default if not provided)
        dry_run: If True, only preview what would be deleted
    
    WARNING: This will delete ALL sales invoices, not just E-Boekhouden ones!
    """
    try:
        # Get default company if not provided
        if not company:
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
        
        if not company:
            return {"success": False, "error": "No company specified"}
        
        # Get all sales invoices for the company
        all_invoices = frappe.get_all("Sales Invoice", 
            filters={
                "company": company,
                "docstatus": ["!=", 2]  # Not cancelled
            },
            fields=["name", "customer", "grand_total", "posting_date", "docstatus", "remarks"],
            order_by="posting_date desc")
        
        if dry_run:
            # Group by patterns for analysis
            patterns = {
                "e_boekhouden": [],
                "acc_sinv": [],
                "sinv_numeric": [],
                "other": []
            }
            
            for inv in all_invoices:
                if inv.remarks and "e-Boekhouden" in inv.remarks:
                    patterns["e_boekhouden"].append(inv)
                elif inv.name.startswith("ACC-SINV-"):
                    patterns["acc_sinv"].append(inv)
                elif inv.name.startswith("SINV-") and inv.name.split("-")[-1].isdigit():
                    patterns["sinv_numeric"].append(inv)
                else:
                    patterns["other"].append(inv)
            
            return {
                "success": True,
                "dry_run": True,
                "total_invoices": len(all_invoices),
                "by_pattern": {
                    "e_boekhouden_remarks": len(patterns["e_boekhouden"]),
                    "acc_sinv_pattern": len(patterns["acc_sinv"]),
                    "sinv_numeric_pattern": len(patterns["sinv_numeric"]),
                    "other": len(patterns["other"])
                },
                "sample_invoices": all_invoices[:10]  # First 10 as sample
            }
        
        # Actual deletion
        deleted_count = 0
        failed_count = 0
        failed_invoices = []
        
        for inv in all_invoices:
            try:
                # First, clean up GL Entries
                frappe.db.sql("""
                    DELETE FROM `tabGL Entry` 
                    WHERE voucher_type = 'Sales Invoice' 
                    AND voucher_no = %s
                """, inv.name)
                
                # Get the document
                si_doc = frappe.get_doc("Sales Invoice", inv.name)
                
                # Cancel if submitted
                if si_doc.docstatus == 1:
                    si_doc.flags.ignore_permissions = True
                    si_doc.ignore_linked_doctypes = (
                        "GL Entry", "Stock Ledger Entry", "Payment Ledger Entry",
                        "Repost Payment Ledger", "Repost Payment Ledger Items",
                        "Repost Accounting Ledger", "Repost Accounting Ledger Items",
                        "Unreconcile Payment", "Unreconcile Payment Entries"
                    )
                    si_doc.cancel()
                
                # Delete the document
                frappe.delete_doc("Sales Invoice", inv.name, force=True)
                deleted_count += 1
                
            except Exception as e:
                failed_count += 1
                failed_invoices.append({
                    "invoice": inv.name,
                    "error": str(e)
                })
                # Try direct SQL delete as last resort
                try:
                    frappe.db.sql("UPDATE `tabSales Invoice` SET docstatus = 2 WHERE name = %s", inv.name)
                    frappe.db.sql("DELETE FROM `tabSales Invoice` WHERE name = %s", inv.name)
                    deleted_count += 1
                    failed_count -= 1
                except:
                    pass
        
        frappe.db.commit()
        
        return {
            "success": True,
            "total_invoices": len(all_invoices),
            "deleted": deleted_count,
            "failed": failed_count,
            "failed_invoices": failed_invoices[:10]  # First 10 failures
        }
        
    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def cleanup_eboekhouden_sales_invoices(company=None):
    """
    Clean up only E-Boekhouden related sales invoices
    Uses multiple detection methods to identify E-Boekhouden invoices
    """
    try:
        # Get default company if not provided
        if not company:
            settings = frappe.get_single("E-Boekhouden Settings")
            company = settings.default_company
        
        if not company:
            return {"success": False, "error": "No company specified"}
        
        # Call the main cleanup function with appropriate filters
        from verenigingen.verenigingen.doctype.e_boekhouden_migration.e_boekhouden_migration import debug_cleanup_all_imported_data
        
        result = debug_cleanup_all_imported_data(company)
        
        if result["success"]:
            return {
                "success": True,
                "sales_invoices_deleted": result["results"].get("sales_invoices_deleted", 0),
                "message": f"Deleted {result['results'].get('sales_invoices_deleted', 0)} E-Boekhouden sales invoices"
            }
        else:
            return result
            
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Test dry run
    print("Previewing sales invoice cleanup...")
    result = cleanup_all_sales_invoices(dry_run=True)
    print(f"Found {result.get('total_invoices', 0)} sales invoices")
    if result.get("by_pattern"):
        print("\nBy pattern:")
        for pattern, count in result["by_pattern"].items():
            print(f"  {pattern}: {count}")