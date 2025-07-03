"""
Check detailed migration information
"""

import frappe
from frappe import _
import json

@frappe.whitelist()
def get_migration_details(migration_name=None):
    """Get detailed information about a migration"""
    
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
    
    # Get the migration document
    migration = frappe.get_doc("E-Boekhouden Migration", migration_name)
    
    # Get basic info
    info = {
        "name": migration.name,
        "status": migration.migration_status,
        "total_records": migration.total_records,
        "imported_records": migration.imported_records,
        "failed_records": migration.failed_records,
        "migration_summary": migration.migration_summary,
        "error_log": migration.error_log if hasattr(migration, 'error_log') else None,
        "start_time": migration.start_time,
        "end_time": migration.end_time
    }
    
    # Check for failed record details stored in the document
    if hasattr(migration, 'failed_record_details'):
        info["failed_record_details"] = migration.failed_record_details
    
    # Check for custom fields that might store failure info
    custom_fields = frappe.db.sql("""
        SELECT fieldname, value
        FROM `tabSingles`
        WHERE doctype = 'E-Boekhouden Migration'
        AND field IN ('failed_mutations', 'error_details', 'skip_summary')
        AND docname = %s
    """, (migration_name,), as_dict=True)
    
    if custom_fields:
        info["custom_fields"] = {cf.fieldname: cf.value for cf in custom_fields}
    
    # Get recent error logs that might be related
    error_logs = frappe.db.sql("""
        SELECT 
            COUNT(*) as count,
            SUBSTRING(error, 1, 100) as error_prefix
        FROM `tabError Log`
        WHERE 
            creation BETWEEN %s AND %s
            AND (error LIKE '%%E-Boekhouden%%' OR error LIKE '%%Payment%%' OR error LIKE '%%Invoice%%')
        GROUP BY error_prefix
        ORDER BY count DESC
        LIMIT 10
    """, (migration.start_time, migration.end_time or frappe.utils.now()), as_dict=True)
    
    info["related_error_patterns"] = error_logs
    
    return info

@frappe.whitelist()
def check_failed_records_file(migration_name=None):
    """Check if there's a failed records log file"""
    
    if not migration_name:
        migration_name = frappe.db.get_value(
            "E-Boekhouden Migration",
            {"migration_status": "Completed"},
            "name",
            order_by="creation desc"
        )
    
    import os
    import glob
    
    # Check for log files
    site_path = frappe.get_site_path()
    log_patterns = [
        os.path.join(site_path, "logs", f"*{migration_name}*"),
        os.path.join(site_path, "logs", "eboekhouden_migration_*"),
        os.path.join(site_path, "private", "files", f"*{migration_name}*")
    ]
    
    found_files = []
    for pattern in log_patterns:
        found_files.extend(glob.glob(pattern))
    
    file_info = []
    for file_path in found_files[:10]:  # Limit to 10 files
        try:
            stat = os.stat(file_path)
            file_info.append({
                "path": file_path,
                "size": stat.st_size,
                "modified": frappe.utils.get_datetime(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # If it's a JSON file and small enough, read it
            if file_path.endswith('.json') and stat.st_size < 100000:  # 100KB
                with open(file_path, 'r') as f:
                    content = json.load(f)
                    file_info[-1]["content_preview"] = str(content)[:500]
        except Exception as e:
            file_info.append({
                "path": file_path,
                "error": str(e)
            })
    
    return {
        "migration": migration_name,
        "log_files": file_info
    }

@frappe.whitelist()
def analyze_invoice_not_found():
    """Analyze the 245 invoice_not_found cases"""
    
    # Get the latest migration summary from the logs
    recent_logs = frappe.db.sql("""
        SELECT 
            creation,
            error
        FROM `tabError Log`
        WHERE 
            error LIKE '%%invoice_not_found%%'
            AND creation >= DATE_SUB(NOW(), INTERVAL 1 DAY)
        ORDER BY creation DESC
        LIMIT 10
    """, as_dict=True)
    
    # Check Payment Entries that might be unreconciled
    unmatched_payments = frappe.db.sql("""
        SELECT 
            pe.name,
            pe.party,
            pe.party_type,
            pe.posting_date,
            pe.paid_amount,
            pe.reference_no,
            pe.creation,
            pe.remarks
        FROM `tabPayment Entry` pe
        LEFT JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
        WHERE 
            pe.docstatus = 1
            AND pe.creation >= DATE_SUB(NOW(), INTERVAL 1 DAY)
            AND per.name IS NULL  -- No references
            AND pe.remarks LIKE '%%E-Boekhouden%%'
        LIMIT 20
    """, as_dict=True)
    
    # Check Journal Entries for unreconciled payments
    payment_journals = frappe.db.sql("""
        SELECT 
            je.name,
            je.posting_date,
            je.total_debit,
            je.eboekhouden_mutation_nr,
            je.eboekhouden_invoice_number,
            je.title,
            je.creation
        FROM `tabJournal Entry` je
        WHERE 
            je.docstatus = 1
            AND je.creation >= DATE_SUB(NOW(), INTERVAL 1 DAY)
            AND je.eboekhouden_invoice_number IS NOT NULL
            AND je.eboekhouden_invoice_number != ''
            AND (
                je.title LIKE '%%Payment%%'
                OR je.title LIKE '%%Betaling%%'
            )
        LIMIT 20
    """, as_dict=True)
    
    return {
        "recent_invoice_not_found_logs": recent_logs,
        "unmatched_payment_entries": unmatched_payments,
        "payment_journal_entries": payment_journals,
        "summary": {
            "total_unmatched_payments": len(unmatched_payments),
            "total_payment_journals": len(payment_journals)
        }
    }