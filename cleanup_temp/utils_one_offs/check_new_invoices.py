"""
Check what invoices are actually new
"""

import frappe
from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI

@frappe.whitelist()
def check_new_invoices():
    """Check what invoices don't exist yet"""
    try:
        # Get all existing invoice numbers
        existing_si_numbers = frappe.db.get_all("Sales Invoice", 
            filters={"eboekhouden_invoice_number": ["!=", ""]},
            pluck="eboekhouden_invoice_number"
        )
        existing_si_set = set(existing_si_numbers)
        
        existing_pi_numbers = frappe.db.get_all("Purchase Invoice",
            filters={"eboekhouden_invoice_number": ["!=", ""]}, 
            pluck="eboekhouden_invoice_number"
        )
        existing_pi_set = set(existing_pi_numbers)
        
        # Sample check - look at recent mutations
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenSOAPAPI(settings)
        
        # Check last 100 mutations
        result = api.get_mutations(mutation_nr_from=7280, mutation_nr_to=7380)
        
        new_sales = 0
        new_purchase = 0
        
        if result["success"]:
            for mut in result["mutations"]:
                soort = mut.get("Soort")
                invoice_no = mut.get("Factuurnummer")
                
                if soort == "FactuurVerstuurd" and invoice_no and invoice_no not in existing_si_set:
                    new_sales += 1
                elif soort == "FactuurOntvangen" and invoice_no and invoice_no not in existing_pi_set:
                    new_purchase += 1
        
        return {
            "success": True,
            "existing_sales_count": len(existing_si_set),
            "existing_purchase_count": len(existing_pi_set),
            "new_sales_in_sample": new_sales,
            "new_purchase_in_sample": new_purchase,
            "sample_size": len(result.get("mutations", [])) if result.get("success") else 0
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    print(check_new_invoices())