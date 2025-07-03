import frappe
from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
import json

@frappe.whitelist()
def test_mutation_count():
    """Test mutation count with date range"""
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenAPI(settings)
    
    # Test 1: Get all mutations without date filter
    result_all = api.get_mutations()
    if result_all["success"]:
        data_all = json.loads(result_all["data"])
        count_all = len(data_all.get("items", []))
    else:
        count_all = "Error"
    
    # Test 2: Get mutations for specific date range (matching your migration)
    result_range = api.get_mutations({
        "dateFrom": "2020-06-28",
        "dateTo": "2025-06-27"
    })
    if result_range["success"]:
        data_range = json.loads(result_range["data"])
        count_range = len(data_range.get("items", []))
    else:
        count_range = "Error"
    
    # Test 3: Get mutations for last month only
    result_month = api.get_mutations({
        "dateFrom": "2025-06-01",
        "dateTo": "2025-06-27"
    })
    if result_month["success"]:
        data_month = json.loads(result_month["data"])
        count_month = len(data_month.get("items", []))
    else:
        count_month = "Error"
    
    return {
        "all_mutations": count_all,
        "date_range_mutations": count_range,
        "last_month_mutations": count_month,
        "message": f"Total: {count_all}, Date range (2020-06-28 to 2025-06-27): {count_range}, Last month: {count_month}"
    }

if __name__ == "__main__":
    print(test_mutation_count())