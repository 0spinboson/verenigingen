"""
Find actual failed transaction attempts in ERPNext
"""

import frappe
from frappe import _
from datetime import datetime, timedelta

@frappe.whitelist()
def find_failed_transactions(migration_name=None, days=7):
    """Find transactions that actually failed during migration"""
    
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
    
    # Get migration time window
    migration_doc = frappe.get_doc("E-Boekhouden Migration", migration_name)
    start_time = migration_doc.start_time
    end_time = migration_doc.end_time or frappe.utils.now()
    
    results = {
        "migration": migration_name,
        "period": f"{start_time} to {end_time}",
        "failed_transactions": {},
        "error_logs": [],
        "partial_records": {}
    }
    
    # 1. Check Error Logs for specific mutation failures
    error_logs = frappe.db.sql("""
        SELECT 
            name,
            method,
            error,
            creation
        FROM `tabError Log`
        WHERE 
            creation BETWEEN %s AND %s
            AND (
                error LIKE '%%MutatieNr%%'
                OR error LIKE '%%mutation%%'
                OR error LIKE '%%E-Boekhouden%%'
                OR error LIKE '%%Payment%%Invoice%%'
                OR error LIKE '%%outstanding amount%%'
            )
        ORDER BY creation DESC
        LIMIT 100
    """, (start_time, end_time), as_dict=True)
    
    # Parse error logs to extract mutation numbers and invoice numbers
    failed_mutations = {}
    for log in error_logs:
        error_text = log.error
        
        # Extract mutation number
        mutation_nr = None
        if "MutatieNr=" in error_text:
            try:
                mutation_nr = error_text.split("MutatieNr=")[1].split(",")[0].strip()
            except:
                pass
        
        # Extract invoice number
        invoice_no = None
        if "Invoice" in error_text and ":" in error_text:
            try:
                invoice_no = error_text.split("Invoice")[1].split(":")[0].strip()
            except:
                pass
                
        if mutation_nr or invoice_no:
            key = f"MUT-{mutation_nr or 'NA'}-INV-{invoice_no or 'NA'}"
            if key not in failed_mutations:
                failed_mutations[key] = {
                    "mutation_nr": mutation_nr,
                    "invoice_no": invoice_no,
                    "errors": [],
                    "count": 0
                }
            
            failed_mutations[key]["errors"].append({
                "log_name": log.name,
                "error": error_text[:200] + "..." if len(error_text) > 200 else error_text,
                "time": log.creation
            })
            failed_mutations[key]["count"] += 1
    
    results["failed_transactions"] = failed_mutations
    
    # 2. Check for partially created records (submitted=0 or cancelled)
    
    # Check draft Payment Entries
    draft_payments = frappe.db.sql("""
        SELECT 
            name,
            party,
            party_type,
            paid_amount,
            reference_no,
            creation,
            modified,
            modified_by
        FROM `tabPayment Entry`
        WHERE 
            docstatus = 0  -- Draft
            AND creation BETWEEN %s AND %s
            AND (
                remarks LIKE '%%E-Boekhouden%%'
                OR reference_no LIKE '%%MUT%%'
                OR reference_no IN (
                    SELECT DISTINCT SUBSTRING_INDEX(SUBSTRING_INDEX(error, 'MutatieNr=', -1), ',', 1)
                    FROM `tabError Log`
                    WHERE creation BETWEEN %s AND %s
                    AND error LIKE '%%MutatieNr=%%'
                )
            )
        LIMIT 50
    """, (start_time, end_time, start_time, end_time), as_dict=True)
    
    # Check cancelled Payment Entries
    cancelled_payments = frappe.db.sql("""
        SELECT 
            name,
            party,
            party_type,
            paid_amount,
            reference_no,
            creation,
            modified
        FROM `tabPayment Entry`
        WHERE 
            docstatus = 2  -- Cancelled
            AND modified BETWEEN %s AND %s
            AND (
                remarks LIKE '%%E-Boekhouden%%'
                OR reference_no LIKE '%%MUT%%'
            )
        LIMIT 50
    """, (start_time, end_time), as_dict=True)
    
    # Check draft Journal Entries
    draft_journals = frappe.db.sql("""
        SELECT 
            name,
            total_debit,
            eboekhouden_mutation_nr,
            eboekhouden_invoice_number,
            title,
            creation,
            modified
        FROM `tabJournal Entry`
        WHERE 
            docstatus = 0  -- Draft
            AND creation BETWEEN %s AND %s
            AND (
                eboekhouden_mutation_nr IS NOT NULL
                OR title LIKE '%%E-Boekhouden%%'
            )
        LIMIT 50
    """, (start_time, end_time), as_dict=True)
    
    results["partial_records"] = {
        "draft_payments": draft_payments,
        "cancelled_payments": cancelled_payments,
        "draft_journals": draft_journals
    }
    
    # 3. Look for specific known failure patterns
    
    # Already paid invoices
    already_paid_attempts = frappe.db.sql("""
        SELECT 
            el.name,
            el.error,
            el.creation
        FROM `tabError Log` el
        WHERE 
            el.creation BETWEEN %s AND %s
            AND (
                el.error LIKE '%%outstanding amount%%'
                OR el.error LIKE '%%already paid%%'
                OR el.error LIKE '%%Allocated Amount cannot be greater%%'
            )
        LIMIT 20
    """, (start_time, end_time), as_dict=True)
    
    # Missing data errors
    missing_data_errors = frappe.db.sql("""
        SELECT 
            el.name,
            el.error,
            el.creation
        FROM `tabError Log` el
        WHERE 
            el.creation BETWEEN %s AND %s
            AND (
                el.error LIKE '%%mandatory%%'
                OR el.error LIKE '%%required%%'
                OR el.error LIKE '%%cannot be blank%%'
            )
        LIMIT 20
    """, (start_time, end_time), as_dict=True)
    
    results["error_patterns"] = {
        "already_paid": len(already_paid_attempts),
        "missing_data": len(missing_data_errors),
        "samples": {
            "already_paid": already_paid_attempts[:3],
            "missing_data": missing_data_errors[:3]
        }
    }
    
    # 4. Summary
    results["summary"] = {
        "unique_failed_transactions": len(failed_mutations),
        "draft_records_found": len(draft_payments) + len(draft_journals),
        "cancelled_records_found": len(cancelled_payments),
        "most_failed_transaction": max(failed_mutations.items(), key=lambda x: x[1]["count"])[0] if failed_mutations else None,
        "actionable_items": []
    }
    
    # Add actionable items
    if draft_payments:
        results["summary"]["actionable_items"].append({
            "type": "Draft Payment Entries",
            "count": len(draft_payments),
            "action": "Review and either submit or delete these draft payments"
        })
    
    if cancelled_payments:
        results["summary"]["actionable_items"].append({
            "type": "Cancelled Payment Entries",
            "count": len(cancelled_payments),
            "action": "These were created but then cancelled - investigate why"
        })
    
    if draft_journals:
        results["summary"]["actionable_items"].append({
            "type": "Draft Journal Entries",
            "count": len(draft_journals),
            "action": "Review and either submit or delete these draft entries"
        })
    
    return results

@frappe.whitelist()
def get_failed_transaction_details(mutation_nr=None, invoice_no=None):
    """Get detailed information about a specific failed transaction"""
    
    if not mutation_nr and not invoice_no:
        return {"error": "Please provide either mutation_nr or invoice_no"}
    
    results = {
        "mutation_nr": mutation_nr,
        "invoice_no": invoice_no,
        "found_records": {},
        "error_logs": [],
        "recommendations": []
    }
    
    # Search for any records with this mutation/invoice
    if mutation_nr:
        # Check Payment Entries
        payment_entries = frappe.db.sql("""
            SELECT 
                name, 
                docstatus,
                party,
                paid_amount,
                creation,
                modified
            FROM `tabPayment Entry`
            WHERE 
                reference_no = %s
                OR eboekhouden_mutation_nr = %s
        """, (mutation_nr, mutation_nr), as_dict=True)
        
        if payment_entries:
            results["found_records"]["payment_entries"] = payment_entries
        
        # Check Journal Entries
        journal_entries = frappe.db.sql("""
            SELECT 
                name,
                docstatus,
                total_debit,
                creation,
                modified
            FROM `tabJournal Entry`
            WHERE 
                eboekhouden_mutation_nr = %s
        """, (mutation_nr,), as_dict=True)
        
        if journal_entries:
            results["found_records"]["journal_entries"] = journal_entries
    
    if invoice_no:
        # Check Invoices
        sales_invoices = frappe.db.get_all(
            "Sales Invoice",
            filters={"eboekhouden_invoice_number": invoice_no},
            fields=["name", "docstatus", "customer", "grand_total", "outstanding_amount"]
        )
        
        if sales_invoices:
            results["found_records"]["sales_invoices"] = sales_invoices
            
        purchase_invoices = frappe.db.get_all(
            "Purchase Invoice",
            filters={"eboekhouden_invoice_number": invoice_no},
            fields=["name", "docstatus", "supplier", "grand_total", "outstanding_amount"]
        )
        
        if purchase_invoices:
            results["found_records"]["purchase_invoices"] = purchase_invoices
    
    # Get related error logs
    search_terms = []
    if mutation_nr:
        search_terms.append(f"%%MutatieNr={mutation_nr}%%")
        search_terms.append(f"%%{mutation_nr}%%")
    if invoice_no:
        search_terms.append(f"%%{invoice_no}%%")
    
    if search_terms:
        where_clause = " OR ".join([f"error LIKE '{term}'" for term in search_terms])
        error_logs = frappe.db.sql(f"""
            SELECT 
                name,
                error,
                creation
            FROM `tabError Log`
            WHERE {where_clause}
            ORDER BY creation DESC
            LIMIT 10
        """, as_dict=True)
        
        results["error_logs"] = error_logs
    
    # Add recommendations based on findings
    if results["found_records"]:
        for doc_type, docs in results["found_records"].items():
            for doc in docs:
                if doc.get("docstatus") == 0:
                    results["recommendations"].append(
                        f"Found draft {doc_type}: {doc['name']} - Review and submit or delete"
                    )
                elif doc.get("docstatus") == 2:
                    results["recommendations"].append(
                        f"Found cancelled {doc_type}: {doc['name']} - Was created but cancelled"
                    )
                elif doc.get("outstanding_amount", 0) == 0:
                    results["recommendations"].append(
                        f"Invoice {doc['name']} is fully paid - Payment attempts will fail"
                    )
    
    return results