"""
Check actual mutation types from E-Boekhouden
"""

import frappe
from frappe import _
from collections import Counter


@frappe.whitelist()
def check_actual_mutation_types():
    """
    Check what mutation types (Soort) are actually being returned by E-Boekhouden
    """
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Get a sample of mutations
    result = api.get_mutations(mutation_nr_from=1, mutation_nr_to=2000)
    
    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error")
        }
    
    # Count all mutation types
    mutation_types = Counter()
    payment_samples = []
    
    for mut in result["mutations"]:
        soort = mut.get("Soort", "Unknown")
        mutation_types[soort] += 1
        
        # Collect samples of payment types
        if "factuurbet" in soort.lower() or "betaling" in soort.lower():
            payment_samples.append({
                "MutatieNr": mut.get("MutatieNr"),
                "Soort": soort,
                "Soort_length": len(soort),
                "Datum": mut.get("Datum", "")[:10],
                "Factuurnummer": mut.get("Factuurnummer"),
                "Omschrijving": mut.get("Omschrijving", "")[:50]
            })
            
            # Limit samples
            if len(payment_samples) >= 20:
                payment_samples = payment_samples[:20]
    
    # Check if abbreviated versions exist
    abbreviated_found = []
    full_names = {
        "FactuurbetalingOntvangen": "Customer Payment",
        "FactuurbetalingVerstuurd": "Supplier Payment",
        "FactuurOntvangen": "Purchase Invoice",
        "FactuurVerstuurd": "Sales Invoice"
    }
    
    for soort, count in mutation_types.items():
        # Check for potential abbreviations
        if "factbet" in soort.lower() or "fact bet" in soort.lower():
            abbreviated_found.append({
                "found": soort,
                "count": count,
                "likely_full": "Unknown"
            })
            
            # Try to match to full name
            if "ontv" in soort.lower():
                abbreviated_found[-1]["likely_full"] = "FactuurbetalingOntvangen"
            elif "verst" in soort.lower():
                abbreviated_found[-1]["likely_full"] = "FactuurbetalingVerstuurd"
    
    # Check current code expectations vs actual data
    code_expectations = [
        "FactuurVerstuurd",
        "FactuurOntvangen", 
        "FactuurbetalingOntvangen",
        "FactuurbetalingVerstuurd",
        "GeldOntvangen",
        "GeldUitgegeven",
        "Memoriaal"
    ]
    
    missing_in_code = []
    for soort in mutation_types.keys():
        if soort not in code_expectations and soort != "Unknown":
            missing_in_code.append({
                "type": soort,
                "count": mutation_types[soort],
                "status": "Not handled in current code"
            })
    
    return {
        "success": True,
        "total_mutations_checked": len(result["mutations"]),
        "unique_mutation_types": len(mutation_types),
        "mutation_types": dict(mutation_types),
        "abbreviated_types_found": abbreviated_found,
        "payment_samples": payment_samples,
        "missing_in_code": missing_in_code,
        "code_expectations": code_expectations
    }


@frappe.whitelist()
def fix_mutation_type_handling():
    """
    Update the migration code to handle abbreviated mutation types
    """
    
    # First, let's check what types we actually have
    check_result = check_actual_mutation_types()
    
    if not check_result["success"]:
        return check_result
    
    # Generate mapping for abbreviated to full names
    type_mapping = {
        # Full names (already handled)
        "FactuurbetalingOntvangen": "FactuurbetalingOntvangen",
        "FactuurbetalingVerstuurd": "FactuurbetalingVerstuurd",
        "FactuurOntvangen": "FactuurOntvangen",
        "FactuurVerstuurd": "FactuurVerstuurd",
        "GeldOntvangen": "GeldOntvangen",
        "GeldUitgegeven": "GeldUitgegeven",
        "Memoriaal": "Memoriaal",
        
        # Potential abbreviated versions
        "Factbet ontv": "FactuurbetalingOntvangen",
        "Factbet verst": "FactuurbetalingVerstuurd",
        "FactBet Ontv": "FactuurbetalingOntvangen",
        "FactBet Verst": "FactuurbetalingVerstuurd",
        "Factuur betaling ontvangen": "FactuurbetalingOntvangen",
        "Factuur betaling verstuurd": "FactuurbetalingVerstuurd"
    }
    
    # Check if we need to update any mappings based on actual data
    updates_needed = []
    for abbrev in check_result["abbreviated_types_found"]:
        if abbrev["found"] not in type_mapping:
            updates_needed.append({
                "abbreviated": abbrev["found"],
                "suggested_mapping": abbrev["likely_full"],
                "count": abbrev["count"]
            })
    
    return {
        "current_mapping": type_mapping,
        "updates_needed": updates_needed,
        "recommendation": "Update eboekhouden_soap_migration.py to normalize mutation types before processing"
    }