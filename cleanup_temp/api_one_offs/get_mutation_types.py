import frappe
from frappe import _

@frappe.whitelist()
def get_all_mutation_types():
    """Get all mutation types from E-Boekhouden SOAP API"""
    try:
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
        
        # Get the highest mutation number
        highest_result = api.get_highest_mutation_number()
        if not highest_result["success"]:
            return {"error": f"Failed to get highest mutation number: {highest_result.get('error')}"}
        
        highest_nr = highest_result["highest_mutation_number"]
        
        # Process in batches
        batch_size = 1000
        all_types = defaultdict(int)
        normalized_types = defaultdict(int)
        type_examples = defaultdict(list)
        total_mutations = 0
        
        # Sample across the entire range
        sample_points = [
            1,  # Start
            int(highest_nr * 0.25),  # 25%
            int(highest_nr * 0.5),   # 50%
            int(highest_nr * 0.75),  # 75%
            max(1, highest_nr - batch_size)  # Near end
        ]
        
        for start_point in sample_points:
            end_point = min(start_point + batch_size - 1, highest_nr)
            
            result = api.get_mutations(mutation_nr_from=start_point, mutation_nr_to=end_point)
            
            if result["success"]:
                mutations = result["mutations"]
                total_mutations += len(mutations)
                
                for mut in mutations:
                    raw_type = mut.get("Soort", "Unknown")
                    normalized_type = normalize_mutation_type(raw_type)
                    
                    all_types[raw_type] += 1
                    normalized_types[normalized_type] += 1
                    
                    # Keep examples
                    if len(type_examples[raw_type]) < 2:
                        type_examples[raw_type].append({
                            "MutatieNr": mut.get("MutatieNr"),
                            "Datum": mut.get("Datum"),
                            "Omschrijving": mut.get("Omschrijving", "")[:80],
                            "Factuurnummer": mut.get("Factuurnummer")
                        })
        
        # Prepare results
        type_stats = []
        for raw_type, count in sorted(all_types.items(), key=lambda x: x[1], reverse=True):
            normalized = normalize_mutation_type(raw_type)
            type_stats.append({
                "raw_type": raw_type,
                "normalized_type": normalized,
                "count": count,
                "percentage": round((count / total_mutations) * 100, 1) if total_mutations > 0 else 0,
                "examples": type_examples.get(raw_type, [])
            })
        
        # Check which types are handled
        handled_types = {
            "FactuurVerstuurd", "FactuurOntvangen", 
            "FactuurbetalingOntvangen", "FactuurbetalingVerstuurd",
            "GeldOntvangen", "GeldUitgegeven", "Memoriaal"
        }
        
        unhandled_stats = []
        handled_stats = []
        
        for stat in type_stats:
            if stat["normalized_type"] in handled_types:
                handled_stats.append(stat)
            else:
                unhandled_stats.append(stat)
        
        total_unhandled = sum(stat["count"] for stat in unhandled_stats)
        unhandled_percentage = round((total_unhandled / total_mutations) * 100, 1) if total_mutations > 0 else 0
        
        return {
            "success": True,
            "highest_mutation_number": highest_nr,
            "total_sampled": total_mutations,
            "sample_ranges": [f"{sp}-{min(sp + batch_size - 1, highest_nr)}" for sp in sample_points],
            "all_types": type_stats,
            "handled_types": handled_stats,
            "unhandled_types": unhandled_stats,
            "unhandled_count": total_unhandled,
            "unhandled_percentage": unhandled_percentage,
            "summary": {
                "total_unique_raw_types": len(all_types),
                "total_unique_normalized_types": len(normalized_types),
                "handled_type_names": list(handled_types)
            }
        }
        
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }