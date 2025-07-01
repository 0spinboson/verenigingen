import frappe
from frappe import _

@frappe.whitelist()
def analyze_missing_mutations():
    """Analyze why thousands of mutations aren't being processed"""
    
    # Get the latest migration
    latest_migration = frappe.get_last_doc("E-Boekhouden Migration", {"migration_status": "Completed"})
    
    results = {
        "migration_name": latest_migration.name,
        "total_records": latest_migration.total_records,
        "imported_records": latest_migration.imported_records,
        "failed_records": latest_migration.failed_records,
        "unprocessed_records": latest_migration.total_records - latest_migration.imported_records - latest_migration.failed_records
    }
    
    # Analyze what mutation types are in the actual SOAP data
    from ..utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    settings = frappe.get_single("E-Boekhouden Settings")
    
    if not settings.soap_username:
        return {"error": "SOAP credentials not configured"}
    
    try:
        api = EBoekhoudenSOAPAPI(
            settings.soap_username,
            settings.get_password('soap_security_code1'),
            settings.get_password('soap_security_code2'),
            settings.soap_guid or ""
        )
        
        # Get a sample of mutations to analyze types
        sample_size = 1000
        highest_mut = api.get_highest_mutation_number()
        
        if highest_mut["success"]:
            # Get sample from different ranges
            mutation_type_counts = {}
            ranges = [
                (1, 500),
                (2000, 2500),
                (4000, 4500),
                (6000, 6500),
                (highest_mut["mutation_nr"] - 500, highest_mut["mutation_nr"])
            ]
            
            total_sampled = 0
            for start, end in ranges:
                if start < 1:
                    start = 1
                if end > highest_mut["mutation_nr"]:
                    end = highest_mut["mutation_nr"]
                    
                result = api.get_mutations(mutation_nr_from=start, mutation_nr_to=end)
                if result["success"]:
                    for mut in result["mutations"]:
                        soort = mut.get("Soort", "Unknown")
                        mutation_type_counts[soort] = mutation_type_counts.get(soort, 0) + 1
                        total_sampled += 1
            
            results["mutation_types_in_soap"] = mutation_type_counts
            results["total_sampled"] = total_sampled
            
            # Check which types are being handled
            handled_types = [
                'FactuurVerstuurd', 'FactuurOntvangen', 
                'FactuurbetalingOntvangen', 'FactuurbetalingVerstuurd',
                'GeldOntvangen', 'GeldUitgegeven', 'Memoriaal'
            ]
            
            unhandled_types = {}
            for mut_type, count in mutation_type_counts.items():
                if mut_type not in handled_types:
                    unhandled_types[mut_type] = count
                    
            results["unhandled_mutation_types"] = unhandled_types
            
            # Estimate total unhandled
            if total_sampled > 0:
                unhandled_count = sum(unhandled_types.values())
                unhandled_percentage = (unhandled_count / total_sampled) * 100
                estimated_unhandled_total = int((unhandled_percentage / 100) * highest_mut["mutation_nr"])
                
                results["unhandled_estimate"] = {
                    "percentage": round(unhandled_percentage, 2),
                    "estimated_total": estimated_unhandled_total
                }
    
    except Exception as e:
        results["soap_error"] = str(e)
    
    # Check what's in the error logs
    error_type_summary = frappe.db.sql("""
        SELECT 
            JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.Soort')) as mutation_type,
            COUNT(*) as count
        FROM `tabE-Boekhouden Migration Error`
        WHERE parent = %s
        GROUP BY mutation_type
    """, latest_migration.name, as_dict=True)
    
    results["error_log_types"] = error_type_summary
    
    # Check for already processed mutations
    processed_counts = {
        "journal_entries": frappe.db.sql("""
            SELECT COUNT(DISTINCT eboekhouden_mutation_nr) as count
            FROM `tabJournal Entry`
            WHERE eboekhouden_mutation_nr IS NOT NULL
            AND eboekhouden_mutation_nr != ''
        """)[0][0],
        "payment_entries": frappe.db.sql("""
            SELECT COUNT(DISTINCT eboekhouden_mutation_nr) as count
            FROM `tabPayment Entry`
            WHERE eboekhouden_mutation_nr IS NOT NULL
            AND eboekhouden_mutation_nr != ''
        """)[0][0],
        "payment_entries_by_ref": frappe.db.sql("""
            SELECT COUNT(DISTINCT reference_no) as count
            FROM `tabPayment Entry`
            WHERE reference_no REGEXP '^[0-9]+$'
        """)[0][0]
    }
    
    results["already_processed"] = processed_counts
    
    return results

@frappe.whitelist()
def check_specific_mutation(mutation_nr):
    """Check if a specific mutation exists and what type it is"""
    
    from ..utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    settings = frappe.get_single("E-Boekhouden Settings")
    
    if not settings.soap_username:
        return {"error": "SOAP credentials not configured"}
        
    api = EBoekhoudenSOAPAPI(
        settings.soap_username,
        settings.get_password('soap_security_code1'),
        settings.get_password('soap_security_code2'),
        settings.soap_guid or ""
    )
    
    # Get the specific mutation
    result = api.get_mutations(mutation_nr_from=int(mutation_nr), mutation_nr_to=int(mutation_nr))
    
    if result["success"] and result["mutations"]:
        mutation = result["mutations"][0]
        
        # Check if it's already processed
        already_processed = {
            "as_journal_entry": frappe.db.exists("Journal Entry", {"eboekhouden_mutation_nr": str(mutation_nr)}),
            "as_payment_entry": frappe.db.exists("Payment Entry", {"eboekhouden_mutation_nr": str(mutation_nr)}),
            "as_payment_ref": frappe.db.exists("Payment Entry", {"reference_no": str(mutation_nr)}),
            "in_error_log": frappe.db.sql("""
                SELECT COUNT(*) 
                FROM `tabE-Boekhouden Migration Error`
                WHERE JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.MutatieNr')) = %s
            """, str(mutation_nr))[0][0]
        }
        
        return {
            "found": True,
            "mutation": mutation,
            "already_processed": already_processed
        }
    else:
        return {
            "found": False,
            "error": result.get("error", "Mutation not found")
        }