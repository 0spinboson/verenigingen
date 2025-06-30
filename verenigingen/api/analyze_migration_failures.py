"""
Analyze failed records from E-Boekhouden migration
"""

import frappe
from frappe import _
from collections import defaultdict

@frappe.whitelist()
def analyze_migration_failures(migration_name=None, days=7):
    """Analyze failed records from migration error logs"""
    
    if not migration_name:
        # Get the latest migration
        migration_name = frappe.db.get_value(
            "E-Boekhouden Migration",
            {"migration_status": "Completed"},
            "name",
            order_by="creation desc"
        )
    
    if not migration_name:
        return {"error": "No completed migrations found"}
    
    # Get error logs related to this migration
    logs = frappe.db.sql("""
        SELECT 
            el.name,
            el.method as title,
            el.error,
            el.creation
        FROM `tabError Log` el
        WHERE 
            el.creation >= DATE_SUB(NOW(), INTERVAL %s DAY)
            AND (el.method LIKE %s OR el.error LIKE %s)
        ORDER BY el.creation DESC
    """, (days, f"%{migration_name}%", f"%{migration_name}%"), as_dict=True)
    
    # Analyze error patterns
    error_patterns = defaultdict(lambda: {"count": 0, "samples": [], "invoices": set()})
    invoice_errors = defaultdict(lambda: {"count": 0, "errors": []})
    
    for log in logs:
        error_msg = log.error
        
        # Extract error type
        error_type = "Unknown"
        invoice_no = None
        
        # Common error patterns
        if "Allocated Amount cannot be greater than outstanding amount" in error_msg:
            error_type = "already_paid"
            # Extract invoice number
            if "Invoice" in error_msg:
                parts = error_msg.split("Invoice")
                if len(parts) > 1:
                    invoice_no = parts[1].split(":")[0].strip()
                    
        elif "Paid Amount is mandatory" in error_msg:
            error_type = "missing_payment_amount"
            
        elif "Due Date cannot be before" in error_msg:
            error_type = "invalid_due_date"
            
        elif "default Stock Received But Not Billed" in error_msg:
            error_type = "stock_configuration"
            
        elif "Duplicate entry" in error_msg:
            error_type = "duplicate_entry"
            if "eboekhouden_mutation_nr" in error_msg:
                error_type = "duplicate_mutation"
                
        elif "does not exist" in error_msg:
            error_type = "missing_reference"
            
        # Track error patterns
        error_patterns[error_type]["count"] += 1
        if len(error_patterns[error_type]["samples"]) < 3:
            error_patterns[error_type]["samples"].append({
                "log_name": log.name,
                "error": error_msg[:200],
                "created": log.creation
            })
            
        if invoice_no:
            error_patterns[error_type]["invoices"].add(invoice_no)
            invoice_errors[invoice_no]["count"] += 1
            invoice_errors[invoice_no]["errors"].append(error_type)
    
    # Convert sets to lists for JSON serialization
    for pattern in error_patterns.values():
        pattern["invoices"] = list(pattern["invoices"])
        pattern["unique_invoices"] = len(pattern["invoices"])
    
    # Check for actual failed payment entries
    failed_payments = frappe.db.sql("""
        SELECT 
            mutation_nr,
            COUNT(*) as attempt_count,
            MAX(error_type) as last_error
        FROM (
            SELECT 
                SUBSTRING_INDEX(SUBSTRING_INDEX(el.error, 'MutatieNr=', -1), ',', 1) as mutation_nr,
                CASE 
                    WHEN el.error LIKE '%%already paid%%' THEN 'already_paid'
                    WHEN el.error LIKE '%%Paid Amount is mandatory%%' THEN 'missing_amount'
                    WHEN el.error LIKE '%%outstanding amount%%' THEN 'exceeds_outstanding'
                    ELSE 'other'
                END as error_type
            FROM `tabError Log` el
            WHERE 
                el.creation >= DATE_SUB(NOW(), INTERVAL %s DAY)
                AND el.error LIKE '%%MutatieNr=%%'
        ) as mutations
        GROUP BY mutation_nr
        HAVING attempt_count > 1
        ORDER BY attempt_count DESC
        LIMIT 20
    """, (days,), as_dict=True)
    
    # Summary
    total_errors = sum(p["count"] for p in error_patterns.values())
    unique_invoices = len(invoice_errors)
    
    return {
        "migration": migration_name,
        "analysis_period_days": days,
        "total_error_logs": len(logs),
        "total_errors_counted": total_errors,
        "unique_invoices_with_errors": unique_invoices,
        "error_patterns": dict(error_patterns),
        "most_problematic_invoices": dict(list(sorted(
            invoice_errors.items(), 
            key=lambda x: x[1]["count"], 
            reverse=True
        ))[:10]),
        "duplicate_payment_attempts": failed_payments,
        "summary": {
            "likely_duplicate_attempts": sum(1 for inv in invoice_errors.values() if inv["count"] > 10),
            "actual_failures": unique_invoices,
            "most_common_error": max(error_patterns.items(), key=lambda x: x[1]["count"])[0] if error_patterns else None
        }
    }

@frappe.whitelist() 
def check_unreconciled_in_journal_entries():
    """Check for unreconciled payments created as journal entries"""
    
    # Look for journal entries that might be unreconciled payments
    unreconciled_je = frappe.db.sql("""
        SELECT 
            je.name,
            je.posting_date,
            je.total_debit as amount,
            je.eboekhouden_mutation_nr,
            je.eboekhouden_invoice_number,
            je.title,
            je.user_remark,
            je.creation
        FROM `tabJournal Entry` je
        WHERE 
            je.docstatus = 1
            AND je.creation >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            AND (
                je.title LIKE '%Payment%Invoice Not Found%'
                OR je.user_remark LIKE '%Invoice Not Found%'
                OR je.user_remark LIKE '%create_payment_journal_entry%'
                OR (je.eboekhouden_invoice_number IS NOT NULL 
                    AND je.title LIKE '%Payment%')
            )
        ORDER BY je.creation DESC
        LIMIT 100
    """, as_dict=True)
    
    # Check for orphaned payment entries
    orphaned_payments = frappe.db.sql("""
        SELECT 
            pe.name,
            pe.party,
            pe.party_type,
            pe.posting_date,
            pe.paid_amount,
            pe.unallocated_amount,
            pe.reference_no,
            pe.remarks,
            pe.creation
        FROM `tabPayment Entry` pe
        WHERE 
            pe.docstatus = 1
            AND pe.unallocated_amount > 0
            AND pe.creation >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            AND (
                pe.remarks LIKE '%E-Boekhouden%'
                OR pe.remarks LIKE '%UNRECONCILED%'
                OR pe.reference_no LIKE 'MUT%'
            )
        ORDER BY pe.creation DESC
        LIMIT 100
    """, as_dict=True)
    
    return {
        "journal_entries": {
            "count": len(unreconciled_je),
            "total_amount": sum(je.amount for je in unreconciled_je),
            "entries": unreconciled_je[:20]
        },
        "orphaned_payments": {
            "count": len(orphaned_payments),
            "total_unallocated": sum(pe.unallocated_amount for pe in orphaned_payments),
            "entries": orphaned_payments[:20]
        },
        "total_unreconciled": len(unreconciled_je) + len(orphaned_payments)
    }