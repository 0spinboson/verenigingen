import frappe
from frappe import _

@frappe.whitelist()
def analyze_mutation_types():
    """Analyze mutation types in the E-Boekhouden data"""
    
    # First check what's in the error logs
    error_mutations = frappe.db.sql("""
        SELECT 
            JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.Soort')) as mutation_type,
            COUNT(*) as count,
            GROUP_CONCAT(DISTINCT JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.MutatieNr')) LIMIT 5) as sample_mutations
        FROM `tabE-Boekhouden Migration Error`
        WHERE error_details IS NOT NULL
        AND JSON_EXTRACT(error_details, '$.Soort') IS NOT NULL
        GROUP BY mutation_type
        ORDER BY count DESC
    """, as_dict=True)
    
    # Check successfully imported records
    successful_records = {
        "sales_invoices": frappe.db.count("Sales Invoice", {"eboekhouden_invoice_number": ["!=", ""]}),
        "purchase_invoices": frappe.db.count("Purchase Invoice", {"eboekhouden_invoice_number": ["!=", ""]}),
        "payment_entries": frappe.db.count("Payment Entry", {"eboekhouden_mutation_nr": ["!=", ""]}),
        "journal_entries": frappe.db.count("Journal Entry", {"eboekhouden_mutation_nr": ["!=", ""]})
    }
    
    # Check for payment entries by reference_no too
    payment_by_ref = frappe.db.sql("""
        SELECT COUNT(*) as count
        FROM `tabPayment Entry`
        WHERE reference_no REGEXP '^[0-9]+$'
        AND reference_no != ''
    """, as_dict=True)[0].count
    
    # Analyze unrecognized mutation types
    unrecognized = []
    recognized_types = [
        'FactuurVerstuurd', 'FactuurOntvangen', 
        'FactuurbetalingOntvangen', 'FactuurbetalingVerstuurd',
        'GeldOntvangen', 'GeldUitgegeven', 'Memoriaal'
    ]
    
    for mut in error_mutations:
        if mut.mutation_type and mut.mutation_type not in recognized_types:
            unrecognized.append(mut)
    
    # Get sample of recent errors
    recent_errors = frappe.db.sql("""
        SELECT 
            error_type,
            error_message,
            COUNT(*) as count
        FROM `tabE-Boekhouden Migration Error`
        WHERE creation > DATE_SUB(NOW(), INTERVAL 1 DAY)
        GROUP BY error_type, error_message
        ORDER BY count DESC
        LIMIT 10
    """, as_dict=True)
    
    return {
        "mutation_types_in_errors": error_mutations,
        "successful_imports": successful_records,
        "payment_entries_by_reference": payment_by_ref,
        "unrecognized_types": unrecognized,
        "recent_error_patterns": recent_errors
    }

@frappe.whitelist()
def get_mutation_type_samples():
    """Get sample mutations for each type to understand the data structure"""
    
    samples = {}
    
    # Get samples for each mutation type
    mutation_types = frappe.db.sql("""
        SELECT DISTINCT JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.Soort')) as mutation_type
        FROM `tabE-Boekhouden Migration Error`
        WHERE error_details IS NOT NULL
        AND JSON_EXTRACT(error_details, '$.Soort') IS NOT NULL
    """, as_dict=True)
    
    for mt in mutation_types:
        if mt.mutation_type:
            # Get a sample record for this type
            sample = frappe.db.sql("""
                SELECT error_details
                FROM `tabE-Boekhouden Migration Error`
                WHERE JSON_UNQUOTE(JSON_EXTRACT(error_details, '$.Soort')) = %s
                AND error_details IS NOT NULL
                LIMIT 1
            """, mt.mutation_type, as_dict=True)
            
            if sample:
                import json
                try:
                    samples[mt.mutation_type] = json.loads(sample[0].error_details)
                except:
                    samples[mt.mutation_type] = sample[0].error_details
    
    return samples