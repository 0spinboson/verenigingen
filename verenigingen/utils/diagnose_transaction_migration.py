"""
Diagnose transaction migration issues
"""

import frappe
from frappe import _
# from verenigingen.utils.eboekhouden_soap_migration import migrate_transactions_by_mutation_range
from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
import json

@frappe.whitelist()
def diagnose_transaction_types():
    """Analyze what transaction types are in the E-Boekhouden data"""
    try:
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenAPI(settings)
        
        # Get a sample of mutations
        result = api.get_mutations(mutation_nr_from=1, mutation_nr_to=100)
        
        if not result["success"]:
            return {"success": False, "error": result.get("error")}
        
        # Count transaction types
        type_counts = {}
        sample_by_type = {}
        
        for mut in result["mutations"]:
            soort = mut.get("Soort", "Unknown")
            type_counts[soort] = type_counts.get(soort, 0) + 1
            
            # Keep a sample of each type
            if soort not in sample_by_type:
                sample_by_type[soort] = mut
        
        # Get highest mutation number
        highest_result = api.get_highest_mutation_number()
        
        return {
            "success": True,
            "highest_mutation": highest_result.get("highest_mutation_number", 0),
            "sample_size": len(result["mutations"]),
            "type_counts": type_counts,
            "samples": sample_by_type
        }
        
    except Exception as e:
        frappe.log_error(f"Diagnosis error: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def check_existing_invoices():
    """Check what invoices already exist in the system"""
    try:
        sales_invoices = frappe.db.count("Sales Invoice", {
            "eboekhouden_invoice_number": ["is", "set"]
        })
        
        purchase_invoices = frappe.db.count("Purchase Invoice", {
            "eboekhouden_invoice_number": ["is", "set"]
        })
        
        # Get some samples
        sample_si = frappe.db.get_all("Sales Invoice", 
            filters={"eboekhouden_invoice_number": ["is", "set"]},
            fields=["name", "eboekhouden_invoice_number", "posting_date"],
            limit=5
        )
        
        sample_pi = frappe.db.get_all("Purchase Invoice",
            filters={"eboekhouden_invoice_number": ["is", "set"]},
            fields=["name", "eboekhouden_invoice_number", "posting_date"],
            limit=5
        )
        
        return {
            "success": True,
            "sales_invoices_count": sales_invoices,
            "purchase_invoices_count": purchase_invoices,
            "sample_sales_invoices": sample_si,
            "sample_purchase_invoices": sample_pi
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    print("Diagnosing transaction types...")
    result = diagnose_transaction_types()
    print(json.dumps(result, indent=2))
    
    print("\nChecking existing invoices...")
    existing = check_existing_invoices()
    print(json.dumps(existing, indent=2))