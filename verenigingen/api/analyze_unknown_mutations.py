import frappe
from frappe import _
import json

@frappe.whitelist()
def analyze_unknown_mutations():
    """Analyze the Unknown mutations from May 2025"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    result = api.get_mutations(date_from="2025-05-01", date_to="2025-05-31")
    
    if not result["success"]:
        return {"error": result.get("error")}
    
    mutations = result["mutations"]
    
    # Analyze Unknown mutations
    unknown_mutations = []
    mutation_types = {}
    
    for mut in mutations:
        soort = mut.get("Soort", "Unknown")
        
        # Count all types
        if soort not in mutation_types:
            mutation_types[soort] = 0
        mutation_types[soort] += 1
        
        # Collect samples of Unknown
        if soort == "Unknown" and len(unknown_mutations) < 10:
            unknown_mutations.append({
                "MutatieNr": mut.get("MutatieNr"),
                "Datum": mut.get("Datum", "")[:10],
                "Omschrijving": mut.get("Omschrijving", "")[:100],
                "Factuurnummer": mut.get("Factuurnummer"),
                "RelatieCode": mut.get("RelatieCode"),
                "Rekening": mut.get("Rekening"),
                "TegenrekeningCode": mut.get("TegenrekeningCode"),
                "MutatieRegels": len(mut.get("MutatieRegels", [])),
                "raw_soort": mut.get("Soort"),
                "all_fields": list(mut.keys())
            })
    
    # Get raw mutation to see actual structure
    raw_sample = None
    for mut in mutations[:5]:
        if mut.get("Soort") == "Unknown":
            raw_sample = mut
            break
    
    return {
        "total_mutations": len(mutations),
        "mutation_types": mutation_types,
        "unknown_samples": unknown_mutations,
        "raw_sample": raw_sample,
        "message": f"Found {mutation_types.get('Unknown', 0)} Unknown mutations out of {len(mutations)} total"
    }

@frappe.whitelist()
def check_mutation_type_values():
    """Check actual Soort values in SOAP response"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Get just a few mutations to check structure
    result = api.get_mutations(date_from="2025-05-01", date_to="2025-05-01")
    
    if not result["success"]:
        return {"error": result.get("error")}
    
    mutations = result["mutations"][:5]
    
    # Debug the actual structure
    debug_info = []
    for mut in mutations:
        debug_info.append({
            "MutatieNr": mut.get("MutatieNr"),
            "Soort_value": mut.get("Soort"),
            "Soort_type": type(mut.get("Soort")).__name__,
            "all_keys": list(mut.keys()),
            "has_Soort": "Soort" in mut
        })
    
    return {
        "mutations_checked": len(mutations),
        "debug_info": debug_info,
        "first_mutation_full": mutations[0] if mutations else None
    }