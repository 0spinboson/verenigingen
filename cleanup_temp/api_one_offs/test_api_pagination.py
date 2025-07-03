import frappe
from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
import json

@frappe.whitelist()
def test_pagination_with_dates():
    """Test if pagination works with date filters"""
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenAPI(settings)
    
    # Test direct API call with limit
    direct_result = api.make_request("v1/mutation", "GET", {
        "dateFrom": "2025-06-01",
        "dateTo": "2025-06-30",
        "limit": 100,
        "offset": 0
    })
    
    if direct_result["success"]:
        data = json.loads(direct_result["data"])
        direct_count = len(data.get("items", []))
        
        # Check if there's a total count in the response
        total_count = data.get("total", None)
        has_more = data.get("hasMore", None)
    else:
        direct_count = 0
        total_count = None
        has_more = None
    
    # Now test with get_mutations which should paginate
    paginated_result = api.get_mutations({
        "dateFrom": "2025-06-01", 
        "dateTo": "2025-06-30"
    })
    
    if paginated_result["success"]:
        paginated_data = json.loads(paginated_result["data"])
        paginated_count = len(paginated_data.get("items", []))
    else:
        paginated_count = 0
    
    # Test without date filter
    no_date_result = api.get_mutations()
    if no_date_result["success"]:
        no_date_data = json.loads(no_date_result["data"])
        no_date_count = len(no_date_data.get("items", []))
    else:
        no_date_count = 0
    
    return {
        "direct_api_count": direct_count,
        "api_total_field": total_count,
        "api_has_more": has_more,
        "paginated_june_2025": paginated_count,
        "no_date_filter": no_date_count,
        "conclusion": "Date filtering is NOT working" if paginated_count == no_date_count else "Date filtering IS working"
    }

if __name__ == "__main__":
    print(test_pagination_with_dates())