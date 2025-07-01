import frappe
from frappe import _

@frappe.whitelist()
def analyze_mutation_types():
    """Analyze mutation types from SOAP API"""
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    from verenigingen.utils.normalize_mutation_types import normalize_mutation_type
    from collections import defaultdict
    
    # Get settings
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Open session
    session_result = api.open_session()
    if not session_result["success"]:
        return {"error": f"Failed to open session: {session_result.get('error')}"}
    
    # Get mutations from the last month
    date_to = frappe.utils.today()
    date_from = frappe.utils.add_months(date_to, -1)
    
    result = api.get_mutations(date_from=date_from, date_to=date_to)
    
    if not result["success"]:
        return {"error": f"Failed to get mutations: {result.get('error')}"}
    
    mutations = result["mutations"]
    
    # Analyze mutation types
    raw_types = defaultdict(int)
    normalized_types = defaultdict(int)
    type_examples = defaultdict(list)
    
    for mut in mutations:
        raw_type = mut.get("Soort", "Unknown")
        normalized_type = normalize_mutation_type(raw_type)
        
        raw_types[raw_type] += 1
        normalized_types[normalized_type] += 1
        
        # Keep first 3 examples of each type
        if len(type_examples[raw_type]) < 3:
            type_examples[raw_type].append({
                "MutatieNr": mut.get("MutatieNr"),
                "Datum": mut.get("Datum"),
                "Omschrijving": mut.get("Omschrijving", "")[:50],
                "Factuurnummer": mut.get("Factuurnummer"),
                "RelatieCode": mut.get("RelatieCode")
            })
    
    # Check for unhandled types
    handled_types = {
        "FactuurVerstuurd", "FactuurOntvangen", 
        "FactuurbetalingOntvangen", "FactuurbetalingVerstuurd",
        "GeldOntvangen", "GeldUitgegeven", "Memoriaal"
    }
    
    unhandled_raw = [t for t in raw_types.keys() if normalize_mutation_type(t) not in handled_types]
    
    # Calculate percentages
    total = len(mutations)
    raw_type_stats = {}
    normalized_type_stats = {}
    
    for raw_type, count in raw_types.items():
        raw_type_stats[raw_type] = {
            "count": count,
            "percentage": round((count / total) * 100, 1) if total > 0 else 0,
            "examples": type_examples.get(raw_type, [])
        }
    
    for norm_type, count in normalized_types.items():
        normalized_type_stats[norm_type] = {
            "count": count,
            "percentage": round((count / total) * 100, 1) if total > 0 else 0
        }
    
    # Calculate unhandled percentage
    total_unhandled = sum(raw_types[t] for t in unhandled_raw)
    unhandled_percentage = round((total_unhandled / total) * 100, 1) if total > 0 else 0
    
    return {
        "total_mutations": total,
        "date_range": f"{date_from} to {date_to}",
        "raw_types": raw_type_stats,
        "normalized_types": normalized_type_stats,
        "unhandled_raw_types": unhandled_raw,
        "unhandled_count": total_unhandled,
        "unhandled_percentage": unhandled_percentage,
        "handled_types": list(handled_types)
    }