"""
Analyze why E-Boekhouden has 15 duplicate entries for mutation 7281
"""

import frappe
from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI

@frappe.whitelist()
def analyze_mutation_7281():
    """Check the source data for mutation 7281"""
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Get mutations around 7281
    result = api.get_mutations_by_number(7280, 7285)
    
    if not result["success"]:
        return {"error": result.get("error")}
    
    # Look for mutation 7281
    mutation_7281_entries = []
    all_mutations = []
    
    for mut in result.get("mutations", []):
        mut_nr = mut.get("MutatieNr")
        all_mutations.append({
            "MutatieNr": mut_nr,
            "Soort": mut.get("Soort"),
            "Datum": mut.get("Datum"),
            "Factuurnummer": mut.get("Factuurnummer")
        })
        
        if mut_nr == "7281":
            mutation_7281_entries.append(mut)
    
    analysis = {
        "total_mutations_retrieved": len(result.get("mutations", [])),
        "mutation_7281_count": len(mutation_7281_entries),
        "all_mutations_summary": all_mutations,
        "mutation_7281_details": mutation_7281_entries[:3] if mutation_7281_entries else None
    }
    
    # Check if this is a data issue in E-Boekhouden
    if len(mutation_7281_entries) > 1:
        analysis["data_quality_issue"] = "E-Boekhouden contains duplicate entries for mutation 7281"
        analysis["recommendation"] = "This is a source data issue, not a migration error"
    
    return analysis

if __name__ == "__main__":
    print(analyze_mutation_7281())