#!/usr/bin/env python3
"""Test REST API endpoints directly"""

import frappe
import requests

@frappe.whitelist()
def test_mutations_endpoint():
    """Test mutations endpoint structure"""
    
    from verenigingen.utils.eboekhouden_rest_client import EBoekhoudenRESTClient
    
    client = EBoekhoudenRESTClient()
    
    # Get session token
    token = client._get_session_token()
    if not token:
        return {"success": False, "error": "Failed to get session token"}
    
    print(f"=== TESTING MUTATIONS ENDPOINT ===\n")
    print(f"Token obtained: {token[:20]}...")
    
    # Test mutations endpoint
    url = f"{client.base_url}/v1/mutation"
    headers = {
        "Authorization": token,
        "Accept": "application/json"
    }
    params = {"limit": 5}  # Just get 5 for testing
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        print(f"\nStatus: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response type: {type(data)}")
            
            if isinstance(data, list):
                print(f"Direct list response with {len(data)} items")
                if data:
                    print(f"\nFirst item type: {type(data[0])}")
                    print(f"First item keys: {list(data[0].keys()) if isinstance(data[0], dict) else 'Not a dict'}")
                    print(f"\nFirst item sample: {data[0]}")
            elif isinstance(data, dict):
                print(f"Dict response with keys: {list(data.keys())}")
                if 'items' in data:
                    items = data['items']
                    print(f"Has 'items' key with {len(items)} items")
                    if items:
                        print(f"\nFirst item: {items[0]}")
            
            return {
                "success": True,
                "response_type": str(type(data)),
                "sample": data[:2] if isinstance(data, list) else data
            }
        else:
            return {
                "success": False,
                "status": response.status_code,
                "error": response.text[:500]
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}