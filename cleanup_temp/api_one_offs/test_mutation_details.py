import frappe
from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
import json

@frappe.whitelist()
def test_mutation_details():
    """Test if we can get mutation details with description"""
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api = EBoekhoudenAPI(settings)
    
    # Test 1: Try with different parameters
    tests = []
    
    # Standard call
    result1 = api.make_request("v1/mutation", "GET", {"limit": 5})
    if result1["success"]:
        data = json.loads(result1["data"])
        tests.append({
            "test": "Standard API call",
            "fields": list(data.get("items", [{}])[0].keys()) if data.get("items") else [],
            "sample": data.get("items", [{}])[0] if data.get("items") else {}
        })
    
    # Try with fields parameter
    result2 = api.make_request("v1/mutation", "GET", {
        "limit": 5,
        "fields": "id,date,amount,description,omschrijving,invoiceNumber,type"
    })
    if result2["success"]:
        data = json.loads(result2["data"])
        tests.append({
            "test": "With fields parameter",
            "fields": list(data.get("items", [{}])[0].keys()) if data.get("items") else [],
            "sample": data.get("items", [{}])[0] if data.get("items") else {}
        })
    
    # Try getting a specific mutation by ID if we have one
    first_mutation = None
    if result1["success"]:
        data = json.loads(result1["data"])
        items = data.get("items", [])
        if items and items[0].get("id"):
            first_mutation = items[0].get("id")
    
    if first_mutation:
        # Try to get single mutation details
        result3 = api.make_request(f"v1/mutation/{first_mutation}", "GET")
        if result3["success"]:
            tests.append({
                "test": f"Single mutation detail (ID: {first_mutation})",
                "response": json.loads(result3["data"])
            })
        else:
            tests.append({
                "test": f"Single mutation detail (ID: {first_mutation})",
                "error": result3.get("error", "Failed")
            })
    
    # Check if there's a different endpoint for detailed mutations
    result4 = api.make_request("v1/mutations", "GET", {"limit": 5})
    if result4["success"]:
        data = json.loads(result4["data"])
        tests.append({
            "test": "Plural endpoint /mutations",
            "fields": list(data.get("items", [{}])[0].keys()) if data.get("items") else [],
            "sample": data.get("items", [{}])[0] if data.get("items") else {}
        })
    else:
        tests.append({
            "test": "Plural endpoint /mutations",
            "error": result4.get("error", "Endpoint not found")
        })
    
    return {
        "tests": tests,
        "conclusion": "The API may not expose description/omschrijving fields",
        "recommendation": "Contact E-Boekhouden support to request access to mutation descriptions"
    }

if __name__ == "__main__":
    print(test_mutation_details())