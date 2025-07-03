#!/usr/bin/env python3
"""Debug REST API authentication issues"""

import frappe
import requests

@frappe.whitelist()
def debug_rest_auth():
    """Debug REST API authentication"""
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api_token = settings.get_password('api_token') if hasattr(settings, 'api_token') else None
    
    print(f"=== REST API AUTH DEBUG ===\n")
    print(f"API Token exists: {bool(api_token)}")
    print(f"API Token length: {len(api_token) if api_token else 0}")
    
    if api_token:
        # Check if it's a Bearer token or needs Bearer prefix
        print(f"Token starts with 'Bearer': {'Bearer' in api_token}")
        print(f"Token preview: {api_token[:20]}...")
        
        # Try different auth methods
        headers_options = [
            {
                "name": "Bearer with token",
                "headers": {
                    "Authorization": f"Bearer {api_token}",
                    "Accept": "application/json"
                }
            },
            {
                "name": "Direct token",
                "headers": {
                    "Authorization": api_token,
                    "Accept": "application/json"
                }
            },
            {
                "name": "X-API-Key header",
                "headers": {
                    "X-API-Key": api_token,
                    "Accept": "application/json"
                }
            }
        ]
        
        url = "https://api.e-boekhouden.nl/v1/administration"
        
        for option in headers_options:
            print(f"\n\nTrying: {option['name']}")
            try:
                response = requests.get(url, headers=option['headers'], timeout=10)
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    print("✓ SUCCESS! This auth method works")
                    data = response.json()
                    print(f"Response preview: {str(data)[:200]}...")
                    return {
                        "success": True,
                        "working_method": option['name'],
                        "status_code": response.status_code
                    }
                else:
                    print(f"✗ Failed: {response.text[:200]}")
            except Exception as e:
                print(f"✗ Error: {str(e)}")
    
    return {
        "success": False,
        "message": "No working auth method found"
    }

@frappe.whitelist()
def check_api_url_format():
    """Check if API URL needs adjustment"""
    
    # Try different URL formats
    base_urls = [
        "https://api.e-boekhouden.nl/v1",
        "https://api.e-boekhouden.nl/api/v1", 
        "https://soap.e-boekhouden.nl/api/v1",
        "https://api.e-boekhouden.nl"
    ]
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api_token = settings.get_password('api_token') if hasattr(settings, 'api_token') else None
    
    if not api_token:
        return {"success": False, "error": "No API token configured"}
    
    for base_url in base_urls:
        print(f"\nTrying base URL: {base_url}")
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json"
        }
        
        try:
            # Try a simple endpoint
            test_url = f"{base_url}/administration" if "/v1" in base_url else f"{base_url}/v1/administration"
            response = requests.get(test_url, headers=headers, timeout=10)
            print(f"Full URL: {test_url}")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "working_url": base_url,
                    "message": f"Found working URL: {base_url}"
                }
        except Exception as e:
            print(f"Error: {str(e)}")
    
    return {"success": False, "message": "No working URL format found"}