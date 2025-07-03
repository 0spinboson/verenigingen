import frappe
import json

@frappe.whitelist()
def test_relation_detail_api():
    """Test different E-Boekhouden API endpoints to get relation details"""
    try:
        response = []
        response.append("=== TESTING E-BOEKHOUDEN RELATION DETAIL APIs ===")
        
        # Get E-Boekhouden API settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Import API class
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        # Test 1: Try the relations list first
        response.append("\n1. Testing v1/relation endpoint...")
        relations_result = api.make_request("v1/relation", "GET", {"limit": 5})
        
        if relations_result["success"]:
            data = json.loads(relations_result["data"])
            response.append(f"   Status: {relations_result['status_code']}")
            response.append(f"   Response keys: {list(data.keys())}")
            
            items = data.get("items", [])
            if items:
                response.append(f"   Found {len(items)} items")
                response.append(f"   First item keys: {list(items[0].keys())}")
                response.append(f"   First item: {items[0]}")
            else:
                response.append("   No items found")
        else:
            response.append(f"   Error: {relations_result.get('error', 'Unknown error')}")
        
        # Test 2: Try to get a specific relation by ID
        response.append("\n2. Testing v1/relation/{id} endpoint...")
        
        # First, get a relation ID from the list
        if relations_result["success"]:
            data = json.loads(relations_result["data"])
            items = data.get("items", [])
            if items and items[0].get("id"):
                relation_id = items[0]["id"]
                response.append(f"   Testing with relation ID: {relation_id}")
                
                detail_result = api.make_request(f"v1/relation/{relation_id}", "GET")
                if detail_result["success"]:
                    detail_data = json.loads(detail_result["data"])
                    response.append(f"   Detail keys: {list(detail_data.keys())}")
                    response.append(f"   Detail data: {detail_data}")
                else:
                    response.append(f"   Detail error: {detail_result.get('error', 'Unknown error')}")
            else:
                response.append("   No relation ID available for testing")
        
        # Test 3: Try supplier-specific endpoint
        response.append("\n3. Testing v1/supplier endpoint...")
        supplier_result = api.make_request("v1/supplier", "GET", {"limit": 5})
        
        if supplier_result["success"]:
            data = json.loads(supplier_result["data"])
            response.append(f"   Status: {supplier_result['status_code']}")
            response.append(f"   Response keys: {list(data.keys())}")
            
            items = data.get("items", [])
            if items:
                response.append(f"   Found {len(items)} suppliers")
                response.append(f"   First supplier keys: {list(items[0].keys())}")
                response.append(f"   First supplier: {items[0]}")
            else:
                response.append("   No suppliers found")
        else:
            response.append(f"   Error: {supplier_result.get('error', 'Unknown error')}")
        
        # Test 4: Try customer endpoint for comparison
        response.append("\n4. Testing v1/customer endpoint...")
        customer_result = api.make_request("v1/customer", "GET", {"limit": 5})
        
        if customer_result["success"]:
            data = json.loads(customer_result["data"])
            response.append(f"   Status: {customer_result['status_code']}")
            response.append(f"   Response keys: {list(data.keys())}")
            
            items = data.get("items", [])
            if items:
                response.append(f"   Found {len(items)} customers")
                response.append(f"   First customer keys: {list(items[0].keys())}")
                response.append(f"   First customer: {items[0]}")
            else:
                response.append("   No customers found")
        else:
            response.append(f"   Error: {customer_result.get('error', 'Unknown error')}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"


@frappe.whitelist()
def get_relation_by_id(relation_id):
    """Get detailed information for a specific relation ID"""
    try:
        response = []
        response.append(f"=== GETTING RELATION DETAIL FOR ID: {relation_id} ===")
        
        # Get E-Boekhouden API settings
        settings = frappe.get_single("E-Boekhouden Settings")
        
        # Import API class
        from verenigingen.utils.eboekhouden_api import EBoekhoudenAPI
        api = EBoekhoudenAPI(settings)
        
        # Try to get the specific relation
        detail_result = api.make_request(f"v1/relation/{relation_id}", "GET")
        
        if detail_result["success"]:
            detail_data = json.loads(detail_result["data"])
            response.append(f"✅ Successfully retrieved relation {relation_id}")
            response.append(f"Status: {detail_result['status_code']}")
            response.append(f"Data keys: {list(detail_data.keys())}")
            response.append(f"Full data:")
            
            for key, value in detail_data.items():
                response.append(f"  {key}: {value}")
        else:
            response.append(f"❌ Failed to get relation {relation_id}")
            response.append(f"Error: {detail_result.get('error', 'Unknown error')}")
            response.append(f"Status: {detail_result.get('status_code', 'Unknown')}")
        
        return "\n".join(response)
        
    except Exception as e:
        return f"Error: {e}\n{frappe.get_traceback()}"