"""
Analyze mutation counts by type
"""

import frappe
from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
import json

@frappe.whitelist()
def analyze_mutations():
    """Analyze all mutations to understand what should be imported"""
    try:
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenSOAPAPI(settings)
        
        # Get mutations in batches and count by type
        type_counts = {}
        invoice_samples = {
            "FactuurVerstuurd": [],
            "FactuurOntvangen": []
        }
        
        # Process in batches of 500
        batch_size = 500
        for start in range(1, 7381, batch_size):
            end = min(start + batch_size - 1, 7380)
            result = api.get_mutations(mutation_nr_from=start, mutation_nr_to=end)
            
            if result["success"]:
                for mut in result["mutations"]:
                    soort = mut.get("Soort", "Unknown")
                    type_counts[soort] = type_counts.get(soort, 0) + 1
                    
                    # Collect samples of invoices
                    if soort == "FactuurVerstuurd" and len(invoice_samples["FactuurVerstuurd"]) < 5:
                        invoice_samples["FactuurVerstuurd"].append({
                            "MutatieNr": mut.get("MutatieNr"),
                            "Factuurnummer": mut.get("Factuurnummer"),
                            "Datum": mut.get("Datum"),
                            "RelatieCode": mut.get("RelatieCode")
                        })
                    elif soort == "FactuurOntvangen" and len(invoice_samples["FactuurOntvangen"]) < 5:
                        invoice_samples["FactuurOntvangen"].append({
                            "MutatieNr": mut.get("MutatieNr"),
                            "Factuurnummer": mut.get("Factuurnummer"),
                            "Datum": mut.get("Datum"),
                            "RelatieCode": mut.get("RelatieCode")
                        })
        
        # Check existing counts
        existing_si = frappe.db.count("Sales Invoice", {"eboekhouden_invoice_number": ["!=", ""]})
        existing_pi = frappe.db.count("Purchase Invoice", {"eboekhouden_invoice_number": ["!=", ""]})
        
        return {
            "success": True,
            "mutation_type_counts": type_counts,
            "existing_in_erpnext": {
                "sales_invoices": existing_si,
                "purchase_invoices": existing_pi
            },
            "invoice_samples": invoice_samples
        }
        
    except Exception as e:
        frappe.log_error(f"Analysis error: {str(e)}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    result = analyze_mutations()
    print(json.dumps(result, indent=2))