"""
Quick check of transaction migration
"""

import frappe
from frappe import _

@frappe.whitelist()
def quick_check():
    """Quick check of what's happening with transactions"""
    try:
        # Check if we have any sales invoices created from migration
        si_count = frappe.db.sql("""
            SELECT COUNT(*) 
            FROM `tabSales Invoice` 
            WHERE eboekhouden_invoice_number IS NOT NULL 
            AND eboekhouden_invoice_number != ''
        """)[0][0]
        
        # Check if we have any purchase invoices created from migration
        pi_count = frappe.db.sql("""
            SELECT COUNT(*) 
            FROM `tabPurchase Invoice` 
            WHERE eboekhouden_invoice_number IS NOT NULL 
            AND eboekhouden_invoice_number != ''
        """)[0][0]
        
        # Check payment entries
        pe_count = frappe.db.sql("""
            SELECT COUNT(*) 
            FROM `tabPayment Entry` 
            WHERE reference_no IS NOT NULL 
            AND reference_no != ''
            AND reference_no LIKE '%'
        """)[0][0]
        
        # Check journal entries
        je_count = frappe.db.sql("""
            SELECT COUNT(*) 
            FROM `tabJournal Entry` 
            WHERE name LIKE 'JV-%'
        """)[0][0]
        
        # Get sample of what transaction types were processed
        from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenSOAPAPI(settings)
        
        # Get a small sample
        result = api.get_mutations(mutation_nr_from=7000, mutation_nr_to=7100)
        
        type_counts = {}
        if result["success"]:
            for mut in result["mutations"]:
                soort = mut.get("Soort", "Unknown")
                type_counts[soort] = type_counts.get(soort, 0) + 1
        
        return {
            "success": True,
            "existing_counts": {
                "sales_invoices": si_count,
                "purchase_invoices": pi_count,
                "payment_entries": pe_count,
                "journal_entries": je_count
            },
            "sample_transaction_types": type_counts,
            "sample_size": len(result.get("mutations", [])) if result.get("success") else 0
        }
        
    except Exception as e:
        frappe.log_error(f"Quick check error: {str(e)}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    print(quick_check())