#!/usr/bin/env python3
"""Debug REST API session token"""

import frappe
import requests

@frappe.whitelist()
def debug_session_token():
    """Debug session token creation"""
    
    settings = frappe.get_single("E-Boekhouden Settings")
    api_token = settings.get_password('api_token')
    
    print(f"=== SESSION TOKEN DEBUG ===\n")
    print(f"API URL: {settings.api_url}")
    print(f"API Token exists: {bool(api_token)}")
    print(f"Source App: {settings.source_application}")
    
    session_url = f"{settings.api_url}/v1/session"
    session_data = {
        "accessToken": api_token,
        "source": settings.source_application or "Verenigingen ERPNext"
    }
    
    print(f"\nPOST to: {session_url}")
    print(f"Data: {{'accessToken': '***', 'source': '{session_data['source']}'}}")
    
    try:
        response = requests.post(session_url, json=session_data, timeout=30)
        print(f"\nResponse status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        # Try to get response as text first
        response_text = response.text
        print(f"\nResponse text: {response_text}")
        
        if response.status_code == 200:
            # Check if it's JSON
            try:
                response_json = response.json()
                print(f"\nResponse JSON: {response_json}")
                print(f"Type: {type(response_json)}")
                
                # If it's a string, it might be the token directly
                if isinstance(response_json, str):
                    print(f"\nDirect token response: {response_json[:20]}...")
                    return {"success": True, "token_preview": response_json[:20] + "..."}
                elif isinstance(response_json, dict):
                    token = response_json.get("token")
                    print(f"\nToken from dict: {token[:20] if token else 'None'}...")
                    return {"success": True, "token_preview": token[:20] + "..." if token else "No token field"}
            except:
                print("\nResponse is not JSON")
                # Maybe the response IS the token
                if response_text:
                    print(f"\nDirect text token: {response_text[:20]}...")
                    return {"success": True, "token_preview": response_text[:20] + "..."}
        
        return {"success": False, "error": f"Status {response.status_code}"}
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        return {"success": False, "error": str(e)}