"""
Test if E-Boekhouden API supports pagination
"""

import frappe
import json


@frappe.whitelist()
def test_pagination():
    """
    Test pagination parameters on the ledger endpoint
    """
    try:
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        
        api = EBoekhoudenAPI()
        
        # Try different pagination parameters
        tests = []
        
        # Test 1: Default call
        result1 = api.make_request("v1/ledger")
        if result1["success"]:
            data1 = json.loads(result1["data"])
            tests.append({
                "test": "Default",
                "params": None,
                "count": len(data1.get("items", [])),
                "total_in_response": data1.get("total", "not provided")
            })
        
        # Test 2: With explicit limit
        result2 = api.make_request("v1/ledger", {"limit": 200})
        if result2["success"]:
            data2 = json.loads(result2["data"])
            tests.append({
                "test": "Limit 200",
                "params": {"limit": 200},
                "count": len(data2.get("items", [])),
                "total_in_response": data2.get("total", "not provided")
            })
        
        # Test 3: With offset
        result3 = api.make_request("v1/ledger", {"offset": 100})
        if result3["success"]:
            data3 = json.loads(result3["data"])
            tests.append({
                "test": "Offset 100",
                "params": {"offset": 100},
                "count": len(data3.get("items", [])),
                "total_in_response": data3.get("total", "not provided")
            })
        
        # Test 4: Page parameter
        result4 = api.make_request("v1/ledger", {"page": 2})
        if result4["success"]:
            data4 = json.loads(result4["data"])
            tests.append({
                "test": "Page 2",
                "params": {"page": 2},
                "count": len(data4.get("items", [])),
                "total_in_response": data4.get("total", "not provided")
            })
        
        # Look for account 10460 specifically
        all_accounts = []
        for i in range(5):  # Try first 5 pages
            result = api.make_request("v1/ledger", {"offset": i * 100, "limit": 100})
            if result["success"]:
                data = json.loads(result["data"])
                accounts = data.get("items", [])
                all_accounts.extend(accounts)
                
                # Check if we found 10460
                for acc in accounts:
                    if acc.get("code") == "10460":
                        return {
                            "success": True,
                            "found_10460": True,
                            "account_10460": acc,
                            "found_at_offset": i * 100,
                            "tests": tests
                        }
                
                # If we got fewer accounts than requested, we've reached the end
                if len(accounts) < 100:
                    break
        
        # Filter for account codes starting with 104
        accounts_104x = [acc for acc in all_accounts if acc.get("code", "").startswith("104")]
        
        return {
            "success": True,
            "pagination_tests": tests,
            "total_accounts_retrieved": len(all_accounts),
            "found_10460": False,
            "accounts_starting_104": accounts_104x
        }
        
    except Exception as e:
        frappe.log_error(f"Error testing pagination: {str(e)}")
        return {"success": False, "error": str(e)}