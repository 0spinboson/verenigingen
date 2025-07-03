"""
Verify mutation type normalization
"""

import frappe
from frappe import _


@frappe.whitelist()
def verify_mutation_type_normalization():
    """
    Verify how mutation types are being normalized
    """
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    from verenigingen.utils.normalize_mutation_types import normalize_mutation_type
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Get a sample of mutations
    result = api.get_mutations(mutation_nr_from=1, mutation_nr_to=500)
    
    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error")
        }
    
    # Track normalization results
    normalization_map = {}
    sample_mutations = []
    
    for mut in result["mutations"]:
        original_soort = mut.get("Soort", "Unknown")
        normalized_soort = normalize_mutation_type(original_soort)
        
        # Track mapping
        if original_soort not in normalization_map:
            normalization_map[original_soort] = {
                "normalized": normalized_soort,
                "count": 0,
                "samples": []
            }
        
        normalization_map[original_soort]["count"] += 1
        
        # Collect samples for payment types
        if "betaling" in original_soort.lower() and len(normalization_map[original_soort]["samples"]) < 3:
            normalization_map[original_soort]["samples"].append({
                "MutatieNr": mut.get("MutatieNr"),
                "Datum": mut.get("Datum", "")[:10],
                "Factuurnummer": mut.get("Factuurnummer"),
                "Omschrijving": mut.get("Omschrijving", "")[:50]
            })
    
    # Summary
    summary = {
        "total_mutations_checked": len(result["mutations"]),
        "unique_original_types": len(normalization_map),
        "normalization_changes": 0
    }
    
    # Check if any normalization occurred
    for original, data in normalization_map.items():
        if original != data["normalized"]:
            summary["normalization_changes"] += 1
    
    return {
        "success": True,
        "summary": summary,
        "normalization_map": normalization_map,
        "message": f"Found {summary['unique_original_types']} unique mutation types. {summary['normalization_changes']} types were normalized."
    }