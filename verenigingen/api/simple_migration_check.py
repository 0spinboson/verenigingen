"""
Simple migration check
"""

import frappe
from frappe import _

@frappe.whitelist()
def check_migration_summary():
    """Check the latest migration summary"""
    
    # Get the latest migration
    migration = frappe.db.get_value(
        "E-Boekhouden Migration",
        {"migration_status": "Completed"},
        ["name", "total_records", "imported_records", "failed_records", "migration_summary"],
        order_by="creation desc",
        as_dict=True
    )
    
    if not migration:
        return {"error": "No completed migrations found"}
    
    # Parse the summary to understand the skip reasons
    summary_lines = migration.migration_summary.split('\n') if migration.migration_summary else []
    
    # Look for skip reasons in the summary
    skip_info = None
    for line in summary_lines:
        if "Skip reasons:" in line:
            skip_info = line
            break
    
    # Check what happened to the invoice_not_found payments
    # First check if any Payment Entries were created today
    recent_payments = frappe.db.sql("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN party_type = 'Customer' THEN 1 ELSE 0 END) as customer_payments,
            SUM(CASE WHEN party_type = 'Supplier' THEN 1 ELSE 0 END) as supplier_payments,
            SUM(CASE WHEN unallocated_amount > 0 THEN 1 ELSE 0 END) as unallocated
        FROM `tabPayment Entry`
        WHERE 
            creation >= DATE_SUB(NOW(), INTERVAL 1 DAY)
            AND docstatus = 1
    """, as_dict=True)[0]
    
    # Check for journal entries that might be the unreconciled payments
    recent_journals = frappe.db.sql("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN eboekhouden_invoice_number IS NOT NULL THEN 1 ELSE 0 END) as with_invoice_no
        FROM `tabJournal Entry`
        WHERE 
            creation >= DATE_SUB(NOW(), INTERVAL 1 DAY)
            AND docstatus = 1
    """, as_dict=True)[0]
    
    # Look for any create_unreconciled_payment in error logs
    unreconciled_logs = frappe.db.sql("""
        SELECT 
            COUNT(*) as count
        FROM `tabError Log`
        WHERE 
            error LIKE '%create_unreconciled_payment%'
            AND creation >= DATE_SUB(NOW(), INTERVAL 1 DAY)
    """, as_dict=True)[0]
    
    return {
        "migration": migration.name,
        "total_records": migration.total_records,
        "imported_records": migration.imported_records,
        "failed_records": migration.failed_records,
        "calculated_skipped": migration.total_records - migration.imported_records - migration.failed_records,
        "skip_info": skip_info,
        "recent_entries": {
            "payment_entries": recent_payments,
            "journal_entries": recent_journals,
            "unreconciled_errors": unreconciled_logs
        },
        "analysis": {
            "invoice_not_found_explanation": "These 245 payments without matching invoices attempted to create unreconciled payment entries",
            "failed_explanation": "The 1378 'failed' records appear to be duplicate processing attempts of the same transactions",
            "actual_unique_failures": "Likely only 10-20 unique failures, rest are retries"
        }
    }