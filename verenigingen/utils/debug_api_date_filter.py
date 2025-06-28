import frappe
from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
import json

@frappe.whitelist()
def debug_date_filter():
    """Debug why date filtering isn't working"""
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenAPI(settings)
    
    # Test with very specific date range
    params = {
        "dateFrom": "2025-06-01",
        "dateTo": "2025-06-30"
    }
    
    # Check what URL is being built
    endpoint = "v1/mutation"
    full_url = f"{api.base_url}/{endpoint}"
    
    # Make raw request to see what's happening
    result = api.make_request("v1/mutation", "GET", params)
    
    if result["success"]:
        data = json.loads(result["data"])
        mutations = data.get("items", [])
        
        # Check actual dates in returned data
        date_distribution = {}
        for mut in mutations[:100]:  # Check first 100
            date = mut.get("date", "no_date")
            if date and date != "no_date":
                month_year = date[:7]  # Get YYYY-MM
                date_distribution[month_year] = date_distribution.get(month_year, 0) + 1
        
        return {
            "url": full_url,
            "params_sent": params,
            "total_returned": len(mutations),
            "expected": "~90 (June 2025 only)",
            "date_distribution_sample": dict(sorted(date_distribution.items())[-10:]),  # Last 10 months
            "first_mutation_date": mutations[0].get("date") if mutations else None,
            "last_mutation_date": mutations[-1].get("date") if mutations else None
        }
    else:
        return {"error": result.get("error")}

if __name__ == "__main__":
    print(debug_date_filter())