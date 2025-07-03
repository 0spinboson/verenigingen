"""
Analyze payment imports from E-Boekhouden
"""

import frappe
from frappe import _


@frappe.whitelist()
def analyze_payment_distribution():
    """
    Analyze how E-Boekhouden payments are distributed across different document types
    """
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"error": "No default company set"}
    
    # Get E-Boekhouden mutation types and their counts
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Get a sample of mutations to analyze
    result = api.get_mutations(mutation_nr_from=1, mutation_nr_to=1000)
    
    if not result["success"]:
        return {"error": f"Failed to fetch mutations: {result.get('error')}"}
    
    mutation_analysis = {
        "total_mutations": len(result["mutations"]),
        "by_type": {},
        "payment_types": {
            "FactuurbetalingOntvangen": 0,  # Customer payments
            "FactuurbetalingVerstuurd": 0,  # Supplier payments
            "GeldOntvangen": 0,              # Money received
            "GeldUitgegeven": 0              # Money spent
        },
        "invoice_found": {
            "customer_payments": {"found": 0, "not_found": 0},
            "supplier_payments": {"found": 0, "not_found": 0}
        }
    }
    
    # Analyze mutations
    for mut in result["mutations"]:
        mut_type = mut.get("Soort", "Unknown")
        mutation_analysis["by_type"][mut_type] = mutation_analysis["by_type"].get(mut_type, 0) + 1
        
        # Count payment types
        if mut_type in mutation_analysis["payment_types"]:
            mutation_analysis["payment_types"][mut_type] += 1
            
            # Check if invoice would be found
            invoice_no = mut.get("Factuurnummer")
            if invoice_no:
                if mut_type == "FactuurbetalingOntvangen":
                    # Check for sales invoice
                    if frappe.db.exists("Sales Invoice", {"eboekhouden_invoice_number": invoice_no}):
                        mutation_analysis["invoice_found"]["customer_payments"]["found"] += 1
                    else:
                        mutation_analysis["invoice_found"]["customer_payments"]["not_found"] += 1
                        
                elif mut_type == "FactuurbetalingVerstuurd":
                    # Check for purchase invoice
                    if frappe.db.exists("Purchase Invoice", {"eboekhouden_invoice_number": invoice_no}):
                        mutation_analysis["invoice_found"]["supplier_payments"]["found"] += 1
                    else:
                        mutation_analysis["invoice_found"]["supplier_payments"]["not_found"] += 1
    
    # Get actual imported documents in ERPNext
    erpnext_analysis = {
        "payment_entries": {},
        "journal_entries": {},
        "unprocessed_payments": {}
    }
    
    # Count Payment Entries
    pe_count = frappe.db.sql("""
        SELECT 
            payment_type,
            party_type,
            COUNT(*) as count,
            MIN(posting_date) as earliest_date,
            MAX(posting_date) as latest_date
        FROM `tabPayment Entry`
        WHERE company = %s
        AND docstatus = 1
        GROUP BY payment_type, party_type
    """, company, as_dict=True)
    
    for row in pe_count:
        key = f"{row.payment_type} - {row.party_type}"
        erpnext_analysis["payment_entries"][key] = {
            "count": row.count,
            "earliest": str(row.earliest_date),
            "latest": str(row.latest_date)
        }
    
    # Count Journal Entries that are payments
    je_count = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_je,
            SUM(CASE WHEN user_remark LIKE '%%Payment%%' OR user_remark LIKE '%%Betaling%%' THEN 1 ELSE 0 END) as payment_je,
            SUM(CASE WHEN user_remark LIKE '%%Money%%' OR user_remark LIKE '%%Geld%%' THEN 1 ELSE 0 END) as money_je,
            SUM(CASE WHEN eboekhouden_mutation_nr IS NOT NULL THEN 1 ELSE 0 END) as with_mutation_nr,
            SUM(CASE WHEN eboekhouden_invoice_number IS NOT NULL THEN 1 ELSE 0 END) as with_invoice_nr
        FROM `tabJournal Entry`
        WHERE company = %s
        AND docstatus = 1
    """, company, as_dict=True)
    
    if je_count:
        erpnext_analysis["journal_entries"] = je_count[0]
    
    # Sample of unlinked payments (Journal Entries that should have been Payment Entries)
    unlinked_payments = frappe.db.sql("""
        SELECT 
            je.name,
            je.posting_date,
            je.user_remark,
            je.eboekhouden_invoice_number,
            je.total_debit
        FROM `tabJournal Entry` je
        WHERE je.company = %s
        AND je.docstatus = 1
        AND je.eboekhouden_invoice_number IS NOT NULL
        AND (je.user_remark LIKE '%%Payment%%' OR je.user_remark LIKE '%%Betaling%%')
        LIMIT 10
    """, company, as_dict=True)
    
    erpnext_analysis["unprocessed_payments"]["samples"] = unlinked_payments
    erpnext_analysis["unprocessed_payments"]["explanation"] = "These are payments imported as Journal Entries because the related invoice wasn't found"
    
    # Summary and recommendations
    summary = {
        "total_payment_mutations": sum(mutation_analysis["payment_types"].values()),
        "payment_entries_created": sum(row.get("count", 0) for row in pe_count),
        "payment_journal_entries": je_count[0].get("payment_je", 0) if je_count else 0,
        "issues": []
    }
    
    # Identify issues
    if mutation_analysis["invoice_found"]["customer_payments"]["not_found"] > 0:
        summary["issues"].append(f"{mutation_analysis['invoice_found']['customer_payments']['not_found']} customer payments couldn't find matching sales invoices")
    
    if mutation_analysis["invoice_found"]["supplier_payments"]["not_found"] > 0:
        summary["issues"].append(f"{mutation_analysis['invoice_found']['supplier_payments']['not_found']} supplier payments couldn't find matching purchase invoices")
    
    # Calculate conversion rate
    if summary["total_payment_mutations"] > 0:
        conversion_rate = (summary["payment_entries_created"] / summary["total_payment_mutations"]) * 100
        summary["conversion_rate"] = f"{conversion_rate:.1f}%"
        summary["explanation"] = f"Only {conversion_rate:.1f}% of payment mutations became Payment Entries. The rest became Journal Entries."
    
    return {
        "mutation_analysis": mutation_analysis,
        "erpnext_analysis": erpnext_analysis,
        "summary": summary
    }


@frappe.whitelist()
def fix_payment_classifications():
    """
    Convert payment-related Journal Entries to proper Payment Entries where possible
    """
    company = frappe.db.get_single_value("E-Boekhouden Settings", "default_company")
    if not company:
        return {"error": "No default company set"}
    
    # Find journal entries that should be payment entries
    candidates = frappe.db.sql("""
        SELECT 
            je.name,
            je.posting_date,
            je.user_remark,
            je.eboekhouden_invoice_number,
            je.eboekhouden_mutation_nr,
            je.total_debit
        FROM `tabJournal Entry` je
        WHERE je.company = %s
        AND je.docstatus = 1
        AND je.eboekhouden_invoice_number IS NOT NULL
        AND (
            je.user_remark LIKE '%%Payment%%' 
            OR je.user_remark LIKE '%%Betaling%%'
            OR je.user_remark LIKE '%%invoice%%'
            OR je.user_remark LIKE '%%factuur%%'
        )
        LIMIT 100
    """, company, as_dict=True)
    
    converted = 0
    failed = []
    
    for je in candidates:
        try:
            # Check if we can find the invoice now
            invoice_no = je.eboekhouden_invoice_number
            
            # Try sales invoice first
            si_name = frappe.db.get_value("Sales Invoice", 
                {"eboekhouden_invoice_number": invoice_no}, "name")
            
            if si_name:
                # This is a customer payment
                # Would need to analyze the journal entry accounts to recreate as payment entry
                # For now, just report it
                failed.append({
                    "journal_entry": je.name,
                    "invoice": si_name,
                    "type": "Customer Payment",
                    "reason": "Manual conversion needed"
                })
                continue
            
            # Try purchase invoice
            pi_name = frappe.db.get_value("Purchase Invoice",
                {"eboekhouden_invoice_number": invoice_no}, "name")
            
            if pi_name:
                # This is a supplier payment
                failed.append({
                    "journal_entry": je.name,
                    "invoice": pi_name,
                    "type": "Supplier Payment",
                    "reason": "Manual conversion needed"
                })
                continue
                
        except Exception as e:
            failed.append({
                "journal_entry": je.name,
                "error": str(e)
            })
    
    return {
        "candidates_found": len(candidates),
        "converted": converted,
        "failed": failed,
        "message": "Analysis complete. Manual intervention may be needed to convert these Journal Entries to Payment Entries."
    }