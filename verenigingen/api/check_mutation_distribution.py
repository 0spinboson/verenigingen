import frappe
from frappe import _

@frappe.whitelist()
def check_all_mutation_types():
    """Check what mutation types are actually in the system"""
    
    results = {}
    
    # 1. Check what mutation types were in error logs
    error_types = frappe.db.sql("""
        SELECT 
            JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.Soort')) as mutation_type,
            COUNT(*) as count
        FROM `tabE-Boekhouden Migration Error`
        WHERE error_details IS NOT NULL
        AND JSON_EXTRACT(error_details, '$.Soort') IS NOT NULL
        GROUP BY mutation_type
        ORDER BY count DESC
    """, as_dict=True)
    
    results["error_mutation_types"] = error_types
    
    # 2. Check for specific types
    specific_checks = {}
    for mut_type in ['GeldOntvangen', 'GeldUitgegeven', 'Memoriaal', 'FactuurVerstuurd', 'FactuurbetalingOntvangen']:
        count = frappe.db.sql("""
            SELECT COUNT(*)
            FROM `tabE-Boekhouden Migration Error`
            WHERE JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.Soort')) = %s
        """, mut_type)[0][0]
        specific_checks[mut_type] = count
    
    results["specific_type_counts"] = specific_checks
    
    # 3. Get the actual mutation count from the SOAP API if possible
    try:
        from ..utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
        settings = frappe.get_single("E-Boekhouden Settings")
        
        if hasattr(settings, 'soap_username') and settings.soap_username:
            api = EBoekhoudenSOAPAPI(
                settings.soap_username,
                settings.get_password('soap_security_code1'),
                settings.get_password('soap_security_code2'),
                settings.soap_guid or ""
            )
            
            # Get mutation count by type
            highest_mutation = api.get_highest_mutation_number()
            if highest_mutation["success"]:
                results["highest_mutation_nr"] = highest_mutation["mutation_nr"]
                
                # Try to get a sample of mutations to see types
                sample_result = api.get_mutations(mutation_nr_from=highest_mutation["mutation_nr"]-100, mutation_nr_to=highest_mutation["mutation_nr"])
                if sample_result["success"]:
                    type_counts = {}
                    for mut in sample_result["mutations"]:
                        soort = mut.get("Soort", "Unknown")
                        type_counts[soort] = type_counts.get(soort, 0) + 1
                    results["sample_mutation_types"] = type_counts
    except Exception as e:
        results["soap_error"] = str(e)
    
    # 4. Summary of what's imported
    results["imported_counts"] = {
        "sales_invoices": frappe.db.count("Sales Invoice", {"eboekhouden_invoice_number": ["!=", ""]}),
        "purchase_invoices": frappe.db.count("Purchase Invoice", {"eboekhouden_invoice_number": ["!=", ""]}),
        "payment_entries": frappe.db.count("Payment Entry", {"eboekhouden_mutation_nr": ["!=", ""]}),
        "journal_entries": frappe.db.count("Journal Entry", {"eboekhouden_mutation_nr": ["!=", ""]})
    }
    
    return results