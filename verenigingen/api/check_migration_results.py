import frappe
from frappe import _

@frappe.whitelist()
def check_migration_results():
    """Check results of E-Boekhouden migration"""
    
    # Count imported sales invoices
    sales_invoices = frappe.db.count("Sales Invoice", 
        {"eboekhouden_invoice_number": ["!=", ""]})
    
    # Get sample invoices
    sample_invoices = frappe.get_all("Sales Invoice",
        filters={"eboekhouden_invoice_number": ["!=", ""]},
        fields=["name", "customer", "posting_date", "grand_total", "eboekhouden_invoice_number"],
        limit=5)
    
    # Count payment entries
    payment_entries = frappe.db.count("Payment Entry",
        {"remarks": ["like", "%E-Boekhouden%"]})
    
    # Count journal entries with E-Boekhouden mutation numbers
    journal_entries = frappe.db.count("Journal Entry",
        {"eboekhouden_mutation_nr": ["!=", ""]})
    
    # Get sample journal entries
    sample_journals = frappe.get_all("Journal Entry",
        filters={"eboekhouden_mutation_nr": ["!=", ""]},
        fields=["name", "posting_date", "total_debit", "eboekhouden_mutation_nr", "user_remark"],
        limit=5)
    
    # Check for duplicate mutation numbers
    duplicate_mutations = frappe.db.sql("""
        SELECT eboekhouden_mutation_nr, COUNT(*) as count
        FROM `tabJournal Entry`
        WHERE eboekhouden_mutation_nr IS NOT NULL
        AND eboekhouden_mutation_nr != ''
        GROUP BY eboekhouden_mutation_nr
        HAVING count > 1
    """, as_dict=True)
    
    return {
        "sales_invoices": {
            "count": sales_invoices,
            "samples": sample_invoices
        },
        "payment_entries": {
            "count": payment_entries
        },
        "journal_entries": {
            "count": journal_entries,
            "samples": sample_journals,
            "duplicates": duplicate_mutations
        },
        "summary": f"Imported {sales_invoices} sales invoices, {payment_entries} payment entries, {journal_entries} journal entries"
    }

@frappe.whitelist()
def get_may_2025_import_summary():
    """Get summary of May 2025 imports"""
    
    # Sales invoices from May 2025
    may_invoices = frappe.get_all("Sales Invoice",
        filters={
            "eboekhouden_invoice_number": ["!=", ""],
            "posting_date": ["between", ["2025-05-01", "2025-05-31"]]
        },
        fields=["name", "customer", "posting_date", "grand_total", "eboekhouden_invoice_number"],
        order_by="posting_date desc"
    )
    
    # Journal entries from May 2025
    may_journals = frappe.get_all("Journal Entry",
        filters={
            "eboekhouden_mutation_nr": ["!=", ""],
            "posting_date": ["between", ["2025-05-01", "2025-05-31"]]
        },
        fields=["name", "posting_date", "total_debit", "eboekhouden_mutation_nr", "user_remark"],
        order_by="posting_date desc"
    )
    
    return {
        "may_invoices": {
            "count": len(may_invoices),
            "list": may_invoices[:10]  # First 10
        },
        "may_journals": {
            "count": len(may_journals),
            "list": may_journals[:10]  # First 10
        }
    }