"""
Debug tool to trace mutation processing during migration
"""

import frappe
from frappe import _
import json

@frappe.whitelist()
def trace_migration_processing(migration_name=None, limit=100):
    """Trace what happens to each mutation during processing"""
    
    if not migration_name:
        # Get the latest migration
        migration_name = frappe.db.get_value(
            "E-Boekhouden Migration",
            {"migration_status": ["in", ["Completed", "In Progress"]]},
            "name",
            order_by="creation desc"
        )
    
    if not migration_name:
        return {"error": "No migrations found"}
    
    # Get SOAP API settings
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    settings = frappe.get_single("E-Boekhouden Settings")
    
    try:
        api = EBoekhoudenSOAPAPI(settings)
        
        # Get a sample of mutations
        result = api.get_mutations(mutation_nr_from=1, mutation_nr_to=limit)
        
        if not result["success"]:
            return {"error": f"Failed to get mutations: {result.get('error')}"}
        
        mutations = result["mutations"]
        
        # Trace each mutation
        trace_results = []
        
        for mut in mutations:
            trace = trace_single_mutation(mut)
            trace_results.append(trace)
        
        # Summarize results
        summary = {
            "total_traced": len(trace_results),
            "by_status": {},
            "by_type": {},
            "samples": []
        }
        
        for trace in trace_results:
            status = trace["status"]
            mut_type = trace["type"]
            
            # Count by status
            if status not in summary["by_status"]:
                summary["by_status"][status] = 0
            summary["by_status"][status] += 1
            
            # Count by type and status
            if mut_type not in summary["by_type"]:
                summary["by_type"][mut_type] = {}
            if status not in summary["by_type"][mut_type]:
                summary["by_type"][mut_type][status] = 0
            summary["by_type"][mut_type][status] += 1
            
            # Keep samples
            if len(summary["samples"]) < 20:
                summary["samples"].append(trace)
        
        return summary
        
    except Exception as e:
        return {"error": str(e), "traceback": frappe.get_traceback()}

def trace_single_mutation(mutation):
    """Trace what happens to a single mutation"""
    
    from verenigingen.utils.normalize_mutation_types import normalize_mutation_type
    
    mut_type = mutation.get("Soort", "Unknown")
    normalized_type = normalize_mutation_type(mut_type)
    mutation_nr = mutation.get("MutatieNr")
    invoice_no = mutation.get("Factuurnummer")
    
    trace = {
        "mutation_nr": mutation_nr,
        "type": mut_type,
        "normalized_type": normalized_type,
        "invoice_no": invoice_no,
        "description": mutation.get("Omschrijving", "")[:50],
        "status": "unknown",
        "reason": None,
        "details": {}
    }
    
    # Check based on mutation type
    if normalized_type == "FactuurVerstuurd":
        # Sales invoice
        if not invoice_no:
            trace["status"] = "skipped"
            trace["reason"] = "no_invoice_number"
        elif frappe.db.exists("Sales Invoice", {"eboekhouden_invoice_number": invoice_no}):
            trace["status"] = "already_imported"
            trace["reason"] = "sales_invoice_exists"
            trace["details"]["sales_invoice"] = frappe.db.get_value(
                "Sales Invoice", 
                {"eboekhouden_invoice_number": invoice_no}, 
                ["name", "customer", "grand_total", "status"],
                as_dict=True
            )
        else:
            trace["status"] = "would_import"
            trace["reason"] = "new_sales_invoice"
            
    elif normalized_type == "FactuurOntvangen":
        # Purchase invoice
        if not invoice_no:
            trace["status"] = "skipped"
            trace["reason"] = "no_invoice_number"
        elif frappe.db.exists("Purchase Invoice", {"eboekhouden_invoice_number": invoice_no}):
            trace["status"] = "already_imported"
            trace["reason"] = "purchase_invoice_exists"
            trace["details"]["purchase_invoice"] = frappe.db.get_value(
                "Purchase Invoice",
                {"eboekhouden_invoice_number": invoice_no},
                ["name", "supplier", "grand_total", "status"],
                as_dict=True
            )
        else:
            trace["status"] = "would_import"
            trace["reason"] = "new_purchase_invoice"
            
    elif normalized_type == "FactuurbetalingOntvangen":
        # Customer payment
        if not invoice_no:
            trace["status"] = "skipped"
            trace["reason"] = "no_invoice_number"
        else:
            # Check if payment exists
            if frappe.db.exists("Payment Entry", [
                ["reference_no", "=", mutation_nr],
                ["docstatus", "!=", 2]
            ]):
                trace["status"] = "already_imported"
                trace["reason"] = "payment_exists"
            else:
                # Check if invoice exists
                if not frappe.db.exists("Sales Invoice", {"eboekhouden_invoice_number": invoice_no}):
                    trace["status"] = "skipped"
                    trace["reason"] = "invoice_not_found"
                else:
                    # Check if invoice is already paid
                    si = frappe.db.get_value(
                        "Sales Invoice",
                        {"eboekhouden_invoice_number": invoice_no},
                        ["name", "outstanding_amount", "status"],
                        as_dict=True
                    )
                    if si and si.outstanding_amount <= 0:
                        trace["status"] = "skipped"
                        trace["reason"] = "already_paid"
                        trace["details"]["invoice_status"] = si.status
                    else:
                        trace["status"] = "would_import"
                        trace["reason"] = "new_payment"
                        
    elif normalized_type == "FactuurbetalingVerstuurd":
        # Supplier payment
        if not invoice_no:
            trace["status"] = "skipped"
            trace["reason"] = "no_invoice_number"
        else:
            # Check if payment exists
            if frappe.db.exists("Payment Entry", [
                ["reference_no", "=", mutation_nr],
                ["docstatus", "!=", 2]
            ]):
                trace["status"] = "already_imported"
                trace["reason"] = "payment_exists"
            else:
                # Check if invoice exists
                if not frappe.db.exists("Purchase Invoice", {"eboekhouden_invoice_number": invoice_no}):
                    trace["status"] = "skipped"
                    trace["reason"] = "invoice_not_found"
                else:
                    # Check if invoice is already paid
                    pi = frappe.db.get_value(
                        "Purchase Invoice",
                        {"eboekhouden_invoice_number": invoice_no},
                        ["name", "outstanding_amount", "status"],
                        as_dict=True
                    )
                    if pi and pi.outstanding_amount <= 0:
                        trace["status"] = "skipped"
                        trace["reason"] = "already_paid"
                        trace["details"]["invoice_status"] = pi.status
                    else:
                        trace["status"] = "would_import"
                        trace["reason"] = "new_payment"
                        
    elif normalized_type in ["GeldOntvangen", "GeldUitgegeven"]:
        # Bank transactions
        if frappe.db.exists("Journal Entry", {"eboekhouden_mutation_nr": mutation_nr}):
            trace["status"] = "already_imported"
            trace["reason"] = "journal_entry_exists"
        else:
            # Check if amount is zero
            total_amount = 0
            for regel in mutation.get("MutatieRegels", []):
                total_amount += float(regel.get("BedragInclBTW", 0))
            
            if total_amount == 0:
                trace["status"] = "skipped"
                trace["reason"] = "zero_amount"
            else:
                trace["status"] = "would_import"
                trace["reason"] = "new_bank_transaction"
                
    elif normalized_type == "Memoriaal":
        # Manual journal entries
        if frappe.db.exists("Journal Entry", {"eboekhouden_mutation_nr": mutation_nr}):
            trace["status"] = "already_imported"
            trace["reason"] = "journal_entry_exists"
        else:
            trace["status"] = "would_import"
            trace["reason"] = "new_memorial_entry"
    else:
        # Unhandled type
        trace["status"] = "unhandled"
        trace["reason"] = f"mutation_type_not_supported"
        
    return trace

@frappe.whitelist()
def get_migration_log_summary(migration_name=None):
    """Get a summary of the migration log messages"""
    
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
    
    # Get log entries for this migration
    logs = frappe.db.sql("""
        SELECT 
            title,
            COUNT(*) as count,
            MIN(creation) as first_occurrence,
            MAX(creation) as last_occurrence
        FROM `tabError Log`
        WHERE 
            title LIKE %s
            AND creation >= (
                SELECT creation FROM `tabE-Boekhouden Migration` WHERE name = %s
            )
        GROUP BY title
        ORDER BY count DESC
        LIMIT 50
    """, (f"%{migration_name}%", migration_name), as_dict=True)
    
    return {
        "migration": migration_name,
        "log_summary": logs,
        "total_log_entries": sum(log.count for log in logs)
    }