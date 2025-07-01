"""
Check historical migration failures
"""

import frappe
from frappe import _

@frappe.whitelist()
def check_historical_failures():
    """Check for failed transactions from all recent migrations"""
    
    # Get recent migrations with failures
    migrations = frappe.db.sql("""
        SELECT 
            name,
            total_records,
            imported_records,
            failed_records,
            start_time,
            end_time,
            migration_status
        FROM `tabE-Boekhouden Migration`
        WHERE 
            failed_records > 0
            AND migration_status = 'Completed'
        ORDER BY creation DESC
        LIMIT 10
    """, as_dict=True)
    
    if not migrations:
        return {"message": "No migrations with failed records found"}
    
    results = {
        "migrations_with_failures": [],
        "all_error_patterns": {},
        "all_partial_records": {
            "draft_payments": [],
            "cancelled_payments": [],
            "draft_journals": []
        }
    }
    
    for mig in migrations:
        # Check error logs during this migration period
        error_count = frappe.db.sql("""
            SELECT COUNT(*) as count
            FROM `tabError Log`
            WHERE 
                creation BETWEEN %s AND %s
                AND (
                    error LIKE '%%E-Boekhouden%%'
                    OR error LIKE '%%MutatieNr%%'
                    OR error LIKE '%%outstanding amount%%'
                )
        """, (mig.start_time, mig.end_time or frappe.utils.now()), as_dict=True)[0].count
        
        results["migrations_with_failures"].append({
            "name": mig.name,
            "failed_records": mig.failed_records,
            "error_logs_found": error_count,
            "period": f"{mig.start_time} to {mig.end_time}"
        })
    
    # Check for any orphaned draft/cancelled records from E-Boekhouden
    
    # Draft Payment Entries
    draft_payments = frappe.db.sql("""
        SELECT 
            pe.name,
            pe.party,
            pe.party_type,
            pe.paid_amount,
            pe.reference_no,
            pe.creation,
            pe.modified,
            pe.owner
        FROM `tabPayment Entry` pe
        WHERE 
            pe.docstatus = 0  -- Draft
            AND (
                pe.remarks LIKE '%%E-Boekhouden%%'
                OR pe.remarks LIKE '%%UNRECONCILED%%'
                OR pe.reference_no REGEXP '^[0-9]+$'  -- Numeric reference (likely mutation number)
                OR pe.owner = 'Administrator'  -- Created by migration
            )
        ORDER BY pe.creation DESC
        LIMIT 20
    """, as_dict=True)
    
    # Cancelled Payment Entries  
    cancelled_payments = frappe.db.sql("""
        SELECT 
            pe.name,
            pe.party,
            pe.party_type,
            pe.paid_amount,
            pe.reference_no,
            pe.creation,
            pe.modified
        FROM `tabPayment Entry` pe
        WHERE 
            pe.docstatus = 2  -- Cancelled
            AND (
                pe.remarks LIKE '%%E-Boekhouden%%'
                OR pe.reference_no REGEXP '^[0-9]+$'
            )
        ORDER BY pe.modified DESC
        LIMIT 20
    """, as_dict=True)
    
    # Draft Journal Entries
    draft_journals = frappe.db.sql("""
        SELECT 
            je.name,
            je.total_debit,
            je.title,
            je.creation,
            je.modified,
            je.owner
        FROM `tabJournal Entry` je
        WHERE 
            je.docstatus = 0  -- Draft
            AND (
                je.title LIKE '%%E-Boekhouden%%'
                OR je.user_remark LIKE '%%E-Boekhouden%%'
                OR (je.owner = 'Administrator' AND je.title LIKE '%%Payment%%')
            )
        ORDER BY je.creation DESC
        LIMIT 20
    """, as_dict=True)
    
    results["all_partial_records"] = {
        "draft_payments": draft_payments,
        "cancelled_payments": cancelled_payments,
        "draft_journals": draft_journals
    }
    
    # Check for specific failed invoice/payment combinations
    failed_payment_attempts = frappe.db.sql("""
        SELECT 
            SUBSTRING_INDEX(SUBSTRING_INDEX(el.error, 'Invoice ', -1), ':', 1) as invoice_ref,
            COUNT(*) as attempt_count,
            MAX(el.creation) as last_attempt
        FROM `tabError Log` el
        WHERE 
            el.error LIKE '%%outstanding amount%%'
            AND el.error LIKE '%%Invoice%%'
        GROUP BY invoice_ref
        HAVING attempt_count > 5
        ORDER BY attempt_count DESC
        LIMIT 10
    """, as_dict=True)
    
    # Check if these invoices actually exist and their status
    for attempt in failed_payment_attempts:
        invoice_ref = attempt.invoice_ref.strip()
        
        # Check if it's a sales invoice
        si = frappe.db.get_value(
            "Sales Invoice",
            {"name": invoice_ref},
            ["outstanding_amount", "status", "grand_total"],
            as_dict=True
        )
        
        if si:
            attempt["invoice_found"] = True
            attempt["invoice_type"] = "Sales Invoice"
            attempt["outstanding"] = si.outstanding_amount
            attempt["status"] = si.status
            attempt["total"] = si.grand_total
        else:
            # Check purchase invoice
            pi = frappe.db.get_value(
                "Purchase Invoice",
                {"name": invoice_ref},
                ["outstanding_amount", "status", "grand_total"],
                as_dict=True
            )
            
            if pi:
                attempt["invoice_found"] = True
                attempt["invoice_type"] = "Purchase Invoice"
                attempt["outstanding"] = pi.outstanding_amount
                attempt["status"] = pi.status
                attempt["total"] = pi.grand_total
            else:
                attempt["invoice_found"] = False
    
    results["failed_payment_attempts"] = failed_payment_attempts
    
    # Summary
    results["summary"] = {
        "total_migrations_with_failures": len(migrations),
        "total_reported_failures": sum(m.failed_records for m in migrations),
        "draft_records_found": len(draft_payments) + len(draft_journals),
        "cancelled_records_found": len(cancelled_payments),
        "invoices_with_multiple_failures": len(failed_payment_attempts),
        "insights": []
    }
    
    # Add insights
    if not draft_payments and not cancelled_payments and not draft_journals:
        results["summary"]["insights"].append(
            "No draft or cancelled records found - failed transactions were not partially created"
        )
    
    if failed_payment_attempts:
        paid_invoices = [a for a in failed_payment_attempts if a.get("outstanding", 1) == 0]
        if paid_invoices:
            results["summary"]["insights"].append(
                f"{len(paid_invoices)} invoices had repeated payment attempts despite being fully paid"
            )
    
    if results["summary"]["draft_records_found"] > 0:
        results["summary"]["insights"].append(
            f"Found {results['summary']['draft_records_found']} draft records that need review"
        )
    
    return results