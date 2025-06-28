import frappe
from frappe import _

@frappe.whitelist()
def test_soap_api_dates():
    """Test SOAP API with different date ranges"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Test different date ranges
    test_cases = [
        ("2025-05-01", "2025-05-31", "May 2025"),
        ("2024-05-01", "2024-05-31", "May 2024"),
        ("2025-06-01", "2025-06-30", "June 2025"),
        ("2025-01-01", "2025-12-31", "Full year 2025"),
        ("2024-01-01", "2024-12-31", "Full year 2024"),
    ]
    
    results = []
    
    for date_from, date_to, label in test_cases:
        result = api.get_mutations(date_from=date_from, date_to=date_to)
        
        if result["success"]:
            mutation_types = {}
            for mut in result["mutations"]:
                soort = mut.get("Soort", "Unknown")
                if soort not in mutation_types:
                    mutation_types[soort] = 0
                mutation_types[soort] += 1
            
            results.append({
                "label": label,
                "date_from": date_from,
                "date_to": date_to,
                "total": result["count"],
                "types": mutation_types
            })
        else:
            results.append({
                "label": label,
                "date_from": date_from,
                "date_to": date_to,
                "error": result.get("error")
            })
    
    return {
        "results": results,
        "api_status": "Connected" if api.session_id else "Not connected"
    }

@frappe.whitelist()
def get_all_mutations_count():
    """Get total count of mutations without date filter"""
    
    from verenigingen.utils.eboekhouden_soap_api import EBoekhoudenSOAPAPI
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenSOAPAPI(settings)
    
    # Try without date filter
    result = api.get_mutations()
    
    if result["success"]:
        return {
            "total": result["count"],
            "has_mutations": result["count"] > 0,
            "sample": result["mutations"][:5] if result["mutations"] else []
        }
    else:
        return {"error": result.get("error")}