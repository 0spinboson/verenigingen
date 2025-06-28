import frappe
from frappe import _

@frappe.whitelist()
def check_negative_payment_terms():
    """Check for mutations with negative payment terms"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    result = api.get_mutations(date_from="2025-05-01", date_to="2025-05-31")
    
    if not result["success"]:
        return {"error": result.get("error")}
    
    negative_terms = []
    zero_terms = []
    
    for mut in result["mutations"]:
        if mut.get("Soort") == "FactuurVerstuurd":
            payment_term = mut.get("Betalingstermijn", "30")
            try:
                term_days = int(payment_term)
                if term_days < 0:
                    negative_terms.append({
                        "invoice": mut.get("Factuurnummer"),
                        "date": mut.get("Datum", "")[:10],
                        "payment_terms": term_days
                    })
                elif term_days == 0:
                    zero_terms.append({
                        "invoice": mut.get("Factuurnummer"),
                        "date": mut.get("Datum", "")[:10],
                        "payment_terms": term_days
                    })
            except:
                pass
    
    return {
        "negative_terms": negative_terms,
        "zero_terms": zero_terms[:5],  # First 5
        "count_negative": len(negative_terms),
        "count_zero": len(zero_terms)
    }