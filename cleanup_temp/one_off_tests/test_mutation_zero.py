import frappe
from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI

@frappe.whitelist()
def test_mutation_zero():
    """Test if mutation 0 (initial balances) can be retrieved via REST API"""
    try:
        settings = frappe.get_single("E-Boekhouden Settings")
        api = EBoekhoudenAPI(settings)
        
        results = {}
        
        # Test 1: Try to get mutation by ID 0 directly
        try:
            result = api.make_request("v1/mutation/0", "GET")
            results["mutation_0_direct"] = {
                "success": result["success"],
                "status_code": result.get("status_code"),
                "data_preview": result.get("data", "")[:500] if result["success"] else result.get("error", "")
            }
        except Exception as e:
            results["mutation_0_direct"] = {"error": str(e)}
        
        # Test 2: Try to get mutations with very early date range to catch initial balances
        try:
            # Use a very early date range that should include initial balances
            params = {
                "dateFrom": "1900-01-01",
                "dateTo": "2000-01-01",
                "limit": 10
            }
            result = api.get_mutations(params)
            results["early_date_range"] = {
                "success": result["success"],
                "status_code": result.get("status_code")
            }
            
            if result["success"]:
                import json
                data = json.loads(result["data"])
                mutations = data.get("items", [])
                results["early_date_range"]["count"] = len(mutations)
                
                # Look for mutation 0 or very low IDs
                if mutations:
                    first_mutation = mutations[0]
                    results["early_date_range"]["first_mutation"] = {
                        "id": first_mutation.get("id"),
                        "date": first_mutation.get("date"),
                        "description": first_mutation.get("description"),
                        "all_fields": list(first_mutation.keys())
                    }
                    
                    # Check if any have ID 0 or very low IDs
                    low_id_mutations = [m for m in mutations if m.get("id", 999999) < 10]
                    results["early_date_range"]["low_id_mutations"] = low_id_mutations
            else:
                results["early_date_range"]["error"] = result.get("error")
                
        except Exception as e:
            results["early_date_range"] = {"error": str(e)}
        
        # Test 3: Try to get mutations without date filter to see if we get all mutations
        try:
            params = {"limit": 20}
            result = api.get_mutations(params)
            results["no_date_filter"] = {
                "success": result["success"],
                "status_code": result.get("status_code")
            }
            
            if result["success"]:
                import json
                data = json.loads(result["data"])
                mutations = data.get("items", [])
                results["no_date_filter"]["count"] = len(mutations)
                
                if mutations:
                    # Sort by ID to see the lowest IDs
                    sorted_mutations = sorted(mutations, key=lambda x: x.get("id", 999999))
                    results["no_date_filter"]["lowest_id_mutations"] = sorted_mutations[:5]
                    results["no_date_filter"]["highest_id_mutations"] = sorted_mutations[-5:]
            else:
                results["no_date_filter"]["error"] = result.get("error")
                
        except Exception as e:
            results["no_date_filter"] = {"error": str(e)}
        
        # Test 4: Try to access mutations endpoint directly with specific parameters
        try:
            # Try with offset 0 to get the very first mutations
            params = {
                "limit": 50,
                "offset": 0
            }
            result = api.make_request("v1/mutation", "GET", params)
            results["offset_zero"] = {
                "success": result["success"],
                "status_code": result.get("status_code")
            }
            
            if result["success"]:
                import json
                data = json.loads(result["data"])
                mutations = data.get("items", [])
                results["offset_zero"]["count"] = len(mutations)
                
                if mutations:
                    # Look for mutation 0 specifically
                    mutation_zero = next((m for m in mutations if m.get("id") == 0), None)
                    results["offset_zero"]["mutation_zero_found"] = bool(mutation_zero)
                    if mutation_zero:
                        results["offset_zero"]["mutation_zero_data"] = mutation_zero
                    
                    # Show ID range
                    ids = [m.get("id") for m in mutations if m.get("id") is not None]
                    if ids:
                        results["offset_zero"]["id_range"] = {
                            "min": min(ids),
                            "max": max(ids),
                            "all_ids": sorted(ids)[:10]  # First 10 IDs
                        }
            else:
                results["offset_zero"]["error"] = result.get("error")
                
        except Exception as e:
            results["offset_zero"] = {"error": str(e)}
        
        return {
            "success": True,
            "results": results,
            "summary": "Tested multiple approaches to find mutation 0 (initial balances)"
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }